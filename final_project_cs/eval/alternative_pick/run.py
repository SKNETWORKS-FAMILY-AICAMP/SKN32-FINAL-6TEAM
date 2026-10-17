# -*- coding: utf-8 -*-
"""대체 후보 1순위 판정 실행기 — 사례마다 운영과 같은 함수로 LLM 을 부르고 관측을 그대로 남긴다. 채점은 `score` 가 한다.

    python -m eval.alternative_pick.run --cases eval/alternative_pick/cases.jsonl          # 사례 × 3회 + 순서 섞기 40 × 2
    python -m eval.alternative_pick.run --cases eval/alternative_pick/cases_smoke.jsonl --dry-run   # 외부 호출 없음
    python -m eval.alternative_pick.run --resume eval/reports/alternative_pick/<run>       # 끊긴 실행 이어서

★운영 경로 그대로 — `alternative_order.preference_inputs` · `payload` · `schema` · `apply` 를 쓰고, 어댑터는
  `OpenAIResponsesJudgeLLM`, 시간 제한은 가드레일 `travel.activity_judge.alternative_order_timeout_seconds` 다.
  단서가 없어 운영이 부르지 않는 사례는 부르지 않는다(`status=not_called`).
★지시문은 기본이 DB 등록 프롬프트(`--prompt db` — 감사 기록이 남는다). 등록 전이면 시작 전에 멈춘다 —
  440번을 모두 「호출 실패」로 세면 M6e 가 환경 문제로 채워진다(계획서 §5). `--prompt file` 은 파일 최신판을 넘긴다.
★실호출을 아낀다(계획서 §4) — 관측은 끝나는 대로 `results.jsonl` 에 한 줄씩 붙인다. 끊기면 `--resume` 으로
  남은 것만 부른다. 같은 실행 폴더에 같은 관측(사례 · 변형 · 회차)을 두 번 쓰지 않는다.
★M8(위치 편향): 사례 `--shuffle-cases` 건을 seed 로 뽑아 후보 순서를 섞은 판 `--shuffles` 개를 한 번씩 부른다.
  섞은 판에서는 섞인 순서가 「코드 순서」다(운영에서 모델이 받는 모양 그대로).
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from app.domains.travel_ops.instances.activity import alternative_order

from .build import DATASET, load_cases

REPORTS = Path(__file__).resolve().parents[1] / "reports" / "alternative_pick"
SCHEMA_NAME = "activity_alternative_order"
#: (body) → JudgeCall 비슷한 것(`output` · `model` · 토큰 · `latency_ms`)
Ask = Callable[[dict[str, Any]], Awaitable[Any]]


def pool_of(case: dict, order: list[str] | None = None) -> list[dict]:
    """운영 `alternatives` 항목 모양(`contentid` · `title` · `reason` · `distance_km`)으로 — `apply` 가 그대로 받는다."""
    rows = {c["id"]: c for c in case["inputs"]["candidates"]}
    ids = order or [c["id"] for c in case["inputs"]["candidates"]]
    return [{"contentid": i, "title": rows[i]["title"], "reason": rows[i]["code_reason"],
             "distance_km": rows[i]["distance_km"]} for i in ids]


def classes_of(case: dict) -> dict[str, str]:
    return {c["id"]: c["class"] for c in case["inputs"]["candidates"]}


def shuffle_plan(cases: list[dict], *, n_cases: int, n_shuffles: int, seed: int) -> dict[str, list[list[str]]]:
    """사례 id → 섞은 순서들. 원래 순서와 같은 것은 빼고, 1순위 자리가 바뀌는 순열을 먼저 쓴다."""
    rng = random.Random(seed)
    picked = rng.sample(cases, min(n_cases, len(cases)))
    plan: dict[str, list[list[str]]] = {}
    for case in sorted(picked, key=lambda c: c["case_id"]):
        ids = [c["id"] for c in case["inputs"]["candidates"]]
        perms = [list(p) for p in itertools.permutations(ids) if list(p) != ids]
        moved = [p for p in perms if p[0] != ids[0]]
        rest = [p for p in perms if p[0] == ids[0]]
        rng.shuffle(moved)
        rng.shuffle(rest)
        plan[case["case_id"]] = (moved + rest)[:n_shuffles]
    return plan


def jobs(cases: list[dict], *, repeats: int, plan: dict[str, list[list[str]]]) -> list[tuple[dict, str, int, list[str]]]:
    """(사례, 변형, 회차, 보낼 순서) — 변형 `base` 는 코드 순서, `shuffle-k` 는 섞은 순서."""
    out = []
    for case in cases:
        ids = [c["id"] for c in case["inputs"]["candidates"]]
        out += [(case, "base", r, ids) for r in range(1, repeats + 1)]
        out += [(case, f"shuffle-{k}", 1, order) for k, order in enumerate(plan.get(case["case_id"], []), start=1)]
    return out


async def observe(case: dict, variant: str, repeat: int, order: list[str], ask: Ask, timeout: float) -> dict:
    """한 관측 — 운영 `_order_alternatives`(llm 모드)와 같은 순서로 부르고 검증한다."""
    pool = pool_of(case, order)
    pref = case["inputs"]["preference"]
    preference = alternative_order.preference_inputs(pref.get("survey"), pref.get("customer_text"))
    row: dict[str, Any] = {"case_id": case["case_id"], "variant": variant, "repeat": repeat, "pool": order,
                           "status": "ok", "error": None, "output": None, "applied": None}
    if preference is None:
        row["status"] = "not_called"
        return row
    body = alternative_order.payload(case["inputs"]["origin"], pool, preference, classes_of(case))
    try:
        call = await asyncio.wait_for(ask(body), timeout=timeout)
    except (TimeoutError, asyncio.TimeoutError):
        row.update(status="llm_timeout")
        return row
    except Exception as exc:  # noqa: BLE001 — 429 · 키 없음 · 프롬프트 미등록 — 운영처럼 종류만 남긴다
        row.update(status="llm_error", error=f"{type(exc).__name__}: {str(exc)[:200]}")
        return row
    output = getattr(call, "output", None)
    applied = alternative_order.apply(pool, output)
    row.update(output=output, applied=applied[1] if applied else None, model=getattr(call, "model", None),
               **{k: getattr(call, k, None) for k in ("latency_ms", "input_tokens", "output_tokens", "reasoning_tokens")})
    return row


def done_keys(results: Path) -> set[tuple[str, str, int]]:
    if not results.exists():
        return set()
    rows = [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {(r["case_id"], r["variant"], r["repeat"]) for r in rows}


async def run(todo: list[tuple[dict, str, int, list[str]]], ask: Ask, *, timeout: float, concurrency: int,
              results: Path) -> int:
    gate = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    count = 0

    async def one(case: dict, variant: str, repeat: int, order: list[str]) -> None:
        nonlocal count
        async with gate:
            row = await observe(case, variant, repeat, order, ask, timeout)
        async with lock:
            with results.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
        first = (row["applied"] or {}).get("ids", [None])[0]
        print(f"  {row['case_id']:<6} {variant:<9} r{repeat} {row['status']:<11} 1순위={first}", flush=True)

    await asyncio.gather(*(one(*job) for job in todo))
    return count


def dry_run_ask() -> Ask:
    """외부 호출 없음 — 받은 순서 그대로 · 취향 안 씀. 실행 · 채점 경로 점검용."""
    async def ask(body: dict[str, Any]) -> Any:
        from types import SimpleNamespace

        return SimpleNamespace(output={"order": [c["id"] for c in body["candidates"]], "used_preference": False,
                                       "reason": ""}, model="dry-run", latency_ms=0, input_tokens=0, output_tokens=0,
                               reasoning_tokens=0)
    return ask


def live_ask(prompt: str, model: str | None) -> Ask:
    from app.domains.travel_ops.instances.activity.judge.llm import file_instructions
    from app.infrastructure.llm.openai_responses import OpenAIResponsesJudgeLLM

    if prompt == "db":
        from app.infrastructure.db.session import get_connection

        llm = OpenAIResponsesJudgeLLM(connection_factory=get_connection)
        instructions = None
    else:
        llm = OpenAIResponsesJudgeLLM()
        instructions = file_instructions(alternative_order.KIND)

    async def ask(body: dict[str, Any]) -> Any:
        return await llm.judge(alternative_order.PROMPT_KEY, body, schema=alternative_order.schema(),
                               schema_name=SCHEMA_NAME, web_search=False, instructions=instructions, model=model)
    return ask


def preflight(prompt: str) -> dict[str, Any]:
    """부르기 전에 환경을 본다 — 키 · 프롬프트. 안 되면 멈춘다(환경 탓 실패로 관측을 채우지 않는다)."""
    from app.core.settings import get_settings

    if not get_settings().openai_api_key.strip():
        raise SystemExit("OpenAI 키가 없다 — 환경을 먼저 고친다")
    if prompt == "db":
        from app.infrastructure.db.session import get_connection
        from app.infrastructure.llm._registry import load_active_prompt

        try:
            prompt_id, template = load_active_prompt(get_connection, alternative_order.PROMPT_KEY)
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(f"프롬프트 {alternative_order.PROMPT_KEY} 를 읽지 못했다 — {exc}. "
                             "등록하거나 --prompt file 로 부른다") from exc
        return {"prompt": "db", "prompt_id": str(prompt_id), "prompt_chars": len(template)}
    from app.domains.travel_ops.instances.activity.judge.llm import file_instructions

    text = file_instructions(alternative_order.KIND)
    if not text:
        raise SystemExit("프롬프트 파일이 없다")
    return {"prompt": "file", "prompt_chars": len(text)}


def prompt_file_version() -> str | None:
    from app.core.settings import REPO_ROOT
    from app.domains.travel_ops.instances.activity.judge.llm import PROMPT_DIR

    files = sorted((REPO_ROOT / "prompts" / PROMPT_DIR).glob(f"{alternative_order.KIND}.v*.md"),
                   key=lambda p: int(p.name.rsplit(".v", 1)[1].removesuffix(".md")))
    return files[-1].name if files else None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DATASET)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--shuffle-cases", type=int, default=40, help="M8 위치 편향용 사례 수(0 이면 섞지 않음)")
    parser.add_argument("--shuffles", type=int, default=2)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--prompt", choices=("db", "file"), default="db")
    parser.add_argument("--model", help="기본은 설정 activity_judge_model")
    parser.add_argument("--dry-run", action="store_true", help="외부 호출 없이 받은 순서 그대로 답한다")
    parser.add_argument("--resume", type=Path, help="끊긴 실행 폴더 — 조건을 그대로 읽어 남은 관측만 부른다")
    args = parser.parse_args(argv)

    from app.core.settings import get_guardrails, get_settings

    if args.resume:
        out = args.resume
        conditions = json.loads((out / "conditions.json").read_text(encoding="utf-8"))
        cases, manifest = load_cases(Path(conditions["cases_file"]))
        if manifest["inputs_sha256"] != conditions["inputs_sha256"]:
            raise SystemExit("사례 입력이 실행 때와 다르다 — 이어서 부르지 않는다")
    else:
        cases, manifest = load_cases(args.cases)
        settings = get_settings()
        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + ("-dry" if args.dry_run else "")
        out = REPORTS / run_id
        conditions = {
            "eval_run": run_id, "cases_file": str(args.cases.resolve()), "inputs_sha256": manifest["inputs_sha256"],
            "dataset_sha256": manifest["sha256"], "split": manifest["split"], "smoke": manifest.get("smoke", False),
            "labeler": manifest.get("labeler"), "cases": len(cases), "repeats": args.repeats,
            "shuffle": {"cases": args.shuffle_cases, "per_case": args.shuffles, "seed": args.seed},
            "dry_run": args.dry_run, "model": "dry-run" if args.dry_run else (args.model or settings.activity_judge_model),
            "reasoning_effort": settings.activity_judge_reasoning_effort, "web_search": False,
            "prompt_file": prompt_file_version(),
            "timeout_s": float(get_guardrails().get("travel.activity_judge.alternative_order_timeout_seconds")),
            "temperature": None, "seed_model": None,
        }
        if not args.dry_run:
            conditions.update(preflight(args.prompt))
        out.mkdir(parents=True, exist_ok=False)
        (out / "conditions.json").write_text(json.dumps(conditions, ensure_ascii=False, indent=1) + "\n",
                                             encoding="utf-8")

    results = out / "results.jsonl"
    plan = (shuffle_plan(cases, n_cases=conditions["shuffle"]["cases"], n_shuffles=conditions["shuffle"]["per_case"],
                         seed=conditions["shuffle"]["seed"]) if conditions["shuffle"]["cases"] else {})
    seen = done_keys(results)
    todo = [j for j in jobs(cases, repeats=conditions["repeats"], plan=plan) if (j[0]["case_id"], j[1], j[2]) not in seen]
    print(json.dumps({**conditions, "todo": len(todo), "already": len(seen)}, ensure_ascii=False))
    if conditions["dry_run"]:
        ask = dry_run_ask()
    else:
        if args.resume:
            preflight(conditions["prompt"])
        ask = live_ask(conditions.get("prompt", "db"), None if conditions["model"] == get_settings().activity_judge_model
                       else conditions["model"])
    written = asyncio.run(run(todo, ask, timeout=conditions["timeout_s"], concurrency=args.concurrency, results=results))
    print(f"\n관측 {written}건 → {results}\n채점: python -m eval.alternative_pick.score {out}")


if __name__ == "__main__":
    main()

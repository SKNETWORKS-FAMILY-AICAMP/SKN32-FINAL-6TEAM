# -*- coding: utf-8 -*-
"""계획 읽기 묶음 나누기 측정 — 긴 계획(`cases.py`)을 묶음 크기별로 `intake/pipeline.read_source` 에 넣고 모델 시간 · 정확도를 잰다. `[2026-10-16]`

    python -m eval.intake_chunking.run --ollama <x600 과 같은 구성의 Ollama 주소> --model tripilot-pointer:e4b-ft --num-ctx 8192 \\
        --sizes 0,4,8,12,16 --repeat 2 --out <결과 폴더>
    python -m eval.intake_chunking.run --api --api-model gpt-6-luna --api-key-file <서버용 키 파일> --sizes 0,8 --cases L1,L4 --api-cap 40 --out <폴더>

★제품 함수 그대로 부른다 — `read_source(chunk_lines=…, reading_seconds=0)`(전체 상한 없음 — 묶음마다 끝까지 기다려 시간 분포를 본다).
  모델 객체는 x600 서버와 같은 `OllamaChat`(think=false · 온도 0 · JSON · num_ctx 8192)이고, 시간 한도는 넉넉히(120초) 둬 **한도에 안 걸린 실제 시간**을 잰다.
★Ollama 응답의 `prompt_eval_count`(새로 읽은 입력 토큰) · `prompt_eval_duration` · `eval_count` · `eval_duration` 를 호출마다 남긴다 —
  묶음마다 지시문을 다시 읽는 비용(b)을 본다(Ollama 는 앞 호출과 같은 앞부분을 다시 계산하지 않을 수 있다 — 그 값이 그대로 나온다).
★순서 효과를 줄이려고 묶음 크기 순서를 건마다 · 반복마다 돌린다(A · B · A · B 교대 — 전역 규칙 §6).
★유료(`--api`): 서버용 키로 `OpenAIChat` 을 부른다(넘김 장치 없이 유료만). 호출 수 상한 `--api-cap`(이 실행 안에서 센다) — 서버의 하루 상한 표(DB)를 쓰지 않으므로 대신 막는다.
★장소 찾기(관광공사 · 카카오)는 하지 않는다 — 재는 것은 남은 줄 모델 단계다.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
KST = ZoneInfo("Asia/Seoul")


class Meter:
    """모델 호출마다 시간 · Ollama 통계를 남긴다. 겉모양(`json`)은 그대로."""

    def __init__(self, inner: Any, stats: list[dict[str, Any]], cap: int = 0) -> None:
        self.inner, self.calls, self.stats, self.cap, self.used = inner, [], stats, cap, 0

    def json(self, system: str, user: str) -> dict[str, Any]:
        if self.cap and self.used >= self.cap:
            raise RuntimeError("이 실행의 유료 호출 상한을 넘었다")
        self.used += 1
        lines = user.count("\n") + 1
        before = len(self.stats)
        started = time.perf_counter()
        try:
            out = self.inner.json(system, user)
            error = None
            return out
        except Exception as exc:                  # noqa: BLE001 — 기록만 하고 그대로 던진다(제품이 그 묶음만 남은 줄로 둔다)
            error = f"{type(exc).__name__}: {exc}"[:200]
            raise
        finally:
            stat = self.stats[before] if len(self.stats) > before else {}
            self.calls.append({"lines": lines, "chars": len(user), "seconds": round(time.perf_counter() - started, 3),
                               "error": error, **stat})


def ollama_transport(stats: list[dict[str, Any]], timeout: float):
    import httpx

    def post(url: str, payload: dict[str, Any]) -> httpx.Response:
        response = httpx.post(url, json=payload, timeout=httpx.Timeout(timeout, connect=5.0))
        try:
            body = response.json()
            stats.append({k: body.get(k) for k in ("prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration",
                                                   "load_duration", "total_duration")})
        except ValueError:
            stats.append({})
        return response

    return post


def predict(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from eval.intake_diverse.run_current import adapt

    return adapt(rows)


def pct(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    k = (len(ordered) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ollama", default="")
    parser.add_argument("--model", default="tripilot-pointer:e4b-ft")
    parser.add_argument("--num-ctx", type=int, default=8192)
    parser.add_argument("--api", action="store_true")
    parser.add_argument("--api-model", default="gpt-6-luna")
    parser.add_argument("--api-key-file", default="")
    parser.add_argument("--api-cap", type=int, default=40)
    parser.add_argument("--sizes", default="0,4,8,12,16")
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--cases", default="")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    sys.path.insert(0, str(HERE.parents[1]))
    from eval.intake_diverse.run_current import _DUMMY_ENV
    for key, value in _DUMMY_ENV.items():
        os.environ.setdefault(key, value)
    from app.domains.travel_ops.components.intake.pipeline import read_source
    from app.domains.travel_ops.components.intake.rules import read_plan
    from eval.intake_chunking.cases import all_cases
    from eval.intake_diverse.score import score_case

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    cases = [c for c in all_cases() if not args.cases or c["case_id"] in args.cases.split(",")]
    stats: list[dict[str, Any]] = []
    if args.api:
        from app.infrastructure.llm_failover import OpenAIChat
        key = ""
        for line in Path(args.api_key_file).read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("ACOP_OPENAI_API_KEY_SERVER="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
        if not key:
            raise SystemExit("서버용 키가 파일에 없다(ACOP_OPENAI_API_KEY_SERVER)")
        inner: Any = OpenAIChat(api_key=key, model=args.api_model, timeout=args.timeout)
        backend = f"openai:{args.api_model}"
    else:
        from app.infrastructure.ollama_chat import OllamaChat
        inner = OllamaChat(base_url=args.ollama, model=args.model, timeout=args.timeout, keep_alive="30m", num_ctx=args.num_ctx,
                           transport=ollama_transport(stats, args.timeout))
        inner.warm()
        backend = f"ollama:{args.model}"
    meter = Meter(inner, stats, cap=args.api_cap if args.api else 0)

    runs: list[dict[str, Any]] = []
    with (out / "runs.jsonl").open("a", encoding="utf-8") as log:
        for rep in range(args.repeat):
            for index, case in enumerate(cases):
                shift = (index + rep) % len(sizes)
                order = sizes[shift:] + sizes[:shift]            # 크기 순서를 건마다 · 반복마다 돌린다
                if rep % 2:
                    order = order[::-1]
                unread = len(read_plan(case["text"]).unread_lines)
                for size in order:
                    meter.calls = []
                    progress: list[dict[str, Any]] = []
                    started = time.perf_counter()
                    error = None
                    try:
                        rows = read_source(case["text"], chat=meter, today=date.fromisoformat(case["today"]),
                                           now=datetime(2026, 10, 16, 9, 0, tzinfo=KST), chunk_lines=size, reading_seconds=0,
                                           on_reading=progress.append)
                    except Exception as exc:              # noqa: BLE001
                        rows, error = [], f"{type(exc).__name__}: {exc}"[:300]
                    seconds = time.perf_counter() - started
                    pred = {"case_id": case["case_id"], "error": error, "seconds": seconds, **predict(rows)}
                    score = score_case({"case_id": case["case_id"], "source_text": case["text"], "gold": case["gold"]}, pred)
                    report = next((r["value"] for r in rows if r.get("field") == "reading.llm"), {}) or {}
                    run = {"rep": rep, "case": case["case_id"], "unread": unread, "size": size, "backend": backend,
                           "model_seconds": round(sum(c["seconds"] for c in meter.calls), 3), "calls": meter.calls,
                           "progress": progress, "report_error": report.get("error"), "accepted": report.get("accepted"),
                           "rejected": len(report.get("rejected") or []), "score": score,
                           "items": [{k: i.get(k) for k in ("title", "date", "kind")} for i in pred.get("items") or []],
                           "at": datetime.now(KST).isoformat(timespec="seconds")}
                    runs.append(run)
                    log.write(json.dumps(run, ensure_ascii=False) + "\n")
                    log.flush()
                    print(f"rep{rep} {case['case_id']} size={size:>2} calls={len(meter.calls)} model={run['model_seconds']:.1f}s "
                          f"max_call={max((c['seconds'] for c in meter.calls), default=0):.1f}s items={score['items']} tamper={score['tamper']}",
                          flush=True)
    summarize(runs, out, backend)


def summarize(runs: list[dict[str, Any]], out: Path, backend: str) -> None:
    by_size: dict[int, list[dict[str, Any]]] = {}
    for run in runs:
        by_size.setdefault(run["size"], []).append(run)
    lines = [f"# 묶음 크기별 요약 — {backend}", "",
             "| 묶음 줄 수 | 실행 | 호출 | 호출 시간 가운데 · 90% · 최대(초) | 건당 모델 시간 가운데 · 최대(초) | 새로 읽은 입력 토큰 가운데 | 항목 찾음 | 조각 거의 같음 | 정밀도 | 종류 | 날짜 | 값 변조 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    table = {}
    for size in sorted(by_size):
        group = by_size[size]
        calls = [c for r in group for c in r["calls"]]
        call_s = [c["seconds"] for c in calls]
        case_s = [r["model_seconds"] for r in group]
        prompt = [c.get("prompt_eval_count") for c in calls if c.get("prompt_eval_count") is not None]

        def tot(field: str) -> tuple[int, int]:
            return sum(r["score"][field][0] for r in group), sum(r["score"][field][1] for r in group)

        row = {name: tot(name) for name in ("items", "items_tight", "items_precision", "kind", "date", "tamper")}
        table[size] = {"runs": len(group), "calls": len(calls), "call_p50": pct(call_s, .5), "call_p90": pct(call_s, .9),
                       "call_max": max(call_s or [0]), "case_p50": pct(case_s, .5), "case_max": max(case_s or [0]),
                       "prompt_p50": statistics.median(prompt) if prompt else None, "errors": sum(1 for c in calls if c["error"]), **row}

        def f(pair: tuple[int, int]) -> str:
            return f"{pair[0]}/{pair[1]} = {100 * pair[0] / pair[1]:.0f}%" if pair[1] else "—"

        lines.append(f"| {size or '한 번'} | {len(group)} | {len(calls)} | {pct(call_s, .5):.1f} · {pct(call_s, .9):.1f} · {max(call_s or [0]):.1f} | "
                     f"{pct(case_s, .5):.1f} · {max(case_s or [0]):.1f} | {table[size]['prompt_p50']} | {f(row['items'])} | {f(row['items_tight'])} | "
                     f"{f(row['items_precision'])} | {f(row['kind'])} | {f(row['date'])} | {f(row['tamper'])} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(table, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

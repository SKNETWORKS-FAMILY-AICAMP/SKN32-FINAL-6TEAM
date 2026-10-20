# -*- coding: utf-8 -*-
"""계획 읽기 — 긴 글을 **한 번에** 보내되 답을 **조금씩 받는**(stream) 방식 측정. `[2026-10-16 2회차 합의]`

    python -m eval.intake_chunking.stream_probe --ollama <x600 과 같은 구성의 Ollama 주소> --repeat 2 --out <폴더>
    python -m eval.intake_chunking.stream_probe --api --api-key-file <서버용 키 파일> --max-tokens 4096 --repeat 1 --out <폴더>

★잴 것: 첫 조각까지 시간 · 조각 사이 가장 긴 간격(멈춤 감시 값의 근거) · 전체 시간 · 답 토큰 수 · 정확도(조각을 다 모은 답을 제품 함수로 채점).
★로컬은 같은 건마다 stream=true / stream=false 를 번갈아(교대) 보내 속도 · 정확도가 같은지 본다. 두 방식 모두 format=json · think=false · 온도 0 · num_ctx 8192 —
  제품의 `OllamaChat._chat` 과 같은 몸통에 `stream` 만 다르다.
★줄 번호는 보낸 목록 안 순서(1부터) — 제품의 `llm_spans.label_lines` 와 같다.
★유료: gpt-6-luna · `response_format=json_object` · `reasoning_effort=none` · stream=True · 출력 예산 `--max-tokens`. 이 실행의 호출 상한 `--api-cap`.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
KST = ZoneInfo("Asia/Seoul")


class Replay:
    """이미 받은 답을 그대로 돌려주는 모델 — 제품 함수(`read_source`)로 채점하려고 쓴다."""

    def __init__(self, answer: dict[str, Any] | None, error: str | None) -> None:
        self.answer, self.error = answer, error

    def json(self, system: str, user: str) -> dict[str, Any]:
        if self.error:
            raise RuntimeError(self.error)
        return self.answer or {}


def ollama_call(url: str, model: str, system: str, user: str, *, stream: bool, num_ctx: int, timeout: float) -> dict[str, Any]:
    import httpx

    payload = {"model": model, "stream": stream, "think": False, "format": "json", "keep_alive": "30m",
               "options": {"temperature": 0, "num_ctx": num_ctx},
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    started = time.perf_counter()
    if not stream:
        body = httpx.post(f"{url}/api/chat", json=payload, timeout=timeout).json()
        took = time.perf_counter() - started
        return {"text": body["message"]["content"], "first": took, "max_gap": took, "seconds": took, "pieces": 1,
                "eval_count": body.get("eval_count"), "prompt_eval_count": body.get("prompt_eval_count"),
                "load": (body.get("load_duration") or 0) / 1e9}
    text, first, last, gap, pieces, tail = [], None, None, 0.0, 0, {}
    with httpx.stream("POST", f"{url}/api/chat", json=payload, timeout=timeout) as response:
        for line in response.iter_lines():
            if not line:
                continue
            part = json.loads(line)
            now = time.perf_counter()
            piece = (part.get("message") or {}).get("content") or ""
            if piece:
                pieces += 1
                if first is None:
                    first = now - started
                elif last is not None:
                    gap = max(gap, now - last)
                last = now
                text.append(piece)
            if part.get("done"):
                tail = part
    return {"text": "".join(text), "first": first, "max_gap": gap, "seconds": time.perf_counter() - started, "pieces": pieces,
            "eval_count": tail.get("eval_count"), "prompt_eval_count": tail.get("prompt_eval_count"),
            "load": (tail.get("load_duration") or 0) / 1e9}


def api_call(key: str, model: str, system: str, user: str, *, max_tokens: int, timeout: float) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=key, timeout=timeout, max_retries=0)
    kwargs: dict[str, Any] = {"model": model, "stream": True, "max_completion_tokens": max_tokens,
                              "response_format": {"type": "json_object"},
                              "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                              "stream_options": {"include_usage": True}}
    if model.startswith("gpt-6-luna"):
        kwargs["reasoning_effort"] = "none"
    started = time.perf_counter()
    text, first, last, gap, pieces, finish, usage = [], None, None, 0.0, 0, None, None
    for chunk in client.chat.completions.create(**kwargs):
        now = time.perf_counter()
        if chunk.usage is not None:
            usage = chunk.usage
        for choice in chunk.choices or []:
            piece = choice.delta.content or ""
            if choice.finish_reason:
                finish = choice.finish_reason
            if piece:
                pieces += 1
                if first is None:
                    first = now - started
                elif last is not None:
                    gap = max(gap, now - last)
                last = now
                text.append(piece)
    return {"text": "".join(text), "first": first, "max_gap": gap, "seconds": time.perf_counter() - started, "pieces": pieces,
            "finish": finish, "eval_count": getattr(usage, "completion_tokens", None),
            "prompt_eval_count": getattr(usage, "prompt_tokens", None)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ollama", default="")
    parser.add_argument("--model", default="tripilot-pointer:e4b-ft")
    parser.add_argument("--num-ctx", type=int, default=8192)
    parser.add_argument("--api", action="store_true")
    parser.add_argument("--api-model", default="gpt-6-luna")
    parser.add_argument("--api-key-file", default="")
    parser.add_argument("--api-cap", type=int, default=20)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--cases", default="")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--numbering", choices=("position", "original"), default="position")
    parser.add_argument("--modes", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(HERE.parents[1]))
    from eval.intake_diverse.run_current import _DUMMY_ENV
    for key, value in _DUMMY_ENV.items():
        os.environ.setdefault(key, value)
    from app.domains.travel_ops.components.intake.llm_spans import SYSTEM
    from app.domains.travel_ops.components.intake.pipeline import read_source
    from app.domains.travel_ops.components.intake.rules import read_plan
    from eval.intake_chunking.cases import all_cases
    from eval.intake_diverse.run_current import adapt
    from eval.intake_diverse.score import score_case

    key = ""
    if args.api:
        for line in Path(args.api_key_file).read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("ACOP_OPENAI_API_KEY_SERVER="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
        if not key:
            raise SystemExit("서버용 키가 파일에 없다(ACOP_OPENAI_API_KEY_SERVER)")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cases = [c for c in all_cases() if not args.cases or c["case_id"] in args.cases.split(",")]
    used = 0
    with (out / "probe.jsonl").open("a", encoding="utf-8") as log:
        for rep in range(args.repeat):
            for index, case in enumerate(cases):
                read = read_plan(case["text"])
                user = "\n".join(f"{at if args.numbering == 'position' else n}: {read.lines[n - 1]}"
                                 for at, n in enumerate(read.unread_lines, start=1))
                modes = ["api"] if args.api else (["stream", "plain"] if (index + rep) % 2 == 0 else ["plain", "stream"])
                if args.modes:
                    modes = args.modes.split(",")
                for mode in modes:
                    if mode == "api":
                        if used >= args.api_cap:
                            print("이 실행의 유료 호출 상한", flush=True)
                            break
                        used += 1
                    error, answer = None, None
                    try:
                        got = (api_call(key, args.api_model, SYSTEM, user, max_tokens=args.max_tokens, timeout=args.timeout) if mode == "api"
                               else ollama_call(args.ollama, args.model, SYSTEM, user, stream=mode == "stream", num_ctx=args.num_ctx,
                                                timeout=args.timeout))
                        try:
                            answer = json.loads(got["text"])
                        except ValueError:
                            error = f"JSON 이 아니다(끝 {got['text'][-40:]!r})"
                    except Exception as exc:          # noqa: BLE001
                        got, error = {}, f"{type(exc).__name__}: {exc}"[:200]
                    rows = read_source(case["text"], chat=Replay(answer, error), today=date.fromisoformat(case["today"]),
                                       now=datetime(2026, 10, 16, 9, 0, tzinfo=KST))
                    score = score_case({"case_id": case["case_id"], "source_text": case["text"], "gold": case["gold"]},
                                       {"error": None, **adapt(rows)})
                    run = {"rep": rep, "case": case["case_id"], "mode": mode, "unread": len(read.unread_lines), "error": error,
                           **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in got.items() if k != "text"},
                           "answer_chars": len(got.get("text") or ""), "answer": got.get("text"), "numbering": args.numbering, "score": score, "at": datetime.now(KST).isoformat(timespec="seconds")}
                    log.write(json.dumps(run, ensure_ascii=False) + "\n")
                    log.flush()
                    print(f"rep{rep} {case['case_id']} {mode:6} first={run.get('first')} gap={run.get('max_gap')} total={run.get('seconds')} "
                          f"out={run.get('eval_count')} items={score['items']} err={error}", flush=True)


if __name__ == "__main__":
    main()

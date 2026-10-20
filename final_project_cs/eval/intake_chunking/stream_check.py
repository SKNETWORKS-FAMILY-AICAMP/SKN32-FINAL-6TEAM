# -*- coding: utf-8 -*-
"""계획 읽기 조금씩 받기 — **제품 경로 그대로** 실제 모델로 한 번 확인한다. `[2026-10-16 2회차 합의]`

    python -m eval.intake_chunking.stream_check --ollama <x600 과 같은 구성의 Ollama 주소> --cases L4,L1 --out <폴더>
    python -m eval.intake_chunking.stream_check --dead-local --api-key-file <서버용 키 파일> --cases L4 --out <폴더>

★`read_source` → `llm_spans.label_lines` → 모델의 `json_stream` 을 그대로 부른다. 설정 값은 가드레일 `travel.intake_reading` 그대로.
★`--dead-local` — 넘김 장치(`FailoverChat`)의 로컬 자리를 아무도 안 듣는 주소로 두고 유료(gpt-6-luna)가 **처음부터** 읽는지 본다(진행 알림이 `reading_api` 로 바뀌는지).
★진행 알림(`on_reading`)을 받은 시각과 함께 남긴다 — 5초 간격 · 줄 수가 늘어나는지 본다.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
KST = ZoneInfo("Asia/Seoul")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ollama", default="")
    parser.add_argument("--model", default="tripilot-pointer:e4b-ft")
    parser.add_argument("--dead-local", action="store_true")
    parser.add_argument("--api-key-file", default="")
    parser.add_argument("--api-model", default="gpt-6-luna")
    parser.add_argument("--cases", default="L4")
    parser.add_argument("--agent", action="store_true", help="읽기 에이전트(D-025)로 읽는다 — agent_mode=on")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(HERE.parents[1]))
    from eval.intake_diverse.run_current import _DUMMY_ENV
    for key, value in _DUMMY_ENV.items():
        os.environ.setdefault(key, value)
    from app.domains.travel_ops.components.intake.pipeline import read_source
    from app.infrastructure import llm_failover
    from app.infrastructure.llm_failover import CircuitBreaker, FailoverChat, OpenAIChat, _Backend
    from app.infrastructure.ollama_chat import OllamaChat
    from eval.intake_chunking.cases import all_cases
    from eval.intake_diverse.run_current import adapt
    from eval.intake_diverse.score import score_case

    if args.dead_local:
        key = next((line.split("=", 1)[1].strip().strip('"').strip("'") for line in Path(args.api_key_file).read_text(encoding="utf-8").splitlines()
                    if line.strip().startswith("ACOP_OPENAI_API_KEY_SERVER=")), "")
        if not key:
            raise SystemExit("서버용 키가 파일에 없다")
        local = OllamaChat(base_url="http://127.0.0.1:9", model=args.model, timeout=9.0, keep_alive="30m", num_ctx=8192)
        chat = FailoverChat([_Backend("ollama", local, CircuitBreaker("ollama", threshold=3, open_seconds=60), timeout=9.0),
                             _Backend("openai", OpenAIChat(api_key=key, model=args.api_model, timeout=8.0),
                                      CircuitBreaker("openai", threshold=3, open_seconds=60), is_api=True, timeout=8.0)])
    else:
        chat = OllamaChat(base_url=args.ollama, model=args.model, timeout=9.0, keep_alive="30m", num_ctx=8192)
        OllamaChat(base_url=args.ollama, model=args.model, timeout=180.0, keep_alive="30m", num_ctx=8192).warm()   # 예열은 넉넉히(내려가 있으면 올리는 데 수십 초)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for case in [c for c in all_cases() if c["case_id"] in args.cases.split(",")]:
        events = []
        started = time.perf_counter()
        error = None
        try:
            rows = read_source(case["text"], chat=chat, today=date.fromisoformat(case["today"]), now=datetime(2026, 10, 16, 9, tzinfo=KST),
                               agent=chat if args.agent else None, agent_mode="on" if args.agent else "off",
                               on_reading=lambda body: events.append({**body, "t": round(time.perf_counter() - started, 2)}))
        except Exception as exc:                          # noqa: BLE001
            rows, error = [], f"{type(exc).__name__}: {exc}"[:300]
        seconds = round(time.perf_counter() - started, 2)
        score = score_case({"case_id": case["case_id"], "source_text": case["text"], "gold": case["gold"]}, {"error": error, **adapt(rows)})
        report = next((r["value"] for r in rows if r.get("field") == ("reading.agent" if args.agent else "reading.llm")), None)
        run = {"case": case["case_id"], "dead_local": args.dead_local, "agent": args.agent, "seconds": seconds, "error": error, "events": events,
               "report": report, "path": llm_failover.current_path(), "items": score["items"], "tamper": score["tamper"],
               "at": datetime.now(KST).isoformat(timespec="seconds")}
        with (out / "check.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps(run, ensure_ascii=False, default=str) + "\n")
        print(json.dumps({k: run[k] for k in ("case", "seconds", "error", "items", "tamper")}, ensure_ascii=False))
        print("  진행:", [(e["phase"], e["done"], e["total"], e["t"]) for e in events])
        print("  경로:", (report or {}).get("path") or (report or {}).get("paths"), (report or {}).get("reasons"), "답 상한",
              (report or {}).get("output_tokens"), "다시 읽음", (report or {}).get("restarted_on_api"), "오류", (report or {}).get("error"))


if __name__ == "__main__":
    main()

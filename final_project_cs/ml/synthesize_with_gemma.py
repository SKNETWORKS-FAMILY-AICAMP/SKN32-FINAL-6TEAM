# -*- coding: utf-8 -*-
"""상담 제목에 거의 없는 라벨을 **합성 글**로 보강한다 — 교사(Gemma)가 쓰고, 교사가 다시 가린다.

    python synthesize_with_gemma.py --output synth_raw.jsonl --per-pair 40

★**왜 필요한가.** 실제 글 풀(소비자상담 제목)은 대부분 환불·취소 분쟁이다. 제품이 받는
  「일정 제출」「조정 거부」「날씨 위험」「경로 불가」 같은 글은 거의 없다. 없는 라벨은
  학습한 모델이 **영원히 못 낸다.**

★**합성이라고 표시한다**(`source: synthetic`). 시험 조각에는 넣지 않는다 — 교사가 쓴
  글을 교사가 가린 점수는 부풀려진다. 학습에만 쓴다.

★**의도한 라벨과 교사의 눈가림 재분류가 같을 때만 남긴다**(일관성 거름). 쓰라고 한
  라벨과 다시 읽고 붙인 라벨이 다르면 글이 그 라벨을 대표하지 못한 것이다. 거른
  건수를 센다 — 재분류는 `label_with_gemma.py` 가 한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path

from label_with_gemma import GUIDE, INTENTS, ISSUE_CODES   # 같은 폴더에 둔다

#: ★보강할 (intent, issue_code) 짝 — 여행 중인 고객이 실제로 보낼 만한 조합만.
TARGET_PAIRS = (
    ("itinerary_submit", "activity_time_conflict"),
    ("itinerary_submit", "activity_other"),
    ("itinerary_submit", "mobility_route_infeasible"),
    ("itinerary_submit", "dining_hours"),
    ("incident_report", "activity_weather_risk"),
    ("incident_report", "activity_time_conflict"),
    ("incident_report", "dining_hours"),
    ("incident_report", "dining_conditions"),
    ("incident_report", "mobility_missed_or_disrupted"),
    ("incident_report", "mobility_route_infeasible"),
    ("incident_report", "booking_mismatch"),
    ("incident_report", "lodging_other"),
    ("confirm_request", "dining_hours"),
    ("confirm_request", "activity_weather_risk"),
    ("confirm_request", "mobility_route_infeasible"),
    ("confirm_request", "activity_time_conflict"),
    ("confirm_request", "booking_change_request"),
    ("adjust_reject", "activity_other"),
    ("adjust_reject", "dining_other"),
    ("adjust_reject", "mobility_other"),
    ("adjust_reject", "booking_change_request"),
    ("other", "other"),
)

SYSTEM = (
    "너는 한국 여행 중인 고객이 여행 관리 서비스에 보내는 **짧은 메시지**를 쓰는 작가다. "
    "실제 사람이 휴대폰으로 급히 쓴 것처럼 다양하게 쓴다 — 존댓말·반말, 짧은 글·긴 글, "
    "오타·줄임말을 섞는다. 장소는 서울의 실제 지명·업종을 쓰되 개인정보(이름·전화·카드번호)는 "
    "넣지 않는다. 같은 문형을 되풀이하지 않는다.\n\n"
    "아래 라벨 정의를 따른다:\n" + GUIDE + "\n\n"
    "출력은 JSON 하나다: {\"messages\": [\"...\", \"...\"]}"
)


def generate(url: str, model: str, intent: str, code: str, n: int, seed: int, timeout: float) -> list[str]:
    user = (f"요청 종류 intent={intent}, 문제 코드 issue_code={code} 에 **정확히** 해당하는 고객 메시지를 "
            f"{n}개 써라. 다른 라벨로 읽힐 수 있는 모호한 글은 쓰지 않는다.")
    body = json.dumps({
        "model": model, "stream": False, "format": "json", "think": False,
        "options": {"temperature": 0.9, "top_p": 0.95, "seed": seed},
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
    }).encode("utf-8")
    request = urllib.request.Request(url.rstrip("/") + "/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    parsed = json.loads(payload.get("message", {}).get("content") or "{}")
    messages = parsed.get("messages") if isinstance(parsed, dict) else None
    return [m.strip() for m in messages if isinstance(m, str) and m.strip()] if isinstance(messages, list) else []


def main() -> int:
    parser = argparse.ArgumentParser(description="부족한 라벨 합성")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:11435")
    parser.add_argument("--model", default="gemma4:12b")
    parser.add_argument("--per-pair", type=int, default=40)
    parser.add_argument("--chunk", type=int, default=20, help="한 번에 몇 개씩 쓰게 하나")
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    for intent, code in TARGET_PAIRS:
        assert intent in INTENTS and code in ISSUE_CODES, (intent, code)

    seen: set[str] = set()
    if args.output.exists():
        for line in args.output.read_text(encoding="utf-8").splitlines():
            if line.strip():
                seen.add(json.loads(line)["text"])
    stats = {"generated": 0, "duplicate": 0, "call_failed": 0}
    started = time.perf_counter()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as out:
        for pair_index, (intent, code) in enumerate(TARGET_PAIRS):
            have = 0
            for round_index in range(0, args.per_pair, args.chunk):
                seed = 1000 + pair_index * 97 + round_index
                try:
                    messages = generate(args.url, args.model, intent, code,
                                        min(args.chunk, args.per_pair - round_index), seed, args.timeout)
                except Exception as exc:                     # ★세어서 남긴다
                    stats["call_failed"] += 1
                    print(f"  {intent}/{code} 호출 실패: {type(exc).__name__}: {exc}", flush=True)
                    continue
                for text in messages:
                    if text in seen:
                        stats["duplicate"] += 1
                        continue
                    seen.add(text)
                    row_id = "syn-" + hashlib.sha1(f"{intent}|{code}|{text}".encode("utf-8")).hexdigest()[:12]
                    out.write(json.dumps({"id": row_id, "text": text, "source": "synthetic",
                                          "intended_intent": intent, "intended_issue_code": code,
                                          "writer": args.model}, ensure_ascii=False) + "\n")
                    stats["generated"] += 1
                    have += 1
                out.flush()
            print(f"  [{pair_index + 1}/{len(TARGET_PAIRS)}] {intent}/{code}: {have}건 "
                  f"({time.perf_counter() - started:.0f}s) {stats}", flush=True)
    print(json.dumps({"stats": stats, "seconds": round(time.perf_counter() - started, 1)},
                     ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

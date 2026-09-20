# -*- coding: utf-8 -*-
"""교사 모델(Gemma)로 `intent`·`issue_code` 라벨을 붙인다 — 증류(distillation)의 교사 쪽.

    python label_with_gemma.py --input pool_real.jsonl --output labeled_real.jsonl

★**표준 라이브러리만 쓴다.** GPU 학습 기계에는 이 저장소가 없다. 어휘가 제품과
  같은지는 저장소의 시험(`tests/unit/ml/test_intent_vocabulary.py`)이 막는다.

★**「정답」이 아니라 「교사의 답」이다.** 여기서 붙은 라벨로 학습한 모델의 점수는
  **교사와의 일치도**다. 사람 정답과의 일치도가 아니다 — 그렇게 적는다.

★**어휘 밖 답은 버리고 센다.** 교사가 목록에 없는 코드를 내면 지어낸 것이다. 가장
  가까운 것으로 고쳐 넣지 않는다(`CLAUDE.md` §1 — 지어내지 않는다).

★**이어서 돈다.** 중간에 끊겨도 이미 붙인 id 는 건너뛴다. 결과는 한 줄씩 바로 쓴다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

#: ★제품 어휘 — `app/modules/travel_ops/feedback.py` 와 같아야 한다(시험이 대조한다).
INTENTS = ("itinerary_submit", "incident_report", "confirm_request", "adjust_reject", "other")
ISSUE_CODES = (
    "activity_cancel_or_change", "activity_weather_risk", "activity_time_conflict", "activity_other",
    "dining_hours", "dining_conditions", "dining_other",
    "mobility_missed_or_disrupted", "mobility_route_infeasible", "mobility_other",
    "booking_mismatch", "booking_change_request", "booking_cancel_request", "booking_other",
    "lodging_other", "flight_other",
    "other",
)

#: ★라벨 뜻풀이 — 제품 프롬프트는 이름만 준다. 교사가 같은 기준으로 고르게 이 세션이
#:  적었다. 바꾸면 라벨 분포가 바뀌므로 판(version)을 올린다.
#: ★v2 — 30건 시험에서 「승차권 구매취소 환급거절」「철도 예약 취소 환급 지연」이 규칙 1 을
#:  어기고 결항 코드로 붙었다. 교통권·이용권도 규칙 1 에 든다고 적었다(2026-09-17).
GUIDE_VERSION = "2026-09-17.v2"
GUIDE = """
[요청 종류 intent — 무엇을 해 달라는 글인가]
- itinerary_submit : 여행 일정·계획을 새로 내거나 등록·검토해 달라는 글
- incident_report  : 이미 일어난 문제·피해·불편을 알리는 글 (결항, 휴무, 지연, 환불 거부, 불친절 피해 등)
- confirm_request  : 규정·가능 여부·금액·정보를 묻는 글 (환불 되나요? 수수료 얼마? 운영하나요?)
- adjust_reject    : 이미 바뀐 일정·대안을 거부하거나 원래대로 되돌려 달라는 글
- other            : 위 어디에도 안 맞는 글

[문제 코드 issue_code — 무엇에 관한 어떤 문제인가. 접두가 담당 팀을 정한다]
- activity_cancel_or_change : 관광·체험·공연·레저 이용을 취소하거나 바꾸는 문제
- activity_weather_risk     : 날씨·재난 때문에 활동이 위험하거나 못 하게 된 문제
- activity_time_conflict    : 활동 시간이 다른 일정과 겹치거나 운영 시간과 안 맞는 문제
- activity_other            : 그 밖의 관광·체험·공연·레저 문제 (시설, 입장, 품질)
- dining_hours              : 식당의 영업시간·휴무·브레이크타임 문제
- dining_conditions         : 식당의 조건 문제 (위생, 음식 품질, 가격 표시, 결제, 서비스)
- dining_other              : 그 밖의 식당·음식 서비스 문제
- mobility_missed_or_disrupted : 항공편·열차·버스·택시가 결항·지연·운행중단되거나 놓친 문제
- mobility_route_infeasible : 이동 경로 자체가 불가능한 문제 (통제, 막차 없음, 승차 거부로 이동 불가)
- mobility_other            : 그 밖의 이동 수단 이용 문제
- booking_mismatch          : 예약 내용이 약속과 다른 문제 (날짜·인원·객실·좌석 불일치, 예약 누락, 임의 변경)
- booking_change_request    : 예약을 바꿔 달라는 요청
- booking_cancel_request    : 예약 취소·환불·위약금·취소수수료 문제
- booking_other             : 그 밖의 예약·결제 문제
- lodging_other             : 숙박 시설 자체의 문제 (시설, 위생, 서비스) — 예약·환불 문제가 아닐 때
- flight_other              : 항공 이용의 그 밖 문제 (마일리지, 수하물, 좌석 서비스) — 예약·환불·결항이 아닐 때
- other                     : 여행과 무관하거나 어디에도 안 맞는 글

[우선 규칙]
1. 예약·표·이용권의 취소·환불·위약금·수수료 얘기면 대상이 호텔·항공권·승차권·공연·레저여도 booking_cancel_request 다. 운행이 실제로 결항·지연·중단된 얘기가 아니면 mobility_ 를 쓰지 않는다.
2. 결항·지연·운행중단은 예약이 걸려 있어도 mobility_missed_or_disrupted 다.
3. 확신이 없으면 접두를 추측하지 말고 other 를 쓴다.
""".strip()

SYSTEM = (
    "너는 여행 고객운영 시스템의 분류기다. 각 글마다 요청 종류(intent)와 문제 코드(issue_code)를 "
    "고른다. 반드시 아래 목록의 값만 쓴다. 목록에 없는 값을 만들지 않는다.\n\n"
    + GUIDE + "\n\n"
    "출력은 JSON 하나다: {\"labels\": [{\"id\": \"...\", \"intent\": \"...\", \"issue_code\": \"...\"}]}. "
    "입력의 모든 id 에 대해 정확히 하나씩 낸다."
)


def call_ollama(url: str, model: str, rows: list[dict], timeout: float) -> list[dict]:
    user = "\n".join(json.dumps({"id": row["id"], "text": row["text"]}, ensure_ascii=False)
                     for row in rows)
    body = json.dumps({
        "model": model, "stream": False, "format": "json", "think": False,
        "options": {"temperature": 0, "seed": 7},
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
    }).encode("utf-8")
    request = urllib.request.Request(url.rstrip("/") + "/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    content = payload.get("message", {}).get("content") or ""
    parsed = json.loads(content)
    labels = parsed.get("labels") if isinstance(parsed, dict) else None
    if not isinstance(labels, list):
        raise ValueError("labels 가 목록이 아니다")
    return labels


def main() -> int:
    parser = argparse.ArgumentParser(description="Gemma 로 intent·issue_code 라벨 붙이기")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="gemma4:12b")
    parser.add_argument("--batch", type=int, default=15)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    # ★보정 단계는 거부 파일을 입력으로 받는다 — 같은 글이 여러 번 거부됐을 수 있어 id 로 한 번만 남긴다.
    unique: dict[str, dict] = {}
    for row in rows:
        clean = {key: value for key, value in row.items()
                 if key not in ("reason", "intent", "issue_code", "teacher", "guide")}
        unique.setdefault(row["id"], clean)
    rows = list(unique.values())
    if args.limit:
        rows = rows[:args.limit]
    done: set[str] = set()
    if args.output.exists():
        for line in args.output.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["id"])
    todo = [row for row in rows if row["id"] not in done]
    print(f"전체 {len(rows)} · 이미 붙임 {len(done)} · 남음 {len(todo)} · 모델 {args.model} · 안내판 {GUIDE_VERSION}",
          flush=True)

    stats = {"labeled": 0, "invalid_label": 0, "missing_in_answer": 0, "batch_failed": 0}
    started = time.perf_counter()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as out, \
            (args.output.with_suffix(".rejected.jsonl")).open("a", encoding="utf-8") as rejected:
        for start in range(0, len(todo), args.batch):
            batch = todo[start:start + args.batch]
            labels = None
            for attempt in (1, 2):
                try:
                    labels = call_ollama(args.url, args.model, batch, args.timeout)
                    break
                except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                    print(f"  묶음 {start} 시도 {attempt} 실패: {type(exc).__name__}: {exc}", flush=True)
            if labels is None:
                stats["batch_failed"] += len(batch)
                for row in batch:
                    rejected.write(json.dumps({**row, "reason": "batch_failed"}, ensure_ascii=False) + "\n")
                continue
            by_id = {str(item.get("id")): item for item in labels if isinstance(item, dict)}
            for row in batch:
                answer = by_id.get(row["id"])
                if answer is None:
                    stats["missing_in_answer"] += 1
                    rejected.write(json.dumps({**row, "reason": "missing_in_answer"}, ensure_ascii=False) + "\n")
                    continue
                intent, code = answer.get("intent"), answer.get("issue_code")
                if intent not in INTENTS or code not in ISSUE_CODES:
                    stats["invalid_label"] += 1
                    rejected.write(json.dumps({**row, "reason": "invalid_label", "intent": intent,
                                               "issue_code": code}, ensure_ascii=False) + "\n")
                    continue
                out.write(json.dumps({**row, "intent": intent, "issue_code": code,
                                      "teacher": args.model, "guide": GUIDE_VERSION,
                                      "label_pass": "single" if args.batch == 1 else "batch"},
                                     ensure_ascii=False) + "\n")
                stats["labeled"] += 1
            out.flush()
            rejected.flush()
            elapsed = time.perf_counter() - started
            handled = min(start + args.batch, len(todo))
            print(f"  {handled}/{len(todo)} ({elapsed:.0f}s, {elapsed / max(1, handled):.2f}s/건) {stats}",
                  flush=True)
    print(json.dumps({"stats": stats, "seconds": round(time.perf_counter() - started, 1)},
                     ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

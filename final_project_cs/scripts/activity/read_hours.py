"""활동 원장의 운영시간 원문을 **요일표로 미리 편다** — `activity.ac_place.hours_week` · `hours_read`. `[2026-10-12]`

★왜. 원문이 워낙 다양해서(하절기/동절기 · 평일/주말 · 매표 마감 …) 규칙으로 펴지는 곳은 1,932곳 중 296곳뿐이다.
  나머지는 코어와 같은 함수(`place_hours.read_hours` — 규칙 먼저, 안 되면 sLLM, 원문 인용이 맞는 것만 받는다)로 **한 번만** 펴 저장한다.
  요청 때(`instances/activity/ledger.state`)는 저장된 표만 읽는다 — 모델을 부르지 않는다(멘토 피드백 10-08 「처음 한 번만」).

두 단계
    1. 모델 없이(기본)      규칙으로 펴지는 곳만 채운다. 나머지는 `method: none` 으로 적어 둔다(다시 볼 대상).
    2. `--model`            아직 못 편 곳(요일표가 비었고 원문이 있는 곳)을 코어 설정의 Ollama 모델(`ollama_model`, 기본 gemma4:12b)로 편다.
                            주소(`ACOP_OLLAMA_BASE_URL`)가 비어 있으면 아무것도 안 하고 멈춘다.

사용법
    python scripts/activity/read_hours.py                    규칙으로 (처음 한 번, 또는 적재 뒤 원문이 바뀐 곳)
    python scripts/activity/read_hours.py --model --limit 50 모델로 50곳만
    python scripts/activity/read_hours.py --model            모델로 남은 곳 전부(한 곳씩 커밋 — 끊겨도 이어서 된다)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))                       # final_project_cs
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SOURCE = "activity_total_data.csv"
#: 아직 안 읽은 곳(규칙 단계)
_UNREAD = "hours_read IS NULL"
#: 규칙으로 못 편 곳 중 원문이 있는 곳(모델 단계). 모델이 읽고도 못 편 곳(`llm`)은 다시 부르지 않는다
_FOR_MODEL = ("hours_week IS NULL AND (usetime_text IS NOT NULL OR restdate_text IS NOT NULL) "
              "AND (hours_read IS NULL OR hours_read->>'method' = 'none')")


def read_one(usetime: str | None, restdate: str | None, chat) -> tuple[dict | None, dict]:
    """원문 → (요일표 | None, 읽은 기록). `chat` 이 None 이면 규칙만."""
    from app.domains.travel_ops.components.places.place_hours import HoursRead, read_by_rule, read_hours

    read = read_hours(usetime, restdate, chat) if chat is not None else read_by_rule(usetime, restdate)
    if read is None:                                   # 규칙 밖 — 모델 단계가 볼 곳
        read = HoursRead(method="none", dropped=["규칙으로 펼 수 없다"] if (usetime or restdate) else ["원문이 비어 있다"])
    now = datetime.now(ZoneInfo("Asia/Seoul")).isoformat()
    return (read.week or None), read.as_record(source=SOURCE, read_at=now)


def _chat():
    from app.core.settings import get_settings
    from app.infrastructure.ollama_chat import from_settings

    chat = from_settings(get_settings())
    if chat is None:
        raise SystemExit("모델 서버 주소(ACOP_OLLAMA_BASE_URL)가 비어 있다 — 규칙 단계만 하려면 --model 없이 돌린다")
    return chat


def run(conn, *, chat=None, limit: int | None = None) -> dict[str, int]:
    """대상 행을 읽어 적는다. 한 곳씩 커밋한다(모델 단계가 길어서 — 끊겨도 다음 실행이 남은 곳부터 한다)."""
    where = _FOR_MODEL if chat is not None else _UNREAD
    with conn.cursor() as cur:
        cur.execute(f"SELECT content_id, usetime_text, restdate_text FROM activity.ac_place WHERE {where} "
                    "ORDER BY content_id" + (" LIMIT %s" if limit else ""), (limit,) if limit else None)
        targets = cur.fetchall()
    out = {"asked": len(targets), "read": 0, "unknown": 0}
    for content_id, usetime, restdate in targets:
        week, record = read_one(usetime, restdate, chat)
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE activity.ac_place SET hours_week = %s, hours_read = %s WHERE content_id = %s",
                        (json.dumps(week, ensure_ascii=False) if week else None,
                         json.dumps(record, ensure_ascii=False, default=str), content_id))
        out["read" if week else "unknown"] += 1
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", action="store_true", help="못 편 곳을 코어 설정의 Ollama 모델로 편다")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    import psycopg
    from load_places import dsn

    chat = _chat() if args.model else None
    with psycopg.connect(dsn(), autocommit=True) as conn:      # ★autocommit — `run` 의 한 곳씩 트랜잭션이 진짜 커밋이 되게
        result = run(conn, chat=chat, limit=args.limit)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FILTER (WHERE hours_week IS NOT NULL), "
                        f"count(*) FILTER (WHERE {_FOR_MODEL}) FROM activity.ac_place")
            filled, waiting = cur.fetchone()
    print(f"{'모델' if args.model else '규칙'} 단계: 대상 {result['asked']:,}곳 → 편 곳 {result['read']:,} · 못 편 곳 {result['unknown']:,}")
    print(f"요일표 있음 {filled:,}곳 · 모델 단계 대기 {waiting:,}곳")


if __name__ == "__main__":
    main()

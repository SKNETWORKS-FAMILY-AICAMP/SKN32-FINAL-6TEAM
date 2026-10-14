# -*- coding: utf-8 -*-
"""요식 판정 에이전트 평가 자료를 만든다 — 실제 원장 가게 · 그날 일정 · 고객 문장 + 기대(골라야 할 체크 · 고르면 안 될 체크 · 기대 판정). `[2026-10-13]`

    python -m scripts.dining.make_agent_eval --dsn postgresql://postgres@127.0.0.1:5433/dining_rebuild

★기대 판정은 **규칙 도구가 그날 원장으로 낸 값**을 얼려 둔다(`agent_tools.DiningTools`) — 원장이 바뀌어도 자료는 그대로다(만든 날 · 원장 DB 를 적는다).
★「골라야 할 체크」는 사람이 정했다 — 시각이 있는 식사는 늘 found · open_at, 고객 문장이 말한 조건(할랄 · 채식 · 아이 · 카드)만 dietary · kids · payment.
  「고르면 안 될 체크」는 말하지 않은 조건이다(설계 §7 — 할랄 요청이 없는데 할랄을 보면 감점).
★holdout 은 프롬프트를 고칠 때 보지 않는다.
"""
from __future__ import annotations

import argparse
import json
from contextlib import contextmanager
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "eval" / "datasets"
ATTR_OF = {"dietary": None, "kids": "kids", "payment": "card"}
STATE_VERDICT = {"yes": "ok", "limited": "ok", "no": "bad", "unknown": "unknown"}
CONDS = ("dietary", "kids", "payment")

# (id, 날짜, 고객 문장, [(가게, 시작, 끝)], 고객이 말한 조건(dietary 는 halal/vegetarian 중 무엇인지))
DEV = [
    ("DG-001", "2026-10-19", "", [("후제", "12:00", "13:00")], {}),
    ("DG-002", "2026-10-25", "", [("산수갑산", "12:00", "13:00")], {}),
    ("DG-003", "2026-10-21", "", [("수유손칼국수", "12:00", "13:00")], {}),
    ("DG-004", "2026-10-20", "", [("유진식당", "15:00", "16:00")], {}),
    ("DG-005", "2026-10-22", "", [("동우설렁탕 본점", "12:00", "13:00")], {}),
    ("DG-006", "2026-10-23", "저희는 할랄 음식만 먹어요.", [("마리먹자", "12:30", "13:30")], {"dietary": "halal"}),
    ("DG-007", "2026-10-21", "무슬림이라 할랄 식당이어야 해요.", [("하동관", "12:00", "13:00")], {"dietary": "halal"}),
    ("DG-008", "2026-10-24", "채식주의자예요. 고기는 못 먹어요.", [("비건 키친", "18:00", "19:00")], {"dietary": "vegetarian"}),
    ("DG-009", "2026-10-25", "5살 아이와 함께 가요.", [("마포옥", "12:00", "13:00")], {"kids": True}),
    ("DG-010", "2026-10-23", "아이 둘이랑 저녁 먹을 거예요.", [("해남천일관", "19:00", "20:00")], {"kids": True}),
    ("DG-011", "2026-10-20", "현금이 없어서 카드로만 결제해요.", [("명동교자 본점", "13:00", "14:00")], {"payment": True}),
    ("DG-012", "2026-10-19", "아이랑 같이 가요.", [("류니끄", "19:00", "20:30")], {"kids": True}),
    ("DG-013", "2026-10-25", "", [("하동관", "12:00", "13:00"), ("마포유가궁중족발", "18:30", "19:30")], {}),
    ("DG-014", "2026-10-20", "매운 거 좋아해요. 사진 찍기 좋은 곳이면 좋겠어요.", [("서울원조아구찜", "18:00", "19:00")], {}),
    ("DG-015", "2026-10-20", "", [("우리집떡볶이", "15:00", "15:40")], {}),
    ("DG-016", "2026-10-23", "", [("쏭타이 본점", "15:30", "16:30")], {}),
]
HOLDOUT = [
    ("DGH-001", "2026-10-25", "", [("오프닝", "19:00", "20:30")], {}),
    ("DGH-002", "2026-10-19", "", [("산도토리임자탕", "12:00", "13:00")], {}),
    ("DGH-003", "2026-10-21", "할랄 인증된 곳이어야 해요.", [("케르반 레스토랑", "13:00", "14:00")], {"dietary": "halal"}),
    ("DGH-004", "2026-10-22", "비건이에요.", [("러빙헛 스마일", "12:00", "13:00")], {"dietary": "vegetarian"}),
    ("DGH-005", "2026-10-24", "초등학생 아이 동반이에요.", [("주양두리돈까스", "12:00", "13:00")], {"kids": True}),
    ("DGH-006", "2026-10-23", "", [("파르코", "15:30", "16:30")], {}),
    ("DGH-007", "2026-10-24", "카드만 들고 가요. 카드 되나요?", [("하동관", "12:00", "13:00")], {"payment": True}),
    ("DGH-008", "2026-10-19", "부모님 모시고 가요.", [("리틀갱스터", "19:00", "20:30"), ("하동관", "12:00", "13:00")], {}),
]


def build(rows, make_tools) -> list[dict]:
    out = []
    for cid, day, note, meals, conds in rows:
        tools = make_tools()                         # 시나리오마다 새 묶음 — 같은 가게가 두 시나리오에 나와도 반복 거절에 안 걸린다
        items, expect = [{"item_id": "a1", "seq": 1, "kind": "activity", "title": "오전 관광", "start": f"{day}T10:00",
                          "end": f"{day}T11:30", "place": {"name": "경복궁"}}], {}
        for n, (shop, start, end) in enumerate(meals, start=1):
            item_id = f"m{n}"
            found = tools.call("find_place", {"name": shop})
            if not found.get("found") or not found.get("place_uid"):
                raise SystemExit(f"{cid} {shop}: 원장에서 못 찾았다 — {found}")
            uid = found["place_uid"]
            open_at = tools.call("check_open_at", {"place_uid": uid, "start": f"{day}T{start}", "end": f"{day}T{end}"})
            verdicts = {"found": found["verdict"], "open_at": open_at["verdict"]}
            must = ["found", "open_at"]
            if conds.get("dietary"):
                state = tools.call("check_attributes", {"place_uid": uid, "wanted": [conds["dietary"]]})["attributes"][conds["dietary"]]["state"]
                verdicts["dietary"] = STATE_VERDICT[state]
                must.append("dietary")
            for cond in ("kids", "payment"):
                if conds.get(cond):
                    word = ATTR_OF[cond]
                    state = tools.call("check_attributes", {"place_uid": uid, "wanted": [word]})["attributes"][word]["state"]
                    verdicts[cond] = STATE_VERDICT[state]
                    must.append(cond)
            items.append({"item_id": item_id, "seq": n + 1, "kind": "dining", "title": f"{shop} 식사",
                          "start": f"{day}T{start}", "end": f"{day}T{end}", "place": {"name": shop}})
            expect[item_id] = {"place_uid": uid, "must": must, "must_not": [c for c in CONDS if c not in must],
                               "verdicts": verdicts}
        out.append({"id": cid, "plan": {"date": day, "customer_notes": note, "items": items}, "expect": expect})
    return out


def main(argv: list[str] | None = None) -> int:
    import psycopg

    from app.domains.travel_ops.instances.dining.agent_tools import DiningTools

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dsn", required=True)
    args = parser.parse_args(argv)

    @contextmanager
    def connect():
        with psycopg.connect(args.dsn, autocommit=True) as conn:
            yield conn

    for name, rows in (("dining_agent_v1.jsonl", DEV), ("dining_agent_holdout_v1.jsonl", HOLDOUT)):
        cases = build(rows, lambda: DiningTools(connect, max_calls=1000))
        with (OUT / name).open("w", encoding="utf-8", newline="\n") as handle:
            for case in cases:
                handle.write(json.dumps({**case, "built": {"on": date.today().isoformat(), "ledger": args.dsn.rsplit("/", 1)[-1]}},
                                        ensure_ascii=False) + "\n")
        verdicts = [v for c in cases for e in c["expect"].values() for v in e["verdicts"].values()]
        print(name, len(cases), "cases", {v: verdicts.count(v) for v in set(verdicts)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

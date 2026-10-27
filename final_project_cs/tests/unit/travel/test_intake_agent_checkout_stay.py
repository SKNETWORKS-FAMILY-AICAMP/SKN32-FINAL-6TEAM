# -*- coding: utf-8 -*-
"""`[2026-10-27 A 접수·읽기 전수검사]` 읽기 에이전트는 「체크아웃」 줄도 숙박(`kind: lodging`)으로 읽는다(지시문 `lodging for hotel
stay/check-in/check-out`). `e43e99681`(체크인 없는 숙박) 뒤로 그 줄이 체크아웃이 아니라 **새 숙박의 시작**이 되어, 마지막 날 11:00 에
시작해 다음 날까지 묵는 가짜 숙박이 생기고 진짜 숙박은 「체크아웃 줄이 없어」로 채워졌다.
"""
from __future__ import annotations

from app.domains.travel_ops.components.intake.assemble import collect

HOTEL = {"name": "롯데호텔 서울", "latitude": 37.5653, "longitude": 126.9810, "kind": "activity", "source": "kakao"}
TOWER = {"name": "남산서울타워", "latitude": 37.5512, "longitude": 126.9882, "kind": "activity", "source": "kakao"}
SOURCE = [{"source_id": "s1", "position": 0, "kind": "chat",
           "transcript": "15:00 롯데호텔 서울 체크인\n10:00 남산타워\n11:00 롯데호텔 서울 체크아웃"}]


def _agent_claims(rows):
    claims = []
    for index, (line, title, day, start, kind, place) in enumerate(rows):
        for field, value in (("title", title), ("date", day), ("starts_at", start), ("kind", kind), ("place", place)):
            if value is None:
                continue
            claims.append({"source_id": "s1", "field": f"items[{index}].{field}", "value": value, "method": "llm_agent",
                           "evidence": {"line": line}})
    return claims


def test_a_check_out_line_the_agent_read_as_lodging_closes_the_stay_instead_of_opening_a_new_one():
    claims = _agent_claims([(1, "롯데호텔 서울 체크인", "2030-11-06", "15:00", "lodging", HOTEL),
                            (2, "남산타워", "2030-11-07", "10:00", "activity", TOWER),
                            (3, "롯데호텔 서울 체크아웃", "2030-11-08", "11:00", "lodging", HOTEL)])
    got = collect(sources=SOURCE, claims=claims)
    stays = [row for row in got.rows if row["kind"] == "lodging"]
    assert len(stays) == 1, f"숙박은 하나다: {[(s['title'], s['date'], s['end_date']) for s in stays]}"
    stay = stays[0]
    assert (stay["date"], stay["start"], stay["end_date"], stay["end"]) == ("2030-11-06", "15:00", "2030-11-08", "11:00")
    assert not any("체크아웃 줄이 없어" in f["note"] for f in got.filled), "체크아웃 줄이 있는데 「없어」로 채우지 않는다"


def test_a_lodging_line_without_check_out_words_still_opens_a_stay():
    """`e43e99681` 의 체크인 없는 숙박(에이전트 · 고객이 숙박으로 고른 줄)은 그대로다."""
    claims = _agent_claims([(1, "롯데호텔 서울", "2030-11-06", None, "lodging", HOTEL),
                            (2, "남산타워", "2030-11-07", "10:00", "activity", TOWER)])
    stay = next(row for row in collect(sources=SOURCE, claims=claims).rows if row["kind"] == "lodging")
    assert (stay["date"], stay["start"], stay["end_date"], stay["end"]) == ("2030-11-06", "15:00", "2030-11-07", "11:00")

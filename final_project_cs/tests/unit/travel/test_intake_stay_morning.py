# -*- coding: utf-8 -*-
"""계획 확인(등록 전)에도 묵는 날 아침 「숙소 → 그날 첫 일정」 이동. `[2026-10-13 사용자 지시]`

☆전에는 아침 이동이 등록 뒤 일정 화면에만 있었다 — 확인 화면은 같은 날 이웃 일정 사이 이동만 계산했다.
  이제 확인 화면이 같은 계산기로 아침 구간을 계산해 싣고(`from_stay` · 그날 일차), 등록은 그 구간을 그날 첫 일정 앞에 그대로 싣는다.
"""
from __future__ import annotations

from datetime import timedelta

from app.domains.travel_ops.components.intake import registered_moves, review
from app.domains.travel_ops.components.intake.assemble import assemble
from app.domains.travel_ops.components.intake.hours import HoursFacts


def _engine():
    def run(a, b, arrive, not_before=None):
        start = arrive - timedelta(minutes=20) if not_before is None or not_before < arrive - timedelta(minutes=20) else not_before
        option = {"id": "subway", "label": "지하철", "eta_min": 15, "uses": []}
        return {"route": {"options": [option], "planned": "subway"}, "starts_at": start,
                "ends_at": start + timedelta(minutes=15), "eta_min": 15, "left_out": []}, None
    return run


def _inputs():
    sources = [{"source_id": "s", "position": 0, "kind": "text", "filename": None,
                "transcript": "15:00 롯데호텔 체크인\n18:00 명동교자\n10:00 남산타워\n11:00 체크아웃"}]
    rows = [("롯데호텔 체크인", "2030-11-06", "15:00", "activity", ("롯데호텔 서울", 37.5653, 126.9810)),
            ("명동교자", "2030-11-06", "18:00", "dining", ("명동교자", 37.5636, 126.9858)),
            ("남산타워", "2030-11-07", "10:00", "activity", ("N서울타워", 37.5512, 126.9882)),
            ("체크아웃", "2030-11-08", "11:00", "activity", None)]
    claims = []
    for i, (title, day, start, kind, place) in enumerate(rows):
        values = {"title": title, "date": day, "starts_at": start, "kind": kind}
        if place:
            values["place"] = {"name": place[0], "latitude": place[1], "longitude": place[2], "source": "customer_pick"}
        claims.extend({"source_id": "s", "field": f"items[{i}].{field}", "value": value, "method": "customer",
                       "evidence": {"line": i + 1}, "needs_review": False, "note": None} for field, value in values.items())
    return sources, claims


def test_the_plan_check_shows_the_morning_move_from_the_stay_and_registration_keeps_it(monkeypatch):
    monkeypatch.setattr(review, "facts_for", lambda *args: HoursFacts(True, {"hours": ["00:00", "23:59"]}))
    monkeypatch.setattr(review, "default_engine", lambda party, modes=None, **kw: _engine())
    sources, claims = _inputs()
    built = review.build(None, tenant_id="t", intake_id="i", revision=1, sources=sources, claims=claims)
    stay = next(item for item in built["items"] if item["kind"] == "lodging")
    assert (stay["title"], stay["date"], stay["end_date"]) == ("롯데호텔", "2030-11-06", "2030-11-08")
    morning = [move for move in built["moves"] if move.get("from_stay")]
    tower = next(item for item in built["items"] if item["title"] == "남산타워")
    assert [(m["from"], m["to"], m["date"], m["day"]) for m in morning] == [(stay["id"], tower["id"], "2030-11-07", tower["day"])], \
        "체크인 다음 날 첫 일정 하나 — 그날 일차로"
    assert (morning[0]["depart"], morning[0]["arrive"]) == ("09:40", "09:55"), "첫 일정 도착에 맞춘 늦은 출발(06:00 하한)"
    evening = [m for m in built["moves"] if not m.get("from_stay") and m["from"] == stay["id"]]
    assert evening and evening[0]["depart"] >= "15:00", "체크인 날 저녁 이동은 체크인 시각부터"

    body = assemble(intake_id="i", revision=1, sources=sources, claims=claims).body
    registered = registered_moves.with_review_moves(body, built)
    kinds = [(row["kind"], row["title"]) for row in registered["items"]]
    at = kinds.index(("activity", "남산타워"))
    assert registered["items"][at - 1]["kind"] == "mobility" and registered["items"][at - 1]["detail"]["from_stay"] is True, \
        "등록은 확인 화면의 아침 구간을 그날 첫 일정 바로 앞에 싣는다"
    assert registered["items"][at - 1]["starts_at"].startswith("2030-11-07T09:40")

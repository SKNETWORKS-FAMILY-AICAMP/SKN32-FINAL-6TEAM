# -*- coding: utf-8 -*-
"""계획서의 이동 말 줄(「택시로 이동」 · 「지하철 타고」)은 일정이 아니라 **앞 · 뒤 일정 사이 구간의 수단**이다. `[2026-10-19 사용자 지시]`

☆전에는 둘 중 한 길로만 됐다 — 읽기 에이전트가 앞뒤 장소를 짚어 줄 때만 구간 수단이 됐고, 앞뒤를 비우면 수단이 버려졌으며,
  규칙으로 읽으면 「택시로 이동」이 장소 없는 일정 한 줄로 남고 그 구간은 추천 수단(예: 지하철)으로 계산됐다.
★이제: 이동 말 줄은 일정에서 빼고(`items[n].removed`), 원문에서 그 줄 바로 앞 일정과 바로 뒤 일정(같은 날) 사이 구간에 수단을 적는다
  (`moves[앞~뒤].mode`, 방법 `rule`). 앞이나 뒤 일정이 없으면(마지막 날 「공항철도 타고 인천공항」) 줄을 「장소 없이 둔 출발」로 남긴다 — 시각은 지킨다.
★화면에 고를 수 있는 수단은 지하철 · 버스 · 택시 · 도보뿐이다 — 공항철도 · 전철 → 지하철, 공항버스 · 리무진 → 버스, 걸어서 → 도보.
  자전거 · 렌터카 · 기차처럼 화면 칸이 없는 수단은 구간에 넣지 않고 근거에만 남긴다.
"""
from __future__ import annotations

from datetime import date

from app.domains.travel_ops.components.intake.landmarks import move_mode
from app.domains.travel_ops.components.intake.pipeline import read_source
from app.domains.travel_ops.components.intake.review import picked_modes

TODAY = date(2030, 1, 1)


class Tour:
    PLACES = {"경복궁": (37.5796, 126.9770, "12"), "광장시장": (37.5700, 126.9996, "38"), "N서울타워": (37.5512, 126.9882, "12"),
              "덕수궁": (37.5658, 126.9751, "12"), "남대문시장": (37.5592, 126.9773, "38")}

    def find(self, name, area_code=None, **_):
        if name not in self.PLACES:
            return None
        lat, lon, kind = self.PLACES[name]
        return {"matched_title": name, "content_id": "c-" + name, "content_type_id": kind, "latitude": lat, "longitude": lon,
                "address": "서울특별시 종로구"}


class Kakao:
    def __init__(self):
        self.asked = []

    def search(self, query, size=5, near=None, **kw):
        self.asked.append(query)
        return [{"id": "x", "name": "○○택시 본사", "category": "교통", "category_group": "", "address": "서울 중구",
                 "latitude": 37.56, "longitude": 126.98}] if "택시" in query else []


def _field(rows, name):
    return next((r for r in rows if r["field"] == name), None)


def _read(text, **kw):
    return read_source(text, tour=Tour(), kakao=Kakao(), our_places=[], today=TODAY, position=0, **kw)


def test_a_taxi_line_between_two_stops_becomes_that_segment_mode_and_leaves_the_schedule():
    rows = _read("1일차 2030-01-05\n10:00 경복궁\n11:30 택시로 이동\n12:00 광장시장")
    removed = _field(rows, "items[1].removed")
    assert removed is not None and removed["value"] is True and removed["method"] == "rule"
    assert removed["evidence"]["method"] == "move_phrase"
    mode = _field(rows, "moves[0-0~0-2].mode")
    assert mode is not None and (mode["value"], mode["method"]) == ("taxi", "rule")
    assert picked_modes(rows) == {"0-0~0-2": "taxi"}


def test_untimed_move_lines_and_other_modes_map_to_the_four_screen_modes():
    rows = _read("1일차 2030-01-05\n10:00 경복궁\n지하철 타고\n12:00 광장시장\n15:00 덕수궁\n걸어서 이동\n17:00 남대문시장")
    # 시각 없는 줄은 규칙이 시각 줄 뒤에 항목으로 읽는다(4 · 5번) — 구간은 번호가 아니라 원문 줄 순서로 정한다
    assert picked_modes(rows) == {"0-0~0-1": "subway", "0-2~0-3": "walk"}
    assert _field(rows, "items[4].removed")["value"] is True and _field(rows, "items[5].removed")["value"] is True


def test_the_last_airport_line_stays_as_a_placeless_departure_with_its_time():
    """앞 일정은 있어도 뒤 일정이 없다 — 구간이 아니라 그날 마지막 「출발」이다. 서울 밖(인천공항)이라 장소는 찾지 않는다."""
    rows = _read("1일차 2030-01-05\n10:00 경복궁\n18:00 공항철도 타고 인천공항")
    assert _field(rows, "items[1].removed") is None
    place = _field(rows, "items[1].place")
    assert place["value"] is None and place["evidence"]["method"] == "move_phrase"
    assert place["evidence"]["destination"] == "인천공항"
    assert not any(r["field"].startswith("moves[") for r in rows)


def test_move_lines_never_cross_days():
    rows = _read("1일차 2030-01-05\n10:00 경복궁\n택시로 이동\n2일차 2030-01-06\n10:00 광장시장")
    assert not any(r["field"].startswith("moves[") for r in rows)
    assert _field(rows, "items[1].removed") is None


def test_mode_words_map_only_to_modes_the_screen_has():
    assert [move_mode(w) for w in ("택시", "카카오 택시", "공항철도", "AREX", "전철", "공항버스", "리무진", "걸어서", "도보")] == \
        ["taxi", "taxi", "subway", "subway", "subway", "bus", "bus", "walk", "walk"]
    assert [move_mode(w) for w in ("따릉이", "렌터카", "KTX", None)] == [None, None, None, None]


# ── 읽기 에이전트가 앞뒤 장소를 비워 둔 이동 ─────────────────────────────
class Agent:
    model = "tripilot-pointer:e4b-ft"

    def __init__(self, answer):
        self.answer = answer

    def structured(self, system, user, schema, *, num_predict=160):
        return self.answer


def _item(quote, start):
    return {"place_quote": quote, "day": 1, "date": "2030-01-05", "date_quote": "1일차 2030-01-05", "start": start, "end": None,
            "time_quote": start, "kind": "activity"}


def test_an_agent_move_without_its_ends_falls_on_the_stops_around_its_line():
    """☆에이전트가 「택시로 이동」을 구간 이동으로 읽었지만 앞뒤 장소를 비워 두면(`from_quote` · `to_quote` 가 null) 수단이 어느 구간에도 붙지 않았다."""
    text = "1일차 2030-01-05\n10:00 경복궁\n12:00 광장시장\n택시로 이동\n15:00 덕수궁"
    agent = Agent({"items": [_item("경복궁", "10:00"), _item("광장시장", "12:00"), _item("덕수궁", "15:00")],
                   "moves": [{"mode": "taxi", "scope": "segment", "day": 1, "from_quote": None, "to_quote": None, "quote": "택시로 이동"}],
                   "conditions": [], "preferences": [], "requests": ["register"], "missing": [],
                   "trip": {"party_size": None, "days": None, "nights": None}})
    rows = read_source(text, today=TODAY, agent=agent, agent_mode="on", position=0)
    assert picked_modes(rows) == {"0-1~0-2": "taxi"}

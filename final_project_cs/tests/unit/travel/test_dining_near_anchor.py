# -*- coding: utf-8 -*-
"""「○○ 근처 맛집」의 기준점 — 고객이 댄 동네 · 명소 이름을 **여행자가 뜻한 곳**으로 잡는다. `[2026-10-16]`

☆화면 점검(관광공사 키 없는 로컬): 「서촌 가서 뭐 좀 먹고 싶은데 근처 맛집 있어?」 → 중랑구 상봉동 가게 3곳.
  카카오 후보가 서촌한옥마을(여행 > 관광,명소 · 종로구) · 「서촌」(부동산 > 지명 · 중랑구 상봉동) · 「서촌」(술집)이었고,
  이름이 **정확히 같은** 후보를 먼저 골라 중랑구의 동네 지명이 기준점이 됐다.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation import trip_messages

KST = ZoneInfo("Asia/Seoul")
AT = datetime(2026, 10, 20, 11, 0, tzinfo=KST)

#: 2026-10-16 카카오 실측 후보(좌표만 줄였다)
SEOCHON = [
    {"name": "서촌한옥마을", "category_group": "", "category": "여행 > 관광,명소", "address": "서울 종로구 통의동",
     "latitude": 37.578728, "longitude": 126.970},
    {"name": "서촌", "category_group": "", "category": "부동산 > 지명", "address": "서울 중랑구 상봉동",
     "latitude": 37.605573, "longitude": 127.085},
    {"name": "서촌", "category_group": "FD6", "category": "음식점 > 술집 > 호프,요리주점", "address": "서울 종로구 자하문로 55",
     "latitude": 37.580897, "longitude": 126.971},
]


class _Store:
    def places(self, conn, trip_id):
        return []


def _anchor(monkeypatch, text, candidates):
    from app.domains.travel_ops.components.intake import places

    monkeypatch.setattr(places, "resolve", lambda *a, **k: SimpleNamespace(
        status="unresolved", latitude=None, longitude=None, name=None, method=None, candidates=candidates))
    decision = SimpleNamespace(item=None, raw={"place_text": text})
    anchor, _ = trip_messages._near_anchor(decision, message=f"{text} 근처 맛집 있어?", items=[], at=AT, store=_Store(),
                                          conn=None, trip_id=uuid4(), place_source=None, kakao_source=object())
    return anchor


def test_a_neighbourhood_name_prefers_the_tourist_spot_over_a_same_named_local_place_elsewhere(monkeypatch):
    anchor = _anchor(monkeypatch, "서촌", SEOCHON)
    assert anchor is not None and anchor["name"] == "서촌한옥마을", anchor


def test_without_a_tourist_spot_the_exact_name_still_wins_and_food_is_never_the_anchor(monkeypatch):
    local = [c for c in SEOCHON if c["name"] != "서촌한옥마을"]
    anchor = _anchor(monkeypatch, "서촌", local)
    assert anchor is not None and anchor["name"] == "서촌", anchor
    assert anchor["latitude"] == pytest.approx(37.605573)                 # 술집(FD6)이 아니라 지명


def test_a_station_is_kept_when_there_is_no_tourist_spot(monkeypatch):
    station = [{"name": "연신내역 3호선", "category_group": "SW8", "category": "교통,수송 > 지하철,전철 > 수도권3호선",
                "address": "서울 은평구 통일로 지하 849", "latitude": 37.619, "longitude": 126.921},
               {"name": "연신내새마을금고 본점", "category_group": "BK9", "category": "금융,보험 > 금융서비스 > 은행 > 새마을금고",
                "address": "서울 은평구 연서로26길 10", "latitude": 37.618, "longitude": 126.920}]
    anchor = _anchor(monkeypatch, "연신내", station)
    assert anchor is not None and anchor["name"] == "연신내역 3호선", anchor



def test_a_tourist_spot_marked_only_by_its_group_code_also_wins(monkeypatch):
    """카카오 후보는 관광지를 분류 글(「여행 > 관광,명소」)이나 그룹 코드(`AT4` 관광명소)로 표시한다 — 둘 중 하나만 있어도 관광지다.
    ☆다른 세션의 LLM 켜짐 재현(`eval/reports/2026-10-16_dining_remaining_llm_probe.json`)이 코드만 있는 후보를 썼다."""
    coded = [{"name": "서촌한옥마을", "category_group": "AT4", "latitude": 37.5803, "longitude": 126.9709, "address": "서울 종로구"},
             {"name": "서촌", "category_group": "", "latitude": 37.5961, "longitude": 127.0928, "address": "서울 중랑구 상봉동"},
             {"name": "서촌", "category_group": "FD6", "latitude": 37.57, "longitude": 126.97, "address": "서울 종로구"}]
    anchor = _anchor(monkeypatch, "서촌", coded)
    assert anchor is not None and anchor["name"] == "서촌한옥마을", anchor

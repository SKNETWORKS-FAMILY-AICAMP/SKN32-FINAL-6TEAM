# -*- coding: utf-8 -*-
"""먼저 채우기가 **빈칸 일정만** 맞춰 본다 — 실제 접수 길(POST → 뒤에서 읽기 → 검사 → 먼저 채우기 → 확인 화면)에서. `[2026-10-28 서빙 속도]`

☆왜. 확인 화면 공개 전 먼저 채우기의 전체 자동 추천(`autofix.plan`)이 빈칸이 아닌 확인 필요 일정(지점 모호한 「올리브영」 · 운영시간 모름 · 늦게 닿는 구간)까지
  후보를 모으고 시간표 이동으로 맞춰 봤다 — 먼저 채우기는 그 결과를 쓰지 않는다. 격리 합성 측정(계산기 호출당 0.3초): 그 계산이 처리 9.9~11.0초 중 약 6.1초.
★지키는 것: 빈칸(「성수 식당」)은 전과 같은 곳으로 채운다 · 이름을 적은 일정은 그대로 · 확인 화면은 먼저 채우기 · 해석 답 반영 뒤에 공개(`stage=review`) ·
  단계 시각은 서버 로그 한 줄(고객 글 · 장소 이름 없음).

재현:

    python -m pytest tests/e2e/test_intake_prefill_scope.py -q
"""
from __future__ import annotations

import logging
from datetime import timedelta

from app.domains.travel_ops.components.intake import autofix as autofix_module
from app.domains.travel_ops.components.intake import candidates as candidates_module
from app.domains.travel_ops.components.intake import pipeline
from app.domains.travel_ops.components.intake import review as review_module

from .test_intake_prefill import filled  # noqa: F401 — 성수 장소 · 요식 원장 · 지명 사전
from .test_intake_review import _client, _item, _key, _send, rv  # noqa: F401
from .test_trip_api import api  # noqa: F401
from tests.helpers import relative_dates as reldate

# ★`[2026-10-28]` 박아 둔 날짜는 실행 날 기준으로 옮긴다 — 전부-과거 가드(`all_dates_before_today`)가 실제 시계를 읽는다.
#   요일 · 순서 · 간격은 원래 자료와 같다(`tests/helpers/relative_dates.py`). 이 파일은 상대 날짜 전환(4fee819ca)과 따로 들어와 빠졌다.
D_2026_10_15 = reldate.day("2026-10-15")

PLAN = (f"{D_2026_10_15}\n"
        "10시 경복궁 관람 1시간 반\n"
        "11시 올리브영\n"
        "12시 반 광장시장 빈대떡\n"
        "15:00 성수 식당\n"
        "16:00 N서울타워\n"
        "18:00 서울역 인근 저녁 식당")


def _subway16(party=None, modes=None, **_kw):
    """시험용 이동 계산기(모방) — 어느 구간이든 지하철 16분, 앞 일정 끝 뒤에 못 떠나면 못 닿는다(진짜 계산기와 같은 답 모양)."""
    def run(a, b, arrive, not_before=None):
        start = arrive - timedelta(minutes=26)
        if not_before is not None and start < not_before:
            return None, {"code": "arrive_late", "reason": "늦음"}
        option = {"id": "subway_1", "label": "subway_1", "eta_min": 16, "uses": ["2호선:을지로입구"], "fare_krw": 1550}
        return {"route": {"options": [option], "planned": "subway_1"}, "starts_at": start,
                "ends_at": start + timedelta(minutes=16), "eta_min": 16, "left_out": []}, None
    return run


def test_prefill_fits_only_the_blank_and_still_fills_it(filled, monkeypatch, caplog):  # noqa: F811
    for module in (review_module, candidates_module, autofix_module):
        monkeypatch.setattr(module, "default_engine", _subway16)
    fitted: list[str] = []
    real_fit = autofix_module._fit_window

    def fit(conn, tenant_id, item, *args, **kwargs):
        fitted.append(item["title"])
        return real_fit(conn, tenant_id, item, *args, **kwargs)
    monkeypatch.setattr(autofix_module, "_fit_window", fit)
    caplog.set_level(logging.INFO, logger=pipeline.log.name)
    caplog.set_level(logging.INFO, logger="app.domains.travel_ops.components.intake.prefill")
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, PLAN)
    assert view["status"] == "review" and view["revision"] == 2
    assert set(fitted) == {"성수 식당"}, fitted                                         # 빈칸이 아닌 「올리브영」 등은 맞춰 보지 않는다
    plain = _item(view, "성수 식당")
    assert plain["place"]["name"] == "성수가든" and plain["starts_at"] == "15:00"       # 빈칸은 전과 같은 곳 · 고객이 적은 시각 그대로
    assert [f["item"] for f in view["prefill"]["filled"]] == [plain["id"]]
    station = _item(view, "서울역 인근 저녁 식당")                                       # 둘째 빈칸 — 후보가 없어 전처럼 그대로(고치기 전 같은 시험의 결과와 같다)
    assert station["place"] is None and station["place_state"] == "needs_choice"
    assert [k["item"] for k in view["prefill"]["kept"]] == [station["id"]] and view["prefill"]["questions"] == []
    olive = _item(view, "올리브영")
    assert olive["starts_at"] == "11:00" and olive["place_state"] == "picked_nearest"   # 이름을 적은 일정은 그대로
    stage = [r.getMessage() for r in caplog.records if "intake stage timing" in r.getMessage()]
    assert len(stage) == 1 and view["intake_id"] in stage[0], stage
    for field in ("read_s=", "check_s=", "prefill_s=", "answers_s=", "to_review_s=", "foreground_s=", "filling=True"):
        assert field in stage[0], stage[0]
    timing = [r.getMessage() for r in caplog.records if "intake prefill timing" in r.getMessage()]
    assert len(timing) == 1 and "planned_items=2" in timing[0] and "gaps_seen=2" in timing[0], timing   # 빈칸 둘(「성수 식당」 · 「서울역 인근 저녁 식당」)만
    assert not any(word in line for line in stage + timing for word in ("성수", "올리브영", "경복궁", "서울역"))

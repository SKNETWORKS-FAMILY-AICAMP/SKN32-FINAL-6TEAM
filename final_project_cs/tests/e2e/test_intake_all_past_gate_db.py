"""DB: 전부 과거인 계획 글은 접수 읽기 끝에 `fatal`(all_dates_in_past) — 확인 화면(`review`)으로 가지 않는다. 일부만 과거면 지금처럼 `review`.

`[2026-10-26 사용자 지시]` 실제 접수 입구(`POST /v1/web/trip-intakes`) → 뒤에서 읽기(`pipeline.process`) → 조회(`GET …/{id}`) 그대로. 제품 시계(`itinerary_checks.datetime`)만
시험이 고정한다(다른 고정 시계 fixture 가 있어도 이 시험의 판정이 바뀌지 않게). 모델 호출 없음(규칙 읽기 · 시험 관광공사 모방).
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.domains.travel_ops.components.itinerary import itinerary_checks as checks
from app.infrastructure.db.session import get_connection

from .test_intake_review import Kakao, Tour, _client, _key, _send, rv  # noqa: F401 — 같은 환경 · 모방을 그대로 쓴다
from .test_trip_api import api  # noqa: F401 — `rv` 가 쓰는 픽스처

NOW = datetime(2032, 5, 8, 12, tzinfo=checks.KST)
ALL_PAST = "2032-05-06\n10시 경복궁 관람 1시간 반\n2032-05-07\n15시 N서울타워"
MIXED = "2032-05-07\n10시 경복궁 관람 1시간 반\n2032-05-09\n15시 N서울타워"
MESSAGE = "모든 일정이 오늘 이전이에요. 여행 날짜를 확인해주세요"


@pytest.fixture()
def frozen(monkeypatch):
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)
    monkeypatch.setattr(checks, "datetime", Frozen)


def _claims(intake_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM intake_claims WHERE intake_id=%s AND method <> 'customer'", (intake_id,))
        return cur.fetchone()[0]


def test_wholly_past_text_ends_on_plan_entry_not_review(rv, frozen):
    client, _, _ = _client()
    view = _send(client, _key(client), text=ALL_PAST)
    assert view["status"] == "fatal", view["status"]
    assert view["fatal"] == {"code": "all_dates_in_past", "detail": MESSAGE}
    assert _claims(view["intake_id"]) == 0                          # 읽다 만 값은 남기지 않는다(다른 fatal 과 같다)


def test_partly_past_text_still_reaches_review(rv, frozen):
    client, _, _ = _client()
    view = _send(client, _key(client), text=MIXED)
    assert view["status"] == "review" and view["fatal"] is None
    assert MESSAGE not in str(view["review"])

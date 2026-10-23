# -*- coding: utf-8 -*-
"""접수 입구의 빠른 거름 — 접수 → 조회. `[2026-10-19 사용자 결정]` 설계서 §5 · 계약 「접수 입구의 빠른 거름」.

★지키려는 것: 빈 글 · 「파이썬 for 루프에 대해서 알려줘」는 **모델을 부르지 않고**(호출 0) 바로 「일정 없음」 — `screened` 가 남고 로딩 설문(`questions[]`)이 없다.
  「편안한 강남여행」 · 「내일 경복궁」은 거르지 않고 지금처럼 읽는다. 거른 접수도 원문 줄은 남는다(사후에 오판을 센다).
"""
from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.domains.travel_ops.entry.trip_api import build_trip_router
from app.infrastructure.db.session import get_connection
from app.presentation.api.app import create_app

from .test_intake_review import Kakao, Tour, _key, rv  # noqa: F401
from .test_trip_api import api  # noqa: F401


class Counting:
    """모델 대역 — 불린 횟수만 센다(거른 접수에서는 0 이어야 한다). 답은 빈 가리키기."""

    model = "test-counting"
    calls = 0

    def json(self, system, user):
        Counting.calls += 1
        return {"spans": []}

    def structured(self, system, user, schema, *, num_predict=160):
        Counting.calls += 1
        raise RuntimeError("이 시험은 이해 에이전트를 쓰지 않는다")

    def see(self, prompt, image):
        Counting.calls += 1
        raise AssertionError("사진이 없다")


def _client():
    tour, kakao = Tour(), Kakao()
    return TestClient(create_app(
        classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
        domain_routers=[build_trip_router(place_factory=lambda: tour, kakao_factory=lambda: kakao, chat_factory=Counting)]))


def _send(client, headers, text):
    response = client.post("/v1/web/trip-intakes", headers=headers, data={"text": text})
    assert response.status_code == 202, response.text
    return client.get(f"/v1/web/trip-intakes/{response.json()['intake_id']}", headers=headers).json()


@pytest.fixture(autouse=True)
def _reset():
    Counting.calls = 0


def test_clearly_unrelated_text_is_sent_back_without_calling_the_model(rv):  # noqa: F811
    client = _client()
    headers = _key(client)
    view = _send(client, headers, "파이썬 for 루프에 대해서 알려줘")
    assert Counting.calls == 0                                                     # 모델 · 유료 호출 0
    assert view["status"] == "review" and view["screened"] == {"code": "off_topic", "rule": "other_task"}
    assert view["questions"] == [] and view["skipped_by_reading"] == [] and view["questions_phase"] is None   # 로딩 설문을 내지 않는다
    assert [line["text"] for line in view["sources"][0]["lines"]] == ["파이썬 for 루프에 대해서 알려줘"]       # 원문은 남는다
    assert view["check"]["items"] == 0
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT screened, survey_plan FROM trip_intakes WHERE intake_id=%s", (UUID(view["intake_id"]),))
        assert cur.fetchone() == ({"code": "off_topic", "rule": "other_task"}, None)


def test_an_empty_intake_is_marked_and_asks_nothing(rv):  # noqa: F811
    client = _client()
    headers = _key(client)
    view = _send(client, headers, "")
    assert view["status"] == "review" and view["screened"] == {"code": "empty", "rule": "empty"} and view["questions"] == []
    assert Counting.calls == 0


@pytest.mark.parametrize("text", ["편안한 강남여행", "내일 경복궁"])
def test_a_travel_clue_is_read_as_before(rv, text):  # noqa: F811
    client = _client()
    headers = _key(client)
    view = _send(client, headers, text)
    assert view["screened"] is None
    assert view["questions"], "거르지 않은 접수는 로딩 설문을 낸다"

# -*- coding: utf-8 -*-
"""접수 응답이 빠른 거름 결과를 말한다 — `screened`. `[2026-10-20 사용자 결정 — ST4F-615]`

웹 「직접 입력」은 「계획 확인하기」를 누르면 입력 화면에서 이 응답을 기다린다. 걸렸으면(`screened` 가 있음) 그 화면에 머물러 다시 입력을 안내하고,
아니면 진행 화면으로 넘어간다. 계약: `wiki/external/rest-endpoints/web-intakes.md` 「접수 입구의 빠른 거름」 · 표의 `POST /v1/web/trip-intakes` 줄.

★지키려는 것: 걸린 접수는 응답부터 `status: review` · `screened: {code, rule}` 이고 읽기 작업을 걸지 않는다(모델 호출 0).
  거르지 않은 접수는 지금처럼 `status: reading` · `screened: null`.
"""
from __future__ import annotations

from uuid import UUID

import pytest

from app.infrastructure.db.session import get_connection

from .test_intake_review import _key, rv  # noqa: F401
from .test_intake_screen import Counting, _client
from .test_trip_api import api  # noqa: F401


@pytest.fixture(autouse=True)
def _reset():
    Counting.calls = 0


def _post(client, headers, text):
    response = client.post("/v1/web/trip-intakes", headers=headers, data={"text": text})
    assert response.status_code == 202, response.text
    return response.json()


def _stage(intake_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, stage FROM trip_intakes WHERE intake_id=%s", (UUID(intake_id),))
        return cur.fetchone()


def test_an_unrelated_text_is_answered_as_screened_and_never_read(rv):  # noqa: F811
    client = _client()
    headers = _key(client)
    answer = _post(client, headers, "파이썬 for 루프에 대해서 알려줘")
    assert (answer["status"], answer["stage"]) == ("review", "review")
    assert answer["screened"] == {"code": "off_topic", "rule": "other_task"}
    assert Counting.calls == 0                                                   # 읽기 작업이 걸리지 않았다(모델 호출 0)
    assert _stage(answer["intake_id"]) == ("review", "review")


def test_an_empty_text_is_answered_as_screened(rv):  # noqa: F811
    client = _client()
    headers = _key(client)
    answer = _post(client, headers, "")
    assert answer["status"] == "review" and answer["screened"] == {"code": "empty", "rule": "empty"}


@pytest.mark.parametrize("text", ["편안한 강남여행", "내일 경복궁"])
def test_a_travel_clue_is_answered_as_reading_with_no_screen(rv, text):  # noqa: F811
    client = _client()
    headers = _key(client)
    answer = _post(client, headers, text)
    assert (answer["status"], answer["stage"]) == ("reading", "received")
    assert answer["screened"] is None

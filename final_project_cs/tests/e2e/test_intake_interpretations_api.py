# -*- coding: utf-8 -*-
"""해석 확인 질문 — 접수 → 질문 → 답(로딩 중 · 로딩 뒤) → 새 판 · 실시간 진행. `[2026-10-20 사용자 지시]`

★지키려는 것
 ①읽기 AI 가 빈 시간으로 읽은 줄의 규칙 일정은 **뺀 채로**(1안) 확인 화면이 나오고, `interpretations[]` 에 1안이 맨 위인 질문이 온다
 ②로딩 중 답은 저장만 하고(`pending`), 첫 검사 직후 · 「검사 끝」 알리기 전에 반영된다(새 판 — 그 일정이 들어가고 검사가 다시 돈다)
 ③로딩 뒤 답은 그 자리에서 새 판, 1안으로 되돌리면 다시 빠진다, 같은 답을 또 보내면 판을 만들지 않는다
 ④실시간 진행(SSE)으로도 같은 본문 · 읽기 진행(`GET …/events`)에 `interpretation` 이벤트 · 틀린 답 422 · 낡은 판 409 · 남의 접수 404

모델은 시험이 정한 답을 내는 대역이다(`structured` 하나) — 모델 품질이 아니라 **묻고 반영하는 길**을 본다. 관광공사 · 카카오도 모방이다.
(시험 글은 실제 접수 원문이 아니라 같은 모양으로 새로 쓴 것이다.)

재현:

    python -m pytest tests/e2e/test_intake_interpretations_api.py -v
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domains.travel_ops.components.intake import agent_read, pipeline
from app.domains.travel_ops.entry.trip_api import build_trip_router
from app.infrastructure.db.session import get_connection
from app.presentation.api.app import create_app

from .test_intake_review import Kakao, Tour, _events, _key, rv  # noqa: F401
from .test_trip_api import api  # noqa: F401

PLAN = ("2026-10-15\n"
        "10시 경복궁\n"
        "오후 1시~4시 정도\n"
        "세 시간 비는데 실내로 뭐 하면 좋을까\n"
        "17:00 광장시장 저녁")

ANSWER = {
    "guard": {"off_topic": False, "prompt_injection": False, "out_of_scope": False, "quote": None},
    "pieces": [{"kind": "plan_item", "quote": "10시 경복궁"}, {"kind": "plan_ask", "quote": "세 시간 비는데 실내로 뭐 하면 좋을까"}],
    "items": [
        {"place_quote": "경복궁", "day": 1, "date": "2026-10-15", "date_quote": "2026-10-15", "start": "10:00", "end": None,
         "time_quote": "10시", "kind": "activity"},
        {"place_quote": "광장시장", "day": 1, "date": "2026-10-15", "date_quote": "2026-10-15", "start": "17:00", "end": None,
         "time_quote": "17:00", "kind": "dining"}],
    "moves": [], "conditions": [], "preferences": [],
    "gaps": [{"kind": "free_slot", "day": 1, "start": "13:00", "end": "16:00", "quote": "오후 1시~4시 정도"}],
    "missing": [], "trip": {"party_size": None, "days": None, "nights": None}}
QID = "q-0-3"


class Reader:
    """읽기 에이전트 대역 — 계획 읽기 틀로 부르면 정한 답, 그 밖의 부름은 모른다고 한다."""

    model = "test-reader"

    def structured(self, system, user, schema, *, num_predict=160):
        if schema is agent_read.SCHEMA:
            return ANSWER
        raise RuntimeError("이 시험은 계획 읽기 말고는 모델을 쓰지 않는다")

    def json(self, *args, **kwargs):
        raise RuntimeError("이 시험은 남은 줄 가리키기를 쓰지 않는다")


@pytest.fixture()
def reading(rv, monkeypatch):  # noqa: F811
    from app.domains.travel_ops.components.intake import prepared

    real = pipeline.agent_reader_config
    monkeypatch.setattr(pipeline, "agent_reader_config", lambda tenant_id: {**real(tenant_id), "mode": "on", "prefill": "off"})
    monkeypatch.setattr(prepared, "WORKERS", 1)        # 대안 미리 준비는 뒤에서 돈다 — 이 시험은 그 결과를 보지 않으니 DB 연결을 적게(PC 메모리)
    yield rv


def _client():
    tour, kakao, reader = Tour(), Kakao(), Reader()
    return TestClient(create_app(
        classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
        domain_routers=[build_trip_router(place_factory=lambda: tour, kakao_factory=lambda: kakao, chat_factory=lambda: reader)]))


def _send(client, headers) -> str:
    response = client.post("/v1/web/trip-intakes", headers=headers, data={"text": PLAN})
    assert response.status_code == 202, response.text
    return response.json()["intake_id"]


def _view(client, headers, intake_id):
    return client.get(f"/v1/web/trip-intakes/{intake_id}", headers=headers).json()


def _titles(view):
    return [i["title"] for i in view["review"]["items"]]


def _answer(client, headers, intake_id, revision, option, *, status=200, stream=False):
    response = client.post(f"/v1/web/trip-intakes/{intake_id}/interpretations", headers={**headers, **(
        {"Accept": "text/event-stream"} if stream else {})}, json={"revision": revision, "answers": {QID: option}})
    assert response.status_code == status, response.text
    return response if stream else response.json()


def test_the_agent_reading_is_the_first_choice_and_the_rule_item_waits_out_of_the_plan(reading):
    client = _client()
    headers = _key(client)
    view = _view(client, headers, _send(client, headers))
    assert view["status"] == "review" and view["revision"] == 1
    assert "정도" not in _titles(view) and _titles(view) == ["경복궁", "광장시장"]          # ①1안 — 일정에 넣지 않았다
    [question] = view["interpretations"]
    assert question["id"] == QID and question["quote"] == "오후 1시~4시 정도" and question["applied"] == "reading"
    assert [o["id"] for o in question["options"]][:2] == ["reading", "item"] and question["options"][0]["recommended"] is True
    assert question["options"][0]["label"] == "13:00~16:00 빈 시간"
    assert question["options"][1]["action"] == "pick_myself"                              # 장소를 못 찾았다 — 지어내지 않고 직접 고르게


def test_an_answer_during_loading_is_kept_and_applied_before_the_check_is_announced(reading):
    client = _client()
    headers = _key(client)
    intake_id = _send(client, headers)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:   # 읽기 일꾼이 아직 「검사 · 먼저 채우기 중」인 순간으로 되돌린다
        cur.execute("UPDATE trip_intakes SET stage='checking' WHERE intake_id=%s", (intake_id,))
    loading = _view(client, headers, intake_id)
    assert loading["status"] == "reading"
    done = _answer(client, headers, intake_id, 1, "item")
    assert done["interpretation"] == {"applied": False, "pending": True, "revision": 1}       # ②저장만
    assert done["interpretations"][0]["answer"] == "item" and done["interpretations"][0]["applied"] == "reading"
    sent: list[tuple[str, dict]] = []
    pipeline._apply_interpretations(get_connection, reading["tenant"], intake_id, tour=Tour(), kakao=Kakao(), dining=None,
                                    push=lambda name, body: sent.append((name, body)))
    # `[2026-10-24 사용자 확정 — 진행 표시 ③ · ST4F-732]` 답을 넣는 동안 「답 반영 0/1」 → 다시 검사까지 끝나면 「1/1」
    assert sent == [("progress", {"phase": "answers", "done": 0, "total": 1, "current": None}),
                    ("progress", {"phase": "answers", "done": 1, "total": 1, "current": None})]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET stage='review' WHERE intake_id=%s", (intake_id,))
    view = _view(client, headers, intake_id)
    assert view["revision"] == 2 and "정도" in _titles(view)                                 # 새 판 · 검사가 그 판으로 다시 돌았다
    assert view["interpretations"][0]["applied"] == "item"
    pipeline._apply_interpretations(get_connection, reading["tenant"], intake_id, tour=Tour(), kakao=Kakao(), dining=None)
    assert _view(client, headers, intake_id)["revision"] == 2                                 # 두 번 불러도 판은 하나


def test_after_loading_an_answer_makes_a_new_revision_and_switching_back_takes_it_out(reading):
    client = _client()
    headers = _key(client)
    intake_id = _send(client, headers)
    done = _answer(client, headers, intake_id, 1, "item")
    assert done["interpretation"] == {"applied": True, "pending": False, "revision": 2}
    assert "정도" in _titles(done) and done["interpretations"][0]["applied"] == "item"
    back = _answer(client, headers, intake_id, 2, "reading")
    assert back["interpretation"]["revision"] == 3 and "정도" not in _titles(back)
    same = _answer(client, headers, intake_id, 3, "reading")
    assert same["interpretation"] == {"applied": True, "pending": False, "revision": 3}          # ③판을 만들지 않는다


def test_streamed_answers_bad_answers_stale_and_strangers(reading):
    client = _client()
    headers = _key(client)
    intake_id = _send(client, headers)
    events = _events(_answer(client, headers, intake_id, 1, "item", stream=True).text)
    names = [name for name, _ in events]
    assert names[0] == "accepted" and ("stage", "applying") in [(n, b.get("stage")) for n, b in events]
    result = dict(events)["result"]
    assert result["interpretation"]["revision"] == 2 and "정도" in _titles(result)
    bad = client.post(f"/v1/web/trip-intakes/{intake_id}/interpretations", headers=headers,
                      json={"revision": 2, "answers": {QID: "nope", "q-9-9": "reading"}})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_answers"
    stale = client.post(f"/v1/web/trip-intakes/{intake_id}/interpretations", headers=headers, json={"revision": 1, "answers": {QID: "reading"}})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_revision"
    stranger = client.post(f"/v1/web/trip-intakes/{intake_id}/interpretations", headers=_key(client),
                           json={"revision": 2, "answers": {QID: "reading"}})
    assert stranger.status_code == 404


def test_the_reading_progress_stream_carries_the_question(reading):
    client = _client()
    headers = _key(client)
    intake_id = _send(client, headers)
    body = client.get(f"/v1/web/trip-intakes/{intake_id}/events", headers=headers).text
    questions = [b for name, b in _events(body) if name == "interpretation"]
    assert questions and questions[-1]["id"] == QID and questions[-1]["options"][0]["id"] == "reading"

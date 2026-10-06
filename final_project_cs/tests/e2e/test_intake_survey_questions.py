# -*- coding: utf-8 -*-
"""로딩 중 질문 — `questions[]` · `POST /v1/web/trip-intakes/{id}/survey` · 등록 때 설문에 합치기. `[2026-10-06 사용자 지시 · uiux 인계]`

계약: `wiki/external/rest-endpoints.md` 「설문 질문」 · 기획 `wiki/records/plans/2026-10-05_설문_계획서에서_읽고_로딩에서_묻기_기획.md` 「서버 몫」 1
구현: `components/intake/survey_answers.py` · `entry/trip_api.py` · `051_intake_survey_answers.sql`

★지키려는 것
 ①접수 조회에 `questions[]` — **쓰는 문항만**(이동 · 대체 우선순위) 최대 3, `on_disruption` · `pace` 는 목록에 없다. 이미 답한 문항도 목록에 남고 `answer` 에 고른 번호가 있다.
 ②답은 한 문항씩 바로 저장 · 부분 답 · 멱등 · **같은 문항을 다시 보내면 덮어쓴다**. 하나라도 틀리면 아무것도 저장하지 않는다(422). `updated_at` 은 안 건드린다(읽기가 멈췄는지 가르는 기준).
 ③등록(`confirm`)할 때 모아 둔 답이 설문에 합쳐진다 — 요청이 직접 준 값이 이긴다. 안 답한 문항은 **채워 넣지 않는다**(`on_disruption` 을 안 줬으면 자동 변경 안 함).
 ④남의 접수 · 없는 접수는 같은 404. 이미 등록된 접수는 409. 답을 하나도 안 했으면 등록 동작은 옛 그대로(설문 없음).

재현:

    python -m pytest tests/e2e/test_intake_survey_questions.py -v
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.intake import survey_answers
from app.domains.travel_ops.components.planning.survey import SURVEY_VERSION, auto_on_disruption

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_trip_intake_api import CHAT_PLAN, _full_client, _key, _send


def _intake(client, headers) -> dict:
    return _send(client, headers, text=CHAT_PLAN)


def _answer(client, headers, intake_id, answers, status=200):
    response = client.post(f"/v1/web/trip-intakes/{intake_id}/survey", headers=headers, json={"answers": answers})
    assert response.status_code == status, response.text
    return response.json()


def _view(client, headers, intake_id) -> dict:
    return client.get(f"/v1/web/trip-intakes/{intake_id}", headers=headers).json()


def _constraints(trip_id) -> dict:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT constraints FROM trips WHERE trip_id=%s", (trip_id,))
        return cur.fetchone()[0]


# ── ① 질문 목록 ───────────────────────────────────────────────────
def test_the_intake_carries_only_the_questions_that_are_used(api):
    client, _, _ = _full_client()
    headers = _key(client)
    view = _intake(client, headers)
    asked = view["questions"]
    assert [q["id"] for q in asked] == ["preferred_mobility", "priority"]
    assert len(asked) <= survey_answers.MAX_QUESTIONS
    for question in asked:
        assert question["kind"] == "single" and question["title"] and question["why"] and question["answer"] is None
        assert question["options"] and all(set(option) == {"id", "label"} for option in question["options"])
    assert [o["id"] for o in asked[0]["options"]] == ["public", "taxi", "walk"]          # 렌트카는 이동 계산기가 아직 못 다룬다
    ids = {q["id"] for q in asked}
    assert not ids & {"on_disruption", "pace", "dietary", "diet", "accessibility", "party", "theme"}   # 카드·화면이 보내는 값 · 민감 항목은 묻지 않는다


# ── ② 답 저장 ─────────────────────────────────────────────────────
def test_answers_are_saved_one_at_a_time_and_a_later_answer_overwrites(api):
    client, _, _ = _full_client()
    headers = _key(client)
    intake_id = _intake(client, headers)["intake_id"]

    assert _answer(client, headers, intake_id, {"preferred_mobility": "taxi"}) == {"ok": True, "answered": ["preferred_mobility"]}
    mobility = {q["id"]: q["answer"] for q in _view(client, headers, intake_id)["questions"]}
    assert mobility == {"preferred_mobility": "taxi", "priority": None}               # 답한 문항도 목록에 남고 `answer` 에 번호가 있다

    again = _answer(client, headers, intake_id, {"preferred_mobility": "walk"})          # ★덮어쓴다 — 앞 질문으로 돌아가 고쳤다
    assert again == {"ok": True, "answered": ["preferred_mobility"]}
    assert _answer(client, headers, intake_id, {"priority": "mobility", "preferred_mobility": "walk"})["answered"] == ["preferred_mobility", "priority"]
    final = {q["id"]: q["answer"] for q in _view(client, headers, intake_id)["questions"]}
    assert final == {"preferred_mobility": "walk", "priority": "mobility"}
    # 같은 값을 또 보내도 같다(멱등)
    assert _answer(client, headers, intake_id, {"priority": "mobility"})["answered"] == ["preferred_mobility", "priority"]


def test_saving_an_answer_does_not_touch_updated_at(api):
    """`updated_at` 은 읽기가 멈췄는지 가르는 기준(`reap_stalled`) — 답을 저장할 때마다 갱신하면 멈춘 접수가 멈춘 줄 모른다."""
    client, _, _ = _full_client()
    headers = _key(client)
    intake_id = _intake(client, headers)["intake_id"]

    def stamp():
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT updated_at FROM trip_intakes WHERE intake_id=%s", (UUID(intake_id),))
            return cur.fetchone()[0]

    before = stamp()
    _answer(client, headers, intake_id, {"priority": "activity"})
    assert stamp() == before


def test_the_card_and_plan_screen_values_are_accepted_but_not_asked(api):
    client, _, _ = _full_client()
    headers = _key(client)
    intake_id = _intake(client, headers)["intake_id"]
    assert _answer(client, headers, intake_id, {"on_disruption": "ask_first", "pace": "moderate"})["answered"] == ["on_disruption", "pace"]
    assert [q["id"] for q in _view(client, headers, intake_id)["questions"]] == ["preferred_mobility", "priority"]


@pytest.mark.parametrize("answers", [
    {"nope": "x"},                                          # 모르는 문항
    {"preferred_mobility": "car"},                          # 렌트카는 선택지에 없다
    {"preferred_mobility": 3},                              # 선택지는 글자
    {"dietary": "halal"},                                   # 민감 항목은 이 입구가 받지 않는다
    {"on_disruption": "yes"},
    {"pace": "packed", "priority": "nope"},                 # 하나라도 틀리면 아무것도 저장하지 않는다
])
def test_a_wrong_answer_is_refused_and_nothing_is_saved(api, answers):
    client, _, _ = _full_client()
    headers = _key(client)
    intake_id = _intake(client, headers)["intake_id"]
    response = _answer(client, headers, intake_id, answers, status=422)
    if all(isinstance(value, str) for value in answers.values()):
        assert response["error"]["code"] == "invalid_answers" and response["error"]["problems"]
    else:                                                    # 글자가 아닌 선택지는 몸통 모양 검사(`validation_error`)가 먼저 막는다
        assert response["error"]["code"] == "validation_error"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT survey FROM trip_intakes WHERE intake_id=%s", (UUID(intake_id),))
        assert cur.fetchone()[0] == {}


def test_an_empty_or_unknown_body_is_refused(api):
    client, _, _ = _full_client()
    headers = _key(client)
    intake_id = _intake(client, headers)["intake_id"]
    url = f"/v1/web/trip-intakes/{intake_id}/survey"
    assert client.post(url, headers=headers, json={"answers": {}}).status_code == 422
    assert client.post(url, headers=headers, json={}).status_code == 422
    assert client.post(url, headers=headers, json={"answers": {"priority": "activity"}, "extra": 1}).status_code == 422


# ── ④ 누구의 접수인가 ─────────────────────────────────────────────
def test_someone_elses_or_a_missing_intake_is_the_same_404(api):
    client, _, _ = _full_client()
    mine, other = _key(client), _key(client)
    intake_id = _intake(client, mine)["intake_id"]
    theirs = client.post(f"/v1/web/trip-intakes/{intake_id}/survey", headers=other, json={"answers": {"priority": "activity"}})
    missing = client.post(f"/v1/web/trip-intakes/{uuid4()}/survey", headers=other, json={"answers": {"priority": "activity"}})
    assert theirs.status_code == missing.status_code == 404 and theirs.json() == missing.json()
    assert [q["answer"] for q in _view(client, mine, intake_id)["questions"]] == [None, None]
    assert client.post(f"/v1/web/trip-intakes/{intake_id}/survey", json={"answers": {"priority": "activity"}}).status_code == 401


# ── ③ 등록 때 합치기 ──────────────────────────────────────────────
def test_the_saved_answers_are_merged_into_the_survey_when_the_intake_is_confirmed(api):
    client, _, _ = _full_client()
    headers = _key(client)
    view = _intake(client, headers)
    _answer(client, headers, view["intake_id"], {"preferred_mobility": "taxi", "priority": "activity", "pace": "packed"})
    done = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=headers,
                       json={"revision": view["revision"], "survey": {"version": SURVEY_VERSION, "pace": "relaxed"}})
    assert done.status_code == 200, done.text
    stored = _constraints(done.json()["trip"]["trip_id"])
    survey = stored["survey"]
    assert survey["priority_details"]["mobility"] == ["taxi"] and survey["priority"] == ["activity"]
    assert survey["pace"] == "relaxed"                                               # ★등록 요청이 직접 준 값이 이긴다(모아 둔 packed 가 아니라)
    assert {"priority_details", "priority", "pace"} <= set(stored["survey_answered"])
    assert "on_disruption" not in stored["survey_answered"] and auto_on_disruption(stored) is False   # 안 답한 문항은 채워 넣지 않는다 — 자동 변경은 켜지지 않는다


def test_confirm_without_a_survey_still_uses_the_saved_answers(api):
    client, _, _ = _full_client()
    headers = _key(client)
    view = _intake(client, headers)
    _answer(client, headers, view["intake_id"], {"preferred_mobility": "public", "on_disruption": "ask_first"})
    done = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=headers, json={"revision": view["revision"]})
    assert done.status_code == 200, done.text
    stored = _constraints(done.json()["trip"]["trip_id"])
    assert stored["survey"]["priority_details"] == {"mobility": ["public"]} and stored["survey"]["on_disruption"] == "ask_first"
    assert "on_disruption" in stored["survey_answered"]                              # 카드가 보낸 끄기는 「직접 고른 것」이다


def test_without_any_answer_confirm_behaves_as_before(api):
    client, _, _ = _full_client()
    headers = _key(client)
    view = _intake(client, headers)
    done = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=headers, json={"revision": view["revision"]})
    assert done.status_code == 200, done.text
    assert "survey" not in _constraints(done.json()["trip"]["trip_id"])               # 옛 동작 그대로 — 설문 없음


def test_an_already_registered_intake_takes_no_more_answers(api):
    client, _, _ = _full_client()
    headers = _key(client)
    view = _intake(client, headers)
    assert client.post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=headers,
                       json={"revision": view["revision"]}).status_code == 200
    late = _answer(client, headers, view["intake_id"], {"priority": "activity"}, status=409)
    assert late["error"]["code"] == "intake_confirmed"


# ── 합치기 규칙 (순수) ────────────────────────────────────────────
def test_merging_keeps_each_area_of_the_details_and_the_request_wins():
    mine = {"preferred_mobility": "taxi", "priority": "mobility"}
    survey = survey_answers.merged_survey(mine, {"version": SURVEY_VERSION, "priority_details": {"food": ["vegetarian"]},
                                                 "priority": ["activity"]})
    assert survey["priority_details"] == {"mobility": ["taxi"], "food": ["vegetarian"]}      # 영역마다 합친다
    assert survey["priority"] == ["activity"]                                                 # 같은 문항은 요청이 이긴다
    assert survey_answers.merged_survey({}, None) is None
    assert survey_answers.merged_survey({}, {"version": SURVEY_VERSION, "pace": "relaxed"}) == {"version": SURVEY_VERSION, "pace": "relaxed"}
    assert survey_answers.merged_survey({"pace": "packed"}, None) == {"version": SURVEY_VERSION, "pace": "packed"}


def test_the_question_catalog_only_offers_choices_the_engines_understand():
    """선택지를 더하면 그 값을 읽는 쪽이 모르는 코드가 되지 않는지 — 이동은 계산기 수단 표(`SURVEY_MODES`), 우선순위는 비슷함 가중(`ORDER`)."""
    from app.domains.travel_ops.instances.activity.similarity import ORDER
    from app.domains.travel_ops.instances.mobility.wiring import SURVEY_MODES

    by_id = {q.id: q for q in survey_answers.QUESTIONS}
    assert set(by_id["preferred_mobility"].option_ids()) <= set(SURVEY_MODES)
    assert set(by_id["priority"].option_ids()) <= set(ORDER)

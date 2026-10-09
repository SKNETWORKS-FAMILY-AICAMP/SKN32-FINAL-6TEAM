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
def test_next_intake_continues_saved_questions_but_not_direct_settings(api):
    client, _, _ = _full_client()
    headers = _key(client)
    previous = _intake(client, headers)["intake_id"]
    _answer(client, headers, previous, {"preferred_mobility": "taxi", "pace": "packed", "on_disruption": "replace"})
    next_view = _intake(client, headers)
    assert {q["id"]: q["answer"] for q in next_view["questions"]} == {"preferred_mobility": "taxi", "priority": None}
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT survey FROM trip_intakes WHERE intake_id=%s", (UUID(next_view["intake_id"]),))
        assert cur.fetchone()[0] == {"preferred_mobility": "taxi"}


def test_next_intake_does_not_inherit_answers_from_another_customer(api):
    first, _, _ = _full_client()
    first_headers = _key(first)
    previous = _intake(first, first_headers)["intake_id"]
    _answer(first, first_headers, previous, {"priority": "mobility"})
    other, _, _ = _full_client()
    other_headers = _key(other)
    assert all(q["answer"] is None for q in _intake(other, other_headers)["questions"])


def test_changed_question_bundle_is_asked_again_on_the_next_intake(api, monkeypatch):
    client, _, _ = _full_client()
    headers = _key(client)
    previous = _intake(client, headers)["intake_id"]
    _answer(client, headers, previous, {"preferred_mobility": "taxi"})
    monkeypatch.setattr(survey_answers, "QUESTION_SET_VERSION", "future-bundle")
    assert all(q["answer"] is None for q in _intake(client, headers)["questions"])


def test_answers_are_saved_one_at_a_time_and_a_later_answer_overwrites(api):
    client, _, _ = _full_client()
    headers = _key(client)
    intake_id = _intake(client, headers)["intake_id"]

    assert _answer(client, headers, intake_id, {"preferred_mobility": "taxi"}) == {"ok": True, "answered": ["preferred_mobility"],
                                                                                  "questions_version": survey_answers.QUESTION_SET_VERSION}
    mobility = {q["id"]: q["answer"] for q in _view(client, headers, intake_id)["questions"]}
    assert mobility == {"preferred_mobility": "taxi", "priority": None}               # 답한 문항도 목록에 남고 `answer` 에 번호가 있다

    again = _answer(client, headers, intake_id, {"preferred_mobility": "walk"})          # ★덮어쓴다 — 앞 질문으로 돌아가 고쳤다
    assert again == {"ok": True, "answered": ["preferred_mobility"], "questions_version": survey_answers.QUESTION_SET_VERSION}
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


# ── ⑤ 문항 번호 ↔ 슬롯 · 질문 묶음 버전 · 답 이력 `[2026-10-06 uiux 요청 · 맞춤 질문 의논 §7]` ─────────
def _history(intake_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT question_id, option_id, slot, value, question_text, option_label, bundle_version FROM trip_intake_survey_answers "
                    "WHERE intake_id=%s ORDER BY seq", (UUID(intake_id),))
        return cur.fetchall()


def _bundle(version, mobility_value="taxi"):
    """다른 묶음 — 문항 번호 `q_move` 가 슬롯 `preferred_mobility` 로 가고, 선택지 `o_taxi` 가 `mobility_value` 로 해석된다(번호와 값이 다르다)."""
    return (version, (survey_answers.Question("q_move", "preferred_mobility", "이동은 어떻게 하세요?", "묶음 시험", (
        survey_answers.Option("o_taxi", "택시로 이동", mobility_value), survey_answers.Option("o_walk", "걸어서", "walk"))),
                      survey_answers.QUESTIONS[1]))


def test_the_view_and_the_answer_reply_carry_the_question_set_version(api):
    client, _, _ = _full_client()
    headers = _key(client)
    view = _intake(client, headers)
    assert view["questions_version"] == survey_answers.QUESTION_SET_VERSION == "2"
    assert _answer(client, headers, view["intake_id"], {"priority": "activity"})["questions_version"] == "2"
    assert all("slot" not in question and "value" not in question for question in view["questions"])    # 웹은 슬롯 · 값을 모른다 — 번호 · 문구 · 선택지만


def test_saving_an_answer_keeps_what_was_shown_and_how_it_was_read(api):
    client, _, _ = _full_client()
    headers = _key(client)
    intake_id = _intake(client, headers)["intake_id"]
    _answer(client, headers, intake_id, {"preferred_mobility": "taxi", "pace": "packed"})
    _answer(client, headers, intake_id, {"preferred_mobility": "taxi"})                                  # 같은 답을 다시 보냄 — 줄이 늘지 않는다(멱등)
    _answer(client, headers, intake_id, {"preferred_mobility": "walk"})                                  # 고침 — 줄이 하나 더 쌓인다(덮어쓰지 않는다)
    rows = _history(intake_id)
    assert [(r[0], r[1]) for r in rows] == [("preferred_mobility", "taxi"), ("pace", "packed"), ("preferred_mobility", "walk")]
    first = rows[0]
    assert first[2:] == ("preferred_mobility", "taxi", "이동은 주로 어떻게 하세요?", "택시", "2")        # 슬롯 · 값 · 그때의 문구 · 라벨 · 묶음 버전
    assert rows[1][2:] == ("pace", "packed", None, None, "2")                                            # 직접 값은 문구 · 라벨이 없다


def test_a_question_id_and_its_slot_are_different_things(api, monkeypatch):
    """문항 번호를 새로 만들어도 슬롯은 같다 — 웹은 번호만 알고, 어디로 가는지는 서버가 안다. 번호 · 선택지 번호와 값이 달라도 설문에 올바르게 들어간다."""
    version, bundle = _bundle("2")
    monkeypatch.setattr(survey_answers, "QUESTIONS", bundle)
    monkeypatch.setattr(survey_answers, "QUESTION_SET_VERSION", version)
    client, _, _ = _full_client()
    headers = _key(client)
    view = _intake(client, headers)
    assert [q["id"] for q in view["questions"]] == ["q_move", "priority"] and view["questions_version"] == "2"
    assert [o["id"] for o in view["questions"][0]["options"]] == ["o_taxi", "o_walk"]
    assert _answer(client, headers, view["intake_id"], {"q_move": "o_taxi"}, status=200)["answered"] == ["q_move"]
    _answer(client, headers, view["intake_id"], {"preferred_mobility": "taxi"}, status=422)             # 옛 번호는 이 묶음에 없다
    assert _history(view["intake_id"])[0][:4] == ("q_move", "o_taxi", "preferred_mobility", "taxi")
    done = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=headers, json={"revision": view["revision"]})
    assert done.status_code == 200, done.text
    assert _constraints(done.json()["trip"]["trip_id"])["survey"]["priority_details"] == {"mobility": ["taxi"]}


def test_an_old_answer_keeps_the_meaning_it_had_when_it_was_saved(api, monkeypatch):
    """묶음이 바뀌어 같은 선택지 번호의 값이 달라져도(원칙은 안 바꾸는 것 — 어겨도 옛 답은 지켜진다) 옛 답은 **저장 때 해석한 값**으로 등록된다."""
    client, _, _ = _full_client()
    headers = _key(client)
    view = _intake(client, headers)
    _answer(client, headers, view["intake_id"], {"preferred_mobility": "taxi"})                          # 묶음 2 에서: taxi → "taxi"
    version, bundle = _bundle("3", mobility_value="walk")                                                # 묶음 3 은 같은 번호를 다르게 읽는다
    monkeypatch.setattr(survey_answers, "QUESTIONS", (survey_answers.Question(
        "preferred_mobility", "preferred_mobility", "이동은?", "묶음 시험", (survey_answers.Option("taxi", "택시", "walk"),)), bundle[1]))
    monkeypatch.setattr(survey_answers, "QUESTION_SET_VERSION", version)
    done = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=headers, json={"revision": view["revision"]})
    assert done.status_code == 200, done.text
    assert _constraints(done.json()["trip"]["trip_id"])["survey"]["priority_details"] == {"mobility": ["taxi"]}    # 저장 때의 뜻 그대로(walk 가 아니다)
    assert [r[-1] for r in _history(view["intake_id"])] == ["2"]


def test_without_history_an_answer_is_read_with_the_current_bundle():
    """053 이 안 올라간 DB 의 옛 답 — 이력이 없으면 지금 묶음의 매핑으로 읽는다(그리고 순수 함수라 DB 없이도 같다)."""
    assert survey_answers.to_survey({"preferred_mobility": "taxi", "priority": "mobility"}) == {"priority_details": {"mobility": ["taxi"]}, "priority": ["mobility"]}
    saved = {"preferred_mobility": ("taxi", "preferred_mobility", "walk")}
    assert survey_answers.to_survey({"preferred_mobility": "taxi"}, saved) == {"priority_details": {"mobility": ["walk"]}}      # 이력이 있으면 그것
    assert survey_answers.to_survey({"preferred_mobility": "walk"}, saved) == {"priority_details": {"mobility": ["walk"]}}      # 선택지가 달라졌으면(고쳤다) 지금 묶음


def test_the_history_is_append_only_and_leaves_with_the_intake(api):
    client, _, _ = _full_client()
    headers = _key(client)
    intake_id = _intake(client, headers)["intake_id"]
    _answer(client, headers, intake_id, {"priority": "activity"})
    with get_connection() as conn, conn.cursor() as cur:
        with pytest.raises(Exception, match="추가만 한다"):
            cur.execute("UPDATE trip_intake_survey_answers SET value='x' WHERE intake_id=%s", (UUID(intake_id),))
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM trip_intakes WHERE intake_id=%s", (UUID(intake_id),))                   # 접수가 지워지면 같이 지워진다
    assert _history(intake_id) == []


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

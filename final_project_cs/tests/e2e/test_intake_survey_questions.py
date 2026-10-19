# -*- coding: utf-8 -*-
"""로딩 중 질문 — `questions[]` · `POST /v1/web/trip-intakes/{id}/survey` · 등록 때 설문에 합치기. `[2026-10-06 사용자 지시 · uiux 인계]` · `[2026-10-19 개편]`

계약: `wiki/external/rest-endpoints/web-intakes.md` 「설문 질문」 · 설계 `wiki/records/plans/2026-10-19_로딩설문_읽은칸빼고_빈칸만묻기.md`
구현: `components/intake/survey_answers.py` · `pipeline.view` · `entry/trip_api.py` · 마이그레이션 051 · 053 · 907

★지키려는 것
 ①접수 조회에 `questions[]` — 시작 설문에서 「일정이 꼬이면」을 뺀 네 문항 중 **계획서에서 못 얻은 것만, 상한 없이.** 처음은 둘(누구와 · 우선순위),
   이해 단계 결과 뒤 실내외 · 여유를 **뒤에 붙인다**(한 번만 늘고 이미 보인 문항은 남는다). 이미 답한 문항도 목록에 남고 `answer` 에 고른 답이 있다.
 ②답은 한 문항씩 바로 저장 · 부분 답 · 멱등 · **같은 문항을 다시 보내면 덮어쓴다**. 하나라도 틀리면 아무것도 저장하지 않는다(422). `updated_at` 은 안 건드린다.
 ③등록(`confirm`)할 때 모아 둔 답이 설문에 합쳐진다 — 요청이 직접 준 값이 이긴다. 안 답한 문항은 **채워 넣지 않는다**(`on_disruption` 을 안 줬으면 자동 변경 안 함).
 ④남의 접수 · 없는 접수는 같은 404. 이미 등록된 접수는 409. 답을 하나도 안 했으면 등록 동작은 옛 그대로(설문 없음).
 ⑤옛 묶음(2)의 답은 저장 때 해석한 값으로 읽힌다 — 새 매핑으로 잘못 읽히지 않는다(053).

재현:

    python -m pytest tests/e2e/test_intake_survey_questions.py -v
"""
from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.intake import pipeline, survey_answers
from app.domains.travel_ops.components.planning.survey import SURVEY_VERSION, auto_on_disruption

from .test_intake_review import rv  # noqa: F401 — 접수를 직접 여는 시험이 쓴다
from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_trip_intake_api import CHAT_PLAN, _full_client, _key, _send

ALL = ["party", "priority", "indoor_outdoor", "pace"]       # `[2026-10-19]` UI 팀 4문항 — 여행 테마는 뺐다
PRIORITY = {"areas": ["food", "mobility"], "details": {"food": ["taste", "clean"], "mobility": ["taxi"]}}


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


def _answers_of(view) -> dict:
    return {q["id"]: q["answer"] for q in view["questions"]}


# ── ① 질문 목록 ───────────────────────────────────────────────────
def test_without_anything_read_all_four_questions_are_asked_with_no_cap(api):
    """이 시험의 읽기는 이해 에이전트를 쓰지 않는다(읽은 칸 없음) — 네 문항이 모두 나온다. 옛 상한 3 은 없다(테마는 문항이 아니다)."""
    client, _, _ = _full_client()
    headers = _key(client)
    view = _intake(client, headers)
    assert [q["id"] for q in view["questions"]] == ALL
    assert view["questions_phase"] == 2 and view["skipped_by_reading"] == []
    assert not hasattr(survey_answers, "MAX_QUESTIONS")
    kinds = {q["id"]: q["kind"] for q in view["questions"]}
    assert kinds == {"party": "single", "priority": "priority", "indoor_outdoor": "pair", "pace": "single"}
    for question in view["questions"]:
        assert question["title"] and question["why"] and question["answer"] is None
        assert "slot" not in question and "value" not in question                      # 웹은 슬롯 · 값을 모른다
    ids = {q["id"] for q in view["questions"]}
    assert not ids & {"on_disruption", "dietary", "diet", "accessibility", "domestic", "mobility_ease", "day_hours"}   # 카드 몫 · 민감 · 문항 없는 칸


def test_question_shapes_carry_groups_parts_and_the_custom_label(api):
    client, _, _ = _full_client()
    headers = _key(client)
    by_id = {q["id"]: q for q in _intake(client, headers)["questions"]}
    priority = by_id["priority"]
    assert [o["id"] for o in priority["options"]] == ["food", "activity", "mobility"]
    groups = {g["id"]: g for g in priority["groups"]}
    assert [o["id"] for o in groups["activity"]["options"]] == ["EV", "EX", "HS", "LS", "NA", "SH", "VE"]     # 2026-10-19 사용자 지시
    assert [o["label"] for o in groups["activity"]["options"]] == ["축제/공연/행사", "체험관광", "역사관광", "레저스포츠", "자연관광", "쇼핑", "문화관광"]
    assert all(g["read"] is None for g in priority["groups"])
    pair = by_id["indoor_outdoor"]
    assert "options" not in pair and [p["id"] for p in pair["parts"]] == ["dining", "activity"]
    assert by_id["party"]["allow_custom"] is True and by_id["party"]["custom_label"] == "기타"
    assert by_id["pace"]["allow_custom"] is False and "theme" not in by_id


# ── ①-2 두 번에 정한다 · 읽은 칸은 뺀다 (접수를 직접 열고 읽기 결과 줄을 넣어 본다) ─────────────
def _open(rv):  # noqa: F811
    with get_connection() as conn:
        return pipeline.open_intake(conn, tenant_id=rv["tenant"], customer_id=rv["customer"], text=CHAT_PLAN, files=[])


def _agent_row(rv, intake_id, value):  # noqa: F811
    """이해 단계가 원본 하나를 읽은 결과 줄(`reading.agent`)을 넣는다 — 읽는 동안 일꾼이 남기는 그 줄과 같은 모양."""
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT source_id FROM intake_sources WHERE tenant_id=%s AND intake_id=%s ORDER BY position LIMIT 1", (rv["tenant"], intake_id))
        source_id = cur.fetchone()[0]
        cur.execute("INSERT INTO intake_claims (intake_id, tenant_id, revision, source_id, field, value_json, method, evidence, needs_review, note) "
                    "VALUES (%s,%s,1,%s,'reading.agent',%s,'llm_agent',%s,false,'시험')",
                    (intake_id, rv["tenant"], source_id, json.dumps({"used": True, **value}, ensure_ascii=False), json.dumps({"source": "model"})))


def _look(rv, intake_id):  # noqa: F811
    with get_connection() as conn:
        return pipeline.view(conn, tenant_id=rv["tenant"], customer_id=rv["customer"], intake_id=intake_id)


def test_first_three_while_reading_then_the_rest_after_the_understanding_result(rv):  # noqa: F811
    intake_id = _open(rv)
    first = _look(rv, intake_id)
    assert first["status"] == "reading" and first["questions_phase"] == 1
    assert [q["id"] for q in first["questions"]] == ["party", "priority"]                               # 계획서에서 거의 안 나오는 것부터 바로
    assert [q["id"] for q in _look(rv, intake_id)["questions"]] == ["party", "priority"]                # 결과 전에는 그대로
    _agent_row(rv, intake_id, {"moves": [{"mode": "subway", "scope": "all", "quote": "다 지하철로"}],
                               "conditions": [{"code": "if_rain_indoor", "quote": "비 오면 실내로"}], "preferences": []})
    second = _look(rv, intake_id)
    assert second["questions_phase"] == 2
    assert [q["id"] for q in second["questions"]] == ["party", "priority", "indoor_outdoor", "pace"]   # 뒤에 붙는다 · 앞 순서 그대로
    priority = {g["id"]: g for g in next(q for q in second["questions"] if q["id"] == "priority")["groups"]}
    assert priority["mobility"]["read"]["quotes"] == ["다 지하철로"] and priority["mobility"]["read"]["value"] == ["subway"]
    assert priority["food"]["read"] is None and priority["activity"]["read"] is None                    # 분야 순서 · 다른 세부는 묻는다
    pair = {p["id"]: p for p in next(q for q in second["questions"] if q["id"] == "indoor_outdoor")["parts"]}
    assert pair["activity"]["read"]["value"] == "indoor" and pair["dining"]["read"] is None             # 「비 오면 실내」 — 식당 칸만 묻는다
    skipped = {(s["question"], s["part"]): s for s in second["skipped_by_reading"]}
    assert set(skipped) == {("priority", "mobility"), ("indoor_outdoor", "activity")}
    assert skipped[("priority", "mobility")]["key"] == "survey.priority_details.mobility" and skipped[("priority", "mobility")]["text"] == "지하철"
    # 한 번만 는다 — 그 뒤로는 흔들리지 않는다
    _agent_row(rv, intake_id, {"preferences": [{"code": "slow_pace", "quote": "천천히"}]})
    assert [q["id"] for q in _look(rv, intake_id)["questions"]] == ["party", "priority", "indoor_outdoor", "pace"]


def test_a_read_pace_is_not_asked_and_is_listed_with_its_quote(rv):  # noqa: F811
    intake_id = _open(rv)
    _look(rv, intake_id)
    _agent_row(rv, intake_id, {"preferences": [{"code": "slow_pace", "quote": "천천히 다닐래요"}]})
    view = _look(rv, intake_id)
    assert [q["id"] for q in view["questions"]] == ["party", "priority", "indoor_outdoor"]
    assert view["skipped_by_reading"] == [{"question": "pace", "part": None, "key": "survey.pace", "value": "relaxed",
                                           "text": "여유 있게", "quotes": ["천천히 다닐래요"]}]


def test_one_taxi_ride_does_not_skip_the_transport_detail(rv):  # noqa: F811
    """☆x600 서버 사례 — 「택시로 이동」 한 구간을 여행 전체(scope all)로 읽어도 「다 · 늘 · 주로 · 웬만하면」류가 없으면 받지 않는다."""
    intake_id = _open(rv)
    _look(rv, intake_id)
    _agent_row(rv, intake_id, {"moves": [{"mode": "taxi", "scope": "all", "quote": "택시로 이동"}]})
    view = _look(rv, intake_id)
    priority = next(q for q in view["questions"] if q["id"] == "priority")
    assert all(group["read"] is None for group in priority["groups"]) and view["skipped_by_reading"] == []


def test_a_shadow_reading_skips_nothing(rv):  # noqa: F811
    """그림자 · 실패한 이해 결과(`used: false`)는 질문을 빼는 근거가 아니다 — 네 문항."""
    intake_id = _open(rv)
    _look(rv, intake_id)
    _agent_row(rv, intake_id, {"used": False, "preferences": [{"code": "slow_pace", "quote": "천천히"}]})
    view = _look(rv, intake_id)
    assert [q["id"] for q in view["questions"]] == ALL and view["skipped_by_reading"] == []


def test_a_failed_reading_asks_all_four(rv):  # noqa: F811
    intake_id = _open(rv)
    _look(rv, intake_id)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET status='fatal', stage='fatal', fatal_code='reading_model_failed' WHERE intake_id=%s", (intake_id,))
    view = _look(rv, intake_id)
    assert view["status"] == "fatal" and [q["id"] for q in view["questions"]] == ALL


def test_answers_given_after_the_first_look_keep_their_place(rv):  # noqa: F811
    """첫 조회 뒤에 답한 문항은 목록에서 빠지지 않는다(`answer` 가 채워진다) — 화면의 `i / N` 이 흔들리지 않는다."""
    intake_id = _open(rv)
    _look(rv, intake_id)
    with get_connection() as conn, conn.transaction():
        survey_answers.save(conn, tenant_id=rv["tenant"], customer_id=rv["customer"], intake_id=intake_id,
                            answers=survey_answers.check({"party": "friends", "pace": "packed"}))
    _agent_row(rv, intake_id, {"preferences": []})
    view = _look(rv, intake_id)
    assert [q["id"] for q in view["questions"]] == ["party", "priority", "indoor_outdoor"]   # 누구와는 남고 · 이미 답한 여유는 붙이지 않는다
    assert _answers_of(view)["party"] == "friends"


def test_without_the_907_column_the_list_is_still_computed(rv, monkeypatch):  # noqa: F811
    """907 이 안 올라간 DB — 저장 없이 그때그때 계산한다(경고). 접수 조회는 막지 않는다."""
    monkeypatch.setattr(survey_answers, "_load_plan", lambda conn, **kw: (None, False))
    intake_id = _open(rv)
    assert [q["id"] for q in _look(rv, intake_id)["questions"]] == ["party", "priority"]


# ── ② 답 저장 ─────────────────────────────────────────────────────
def test_next_intake_continues_saved_questions_but_not_direct_settings(api):
    client, _, _ = _full_client()
    headers = _key(client)
    previous = _intake(client, headers)["intake_id"]
    _answer(client, headers, previous, {"party": "family", "priority": PRIORITY, "on_disruption": "replace"})
    next_view = _intake(client, headers)
    assert [q["id"] for q in next_view["questions"]] == ["indoor_outdoor", "pace"]                  # 이어받은 답은 묻지 않는다
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT survey FROM trip_intakes WHERE intake_id=%s", (UUID(next_view["intake_id"]),))
        saved = cur.fetchone()[0]
    assert set(saved) == {"party", "priority"} and json.loads(saved["priority"]) == PRIORITY            # 항로 지킴이 같은 직접 설정은 이어받지 않는다


def test_next_intake_does_not_inherit_answers_from_another_customer(api):
    first, _, _ = _full_client()
    first_headers = _key(first)
    previous = _intake(first, first_headers)["intake_id"]
    _answer(first, first_headers, previous, {"party": "friends"})
    other, _, _ = _full_client()
    other_headers = _key(other)
    view = _intake(other, other_headers)
    assert [q["id"] for q in view["questions"]] == ALL and all(q["answer"] is None for q in view["questions"])


def test_changed_question_bundle_is_asked_again_on_the_next_intake(api, monkeypatch):
    client, _, _ = _full_client()
    headers = _key(client)
    previous = _intake(client, headers)["intake_id"]
    _answer(client, headers, previous, {"party": "friends"})
    monkeypatch.setattr(survey_answers, "QUESTION_SET_VERSION", "future-bundle")
    view = _intake(client, headers)
    assert [q["id"] for q in view["questions"]] == ALL and all(q["answer"] is None for q in view["questions"])


def test_answers_are_saved_one_at_a_time_and_a_later_answer_overwrites(api):
    client, _, _ = _full_client()
    headers = _key(client)
    intake_id = _intake(client, headers)["intake_id"]

    assert _answer(client, headers, intake_id, {"party": "friends"}) == {"ok": True, "answered": ["party"],
                                                                     "questions_version": survey_answers.QUESTION_SET_VERSION}
    assert _answers_of(_view(client, headers, intake_id))["party"] == "friends"               # 답한 문항도 목록에 남고 `answer` 에 번호가 있다
    _answer(client, headers, intake_id, {"party": "family"})                                  # ★덮어쓴다 — 앞 질문으로 돌아가 고쳤다
    both = {"priority": PRIORITY, "indoor_outdoor": {"dining": "indoor", "activity": "any"}}
    assert _answer(client, headers, intake_id, both)["answered"] == ["indoor_outdoor", "party", "priority"]
    final = _answers_of(_view(client, headers, intake_id))
    assert final["party"] == "family" and final["priority"] == PRIORITY and final["indoor_outdoor"] == {"dining": "indoor", "activity": "any"}
    assert [q["id"] for q in _view(client, headers, intake_id)["questions"]] == ALL           # 답해도 목록은 그대로
    # 같은 값을 또 보내도 같다(멱등) — 순서가 다른 같은 객체도 같은 답이다
    again = _answer(client, headers, intake_id, {"indoor_outdoor": {"activity": "any", "dining": "indoor"}})
    assert again["answered"] == ["indoor_outdoor", "party", "priority"]


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
    _answer(client, headers, intake_id, {"pace": "relaxed"})
    assert stamp() == before


def test_a_theme_answer_is_accepted_and_kept_but_never_asked(api):
    """`[2026-10-19]` UI 팀 4문항에서 테마가 빠졌다 — 로딩 문항은 아니지만, 옛 화면이 보낸 테마는 거절하지 않고 받아 두었다가 등록 때 설문에 싣는다."""
    client, _, _ = _full_client()
    headers = _key(client)
    view = _intake(client, headers)
    assert "theme" not in [q["id"] for q in view["questions"]]
    assert _answer(client, headers, view["intake_id"], {"theme": "culture"})["answered"] == ["theme"]
    assert "theme" not in [q["id"] for q in _view(client, headers, view["intake_id"])["questions"]]
    done = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=headers, json={"revision": view["revision"]})
    assert done.status_code == 200, done.text
    assert _constraints(done.json()["trip"]["trip_id"])["survey"]["theme"] == "culture"


def _trip_party(trip_id) -> tuple[int | None, dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT party_size, constraints FROM trips WHERE trip_id=%s", (trip_id,))
        return cur.fetchone()


def test_a_saved_party_size_fills_an_empty_trip_party_size(api):
    """`[2026-10-20 B안 · ST4F-581]` 계획서에 인원이 없으면 여행자 구성 카드의 인원이 여행 인원이 된다 — 묻는 문항은 아니고, 어디서 채웠는지 남는다."""
    client, _, _ = _full_client()
    headers = _key(client)
    view = _intake(client, headers)
    assert _answer(client, headers, view["intake_id"], {"party": "friends", "party_size": "3"})["answered"] == ["party", "party_size"]
    assert "party_size" not in [q["id"] for q in _view(client, headers, view["intake_id"])["questions"]]
    done = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=headers, json={"revision": view["revision"]})
    assert done.status_code == 200, done.text
    party, constraints = _trip_party(done.json()["trip"]["trip_id"])
    assert party == 3 and constraints["survey"]["party_size"] == 3
    assert "설문" in constraints["derived"]["party_size"]


def test_the_registration_survey_size_fills_an_empty_trip_party_size(api):
    client, _, _ = _full_client()
    headers = _key(client)
    view = _intake(client, headers)
    done = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=headers,
                       json={"revision": view["revision"], "survey": {"version": SURVEY_VERSION, "party": "family", "party_size": 4}})
    assert done.status_code == 200, done.text
    assert _trip_party(done.json()["trip"]["trip_id"])[0] == 4


def test_a_party_size_read_from_the_plan_wins_over_the_survey(api):
    """계획서에서 읽은 인원(「2명이서」)이 먼저다 — 설문 인원은 비었을 때만 쓴다."""
    client, _, _ = _full_client()
    headers = _key(client)
    view = _send(client, headers, text=CHAT_PLAN + "\n우리 2명이서 가요")
    done = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=headers,
                       json={"revision": view["revision"], "survey": {"version": SURVEY_VERSION, "party": "family", "party_size": 4}})
    assert done.status_code == 200, done.text
    party, constraints = _trip_party(done.json()["trip"]["trip_id"])
    assert party == 2 and constraints["survey"]["party_size"] == 4                     # 설문 답은 그대로 남는다
    assert "party_size" not in (constraints.get("derived") or {})


def test_the_guardian_card_value_is_accepted_but_not_asked(api):
    client, _, _ = _full_client()
    headers = _key(client)
    intake_id = _intake(client, headers)["intake_id"]
    assert _answer(client, headers, intake_id, {"on_disruption": "ask_first", "pace": "moderate"})["answered"] == ["on_disruption", "pace"]
    assert "on_disruption" not in [q["id"] for q in _view(client, headers, intake_id)["questions"]]


@pytest.mark.parametrize("answers", [
    {"nope": "x"},                                                        # 모르는 문항
    {"preferred_mobility": "taxi"},                                       # 묶음 2의 문항 — 이 묶음에 없다
    {"theme": "beach"},                                                   # 받기만 하는 테마도 선택지는 정해져 있다
    {"theme": {"custom": "바다"}},                                         # 직접 입력은 누구와(party)만
    {"dietary": "halal"},                                                 # 민감 항목은 이 입구가 받지 않는다
    {"on_disruption": "yes"},
    {"party_size": "5"},                                                 # 인원은 1~4(상품 범위)
    {"party_size": 3},                                                   # 입구는 글자로 받는다
    {"priority": "activity"},                                             # 묶음 2의 단일 답 모양
    {"priority": {"areas": []}},                                          # 분야는 하나 이상
    {"priority": {"areas": ["food", "food"]}},                            # 겹침
    {"priority": {"areas": ["food"], "details": {"mobility": ["taxi"]}}},  # 고르지 않은 분야의 세부
    {"priority": {"areas": ["activity"], "details": {"activity": ["healing"]}}},   # 옛 활동 세부 — 이제 관광 분류 코드
    {"indoor_outdoor": {"dining": "maybe"}},
    {"indoor_outdoor": {}},
    {"pace": "packed", "theme": "nope"},                                  # 하나라도 틀리면 아무것도 저장하지 않는다
])
def test_a_wrong_answer_is_refused_and_nothing_is_saved(api, answers):
    client, _, _ = _full_client()
    headers = _key(client)
    intake_id = _intake(client, headers)["intake_id"]
    response = _answer(client, headers, intake_id, answers, status=422)
    assert response["error"]["code"] in ("invalid_answers", "validation_error")
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
    assert client.post(url, headers=headers, json={"answers": {"party": "friends"}, "extra": 1}).status_code == 422


# ── ④ 누구의 접수인가 ─────────────────────────────────────────────
def test_someone_elses_or_a_missing_intake_is_the_same_404(api):
    client, _, _ = _full_client()
    mine, other = _key(client), _key(client)
    intake_id = _intake(client, mine)["intake_id"]
    theirs = client.post(f"/v1/web/trip-intakes/{intake_id}/survey", headers=other, json={"answers": {"party": "friends"}})
    missing = client.post(f"/v1/web/trip-intakes/{uuid4()}/survey", headers=other, json={"answers": {"party": "friends"}})
    assert theirs.status_code == missing.status_code == 404 and theirs.json() == missing.json()
    assert all(q["answer"] is None for q in _view(client, mine, intake_id)["questions"])
    assert client.post(f"/v1/web/trip-intakes/{intake_id}/survey", json={"answers": {"party": "friends"}}).status_code == 401


# ── ⑤ 문항 번호 ↔ 슬롯 · 질문 묶음 버전 · 답 이력 `[2026-10-06 uiux 요청 · 맞춤 질문 의논 §7]` ─────────
def _history(intake_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT question_id, option_id, slot, value, question_text, option_label, bundle_version FROM trip_intake_survey_answers "
                    "WHERE intake_id=%s ORDER BY seq", (UUID(intake_id),))
        return cur.fetchall()


def test_the_view_and_the_answer_reply_carry_the_question_set_version(api):
    client, _, _ = _full_client()
    headers = _key(client)
    view = _intake(client, headers)
    assert view["questions_version"] == survey_answers.QUESTION_SET_VERSION == "3"
    assert _answer(client, headers, view["intake_id"], {"party": "friends"})["questions_version"] == "3"


def test_saving_an_answer_keeps_what_was_shown_and_how_it_was_read(api):
    client, _, _ = _full_client()
    headers = _key(client)
    intake_id = _intake(client, headers)["intake_id"]
    _answer(client, headers, intake_id, {"party": "friends", "on_disruption": "ask_first"})
    _answer(client, headers, intake_id, {"party": "friends"})                                  # 같은 답을 다시 보냄 — 줄이 늘지 않는다(멱등)
    _answer(client, headers, intake_id, {"priority": PRIORITY})
    rows = _history(intake_id)
    assert [r[0] for r in rows] == ["party", "on_disruption", "priority"]
    assert rows[0][2:] == ("party", "friends", "누구와 함께 떠나나요?", "친구", "3")         # 슬롯 · 값 · 그때의 문구 · 라벨 · 묶음 버전
    assert rows[1][2:] == ("on_disruption", "ask_first", None, None, "3")                    # 직접 값은 문구 · 라벨이 없다
    assert rows[2][2] == "priority_rank" and json.loads(rows[2][3]) == PRIORITY              # 여러 칸 답은 정리한 JSON 글
    assert rows[2][5] == "음식 > 이동 / 음식: 맛 · 청결 / 이동: 택시"


def test_an_answer_saved_under_bundle_2_keeps_its_meaning(api):
    """묶음 2의 답(대체할 곳 `priority=activity` · 이동 `preferred_mobility=taxi`)이 남은 접수 — 이력의 해석 값으로 등록된다(새 우선순위 매핑으로 읽지 않는다)."""
    client, _, _ = _full_client()
    headers = _key(client)
    view = _intake(client, headers)
    intake_id = UUID(view["intake_id"])
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET survey=%s::jsonb WHERE intake_id=%s",
                    (json.dumps({"priority": "activity", "preferred_mobility": "taxi"}), intake_id))
        for question, option in (("priority", "activity"), ("preferred_mobility", "taxi")):
            cur.execute("INSERT INTO trip_intake_survey_answers (tenant_id,intake_id,question_id,option_id,slot,value,bundle_version) "
                        "SELECT tenant_id, intake_id, %s, %s, %s, %s, '2' FROM trip_intakes WHERE intake_id=%s",
                        (question, option, question, option, intake_id))
    done = client.post(f"/v1/web/trip-intakes/{intake_id}/confirm", headers=headers, json={"revision": view["revision"]})
    assert done.status_code == 200, done.text
    survey = _constraints(done.json()["trip"]["trip_id"])["survey"]
    assert survey["priority"] == ["activity"] and survey["priority_details"] == {"mobility": ["taxi"]}


def test_without_history_an_old_answer_is_not_misread_by_the_new_bundle():
    """053 이 안 올라간 DB 의 옛 답 — 묶음 3의 `priority` 는 여러 칸 문항이라 옛 단일 답(「activity」)을 새 뜻으로 읽지 않고 버린다(경고)."""
    assert survey_answers.to_survey({"priority": "activity", "preferred_mobility": "taxi"}) == {}
    saved = {"priority": ("activity", "priority", "activity")}
    assert survey_answers.to_survey({"priority": "activity"}, saved) == {"priority": ["activity"]}                # 이력이 있으면 그때의 뜻


def test_the_history_is_append_only_and_leaves_with_the_intake(api):
    client, _, _ = _full_client()
    headers = _key(client)
    intake_id = _intake(client, headers)["intake_id"]
    _answer(client, headers, intake_id, {"party": "friends"})
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
    _answer(client, headers, view["intake_id"], {"theme": "nature", "party": {"custom": "부모님과 아이 둘"}, "priority": PRIORITY,
                                                 "indoor_outdoor": {"dining": "indoor", "activity": "outdoor"}, "pace": "packed"})
    done = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=headers,
                       json={"revision": view["revision"], "survey": {"version": SURVEY_VERSION, "pace": "relaxed"}})
    assert done.status_code == 200, done.text
    stored = _constraints(done.json()["trip"]["trip_id"])
    survey = stored["survey"]
    assert survey["theme"] == "nature" and survey["party"] == "부모님과 아이 둘" and survey["custom_answers"]["party"] == "부모님과 아이 둘"
    assert survey["priority"] == ["food", "mobility"] and survey["priority_details"] == {"food": ["taste", "clean"], "mobility": ["taxi"]}
    assert survey["indoor_outdoor"] == {"dining": "indoor", "activity": "outdoor"}
    assert survey["pace"] == "relaxed"                                               # ★등록 요청이 직접 준 값이 이긴다(모아 둔 packed 가 아니라)
    assert {"theme", "party", "priority_details", "priority", "indoor_outdoor", "pace"} <= set(stored["survey_answered"])
    assert "on_disruption" not in stored["survey_answered"] and auto_on_disruption(stored) is False   # 안 답한 문항은 채워 넣지 않는다


def test_activity_details_reach_the_trip_as_the_tourism_codes(api):
    client, _, _ = _full_client()
    headers = _key(client)
    view = _intake(client, headers)
    _answer(client, headers, view["intake_id"], {"priority": {"areas": ["activity"], "details": {"activity": ["HS", "EV"]}}})
    done = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=headers, json={"revision": view["revision"]})
    assert done.status_code == 200, done.text
    assert _constraints(done.json()["trip"]["trip_id"])["survey"]["priority_details"] == {"activity": ["HS", "EV"]}


def test_confirm_without_a_survey_still_uses_the_saved_answers(api):
    client, _, _ = _full_client()
    headers = _key(client)
    view = _intake(client, headers)
    _answer(client, headers, view["intake_id"], {"pace": "relaxed", "on_disruption": "ask_first"})
    done = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=headers, json={"revision": view["revision"]})
    assert done.status_code == 200, done.text
    stored = _constraints(done.json()["trip"]["trip_id"])
    assert stored["survey"]["pace"] == "relaxed" and stored["survey"]["on_disruption"] == "ask_first"
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
    late = _answer(client, headers, view["intake_id"], {"party": "friends"}, status=409)
    assert late["error"]["code"] == "intake_confirmed"


# ── 합치기 규칙 (순수) ────────────────────────────────────────────
def test_merging_keeps_each_area_of_the_details_and_the_request_wins():
    mine = survey_answers.check({"priority": PRIORITY})
    survey = survey_answers.merged_survey(mine, {"version": SURVEY_VERSION, "priority_details": {"food": ["michelin"]},
                                                 "priority": ["activity"]})
    assert survey["priority_details"] == {"mobility": ["taxi"], "food": ["michelin"]}          # 영역마다 합친다 — 같은 영역은 요청이 이긴다
    assert survey["priority"] == ["activity"]                                                 # 같은 문항은 요청이 이긴다
    assert survey_answers.merged_survey({}, None) is None
    assert survey_answers.merged_survey({}, {"version": SURVEY_VERSION, "pace": "relaxed"}) == {"version": SURVEY_VERSION, "pace": "relaxed"}
    assert survey_answers.merged_survey({"pace": "packed"}, None) == {"version": SURVEY_VERSION, "pace": "packed"}


def test_the_question_catalog_only_offers_choices_the_engines_understand():
    """선택지 값이 읽는 쪽이 아는 코드인지 — 이동 세부는 계산기 수단 표(렌트카만 예외 — 시작 설문과 같게 두고 계산기 기본 수단으로 간다), 분야는 대체 비슷함 가중."""
    from app.domains.travel_ops.instances.activity.similarity import ORDER
    from app.domains.travel_ops.instances.mobility.wiring import SURVEY_MODES

    priority = next(q for q in survey_answers.QUESTIONS if q.id == "priority")
    mobility = next(g for g in priority.groups if g.id == "mobility")
    assert set(mobility.option_ids()) - {"car"} <= set(SURVEY_MODES)
    assert {"activity", "mobility"} <= set(ORDER) and set(survey_answers.REPLACEMENT_QUESTION.option_ids()) <= set(ORDER)

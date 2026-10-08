# -*- coding: utf-8 -*-
"""항로 지킴이(일정이 꼬이면 알아서 고치는 모드) 켜기 · 끄기. `[결정 2026-10-06 사용자]`

계약: `wiki/external/rest-endpoints.md` 「항로 지킴이」 · 기획 `wiki/records/plans/2026-10-05_설문_계획서에서_읽고_로딩에서_묻기_기획.md` 「서버 몫」 2·3
구현: `components/planning/guardian.py` · `entry/trip_api.py`(`POST /v1/web/trips/{id}/guardian` · 여행 조회의 `guardian`) · `050_trip_guardian_changes.sql`

★지키려는 것
 ①켜기 = `on_disruption=replace` · 끄기 = **`ask_first` 를 명시**하고 둘 다 「직접 답한 문항」(`survey_answered`)에 들어간다. 건너뛰기(끄고 진행)는 값을 안 보내는 것이 아니라 `ask_first` 다 —
   미응답은 기본 `replace` 로 읽혀 휴무 · 교통 통제가 자동 적용된다.
 ②누가 · 언제 · 어디서(via)가 **추가만 하는 표**에 남는다. 같은 값을 다시 눌러도 행이 늘지 않고 「언제부터」가 밀리지 않는다.
 ③**쿠키 세션**으로만 켠다 — 사용자 키 · 인증 없음 · CSRF 없는 쿠키는 막히고, 남의 여행 · 없는 여행은 같은 404.
 ④옛 여행(설문 없음)은 불변 — 꺼짐이고 `since`·`via` 는 null. 등록 때 카드가 보낸 값은 `registration` 으로 읽힌다.
 ⑤여행을 지우면 기록도 같이 지워진다. 고정한 일정은 켜져 있어도 먼저 묻는다.

재현:

    python -m pytest tests/e2e/test_trip_guardian.py -v
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.planning import guardian
from app.domains.travel_ops.components.planning.pending import decide
from app.domains.travel_ops.components.planning.survey import auto_on_disruption, on_disruption
from app.domains.travel_ops.modules.web_account.web_session import issue

from .test_ask_first import DUST, _item
from .test_guest_and_trip_delete import _count, _delete, _make_trip
from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_cookie_session import WEB, _guest, cookies  # noqa: F401

#: 설문이 없는 여행의 제약(시나리오 기본은 등록 때 이미 `replace` 로 답한 모양이라 따로 만든다)
NO_SURVEY = {"payment": "card"}


def _post(env, trip_id, body, *, client=None, csrf=True):
    client = client or env["client"]
    headers = {"Origin": WEB}
    if csrf:
        headers["X-CSRF-Token"] = client.get("/v1/web/auth/me").json()["csrf_token"]
    return client.post(f"/v1/web/trips/{trip_id}/guardian", json=body, headers=headers)


def _stored(trip_id) -> dict:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT constraints FROM trips WHERE trip_id=%s", (trip_id,))
        return cur.fetchone()[0]


def _rows(trip_id) -> list[tuple[bool, str]]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT enabled, via FROM trip_guardian_changes WHERE trip_id=%s ORDER BY seq", (trip_id,))
        return [tuple(row) for row in cur.fetchall()]


def _trip(env, **override) -> str:
    _guest(env)
    status, trip = _make_trip(env, **override)
    assert status == 201, trip
    return trip["trip_id"]


# ── ① 켜기 · 끄기 ─────────────────────────────────────────────────
def test_on_and_off_change_the_stored_choice_and_leave_a_record(cookies):
    trip_id = _trip(cookies, constraints=NO_SURVEY)
    assert cookies["client"].get(f"/v1/web/trips/{trip_id}").json()["guardian"] == {"enabled": False, "since": None, "via": None}

    on = _post(cookies, trip_id, {"enabled": True, "via": "header"})
    assert on.status_code == 200, on.text
    body = on.json()
    assert set(body) == {"enabled", "since", "via"} and body["enabled"] is True and body["via"] == "header"
    datetime.fromisoformat(body["since"])                                  # 시각이다
    stored = _stored(trip_id)
    assert stored["survey"]["on_disruption"] == "replace" and stored["survey"]["version"]
    assert stored["survey_answered"] == ["on_disruption"] and auto_on_disruption(stored) is True
    assert stored["payment"] == "card"                                       # 다른 제약은 그대로
    assert cookies["client"].get(f"/v1/web/trips/{trip_id}").json()["guardian"] == body

    again = _post(cookies, trip_id, {"enabled": True, "via": "notice"})        # 같은 값 — 아무것도 안 바뀐다
    assert again.json() == body and _rows(trip_id) == [(True, "header")]

    off = _post(cookies, trip_id, {"enabled": False, "via": "settings"})
    assert off.json()["enabled"] is False and off.json()["via"] == "settings"
    stored = _stored(trip_id)
    assert stored["survey"]["on_disruption"] == "ask_first" and "on_disruption" in stored["survey_answered"]
    assert auto_on_disruption(stored) is False
    assert _rows(trip_id) == [(True, "header"), (False, "settings")]


def test_skip_sends_ask_first_explicitly_so_it_does_not_fall_back_to_the_replace_default(cookies):
    """★건너뛰기 = 꺼짐은 `ask_first` 를 **명시**해야 한다. 답을 안 하면 기본 `replace` 로 읽혀 휴무 · 교통 통제는 자동 적용된다(`pending.decide` 는 답했는지를 보지 않는다)."""
    trip_id = _trip(cookies, constraints=NO_SURVEY)
    untouched = _stored(trip_id)
    assert on_disruption(untouched) == "replace" and decide(constraints=untouched, item=_item(), report=DUST).action == "apply"

    assert _post(cookies, trip_id, {"enabled": False, "via": "card"}).json()["enabled"] is False
    skipped = _stored(trip_id)
    assert on_disruption(skipped) == "ask_first" and "on_disruption" in skipped["survey_answered"]
    decision = decide(constraints=skipped, item=_item(), report=DUST)
    assert (decision.action, decision.reason) == ("ask", "ask_first")
    assert _rows(trip_id) == [(False, "card")]               # 처음 「직접 골랐다」가 기록된다 — 바뀐 값이 없어 보여도


def test_a_pinned_item_is_still_asked_while_it_is_on(cookies):
    trip_id = _trip(cookies, constraints=NO_SURVEY)
    _post(cookies, trip_id, {"enabled": True, "via": "card"})
    on = _stored(trip_id)
    assert decide(constraints=on, item=_item(), report=DUST).action == "apply"
    pinned = decide(constraints=on, item=_item(detail={"customer_pinned": True}), report=DUST)
    assert (pinned.action, pinned.reason, pinned.protected_by) == ("ask", "protected", "customer_pinned")


# ── ③ 누가 부를 수 있나 ───────────────────────────────────────────
def test_only_a_logged_in_cookie_session_can_turn_it_on(cookies):
    trip_id = _trip(cookies, constraints=NO_SURVEY)
    body = {"enabled": True, "via": "header"}

    stranger = TestClient(cookies["client"].app, follow_redirects=False)
    assert stranger.post(f"/v1/web/trips/{trip_id}/guardian", json=body).status_code == 401

    with get_connection() as conn, conn.transaction():
        _, key = issue(conn, tenant_id=cookies["tenant"])
    by_key = stranger.post(f"/v1/web/trips/{trip_id}/guardian", json=body, headers={"X-User-Key": key})
    assert by_key.status_code == 403 and by_key.json()["error"]["code"] == "cookie_session_required"

    no_csrf = _post(cookies, trip_id, body, csrf=False)
    assert no_csrf.status_code == 403 and no_csrf.json()["error"]["code"] == "csrf_failed"
    assert _rows(trip_id) == [] and auto_on_disruption(_stored(trip_id)) is False        # 어느 것도 바꾸지 못했다


def test_someone_elses_or_a_missing_trip_is_the_same_404(cookies):
    trip_id = _trip(cookies, constraints=NO_SURVEY)
    other = {**cookies, "client": TestClient(cookies["client"].app, follow_redirects=False), "ip": "10.9.1." + str(uuid4().int % 250)}
    _guest(other)
    body = {"enabled": True, "via": "header"}
    mine_by_other, missing = _post(other, trip_id, body), _post(other, uuid4(), body)
    assert mine_by_other.status_code == missing.status_code == 404
    assert mine_by_other.json() == missing.json()
    assert _rows(trip_id) == []


@pytest.mark.parametrize("body", [
    {"enabled": True, "via": "email"},                 # 모르는 곳
    {"enabled": True},                                  # via 없음 — 어디서 눌렀는지 기록할 수 없다
    {"via": "header"},                                  # enabled 없음
    {"enabled": "yes", "via": "header"},
    {"enabled": True, "via": "header", "extra": 1},     # 모르는 칸은 거절
])
def test_a_wrong_body_is_refused(cookies, body):
    trip_id = _trip(cookies, constraints=NO_SURVEY)
    assert _post(cookies, trip_id, body).status_code == 422
    assert _rows(trip_id) == []


# ── ④ 옛 여행 · 등록 때 고른 값 ───────────────────────────────────
def test_a_trip_without_a_survey_is_off_and_unrecorded(cookies):
    trip_id = _trip(cookies, constraints=NO_SURVEY)
    assert cookies["client"].get(f"/v1/web/trips/{trip_id}").json()["guardian"] == {"enabled": False, "since": None, "via": None}
    assert _stored(trip_id) == NO_SURVEY                                    # 조회가 저장본을 건드리지 않는다


def test_a_choice_made_at_registration_reads_back_as_registration(cookies):
    """등록(계획 담기) 때 카드가 `on_disruption` 을 설문과 함께 보냈다 — 기록 행은 없지만 값은 직접 고른 것이다."""
    on_trip = _trip(cookies)                                                # 시나리오 기본: 설문 `replace` 를 직접 답함
    view = cookies["client"].get(f"/v1/web/trips/{on_trip}").json()["guardian"]
    assert view["enabled"] is True and view["via"] == guardian.REGISTRATION
    datetime.fromisoformat(view["since"])
    assert _rows(on_trip) == []


def test_skip_at_registration_reads_back_as_off(cookies):
    ask = {"payment": "card", "survey": {"version": "2026-09-24.v1", "on_disruption": "ask_first"}}
    trip_id = _trip(cookies, constraints=ask)
    view = cookies["client"].get(f"/v1/web/trips/{trip_id}").json()["guardian"]
    assert view["enabled"] is False and view["via"] == guardian.REGISTRATION


# ── ⑤ 지우면 같이 지워진다 ────────────────────────────────────────
def test_deleting_the_trip_deletes_its_guardian_record(cookies):
    trip_id = _trip(cookies, constraints=NO_SURVEY)
    _post(cookies, trip_id, {"enabled": True, "via": "header"})
    _post(cookies, trip_id, {"enabled": False, "via": "settings"})
    assert _count("SELECT count(*) FROM trip_guardian_changes WHERE trip_id=%s", UUID(trip_id)) == 2
    assert _delete(cookies, trip_id).status_code == 200
    assert _count("SELECT count(*) FROM trip_guardian_changes WHERE trip_id=%s", UUID(trip_id)) == 0


# ── ⑥ 알림 — 켜 둔 사용자에게는 「바꿨어요」 표시, 꺼 둔 사용자에게는 「켜기」 ──────────
AUTO_CHANGE = {"type": "change_notice", "text": "경복궁이 문을 닫아 다른 곳으로 바꿨어요.", "rollback": {"base_version": 2, "to_version": 1,
               "request_id": "rollback:v2->v1", "label": "되돌리기", "path": "/rollback"}}
CHOSEN_CHANGE = {"type": "change_notice", "text": "고르신 곳으로 바꿨어요.", "proposal_id": "p1"}      # 고객이 고른 변경 — `rollback` 이 없다
ASK = {"type": "proposal_request", "reason": "ask_first", "text": "경복궁이 닫아요. 어떻게 할까요?",
       "options": [{"key": "a", "rank": 1, "name": "창덕궁"}, {"key": "b", "rank": 2, "name": "덕수궁"}]}


def _sent(env, trip_id, queue, payload, *, version=None, key=None) -> dict:
    """알림을 바깥함에 넣고 실린 payload 를 읽는다 — 시나리오용 여행 버전의 길(`TripStore.enqueue_*`)."""
    with get_connection() as conn, conn.transaction():
        if version is not None:
            env["store"].enqueue_notice(conn, trip_id=UUID(trip_id), version=version, payload=payload)
            wanted = f"{trip_id}:v{version}"
        else:
            env["store"].enqueue_message(conn, trip_id=UUID(trip_id), key=key, payload=payload)
            wanted = f"{trip_id}:{key}"
    return next(row[1] for row in env["notices"]() if row[0] == wanted)


def test_an_automatic_change_says_the_guardian_did_it_only_when_it_is_on(cookies):
    on_trip = _trip(cookies)                                                   # 시나리오 기본: 등록 때 켬
    assert _sent(cookies, on_trip, "version", AUTO_CHANGE, version=2)["guardian"] == {"changed": True}
    # 고객이 고른 변경 — 항로 지킴이가 한 일이 아니다
    assert "guardian" not in _sent(cookies, on_trip, "version", CHOSEN_CHANGE, version=3)


def test_a_trip_that_never_turned_it_on_gets_no_changed_mark(cookies):
    """켜 두지 않은 여행(옛 여행의 기본 `replace`)의 자동 변경은 항로 지킴이가 한 일이 아니다 — 표시를 싣지 않는다."""
    trip_id = _trip(cookies, constraints=NO_SURVEY)
    assert "guardian" not in _sent(cookies, trip_id, "version", AUTO_CHANGE, version=2)
    _post(cookies, trip_id, {"enabled": True, "via": "header"})
    assert _sent(cookies, trip_id, "version", AUTO_CHANGE, version=3)["guardian"] == {"changed": True}   # 켠 뒤에는 싣는다
    _post(cookies, trip_id, {"enabled": False, "via": "settings"})
    assert "guardian" not in _sent(cookies, trip_id, "version", AUTO_CHANGE, version=4)               # 끈 뒤에는 다시 안 싣는다


def test_the_off_user_gets_the_turn_on_offer_with_the_alternatives(cookies):
    trip_id = _trip(cookies, constraints=NO_SURVEY)
    payload = _sent(cookies, trip_id, "message", ASK, key="proposal:p1")
    offer = payload["guardian"]["offer"]
    assert offer["label"] == "항로 지킴이 켜기" and offer["via"] == "notice"
    assert offer["path"] == f"/trips/{trip_id}?guardian=on" and offer["url"] == f"{WEB}{offer['path']}"
    # 링크만으로는 켜지지 않는다 — 서버가 켜는 길은 쿠키 세션의 `POST …/guardian` 하나뿐이다(위 시험)
    _post(cookies, trip_id, {"enabled": True, "via": "notice"})
    assert "guardian" not in _sent(cookies, trip_id, "message", ASK, key="proposal:p2")                # 이미 켠 사용자에게는 권하지 않는다


@pytest.mark.parametrize("override", [
    {"reason": "protected", "protected_by": "customer_pinned"},   # 고정한 일정 — 켜도 먼저 묻는다
    {"type": "safety_alert", "reason": "safety_alert"},           # 안전 알림 — 권하지 않는다
    {"reason": "indoor_unknown", "consent": True, "options": []}, # 「바꿀까요?」 — 대안이 아직 없다
    {"options": []},                                              # 보낼 대안이 없다
])
def test_the_offer_is_not_attached_where_turning_it_on_would_change_nothing(cookies, override):
    trip_id = _trip(cookies, constraints=NO_SURVEY)
    assert "guardian" not in _sent(cookies, trip_id, "message", {**ASK, **override}, key=f"proposal:{uuid4().hex[:6]}")


def test_the_web_notice_list_carries_the_guardian_part(cookies):
    trip_id = _trip(cookies, constraints=NO_SURVEY)
    _sent(cookies, trip_id, "message", ASK, key="proposal:p1")
    notices = cookies["client"].get(f"/v1/web/trips/{trip_id}/notices").json()["notices"]
    assert notices[-1]["guardian"]["offer"]["path"] == f"/trips/{trip_id}?guardian=on"
    assert all("guardian" in n for n in notices)                      # 칸은 늘 있고 없으면 null


def test_the_case_version_path_marks_it_too(cookies):
    """실시간 감시는 Case 를 거쳐 바깥함에 **직접** 쓴다(`itinerary_actions`) — 시나리오용 여행 버전과 같은 규칙(`guardian.annotate`)을 쓴다."""
    from app.domains.travel_ops.components.actions import itinerary_actions

    on_trip = UUID(_trip(cookies))
    arguments = {"reason": "auto_adjusted", "notice": {"type": "change_notice", "text": "바꿨어요."}}
    for constraints, expected in (({"survey": {"version": "v", "on_disruption": "replace"}, "survey_answered": ["on_disruption"]}, {"changed": True}),
                                  (NO_SURVEY, None)):
        message = itinerary_actions._version_notice(tenant_id=cookies["tenant"], trip={"locale": "ko", "constraints": constraints},
                                                    trip_id=on_trip, version=5, base=4, arguments=arguments)
        assert message.payload.get("guardian") == expected


# ── 바깥 채널(디스코드 · 텔레그램) 글 ─────────────────────────────
def test_the_outside_channels_get_the_lines_as_links(cookies):
    from app.infrastructure.notify import discord

    plain = {"type": "change_notice", "text": "바꿨어요.", "plan_url": "https://plan.example.test/p"}
    assert discord.render(plain) == "바꿨어요.\nhttps://plan.example.test/p"                    # 이 값이 없으면 문구가 한 글자도 안 바뀐다
    changed = discord.render({**plain, "guardian": {"changed": True}}).splitlines()
    assert changed == ["바꿨어요.", "항로 지킴이가 바꿨어요. 마음에 안 들면 웹에서 되돌릴 수 있어요.", "https://plan.example.test/p"]   # 알림은 계획서 링크로 끝난다
    offered = discord.render({"type": "proposal_request", "text": "어떻게 할까요?",
                              "guardian": {"offer": {"url": "https://web.example.test/trips/t?guardian=on"}}})
    assert offered.splitlines()[-1] == "항로 지킴이를 켜면 다음부터 알아서 바꿔 드려요: https://web.example.test/trips/t?guardian=on"
    no_url = discord.render({"type": "proposal_request", "text": "어떻게 할까요?", "guardian": {"offer": {"url": None, "path": "/trips/t?guardian=on"}}})
    assert "항로 지킴이" not in no_url                                                          # 웹 주소가 없으면 그 줄은 붙이지 않는다


def test_the_record_cannot_be_rewritten(cookies):
    """추가만 한다 — 고치기는 DB 가 막는다(누가 언제 켰나가 덮여 사라지면 「직접 고른 것」을 증명할 수 없다)."""
    from psycopg import errors

    trip_id = _trip(cookies, constraints=NO_SURVEY)
    _post(cookies, trip_id, {"enabled": True, "via": "header"})
    with pytest.raises(errors.RaiseException):
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE trip_guardian_changes SET via='settings' WHERE trip_id=%s", (trip_id,))
    assert _rows(trip_id) == [(True, "header")]

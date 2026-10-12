"""후속 질문·선택지의 대상과 여행 격리. 모델이 대상을 누락하는 실제 실패 조건을 고정한다."""
from uuid import uuid4
from dataclasses import replace

from app.infrastructure.db.session import get_connection

from .test_decision_unit_web import decided, _say  # noqa: F401
from .test_web_api import api, _fresh_limit_cache, _h, _session, _web_body  # noqa: F401
from .test_web_api import _member


def _omit_target(decided, fact="address"):
    def structured(system, user, schema, **kw):
        decided["decider"].prompts.append(user)
        return {"action": "answer_fact", "target_item": "none", "target_change": "none",
                "fact": fact, "minutes": 0, "choices": []}
    decided["decider"].structured = structured


def test_named_answer_choices_keep_target_when_model_omits_it(decided):
    _omit_target(decided)
    first = _say(decided, "성수 점심 식당 어디에 있어?", "ctx-1")
    assert "성수 점심" in first["answer"]
    detail = next(c for c in first["choices"] if "자세히" in c["message"])
    assert detail.get("item_id"), first
    _omit_target(decided, "detail")
    second = _say(decided, "자세히 알려줘", "ctx-2", item_id=detail["item_id"])
    assert "성수 점심" in second["answer"] and "찾지 못했어요" not in second["answer"]


def test_free_followup_and_topic_switch_survive_server_record_reload(decided):
    _omit_target(decided)
    _say(decided, "성수 점심 식당 주소 알려줘", "ctx-f1")
    _omit_target(decided, "detail")
    for n, text in enumerate(("자세히 알려줘", "거기 알려줘", "그거 알려줘")):
        assert "성수 점심" in _say(decided, text, f"ctx-f{n+2}")["answer"]
    switched = _say(decided, "저녁 상세 알려줘", "ctx-switch")
    assert "저녁" in switched["answer"]
    assert "저녁" in _say(decided, "그거 자세히 알려줘", "ctx-switch-follow")["answer"]
    turns = decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}/chat", headers=_h(decided["key"])).json()["turns"]
    assert turns[-1]["reply"]["choices"] and turns[-1]["reply"]["focus"]["item_id"]


def test_foreign_and_removed_selected_target_never_fall_to_another_item(decided):
    _omit_target(decided, "detail")
    body = _say(decided, "자세히 알려줘", "ctx-foreign", item_id=str(uuid4()))
    assert body["status"] == "clarify" and "선택" in body["answer"]
    assert decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}", headers=_h(decided["key"])).json()["version"] == 1
    other = _session({"client": decided["client"]})
    for suffix in ("/chat", ""):
        response = decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}{suffix}", headers=_h(other["user_key"]))
        assert response.status_code == 404


def test_same_customer_other_trip_does_not_inherit_focus_or_accept_foreign_item(decided, api):
    _omit_target(decided)
    first = _say(decided, "성수 점심 식당 주소 알려줘", "ctx-isolated-1")
    target = first["choices"][0]["item_id"]
    _member(api, decided["key"])
    response = decided["client"].post("/v1/web/trips", headers=_h(decided["key"]),
                                         json=_web_body(api, request_id="ctx-second-trip"))
    assert response.status_code == 201, response.text
    second = {**decided, "trip": response.json()}
    _omit_target(decided, "detail")
    assert "찾지 못했어요" in _say(second, "자세히 알려줘", "ctx-isolated-2")["answer"]
    assert _say(second, "자세히 알려줘", "ctx-isolated-3", item_id=target)["status"] == "clarify"
    turns = decided["client"].get(f"/v1/web/trips/{second['trip']['trip_id']}/chat", headers=_h(decided["key"])).json()["turns"]
    assert all("성수 점심 식당 주소" not in t["text"] for t in turns)


def test_replaced_item_invalidates_previous_focus_and_old_button(decided, api):
    _omit_target(decided)
    first = _say(decided, "성수 점심 식당 주소 알려줘", "ctx-replaced-1")
    target = first["choices"][0]["item_id"]
    with get_connection() as conn, conn.transaction():
        trip, items = api["store"].latest(conn, decided["trip"]["trip_id"])
        updated = [replace(i, item_id=uuid4(), title="새 점심 일정") if str(i.item_id) == target else i for i in items]
        api["store"].append_version(conn, trip_id=trip["trip_id"], base_version=trip["version"],
                                      items=updated, reason="context_regression", causes=[])
    _omit_target(decided, "detail")
    assert _say(decided, "자세히 알려줘", "ctx-replaced-2")["status"] == "clarify"
    assert _say(decided, "자세히 알려줘", "ctx-replaced-3", item_id=target)["status"] == "clarify"


def test_reconnect_with_same_request_restores_choices_without_duplicate_turns(decided):
    _omit_target(decided)
    first = _say(decided, "성수 점심 식당 주소 알려줘", "ctx-retry")
    retried = _say(decided, "성수 점심 식당 주소 알려줘", "ctx-retry")
    assert retried["choices"] == first["choices"]
    assert retried["case_id"] == first["case_id"]
    turns = decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}/chat", headers=_h(decided["key"])).json()["turns"]
    assert len(turns) == 2

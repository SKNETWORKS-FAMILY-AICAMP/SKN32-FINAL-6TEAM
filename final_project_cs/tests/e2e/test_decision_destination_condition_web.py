"""고객이 말한 목적지 · 조건을 해석 결과에 담고, 지킬 수 없으면 다른 곳으로 바꾸지 않는다(`decision_unit.decide`).

x600 서버 웹 채팅 시험(2026-10-13)에서 「광장시장 대신 통인시장」은 평래옥으로, 「비 오면 실내로」는 비가 안 왔는데도 바로 바뀌었다.
"""
from app.infrastructure.db.session import get_connection
from .test_decision_unit_web import decided, _say  # noqa: F401
from .test_web_api import api, _fresh_limit_cache, _h  # noqa: F401


def _versions(decided):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM itinerary_versions WHERE trip_id=%s", (decided["trip"]["trip_id"],))
        return cur.fetchone()[0]


def _answer_with(decided, **fields):
    original = decided["decider"].structured

    def structured(system, user, schema, *, num_predict=160):
        decided["decider"].prompts.append(user)
        target = decided["decider"]._alias(user, "성수 점심")
        return {"action": "apply_change", "target_item": target, "target_change": "none", "fact": "none", "minutes": 0,
                "choices": [], "reads": [], "social": "", "general_requests": [], "change_scope": "place", **fields}
    decided["decider"].structured = structured
    return original


def test_a_named_destination_is_not_replaced_by_the_nearest_candidate(decided):
    _answer_with(decided, destination_text="통인시장")
    before = _versions(decided)
    body = _say(decided, "점심 통인시장으로 바꿔", "named-destination")
    assert _versions(decided) == before, body                     # 일정은 바뀌지 않았다
    assert body["status"] != "adjusted" and body["decision"]["action"] == "propose_alternatives", body
    assert body["answer"].startswith("말씀하신 「통인시장」(으)로 바로 바꾸는 기능은 아직 없어 일정은 바꾸지 않았어요."), body
    assert body["decision"]["raw"]["named_destination"]["text"] == "통인시장"


def test_a_change_without_a_named_destination_still_applies(decided):
    _answer_with(decided, destination_text="")
    body = _say(decided, "점심 다른 데로 바꿔", "unnamed-destination")
    assert body["status"] == "adjusted", body


def test_a_conditional_change_is_not_applied_now(decided):
    _answer_with(decided, condition_text="비 오면")
    before = _versions(decided)
    body = _say(decided, "비 오면 점심 다른 데로 바꿔", "conditional-change")
    assert _versions(decided) == before and body["status"] == "answered", body
    assert "「비 오면」처럼 조건이 붙은 변경은 아직 미리 걸어 둘 수 없어 지금은 일정을 바꾸지 않았어요." in body["answer"]

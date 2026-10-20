"""고객이 말한 목적지 · 조건을 해석 결과에 담고, 지킬 수 없으면 다른 곳으로 바꾸지 않는다(`decision_unit.decide`).

x600 서버 웹 채팅 시험(2026-10-13)에서 「광장시장 대신 통인시장」은 평래옥으로, 「비 오면 실내로」는 비가 안 왔는데도 바로 바뀌었다.
"""
from app.infrastructure.db.session import get_connection
from .test_decision_unit_web import decided, _say  # noqa: F401
from .test_trip_api import DAY
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
    """`[2026-10-15]` 말한 곳은 **그곳을 찾아** 바꾼다(`chat_edit` — 웹 「일정 수정」과 같은 이름 찾기). 못 찾아도 근처 후보로 바꾸지 않는다 —
    전에는 근처 첫 후보로 바꾸고 「요청하신 대로」라고 답했다(10-13), 그다음엔 다른 안만 보였다(10-14). 찾은 경우는 `test_chat_edit_web.py`.

    ★`[2026-10-20]` 못 찾았을 때의 기대값은 2026-10-19 사용자 결정 A 다 — 요청한 이름을 「위치 확인 필요」로 **저장**하고
    같은 답에 직접 고르기 카드(`pick: change`)를 싣는다(`wiki/records/plans/2026-10-19_못찾은장소_후보와_직접고르기_설계.md` §2-4).
    대화 시각은 여행 날로 보낸다 — 2030년으로 보내면 모든 일정이 「이미 지난 일정」이라 바꾸기 자체가 거절된다."""
    _answer_with(decided, destination_text="통인시장")
    before = _versions(decided)
    body = _say(decided, "점심 통인시장으로 바꿔", "named-destination", at=f"{DAY}T09:00:00+09:00")
    assert _versions(decided) == before + 1, body                 # 요청한 이름은 남는다(결정 A — 거절하고 원래 일정을 남기는 안 B 는 고르지 않았다)
    assert "요청하신 대로" not in body["answer"] and "통인시장" in body["answer"] and "확인 중" in body["answer"], body
    assert body["pick"]["mode"] == "change" and body["pick"]["query"] == "통인시장", body       # 근처 후보로 바꾸지 않고 고객이 고르게 한다
    assert body["decision"]["raw"]["named_destination"]["text"] == "통인시장"


def test_a_change_without_a_named_destination_still_applies(decided):
    _answer_with(decided, destination_text="")
    body = _say(decided, "점심 다른 데로 바꿔", "unnamed-destination")
    assert body["status"] == "adjusted", body


def test_a_conditional_change_is_not_applied_now(decided):
    """★`[2026-10-14]` 조건이 붙으면 바로 바꾸지 않고 다른 안을 보여 고르게 한다 — 전에는 통째로 막아 「다른 식당으로」 같은
    정상 요청까지 「조건이 붙은 변경은 미리 걸어 둘 수 없다」로 답했다(모델이 원하는 곳 설명을 조건 칸에 적은 경우)."""
    _answer_with(decided, condition_text="비 오면")
    before = _versions(decided)
    body = _say(decided, "비 오면 점심 다른 데로 바꿔", "conditional-change")
    assert _versions(decided) == before and body["status"] != "adjusted", body       # 일정은 바뀌지 않았다
    assert body["decision"]["action"] == "propose_alternatives", body
    assert body["decision"]["raw"]["condition_guard"] == {"condition": "비 오면", "blocked_action": "apply_change"}
    assert "미리 걸어 둘 수 없어" not in body["answer"], body


def test_a_destination_mistaken_for_a_condition_still_gets_alternatives(decided):
    _answer_with(decided, condition_text="다른 식당으로")
    before = _versions(decided)
    body = _say(decided, "토속촌 삼계탕 다른 식당으로 바꿔줘", "condition-false-positive")
    assert _versions(decided) == before, body
    assert body["decision"]["action"] == "propose_alternatives" and body.get("choices"), body

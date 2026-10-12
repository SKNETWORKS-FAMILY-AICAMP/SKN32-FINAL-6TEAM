"""복합 질문과 문맥의 대상 검증을 실제 API 경로에서 확인한다."""
from .test_decision_unit_web import decided, _say  # noqa: F401
from .test_web_api import api, _fresh_limit_cache, _h  # noqa: F401


def _model(decided, requests=(), social=""):
    def structured(system, user, schema, **kwargs):
        aliases = {name: decided["decider"]._alias(user, name) for name in ("성수 점심", "· 저녁")}
        reads = [{"fact": fact, "target_item": aliases[name] if name else "none",
                  "reference": reference, "origin_item": "none", "query": None,
                  "text": "", "advice": ""} for fact,name,reference in requests]
        return {"action": "answer_fact" if reads else "other", "target_item": reads[0]["target_item"] if reads else "none",
                "target_change": "none", "fact": reads[0]["fact"] if reads else "none", "minutes": 0,
                "choices": [], "query": None, "reads": reads, "social": social}
    decided["decider"].structured = structured


def test_each_read_keeps_its_own_target_and_last_target_survives_reload(decided):
    _model(decided, [("time", "성수 점심", "explicit"), ("duration", "· 저녁", "explicit")], "천천히 확인해 볼게요.")
    first = _say(decided, "성수 점심은 언제고 저녁은 얼마나 머물러?", "multi-read-1")
    assert "성수 점심" in first["answer"] and "저녁" in first["answer"] and "분 머무는" in first["answer"]
    turns = decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}/chat", headers=_h(decided["key"])).json()["turns"]
    assert turns[-1]["turn_id"] > turns[-2]["turn_id"]
    _model(decided, [("time", "성수 점심", "previous")])  # 모델의 잘못된 옛 장소 추측을 주입한다.
    follow = _say(decided, "ㅇㅋ 거기는 몇 시에 감?", "multi-read-2")
    assert "저녁" in follow["answer"] and "성수 점심" not in follow["answer"]
    assert decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}", headers=_h(decided["key"])).json()["version"] == 1


def test_social_turn_clears_old_focus_instead_of_reusing_a_place(decided):
    _model(decided, [("time", "성수 점심", "explicit")])
    _say(decided, "성수 점심 시간", "social-clear-1")
    _model(decided, social="오늘 하루도 수고하셨어요.")
    assert "수고" in _say(decided, "아 오늘 힘들었다", "social-clear-2")["answer"]
    _model(decided, [("hours", "성수 점심", "previous")])
    after = _say(decided, "그쪽 몇 시까지 열어?", "social-clear-3")
    assert "성수 점심" not in after["answer"] and "알려" in after["answer"]

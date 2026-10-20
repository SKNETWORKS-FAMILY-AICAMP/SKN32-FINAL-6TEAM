# -*- coding: utf-8 -*-
"""대체 후보 순서 — 코드가 찾고 검증한 후보 안에서 LLM 이 취향에 맞춰 먼저 보여 줄 순서를 정한다. `[2026-10-12 사용자 결정]`

★가짜 모델로(API 없음). 후보 계산(`rank_alternatives`)은 그대로 — 바뀌는 것은 보여 주는 순서와 이유 한 줄뿐이다.
★목록에 없는 장소는 버리고, 꺼져 있거나 · 실패하면 코드 순서 그대로다.
"""
from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace

from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.instances.activity import alternative_order
from app.domains.travel_ops.instances.activity import replacement as replacement_module
from app.domains.travel_ops.instances.activity import team as team_module
from app.domains.travel_ops.instances.activity.judge.modes import kind_mode

from ..helpers import FakeTools, pack, task
from .test_activity_closed_alternatives import ALLOWED, CLEAR, PLACE, POOL, TUESDAY, WEEK, _hours
from ._disaster import disaster_from

CODE_ORDER = ["창덕궁", "덕수궁"]          # 코드 순서 — 같은 분류 · 가까운 곳 먼저(종묘는 같은 화요일 휴무라 빠진다)
SURVEY = {"party": "아이 동반", "theme": "체험", "priority": ["activity"]}


class OrderLLM:
    def __init__(self, output=None, *, exc=None):
        self.output, self.exc, self.calls = output, exc, []

    async def judge(self, prompt_key, payload, *, schema, schema_name, web_search=None, instructions=None, run_id=None):
        self.calls.append({"prompt_key": prompt_key, "payload": payload, "web_search": web_search,
                           "instructions": instructions})
        if self.exc is not None:
            raise self.exc
        return SimpleNamespace(output=self.output, model="fake")


class Inline:
    def submit(self, work):
        thread = threading.Thread(target=work)
        thread.start()
        thread.join(10)
        return True


def _modes(monkeypatch, order_mode):
    modes = {"alternative_order": order_mode}            # 나머지 종류는 `rule`(부르지 않음)
    for module in (team_module, replacement_module):
        monkeypatch.setattr(module, "kind_mode", lambda kind, _m=None: kind_mode(kind, modes))


def _run(monkeypatch, llm, *, mode="llm", survey=SURVEY, text="아이랑 갈 만한 데로 바꿔 주세요", extra_state=None):
    _modes(monkeypatch, mode)
    values = {"read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": TUESDAY,
                               "party_size": 2, "capacity": 4},
              "read.policy": [], "read.place": PLACE, "read.disruptions": CLEAR, "read.disaster": disaster_from(CLEAR),
              "read.place_hours": _hours({**WEEK, "tue": "closed"}), "read.place_candidates": POOL}
    team = ActivityTeam(FakeTools(values))
    team.judge_llm, team.judge_runner = llm, Inline()
    state = {**({"survey": survey} if survey else {}), **(extra_state or {})} or None
    context = pack("activity", scope=["activity"], state=state)
    result = asyncio.run(team.execute(task("activity", "activity.check_feasible", context, ALLOWED, input_text=text)))
    alternatives = result.decisions[0]["alternatives"]
    return result, alternatives, [a["title"] for a in alternatives["alternatives"] if a["revalidated"]]


def test_the_llm_reorders_only_the_checked_candidates_and_says_why(monkeypatch):
    llm = OrderLLM({"order": ["b", "a"], "used_preference": True, "reason": "아이와 함께라 체험 프로그램이 있는 덕수궁을 먼저 보여 드려요"})
    result, alternatives, titles = _run(monkeypatch, llm)

    assert titles == ["덕수궁", "창덕궁"]
    assert alternatives["order"]["by"] == "llm" and alternatives["order"]["ids"] == ["b", "a"]
    assert "AI 가 고객님 취향에 맞춰" in result.answer and "덕수궁을 먼저" in result.answer
    sent = llm.calls[0]
    assert sent["prompt_key"] == alternative_order.PROMPT_KEY and sent["web_search"] is False
    assert [c["id"] for c in sent["payload"]["candidates"]] == ["a", "b"]           # 검증된 후보만, 코드 순서로
    assert sent["payload"]["preference"]["survey"]["party"] == "아이 동반"
    assert "mapx" not in str(sent["payload"])                                       # 좌표 원문은 보내지 않는다


def test_a_made_up_place_is_dropped_and_the_rest_keep_code_order(monkeypatch):
    llm = OrderLLM({"order": ["zzz", "b"], "used_preference": True, "reason": "체험형"})
    result, alternatives, titles = _run(monkeypatch, llm)

    assert titles == ["덕수궁", "창덕궁"] and alternatives["order"]["dropped"] == 1
    assert any("목록에 없는 장소" in w for w in result.warnings)


def test_failures_keep_the_code_order(monkeypatch):
    for llm in (OrderLLM(exc=RuntimeError("no active prompt")), OrderLLM({"order": ["zzz"], "used_preference": True,
                                                                          "reason": "x"})):
        result, alternatives, titles = _run(monkeypatch, llm)
        assert titles == CODE_ORDER and alternatives["order"]["by"] == "code"
        assert "AI 가" not in result.answer


def test_no_reason_is_shown_when_the_model_did_not_use_the_preference(monkeypatch):
    result, _, titles = _run(monkeypatch, OrderLLM({"order": ["a", "b"], "used_preference": False, "reason": "없음"}))
    assert titles == CODE_ORDER and "AI 가" not in result.answer


def test_off_by_default_and_in_shadow_the_customer_sees_the_code_order(monkeypatch):
    llm = OrderLLM({"order": ["b", "a"], "used_preference": True, "reason": "체험형"})
    _, alternatives, titles = _run(monkeypatch, llm, mode="rule")
    assert llm.calls == [] and titles == CODE_ORDER and "order" not in alternatives

    _, alternatives, titles = _run(monkeypatch, llm, mode="shadow")
    assert len(llm.calls) == 1 and titles == CODE_ORDER and "order" not in alternatives


def test_preference_inputs_need_a_clue():
    assert alternative_order.preference_inputs(None, "  ") is None
    assert alternative_order.preference_inputs({"pace": "relaxed", "domestic": True}, "") is None   # 취향과 무관한 칸뿐
    picked = alternative_order.preference_inputs({"theme": "힐링", "priority_details": {"activity": ["힐링"]}}, None)
    assert picked == {"survey": {"theme": "힐링", "activity_details": ["힐링"]}, "customer_text": None}


def test_priority_is_not_a_taste_and_is_not_sent():
    """`[2026-10-20]` 우선순위는 후보를 뽑는 범위다 — LLM 에 넘기지 않고, 그것만 있으면 단서 없음(부르지 않음)."""
    assert alternative_order.preference_inputs({"priority": ["mobility"]}, None) is None
    picked = alternative_order.preference_inputs({"priority": ["activity"], "theme": "자연"}, "바꿔 주세요")
    assert picked["survey"] == {"theme": "자연"}


def test_the_llm_does_not_see_the_priority(monkeypatch):
    llm = OrderLLM({"order": ["a", "b"], "used_preference": False, "reason": ""})
    _run(monkeypatch, llm)
    assert "priority" not in llm.calls[0]["payload"]["preference"]["survey"]


# ── `[2026-10-19]` 감시 루프가 연 Case — 제목(시스템 문구)을 고객 문장으로 넘기지 않는다 ──────────────────

WATCH = {"trigger_source": alternative_order.WATCH_TRIGGER}
WATCH_SUBJECT = "[감시] 경복궁 — closure"


def test_a_watch_case_sends_the_survey_but_not_its_system_subject(monkeypatch):
    llm = OrderLLM({"order": ["b", "a"], "used_preference": True, "reason": "아이와 함께라 체험이 있는 덕수궁을 먼저 보여 드려요"})
    _, alternatives, titles = _run(monkeypatch, llm, text=WATCH_SUBJECT, extra_state=WATCH)

    sent = llm.calls[0]["payload"]["preference"]
    assert sent["customer_text"] is None and sent["survey"]["theme"] == "체험"
    assert "[감시]" not in str(llm.calls[0]["payload"])
    assert titles == ["덕수궁", "창덕궁"] and alternatives["order"]["by"] == "llm"


def test_a_watch_case_without_survey_does_not_call_the_llm(monkeypatch):
    llm = OrderLLM({"order": ["b", "a"], "used_preference": True, "reason": "x"})
    _, alternatives, titles = _run(monkeypatch, llm, survey=None, text=WATCH_SUBJECT, extra_state=WATCH)

    assert llm.calls == [] and titles == CODE_ORDER and "order" not in alternatives     # 전에는 시스템 문구 때문에 불렀다


def test_a_watch_case_sends_only_what_the_customer_answered(monkeypatch):
    llm = OrderLLM({"order": ["a", "b"], "used_preference": False, "reason": ""})
    text = f"원래 요청: {WATCH_SUBJECT}\n추가 답변: 아이랑 실내가 좋아요"
    _run(monkeypatch, llm, survey=None, text=text, extra_state={**WATCH, "customer_input": "아이랑 실내가 좋아요"})

    assert llm.calls[0]["payload"]["preference"]["customer_text"] == "아이랑 실내가 좋아요"


def test_customer_words_keeps_customer_cases_as_they_are():
    assert alternative_order.customer_words("비 와서 실내로 바꿔 주세요", {}) == "비 와서 실내로 바꿔 주세요"
    assert alternative_order.customer_words("비 와서 실내로", {"customer_input": "아이도 있어요"}) == "비 와서 실내로"
    assert alternative_order.customer_words(WATCH_SUBJECT, WATCH) is None
    assert alternative_order.customer_words(WATCH_SUBJECT, {**WATCH, "customer_input": {"choice": 1}}) is None


# ── `[2026-10-13 사용자 결정 A안]` 3곳 → 3곳 순서만 ─────────────────────────────────────

def _pool_of_six():
    from .test_activity_closed_alternatives import ORIGIN, _row

    rows = [_row(f"c{i}", f"장소{i}", x=126.9770 + 0.002 * i, y=37.5796) for i in range(1, 7)]
    return {"origin": ORIGIN, "source": "place_catalog", "confirmed_at": "2026-10-09T03:00:00+09:00", "candidates": rows}


def _run_six(monkeypatch, llm, *, mode="llm"):
    _modes(monkeypatch, mode)
    values = {"read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": TUESDAY, "party_size": 2, "capacity": 4},
              "read.policy": [], "read.place": PLACE, "read.disruptions": CLEAR, "read.disaster": disaster_from(CLEAR),
              "read.place_hours": _hours({**WEEK, "tue": "closed"}), "read.place_candidates": _pool_of_six()}
    team = ActivityTeam(FakeTools(values))
    team.judge_llm, team.judge_runner = llm, Inline()
    context = pack("activity", scope=["activity"], state={"survey": SURVEY})
    result = asyncio.run(team.execute(task("activity", "activity.check_feasible", context, ALLOWED,
                                           input_text="아이랑 갈 만한 데로 바꿔 주세요")))
    alt = result.decisions[0]["alternatives"]
    return result, alt, [a["contentid"] for a in alt["alternatives"]], [a["contentid"] for a in alt["more_alternatives"]]


def test_only_the_three_shown_candidates_go_to_the_llm_and_more_stays_in_code_order(monkeypatch):
    base = OrderLLM({"order": ["c1", "c2", "c3"], "used_preference": False, "reason": ""})
    _, _, shown_code, more_code = _run_six(monkeypatch, base)
    assert len(shown_code) == 3 and len(more_code) >= 3                     # 화면 3곳 + 더보기
    assert [c["id"] for c in base.calls[0]["payload"]["candidates"]] == shown_code

    llm = OrderLLM({"order": [shown_code[2], shown_code[0], shown_code[1]], "used_preference": True,
                    "reason": "아이와 함께라 가장 가까운 곳을 먼저 보여 드려요"})
    result, alt, shown, more = _run_six(monkeypatch, llm)

    assert shown == [shown_code[2], shown_code[0], shown_code[1]]            # 같은 3곳, 순서만 바뀜
    assert set(shown) == set(shown_code) and more == more_code               # 더보기는 코드 순서 그대로
    assert alt["order"]["by"] == "llm" and "AI 가 고객님 취향에 맞춰" in result.answer


def test_the_llm_cannot_promote_a_more_candidate_into_the_shown_three(monkeypatch):
    _, _, shown_code, more_code = _run_six(monkeypatch, OrderLLM({"order": [], "used_preference": False, "reason": ""}))
    llm = OrderLLM({"order": [more_code[0], *shown_code], "used_preference": True, "reason": "더 어울려요"})
    _, alt, shown, more = _run_six(monkeypatch, llm)

    assert shown == shown_code                                               # 더보기 후보는 상위 3곳에 들어오지 못한다
    assert more_code[0] not in shown and more == more_code and alt["order"]["dropped"] == 1


def test_a_reorder_without_a_reason_is_not_accepted(monkeypatch):
    _, _, shown_code, _ = _run_six(monkeypatch, OrderLLM({"order": [], "used_preference": False, "reason": ""}))
    for output in ({"order": list(reversed(shown_code)), "used_preference": False, "reason": ""},
                   {"order": list(reversed(shown_code)), "used_preference": True, "reason": "  "}):
        result, alt, shown, _ = _run_six(monkeypatch, OrderLLM(output))
        assert shown == shown_code and alt["order"]["by"] == "code"
        assert "AI 가" not in result.answer


def test_the_same_order_needs_no_reason(monkeypatch):
    _, _, shown_code, _ = _run_six(monkeypatch, OrderLLM({"order": [], "used_preference": False, "reason": ""}))
    _, alt, shown, _ = _run_six(monkeypatch, OrderLLM({"order": shown_code, "used_preference": False, "reason": ""}))
    assert shown == shown_code and alt["order"]["by"] == "llm" and alt["order"]["reason"] is None


# ── `[2026-10-20 실험 E1]` 분류 이름 — 코드만 주면 모델이 뜻을 짐작했다 ─────────────────────────────

def test_class_names_come_from_the_kto_table_and_are_opt_in():
    assert alternative_order.class_path("HS010100") == "역사관광 > 역사유적지 > 고궁"
    assert alternative_order.class_path("VE010100") == "문화관광 > 랜드마크관광 > 건물"      # 팔각정 — 궁궐이 아니다
    assert alternative_order.class_path(None) is None and alternative_order.class_path("ZZ000000") is None
    pool = [{"contentid": "a", "title": "팔각정", "reason": "0.1km", "distance_km": 0.1}]
    plain = alternative_order.candidate_rows(pool, {"a": "VE010100"})
    named = alternative_order.candidate_rows(pool, {"a": "VE010100"}, with_class_name=True)
    assert "class_name" not in plain[0]                                                  # 운영은 아직 끔(v2)
    assert named[0]["class_name"] == "문화관광 > 랜드마크관광 > 건물" and named[0]["class"] == "VE010100"


def test_production_sends_class_names_with_prompt_v3(monkeypatch):
    """`[2026-10-20]` holdout-2 판정 뒤 운영 경로가 분류 이름을 싣는다 — 지시문 v3 가 그 칸을 읽는다."""
    llm = OrderLLM({"order": ["a", "b"], "used_preference": False, "reason": ""})
    _run(monkeypatch, llm)
    assert all("class_name" in c for c in llm.calls[0]["payload"]["candidates"])
    from app.domains.travel_ops.instances.activity.judge.llm import file_instructions

    assert "class_name" in file_instructions(alternative_order.KIND)            # 가장 높은 판(v3)이 그 칸을 설명한다


# ── `[2026-10-20]` 이유 문장 지킴이 — 확인할 수 없는 말 · 「A 아니면 B」 거꾸로 읽기 · 장소 번호 ──────────────────

def _guarded(reason, text):
    pool = [{"contentid": "a", "title": "은평역사한옥박물관"}, {"contentid": "b", "title": "진관사"}]
    out = alternative_order.apply(pool, {"order": ["a", "b"], "used_preference": True, "reason": reason},
                                  customer_text=text, classes={"a": "VE070100", "b": "HS030100"})
    return out[1]["reason"], out[1]["reason_guard"], [c["contentid"] for c in out[0]]


def test_reason_guard_replaces_unverifiable_claims_but_keeps_the_order():
    reason, why, order = _guarded("조용한 실내에 맞게 박물관을 1순위로 했어요.", "조용한 실내로 부탁해요")
    assert why == "unverifiable" and "조용" not in reason and order == ["a", "b"]
    assert reason == "요청에 맞춰 ‘은평역사한옥박물관’(박물관)을 먼저 보여 드려요."


def test_reason_guard_catches_a_reversed_either_or_and_content_ids():
    assert _guarded("박물관 후보는 1순위를 피했어요.", "박물관 아니면 전시 같은 거")[1] == "reversed_either"
    assert _guarded("박물관 말고 다른 곳을 먼저 두었어요.", "박물관 말고 전시")[1] is None     # 고객이 정말 거부했다
    assert _guarded("3080519 를 1순위로 했어요.", "실내")[1] == "content_id"


def test_reason_guard_leaves_grounded_reasons_alone():
    reason, why, _ = _guarded("실내를 원하셔서 전시시설인 박물관을 먼저 보여 드려요.", "실내로 바꿔 주세요")
    assert why is None and reason.startswith("실내를 원하셔서")
    assert alternative_order._particle("무인비행장치(드론)") == "을" and alternative_order._particle("놀이터") == "를"

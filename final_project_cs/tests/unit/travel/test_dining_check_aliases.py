# -*- coding: utf-8 -*-
"""요식 판정 — 속성 이름으로 적은 체크 이름(식단 · 결제 · 아이) · 화면 문장의 조건 이름. `[2026-10-18]`

★실측: 모델이 체크 이름을 `dietary` 가 아니라 속성 이름(`halal`)으로 적어 검증기가 `unknown_check` 로 거절했다
  (v1 DG-007 · v2 DG2-041, 할랄 조건 판 39회 중 1회). 그러면 그 식사의 식이 줄이 빠져, 필수 할랄이 안 맞아도 등록이 막히지 않을 수 있다.
  → 속성 이름(halal · vegetarian · vegan → dietary, card · card_payment → payment, kids_allowed → kids)만 맞춰 읽는다.
    근거 검증은 그대로 한다. 원래 이름은 `claimed_check` 에 남긴다. 결제는 식단을 고친 뒤 재측정에서 나왔다(DG2-040 `card`).
★화면 문장 「요청하신 식사 조건(할랄 · 채식)」은 고정 글자였다 — 할랄만 말해도 채식이 같이 나왔다. 근거로 확인한 속성만 적는다.
"""
from __future__ import annotations

import json
from contextlib import nullcontext

import pytest

from app.domains.travel_ops.instances.dining import judge
from app.domains.travel_ops.instances.dining.agent import judge_day, validate_check
from app.infrastructure.llm.tool_chat import ToolTurn

from .test_dining_agent import PLAN, UID, AttrTools, Script, _call


def _tools():
    return AttrTools(lambda: nullcontext(None))


TOOLS_TURN = ToolTurn(content=None, tool_calls=[
    _call(1, "find_place", name="시험국밥"),
    _call(2, "check_open_at", place_uid=UID, start="2026-10-25T12:00", end="2026-10-25T13:00"),
    _call(3, "check_attributes", place_uid=UID, wanted=["halal", "vegetarian"])])


def _final(diet_name, verdict, path, value):
    checks = [{"check": "found", "verdict": "ok", "reason": "x", "evidence": [{"call_id": "c1", "path": "verdict", "value": "ok"}]},
              {"check": "open_at", "verdict": "ok", "reason": "x", "evidence": [{"call_id": "c2", "path": "verdict", "value": "ok"}]},
              {"check": diet_name, "verdict": verdict, "reason": "x", "required": True,
               "evidence": [{"call_id": "c3", "path": path, "value": value}]}]
    return ToolTurn(content=json.dumps({"items": [{"item_id": "i1", "place": {"place_uid": UID, "call_id": "c1"},
                                                    "checks": checks}], "skipped": []}, ensure_ascii=False))


def _diet(result):
    return next(c for c in result.items[0]["checks"] if c["check"] == "dietary")


@pytest.mark.parametrize("name,verdict,attr,value", [("halal", "bad", "halal", "no"), ("Halal", "bad", "halal", "no"),
                                                     ("vegetarian", "ok", "vegetarian", "limited"),
                                                     ("vegan", "ok", "vegetarian", "limited")])
def test_a_diet_attribute_name_is_read_as_the_dietary_check(name, verdict, attr, value):
    result = judge_day(PLAN, tools=_tools(), chat=Script(TOOLS_TURN, _final(name, verdict, f"attributes.{attr}.state", value)))
    diet = _diet(result)
    assert result.stats["validation_failures"] == 0 and "failure" not in diet
    assert (diet["verdict"], diet["claimed_check"], diet["required"]) == (verdict, name, True)
    assert not result.missing


def test_the_alias_is_still_validated_against_the_cited_attribute():
    """이름만 맞춰 준다 — 아이 동반을 인용한 「할랄 ok」 · 할랄 no 를 인용한 「할랄 ok」는 그대로 거절한다."""
    tools = _tools()
    tools.call("check_attributes", {"place_uid": UID, "wanted": ["halal", "kids"]})

    def claim(path, value, verdict="ok"):
        return {"check": "halal", "verdict": verdict, "reason": "x", "evidence": [{"call_id": "c1", "path": path, "value": value}]}
    assert validate_check(claim("attributes.kids.state", "yes"), tools, place_uid=UID) == "evidence_wrong_attribute"
    assert validate_check(claim("attributes.halal.state", "no"), tools, place_uid=UID) == "contradicts_attribute"
    assert validate_check(claim("attributes.halal.state", "no", "bad"), tools, place_uid=UID) is None


class CardNoTools(AttrTools):
    """카드 결제 no — 필수 결제가 안 맞는 경우(위험 쪽)."""

    def _check_attributes(self, place_uid, wanted):
        table = {"halal": "no", "vegetarian": "limited", "kids": "yes", "card": "no"}
        return {"attributes": {w: {"state": table[w], "source_text": None, "source": None, "verified_at": None} for w in wanted}}


@pytest.mark.parametrize("name,check,verdict,attr,value", [("card", "payment", "bad", "card", "no"),
                                                           ("card_payment", "payment", "bad", "card", "no"),
                                                           ("Card", "payment", "bad", "card", "no"),
                                                           ("kids_allowed", "kids", "ok", "kids", "yes")])
def test_a_payment_or_kids_attribute_name_is_read_as_its_check(name, check, verdict, attr, value):
    """`[2026-10-18 v2 재측정]` DG2-040(필수 결제) — 모델이 `card` 로 적어 `unknown_check` 로 거절됐다. 식단과 같은 결함이다."""
    turn = ToolTurn(content=None, tool_calls=[
        _call(1, "find_place", name="시험국밥"),
        _call(2, "check_open_at", place_uid=UID, start="2026-10-25T12:00", end="2026-10-25T13:00"),
        _call(3, "check_attributes", place_uid=UID, wanted=[attr])])
    result = judge_day(PLAN, tools=CardNoTools(lambda: nullcontext(None)),
                       chat=Script(turn, _final(name, verdict, f"attributes.{attr}.state", value)))
    got = next(c for c in result.items[0]["checks"] if c["check"] == check)
    assert result.stats["validation_failures"] == 0 and "failure" not in got
    assert (got["verdict"], got["claimed_check"], got["required"]) == (verdict, name, True)


def test_a_payment_alias_citing_another_attribute_is_still_refused():
    tools = CardNoTools(lambda: nullcontext(None))
    tools.call("check_attributes", {"place_uid": UID, "wanted": ["card", "kids"]})
    claim = {"check": "card", "verdict": "ok", "reason": "x", "evidence": [{"call_id": "c1", "path": "attributes.kids.state", "value": "yes"}]}
    assert validate_check(claim, tools, place_uid=UID) == "evidence_wrong_attribute"
    claim["evidence"] = [{"call_id": "c1", "path": "attributes.card.state", "value": "no"}]
    assert validate_check(claim, tools, place_uid=UID) == "contradicts_attribute"       # 카드 no 인데 ok


def test_other_unknown_names_are_still_refused():
    tools = _tools()
    for name in ("parking", "attributes", "kids_ok", "cash", ""):
        assert validate_check({"check": name, "verdict": "unknown", "evidence": []}, tools) == "unknown_check", name


def _diet_row(evidence, verdict="bad"):
    review = {"items": [{"id": "0-1", "kind": "dining", "status": "keep", "rows": [{"row": "place", "result": "ok"}]}],
              "moves": [], "ready": True}
    merged, _ = judge.merge(review, {"0-1": [{"check": "dietary", "verdict": verdict, "evidence": evidence,
                                             "validated": True, "required": True}]})
    return next(r for r in merged["items"][0]["rows"] if r["row"] == "dietary")


def _ev(*attrs):
    return [{"tool": "check_attributes", "call_id": f"c{n}", "path": f"attributes.{a}.state", "value": "no"}
            for n, a in enumerate(attrs, start=1)]


@pytest.mark.parametrize("attrs,verdict,text", [
    (("halal",), "bad", "요청하신 식사 조건(할랄)에 맞지 않는 곳이에요"),
    (("vegetarian",), "ok", "요청하신 식사 조건(채식)에 맞는 곳이에요"),
    (("halal", "vegetarian"), "bad", "요청하신 식사 조건(할랄 · 채식)에 맞지 않는 곳이에요"),
    (("halal", "halal"), "unknown", "요청하신 식사 조건(할랄)은 확인하지 못했어요"),
    ((), "unknown", "요청하신 식사 조건은 확인하지 못했어요"),
])
def test_the_screen_text_names_only_the_conditions_that_were_checked(attrs, verdict, text):
    assert _diet_row(_ev(*attrs), verdict)["text"] == text


def test_a_dietary_claim_without_an_attribute_path_gets_the_plain_text():
    assert _diet_row([{"tool": "check_attributes", "call_id": "c1", "path": "verdict", "value": "bad"}])["text"] == \
        "요청하신 식사 조건에 맞지 않는 곳이에요"

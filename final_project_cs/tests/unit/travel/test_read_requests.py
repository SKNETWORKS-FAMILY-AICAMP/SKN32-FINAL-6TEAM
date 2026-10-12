from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.conversation import decision_unit as du, read_requests


NOW = datetime(2031, 3, 10, tzinfo=timezone.utc)


def item(name, seq, day=0):
    return SimpleNamespace(item_id=uuid4(), title=name, kind="activity", seq=seq, detail={},
                           starts_at=NOW + timedelta(days=day, hours=seq), ends_at=NOW + timedelta(days=day, hours=seq + 1),
                           place={"name": name, "attributes": {}, "kind": "activity"})


def read(fact, target="i1", reference="explicit", query=None, origin="none"):
    return dict(fact=fact, target_item=target, reference=reference, origin_item=origin, query=query, text="", advice="")


def render(items, requests, message="", turns=()):
    decision = du.Decision("answer_fact", None, None, requests[0]["fact"], None, "", reads=requests)
    return read_requests.reply(decision, items=items, message=message, selected=None, turns=turns, version=1,
                               now=NOW, context_now=NOW, ttl_seconds=1800, place_source=None)


@pytest.mark.parametrize("message", ["그쪽 문은 언제 닫아요?", "ㅇㅋ 거긴 마감 몇시임ㅋㅋ", "When does it close?"])
def test_semantic_followup_overrides_wrong_model_guess_in_any_style(message):
    a,b=item("솔빛전시관",1),item("푸른수목원",2)
    turns=[{"role":"assistant","reply":{"focus":{"item_id":str(b.item_id),"version":1,"at":NOW.isoformat()}}}]
    outcome,basis,focus=render([a,b],[read("hours","i1","previous")],message,turns)
    assert focus["item_id"] == str(b.item_id)
    assert basis["questions"][0]["item_id"] == str(b.item_id)
    assert a.title not in outcome["text"]


def test_explicit_scope_is_executed_and_no_query_is_lost():
    a,b=item("솔빛전시관",1),item("푸른수목원",2,1)
    result,basis,_=render([a,b],[read("day","none","none",dict(day="d2",period="all",kind="all"))])
    assert b.title in result["text"] and a.title not in result["text"]
    assert basis["questions"][0]["query"]["day"] == "d2"


def test_multiple_places_and_facts_are_not_reduced_to_the_first_question():
    a,b=item("솔빛전시관",1),item("푸른수목원",2)
    result,basis,focus=render([a,b],[read("time","i1"),read("duration","i2")])
    assert a.title in result["text"] and b.title in result["text"] and "60분" in result["text"]
    assert len(basis["questions"]) == 2 and focus["item_id"] == str(b.item_id)


def test_other_clause_exact_name_never_replaces_this_clause_alias_target():
    a,b=item("솔빛전시관",1),item("푸른수목원",2)
    requests=[{**read("time","i1"),"text":"솔빛전시관 방문 시간"},
              {**read("duration","i2"),"text":"수목원 머무는 시간"}]
    result,basis,focus=render([a,b],requests,"솔빛전시관 방문 시간이랑 수목원 머무는 시간 알려줘")
    assert [q["item_id"] for q in basis["questions"]] == [str(a.item_id),str(b.item_id)]
    assert b.title+":" in result["text"]
    assert focus["item_id"] == str(b.item_id)


def test_negated_old_place_does_not_make_the_new_explicit_place_ambiguous():
    a,b=item("솔빛전시관",1),item("푸른수목원",2)
    result,_,focus=render([a,b],[read("time","i2")],f"{a.title} 말고 {b.title} 방문 시간 좀요")
    assert b.title in result["text"] and a.title not in result["text"]
    assert focus["item_id"] == str(b.item_id)


def test_ambiguous_departure_never_uses_the_destination_next_leg():
    a,b=item("솔빛전시관",1),item("푸른수목원",2)
    result,basis,_=render([a,b],[read("move","i2")],"전시 보고 수목원 갈 건데 얼마나 걸려?")
    assert "출발지" in result["text"] and basis["questions"][0]["unresolved"] == "origin"


def test_customer_selected_place_conflict_is_exposed_and_keeps_target_for_followup():
    a=item("솔빛전시관",1)
    a.place["name"]="바람축제"
    a.detail={"provenance":{"place":{"method":"customer"}}}
    result,basis,focus=render([a],[read("hours")],"솔빛전시관 운영시간")
    assert a.title in result["text"] and "바람축제" in result["text"]
    assert basis["questions"][0]["unresolved"] == "place_identity"
    assert focus["item_id"] == str(a.item_id)


def test_absent_booking_requirement_does_not_become_no_reservation_needed():
    a=item("솔빛전시관",1)
    result,basis,_=render([a],[read("price"),read("entry_booking")])
    assert len(basis["questions"]) == 2
    assert all(q.get("unresolved") for q in basis["questions"])
    assert "필요 없" in result["text"] and "해석하지 않았" in result["text"]


def test_decoder_rejects_out_of_trip_read_target():
    class Chat:
        def structured(self,*args,**kw):
            return dict(action="answer_fact",target_item="i1",target_change="none",fact="time",minutes=0,
                        choices=[], reads=[read("time","i999")],social="")
    with pytest.raises(du.DecisionFailed):
        du.decide(Chat(),stops=du.stops_of([item("솔빛전시관",1)]),changes=[],history=[],selected_item_id=None,message="방문 시간")


def test_broad_origin_expression_never_selects_one_of_several_matching_places():
    a,b,c=item("솔빛전시관",1),item("달빛전시관",2),item("푸른수목원",3)
    request={**read("move","i3",origin="i1"),"origin_text":"전시관","transport_mode":"transit"}
    result,basis,_=render([a,b,c],[request],"전시관에서 수목원까지 대중교통 얼마나 걸려?")
    assert basis["questions"][0]["unresolved"] == "ambiguous_origin"
    assert a.title in result["text"] and b.title in result["text"]


def test_requested_transport_mode_reaches_the_registered_calculator(monkeypatch):
    from app.domains.travel_ops.components.team_hooks import legs
    a,b=item("솔빛전시관",1),item("푸른수목원",2)
    seen=[]
    def factory(*args,**kwargs):
        seen.append(kwargs["modes"])
        return lambda *args: ({"eta_min":11,"starts_at":NOW,"route":{"planned":"s","options":[{"id":"s","label":"지하철"}]}},None)
    monkeypatch.setattr(legs,"leg_planner",factory)
    request={**read("move","i2",origin="i1"),"origin_text":a.title,"transport_mode":"subway"}
    result,basis,_=render([a,b],[request],f"{a.title}에서 {b.title}까지 지하철")
    assert seen == [["subway"]] and "11분" in result["text"] and "도보" not in result["text"]


def test_first_last_query_focus_is_the_actual_filtered_item_not_model_hint():
    a,b=item("솔빛전시관",1),item("푸른수목원",2)
    query=dict(day="d1",period="all",kind="all",position="last")
    result,basis,focus=render([a,b],[read("day","none","none",query)])
    assert basis["questions"][0]["item_ids"] == [str(b.item_id)]
    assert focus["item_id"] == str(b.item_id) and a.title not in result["text"]


def test_general_request_answer_is_preserved_beside_a_travel_read():
    a=item("솔빛전시관",1)
    class Chat:
        def structured(self, system, prompt, schema, **kwargs):
            assert "general_requests" in schema["required"]
            return dict(action="answer_fact",target_item="i1",target_change="none",fact="time",minutes=0,
                        choices=[],reads=[read("time")],social="바쁜 날이셨군요.",
                        general_requests=[dict(question="편한 책 하나 권해줘",answer="짧은 에세이를 권해요. 잠깐씩 읽기 좋아요.")])
    d=du.decide(Chat(),stops=du.stops_of([a]),changes=[],history=[],selected_item_id=None,
                message="바빴어. 편한 책 하나 권해줘. 전시관은 언제 가?")
    result,_,focus=read_requests.reply(d,items=[a],message="전시관은 언제 가?",selected=None,turns=[],version=1,
                                      now=NOW,context_now=NOW,ttl_seconds=1800,place_source=None)
    assert "짧은 에세이" in result["text"] and a.title in result["text"]
    assert focus["item_id"]==str(a.item_id) and d.action=="answer_fact"


@pytest.mark.parametrize("general", [[{"question":"책 추천","answer":""}], {"answer":"책"},
                                    [{"question":"책 추천","answer":"책","action":"apply_change"}]])
def test_general_request_cannot_smuggle_actions_or_omit_the_answer(general):
    class Chat:
        def structured(self,*args,**kwargs):
            return dict(action="other",target_item="none",target_change="none",fact="none",minutes=0,
                        choices=[],reads=[],social="",general_requests=general)
    with pytest.raises(du.DecisionFailed):
        du.decide(Chat(),stops=[],changes=[],history=[],selected_item_id=None,message="책 추천")


def _decide_general(general, social=""):
    class Chat:
        def structured(self,*args,**kwargs):
            return dict(action="other",target_item="none",target_change="none",fact="none",minutes=0,
                        choices=[],reads=[],social=social,general_requests=general)
    return du.decide(Chat(),stops=[],changes=[],history=[],selected_item_id=None,message="추천해줘")


def test_general_answers_carry_one_fixed_note_that_they_are_not_trip_data():
    d=_decide_general([dict(question="조용한 곳 추천",answer="일정이 빡빡하셨다니 조용한 정원을 권해요."),
                       dict(question="책 추천",answer="짧은 에세이를 권해요.")],social="수고하셨어요.")
    assert d.social.count(du.GENERAL_NOTE) == 1 and d.social.endswith(du.GENERAL_NOTE)
    assert d.social.startswith("수고하셨어요.") and "짧은 에세이" in d.social


def test_note_is_not_added_without_a_general_request():
    d=_decide_general([],social="수고하셨어요.")
    assert d.social == "수고하셨어요." and du.GENERAL_NOTE not in d.social


def test_prompt_routes_out_of_itinerary_history_to_evidence_and_limits_recommendation_reasons():
    assert "action=ask_policy" in du.SYSTEM and "일정 목록에 없는 장소" in du.SYSTEM
    assert "이 프롬프트에 실제로 있는 근거만" in du.SYSTEM and "취향을 기억하거나 저장한다고 말하지 않는다" in du.SYSTEM


def test_unfound_place_history_is_reported_as_not_found_instead_of_answered_from_memory():
    from app.domains.travel_ops.components.conversation import trip_replies
    seen=[]
    def search(**kwargs):
        seen.append(kwargs)
        return []
    status,text,evidence=trip_replies.question_reply(
        message="이 옛 성터는 언제 누가 세웠어?",items=[item("솔빛전시관",1)],tenant_id="t",policy_search=search,
        scopes=list(trip_replies.QUESTION_SCOPES),min_score=0.5,now=NOW)
    assert seen and status=="answered" and "지어내 답하지 않았어요" in text
    assert evidence["policy_hits"]==0 and evidence["unmatched"] is True

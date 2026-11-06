# -*- coding: utf-8 -*-
"""고객이 알려 주는 운영시간 — 확인 화면에서 운영시간을 못 찾은 곳에 고객이 넣은 값. `[2026-10-13 사용자 결정]`

★지키는 것: ① 모양이 맞는 값만 받는다 ② 관광공사 · 원장 · 장소 행 값이 있으면 그것이 이긴다(고객 값은 모를 때만)
  ③ 고객 값으로 낸 확인 줄은 「✓ 통과」가 아니라 「✎ 채움」이고 출처를 밝힌다 ④ 등록 뒤 판정은 장소 행이 아니라 그 일정 항목에 실린 값을 본다
  (공용 장소 행에 넣으면 다른 고객의 같은 장소에 섞인다).

DB 없이 도는 시험이다. 재현:

    python -m pytest tests/unit/travel/test_intake_customer_hours.py -v
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake import assemble, hours, pipeline, review
from app.domains.travel_ops.components.itinerary.itinerary_checks import Part, check_itinerary

KST = ZoneInfo("Asia/Seoul")
TOLD = {"open": "10:00", "close": "19:00", "closed_days": ["sun"]}
KAKAO = {"name": "통인시장", "source": "kakao", "latitude": 37.5809, "longitude": 126.9696}     # 카카오 값 — 운영시간이 없다(DB 를 묻지 않는다)


class _Conn:
    """DB 대역 — 활동 원장 단계가 세이브포인트(`conn.transaction()`)만 연다. 장소 번호가 없으니 원장은 묻지 않는다."""

    def transaction(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


CONN = _Conn()


def at(day: int, hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime(2026, 10, day, int(h), int(m), tzinfo=KST)          # 2026-10-15 목요일 · 10-18 일요일


# ── 받는 모양 ─────────────────────────────────────────────────────
def test_the_told_hours_are_checked_and_stored_in_week_order():
    value, evidence, note = pipeline._checked("items[0].hours", {"open": "10:00", "close": "24:00", "closed_days": ["sun", "mon"]})
    assert value == {"open": "10:00", "close": "24:00", "closed_days": ["mon", "sun"]}
    assert evidence == {"source": "customer"} and note == "고객이 알려 준 운영시간"
    assert pipeline._checked("items[0].hours", {"open": "09:30", "close": "18:00"})[0]["closed_days"] == []
    cleared, evidence, _ = pipeline._checked("items[0].hours", None)
    assert cleared is None and evidence["cleared"] is True


@pytest.mark.parametrize("bad", [
    "10:00-19:00", {"open": "10:00"}, {"open": "10:00", "close": "19:00", "extra": 1}, {"open": "9:00", "close": "19:00"},
    {"open": "10:00", "close": "25:00"}, {"open": "19:00", "close": "10:00"}, {"open": "10:00", "close": "10:00"},
    {"open": "24:00", "close": "24:00"}, {"open": "10:00", "close": "19:00", "closed_days": ["일"]},
    {"open": "10:00", "close": "19:00", "closed_days": ["sun", "sun"]}, {"open": "10:00", "close": "19:00", "closed_days": "sun"},
    {"open": "10:00", "close": "19:00", "closed_days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]},
])
def test_a_wrong_shape_is_refused(bad):
    with pytest.raises(pipeline.IntakeRejected) as caught:
        pipeline._checked("items[0].hours", bad)
    assert caught.value.code == "invalid_value"


def test_the_told_hours_become_a_full_week_table():
    week = hours.customer_week(TOLD)
    assert week["sun"] == "closed" and week["thu"] == {"open": "10:00", "close": "19:00", "last_entry": None} and len(week) == 7
    assert hours.customer_week(None) is None and hours.customer_week({"open": "10:00"}) is None


# ── 다른 출처가 이긴다 ────────────────────────────────────────────
def test_the_told_hours_are_used_only_when_no_other_source_knows():
    told = hours.facts_for(CONN, "t", KAKAO, "activity", at(15, "12:30"), at(15, "13:30"), customer=TOLD)
    assert told.known and told.source == "customer" and told.why_unknown is None
    assert told.attributes["hours_week"]["sun"] == "closed"
    official = {**KAKAO, "_hours": {"hours_week": {"thu": {"open": "09:00", "close": "18:00"}}}}
    kept = hours.facts_for(CONN, "t", official, "activity", at(15, "12:30"), at(15, "13:30"), customer=TOLD)
    assert kept.source == "tour_api" and kept.attributes["hours_week"] == {"thu": {"open": "09:00", "close": "18:00"}}
    assert hours.facts_for(CONN, "t", KAKAO, "activity", at(15, "12:30"), None).known is False        # 알려 주지 않으면 그대로 모른다


# ── 확인 줄 ───────────────────────────────────────────────────────
def lines_for(day: int, start: str, end: str):
    row = {"date": f"2026-10-{day}", "start": start, "end": end, "place": KAKAO}
    facts = hours.facts_for(CONN, "t", KAKAO, "activity", at(day, start), at(day, end), customer=TOLD)
    found = check_itinerary([Part(seq=1, kind="activity", title="통인시장", starts_at=at(day, start), ends_at=at(day, end),
                                  place={"name": "통인시장", "attributes": dict(facts.attributes)})])
    got = review._hours_lines(row, facts, found)
    return tuple(review._told(line) for line in got)


def test_a_line_from_the_told_hours_is_filled_not_passed_and_says_where_it_came_from():
    hours_line, closed_line = lines_for(15, "12:30", "13:30")
    assert hours_line == {"row": "hours", "result": "filled", "text": "10:00–19:00 안에 머물러요 · 알려 주신 시간 기준"}
    assert closed_line["result"] == "filled" and closed_line["text"].startswith("일요일 휴무") and closed_line["text"].endswith("알려 주신 시간 기준")


def test_a_problem_under_the_told_hours_still_needs_a_look():
    early, _ = lines_for(15, "09:00", "10:30")
    assert early["result"] == "warn" and "10:00에 열어요" in early["text"]
    _, sunday = lines_for(18, "12:30", "13:30")
    assert sunday["result"] == "bad" and "쉬는 날" in sunday["text"]


# ── 등록 뒤 판정 ──────────────────────────────────────────────────
def test_the_registered_check_reads_the_told_hours_from_the_item_only_when_the_place_has_none():
    detail = {"customer_hours": {"hours_week": hours.customer_week(TOLD), "told": TOLD}}
    sunday = Part(seq=1, kind="activity", title="통인시장", starts_at=at(18, "12:30"), ends_at=at(18, "13:30"),
                  place={"name": "통인시장", "attributes": {}}, detail=detail)
    assert [v.code for v in check_itinerary([sunday])] == ["closed_day"]
    known = Part(seq=1, kind="activity", title="통인시장", starts_at=at(18, "12:30"), ends_at=at(18, "13:30"),
                 place={"name": "통인시장", "attributes": {"hours_week": {"sun": {"open": "09:00", "close": "18:00"}}}}, detail=detail)
    assert check_itinerary([known]) == []                                  # 장소 값이 이긴다
    assert check_itinerary([Part(seq=1, kind="activity", title="통인시장", starts_at=at(18, "12:30"), ends_at=at(18, "13:30"),
                                 place={"name": "통인시장", "attributes": {}})]) == []          # 알려 준 값이 없으면 그대로 모른다


def _claim(field, value, method="customer"):
    return {"source_id": "s1", "field": field, "value": value, "method": method, "evidence": {"line": 1}, "needs_review": False, "note": None}


def test_the_registration_body_carries_the_told_hours_on_the_item_not_on_the_place():
    place = {**KAKAO}
    claims = [_claim("trip.first_day", "2026-10-15", "rule"), _claim("items[0].title", "통인시장", "rule"),
              _claim("items[0].date", "2026-10-15", "rule"), _claim("items[0].starts_at", "12:30", "rule"),
              _claim("items[0].ends_at", "13:30", "rule"), _claim("items[0].place", place, "rule"),
              _claim("items[0].hours", TOLD)]
    built = assemble.assemble(intake_id="i1", revision=2, sources=[{"source_id": "s1", "position": 0, "transcript": "12시 반 통인시장"}],
                              claims=claims)
    item = built.body["items"][0]
    assert item["detail"]["customer_hours"] == {"hours_week": hours.customer_week(TOLD), "told": TOLD}
    assert "hours_week" not in built.body["places"][0]["attributes"]
    cleared = assemble.assemble(intake_id="i1", revision=3, sources=[{"source_id": "s1", "position": 0, "transcript": "12시 반 통인시장"}],
                                claims=claims + [_claim("items[0].hours", None)])
    assert "customer_hours" not in cleared.body["items"][0]["detail"]


def test_review_emits_customer_hours_and_customer_provenance(monkeypatch):
    monkeypatch.setattr(review, "_fixed_neighbours", lambda *a: [])
    claims = [_claim("trip.first_day", "2026-10-15", "rule"), _claim("items[0].title", "통인시장", "rule"),
              _claim("items[0].date", "2026-10-15", "rule"), _claim("items[0].starts_at", "12:30", "rule"),
              _claim("items[0].ends_at", "13:30", "rule"), _claim("items[0].place", KAKAO, "rule"),
              _claim("items[0].hours", TOLD)]
    events = []
    result = review.build(CONN, tenant_id="t", intake_id="i", revision=2,
                          sources=[{"source_id": "s1", "position": 0, "transcript": "12시 반 통인시장"}],
                          claims=claims, use_engine=False, on_event=lambda n, b: events.append((n,b)))
    row = result["items"][0]
    assert row["hours_state"] == "customer" and row["customer_hours"] == TOLD
    assert next(x for x in row["rows"] if x["row"] == "hours")["result"] == "filled"
    assert next(b for n,b in events if n == "item")["customer_hours"] == TOLD


def test_trip_view_isolated_and_replacement_clears_customer_hours():
    from uuid import uuid4
    from app.domains.travel_ops.components.itinerary import itinerary as it
    from app.domains.travel_ops.components.watch import dawn_check
    place_id = uuid4()
    place = {"place_id": str(place_id), "name": "통인시장", "attributes": {}}
    detail = {"customer_hours": {"hours_week": hours.customer_week(TOLD), "told": TOLD}}
    view = it.with_told_hours(place, detail)
    assert place["attributes"] == {}
    assert it.with_told_hours(place, {})["attributes"] == {}
    stop = it.Item(uuid4(), 1, "activity", "통인시장", place_id, at(18,"12:30"), at(18,"13:30"), detail=detail, place=view)
    assert dawn_check.told_verdict(stop)[0] == "closed"
    other = stop.replaced_by(place={"place_id":str(uuid4()),"name":"다른 곳","attributes":{}},title="다른 곳")
    assert "customer_hours" not in other.detail
    assert stop.detail == detail
    assert stop.replaced_by(place=None,title="통인시장").detail == detail


@pytest.mark.parametrize("state, expected_source", [("unknown", "customer_hours"), ("open", "google_places")])
def test_dawn_unknown_uses_customer_but_google_open_wins(state, expected_source):
    from uuid import uuid4
    from app.domains.travel_ops.components.itinerary.itinerary import Item, with_told_hours
    from app.domains.travel_ops.components.watch.dawn_check import DawnCheck, DawnResult, PROVIDER
    detail = {"customer_hours": {"hours_week": hours.customer_week(TOLD), "told": TOLD}}
    place = with_told_hours({"place_id": str(uuid4()), "name": "통인시장", "attributes": {}}, detail)
    stop = Item(uuid4(),1,"activity","통인시장",None,at(15,"12:30"),at(15,"13:30"),detail=detail,place=place)
    checker = object.__new__(DawnCheck)
    records = []
    checker._record = lambda *a, **kw: records.append((a,kw))
    result = DawnResult()
    checker._apply_verdict(uuid4(),stop,at(15,"12:30").date(),[],result,state,"provider result")
    assert result.open == 1 and not result.unknown
    assert records[0][1]["source"] == (PROVIDER if state == "open" else expected_source)


def test_place_edit_clears_only_its_customer_hours():
    claims = [_claim("items[0].hours",TOLD), {**_claim("items[0].hours",TOLD),"source_id":"s2"}]
    rows = [("s1","items[0].place",None,{},None)]
    pipeline._clear_hours_on_place_change(rows, claims)
    assert rows[-1][0:3] == ("s1","items[0].hours",None)
    assert len(rows) == 2
    explicit = [("s1","items[0].place",None,{},None),("s1","items[0].hours",TOLD,{},None)]
    pipeline._clear_hours_on_place_change(explicit,claims)
    assert len(explicit) == 2 and explicit[-1][2] == TOLD


def test_customer_provenance_in_chat_answer():
    from app.domains.travel_ops.components.conversation.trip_facts import _stored_hours
    from app.domains.travel_ops.components.itinerary.itinerary import with_told_hours
    view = with_told_hours({"name":"통인시장","attributes":{}}, {"customer_hours":{"hours_week":hours.customer_week(TOLD),"told":TOLD}})
    assert "알려 주신 운영시간" in _stored_hours(view, at(15,"12:30").date())


def test_registered_row_conversion_is_per_item():
    from uuid import uuid4
    from app.domains.travel_ops.components.itinerary.itinerary import _item_of
    pid = uuid4()
    place = (pid,"통인시장","activity",37.58,126.97,False,{})
    detail={"customer_hours":{"hours_week":hours.customer_week(TOLD),"told":TOLD}}
    row = (uuid4(),1,"activity","통인시장",pid,at(15,"12:30"),at(15,"13:30"),False,None,None,detail)
    assert _item_of(row+place).place["attributes"]["hours_read"]["source"] == "customer"
    assert _item_of((*row[:10],{})+place).place["attributes"] == {}


def test_schedule_reflow_respects_told_closing_time():
    from .test_intake_direct_schedule import row, walk11
    from app.domains.travel_ops.components.intake.direct_schedule import fit, ScheduleConflict
    rows = [row(0,"09:00","10:00",locked=True), row(1,"10:05","11:05",customer_hours={"open":"09:00","close":"11:05","closed_days":[]})]
    with pytest.raises(ScheduleConflict):
        fit(CONN,tenant_id="t",rows=rows,touched={("source",0)},engine=walk11,use_engine=False,forward_only=True)


def test_unmatched_google_can_use_customer_hours():
    from uuid import uuid4
    from types import SimpleNamespace
    from app.domains.travel_ops.components.itinerary.itinerary import Item, with_told_hours
    from app.domains.travel_ops.components.watch.dawn_check import DawnCheck, DawnResult
    detail={"customer_hours":{"hours_week":hours.customer_week(TOLD),"told":TOLD}}
    view=with_told_hours({"place_id":str(uuid4()),"name":"통인시장","latitude":37.58,"longitude":126.97,"attributes":{}},detail)
    item=Item(uuid4(),1,"activity","통인시장",None,at(15,"12:30"),at(15,"13:30"),detail=detail,place=view)
    checker=object.__new__(DawnCheck)
    checker.place_status=None; checker._connect=lambda:CONN; checker._provider_id=lambda *a:None
    checker.source=SimpleNamespace(find_place_id=lambda **kw:"unmatched")
    records=[]; checker._record=lambda *a,**kw:records.append((a,kw))
    result=DawnResult(); checker._check(uuid4(),item,at(15,"12:30").date(),[],result)
    assert result.open==1 and not result.unmatched
    assert records[0][1]["source"]=="customer_hours"


@pytest.mark.parametrize("official", ["tour", "activity", "dining"])
def test_all_official_sources_take_precedence(monkeypatch, official):
    place=dict(KAKAO)
    if official == "tour": place["_hours"]={"hours_week":{"thu":{"open":"09:00","close":"18:00"}}}
    if official == "activity":
        monkeypatch.setattr(hours,"_apply_activity_ledger", lambda conn,tenant,core,content,start,end,out: (setattr(out,"known",True),setattr(out,"source","activity_ledger")))
    if official == "dining":
        monkeypatch.setattr(hours,"_apply_ledger_by_uid",lambda conn,content,place,start,end,out:(setattr(out,"known",True),setattr(out,"source","dining_ledger")))
    facts=hours.facts_for(CONN,"t",place,"dining" if official=="dining" else "activity",at(15,"12:30"),at(15,"13:30"),customer=TOLD)
    assert facts.source!="customer" and facts.known


def test_edit_persists_hours_with_customer_scope_and_check_false(monkeypatch):
    import json
    from .test_web_taxi_pricing_v1 import RecordingConnection
    conn=RecordingConnection()
    monkeypatch.setattr(pipeline,"_sources",lambda *a:[{"source_id":"s1","position":0,"transcript":"통인시장"}])
    monkeypatch.setattr(pipeline,"_claims",lambda *a:[_claim("items[0].title","통인시장")])
    monkeypatch.setattr(pipeline,"_review_of",lambda *a,**kw:({},None))
    assert pipeline.edit(conn,tenant_id="tenant-a",customer_id="customer-a",intake_id="i",revision=3,
                         edits=[{"source_id":"s1","field":"items[0].hours","value":TOLD}],check=False)==4
    writes=[params for sql,params in conn.calls if "VALUES" in sql]
    assert json.loads(writes[0][5])==TOLD
    assert "customer_id=%s" in conn.calls[0][0] and conn.calls[0][1]==("tenant-a","i","customer-a")
    assert not any("UPDATE places" in sql or "INSERT INTO places" in sql for sql,_ in conn.calls)


def test_trip_place_information_labels_customer_source(monkeypatch):
    from app.domains.travel_ops.components.places import place_info as pi
    from app.domains.travel_ops.components.itinerary.itinerary import with_told_hours
    monkeypatch.setattr(pi,"_ledger_uid",lambda *a:None)
    monkeypatch.setattr(pi,"_catalog_row",lambda *a:None)
    view=with_told_hours({"name":"통인시장","attributes":{}},{"customer_hours":{"hours_week":hours.customer_week(TOLD),"told":TOLD}})
    assert "알려 주신" in pi.place_info(CONN,"t",view)["source_note"]


def test_official_dining_verdict_without_clock_beats_customer_week():
    detail={"customer_hours":{"hours_week":hours.customer_week(TOLD),"told":TOLD}}
    part=Part(seq=1,kind="dining",title="식당",starts_at=at(18,"12:30"),ends_at=at(18,"13:30"),
              place={"attributes":{},"ledger":{"open_at_slot":True}},detail=detail)
    assert check_itinerary([part]) == []


def test_dining_source_verdict_is_official_even_without_clock(monkeypatch):
    monkeypatch.setattr(hours,"_apply_ledger_by_uid",lambda conn,content,place,start,end,out: hours._merge_state({"open_at_slot":True},start,out))
    facts=hours.facts_for(CONN,"t",KAKAO,"dining",at(18,"12:30"),at(18,"13:30"),customer=TOLD)
    assert facts.known and facts.source == "dining_ledger"


def test_registered_trip_reopen_preserves_and_edits_hours():
    from uuid import uuid4
    from app.domains.travel_ops.components.itinerary.itinerary import Item
    from app.domains.travel_ops.components.intake import reopen
    pid=uuid4()
    detail={"customer_hours":{"hours_week":hours.customer_week(TOLD),"told":TOLD}}
    origin=Item(uuid4(),1,"activity","통인시장",pid,at(15,"12:30"),at(15,"13:30"),detail=detail,
                place={"place_id":str(pid),**KAKAO,"attributes":{}})
    claims=[_claim(f,v,"trip") for f,v,e in reopen._claims_for(0,origin,{})]
    assert next(c["value"] for c in claims if c["field"]=="items[0].hours")==TOLD
    for new in ({"open":"09:00","close":"20:00","closed_days":[]},None):
        got=assemble.collect(sources=[{"source_id":"s1","position":0,"transcript":"통인시장"}],claims=claims+[_claim("items[0].hours",new)])
        plan=reopen.plan_edit(rows=got.rows,origin_of={("s1",0):origin.item_id},base_items=[origin],frozen_ids=set(),intake_id="i",revision=4,now=at(15,"08:00"))
        assert plan.items[0].item_id != origin.item_id
        if new is None: assert "customer_hours" not in plan.items[0].detail
        else: assert plan.items[0].detail["customer_hours"]["told"]==new


@pytest.mark.parametrize("bad", [
    {"open":"10:00","close":"09:00"},
    {"open":"10:00","close":"19:00","closed_days":["sun","sun"]},
    {"open":"10:00","close":"19:00","closed_days":["mon","tue","wed","thu","fri","sat","sun"]},
    {"open":"24:00","close":"24:00"},
])
def test_actual_edit_endpoint_returns_422_without_writes(monkeypatch,bad):
    from contextlib import nullcontext
    from uuid import uuid4
    from fastapi import BackgroundTasks, HTTPException
    from app.domains.travel_ops.entry import trip_api
    from .test_web_taxi_pricing_v1 import RecordingConnection
    conn=RecordingConnection()
    monkeypatch.setattr(trip_api,"get_connection",lambda:nullcontext(conn))
    monkeypatch.setattr(pipeline,"_sources",lambda *a:[{"source_id":"s1","position":0,"transcript":"통인시장"}])
    monkeypatch.setattr(pipeline,"_claims",lambda *a:[_claim("items[0].title","통인시장")])
    router=trip_api.build_trip_router()
    endpoint=next(r.endpoint for r in router.routes if r.path=="/v1/web/trip-intakes/{intake_id}/edits")
    req=trip_api.IntakeEditIn(revision=3,edits=[{"source_id":"s1","field":"items[0].hours","value":bad}],check=False)
    with pytest.raises(HTTPException) as caught:
        endpoint(uuid4(),req,BackgroundTasks(),("tenant-a",uuid4()))
    assert caught.value.status_code==422
    assert caught.value.detail["error"]["code"]=="invalid_value"
    assert not any(sql.startswith(("INSERT","UPDATE")) for sql,_ in conn.calls)

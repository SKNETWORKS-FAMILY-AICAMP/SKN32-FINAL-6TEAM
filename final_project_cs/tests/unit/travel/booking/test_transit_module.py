# -*- coding: utf-8 -*-
"""예약 모듈 — 기차 · 버스(`[2026-10-14]` TAGO). 규칙 해석(교통수단 · 역 · 등급) → booking 모듈(역 · 터미널 옮기기 · 운행 합치기) → 답. 어댑터는 가짜다."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.contracts import ContextPack, TeamTask, ToolNotAllowed
from app.domains.travel_ops.components.booking.offers import search_transit
from app.domains.travel_ops.components.booking.offers.transit import STATIONS
from app.domains.travel_ops.instances.booking import BookingTeam
from app.domains.travel_ops.instances.booking.interpret import needs, parse
from app.domains.travel_ops.instances.booking.interpret_rules import interpret
from app.domains.travel_ops.ports.data_sources.tago_transit import TagoTransit

TODAY = datetime.now(ZoneInfo("Asia/Seoul")).date()
_NEXT = (TODAY.replace(day=1) + timedelta(days=32)).replace(day=1)
GO, BACK = _NEXT.replace(day=6), _NEXT.replace(day=9)
STAMP = GO.strftime("%Y%m%d")


def _rules(text):
    found = parse(interpret(text, today=TODAY))
    return found, needs(found, today=TODAY)


# ── 규칙 해석 ─────────────────────────────────────────────
@pytest.mark.parametrize("text,mode,origin,destination,grade,kind", [
    ("11월 6일 서울에서 부산 가는 KTX 2명 오전 출발", "train", "서울", "부산", "KTX", None),
    ("내일 동대구역에서 서울역 기차 혼자", "train", "동대구", "서울", None, None),
    ("다음 달 3일 서울에서 강릉 고속버스 3명", "bus", "서울", "강릉", None, "express"),
    ("서울 광주 시외버스 내일 우등 2명", "bus", "서울", "광주", "우등", "suburbs"),
    ("비행기 말고 기차로 부산 가고 싶어 11월 6일 2명", "train", None, "부산", None, None),
    ("기차 말고 비행기 김포 제주 내일 1명", "flight", "GMP", "CJU", None, None),
    ("11월 6일 인천에서 나리타 가는 편도 2명", "flight", "ICN", "NRT", None, None),
    ("대구에서 광주 가는 열차 11월 6일 2명", "train", "대구", "광주", None, None),   # 말한 이름 그대로 — 동대구 · 광주송정으로 옮기는 것은 booking 모듈
])
def test_the_rules_read_the_transport_mode_and_station_names(text, mode, origin, destination, grade, kind):
    found, _ = _rules(text)
    assert (found.mode, found.origin, found.destination, found.grade, found.kind) == (mode, origin, destination, grade, kind)
    if mode != "flight":
        assert found.domestic is True and found.cabin is None and found.direct_only is None


def test_a_train_sentence_without_a_station_is_asked_back_not_guessed():
    found, missing = _rules("비행기 말고 기차로 부산 가고 싶어 11월 6일 2명")
    assert found.mode == "train" and missing == ["origin"]


def test_every_station_in_the_dictionary_maps_to_a_name_and_a_region():
    assert all(isinstance(name, str) and isinstance(city, str) and name and city for name, city in STATIONS.values())
    assert STATIONS["대구"] == ("동대구", "대구") and STATIONS["광주"] == ("광주송정", "광주") and STATIONS["청주"] == ("오송", "충북")


# ── 어댑터 ─────────────────────────────────────────────
class _Response:
    status_code = 200

    def __init__(self, payload):
        self._payload, self.text = payload, ""

    def json(self):
        return self._payload


def _payload(items):
    return {"response": {"header": {"resultCode": "00", "resultMsg": "OK"},
                         "body": {"items": {"item": items} if items else "", "numOfRows": 300, "pageNo": 1, "totalCount": len(items)}}}


def test_the_adapter_uses_the_2026_03_addresses_and_normalises_rows():
    """★주소는 `…/1613000/TrainInfo/GetStrtpntAlocFndTrainInfo`(2026-03 개편 — 옛 `TrainInfoService/get…` 은 NO_OPENAPI_SERVICE)."""
    urls = []

    def transport(url, params):
        urls.append((url, dict(params)))
        if url.endswith("/TrainInfo/GetCtyCodeList"):
            return _Response(_payload([{"citycode": 11, "cityname": "서울특별시"}, {"citycode": 26, "cityname": "부산광역시"}]))
        if url.endswith("/TrainInfo/GetCtyAcctoTrainSttnList"):
            code = params["cityCode"]
            return _Response(_payload([{"nodeid": "NAT010000", "nodename": "서울"}, {"nodeid": "NAT010032", "nodename": "영등포"}]
                                      if code == "11" else [{"nodeid": "NAT014445", "nodename": "부산"}]))
        if url.endswith("/TrainInfo/GetStrtpntAlocFndTrainInfo"):
            return _Response(_payload([
                {"adultcharge": 59800, "arrplacename": "부산", "arrplandtime": int(f"{STAMP}0940"), "depplacename": "서울",
                 "depplandtime": int(f"{STAMP}0700"), "traingradename": "KTX", "trainno": 101},
                {"adultcharge": 28600, "arrplacename": "부산", "arrplandtime": f"{STAMP}1330", "depplacename": "서울",
                 "depplandtime": f"{STAMP}0800", "traingradename": "무궁화호", "trainno": 1201}]))
        if url.endswith("/ExpBusInfo/GetExpBusTrminlList"):
            return _Response(_payload([{"terminalId": "NAEK010", "terminalNm": "서울경부"}, {"terminalId": "NAEK011", "terminalNm": "서울호남"},
                                       {"terminalId": "NAEK700", "terminalNm": "부산"}]))
        if url.endswith("/ExpBusInfo/GetStrtpntAlocFndExpbusInfo"):
            if params["depTerminalId"] == "NAEK010":
                return _Response(_payload([{"arrPlaceNm": "부산", "arrPlandTime": f"{STAMP}1030", "charge": 26600, "depPlaceNm": "서울경부",
                                            "depPlandTime": f"{STAMP}0600", "gradeNm": "우등", "routeId": "R1"}]))
            return _Response(_payload([]))
        raise AssertionError(url)

    source = TagoTransit(service_key="k", transport=transport)
    stations = source.train_stations("서울")
    assert stations == [{"id": "NAT010000", "name": "서울"}, {"id": "NAT010032", "name": "영등포"}]
    rows = source.train_schedules(dep_id="NAT010000", arr_id="NAT014445", date=GO.isoformat())
    assert [(r["grade"], r["number"], r["depart"], r["arrive"], r["minutes"], r["price"], r["date"]) for r in rows] == [
        ("KTX", "101", "07:00", "09:40", 160, 59800, GO.isoformat()), ("무궁화호", "1201", "08:00", "13:30", 330, 28600, GO.isoformat())]
    assert source.bus_terminals("express", "서울") == [{"id": "NAEK010", "name": "서울경부"}, {"id": "NAEK011", "name": "서울호남"}]
    bus = source.bus_schedules("express", dep_id="NAEK010", arr_id="NAEK700", date=GO.isoformat())
    assert bus[0]["kind"] == "express" and bus[0]["grade"] == "우등" and bus[0]["price"] == 26600 and bus[0]["minutes"] == 270
    assert all(("Service" not in url and "/Get" in url) for url, _ in urls), "2026-03 개편 주소 — Service 없음 · 동작 대문자"
    assert all(params["serviceKey"] == "k" and params["_type"] == "json" for _, params in urls)
    sent = [params for url, params in urls if url.endswith("GetStrtpntAlocFndTrainInfo")][0]
    assert sent["depPlandTime"] == STAMP and sent["depPlaceId"] == "NAT010000"


# ── booking 모듈 ─────────────────────────────────────────────
class FakeTago:
    """어댑터 대신 — 역 · 터미널 · 운행을 정해 둔 값으로. 부른 것을 남긴다."""

    def __init__(self, *, trains=None, express=None, suburbs=None, stations=None, terminals=None):
        self.calls = []
        self.trains, self.express, self.suburbs = trains or [], express, suburbs
        self.stations = stations or {"서울": [{"id": "S1", "name": "서울"}, {"id": "S2", "name": "영등포"}],
                                     "부산": [{"id": "B1", "name": "부산"}], "울산": [{"id": "U1", "name": "울산(통도사)"}]}
        self.terminals = terminals or {"서울": [{"id": "T1", "name": "서울경부"}, {"id": "T2", "name": "서울호남"}, {"id": "T3", "name": "동서울"},
                                               {"id": "T4", "name": "서울남부"}],
                                       "부산": [{"id": "T7", "name": "부산"}, {"id": "T8", "name": "부산사상"}], "강릉": [{"id": "T9", "name": "강릉"}]}

    def train_stations(self, city):
        self.calls.append(("train_stations", city))
        return self.stations.get(city)

    def train_schedules(self, *, dep_id, arr_id, date):
        self.calls.append(("train_schedules", dep_id, arr_id, date))
        return self.trains

    def bus_terminals(self, kind, keyword):
        self.calls.append(("bus_terminals", kind, keyword))
        return self.terminals.get(keyword, [])

    def bus_schedules(self, kind, *, dep_id, arr_id, date):
        self.calls.append(("bus_schedules", kind, dep_id, arr_id, date))
        table = self.express if kind == "express" else self.suburbs
        if table is None:
            return None
        return list(table.get((dep_id, arr_id), []))


def _train(grade, depart, arrive, price, number="101"):
    return {"mode": "train", "kind": None, "grade": grade, "number": number, "origin": "서울", "destination": "부산",
            "date": GO.isoformat(), "depart": depart, "arrive": arrive, "minutes": 160, "price": price}


def _bus(kind, dep, arr, depart, price, grade="우등"):
    return {"mode": "bus", "kind": kind, "grade": grade, "number": "R", "origin": dep, "destination": arr,
            "date": GO.isoformat(), "depart": depart, "arrive": None, "minutes": None, "price": price}


def test_train_search_turns_names_into_stations_and_sorts_by_departure():
    tago = FakeTago(trains=[_train("무궁화호", "08:00", "13:30", 28600), _train("KTX", "07:00", "09:40", 59800)])
    got = search_transit(SimpleNamespace(transit_schedule=tago), mode="train", origin="서울", destination="울산", depart_date=GO.isoformat(), adults=2)
    assert tago.calls == [("train_stations", "서울"), ("train_stations", "울산"), ("train_schedules", "S1", "U1", GO.isoformat())]
    assert got["resolved"] == {"origin": "서울", "destination": "울산(통도사)"}, "「울산」 → 역 목록에서 「울산(통도사)」(앞머리 일치)"
    assert [option["depart"] for option in got["options"]] == ["07:00", "08:00"]
    assert got["sources"]["tago"]["status"] == "ok" and got["sources"]["tago"]["count"] == 2
    assert [site["name"] for site in got["elsewhere"]] == ["코레일 승차권 예매(KTX · ITX · 무궁화)", "SRT 예매"]


def test_an_unknown_station_name_is_reported_not_guessed():
    tago = FakeTago()
    got = search_transit(SimpleNamespace(transit_schedule=tago), mode="train", origin="서울", destination="화성", depart_date=GO.isoformat())
    assert got["sources"]["tago"] == {"status": "unresolved", "count": 0, "calls": ["train_stations:서울"], "seconds": got["sources"]["tago"]["seconds"],
                                      "unresolved": ["화성"]}
    assert got["options"] == [] and all(call[0] != "train_schedules" for call in tago.calls)


def test_bus_search_asks_every_matching_terminal_pair_express_first_and_suburbs_only_when_needed():
    express = {("T1", "T7"): [_bus("express", "서울경부", "부산", "06:00", 26600)], ("T4", "T8"): [_bus("express", "서울남부", "부산사상", "07:10", 24000)]}
    tago = FakeTago(express=express, suburbs={})
    got = search_transit(SimpleNamespace(transit_schedule=tago), mode="bus", origin="서울", destination="부산", depart_date=GO.isoformat())
    pairs = [(c[2], c[3]) for c in tago.calls if c[0] == "bus_schedules"]
    assert pairs == [("T1", "T7"), ("T1", "T8"), ("T2", "T7"), ("T2", "T8"), ("T4", "T7"), ("T4", "T8")], \
        "「서울」로 시작하는 터미널 3곳(TERMINALS_EACH — 동서울은 뒤로) × 도착 2곳"
    assert all(c[1] == "express" for c in tago.calls if c[0] == "bus_schedules"), "고속에 결과가 있으면 시외는 안 본다"
    assert got["resolved"] == {"origin": "서울경부 · 서울남부", "destination": "부산 · 부산사상"}
    assert [option["depart"] for option in got["options"]] == ["06:00", "07:10"]
    assert [site["name"] for site in got["elsewhere"]] == ["코버스 고속버스 예매"]

    tago = FakeTago(express={}, suburbs={("T4", "T9"): [_bus("suburbs", "서울남부", "강릉", "09:00", 15000)]},
                    terminals={"서울": [{"id": "T4", "name": "서울남부"}], "강릉": [{"id": "T9", "name": "강릉"}]})
    got = search_transit(SimpleNamespace(transit_schedule=tago), mode="bus", origin="서울", destination="강릉", depart_date=GO.isoformat())
    kinds = [c[1] for c in tago.calls if c[0] == "bus_schedules"]
    assert kinds == ["express", "suburbs"] and got["options"][0]["kind"] == "suburbs"
    assert [site["name"] for site in got["elsewhere"]] == ["버스타고 시외버스 예매", "티머니 시외버스 예매"]


def test_a_requested_bus_kind_skips_the_other_and_a_missing_source_is_failed():
    tago = FakeTago(express={}, suburbs={})
    search_transit(SimpleNamespace(transit_schedule=tago), mode="bus", origin="서울", destination="부산", depart_date=GO.isoformat(), kind="suburbs")
    assert {c[1] for c in tago.calls if c[0] in ("bus_terminals", "bus_schedules")} == {"suburbs"}
    got = search_transit(SimpleNamespace(transit_schedule=None), mode="train", origin="서울", destination="부산", depart_date=GO.isoformat())
    assert got["sources"]["tago"]["status"] == "failed" and got["options"] == []


# ── 팀(답) ─────────────────────────────────────────────
class FakeTools:
    def __init__(self, tago):
        self.calls, self.travel = [], SimpleNamespace(transit_schedule=tago)

    def call(self, name, context, arguments, allowed_tools, seen, budget=None):
        if name not in allowed_tools:
            raise ToolNotAllowed(name)
        seen.add(name + repr(sorted(arguments.items())))
        self.calls.append((name, dict(arguments)))
        assert name == "read.booking_search_transit", "기차 · 버스는 항공 도구를 부르지 않는다"
        return search_transit(self.travel, **arguments)


def _run(text, tago):
    toolbox, case_id = FakeTools(tago), uuid4()
    pack = ContextPack(pack_id=uuid4(), case_id=case_id, team_id="flight", tenant_id="t", knowledge_scope=["flight"],
                       current_state={"customer_id": str(uuid4())}, estimated_input_tokens=1)
    task = TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id="flight", capability="flight.assist",
                    case_version=1, input_text=text, context=pack, allowed_tools=BookingTeam.manifest.allowed_tools,
                    deadline_at=datetime.now(UTC) + timedelta(seconds=90))
    return asyncio.run(BookingTeam(toolbox, None).execute(task)), toolbox


def test_a_train_sentence_is_answered_from_tago_by_time_band_with_booking_links():
    tago = FakeTago(trains=[_train("KTX", "07:00", "09:40", 59800, "101"), _train("KTX", "07:30", "10:10", 59800, "103"),
                            _train("KTX", "08:00", "10:40", 59800, "105"), _train("무궁화호", "13:00", "18:30", 28600, "1205"),
                            _train("SRT", "19:00", "21:20", 52600, "381")])
    result, tools = _run(f"{GO.month}월 {GO.day}일 서울에서 부산 가는 기차 2명", tago)
    assert result.outcome == "completed"
    assert tools.calls == [("read.booking_search_transit", {"mode": "train", "origin": "서울", "destination": "부산",
                                                            "depart_date": GO.isoformat(), "adults": 2})]
    assert [e.source_id for e in result.evidence] == ["flight.interpret_rules", "read.booking_search_transit:가는 편"]
    answer = result.answer
    assert answer.startswith(f"서울 → 부산 · {GO.isoformat()} · 성인 2명 조건으로 찾은 기차 운행입니다.")
    assert "[가는 편] 서울 → 부산 · 전체 5편 중 시간대마다 앞 운행을 보여 드립니다." in answer
    assert "[오전] KTX 101 — 서울 07:00 → 부산 09:40 (2시간 40분) · 어른 59,800원 (성인 2명 119,600원)" in answer
    assert "KTX 103" in answer and "KTX 105" not in answer, "시간대마다 앞 2편"
    assert "[오후] 무궁화호 1205" in answer and "[저녁] SRT 381" in answer
    assert "코레일 승차권 예매(KTX · ITX · 무궁화): https://www.letskorail.com/" in answer
    assert "어른 1인 기준 조회 시점 참고값" in answer
    assert result.decisions[0]["mode"] == "train" and result.decisions[0]["tago_calls"] == 3


def test_a_time_band_and_a_grade_narrow_the_trains_and_a_return_day_adds_a_second_search():
    tago = FakeTago(trains=[_train("KTX", "07:00", "09:40", 59800, "101"), _train("무궁화호", "07:20", "12:50", 28600, "1201"),
                            _train("KTX", "13:00", "15:40", 59800, "121")])
    result, tools = _run(f"{GO.month}월 {GO.day}일 서울에서 부산 KTX 2명 오전 출발, {BACK.day}일에 오는", tago)
    assert [a["depart_date"] for _, a in tools.calls] == [GO.isoformat(), BACK.isoformat()]
    assert [(a["origin"], a["destination"]) for _, a in tools.calls] == [("서울", "부산"), ("부산", "서울")]
    answer = result.answer
    assert "[오는 편]" in answer
    going = answer.split("[오는 편]")[0]                       # 오는 편은 가짜 어댑터가 같은 열차를 돌려줘 시간대 제한 없이 다 보인다
    assert "[가는 편] 서울 → 부산 · 전체 2편 중 오전 출발 1편 보여 드립니다." in going, "KTX 만 · 오전만"
    assert "KTX 101" in going and "무궁화호 1201" not in going and "KTX 121" not in going


def test_an_unknown_station_or_no_schedule_is_said_plainly_and_a_dead_source_is_unknown():
    result, _ = _run(f"{GO.month}월 {GO.day}일 서울에서 강릉 가는 기차 2명", FakeTago())   # 사전엔 있지만 공급자 목록(가짜)에 없는 역
    assert "「강릉」을(를) 역 이름으로 찾지 못했습니다. 역 이름을 정확히 알려 주세요." in result.answer
    found, missing = _rules(f"{GO.month}월 {GO.day}일 서울에서 화성 가는 기차 2명")             # 사전에 없는 곳은 해석에서 비워 되묻는다
    assert found.destination is None and missing == ["destination"]
    result, _ = _run(f"{GO.month}월 {GO.day}일 서울에서 부산 가는 기차 2명", FakeTago(trains=[]))
    assert "그날 운행이 없습니다(공급자 결과 기준)" in result.answer
    result, _ = _run(f"{GO.month}월 {GO.day}일 서울에서 부산 가는 기차 2명", None)
    assert result.outcome != "completed" or "모름" in (result.answer or ""), "소스가 없으면 모름(지어내지 않음)"


def test_a_bus_sentence_shows_the_terminal_used_and_the_bus_links():
    express = {("T1", "T7"): [_bus("express", "서울경부", "부산", "06:00", 26600)]}
    result, tools = _run(f"{GO.month}월 {GO.day}일 서울에서 부산 가는 고속버스 3명 새벽", FakeTago(express=express, suburbs={}))
    assert tools.calls[0][1]["kind"] == "express"
    assert "[가는 편] 서울경부 → 부산 · 전체 1편 중 새벽 출발 1편 보여 드립니다." in result.answer
    assert "[새벽] 고속우등 — 서울경부 06:00 → 부산 ? (소요 모름) · 어른 26,600원 (성인 3명 79,800원)" in result.answer
    assert "코버스 고속버스 예매: https://www.kobus.co.kr/" in result.answer

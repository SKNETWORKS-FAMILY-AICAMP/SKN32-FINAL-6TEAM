# -*- coding: utf-8 -*-
"""장소 정보 채우기 파이프라인(`place_enrichment.enrich_place`) — 가짜 DB · 카카오 · LLM · 지오코더로 본다(실제 호출 없음). `[2026-10-19]`

흐름: 장소 이름 → 활동 원장 → (없으면) 카카오 실존만 → 웹 검색(비어 있는 칸만) → 주소를 좌표로 → 저장.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace


from app.domains.travel_ops.instances.activity import geocode as g
from app.domains.travel_ops.instances.activity import place_enrichment as pe
from app.domains.travel_ops.instances.activity import web_info as wi

NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
URL = "https://www.example.go.kr/info"
KW = dict(timeout=5, wait=0.1, concurrent=1, max_age_days=3650)       # 가드레일 대신 값을 직접 준다


class IO:
    """`PlaceIO` 와 같은 모양의 가짜 — 원장 찾기 결과 · 원장 행 · 웹 정보 줄을 정해 두고 저장을 기록한다."""

    def __init__(self, lookup, ledger=None, web=None, save_ok=True):
        self._lookup, self._ledger, self._web, self._save_ok = lookup, ledger, web or {}, save_ok
        self.saved: list[tuple[str, list[wi.Entry]]] = []
        self.lookups: list[str] = []

    def lookup(self, name):
        self.lookups.append(name)
        return self._lookup

    def ledger_row(self, content_id):
        return self._ledger

    def web_entries(self, key):
        return self._web

    def save(self, key, entries, *, model, now):
        self.saved.append((key, list(entries)))
        return self._save_ok


class LLM:
    def __init__(self, output=None, sources=(URL,), exc=None):
        self.output, self.sources, self.exc, self.calls = output, list(sources), exc, []

    async def judge(self, prompt_key, payload, *, schema, schema_name, web_search=None, instructions=None, run_id=None):
        self.calls.append({"prompt_key": prompt_key, "payload": payload, "schema": schema, "web_search": web_search})
        if self.exc is not None:
            raise self.exc
        return SimpleNamespace(output=self.output, sources=self.sources, model="fake-web")


class Geo:
    def __init__(self, result=None):
        self.result, self.asked = result or g.GeoResult(g.OK, 37.55, 126.98, "road"), []

    def geocode(self, address):
        self.asked.append(address)
        return self.result


def _item(value, quote=None):
    return {"value": value, "quote": quote or value, "url": URL, "published_at": "2026-10-01"}


FOUND = {"status": "found", "content_id": "126535", "via": "place_catalog"}
OFF = {"status": "exists_unregistered", "via": "kakao"}                  # 카카오는 「있다」만 — 이름 · 좌표 · 주소는 없다


def _out(**kw):
    return {f: kw.get(f) for f in wi.FIELDS}


def _run(io, llm=None, geo=None, name="OO 카페", **kw):
    return pe.enrich_place(name, io, llm or LLM(_out()), geo or Geo(), now=NOW, **{**KW, **kw})


# ── 어디서 멈추나 ────────────────────────────────────────────────

def test_empty_name_and_not_found_never_call_the_web():
    llm = LLM(_out())
    assert _run(IO({"status": "not_found"}), llm)["status"] == pe.NOT_FOUND
    assert _run(IO(FOUND), llm, name="  ")["status"] == pe.NOT_FOUND
    assert llm.calls == []


def test_ambiguous_ledger_names_are_not_guessed():
    out = _run(IO({"status": "ambiguous", "candidates": [{"content_id": "1", "title": "서울 숲"}]}), llm := LLM(_out()))
    assert out["status"] == pe.AMBIGUOUS and out["candidates"] and llm.calls == []


def test_a_kakao_that_could_not_be_asked_is_unknown_not_not_found():
    out = _run(IO({"status": "unknown", "reason": "kakao_blocked"}), llm := LLM(_out()))
    assert out["status"] == pe.UNKNOWN and out["reason"] == "kakao_blocked" and llm.calls == []


def test_nothing_missing_means_complete_and_no_web_call():
    ledger = {c: "x" for c in pe._LEDGER_COLUMNS}
    fresh = {f: wi.Entry(f, "v", "web", "q", URL, None, NOW + timedelta(days=5)) for f in ("homepage", "pet")}
    llm = LLM(_out())
    out = _run(IO(FOUND, ledger, fresh), llm)
    assert out["status"] == pe.COMPLETE and out["in_ledger"] is True and llm.calls == []


# ── 원장에 있는 장소: 빈 칸만 ────────────────────────────────────

def test_ledger_place_asks_only_for_empty_columns_and_never_geocodes():
    ledger = {c: "x" for c in pe._LEDGER_COLUMNS}
    ledger.update(usetime_text=None, restdate_text="")                     # 운영시간 · 휴무만 비어 있다
    io, llm, geo = IO(FOUND, ledger), LLM(_out(business_hours=_item("09:00~18:00"), closed_days=_item("매주 월요일"))), Geo()
    out = _run(io, llm, geo, name="남산타워")
    assert llm.calls[0]["payload"]["fields"] == ["business_hours", "closed_days", "homepage", "pet"]   # 채워진 칸은 패스
    assert llm.calls[0]["payload"]["place_name"] == "남산타워" and llm.calls[0]["prompt_key"] == "activity_judge.place_info"
    assert out["status"] == pe.ENRICHED and out["place_key"] == "126535" and out["in_ledger"] is True
    assert sorted(out["filled"]) == ["business_hours", "closed_days"] and geo.asked == []
    key, entries = io.saved[0]
    web = [e for e in entries if e.source == "web"]
    assert key == "126535" and {e.field for e in web} == {"business_hours", "closed_days"}
    assert all(e.quote and e.url for e in web)
    assert {e.field for e in entries if e.source == "none"} == {"homepage", "pet"}      # 물었는데 못 찾은 칸 — 「못 찾음」 표시


# ── 원장 밖: 카카오 실존만 → 웹 → 좌표 ───────────────────────────

def test_off_ledger_place_gets_web_info_then_coordinates_from_vworld_and_the_customer_name():
    io = IO(OFF)
    llm = LLM(_out(address=_item("서울특별시 종로구 사직로 161"), business_hours=_item("10:00~20:00", "영업시간 10:00~20:00")))
    geo = Geo(g.GeoResult(g.OK, 37.5758, 126.9769, "road"))
    out = _run(io, llm, geo)
    assert out["status"] == pe.ENRICHED and out["in_ledger"] is False and out["place_key"] == "web:oo카페"
    assert out["coords"] == {"latitude": 37.5758, "longitude": 126.9769} and geo.asked == ["서울특별시 종로구 사직로 161"]
    entries = {e.field: e for e in io.saved[0][1]}
    assert entries["lat_lng"].source == "vworld" and entries["lat_lng"].value == "37.5758,126.9769"
    assert entries["name"].source == "customer" and entries["name"].value == "OO 카페"      # 고객이 쓴 이름만 — 카카오 이름이 아니다
    assert llm.calls[0]["payload"]["address"] is None                    # 주소를 아직 모른다
    assert "address" in llm.calls[0]["payload"]["fields"]


def test_geocode_failure_still_saves_the_web_facts_without_coordinates():
    io = IO(OFF)
    out = _run(io, LLM(_out(address=_item("서울특별시 종로구 사직로 161"))), Geo(g.GeoResult(g.UNAVAILABLE, reason="TimeoutError")))
    assert out["status"] == pe.ENRICHED and out["coords"] is None and out["geocode"] == g.UNAVAILABLE
    assert "lat_lng" not in {e.field for e in io.saved[0][1]}


def test_no_address_means_no_geocoder_call():
    geo = Geo()
    _run(IO(OFF), LLM(_out(business_hours=_item("10:00~20:00"))), geo)
    assert geo.asked == []


# ── 웹 검색이 못 하거나 쓸 값이 없을 때 ──────────────────────────

def test_values_that_fail_verification_are_dropped_and_nothing_is_saved_if_nothing_passes():
    io = IO(OFF)
    bad = {**_item("09:00~21:00", "운영시간 09:00~18:00")}                # 인용에 없는 숫자
    out = _run(io, LLM(_out(business_hours=bad)))
    assert out["status"] == pe.NO_INFO and "business_hours:value_not_in_quote" in out["dropped"]
    assert {e.source for e in io.saved[0][1]} == {"none"}                  # 값은 저장하지 않고, 「못 찾음」 표시만 남긴다


def test_a_url_the_model_did_not_search_is_dropped():
    out = _run(IO(OFF), LLM(_out(business_hours=_item("10:00~20:00")), sources=["https://other.example/x"]))
    assert out["status"] == pe.NO_INFO and "business_hours:url_not_in_sources" in out["dropped"]


def test_a_timeout_is_reported_as_a_timeout_and_other_errors_by_kind_never_as_not_found():
    io = IO(OFF)
    assert _run(io, LLM(exc=TimeoutError("slow")))["status"] == pe.WEB_TIMEOUT
    out = _run(io, LLM(exc=RuntimeError("boom")))
    assert out["status"] == pe.WEB_ERROR and out["error"] == "RuntimeError" and io.saved == []


def test_budget_exhausted_does_not_call_the_web():
    llm = LLM(_out())
    out = _run(IO(OFF), llm, budget=lambda meter: False)
    assert out["status"] == pe.BUDGET and llm.calls == []


def test_the_budget_is_asked_with_the_web_meter():
    seen = []
    _run(IO(OFF), LLM(_out()), budget=lambda meter: seen.append(meter) or True)
    assert seen == ["activity_judge_web"]


def test_a_missing_table_is_reported_so_the_caller_can_see_nothing_was_saved():
    out = _run(IO(OFF, save_ok=False), LLM(_out(business_hours=_item("10:00~20:00"))))
    assert out["status"] == pe.TABLE_MISSING


def test_only_the_asked_fields_come_back_even_if_the_model_adds_others():
    io = IO(FOUND, {c: "x" for c in pe._LEDGER_COLUMNS})
    out = _run(io, LLM({**_out(), "business_hours": _item("10:00~20:00"), "overview": _item("멋진 곳", "멋진 곳")}))
    assert out["status"] == pe.NO_INFO                                    # 운영시간은 원장이 이미 있어 묻지 않았다 — 모델이 덧붙인 값은 버린다


def test_a_web_search_that_opened_no_page_is_web_off_and_leaves_no_not_found_markers():
    """★웹 검색이 꺼져 있으면(`activity_judge_web_search`) 검색한 출처가 없다 — 「못 찾음」 표시를 남기면 7일 동안 다시 안 묻는다."""
    io = IO(OFF)
    out = _run(io, LLM(_out(business_hours=_item("10:00~20:00")), sources=[]))
    assert out["status"] == pe.WEB_OFF and io.saved == []

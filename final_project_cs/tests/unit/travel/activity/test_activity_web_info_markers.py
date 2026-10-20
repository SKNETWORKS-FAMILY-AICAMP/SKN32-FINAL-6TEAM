# -*- coding: utf-8 -*-
"""웹 검색에서 값을 못 찾은 칸의 「못 찾음」 표시 — 같은 칸을 매번 다시 검색하지 않게 한다. `[2026-10-19]`

검색은 한 번에 약 $0.03 이다. 값을 못 얻은 칸을 표시 없이 두면 일정을 열 때마다 같은 칸을 다시 검색한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domains.travel_ops.instances.activity import place_enrichment as pe
from app.domains.travel_ops.instances.activity import web_info as wi

from .test_activity_place_enrichment import IO, LLM, OFF, NOW, _item, _out, _run


def test_a_not_found_marker_is_not_a_value_and_blocks_asking_again_until_it_expires():
    marker = wi.not_found_markers(["fee"], [], NOW)[0]
    assert marker.source == "none" and marker.value == "" and marker.expires_at == NOW + timedelta(days=wi.NOTHING_TTL_DAYS)
    assert wi.effective("fee", None, marker, NOW) == (None, None)                      # 값이 아니다
    assert wi.missing_fields({}, {"fee": marker}, NOW, wanted=("fee",)) == []          # 만료 전에는 다시 묻지 않는다
    assert wi.missing_fields({}, {"fee": marker}, NOW + timedelta(days=8), wanted=("fee",)) == ["fee"]


def test_markers_are_made_only_for_fields_that_were_not_found():
    assert [m.field for m in wi.not_found_markers(["fee", "tel", "pet"], ["tel"], NOW)] == ["fee", "pet"]


def test_fields_the_web_could_not_answer_get_markers_and_are_not_searched_again():
    io = IO(OFF)
    out = _run(io, LLM(_out(business_hours=_item("10:00~20:00"))))
    entries = {e.field: e for e in io.saved[0][1]}
    assert out["status"] == pe.ENRICHED and entries["business_hours"].source == "web"
    assert entries["closed_days"].source == "none" and entries["closed_days"].value == ""
    assert entries["closed_days"].expires_at == NOW + timedelta(days=wi.NOTHING_TTL_DAYS)
    assert "closed_days" in out["not_found"] and "business_hours" not in out["not_found"]
    again, llm = IO(OFF, web=dict(entries)), LLM(_out())
    assert _run(again, llm)["status"] == pe.COMPLETE and llm.calls == []

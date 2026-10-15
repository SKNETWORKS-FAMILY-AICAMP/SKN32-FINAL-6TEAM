# -*- coding: utf-8 -*-
"""활동 CSV 사실 칸 → 장소 목록 `raw_json` 맞추기(`scripts/activity/load_csv_facts.py`)와 그 출처 표시. `[2026-10-15]`"""
from __future__ import annotations

import json

from app.domains.travel_ops.components.places.place_info import catalog_fact_note
from scripts.activity.load_csv_facts import patch_for

HUMAN = {"by": "human", "checked": "2026-10-15", "note": "사용자 확인(대화로 값 제공 2026-10-15)"}
CLAUDE = {"by": "claude", "url": "https://www.example.go.kr/", "checked": "2026-10-15", "quote": "문의 02-000-0000"}


def _row(**values):
    return {"contentid": "1", "field_sources": "", **values}


def test_new_csv_values_are_put_and_same_values_are_left():
    raw = {"tel": "02-111-1111", "overview": "남의 글"}
    put, drop = patch_for(_row(tel="02-111-1111", fee="무료", age_limit="5세 이상"), raw)
    assert put == {"fee": "무료", "age_limit": "5세 이상"} and drop == []


def test_an_emptied_csv_cell_drops_the_old_key_but_never_the_overview():
    put, drop = patch_for(_row(tel=""), {"tel": "옛 번호", "overview": "남의 글"})
    assert put == {} and drop == ["tel"]                         # ★옛 값이 사실처럼 남지 않게 · 소개글은 손대지 않는다


def test_field_sources_are_stored_as_an_object_and_compared_with_the_old_text():
    sources = {"tel": HUMAN}
    put, _ = patch_for(_row(tel="02-1", field_sources=json.dumps(sources, ensure_ascii=False)), {"tel": "02-1"})
    assert put == {"field_sources": sources}
    put, drop = patch_for(_row(tel="02-1", field_sources=json.dumps(sources)),
                          {"tel": "02-1", "field_sources": json.dumps(sources)})   # 예전 적재분은 글이다 — 같은 뜻이면 그대로
    assert put == {} and drop == []


def test_a_human_phone_is_not_shown_as_a_tour_api_value():
    assert catalog_fact_note({"tel": "02-780-6948", "field_sources": {"tel": HUMAN}}, "tel") == "연락처: 직접 확인(2026-10-15)"
    assert catalog_fact_note({"tel": "02-1", "field_sources": json.dumps({"tel": CLAUDE})}, "tel") == \
        "연락처: 공식 페이지(2026-10-15 AI 확인)"


def test_a_tour_api_phone_or_an_empty_na_cell_has_no_note():
    assert catalog_fact_note({"tel": "02-1"}, "tel") is None
    assert catalog_fact_note({"tel": "02-1", "field_sources": {"closed_days": HUMAN}}, "tel") is None
    assert catalog_fact_note({"field_sources": {"tel": {**HUMAN, "na": True}}}, "tel") is None

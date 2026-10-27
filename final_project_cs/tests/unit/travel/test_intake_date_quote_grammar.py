# -*- coding: utf-8 -*-
"""접수 읽기 생성 문법 — 날짜를 내면 날짜 인용 칸을 비울 수 없다. `[2026-10-27 G 모델 품질 · 수용 I05]`

☆왜(실 E4B 진단 `fix5 ev/diag-i05.json`): 「2030년 1월 2일 서울 2명 여행: 오전 10시~11시 …」에 items 3개 모두
  date="2030-01-02" · date_quote=null 을 냈다. 스키마가 두 칸을 독립된 「문자열 또는 null」로 두어 날짜만 내고 인용을 비울 수 있었다.
  `ground` 는 인용 없는 날짜를 버린다(dropped.date=3) → 첫날 질문.
★지키려는 것: 생성 문법만 좁힌다. 날짜를 내려면 인용도 낸다 — 인용이 원문에 없으면 `ground` 가 지금처럼 버린다
  (코드가 인용을 붙이지 않는다 — fix5 Codex G1 에서 기각한 규칙 인용 붙이기와 다르다). 날짜 null · 인용 null 은 그대로 낼 수 있다.
  유료 엄격 스키마(`strict_schema`)도 받는다.
"""
from __future__ import annotations

import jsonschema
import pytest

from app.domains.travel_ops.components.intake import agent_read
from app.infrastructure.llm_failover import strict_schema


def _raw(**item):
    base = {"place_quote": "합성궁", "day": 1, "date": None, "date_quote": None, "start": "10:00", "end": "11:00",
            "time_quote": "오전 10시~11시", "kind": "activity", "locked": None, "locked_quote": None}
    return {"guard": {"off_topic": False, "prompt_injection": False, "out_of_scope": False, "quote": None},
            "pieces": [{"kind": "plan_item", "quote": "오전 10시~11시 합성궁"}], "items": [{**base, **item}], "moves": [],
            "conditions": [], "preferences": [], "gaps": [], "missing": [], "trip": {"party_size": 2, "days": 1, "nights": None}}


def _admits(raw, schema=agent_read.SCHEMA) -> bool:
    try:
        jsonschema.validate(raw, schema)
    except jsonschema.ValidationError:
        return False
    return True


def test_a_dated_item_without_a_date_quote_is_not_generated():
    assert not _admits(_raw(date="2031-03-04", date_quote=None))
    assert not _admits(_raw(date="2031-03-04", date_quote=""))


@pytest.mark.parametrize("item", [{"date": None, "date_quote": None}, {"date": "2031-03-04", "date_quote": "2031년 3월 4일"}])
def test_undated_and_quoted_items_are_generated(item):
    assert _admits(_raw(**item))


def test_a_quote_without_a_date_is_not_generated():
    assert not _admits(_raw(date=None, date_quote="2031년 3월 4일"))


def test_the_paid_strict_schema_still_has_object_branches():
    strict = strict_schema(agent_read.SCHEMA)
    branches = strict["properties"]["items"]["items"]["anyOf"]
    assert len(branches) == 2
    for branch in branches:
        assert branch["additionalProperties"] is False and sorted(branch["required"]) == sorted(branch["properties"])

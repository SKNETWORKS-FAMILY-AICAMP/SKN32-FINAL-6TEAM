# -*- coding: utf-8 -*-
"""`place_identity.explain` — 판정과 **이유**. 직접 입력해 보는 도구(`scripts/activity/try_place_names.py`)가 이 이유를 보여 준다. `[2026-10-20]`"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.instances.activity import place_aliases as pa
from app.domains.travel_ops.instances.activity import place_identity as pi

TABLE = pa.AliasTable([("N서울타워", "126535"), ("남산타워", "126535")])
TOWER = pi.Spot("남산서울타워", 37.5510, 126.9878, "126535")


def _item(name, dlat=0.0, **kw):
    return pi.Spot(name, 37.5510 + dlat, 126.9878, **kw)


@pytest.mark.parametrize("item, expected, reason_part", [
    (pi.Spot("아무 이름", None, None, "126535"), "same", "같은 contentid"),
    (_item("남산 서울타워"), "same", "정규화한 이름이 같다"),
    (_item("N서울타워", 0.0005), "same", "별칭 일치"),
    (pi.Spot("N서울타워", None, None), "same", "좌표를 몰라 별칭을 믿는다"),
    (_item("N서울타워", 0.05), "ambiguous", "별칭이지만"),
    (_item("남산서울타우", 0.0005), "ambiguous", "유사도"),
    (_item("롯데월드 아쿠아리움", 0.0005), "different", "이름이 닮지 않았다"),
    (_item("남산서울타우", 0.05), "different", "떨어져 있다"),
    (pi.Spot("남산서울타우", None, None), "different", "좌표를 몰라"),
])
def test_explain_gives_the_verdict_and_the_rule_that_decided(item, expected, reason_part):
    verdict, why = pi.explain(item, TOWER, TABLE)
    assert verdict == expected and reason_part in why


def test_verdict_is_exactly_the_first_part_of_explain():
    for item in (_item("N서울타워"), _item("남산서울타우", 0.0005), _item("경복궁", 0.0005)):
        assert pi.verdict(item, TOWER, TABLE) == pi.explain(item, TOWER, TABLE)[0]


def test_an_empty_name_is_different_with_a_reason():
    assert pi.explain(pi.Spot("", 0, 0), TOWER, TABLE) == ("different", "이름이 비었다")

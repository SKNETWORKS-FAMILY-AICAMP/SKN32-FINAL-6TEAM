"""make_michelin_sql — 이름이 같을 때만 잇고, 다른 이름은 주소로 맞춘 별칭만 잇는다."""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(HERE, "..", "..", "..", "scripts", "dining", "make_michelin_sql.py")


@pytest.fixture(scope="module")
def mm():
    spec = importlib.util.spec_from_file_location("dining_make_michelin_sql", os.path.abspath(MODULE))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dining_make_michelin_sql"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_이름은_띄어쓰기와_기호를_떼고_비교한다(mm):
    assert mm.norm("3대 삼계장인") == mm.norm("3대삼계장인")
    assert mm.norm("테이블 포 포") == mm.norm("테이블포포")
    assert mm.norm("무오키") != mm.norm("무오키(MUOKI)")   # 그래서 별칭이 필요하다


def test_주소가_다른_오레노_라멘은_별칭에_없다(mm):
    assert "오레노 라멘" not in mm.ALIAS


def test_목록은_가이드_서울_180곳(mm):
    import csv
    rows = list(csv.DictReader(open(mm.LIST, encoding="utf-8")))
    assert len(rows) == 180
    assert {r["등급"] for r in rows} == {"3스타", "2스타", "1스타", "빕 구르망", "셀렉티드"}

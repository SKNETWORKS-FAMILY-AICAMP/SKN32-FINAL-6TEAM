"""make_nopo_sql — 자치구 · 도로명 · 건물번호 · 상호가 모두 맞을 때만 잇는다. `[2026-10-07]`

데이터 파일을 읽지 않는다 — 주소 해석과 SQL 조각만 본다(데이터는 git 밖이라 CI 에 없다).
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(HERE, "..", "..", "..", "scripts", "dining", "make_nopo_sql.py")


@pytest.fixture(scope="module")
def mn():
    spec = importlib.util.spec_from_file_location("dining_make_nopo_sql", os.path.abspath(MODULE))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dining_make_nopo_sql"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("address, key", [
    ("서울 종로구 종로46길 1 1층 (창신동)", ("종로구", "종로46길", "1")),
    ("서울특별시 마포구 동교로 83 (망원동)", ("마포구", "동교로", "83")),
    ("서울특별시 중구 동호로 249, 신라호텔 23층", ("중구", "동호로", "249")),
    ("서울 영등포구 신길로 200-20 (신길동)", ("영등포구", "신길로", "200-20")),
])
def test_도로명_주소에서_자치구_도로명_건물번호만_꺼낸다(mn, address, key):
    assert mn.addr_key(address) == key


@pytest.mark.parametrize("address", ["서울특별시 동작구 노량진동 297-1", "서울특별시 종로구  자하문로1가길 (9)", ""])
def test_도로명_주소가_아니면_잇지_않는다(mn, address):
    assert mn.addr_key(address) is None


def test_건물번호는_뒤에_숫자가_붙은_번지에_걸리지_않는다(mn):
    sql = mn.match_sql("망원동즉석우동돈까스", ("마포구", "동교로", "83"))
    pattern = re.search(r"p\.road_address ~ '(.+?)'", sql).group(1)
    assert re.search(pattern, "서울특별시 마포구 동교로 83 (망원동)")
    assert re.search(pattern, "서울특별시 마포구 동교로 83, 1층")
    assert not re.search(pattern, "서울특별시 마포구 동교로 830")
    assert not re.search(pattern, "서울특별시 마포구 동교로 83-1")


def test_별칭이_있으면_원장_상호로_찾고_없으면_정규화한_상호로_찾는다(mn):
    assert "p.name_ko = '망원동즉석우동 본점'" in mn.match_sql("망원동즉석우동돈까스", ("마포구", "동교로", "83"))
    plain = mn.match_sql("공평동꼼장어 본점", ("종로구", "우정국로", "29"))
    assert "'공평동꼼장어본점'" in plain and "strpos" in plain
    assert "HAVING count(*) = 1" in plain       # 후보가 둘이면 잇지 않는다


def test_도로명_주소가_아닌_행은_SQL_을_만들지_않는다(mn):
    lines = mn.sql_lines([{"상호": "번지집", "주소": "서울특별시 동작구 노량진동 297-1", "자치구": "동작구"}])
    assert not any("dn_attribute (" in line for line in lines)

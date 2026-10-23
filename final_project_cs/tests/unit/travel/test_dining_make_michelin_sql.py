"""make_michelin_sql — 이름이 같을 때만 잇고, 다른 이름은 주소로 맞춘 별칭만 잇는다.

데이터 파일을 읽는 시험은 파일이 없으면 건너뛴다. 데이터는 git 밖(datasets/dining/processed)에 있어
CI 에는 없다 — 팀 드라이브에서 받은 PC 에서만 돈다.
"""
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


def _need(*paths: str) -> None:
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        pytest.skip(f"데이터 없음(git 밖): {os.path.basename(missing[0])}")


def test_목록은_가이드_서울_180곳(mm):
    import csv
    _need(mm.LIST)
    rows = list(csv.DictReader(open(mm.LIST, encoding="utf-8")))
    assert len(rows) == 180
    assert {r["등급"] for r in rows} == {"3스타", "2스타", "1스타", "빕 구르망", "셀렉티드"}


def test_요리_종류로_대표_분류(mm):
    assert mm.category_of("냉면") == "한식"
    assert mm.category_of("한식 컨템퍼러리") == "한식"
    assert mm.category_of("재패니즈 컨템퍼러리") == "일식"
    assert mm.category_of("비건, 중식") == "중식"
    assert mm.category_of("프렌치") == "양식"
    assert mm.category_of("타이") == "기타"


def test_전화는_원장_표기로(mm):
    assert mm.phone_of("+82 2-2230-3367") == "02-2230-3367"
    assert mm.phone_of("+82 10-7286-9914") == "010-7286-9914"
    assert mm.phone_of(None) is None


def test_편의시설은_표시가_있는_것만_속성으로(mm):
    got = mm.facts_attributes({"편의시설": ["발렛파킹", "현금만 가능"], "가족": True})
    assert ("card_payment", "no", "현금만 가능") in got
    assert ("parking", "limited", "발렛파킹만") in got
    assert any(code == "kids_allowed" and state == "yes" for code, state, _ in got)
    assert mm.facts_attributes({"편의시설": ["에어컨"], "가족": None}) == []


def test_모은_가게는_목록의_나머지_145곳(mm):
    import csv
    import json
    _need(mm.FACTS, mm.LIST)
    facts = [json.loads(line) for line in open(mm.FACTS, encoding="utf-8")]
    names = {r["상호"] for r in csv.DictReader(open(mm.LIST, encoding="utf-8"))}
    assert len(facts) == 145 and {f["상호"] for f in facts} <= names
    assert all(f["위도"] and f["경도"] and f["주소"] for f in facts)

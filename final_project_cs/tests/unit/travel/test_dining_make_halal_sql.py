"""make_halal_sql 의 「언제 할랄이라고 말하는가」.

사람이 채운 [확인] 칸은 등급 표를 따른다. 확인일이 「웹 …」인 행은 운영 결정으로 yes 이되
상세에 「웹 근거」를 적어 사람 확인과 섞이지 않게 한다.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from datetime import date

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(HERE, "..", "..", "..", "scripts", "dining", "make_halal_sql.py")
TODAY = date(2026, 9, 28)


@pytest.fixture(scope="module")
def mh():
    spec = importlib.util.spec_from_file_location("dining_make_halal_sql", os.path.abspath(MODULE))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dining_make_halal_sql"] = mod
    spec.loader.exec_module(mod)
    return mod


def row(**checked):
    base = {"[확인] 등급": "", "[확인] 인증 유효기간": "", "[확인] 돼지고기": "",
            "[확인] 술": "", "확인일": "2026-09-28"}
    return {**base, **checked}


def test_확인하지_않은_행은_붙이지_않는다(mh):
    assert mh.halal_state(row(확인일=""), TODAY)[0] is None
    assert mh.halal_state(row(**{"[확인] 등급": "KMF 인증", "확인일": ""}), TODAY)[0] is None


def test_유효한_인증은_yes(mh):
    state, detail = mh.halal_state(row(**{"[확인] 등급": "KMF 인증",
                                          "[확인] 인증 유효기간": "2027-03-16"}), TODAY)
    assert state == "yes" and "2027-03-16" in detail


def test_만료된_인증은_모름(mh):
    state, detail = mh.halal_state(row(**{"[확인] 등급": "KMF 인증",
                                          "[확인] 인증 유효기간": "2026-09-17"}), TODAY)
    assert state is None and "만료" in detail


def test_프렌들리와_포크프리는_조건부(mh):
    for grade in ("무슬림 자가인증", "무슬림 프렌들리", "포크프리"):
        assert mh.halal_state(row(**{"[확인] 등급": grade}), TODAY)[0] == "limited"


def test_돼지고기가_있으면_등급과_상관없이_no(mh):
    state, _ = mh.halal_state(row(**{"[확인] 등급": "무슬림 프렌들리", "[확인] 돼지고기": "있음"}), TODAY)
    assert state == "no"


def test_할랄_아님은_no_모름은_붙이지_않는다(mh):
    assert mh.halal_state(row(**{"[확인] 등급": "할랄 아님"}), TODAY)[0] == "no"
    assert mh.halal_state(row(**{"[확인] 등급": "모름"}), TODAY)[0] is None


def test_웹_근거는_등급과_상관없이_yes_상세에_웹_근거(mh):
    for grade in ("KMF 인증 만료", "할랄 표방 (인증 근거 없음)", "모름"):
        state, detail = mh.halal_state(row(**{"[확인] 등급": grade, "확인일": "웹 2026-09-28"}), TODAY)
        assert state == "yes" and detail.startswith("웹 근거") and grade in detail


def test_웹_근거라도_돼지고기_있음이나_할랄_아님은_no(mh):
    web = {"확인일": "웹 2026-09-28"}
    assert mh.halal_state(row(**{"[확인] 등급": "할랄 표방", "[확인] 돼지고기": "있음", **web}), TODAY)[0] == "no"
    assert mh.halal_state(row(**{"[확인] 등급": "할랄 아님", **web}), TODAY)[0] == "no"


def test_웹_근거의_유효기간과_술은_상세에(mh):
    state, detail = mh.halal_state(row(**{"[확인] 등급": "KMF 인증 만료", "[확인] 인증 유효기간": "2026-04-14 만료",
                                          "[확인] 술": "안 팖", "확인일": "웹 2026-09-28"}), TODAY)
    assert state == "yes" and "2026-04-14 만료" in detail and "술 안 팖" in detail


def test_사람_확인_행은_웹_규칙을_타지_않는다(mh):
    # 만료된 인증을 사람이 확인했으면 여전히 붙이지 않는다
    assert mh.halal_state(row(**{"[확인] 등급": "KMF 인증", "[확인] 인증 유효기간": "2026-04-14"}), TODAY)[0] is None


def test_술은_판정에_쓰지_않고_상세에_적는다(mh):
    state, detail = mh.halal_state(row(**{"[확인] 등급": "무슬림 프렌들리", "[확인] 술": "팖"}), TODAY)
    assert state == "limited" and "술 팖" in detail

"""아이 동반(kids_allowed) — 놀이방이 없다는 것은 아이를 받지 않는다는 근거가 아니다."""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(HERE, "..", "..", "..", "scripts", "dining", "make_attribute_sql.py")


@pytest.fixture(scope="module")
def ma():
    spec = importlib.util.spec_from_file_location("dining_make_attribute_sql", os.path.abspath(MODULE))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dining_make_attribute_sql"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_놀이방이_있으면_yes(ma):
    assert ma.kids_state({"kidsfacility": "1"})[:2] == ("yes", "어린이 놀이방")


def test_놀이방이_없다는_것만으로는_모름(ma):
    assert ma.kids_state({"kidsfacility": "0"})[0] == "unknown"
    assert ma.kids_state({})[0] == "unknown"


def test_아동_요금이_있으면_yes(ma):
    assert ma.kids_state({"kidsfacility": "0", "treatmenu": "성인 이용 가격 / 아동 이용 가격"})[0] == "yes"


def test_노키즈가_적혀_있으면_놀이방보다_먼저_no(ma):
    assert ma.kids_state({"kidsfacility": "1", "infocenterfood": "노키즈존 운영"})[0] == "no"


def test_검수_시트는_확인일이_있는_행만(ma, tmp_path):
    path = tmp_path / "kids.csv"
    path.write_text(
        "번호,place_uid,상호,[확인] 아이 동반,[확인] 조건,확인일\n"
        "예시,,(적는 법),가능 / 노키즈 / 일부 / 모름,,2026-09-28\n"
        "1,u1,가,노키즈,13세 미만 불가,2026-09-28\n"
        "2,u2,나,일부,디너만 노키즈,2026-09-28\n"
        "3,u3,다,노키즈,,\n"
        "4,u4,라,모름,,2026-09-28\n", encoding="utf-8-sig")
    got = ma.kids_sheet(str(path))
    assert got == {"u1": ("no", "13세 미만 불가", "2026-09-28"),
                   "u2": ("limited", "디너만 노키즈", "2026-09-28")}

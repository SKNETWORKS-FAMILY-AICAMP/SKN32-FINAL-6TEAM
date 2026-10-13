"""make_category_sql — 확인일이 적힌 줄의 대표 분류만 manual 로 넣고, 틀린 값은 멈춘다. `[2026-10-12]`

데이터 폴더를 읽지 않는다 — 시험이 만든 임시 시트만 본다(데이터는 git 밖이라 CI 에 없다).
"""
from __future__ import annotations

import csv
import importlib.util
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(HERE, "..", "..", "..", "scripts", "dining", "make_category_sql.py")
COLS = ["번호", "place_uid", "상호", "분류 초안", "[확인] 분류", "확인일"]


@pytest.fixture(scope="module")
def mc():
    spec = importlib.util.spec_from_file_location("dining_make_category_sql", os.path.abspath(MODULE))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dining_make_category_sql"] = mod
    spec.loader.exec_module(mod)
    return mod


def _sheet(tmp_path, rows):
    path = tmp_path / "분류_검수_20261012.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in COLS} for r in rows)
    return str(path)


def test_확인일이_있는_줄만_manual_로_넣는다(mc, tmp_path):
    sheet = _sheet(tmp_path, [
        {"place_uid": "u1", "상호": "가", "분류 초안": "한식", "[확인] 분류": "한식", "확인일": "2026-10-12"},
        {"place_uid": "u2", "상호": "나", "분류 초안": "양식", "[확인] 분류": "", "확인일": ""},          # 초안만 — 넣지 않는다
        {"place_uid": "u3", "상호": "다", "분류 초안": "양식", "[확인] 분류": "기타", "확인일": "2026-10-12"},  # 사람이 고친 값
    ])
    lines, n = mc.build(sheet)
    updates = [line for line in lines if line.startswith("UPDATE")]
    assert n == {"분류": 2, "결": 0, "확인 전": 1}
    assert updates == [
        "UPDATE dining.dn_place SET category = '한식', category_method = 'manual', updated_at = now() WHERE place_uid = 'u1';",
        "UPDATE dining.dn_place SET category = '기타', category_method = 'manual', updated_at = now() WHERE place_uid = 'u3';"]


@pytest.mark.parametrize("value", ["미상", "중국식", "", "양 식"])
def test_칸에_없는_분류는_건너뛰지_않고_멈춘다(mc, tmp_path, value):
    sheet = _sheet(tmp_path, [{"place_uid": "u1", "상호": "가", "[확인] 분류": value, "확인일": "2026-10-12"}])
    with pytest.raises(ValueError):
        mc.build(sheet)


def test_분류_칸은_원장_제약과_같다(mc):
    """214 `dn_place_category_chk` 의 칸에서 「미상」만 뺐다 — 미상을 manual 로 박으면 규칙이 다시 못 본다."""
    assert set(mc.ALLOWED) == {"한식", "중식", "일식", "양식", "카페디저트", "기타"}


STYLE_COLS = [*COLS, "[확인] 결"]


def _style_sheet(tmp_path, rows):
    path = tmp_path / "분류_검수_20261013.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=STYLE_COLS)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in STYLE_COLS} for r in rows)
    return str(path)


def test_결만_적힌_줄은_결만_넣고_없음은_비운_manual이다(mc, tmp_path):
    """`[2026-10-12]` 음식 결(231) — 분류 없이 결만 고칠 수 있다. 「없음」은 규칙이 다시 채우지 않게 manual 로 비운다."""
    sheet = _style_sheet(tmp_path, [
        {"place_uid": "u1", "[확인] 분류": "한식", "[확인] 결": "고기구이", "확인일": "2026-10-12"},
        {"place_uid": "u2", "[확인] 결": "없음", "확인일": "2026-10-12"},
    ])
    lines, n = mc.build(sheet)
    updates = [line for line in lines if line.startswith("UPDATE")]
    assert n == {"분류": 1, "결": 2, "확인 전": 0}
    assert "SET style = '고기구이', style_method = 'manual'" in updates[1] and "'u1'" in updates[1]
    assert "SET style = NULL, style_method = 'manual'" in updates[2] and "'u2'" in updates[2]


def test_칸에_없는_결은_멈춘다(mc, tmp_path):
    sheet = _style_sheet(tmp_path, [{"place_uid": "u1", "[확인] 결": "고기", "확인일": "2026-10-12"}])
    with pytest.raises(ValueError):
        mc.build(sheet)


def test_결_칸은_원장_제약과_같다(mc):
    """231 `dn_place_style_chk` 와 글자까지 같아야 한다 — 다르면 시트는 통과하고 적재가 터진다."""
    import re
    sql = open(os.path.join(HERE, "..", "..", "..", "app", "infrastructure", "db", "migrations", "231_dining_style.sql"),
               encoding="utf-8").read()
    block = sql.split("dn_place_style_chk CHECK", 1)[1].split(");", 1)[0]
    assert tuple(re.findall(r"'([^']+)'", block)) == mc.STYLES


def test_엑셀_판도_같은_규칙으로_읽고_날짜가_된_확인일을_돌린다(mc, tmp_path):
    """`[2026-10-12]` 드롭다운이 있는 .xlsx 검수 시트 — 「검수」 시트를 읽는다. 엑셀이 확인일을 날짜로 바꿔도 받는다."""
    from datetime import datetime

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = mc.XLSX_SHEET
    ws.append(STYLE_COLS)
    ws.append(["1", "u1", "가", "", "한식", datetime(2026, 10, 13), "고기구이"])
    ws.append(["2", "u2", "나", "", "", None, ""])                       # 확인 전
    path = tmp_path / "분류_검수_20261013.xlsx"
    wb.save(path)
    lines, n = mc.build(str(path))
    assert n == {"분류": 1, "결": 1, "확인 전": 1}
    assert any("style = '고기구이'" in line and "'u1'" in line for line in lines)


def test_같은_이름이면_엑셀_판을_읽는다(mc, tmp_path, monkeypatch):
    for name in ("분류_검수_20261012.csv", "분류_검수_20261012_결.csv", "분류_검수_20261012_결.xlsx"):
        (tmp_path / name).write_text("", encoding="utf-8")
    patterns = [str(tmp_path / ("분류_검수_[0-9]*." + ext)) for ext in ("csv", "xlsx")]
    import glob
    assert sorted(p for pat in patterns for p in glob.glob(pat))[-1].endswith("_결.xlsx")

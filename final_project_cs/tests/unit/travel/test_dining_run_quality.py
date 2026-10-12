"""run_quality.judge — 폐업이라 원문이 틀렸던 곳은 원장이 닫았으면 맞춘 것으로 센다. `[2026-10-12]`

DB 없이 커서를 흉내 낸다 — 질의 순서대로 준비한 한 줄씩 돌려준다.
"""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(HERE, "..", "..", "..", "scripts", "dining", "run_quality.py")


@pytest.fixture(scope="module")
def rq():
    spec = importlib.util.spec_from_file_location("dining_run_quality", os.path.abspath(MODULE))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dining_run_quality"] = mod
    spec.loader.exec_module(mod)
    return mod


class Cursor:
    def __init__(self, *rows):
        self.rows = list(rows)
        self.sql: list[str] = []

    def execute(self, sql, params=None):
        self.sql.append(sql)

    def fetchone(self):
        return self.rows.pop(0)


CLOSED_TRUTH = {"원문이_실제와_같다": False, "틀린방향": "폐업"}


def test_폐업으로_틀린_곳은_원장이_닫았으면_맞음(rq):
    cur = Cursor(("closed",))
    verdict, actual, _ = rq.judge(cur, "t", "u", "weekday_hours", CLOSED_TRUTH)
    assert verdict == "match"
    assert actual == {"record_status": "closed"}


def test_폐업으로_틀린_곳이_아직_열려_있으면_틀림(rq):
    cur = Cursor(("unknown",), (["tourapi_kor_food"],))
    verdict, _, detail = rq.judge(cur, "t", "u", "weekday_hours", CLOSED_TRUTH)
    assert verdict == "mismatch"
    assert "실제와 달랐다" in detail


def test_폐업이_아닌_정답은_가게_상태를_보지_않는다(rq):
    cur = Cursor((["tourapi_kor_food"],))
    verdict, _, _ = rq.judge(cur, "t", "u", "weekday_hours",
                             {"원문이_실제와_같다": False, "틀린방향": "영업시간 다름"})
    assert verdict == "mismatch"
    assert len(cur.sql) == 1          # record_status 를 묻지 않았다

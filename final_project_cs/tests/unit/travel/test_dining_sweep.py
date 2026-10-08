"""하루 점검(sweep_day)의 경계 — 어디서 판정을 가져오는가, 무엇을 모름으로 두는가.

DB 없이 돈다. 원장 판정(dining_state)은 가짜로 바꿔 끼운다. 원장 SQL 은 integration 시험이 본다.
sweep.py 는 경로로 읽는다 — 패키지를 import 하면 Team 의존 사슬(openai …)이 따라온다.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest

KST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "..", "..", "..", "app", "domains", "travel_ops", "instances", "dining")
DAY = date(2026, 10, 7)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"dining_sweep_pkg.{name}",
                                                  os.path.abspath(os.path.join(PKG, f"{name}.py")))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def sw():
    sys.modules.setdefault("dining_sweep_pkg", types.ModuleType("dining_sweep_pkg")).__path__ = [PKG]
    _load("ledger")
    return _load("sweep")


def at(hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime(DAY.year, DAY.month, DAY.day, h, m, tzinfo=KST)


@dataclass
class Item:
    title: str
    starts_at: datetime
    ends_at: datetime | None = None
    kind: str = "dining"
    place_id: str | None = "11111111-1111-4111-8111-111111111111"
    place: dict[str, Any] | None = None
    item_id: str = "item"
    detail: dict = field(default_factory=dict)


def ledger_says(sw, monkeypatch, **state):
    monkeypatch.setattr(sw, "dining_state", lambda *a, **k: state)
    monkeypatch.setattr(sw, "_resolve", lambda *a, **k: "uid")
    monkeypatch.setattr(sw, "_alternatives", lambda *a, **k: ["대안집", "옆집"])


def test_원장이_닫힘이라면_대안을_붙인다(sw, monkeypatch):
    ledger_says(sw, monkeypatch, linked=True, open_at_slot=False)
    c = sw.check_meal(None, "t", Item("저녁", at("18:00"), at("19:00")))
    assert (c["status"], c["source"], c["alternatives"]) == ("closed", "dining_ledger", ["대안집", "옆집"])


def test_원장이_열림이면_영업_확인(sw, monkeypatch):
    ledger_says(sw, monkeypatch, linked=True, open_at_slot=True, needs_check=False)
    assert sw.check_meal(None, "t", Item("점심", at("12:00")))["status"] == "open"


def test_마감_임박이나_명절이면_확인_필요(sw, monkeypatch):
    ledger_says(sw, monkeypatch, linked=True, open_at_slot=True, needs_check=True)
    assert sw.check_meal(None, "t", Item("저녁", at("20:50")))["status"] == "check"
    ledger_says(sw, monkeypatch, linked=True, open_at_slot=True, needs_holiday_check=True)
    assert "명절" in sw.check_meal(None, "t", Item("저녁", at("18:00")))["reason"]


def test_원장에_없으면_코어_영업시간으로(sw, monkeypatch):
    ledger_says(sw, monkeypatch, linked=False, open_at_slot=None)
    place = {"attributes": {"hours": ["11:00", "21:00"], "break": ["15:00", "17:00"]}}
    c = sw.check_meal(None, "t", Item("점심", at("13:00"), at("13:50"), place=place))
    assert (c["status"], c["source"]) == ("open", "core_place")
    c = sw.check_meal(None, "t", Item("늦은 점심", at("14:30"), at("15:30"), place=place))
    assert c["status"] == "closed" and "브레이크" in c["reason"]
    c = sw.check_meal(None, "t", Item("아침", at("09:00"), at("09:40"), place=place))
    assert c["status"] == "closed"


def test_아무_자료도_없으면_모름이지_닫힘이_아니다(sw, monkeypatch):
    ledger_says(sw, monkeypatch, linked=False, open_at_slot=None)
    c = sw.check_meal(None, "t", Item("저녁", at("18:00"), place={"attributes": {}}))
    assert c["status"] == "unknown" and c["source"] is None


def test_그날_남은_식당_항목만_시각순으로(sw, monkeypatch):
    ledger_says(sw, monkeypatch, linked=True, open_at_slot=True)
    items = [Item("저녁", at("18:00")), Item("관광", at("10:00"), kind="activity"),
             Item("아침", at("08:30")), Item("점심", at("12:00")),
             Item("내일 점심", at("12:00") + timedelta(days=1))]
    got = sw.sweep_day(None, "t", items, day=DAY, now=at("09:00"))
    assert [c["title"] for c in got] == ["점심", "저녁"]


def test_안내_줄(sw):
    checks = [{"title": "점심", "starts_at": at("13:00"), "status": "open", "reason": "영업 중",
               "alternatives": []},
              {"title": "저녁", "starts_at": at("18:00"), "status": "closed", "reason": "휴무",
               "alternatives": ["대안집"]}]
    text = sw.meal_lines(checks)
    assert "13:00 점심 — 영업 확인" in text and "18:00 저녁 — 영업 안 함 (휴무)" in text
    assert "대안: 대안집" in text and "바꿀지" in text
    assert sw.meal_lines([]) == ""


def test_식이_조건은_대안_찾기에_넘긴다(sw, monkeypatch):
    ledger_says(sw, monkeypatch, linked=True, open_at_slot=False)
    seen = {}
    monkeypatch.setattr(sw, "_alternatives", lambda *a: seen.setdefault("conds", a[-1]) and ["할랄집"])
    got = sw.sweep_day(None, "t", [Item("저녁", at("18:00"))], day=DAY, now=at("09:00"),
                       conds=["halal"])
    assert seen["conds"] == ["halal"] and got[0]["alternatives"] == ["할랄집"]


def test_확인된_식이_대안이_없으면_없다고_말한다(sw, monkeypatch):
    ledger_says(sw, monkeypatch, linked=True, open_at_slot=False)
    monkeypatch.setattr(sw, "_alternatives", lambda *a, **k: [])
    c = sw.check_meal(None, "t", Item("저녁", at("18:00")), ["halal"])
    assert c["no_alternative"] == "근처에 확인된 할랄 식당이 없어요"
    assert "근처에 확인된 할랄 식당이 없어요" in sw.meal_lines([c])
    # 식이 조건이 없으면 그런 말을 하지 않는다
    assert sw.check_meal(None, "t", Item("저녁", at("18:00")))["no_alternative"] is None

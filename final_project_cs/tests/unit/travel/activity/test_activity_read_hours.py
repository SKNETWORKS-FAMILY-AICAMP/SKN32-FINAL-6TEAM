"""활동 원장 요일표 미리 펴기(`scripts/activity/read_hours.py`) — 원문 한 줄이 어떤 요일표 · 기록이 되나. DB 없이."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts" / "activity"))
_spec = importlib.util.spec_from_file_location("activity_read_hours", ROOT / "scripts" / "activity" / "read_hours.py")
read_hours = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(read_hours)


class _Chat:
    """모델 대역 — 원문에 있는 인용만 돌려준다."""

    def __init__(self):
        self.calls = 0

    def json(self, system, user):
        self.calls += 1
        return {"open": [{"days": ["mon", "tue", "wed", "thu", "fri"], "open": "10:00", "close": "17:00",
                          "last_entry": None, "quote": "평일 10:00~17:00"}],
                "closed": [{"days": ["sat", "sun"], "quote": "토·일 휴관"}], "conditions": []}


def test_rule_stage_fills_simple_text_without_model():
    week, record = read_hours.read_one("09:00~18:00", "매주 월요일", None)
    assert week["mon"] == "closed" and week["tue"]["open"] == "09:00"
    assert record["method"] == "rule"


def test_rule_stage_marks_complex_text_for_the_model_stage():
    week, record = read_hours.read_one("평일 10:00~17:00", "주말 휴관", None)
    assert week is None and record["method"] == "none" and record["dropped"] == ["규칙으로 펼 수 없다"]


def test_empty_text_is_recorded_as_empty():
    week, record = read_hours.read_one(None, None, None)
    assert week is None and record["dropped"] == ["원문이 비어 있다"]


def test_model_stage_uses_core_reader_with_quote_check():
    chat = _Chat()
    week, record = read_hours.read_one("평일 10:00~17:00", "토·일 휴관", chat)
    assert chat.calls == 1 and record["method"] == "llm"
    assert week["wed"]["close"] == "17:00" and week["sat"] == "closed"

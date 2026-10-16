"""활동 원장의 `live_status` 칸 — 장소 행 길(`state`)과 관광공사 번호 길(`state_by_content`) 둘 다에 실린다.

★`[2026-10-15]` ST4F-573. 전에는 `state` 에만 있어, 확인 화면이 장소 행 없이 번호만 가진 채 `state_by_content` 를 부르면 칸이 비어
  있었다. 두 길이 같은 판정 규칙(`_with_live_status`)을 쓰는지 본다.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.instances.activity import ledger, live_store
from app.domains.travel_ops.instances.activity.judge import modes

KST = ZoneInfo("Asia/Seoul")
WEDNESDAY = datetime(2026, 10, 14, 10, 0, tzinfo=KST)
ROW = {"content_id": "126508", "name_ko": "경복궁", "usetime_text": "09:00~18:00", "restdate_text": "매주 화요일",
       "hours_week": None, "hours_read": None}
CLOSED = {"content_id": "126508", "visit_date": date(2026, 10, 14), "value": "closed",
          "citations": [{"url": "https://x.example/notice", "quote": "임시 휴관", "published_at": None}],
          "checked_at": datetime(2026, 10, 14, 3, 30, tzinfo=KST)}



class _Conn:
    """가짜 연결 — 실시간 운영 상태 읽기는 세이브포인트(`conn.transaction()`) 안에서 한다(`ledger._in_savepoint`, 2026-10-16)."""

    def transaction(self):
        from contextlib import nullcontext
        return nullcontext()


CONN = _Conn()

@pytest.fixture
def stored(monkeypatch):
    """원장 행 · 저장된 운영 상태를 고정한다. 키가 장소 행이든 번호든 같은 줄을 돌려준다."""
    calls = {"lookup": 0, "read": 0}
    monkeypatch.setattr(ledger, "place_row", lambda conn, tenant, place: ROW)
    monkeypatch.setattr(ledger, "content_row", lambda conn, content_id: ROW)

    def lookup(conn, tenant, place, day):
        calls["lookup"] += 1
        return CLOSED

    def read(conn, content_id, day):
        calls["read"] += 1
        return CLOSED

    monkeypatch.setattr(live_store, "lookup", lookup)
    monkeypatch.setattr(live_store, "read", read)
    return calls


def _mode(monkeypatch, value):
    monkeypatch.setattr(modes, "kind_mode", lambda kind: value)


@pytest.mark.parametrize("path", ["state", "state_by_content"])
def test_shadow_carries_the_field_and_keeps_the_verdict(monkeypatch, stored, path):
    _mode(monkeypatch, "shadow")
    out = (ledger.state(CONN, "t", "p1", WEDNESDAY) if path == "state"
           else ledger.state_by_content(CONN, "126508", WEDNESDAY))
    assert out["live_status"]["value"] == "closed" and out["live_status"]["applied"] is False
    assert out["closed"] is False                       # 수요일 — 정기휴무 아님. shadow 는 판정을 안 바꾼다
    assert out.get("closure_reason") != "live_status"


@pytest.mark.parametrize("path", ["state", "state_by_content"])
def test_llm_applies_a_cited_closed(monkeypatch, stored, path):
    _mode(monkeypatch, "llm")
    out = (ledger.state(CONN, "t", "p1", WEDNESDAY) if path == "state"
           else ledger.state_by_content(CONN, "126508", WEDNESDAY))
    assert out["live_status"]["applied"] is True
    assert out["closed"] is True and out["closure_reason"] == "live_status" and out["quote"] == "임시 휴관"


def test_each_path_reads_through_its_own_key(monkeypatch, stored):
    _mode(monkeypatch, "shadow")
    ledger.state(CONN, "t", "p1", WEDNESDAY)
    assert stored == {"lookup": 1, "read": 0}
    ledger.state_by_content(CONN, "126508", WEDNESDAY)
    assert stored == {"lookup": 1, "read": 1}


@pytest.mark.parametrize("path", ["state", "state_by_content"])
def test_rule_mode_has_no_field(monkeypatch, stored, path):
    _mode(monkeypatch, "rule")
    out = (ledger.state(CONN, "t", "p1", WEDNESDAY) if path == "state"
           else ledger.state_by_content(CONN, "126508", WEDNESDAY))
    assert "live_status" not in out

"""감시(새벽 확인)가 활동 원장 판정의 `live_status` 칸을 읽는다 — `[2026-10-15]` 활동 → 코어 전달 4번 (TeamFlow ST4F-536).

칸의 모양(활동 팀 약속): `value`(open · closed · unknown · unchecked) · `mode`(shadow · llm) · `applied` · `checked_at` · `citations` · `visit_date`.
  - `llm` 이고 `applied` 인 「닫힘」만 판정에 들어간다 — 감시 결과가 닫힘(`activity_live_status`)이 된다.
  - `shadow` 면 `closed` 여도 판정은 그대로다(모름) — 값은 결과의 `live_status_reference` 로만 따라가고, 새벽 확인의 `references` 에 쌓인다.
  - 열었다 · 모름 · 아직 안 봄은 닫힘도 열림도 아니다 — 「열었다」로 풀어 주지 않는다.
활동 원장은 팀이 조립 때 꽂는 자리라, 여기서는 그 자리(`activity_ledger.state`)를 대역으로 바꿔 코어가 칸을 읽는 길만 본다.
(활동 팀의 실제 원장이 이 칸을 싣는지는 활동 팀 쪽 변경이 합쳐진 뒤 확인한다.)
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components.team_hooks import activity_ledger
from app.domains.travel_ops.components.watch.dawn_check import DawnCheck
from app.domains.travel_ops.components.watch.place_status import PlaceStatus
from app.infrastructure.db.session import get_connection

from .test_case_version_day import Clock
from .test_place_status_policy import lookup, world  # noqa: F401  (격리 DB 에 여행 하나를 만드는 장면 재사용)


def _live(value="closed", mode="llm", applied=None, **extra):
    applied = (mode == "llm") if applied is None else applied
    return {"value": value, "mode": mode, "applied": applied, "visit_date": "2026-11-10",
            "checked_at": "2026-09-23T03:10:00+09:00", "citations": [{"url": "https://example.test/n", "quote": "임시 휴관"}], **extra}


def _ledger(monkeypatch, live):
    calls: list = []

    def state(conn, tenant_id, place_id, at, until=None, *, holiday=None):
        calls.append((tenant_id, place_id))
        return None if live is None else {"closed": False, "live_status": live}

    monkeypatch.setattr(activity_ledger, "state", state)
    return calls


def test_applied_llm_closed_becomes_a_closed_verdict_without_calling_anything_paid(world, monkeypatch):  # noqa: F811
    calls = _ledger(monkeypatch, _live("closed", "llm"))
    result = lookup(world, kind="activity")
    assert result["status"] == "closed" and result["source"] == "activity_live_status"
    assert result["reason"] == "verified_free" and result["paid_attempted"] is False
    assert result["checked_at"] == "2026-09-23T03:10:00+09:00"              # 저장된 확인 시각 — 지금(04:00)으로 바꾸지 않는다
    assert "live_status_reference" not in result and calls == [(world.tenant, str(world.meal.place["place_id"]))]


def test_shadow_closed_does_not_change_the_verdict_and_is_carried_as_a_reference(world, monkeypatch):  # noqa: F811
    _ledger(monkeypatch, _live("closed", "shadow"))
    result = lookup(world, kind="activity")
    assert result["status"] == "unverifiable" and result["reason"] == "free_unverifiable"     # 판정은 그대로 모름
    ref = result["live_status_reference"]
    assert ref["value"] == "closed" and ref["mode"] == "shadow" and ref["applied"] is False
    assert ref["citations"] and ref["checked_at"] == "2026-09-23T03:10:00+09:00"


def test_a_future_checked_at_is_not_trusted(world, monkeypatch):  # noqa: F811
    """저장된 확인 시각이 지금보다 미래(시계 어긋남)면 그 시각을 믿지 않고 지금으로 둔다 — 정책 검사(확인 시각 ≤ 지금)에서 걸러지지 않게."""
    _ledger(monkeypatch, _live("closed", "llm", checked_at="2026-09-24T03:10:00+09:00"))
    result = lookup(world, kind="activity")
    assert result["status"] == "closed" and result["checked_at"] == world.now.isoformat()


@pytest.mark.parametrize("live", [_live("open", "llm"), _live("unknown", "llm"), _live("unchecked", "llm"),
                                  _live("open", "shadow"), _live("unchecked", "shadow"),
                                  _live("closed", "llm", applied=False)], ids=lambda v: f"{v['value']}-{v['mode']}-{v['applied']}")
def test_other_values_are_neither_closed_nor_open_and_leave_no_reference(world, monkeypatch, live):  # noqa: F811
    _ledger(monkeypatch, live)
    result = lookup(world, kind="activity")
    assert result["status"] == "unverifiable" and "live_status_reference" not in result


@pytest.mark.parametrize("state", [None, {"closed": False}])
def test_no_live_status_column_changes_nothing(world, monkeypatch, state):  # noqa: F811
    monkeypatch.setattr(activity_ledger, "state", lambda *a, **k: state)
    result = lookup(world, kind="activity")
    assert result["status"] == "unverifiable" and "live_status_reference" not in result


def test_dining_never_reads_the_activity_ledger(world, monkeypatch):  # noqa: F811
    calls = _ledger(monkeypatch, _live("closed", "llm"))
    result = lookup(world, kind="dining")
    assert calls == [] and result.get("source") != "activity_live_status"


def test_dawn_check_collects_shadow_references_but_does_not_count_them(world, monkeypatch):  # noqa: F811
    """새벽 확인: 섀도 「닫힘」은 `references` 에 쌓이고 건수(`counts`)·닫힌 곳(`closed`)에는 들어가지 않는다. 활동 항목만 이 길을 탄다."""
    w = world
    _ledger(monkeypatch, _live("closed", "shadow"))
    runner = DawnCheck(store=w.store, connection_factory=get_connection, clock=Clock(w.now), source=None,
                       place_status=PlaceStatus(get_connection))
    activity_titles = {i.title for i in _items(w) if i.kind == "activity"}       # 닫힘이 바꿔 놓기 전의 제목
    assert activity_titles, "시험 장면에 활동 항목이 있어야 한다"
    result = runner.tick()
    assert result.references and {r["item"] for r in result.references} <= activity_titles
    assert all(r["live_status"]["mode"] == "shadow" and r["live_status"]["applied"] is False for r in result.references)
    assert not any(c["item"] in activity_titles for c in result.closed)         # 판정에 반영되지 않았다
    assert "references" not in result.counts()


def test_dawn_check_applied_llm_closed_is_a_closed_verdict(world, monkeypatch):  # noqa: F811
    w = world
    _ledger(monkeypatch, _live("closed", "llm"))
    runner = DawnCheck(store=w.store, connection_factory=get_connection, clock=Clock(w.now), source=None,
                       place_status=PlaceStatus(get_connection))
    activity_titles = {i.title for i in _items(w) if i.kind == "activity"}       # 닫힘이 일정을 바꾸기 전의 제목
    result = runner.tick()
    assert result.closed and {c["item"] for c in result.closed} <= activity_titles
    assert all(c["detail"] == "웹 공지 임시 휴무 확인" for c in result.closed) and not result.references
    with get_connection() as conn:
        sources = {r[0] for r in conn.execute("SELECT source FROM place_open_checks WHERE tenant_id=%s AND verdict='closed'",
                                              (w.tenant,)).fetchall()}
    assert sources == {"activity_live_status"}


def _items(w):
    with get_connection() as conn:
        _, items = w.store.latest(conn, w.trip)
    return items

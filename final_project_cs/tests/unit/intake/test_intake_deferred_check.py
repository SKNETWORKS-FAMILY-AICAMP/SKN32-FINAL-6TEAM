# -*- coding: utf-8 -*-
"""수정 화면은 저장만 하고 검사는 「다시 제출」 때 한 번 — 2026-10-20 사용자 지시.

「시간을 바꾸면 서버로 넘어가면서 지연이 생긴다 · 체크는 마지막에 제출 누를 때 한 번에」: 확인 화면의 고치기(`edits` 의 `check: false`)는
이동 계산기를 부르지 않는 미룬 검사(`review.ensure(quick=True)`)로 새 판을 남기고, 그 판은 `checked: false` · `ready: false` 라 등록되지 않는다.
재검증(`force`)은 계산기로 다시 잰다. 옛 저장본(칸 없음)은 검사된 것으로 읽는다.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.domains.travel_ops.components.intake import review, risks


@pytest.fixture()
def built(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake_build(conn, **kwargs):
        calls.append(kwargs)
        return {"revision": kwargs["revision"], "items": [], "moves": [], "needs": {"total": 0}, "ready": True}

    monkeypatch.setattr(review, "build", fake_build)
    monkeypatch.setattr(review, "load", lambda *a, **k: None)
    monkeypatch.setattr(review, "store", lambda *a, **k: None)

    def fake_decorate(conn, *, tenant_id, review, mode, reuse=None):
        calls.append({"risk_mode": mode})
        return review

    monkeypatch.setattr(risks, "decorate", fake_decorate)
    return calls


def test_quick_check_skips_the_move_engine_and_is_not_ready(built: list[dict[str, Any]]) -> None:
    payload = review.ensure(object(), tenant_id="t", intake_id="i", revision=4, sources=[], claims=[], force=True, quick=True)
    assert built[-2]["use_engine"] is False and built[-2]["engine"] is None
    assert built[-1]["risk_mode"] == "cached"                  # 위험(날씨 · 재난)도 바깥 조회 없이 저장해 둔 값만
    assert payload["checked"] is False and payload["ready"] is False
    assert review.unchecked(payload)


def test_full_check_is_marked_checked_and_keeps_ready(built: list[dict[str, Any]]) -> None:
    payload = review.ensure(object(), tenant_id="t", intake_id="i", revision=4, sources=[], claims=[], force=True)
    assert "use_engine" not in built[-2]
    assert built[-1]["risk_mode"] == "fresh"
    assert payload["checked"] is True and payload["ready"] is True
    assert not review.unchecked(payload)


def test_an_older_stored_check_without_the_field_counts_as_checked() -> None:
    assert not review.unchecked({"revision": 2, "ready": True})
    assert not review.unchecked(None)


def test_edit_request_checks_unless_told_not_to() -> None:
    from app.domains.travel_ops.entry.trip_api import IntakeEditIn

    edit = {"source_id": "s", "field": "items[0].starts_at", "value": "13:00"}
    assert IntakeEditIn.model_validate({"revision": 3, "edits": [edit]}).check is True
    assert IntakeEditIn.model_validate({"revision": 3, "edits": [edit], "check": False}).check is False

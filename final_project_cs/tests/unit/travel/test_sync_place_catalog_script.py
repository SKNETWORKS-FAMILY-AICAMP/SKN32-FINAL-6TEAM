# -*- coding: utf-8 -*-
"""`scripts/sync_place_catalog.py` — 장소 목록 적재 실행 껍데기. `[2026-10-05]` (활동 팀 develop 에서 옮김)

관광공사를 실제로 부르지 않는다 — 껍데기가 동기화 객체를 **올바른 방식으로** 부르는지만 본다."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts import sync_place_catalog as script


class _Syncer:
    def __init__(self, fail_on: str | None = None) -> None:
        self.calls, self.fail_on = [], fail_on

    @staticmethod
    def _outcome(rows: int):
        return SimpleNamespace(rows_written=rows, finished=True, pages_fetched=1, note=None, delta_trusted=None)

    def run(self, code, *, max_pages):
        self.calls.append(("run", code, max_pages))
        if code == self.fail_on:
            raise RuntimeError("secret 키 값이 든 문구")
        return self._outcome(10)

    def audit(self, code, *, max_pages):
        self.calls.append(("audit", code, max_pages))
        return self._outcome(0)

    def _load_state(self, code):
        return {"state": code}

    def _delta(self, code, state):
        self.calls.append(("delta", code, state))
        return self._outcome(3)


@pytest.fixture
def syncer(monkeypatch):
    fake = _Syncer()
    monkeypatch.setattr(script, "_load_source", lambda: object())
    monkeypatch.setattr(script, "_make_syncer", lambda source, tenant, size: fake)
    monkeypatch.setattr(script, "_class_counts", lambda tenant: (8006, [("SH", 4000)]))
    return fake


def test_default_is_seoul_bootstrap_with_five_pages(syncer, capsys):
    assert script.main([]) == 0
    assert syncer.calls == [("run", "1", 5)]
    assert "합계: 10행 저장" in capsys.readouterr().out


@pytest.mark.parametrize("mode, expected", [("audit", ("audit", "1", 30)), ("delta", ("delta", "1", {"state": "1"}))])
def test_other_modes(syncer, mode, expected):
    assert script.main(["--mode", mode, "--max-pages", "30"]) == 0
    assert syncer.calls == [expected]


def test_one_failing_area_does_not_stop_the_others_and_leaks_nothing(monkeypatch, capsys):
    fake = _Syncer(fail_on="2")
    monkeypatch.setattr(script, "_load_source", lambda: object())
    monkeypatch.setattr(script, "_make_syncer", lambda source, tenant, size: fake)
    assert script.main(["--area", "1", "2", "3"]) == 1                    # 실패가 있으면 0 으로 끝내지 않는다
    assert [c[1] for c in fake.calls] == ["1", "2", "3"]                  # 나머지 지역은 돌았다
    captured = capsys.readouterr()
    assert "FAIL  2(인천): RuntimeError" in captured.out
    assert "secret" not in captured.out + captured.err                    # 예외 문구(키가 들 수 있다)는 찍지 않는다


def test_missing_key_stops_before_any_call(monkeypatch):
    monkeypatch.setattr("app.core.settings.get_settings", lambda: SimpleNamespace(tour_api_key="", tenant_id="demo"))
    with pytest.raises(SystemExit) as stopped:
        script._load_source()
    assert stopped.value.code == 1

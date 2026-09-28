"""세는 것과 **알리는 것**은 다르다 — `errored` 가 실제로 밖으로 나가는가.

★2026-09-07 `final_project_cs` 에서 이식. 두 sweeper 는 `errored`(아무것도 기록하지 못한 수)를 정확히
  세고 로그에도 남겼는데, 실행기(`scripts/run_sweepers.py`)는 그걸 찍기만 하고
  **exit 0** 이었다. cron 에 걸어 두면 실패가 로그 속에만 남아 아무도 안 본다.
  `CLAUDE.md` §3 은 "실패를 세어 **보고**해야 한다" 고 적는다 — 세기만 한 상태였다.
  ★cs 에서 먼저 고쳤는데 여기가 그대로였다. **한쪽만 고쳐진** 자리가 또 하나.

★`errored` 와 `failed` 는 다르다. `failed` 는 실패를 **기록까지 한** 것이라
  Case 가 escalated 로 넘어가 사람 손에 들어간다. `errored` 는 Case 가 그 상태에
  그대로 남아 **다음 회차에 또 걸린다** — 아무도 안 보면 영원히 돈다.
"""
from __future__ import annotations

import json

import pytest

from scripts import run_sweepers


@pytest.fixture()
def tenant(monkeypatch):
    monkeypatch.setattr(run_sweepers, "get_settings",
                        lambda: type("S", (), {"tenant_id": "t-1"})())


def _once(monkeypatch, result):
    monkeypatch.setattr(run_sweepers, "_run_once", lambda _tenant, _only: result)
    monkeypatch.setattr("sys.argv", ["run_sweepers"])


def test_clean_pass_is_exit_zero_and_says_nothing_on_stderr(tenant, monkeypatch, capsys):
    _once(monkeypatch, {"classifying": {"scanned": 3, "classified": 3, "errored": 0},
                        "routing": {"scanned": 0, "started": 0, "errored": 0}})

    assert run_sweepers.main() == 0
    out = capsys.readouterr()
    assert json.loads(out.out)["classifying"]["classified"] == 3
    assert out.err == ""


def test_errored_makes_the_once_run_fail(tenant, monkeypatch, capsys):
    """★cron 은 exit code 만 본다. 여기서 0 을 내면 아무도 모른다."""
    _once(monkeypatch, {"classifying": {"scanned": 5, "classified": 3, "errored": 2},
                        "routing": {"scanned": 0, "started": 0, "errored": 0}})

    assert run_sweepers.main() == 1
    err = capsys.readouterr().err
    assert "classifying" in err and "errored=2" in err
    # 안 터진 sweeper 를 굳이 시끄럽게 하지 않는다
    assert "routing" not in err


def test_stdout_stays_one_json_line_even_when_something_errored(tenant, monkeypatch, capsys):
    """★사유는 stderr 로 간다. stdout 이 JSON 한 줄이라는 계약이 깨지면
    파이프로 받아 쓰는 쪽이 깨진다."""
    _once(monkeypatch, {"routing": {"scanned": 1, "started": 0, "errored": 1}})

    run_sweepers.main()
    out = capsys.readouterr()
    assert len(out.out.strip().splitlines()) == 1
    assert json.loads(out.out)["routing"]["errored"] == 1


def test_resident_mode_does_not_die_on_errors(tenant, monkeypatch, capsys):
    """★상주 sweeper 가 첫 실패에 멈추면 **되잡기 자체가 멈춘다.** 멈춘 Case 를
    되잡는 장치가 멈추는 것이 더 나쁘다 — 알리고 계속 돈다."""
    calls = {"n": 0}

    def _run(_tenant, _only):
        calls["n"] += 1
        return {"routing": {"scanned": 1, "started": 0, "errored": 1}}

    def _sleep(_seconds):
        if calls["n"] >= 3:
            raise KeyboardInterrupt  # 세 회차를 돌린 뒤에만 빠져나온다

    monkeypatch.setattr(run_sweepers, "_run_once", _run)
    monkeypatch.setattr(run_sweepers.time, "sleep", _sleep)
    monkeypatch.setattr("sys.argv", ["run_sweepers", "--interval", "1"])

    with pytest.raises(KeyboardInterrupt):
        run_sweepers.main()

    assert calls["n"] == 3, "errored 가 나와도 다음 회차를 돌아야 한다"
    assert capsys.readouterr().err.count("errored=1") == 3

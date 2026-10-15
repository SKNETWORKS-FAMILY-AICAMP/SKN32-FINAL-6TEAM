"""팀이 끼우는 정기 작업 — 코어를 고치지 않고 배치를 더하고, 새벽 정기 점검 시간대에만 돈다. `[2026-10-13]`

★왜. 작업 실행기에 작업 이름이 전부 고정돼 있어, 활동 팀의 웹 확인 배치 · 장소 갱신 스크립트가 손으로 돌리는 채로 남았다
  (활동 → 코어 전달 사항 10-13 2번). 이제 팀이 `instances/<팀>/jobs.py` 에 `JOBS` 를 두면 조립이 등록하고 실행기가 부른다.
"""
from __future__ import annotations

import sys
import types
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.team_hooks import scheduled_jobs
from app.domains.travel_ops.components.team_hooks.scheduled_jobs import TeamJob
from scripts import run_sweepers

KST = ZoneInfo("Asia/Seoul")


@pytest.fixture(autouse=True)
def _clean():
    scheduled_jobs.clear()
    yield
    scheduled_jobs.clear()


def _job(calls, window="dawn"):
    return TeamJob(name="fake_live_status", window=window,
                   tick=lambda tenant_id, now: calls.append((tenant_id, now)) or {"checked": 2, "left": 0})


def test_a_job_runs_inside_the_dawn_window_and_not_outside():
    calls = []
    job = _job(calls)
    inside = run_sweepers._run_team_job("t-1", job, now=datetime(2026, 10, 14, 3, 30, tzinfo=KST))
    outside = run_sweepers._run_team_job("t-1", job, now=datetime(2026, 10, 14, 15, 0, tzinfo=KST))
    assert inside == {"checked": 2, "left": 0}
    assert outside == {"outside_window": 1}
    assert [tenant for tenant, _ in calls] == ["t-1"]                  # 시간대 밖에서는 부르지 않았다


def test_the_window_end_is_not_inside():
    calls = []
    assert run_sweepers._run_team_job("t-1", _job(calls), now=datetime(2026, 10, 14, 8, 0, tzinfo=KST)) == {"outside_window": 1}


def test_forced_run_ignores_the_window():
    calls = []
    assert run_sweepers._run_team_job("t-1", _job(calls), forced=True,
                                      now=datetime(2026, 10, 14, 15, 0, tzinfo=KST)) == {"checked": 2, "left": 0}


def test_an_unknown_window_does_not_run():
    """모르는 시간대를 「언제나」로 읽지 않는다 — 실행기가 그 작업을 실패로 센다."""
    calls = []
    with pytest.raises(Exception):
        run_sweepers._run_team_job("t-1", _job(calls, window="no_such_window"), now=datetime(2026, 10, 14, 3, 30, tzinfo=KST))
    assert calls == []


def test_a_window_over_midnight():
    at = lambda h: datetime(2026, 10, 14, h, 0, tzinfo=KST)        # noqa: E731
    assert run_sweepers._in_window(at(23), "22:00", "02:00") and run_sweepers._in_window(at(1), "22:00", "02:00")
    assert not run_sweepers._in_window(at(3), "22:00", "02:00")


def test_assembly_registers_the_jobs_of_an_active_team_without_core_changes(monkeypatch):
    """팀 폴더에 `jobs.py` 만 두면 등록된다. 정기 작업이 없는 팀(파일 없음)은 조용히 건너뛴다 — 그건 오류가 아니다."""
    from app import composition

    calls = []
    package = types.ModuleType("app.domains.travel_ops.instances.fake_team")
    package.__path__ = []
    jobs = types.ModuleType("app.domains.travel_ops.instances.fake_team.jobs")
    jobs.JOBS = [_job(calls)]
    monkeypatch.setitem(sys.modules, package.__name__, package)
    monkeypatch.setitem(sys.modules, jobs.__name__, jobs)

    composition._wire_domain_providers(active_ids={"fake_team", "team_without_jobs"})

    assert [job.name for job in scheduled_jobs.registered()] == ["fake_live_status"]


def test_a_broken_jobs_file_is_not_hidden(monkeypatch):
    """`jobs.py` 안의 import 가 깨졌으면 기동을 멈춘다 — 「작업이 없는 팀」으로 숨기지 않는다."""
    import importlib

    from app import composition

    real = importlib.import_module

    def broken(name, *args, **kwargs):
        if name == "app.domains.travel_ops.instances.fake_team.jobs":
            raise ModuleNotFoundError("No module named 'requests_oauthlib'", name="requests_oauthlib")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(composition.importlib, "import_module", broken)
    with pytest.raises(ModuleNotFoundError):
        composition._wire_domain_providers(active_ids={"fake_team"})


def test_the_runner_accepts_a_team_job_name(monkeypatch):
    seen = []
    monkeypatch.setattr(run_sweepers, "get_settings", lambda: type("S", (), {"tenant_id": "t-1"})())
    monkeypatch.setattr(run_sweepers, "_round_result", lambda tenant, only: seen.append(only) or {})
    monkeypatch.setattr("sys.argv", ["run_sweepers", "--only", "team:fake_live_status"])
    assert run_sweepers.main() == 0 and seen == ["team:fake_live_status"]

def test_running_one_team_job_by_hand_goes_through_the_assembly(monkeypatch):
    """`--only team:<이름>` 도 조립 판 안에서 돈다 — 작업 목록이 거기에만 있다. `[2026-10-14]` 전에는 조립 없이 돌아 빈 결과로 끝났다."""
    seen = []
    monkeypatch.setattr(run_sweepers, "_run_bound_once", lambda tenant_id, only: seen.append(only) or {"bound": {}})
    assert run_sweepers._run_once("demo", "team:activity_live_status") == {"bound": {}}
    assert seen == ["team:activity_live_status"]

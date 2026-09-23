# -*- coding: utf-8 -*-
"""상시 작업의 세 가지 안전장치 — 겹침 막기 · 로그 정리 · 연속 실패 알림.

★`[2026-09-22]` 1분마다 도는 작업을 스케줄러에 걸면 따라오는 것들이다. 겹치면 바깥 API 를 두 번
  부르고(한도를 갉는다), 로그는 지우는 사람 없이 쌓이며, 실패는 스케줄러의 「마지막 결과」에만 남아
  사람이 그 화면을 안 보면 며칠이 지난다 — 바깥함 일꾼이 실제로 4시간 넘게 그랬다.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

import pytest

from scripts.ops.guard import ALERT_AFTER, Skipped, note_result, only_one, prune_logs


# ── 겹침 ───────────────────────────────────────────────────────
def test_a_second_run_is_skipped_while_the_first_holds_the_lock(tmp_path):
    lock = tmp_path / "sweepers.lock"
    with only_one(lock):
        assert lock.exists()
        with pytest.raises(Skipped, match="앞 회차가 아직 돈다"):
            with only_one(lock):
                pytest.fail("겹쳐 들어왔다")
    assert not lock.exists(), "끝나면 잠금을 놓아야 한다"


def test_a_lock_left_by_a_dead_run_does_not_block_forever(tmp_path):
    """★죽은 회차가 남긴 잠금이 영영 막으면 그 작업은 다시는 안 돈다."""
    lock = tmp_path / "outbox.lock"
    lock.write_text(json.dumps({"pid": 999_999_999, "since": datetime.now().timestamp()}),
                    encoding="utf-8")
    with only_one(lock):
        held = json.loads(lock.read_text(encoding="utf-8"))
        assert held["pid"] == os.getpid(), "죽은 회차의 잠금을 빼앗아야 한다"


def test_a_lock_that_is_too_old_is_taken_even_if_the_pid_is_alive(tmp_path):
    """매달린 회차(살아 있지만 상한을 넘김)도 다음 회차를 영영 막지 못한다."""
    lock = tmp_path / "app.lock"
    stale = (datetime.now() - timedelta(hours=2)).timestamp()
    lock.write_text(json.dumps({"pid": os.getpid(), "since": stale}), encoding="utf-8")
    with only_one(lock, stale_seconds=600):
        assert json.loads(lock.read_text(encoding="utf-8"))["pid"] == os.getpid()


# ── 로그 정리 ──────────────────────────────────────────────────
def test_old_logs_go_and_recent_ones_stay(tmp_path):
    old, new = tmp_path / "sweepers-20260101.log", tmp_path / "sweepers-오늘.log"
    old.write_text("옛 기록", encoding="utf-8")
    new.write_text("새 기록", encoding="utf-8")
    long_ago = (datetime.now() - timedelta(days=90)).timestamp()
    os.utime(old, (long_ago, long_ago))

    removed = prune_logs(tmp_path, keep_days=14)

    assert removed == [old.name] and not old.exists()
    assert new.exists(), "최근 로그를 지우면 안 된다"


def test_pruning_reports_what_it_removed(tmp_path):
    """★조용히 지우지 않는다 — 무엇을 지웠는지 돌려준다(CLAUDE.md §3)."""
    assert prune_logs(tmp_path / "없는폴더") == []


# ── 연속 실패 알림 ─────────────────────────────────────────────
def test_one_failure_does_not_alert_but_a_streak_does(tmp_path):
    for attempt in range(1, ALERT_AFTER):
        verdict = note_result(tmp_path, "outbox", exit_code=1, detail="DB 연결 실패")
        assert verdict["should_alert"] is False, f"{attempt}회째에 알리면 시끄럽다"
    verdict = note_result(tmp_path, "outbox", exit_code=1, detail="DB 연결 실패")
    assert verdict == {"streak": ALERT_AFTER, "should_alert": True, "kind": "failing"}


def test_it_alerts_once_per_streak_not_every_minute(tmp_path):
    """★1분마다 도는 작업이 실패하면 하루 1,440건이 나간다 — 연속 실패는 **한 번만** 알린다."""
    for _ in range(ALERT_AFTER):
        note_result(tmp_path, "sweepers", exit_code=1)
    again = [note_result(tmp_path, "sweepers", exit_code=1) for _ in range(5)]
    assert [v["should_alert"] for v in again] == [False] * 5
    assert again[-1]["streak"] == ALERT_AFTER + 5


def test_coming_back_is_announced_once_and_only_if_we_had_alerted(tmp_path):
    for _ in range(ALERT_AFTER):
        note_result(tmp_path, "app", exit_code=1)
    back = note_result(tmp_path, "app", exit_code=0)
    assert back["kind"] == "recovered" and back["streak"] == 0
    assert note_result(tmp_path, "app", exit_code=0)["should_alert"] is False, "평소 성공에 알리면 안 본다"


def test_a_success_without_a_previous_alert_says_nothing(tmp_path):
    assert note_result(tmp_path, "daily_feedback", exit_code=0)["should_alert"] is False
    assert note_result(tmp_path, "daily_feedback", exit_code=1)["should_alert"] is False
    assert note_result(tmp_path, "daily_feedback", exit_code=0)["should_alert"] is False


def test_without_a_place_to_send_it_says_so_instead_of_pretending(monkeypatch):
    """★보낼 곳이 없으면 **조용히 성공하지 않는다** — 안 보냈다고 말한다(RULE §3.2)."""
    from app.core import settings as settings_module
    from scripts.ops import guard

    original = settings_module.get_settings()
    patched = original.model_copy(update={"discord_webhook_url": "", "ops_alert_webhook_url": ""})
    monkeypatch.setattr(settings_module, "get_settings", lambda: patched)
    assert "보낼 곳이 없다" in guard.send_alert("outbox", "failing", streak=3)


# ── 등록 대상 고르기 (2026-09-22) ──────────────────────────────
def test_only_accepts_both_a_comma_list_and_repeated_flags():
    """★`--only a --only b --only c` 가 **조용히 마지막 하나**로 줄어 셋 중 둘이 안 걸렸다."""
    from scripts.ops.jobs import select

    assert [j.name for j in select("sweepers,outbox")] == ["sweepers", "outbox"]
    assert [j.name for j in select(["sweepers", "outbox", "daily_feedback"])] == \
        ["sweepers", "outbox", "daily_feedback"]
    assert [j.name for j in select(["sweepers,outbox", "daily_feedback", "outbox"])] == \
        ["sweepers", "outbox", "daily_feedback"], "같은 이름을 두 번 줘도 두 번 걸지 않는다"


def test_an_unknown_job_name_stops_instead_of_being_skipped():
    from scripts.ops.jobs import select

    with pytest.raises(SystemExit, match="모르는 작업 이름"):
        select(["sweepers", "없는작업"])


def test_the_app_job_uses_the_public_base_url_port():
    """★앱 포트와 공개 주소가 어긋나면 통지에 실린 계획서 링크가 죽은 주소를 가리킨다."""
    from app.core.settings import get_settings
    from scripts.ops.jobs import JOBS

    port = str(get_settings().public_base_url).rsplit(":", 1)[-1].strip("/")
    assert port in JOBS["app"].argv, (port, JOBS["app"].argv)


def test_writing_output_never_kills_a_windowless_run(monkeypatch):
    """★`pythonw` 로 창 없이 돌면 `sys.stdout` 이 None 이다 — 찍다가 죽으면 스케줄러가 실패로 본다.

    실제로 등록 직후 그렇게 났다: 로그·흔적에는 `exit=0` 이 적혔는데 작업 스케줄러의
    「마지막 결과」는 1 이었다. 기록을 남긴 **뒤** 출력에서 죽었기 때문이다.
    """
    import sys as _sys

    from scripts.ops import tick

    monkeypatch.setattr(_sys, "stdout", None)
    monkeypatch.setattr(_sys, "stderr", None)
    tick.say("창이 없어도 죽지 않는다")
    tick.say("표준 오류도 마찬가지", err=True)


def test_a_closed_pipe_does_not_kill_it_either(monkeypatch):
    import io
    import sys as _sys

    from scripts.ops import tick

    closed = io.StringIO()
    closed.close()
    monkeypatch.setattr(_sys, "stdout", closed)
    tick.say("닫힌 파이프")

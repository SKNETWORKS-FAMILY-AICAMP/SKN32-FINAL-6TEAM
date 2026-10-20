"""배포 공지 상태 쓰기(`deploy/deploy_notice.py`, D-CS-019) — 배포 스크립트가 단계마다 부르는 표준 라이브러리 도구."""
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('deploy_notice', Path(__file__).resolve().parents[3] / 'deploy/deploy_notice.py')
notice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notice)

T0 = datetime(2026, 10, 20, 14, 5, 0, tzinfo=notice.KST)


def read(directory):
    return json.loads((directory / notice.NOTICE).read_text(encoding='utf-8'))


def test_whole_successful_deploy_walks_preparing_switching_done(tmp_path):
    first = notice.begin(tmp_path, '09bf0dad1234567', at=T0)
    assert first['phase'] == 'preparing' and first['step'] == 'build'
    assert first['deploy_id'] == f'09bf0dad12-{int(T0.timestamp())}'
    assert first['started_at'] == '2026-10-20T14:05:00+09:00'          # 한국 시각 원값
    assert first['expected_outage_seconds'] == notice.DEFAULT_OUTAGE_SECONDS
    notice.step(tmp_path, 'migrate', at=T0 + timedelta(minutes=4))
    assert read(tmp_path)['phase'] == 'preparing'
    notice.step(tmp_path, 'switch', at=T0 + timedelta(minutes=5))
    assert read(tmp_path)['phase'] == 'switching'
    notice.end(tmp_path, 'done', at=T0 + timedelta(minutes=6, seconds=30))
    final = read(tmp_path)
    assert final['phase'] == 'done' and final['finished_at'] == '2026-10-20T14:11:30+09:00'
    assert json.loads((tmp_path / notice.HISTORY).read_text(encoding='utf-8')) == [90]
    # 다음 배포는 지난 실측으로 끊김을 예상한다
    assert notice.begin(tmp_path, 'abcdef1234', at=T0 + timedelta(hours=1))['expected_outage_seconds'] == 90


def test_failure_before_switch_keeps_previous_and_does_not_count_as_outage(tmp_path):
    notice.begin(tmp_path, 'a' * 10, at=T0)
    notice.step(tmp_path, 'migrate', at=T0 + timedelta(minutes=3))
    notice.end(tmp_path, 'kept_previous', at=T0 + timedelta(minutes=6))
    assert read(tmp_path)['phase'] == 'kept_previous'
    assert not (tmp_path / notice.HISTORY).exists()


def test_outage_estimate_takes_the_worst_recent_switch_within_bounds(tmp_path):
    (tmp_path / notice.HISTORY).write_text(json.dumps([400, 20, 50, 70, 60, 80]), encoding='utf-8')
    assert notice.expected_outage(tmp_path) == 80            # 최근 5개만, 그 최댓값
    (tmp_path / notice.HISTORY).write_text(json.dumps([10]), encoding='utf-8')
    assert notice.expected_outage(tmp_path) == 30            # 아래 한계
    (tmp_path / notice.HISTORY).write_text(json.dumps([900]), encoding='utf-8')
    assert notice.expected_outage(tmp_path) == 300           # 위 한계
    (tmp_path / notice.HISTORY).write_text('not json', encoding='utf-8')
    assert notice.expected_outage(tmp_path) == notice.DEFAULT_OUTAGE_SECONDS


def test_step_or_end_without_a_running_notice_refuses(tmp_path):
    with pytest.raises(SystemExit):
        notice.step(tmp_path, 'switch')
    notice.begin(tmp_path, 'b' * 10, at=T0)
    notice.end(tmp_path, 'done', at=T0)
    with pytest.raises(SystemExit):                          # 끝난 공지를 다시 끝내지 않는다
        notice.end(tmp_path, 'trouble')


def test_write_replaces_the_file_whole_and_leaves_no_temporary(tmp_path):
    notice.begin(tmp_path, 'c' * 10, at=T0)
    notice.step(tmp_path, 'switch', at=T0)
    assert sorted(p.name for p in tmp_path.iterdir()) == [notice.NOTICE]


def test_command_line(tmp_path, capsys):
    notice.main(['--dir', str(tmp_path), 'begin', '--sha', 'd' * 40])
    notice.main(['--dir', str(tmp_path), 'step', 'switch'])
    notice.main(['--dir', str(tmp_path), 'end', 'trouble'])
    assert read(tmp_path)['phase'] == 'trouble'
    assert '배포 공지: trouble' in capsys.readouterr().out

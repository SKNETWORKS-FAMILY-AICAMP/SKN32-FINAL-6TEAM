"""배포 공지(D-CS-019) — 자동 배포가 쓴 상태 파일 → 정해 둔 문구의 고객 공지 한 건 → 고객 공지 경로(`GET /v1/web/support/notices`)의 맨 앞."""
import importlib.util
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application import deploy_notice
from app.domains.travel_ops.modules.web_account import admin_customer_api

spec = importlib.util.spec_from_file_location('deploy_notice_writer', Path(__file__).resolve().parents[2] / 'deploy/deploy_notice.py')
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)

T0 = datetime(2026, 10, 20, 14, 5, 0, tzinfo=writer.KST)


def notice_at(directory, now):
    return deploy_notice.current_notice(now, directory / writer.NOTICE)


def test_no_file_means_no_notice(tmp_path):
    assert notice_at(tmp_path, T0) is None


def test_each_phase_has_its_own_fixed_words_in_korean_and_english(tmp_path):
    writer.begin(tmp_path, '09bf0dad12', at=T0)
    preparing = notice_at(tmp_path, T0 + timedelta(minutes=1))
    assert preparing['id'] == f'deploy:09bf0dad12-{int(T0.timestamp())}:preparing'
    assert preparing['kind'] == '점검 예고' and preparing['title'] == '곧 새 판으로 바뀌어요'
    assert '14:05에 시작한 준비' in preparing['body'] and '약 2분' in preparing['body']        # 시각은 파일 값 그대로 · 120초 = 2분
    assert '14:05 KST' in preparing['bodyEn'] and 'about 2 min' in preparing['bodyEn']
    assert preparing['startsAt'] == '2026-10-20T14:05' and preparing['endsAt'] is None
    writer.step(tmp_path, 'switch', at=T0 + timedelta(minutes=6))
    switching = notice_at(tmp_path, T0 + timedelta(minutes=6))
    assert switching['title'] == '새 판으로 바꾸는 중이에요' and switching['body'].startswith('14:11부터 약 2분')
    assert switching['id'] != preparing['id']                                                     # 앞 단계를 닫아도 새 단계는 다시 뜬다
    writer.end(tmp_path, 'done', at=T0 + timedelta(minutes=7, seconds=30))
    done = notice_at(tmp_path, T0 + timedelta(minutes=8))
    assert (done['kind'], done['title'], done['body']) == ('안내', '새 판으로 바뀌었어요', '14:12에 끝났어요. 계속 쓰시면 돼요.')
    assert done['titleEn'] == 'The new version is live'


def test_failed_update_says_the_previous_version_stays(tmp_path):
    writer.begin(tmp_path, 'a' * 10, at=T0)
    writer.end(tmp_path, 'kept_previous', at=T0 + timedelta(minutes=3))
    before_switch = notice_at(tmp_path, T0 + timedelta(minutes=3))
    assert before_switch['title'] == '이번 업데이트는 미뤘어요' and '이용에는 영향이 없어요' in before_switch['body']
    writer.begin(tmp_path, 'b' * 10, at=T0)
    writer.step(tmp_path, 'switch', at=T0 + timedelta(minutes=5))
    writer.end(tmp_path, 'kept_previous', at=T0 + timedelta(minutes=9))
    rolled_back = notice_at(tmp_path, T0 + timedelta(minutes=9))
    assert '14:14에 원래 판으로 되돌렸어요' in rolled_back['body']
    writer.begin(tmp_path, 'c' * 10, at=T0)
    writer.step(tmp_path, 'switch', at=T0 + timedelta(minutes=5))
    writer.end(tmp_path, 'trouble', at=T0 + timedelta(minutes=9))
    trouble = notice_at(tmp_path, T0 + timedelta(minutes=20))
    assert trouble['kind'] == '기능 차질·장애' and trouble['body'].startswith('14:14부터 일부 기능')


@pytest.mark.parametrize('outcome, shown_for', [('done', 5), ('kept_previous', 5), ('trouble', 30)])
def test_ended_notice_goes_away_by_itself(tmp_path, outcome, shown_for):
    writer.begin(tmp_path, 'd' * 10, at=T0)
    writer.end(tmp_path, outcome, at=T0)
    assert notice_at(tmp_path, T0 + timedelta(minutes=shown_for) - timedelta(seconds=1)) is not None
    assert notice_at(tmp_path, T0 + timedelta(minutes=shown_for, seconds=1)) is None


def test_a_deploy_that_stopped_updating_is_not_shown(tmp_path):
    writer.begin(tmp_path, 'e' * 10, at=T0)
    assert notice_at(tmp_path, (T0 + timedelta(minutes=29)).astimezone(timezone.utc)) is not None
    assert notice_at(tmp_path, (T0 + timedelta(minutes=31)).astimezone(timezone.utc)) is None


def test_broken_file_is_logged_not_silently_ignored(tmp_path, caplog):
    path = tmp_path / writer.NOTICE
    for content in ('{not json', json.dumps({'phase': 'switching'}), json.dumps({'phase': 'party', 'deploy_id': 'x'})):
        path.write_text(content, encoding='utf-8')
        assert deploy_notice.current_notice(T0, path) is None
    assert caplog.text.count('배포 공지 파일') == 3


def test_public_notices_put_the_deploy_notice_first(tmp_path, monkeypatch):
    @contextmanager
    def connection():
        yield None
    operator = {'id': 'n1', 'kind': '안내', 'title': '운영자 공지', 'body': '본문', 'audience': 'all', 'author': 'ops',
                'startsAt': '2000-01-01T00:00', 'endsAt': '2999-01-01T00:00'}
    monkeypatch.setattr(admin_customer_api, 'get_connection', connection)
    monkeypatch.setattr(admin_customer_api.admin_service, 'records', lambda conn, tenant, kind: [operator])
    monkeypatch.setattr(admin_customer_api.admin_service, 'record', lambda conn, tenant, kind, key: None)
    app = FastAPI(); app.include_router(admin_customer_api.build_router())
    client = TestClient(app)
    monkeypatch.setattr(deploy_notice, 'current_notice', lambda now, path=None: None)
    assert [n['id'] for n in client.get('/v1/web/support/notices').json()['notices']] == ['n1']
    writer.begin(tmp_path, 'f' * 10, at=datetime.now(writer.KST))
    monkeypatch.setattr(deploy_notice, 'current_notice', lambda now, path=None: deploy_notice.customer_notice(
        deploy_notice.read_state(tmp_path / writer.NOTICE, now)))
    notices = client.get('/v1/web/support/notices').json()['notices']
    assert [n['title'] for n in notices] == ['곧 새 판으로 바뀌어요', '운영자 공지']
    assert 'author' not in notices[1]

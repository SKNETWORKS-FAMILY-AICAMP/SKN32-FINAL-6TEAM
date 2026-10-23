# -*- coding: utf-8 -*-
"""배포 공지(D-CS-019) — 배포 한 번에 공지사항 게시판 한 건. 진행 중엔 게시 중, 끝나면 종료, 단계가 바뀌어도 건이 늘지 않는다 `[2026-10-23 사용자 결정]`."""
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app.application import admin_service as admin
from app.application import deploy_notice
from app.infrastructure.db.session import get_connection

spec = importlib.util.spec_from_file_location('deploy_notice_writer', Path(__file__).resolve().parents[2] / 'deploy/deploy_notice.py')
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)


@pytest.fixture
def state():
    with get_connection() as conn:
        tenant = 'deploy_board_' + uuid4().hex
        conn.execute("INSERT INTO tenants(tenant_id,name) VALUES(%s,'배포 공지 시험')", (tenant,))
        try:
            yield conn, tenant
        finally:
            conn.rollback()


def board(conn, tenant, now):
    return admin.notice_board(conn, tenant, now)


def test_one_board_entry_per_deploy_from_start_to_end(state, tmp_path):
    conn, tenant = state
    path = tmp_path / writer.NOTICE
    t0 = datetime.now(writer.KST).replace(microsecond=0)
    writer.begin(tmp_path, 'a' * 10, at=t0)
    deploy_notice.sync_board(conn, tenant, path)
    deploy_notice.sync_board(conn, tenant, path)                                                       # 같은 상태를 다시 맞춰도 건이 늘지 않는다
    entries = board(conn, tenant, t0)
    assert len(entries) == 1 and entries[0]['status'] == 'posted' and entries[0]['title'] == '곧 새 판으로 바뀌어요'
    assert 'author' not in entries[0] and entries[0]['source'] == 'deploy'
    writer.step(tmp_path, 'switch', at=t0 + timedelta(minutes=1))
    deploy_notice.sync_board(conn, tenant, path)
    entries = board(conn, tenant, t0 + timedelta(minutes=1))
    assert len(entries) == 1 and entries[0]['status'] == 'posted' and entries[0]['title'] == '새 판으로 바꾸는 중이에요'
    writer.end(tmp_path, 'done', at=t0 + timedelta(minutes=3))
    deploy_notice.sync_board(conn, tenant, path)
    entries = board(conn, tenant, t0 + timedelta(minutes=4))
    assert len(entries) == 1 and entries[0]['status'] == 'ended' and entries[0]['title'] == '새 판으로 바뀌었어요'
    # 단계마다의 변화는 감사 기록에만 남는다(관리자 앱에서만 본다)
    audits = conn.execute("SELECT count(*) FROM admin_audit WHERE tenant_id=%s AND action='deploy-notice'", (tenant,)).fetchone()[0]
    assert audits == 3


def test_next_deploy_is_a_new_entry_and_the_old_one_stays_ended(state, tmp_path):
    conn, tenant = state
    path = tmp_path / writer.NOTICE
    t0 = datetime.now(writer.KST).replace(microsecond=0) - timedelta(hours=1)
    writer.begin(tmp_path, 'b' * 10, at=t0)
    writer.end(tmp_path, 'kept_previous', at=t0 + timedelta(minutes=2))
    deploy_notice.sync_board(conn, tenant, path)
    t1 = t0 + timedelta(minutes=50)
    writer.begin(tmp_path, 'c' * 10, at=t1)
    deploy_notice.sync_board(conn, tenant, path)
    entries = board(conn, tenant, t1 + timedelta(minutes=1))
    assert [e['status'] for e in entries] == ['posted', 'ended']                                       # 게시 중이 위, 종료가 아래
    assert entries[1]['title'] == '이번 업데이트는 미뤘어요'


def test_a_deploy_that_stopped_updating_ends_by_itself(state, tmp_path):
    conn, tenant = state
    path = tmp_path / writer.NOTICE
    t0 = datetime.now(writer.KST).replace(microsecond=0) - timedelta(hours=2)
    writer.begin(tmp_path, 'd' * 10, at=t0)
    deploy_notice.sync_board(conn, tenant, path)
    assert board(conn, tenant, t0 + timedelta(minutes=29))[0]['status'] == 'posted'
    assert board(conn, tenant, t0 + timedelta(minutes=31))[0]['status'] == 'ended'


def test_sync_without_a_state_file_writes_nothing(state, tmp_path):
    conn, tenant = state
    deploy_notice.sync_board(conn, tenant, tmp_path / writer.NOTICE)
    assert board(conn, tenant, datetime.now(writer.KST)) == []

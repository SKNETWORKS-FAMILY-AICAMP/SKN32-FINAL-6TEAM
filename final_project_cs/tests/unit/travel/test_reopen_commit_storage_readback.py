"""저장 실패 뒤 다시 읽기(공용 `reopen_commit.version_unchanged_after_failure`) — 채팅 고치기 · 웹 「일정 수정」 완료가 같이 쓴다.

`[2026-10-26 묶음 M]` 「일정은 바꾸지 않았어요」라고 답해도 되는지를 정하는 확인이다. 판 번호가 기준 그대로이고(trips 행 `FOR SHARE` 뒤),
웹 완료는 그 「완료」의 요청 id 판도 없어야 True. 다시 읽지 못하면 False(모른다). 로그엔 예외 종류만.
실제 두 연결 대기는 `tests/e2e/test_chat_edit_web.py::test_the_failure_readback_waits_for_an_unfinished_save_and_reports_what_it_became`,
웹 완료의 HTTP 503 은 `tests/e2e/test_trip_reopen.py::test_a_storage_failure_while_saving_done_is_an_explicit_unchanged_failure_not_a_500`.
"""
from contextlib import contextmanager
from uuid import uuid4

import psycopg
import pytest

from app.domains.travel_ops.components.intake import reopen_commit

PRIVATE = "CONTROLLED_PRIVATE_SQL_DETAIL params=(010-1234-5678)"


class _Conn:
    """다시 읽기 연결 — 실행한 SQL 을 적고 차례대로 `rows` 를 돌려준다. `broken` 이면 첫 문장에서 끊긴다."""

    def __init__(self, rows, sqls, broken=False):
        self.rows, self.sqls, self.broken = list(rows), sqls, broken

    @contextmanager
    def transaction(self):
        yield

    @contextmanager
    def cursor(self):
        yield self

    def execute(self, sql, params=None):
        self.sqls.append(sql)
        if self.broken:
            raise psycopg.OperationalError("connection lost " + PRIVATE)

    def fetchone(self):
        return self.rows.pop(0)


def _connect(rows, sqls, broken=False):
    @contextmanager
    def connect():
        yield _Conn(rows, sqls, broken)
    return connect


def test_the_same_version_and_no_version_for_this_done_means_unchanged():
    sqls = []
    assert reopen_commit.version_unchanged_after_failure(_connect([(3,), None], sqls), "t", uuid4(), 3,
                                                         request_id=reopen_commit.request_id_for(uuid4(), 2)) is True
    assert sqls[0] == f"SET LOCAL lock_timeout = '{reopen_commit.SETTLE_LOCK_TIMEOUT}'"
    assert "FROM trips" in sqls[1] and sqls[1].rstrip().endswith("FOR SHARE")
    assert "FROM itinerary_versions" in sqls[2] and "cause_json" in sqls[2]       # 같은 잠금 · 트랜잭션 안에서 본다


@pytest.mark.parametrize("rows,request_id", [([(4,), None], "intake:x:r1"), ([(3,), (4,)], "intake:x:r1"), ([None], None)],
                         ids=["moved", "this_done_was_saved", "trip_gone"])
def test_anything_but_the_same_version_without_this_done_is_not_unchanged(rows, request_id):
    assert reopen_commit.version_unchanged_after_failure(_connect(rows, []), "t", uuid4(), 3, request_id=request_id) is False


def test_without_a_request_id_only_the_version_is_read():
    # 채팅 고치기는 판 번호만 본다(묶음 L 그대로) — 요청 id 조회를 하지 않는다
    sqls = []
    assert reopen_commit.version_unchanged_after_failure(_connect([(3,)], sqls), "t", uuid4(), 3) is True
    assert len(sqls) == 2


def test_a_readback_that_fails_is_not_unchanged_and_logs_only_the_kind(caplog):
    assert reopen_commit.version_unchanged_after_failure(_connect([], [], broken=True), "t", uuid4(), 3,
                                                         request_id="intake:x:r1") is False
    assert "OperationalError" in caplog.text
    assert "010-1234-5678" not in caplog.text and "CONTROLLED_PRIVATE" not in caplog.text


def test_the_done_request_id_is_the_one_the_commit_writes():
    intake = uuid4()
    assert reopen_commit.request_id_for(intake, 7) == f"intake:{intake}:r7"

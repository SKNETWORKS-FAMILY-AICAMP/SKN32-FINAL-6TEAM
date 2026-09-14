"""`read_trace` 가 형식 아닌 run_id 를 실제 DB 에러와 구분하는지.

★실측했다 — postgres 는 UUID 형식이 아닌 값을 조회 전에
  `invalid input syntax for type uuid` 로 거부한다. 이걸 그대로 화면에 보이면
  "그런 실행이 없다" 인지 "값이 형식에 안 맞다" 인지 사용자가 구분 못 한다.
"""
from __future__ import annotations

from console.db import read_trace


def test_a_non_uuid_run_id_is_reported_before_hitting_the_database():
    result = read_trace("postgresql://nobody@127.0.0.1:1/none", "doesnotexist")
    assert result.status == "그 실행이 없다"
    assert "형식" in result.detail
    # ★DB 에 연결조차 시도하지 않는다 — 형식만으로 걸러진다
    # (연결 실패였다면 status 가 "연결하지 못했다" 였을 것이다)

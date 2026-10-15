# -*- coding: utf-8 -*-
"""시험이 `case_events` 를 정리할 때 쓰는 문 — `[2026-10-15]` 마이그레이션 904.

`case_events` 는 DB 가 추가만 하게 막는다(UPDATE · DELETE · TRUNCATE 거절). 시험이 자기 테넌트의 행을 치우려면
**지우기 직전, 같은 트랜잭션에서** 이 함수로 정리 스위치를 켠다. `SET LOCAL` 이라 트랜잭션이 끝나면 저절로 꺼진다.

★자동 커밋 연결에서는 효과가 없다(트랜잭션이 문장 하나로 끝난다) — `with conn.transaction():` 안에서 부른다.
"""
from __future__ import annotations


def allow_case_events_purge(cur) -> None:
    """이 트랜잭션에서만 `case_events` 의 DELETE · TRUNCATE 를 허용한다."""
    cur.execute("SET LOCAL app.case_events_purge = 'on'")


__all__ = ["allow_case_events_purge"]

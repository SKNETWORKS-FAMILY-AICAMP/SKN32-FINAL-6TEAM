"""운영자 전용 — 일정 감시에 보내지 않은 「기타」 재난 문자 현황 읽기 `[2026-10-13 사용자 결정]`. 외부 소스를 호출하지 않는다."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.errors import UndefinedTable

from app.domains.travel_ops.components.watch import notice_exclusions
from app.infrastructure.db.session import get_ops_read_connection


def build_router(*, operator_dependency, require_permission):
    router = APIRouter(prefix='/admin/api/notice-exclusions', tags=['operations-notice-exclusions'])

    @router.get('')
    def listing(op=Depends(operator_dependency), days: int = Query(30, ge=1, le=365), limit: int = Query(100, ge=1, le=500)):
        """최근 `days` 일 동안 걸러진 문자 — 본문 단위로 묶어 건수가 많은 순. 무슨 사안이 몇 번 왔는지 본다."""
        require_permission(op, 'ops:introspect')
        try:
            with get_ops_read_connection() as conn:
                return notice_exclusions.summary(conn, days=days, limit=limit)
        except UndefinedTable:
            raise HTTPException(503, '걸러진 재난 문자 기록 표가 아직 없습니다. 마이그레이션 903 을 적용해 주세요.') from None
        except Exception:
            raise HTTPException(503, '걸러진 재난 문자 기록을 읽지 못했습니다.') from None

    return router


__all__ = ['build_router']

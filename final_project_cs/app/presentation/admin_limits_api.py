"""운영자 전용 API 환경설정 한도 조회."""
from fastapi import APIRouter, Depends

from app.application.api_limits import snapshot
from app.infrastructure.db.session import get_connection


def build_router(*, operator_dependency, require_permission):
    router = APIRouter(prefix='/admin/api/api-limits', tags=['operations-api-limits'])

    @router.get('')
    def listing(op=Depends(operator_dependency)):
        require_permission(op, 'ops:introspect')
        return snapshot(connection_factory=get_connection)

    return router

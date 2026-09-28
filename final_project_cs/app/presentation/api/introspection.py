from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.introspection.contract import snapshot
from app.presentation.security import Principal, require_scope

router = APIRouter(tags=["introspection"])


@router.get("/introspection")
def introspection(request: Request,
                  principal: Principal = Depends(require_scope("ops:introspect"))):
    """조립 상태를 JSON 으로. ★고객 데이터도 비밀도 담지 않는다.

    ★`app.state.runtime` 에서 **실행 중인 조립**을 가져온다(2026-09-06, 계약 1.1).
      없으면 `None` 을 넘기고 `active_revision` 은 "모름" 이 된다 — 저장소에서
      읽은 값을 실행 중인 것으로 적지 않는다. 라우터를 직접 붙여 쓰는 테스트가
      아직 있어 `getattr` 로 받는다.
    """
    del principal
    return snapshot(runtime=getattr(request.app.state, "runtime", None))

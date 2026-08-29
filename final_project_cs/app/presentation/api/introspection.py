from __future__ import annotations

from fastapi import APIRouter, Depends

from app.introspection.contract import snapshot
from app.presentation.security import Principal, require_scope

router = APIRouter(tags=["introspection"])


@router.get("/introspection")
def introspection(principal: Principal = Depends(require_scope("ops:introspect"))):
    del principal
    return snapshot()

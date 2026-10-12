"""제품의 read-only 자기소개 표면.

★계약 본문은 `contract.py` 하나다. 여기서는 **재수출만** 한다 —
  한때 `__init__.py` 와 `contract.py` 에 `snapshot` 이 **둘 다** 정의돼 있었고,
  맨 아래 `from .contract import snapshot` 이 위쪽 정의를 조용히 덮었다.
  같은 이름이 두 곳에 있으면 어느 쪽이 도는지 아무도 모른다.
"""
from __future__ import annotations

from acop_basement.introspection.contract import (
    CONTRACT_VERSION,
    build_snapshot,
    describe,
    introspect,
    snapshot,
)

__all__ = ["CONTRACT_VERSION", "snapshot", "introspect", "build_snapshot", "describe"]

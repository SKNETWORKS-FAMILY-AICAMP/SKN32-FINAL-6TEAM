"""점검 Port가 시험 입력 공급자를 받는 중립 연결. 구현의 저장소는 알지 않는다."""
from __future__ import annotations

from typing import Any, Protocol


class SimulationProvider(Protocol):
    def resolve(self, place: dict) -> dict | None: ...

    def inputs(self, current: dict, place: dict, *, safety_only: bool = False) -> dict[str, dict]: ...

    def record_result(self, current: dict, report: dict, *, safety_only: bool) -> None: ...


_provider: SimulationProvider | None = None


def register(provider: SimulationProvider) -> None:
    """조립이 공급자를 연결한다. 공급자의 인증·범위 확인은 그대로 수행한다."""
    if not all(callable(getattr(provider, name, None)) for name in ("resolve", "inputs", "record_result")):
        raise TypeError("simulation provider must implement resolve, inputs and record_result")
    global _provider
    _provider = provider


def clear() -> None:
    global _provider
    _provider = None


def resolve(place: dict) -> dict | None:
    return None if _provider is None else _provider.resolve(place)


def inputs(current: dict, place: dict, *, safety_only: bool = False) -> dict[str, dict]:
    if _provider is None:
        raise RuntimeError("simulation provider is not registered")
    return _provider.inputs(current, place, safety_only=safety_only)


def record_result(current: dict, report: dict[str, Any], *, safety_only: bool) -> None:
    if _provider is None:
        raise RuntimeError("simulation provider is not registered")
    _provider.record_result(current, report, safety_only=safety_only)

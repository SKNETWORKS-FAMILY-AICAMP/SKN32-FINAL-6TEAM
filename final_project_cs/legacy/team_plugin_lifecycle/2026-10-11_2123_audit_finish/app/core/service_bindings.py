"""Request-local service connections; candidate assembly never edits live tables."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class BindingTable:
    values: Mapping[tuple[str, str], Any]
    registry: Any = None
    revision: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


_bound: ContextVar[BindingTable | None] = ContextVar("service_bindings", default=None)
_building: ContextVar[dict | None] = ContextVar("building_services", default=None)
_standalone: ContextVar[bool] = ContextVar("standalone_services", default=False)


@contextmanager
def standalone_services(enabled=True):
    """Explicit legacy seam for independently assembled components and their tests."""
    token = _standalone.set(enabled)
    try:
        yield
    finally:
        _standalone.reset(token)


@contextmanager
def collect_services():
    values: dict = {}
    token = _building.set(values)
    try:
        yield values
    finally:
        _building.reset(token)


def collect_registration(group: str, values: Mapping[str, Any]) -> bool:
    builder = _building.get()
    if builder is None:
        return False
    builder.update({(group, key): value for key, value in values.items()})
    return True


def collecting_services() -> bool:
    return _building.get() is not None


@contextmanager
def bind_services(table: BindingTable | None):
    if table is None or _bound.get() is not None:
        yield
        return
    token = _bound.set(table)
    try:
        yield
    finally:
        _bound.reset(token)


def current_bindings() -> BindingTable | None:
    return _bound.get()


def read_binding(group: str, key: str, legacy=None, *, required_team: str | None = None):
    table = _bound.get()
    if table is None:
        if _standalone.get():
            return legacy
        from app.core.team_availability import TeamUnavailable

        if required_team:
            raise TeamUnavailable(required_team, "composition_unbound")
        raise RuntimeError("service access requires a bound composition")
    value = table.values.get((group, key))
    if required_team:
        from app.core.team_availability import TeamUnavailable

        if table.registry is None:
            raise TeamUnavailable(required_team, "not_installed")
        table.registry.require_runnable(required_team)
        if value is None:
            raise TeamUnavailable(required_team, "not_installed")
    elif value is None:
        import logging

        logging.getLogger(__name__).info("optional_service_omitted", extra={
            "service_group": group, "service_key": key,
            "reason": "provider_unavailable", "composition_revision": table.revision})
    return value


def use_instance_bindings(method):
    @wraps(method)
    async def call(self, *args, **kwargs):
        with bind_services(getattr(self, "service_bindings", None)):
            return await method(self, *args, **kwargs)
    return call


class PinCompositionMiddleware:
    """Hold a runtime snapshot through the complete ASGI/SSE response lifetime."""

    def __init__(self, app, runtime):
        self.app, self.runtime = app, runtime

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        with self.runtime.pin():
            await self.app(scope, receive, send)

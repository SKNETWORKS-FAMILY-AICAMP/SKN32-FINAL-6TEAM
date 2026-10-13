"""고정된 Mobility 제공자로 지도 경로선을 계산한다."""
from __future__ import annotations

from typing import Any, Callable

from app.core.service_bindings import collect_registration, read_binding
from app.core.team_availability import TeamUnavailable

_items: Callable[..., Any] | None = None
_review: Callable[..., Any] | None = None


def register(*, items: Callable[..., Any], review: Callable[..., Any]) -> None:
    if collect_registration("mobility_shapes", locals()):
        return
    global _items, _review
    _items, _review = items, review


def clear() -> None:
    global _items, _review
    _items = _review = None


def _provider(key, legacy):
    selected = read_binding("mobility_shapes", key, legacy, required_team="mobility")
    if selected is None:
        raise TeamUnavailable("mobility", "not_installed")
    return selected


def items(*args, **kwargs):
    return _provider("items", _items)(*args, **kwargs)


def review(*args, **kwargs):
    return _provider("review", _review)(*args, **kwargs)

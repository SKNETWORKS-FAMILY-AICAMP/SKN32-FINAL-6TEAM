"""후보 계산의 내부 관찰 포트. 고객 응답과 분리하며 저장은 감시 실행 계층이 맡는다."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import json
import logging
import re

_sink = ContextVar("candidate_diagnostic_sink", default=None)
_scope = ContextVar("candidate_diagnostic_scope", default={})
logger = logging.getLogger(__name__)


@contextmanager
def observe(sink):
    token = _sink.set(sink)
    try:
        yield
    finally:
        _sink.reset(token)


@contextmanager
def scope(**values):
    token = _scope.set({**_scope.get(), **values})
    try:
        yield
    finally:
        _scope.reset(token)


def for_item(phase):
    """일정별 계산의 관찰 범위를 묶는다. 계산 결과에는 진단 필드를 붙이지 않는다."""
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            item = kwargs.get("item") or kwargs.get("current")
            with scope(phase=phase, item_id=str(item.item_id), target_title=item.title):
                return function(*args, **kwargs)
        return wrapped
    return decorate


def _text(value):
    value = str(value)
    value = re.sub(r'https?://\S+|\b(?:\d{1,3}\.){3}\d{1,3}\b', '[주소 가림]', value)
    return re.sub(r'(?i)(token|secret|password|api[_-]?key|authorization)\s*[:=]\s*\S+',
                  r'\1=[가림]', value)[:1000]


def record(*, key, name, outcome, reasons=(), report=None, **values):
    report = report or {}
    event = {**{k: _text(v) if isinstance(v, str) else v for k, v in _scope.get().items()}, "candidate_key": _text(key), "name": _text(name), "outcome": outcome,
             "reasons": [_text(r) for r in reasons], "verdict": report.get("verdict"),
             "failed_categories": [_text(v) for v in report.get("failed_categories", [])],
             "error_code": _text(report.get("reason") or ""), **values}
    fields = {'category', 'status', 'mode', 'source', 'reason', 'tried', 'simulation_id', 'confirmed_at'}
    event['checks'] = [{k: [_text(v) for v in value] if isinstance(value, list) else _text(value)
                        for k, value in check.items() if k in fields and value is not None}
                       for check in report.get('checks', []) if isinstance(check, dict)]
    sink = _sink.get()
    if sink is not None:
        sink(event)
    else:
        logger.info("candidate_evaluation %s", json.dumps(event, ensure_ascii=False, default=str))

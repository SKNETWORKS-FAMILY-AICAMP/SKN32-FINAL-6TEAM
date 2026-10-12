"""같은 프로세스 MCP→웹 API에만 전달하는 검증된 호출 문맥. HTTP 헤더로 만들지 않는다."""
from contextlib import contextmanager
from contextvars import ContextVar

_verified_identity = ContextVar("personal_ai_verified_identity", default=None)


def current_identity():
    return _verified_identity.get()


@contextmanager
def delegated_identity(identity):
    marker = _verified_identity.set(identity)
    try:
        yield
    finally:
        _verified_identity.reset(marker)

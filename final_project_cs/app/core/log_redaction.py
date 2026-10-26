"""로그 줄에서 비밀 쿼리 파라미터 · 등록된 키 값을 가린다 — 프로세스마다 한 번 건다(`install_log_redaction`). `[2026-10-26]`

★왜: x600 api 컨테이너 로그에 바깥 API 요청 주소가 키 쿼리째 찍혔다. 경로는 이렇다.
  `create_app()` → `composition.build_mcp_surface` → `FastMCP(...)` 가 `mcp.server.fastmcp.utilities.logging.configure_logging("INFO")`
  로 **루트 로거를 INFO** 로 올린다(`logging.basicConfig`, RichHandler). 레벨을 따로 두지 않은 `httpx` 로거의
  `HTTP Request: GET <주소 전체> "HTTP/1.1 200 OK"` INFO 줄이 루트로 올라가 그대로 찍혔다.

★막는 방법은 둘이고 둘 다 건다.
  ① `httpx` · `httpcore` 로거를 WARNING 이상으로 — 요청마다 주소를 찍는 줄 자체가 안 생긴다.
  ② 로그 레코드 팩토리(`logging.setLogRecordFactory`)로 **모든 로거**의 메시지 · 예외 글을 `redaction.redact_secrets` 로 가린다 —
     자체 로그 · 예외 문자열(`HTTPStatusError` 는 주소를 싣는다) · uvicorn 접속 로그까지. 이름 목록은 `redaction.SECRET_QUERY_PARAMS` 한 곳이다.
     키가 경로 조각인 공급자는 이름으로 못 잡으므로 설정의 키 값(`*_key` · `*_keys` · `*_secret` · `*_token`)을 등록해 값으로 가린다.
"""
from __future__ import annotations

import logging
import traceback
from typing import Any, Iterable

from app.core import redaction

#: 요청마다 주소 전체를 INFO 로 찍는 라이브러리 로거 — WARNING 아래로 두지 않는다
QUIET_LOGGERS = ("httpx", "httpcore")
#: 값을 등록할 설정 필드 이름 끝 — 쉼표로 여러 개를 적는 필드(`*_keys`)는 나눠서 넣는다
SECRET_FIELD_SUFFIXES = ("_key", "_keys", "_secret", "_token", "_key_server")

_SECRET_VALUES = redaction._SECRET_VALUES


def register_secret_values(values: Iterable[Any]) -> None:
    redaction.add_secret_values(values)


def register_settings_secrets(settings: Any) -> None:
    """설정 객체의 키 · 비밀값 필드 값을 가릴 값으로 등록한다(필드 이름은 끝말로만 고른다 — 특정 키 이름을 적지 않는다)."""
    fields = getattr(type(settings), "model_fields", None) or {}
    values: list[str] = []
    for name in fields:
        if not name.endswith(SECRET_FIELD_SUFFIXES):
            continue
        value = getattr(settings, name, "")
        if hasattr(value, "get_secret_value"):
            value = value.get_secret_value()
        if isinstance(value, str) and value:
            values.extend(_split_secret_field(value))
    register_secret_values(values)


def _split_secret_field(value: str) -> list[str]:
    """한 필드에 키를 여럿 적는 모양 — JSON 객체(값들) · JSON 배열 · 쉼표 구분 — 을 낱낱의 값으로. 그 밖은 통째로."""
    import json

    try:
        parsed = json.loads(value)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict):
        return [str(item) for item in parsed.values() if isinstance(item, str)]
    if isinstance(parsed, list):
        return [str(item) for item in parsed if isinstance(item, str)]
    return [value, *(part.strip() for part in value.split(","))]


def _scrub(record: logging.LogRecord) -> None:
    try:
        message = record.getMessage()
    except Exception:  # noqa: BLE001 — 형식이 틀린 레코드는 logging 이 원래대로 알린다(예외 · 스택 글은 아래에서 그대로 가린다)
        message = None
    if message is not None:
        clean = redaction.redact_secrets(message)
        if clean != message:
            record.msg, record.args = clean, ()
    if record.exc_info and record.exc_info[1] is not None:
        text = "".join(traceback.format_exception(*record.exc_info)).rstrip("\n")
        clean_exc = redaction.redact_secrets(text)
        if clean_exc != text:
            # 가린 글을 `exc_text` 로 주고 원래 예외는 뗀다 — Formatter · RichHandler 가 원래 예외로 다시 쓰지 않게
            record.exc_text, record.exc_info = clean_exc, None
    if record.stack_info:
        record.stack_info = redaction.redact_secrets(record.stack_info)


def _installed() -> bool:
    return bool(getattr(logging.getLogRecordFactory(), "_secret_redaction", False))


def install_log_redaction(settings: Any | None = None) -> None:
    """다시 불러도 같다. ① 시끄러운 라이브러리 로거를 WARNING 으로 ② 레코드 팩토리에 가림을 끼운다(지금 팩토리에 이미 있으면 건너뛴다 —
    다른 코드가 팩토리를 바꿔 끼웠으면 그 위에 다시 건다) ③ 설정의 키 값을 등록한다.
    ★가리는 것은 레코드의 메시지 · 예외 글 · 스택 글이다. `extra=` 로 붙인 필드는 대상이 아니다 — 거기에 주소 · 키를 싣지 않는다."""
    for name in QUIET_LOGGERS:
        logger = logging.getLogger(name)
        if logger.level < logging.WARNING:
            logger.setLevel(logging.WARNING)
    if settings is None:
        try:
            from app.core.settings import get_settings

            settings = get_settings()
        except Exception:  # noqa: BLE001 — 설정을 못 읽는 프로세스(일부 시험 · 도구)도 이름 규칙 가림은 건다
            settings = None
    if settings is not None:
        register_settings_secrets(settings)
    if _installed():
        return
    previous = logging.getLogRecordFactory()

    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = previous(*args, **kwargs)
        _scrub(record)
        return record

    factory._secret_redaction = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(factory)

# -*- coding: utf-8 -*-
"""바깥 API 키가 로그 · 진단 기록 · 예외 문자열에 남지 않는다. `[2026-10-26]`

x600 api 컨테이너 로그에 공공데이터 요청 주소가 `serviceKey=…` 쿼리째 찍혔다. 경로:
`create_app()` → `composition.build_mcp_surface` → `FastMCP(...)` 가 `mcp.server.fastmcp.utilities.logging.configure_logging("INFO")`
로 **루트 로거를 INFO** 로 올린다(`logging.basicConfig`). 그러면 레벨을 따로 안 둔 `httpx` 로거의
`HTTP Request: GET <주소 전체> "HTTP/1.1 200 OK"` INFO 줄이 그대로 나간다.

재현:

    python -m pytest tests/security/test_secret_query_log_redaction.py -v
"""
from __future__ import annotations

import logging

import httpx
import pytest

from app.core import log_redaction
from app.core.redaction import SECRET_QUERY_PARAMS, redact_secrets

SECRET = "UnitSecretValue0123456789abcdefXYZ"   # 시험용 가짜 값


class _Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


@pytest.fixture(autouse=True)
def _fresh_logging_state():
    # 시험마다 가림이 안 걸린 상태 · 빈 값 목록에서 시작하고, 끝나면 원래대로 돌려 다른 시험에 새지 않게 한다
    factory = logging.getLogRecordFactory()
    levels = {name: logging.getLogger(name).level for name in ("httpx", "httpcore")}
    values = set(log_redaction._SECRET_VALUES)
    logging.setLogRecordFactory(logging.LogRecord)
    log_redaction._SECRET_VALUES.clear()
    try:
        yield
    finally:
        logging.setLogRecordFactory(factory)
        for name, level in levels.items():
            logging.getLogger(name).setLevel(level)
        log_redaction._SECRET_VALUES.clear()
        log_redaction._SECRET_VALUES.update(values)


@pytest.fixture
def root_lines():
    handler = _Collect()
    handler.setFormatter(logging.Formatter("%(name)s %(message)s"))
    root = logging.getLogger()
    old = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)        # FastMCP 가 해 두는 상태 그대로
    try:
        yield handler.lines
    finally:
        root.removeHandler(handler)
        root.setLevel(old)


def _mock_get(url: str) -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))) as client:
        client.get(url)


# invariant: INV-CS-SEC-016
def test_the_api_app_does_not_let_httpx_print_request_urls(root_lines):
    from app.presentation.api.app import create_app

    create_app()
    _mock_get(f"https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst?serviceKey={SECRET}&pageNo=1")
    assert not [line for line in root_lines if SECRET in line], root_lines
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING


@pytest.mark.parametrize("name", ["serviceKey", "ServiceKey", "key", "apiKey", "api_key", "appkey", "authKey",
                                  "crtfc_key", "client_secret", "access_token"])
def test_any_logger_line_with_a_secret_query_parameter_is_masked(root_lines, name):
    log_redaction.install_log_redaction()
    logging.getLogger("app.unit.anything").warning("failed %s", f"https://example.test/a?x=1&{name}={SECRET}&y=2")
    joined = "\n".join(root_lines)
    assert SECRET not in joined
    assert f"{name}=***" in joined and "x=1" in joined and "y=2" in joined


def test_exception_text_in_a_log_record_is_masked(root_lines):
    log_redaction.install_log_redaction()
    request = httpx.Request("GET", f"https://apis.data.go.kr/x?serviceKey={SECRET}")
    try:
        httpx.Response(500, request=request).raise_for_status()
    except httpx.HTTPStatusError:
        logging.getLogger("app.unit.exc").exception("call failed")
    joined = "\n".join(root_lines)
    assert "call failed" in joined and "HTTPStatusError" in joined
    assert SECRET not in joined


def test_a_configured_key_value_in_a_url_path_is_masked(root_lines, monkeypatch):
    # 서울 열린데이터처럼 키가 경로 조각인 공급자 — 이름 규칙으로는 못 잡아 설정에 든 값 자체를 가린다
    log_redaction.register_secret_values([SECRET])
    log_redaction.install_log_redaction()
    logging.getLogger("app.unit.path").warning("GET http://swopenapi.seoul.go.kr/api/subway/%s/json/x", SECRET)
    assert SECRET not in "\n".join(root_lines)


def test_settings_key_fields_are_registered_as_secret_values(monkeypatch):
    from app.core.settings import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "seoul_openapi_key", SECRET, raising=False)
    log_redaction.register_settings_secrets(settings)
    assert SECRET not in redact_secrets(f"http://openapi.seoul.go.kr:8088/{SECRET}/json/bikeList/1/5/1")


def test_the_parameter_list_lives_in_one_place():
    assert {"servicekey", "key", "apikey", "api_key", "appkey", "authkey", "crtfc_key", "client_secret",
            "access_token"} <= SECRET_QUERY_PARAMS
    assert all(name == name.lower() for name in SECRET_QUERY_PARAMS)


def test_ordinary_parameters_and_words_are_left_alone():
    text = "https://x.test/a?cache_key=1&monkey=2&keyword=3&page=4 key 문서"
    assert redact_secrets(text) == text


def test_url_encoded_secret_values_are_masked_too():
    value = "abc+def/ghi=="
    log_redaction.register_secret_values([value])
    from urllib.parse import quote

    assert quote(value, safe="") not in redact_secrets(f"https://x.test/a?serviceKey2={quote(value, safe='')}")


def test_travel_source_miss_line_does_not_keep_the_key(root_lines):
    # 공급자 어댑터를 만들기만 해도(조립 · 감시 · 일괄 작업 어느 프로세스든) 가림이 걸린다
    from app.domains.travel_ops.ports.data_sources.base import TravelSource

    def boom(url, params):
        raise httpx.UnsupportedProtocol(f"Request URL has an unsupported protocol 'htp://a.test/?serviceKey={SECRET}'")

    source = TravelSource(transport=boom)
    assert source._fetch_json("https://apis.data.go.kr/x", {"serviceKey": SECRET}) is None
    assert source.misses["transport_error"] == 1
    assert [line for line in root_lines if "travel source miss" in line]
    assert SECRET not in " | ".join(root_lines)


def test_persisted_diagnostic_values_do_not_keep_the_key():
    # Case 상태 · 실패 사유처럼 저장 전에 `mask_json` 을 거치는 진단 기록 — 설정에 든 키 값이면 어디에 있든 가린다
    from app.core.redaction import mask_json

    log_redaction.register_secret_values([SECRET])
    stored = mask_json({"failed": {"detail": f"HTTPStatusError: Server error '500' for url 'https://apis.data.go.kr/x?serviceKey={SECRET}&pageNo=1'"}})
    assert SECRET not in str(stored)
    assert "serviceKey=***" in stored["failed"]["detail"] and "pageNo=1" in stored["failed"]["detail"]


def test_customer_links_in_persisted_values_keep_their_token_and_key_parameters():
    # 이름 규칙(`?token=` · `?key=`)은 로그에만 — 고객이 적은 링크를 저장값에서 망가뜨리지 않는다
    from app.core.redaction import mask_json

    link = "https://share.example.test/trip?token=abcDEF123456&key=room-42"
    assert mask_json({"text": f"이 링크 봐 주세요 {link}"}) == {"text": f"이 링크 봐 주세요 {link}"}


def test_values_with_separators_and_json_shapes_are_masked_whole():
    assert SECRET not in redact_secrets(f"https://x.test/a?serviceKey={SECRET},{SECRET}&n=1")
    assert redact_secrets("https://x.test/a?serviceKey=abc,def;ghi&n=1") == "https://x.test/a?serviceKey=***&n=1"
    assert redact_secrets(f'{{"serviceKey": "{SECRET}", "pageNo": 1}}') == '{"serviceKey": "***", "pageNo": 1}'
    assert redact_secrets(f"{{'api_key': '{SECRET}'}}") == "{'api_key': '***'}"


def test_a_record_whose_message_cannot_be_formatted_still_has_its_exception_masked(root_lines):
    log_redaction.install_log_redaction()
    try:
        raise RuntimeError(f"GET https://apis.data.go.kr/x?serviceKey={SECRET}")
    except RuntimeError:
        record = logging.getLogger("app.unit.bad").makeRecord("app.unit.bad", logging.ERROR, __file__, 1, "bad %s %s",
                                                               ("only-one",), __import__("sys").exc_info())
    assert record.exc_info is None and SECRET not in (record.exc_text or "") and "serviceKey=***" in record.exc_text


def test_install_is_redone_when_another_library_replaced_the_record_factory(root_lines):
    log_redaction.install_log_redaction()
    logging.setLogRecordFactory(logging.LogRecord)                       # 다른 코드가 팩토리를 갈아 끼웠다
    log_redaction.install_log_redaction()
    logging.getLogger("app.unit.again").warning("GET https://x.test/?apikey=%s", SECRET)
    assert SECRET not in " | ".join(root_lines)


def test_multi_key_fields_written_as_json_register_each_value():
    from app.core.log_redaction import _split_secret_field

    assert set(_split_secret_field('{"a": "first-secret-value", "b": "second-secret-value"}')) == {
        "first-secret-value", "second-secret-value"}
    assert "second-secret-value" in _split_secret_field("first-secret-value,second-secret-value")

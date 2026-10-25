# -*- coding: utf-8 -*-
"""모델 서버(Ollama · GPU 서버)가 죽거나 늦을 때 **서버용 OpenAI 키**로 자동으로 넘기는 장치. `[2026-10-07 사용자 지시]`

    「올라마나 외부 GPU 서버가 모두 장애면 서버키(개인키 말고)로 자동 전환돼서 동작하게」

★한 곳에서 한다 — `ollama_chat.from_settings()` 가 돌려주는 객체가 `OllamaChat` 와 **같은 메서드**(`json` · `text` · `structured` · `see` · `loaded` · `warm`)를
  가진 `FailoverChat` 이 된다. 그래서 결정 단위 · 계획 읽기 · 알림 번역 · 분류가 코드를 바꾸지 않고 같이 넘어간다.
★순서: ① Ollama(설정 `ollama_base_url`, 그다음 `ollama_fallback_base_urls` 의 서버들 — 앞에서부터) → ② OpenAI(서버용 키). **모두** 안 될 때만 ②로 간다.
★넘기는 조건: 연결 실패 · 시간 초과 · 5xx · 429 · 빈 답(서버 문제로 센다) · 모양이 틀린 답(그 한 번만 넘긴다 — 서버가 살아 있으니 서킷에는 안 센다).
  429 · 5xx 는 **한 번만** 짧게 쉬었다가 다시 시도한다(전체 시간 안에 다 들어갈 때만).
★회로 차단기: 한 서버가 연속 `llm_failover_failures` 번 서버 문제로 실패하면 `llm_failover_open_seconds` 동안 **건너뛴다**(바로 다음 경로로). 시간이 지나면
  한 호출만 시험(반쯤 열림)해서 성공하면 닫는다. 서킷은 프로세스 안 전역이다(`from_settings` 를 요청마다 불러도 상태가 이어진다).
★넘긴 답도 부르는 쪽의 검증을 그대로 거친다(`decision_unit.decide` 의 목록 밖 값 거부 · 분류기의 라벨 검사 · 번역 숫자 · 단위 대조) — 이 모듈은 모양만 맞춰 준다.
★개인정보: API 로 보내는 글은 `redaction.masked` 로 한 번 더 가린다(전화 · 이메일 같은 것). 호출부가 이미 가린 글이라 보통 달라지지 않는다.
  ★이미지(`see`)는 **가릴 수 없다** — 이름 · 예약번호가 그대로 있어 `llm_failover_vision` 을 따로 켰을 때만 넘긴다(기본 꺼짐).
★비용 방어: API 로 넘긴 호출은 `external_call_budget` 의 `openai_failover` 줄(일 · 월 상한)로 센다. 넘으면 더 부르지 않고 실패로 올린다.
★기록: 어느 경로로 답했는지(`local` · `api`)와 넘긴 이유를 로그(`app.llm_failover`)와 프로세스 안 지표(`snapshot()`)에 남긴다. 호출 직후 `current_path()` 로 읽을 수 있다.
★스위치 `llm_failover_enabled` 는 기본 꺼짐 — 꺼져 있거나 서버용 키가 비어 있으면 지금처럼 Ollama 만 쓴다(`wrap_from_settings` 가 원래 객체를 그대로 돌려준다).
★실패는 `OllamaError` 로 올린다(부르는 쪽이 이미 이것을 「모름」으로 바꾼다). 키 값은 어떤 메시지에도 싣지 않는다 — 상태 코드와 이유 이름만.
★`[2026-10-16]` `json_stream` — 답을 조금씩 받으며 첫 조각 · 조각 사이 · 맨 위 상한으로 멈춤을 본다(`model_stream.py`). 한 답은 한 경로가 처음부터 끝까지 쓰고,
  로컬이 멈추면 유료가 처음부터 다시 읽는다. 로컬 모델이 안 올라와 있으면 곧바로 유료로 간다(`ModelNotLoaded`). 다른 메서드의 동작은 그대로다.
★`[2026-10-26]` 첫 Ollama 가 안 올라와 있어 넘길 때는 **뒤에서 예열을 한 번 시작한다**(`register_warm_starter` — 조립 루트가 `model_warmup` 의 중복 억제를 꽂는다).
  고객 요청은 예열을 기다리지 않는다. 안 올리면 runner 가 내려간 동안 다음 요청도 계속 유료였다(x600 `not_loaded`).
"""
from __future__ import annotations

import base64
import contextvars
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from app.core.redaction import masked
from app.infrastructure.ollama_chat import OllamaChat, OllamaContentError, OllamaError, validate_content, validate_structured

log = logging.getLogger("app.llm_failover")

# Request-local SDK attempt authorization. General API calls retain their policy.
_reader_attempt: contextvars.ContextVar[Any] = contextvars.ContextVar("reader_attempt", default=None)

METER = "openai_failover"

#: 호출 직후 「이 호출이 어느 경로로 답했나」 — 같은 스레드에서 읽는다(요청마다 스레드가 다르므로 섞이지 않는다)
_path_var: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar("llm_failover_path", default=None)


def current_path() -> dict[str, Any] | None:
    """직전 호출의 `{path: "local"|"api", backend, op, reasons: [[backend, reason]…], seconds}`. 호출이 없었으면 `None`."""
    return _path_var.get()


def clear_path() -> None:
    """호출 직전에 비운다 — 요청이 스레드를 재사용하므로 앞 요청의 기록이 남아 있으면 안 된다."""
    _path_var.set(None)


class ModelCallError(OllamaError):
    """API 쪽 호출 실패 — 이유 이름(`reason`)을 가진다. ★메시지에 키 · 응답 본문을 싣지 않는다."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


# ─────────────────────────── 회로 차단기 ───────────────────────────
class CircuitBreaker:
    """닫힘 → (연속 실패) → 열림 → (시간 경과) → 반쪽(한 호출만 시험) → 성공이면 닫힘 · 실패면 다시 열림."""

    def __init__(self, name: str, *, threshold: int, open_seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self.name, self.threshold, self.open_seconds, self._clock = name, max(1, int(threshold)), float(open_seconds), clock
        self._lock = threading.Lock()
        self.state = "closed"
        self.failures = 0
        self.opened_at = 0.0
        self._probing = False

    def allow(self) -> bool:
        with self._lock:
            if self.state == "closed":
                return True
            if self.state == "open":
                if self._clock() - self.opened_at < self.open_seconds:
                    return False
                self.state, self._probing = "half_open", True        # 시간이 지났다 — 이 호출 하나만 시험으로 보낸다
                log.warning("llm_failover breaker=%s state=half_open", self.name)
                return True
            if self._probing:                                          # 반쪽 — 이미 시험 중이면 다른 호출은 건너뛴다
                return False
            self._probing = True
            return True

    def success(self) -> None:
        with self._lock:
            if self.state != "closed":
                log.warning("llm_failover breaker=%s state=closed", self.name)
            self.state, self.failures, self._probing = "closed", 0, False

    def release(self) -> None:
        """시험(반쪽) 자리를 돌려준다 — 이 경로를 실제로 부르지는 않았을 때(예: 호출 상한)."""
        with self._lock:
            self._probing = False

    def failure(self) -> None:
        with self._lock:
            self._probing = False
            self.failures += 1
            if self.state == "half_open" or self.failures >= self.threshold:
                if self.state != "open":
                    log.warning("llm_failover breaker=%s state=open failures=%d for=%.0fs", self.name, self.failures, self.open_seconds)
                self.state, self.opened_at = "open", self._clock()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"state": self.state, "failures": self.failures}


_breakers: dict[tuple[str, int, float], CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def breaker_for(name: str, *, threshold: int, open_seconds: float, clock: Callable[[], float] = time.monotonic) -> CircuitBreaker:
    with _breakers_lock:
        key = (name, int(threshold), float(open_seconds))
        if key not in _breakers:
            _breakers[key] = CircuitBreaker(name, threshold=threshold, open_seconds=open_seconds, clock=clock)
        return _breakers[key]


# ─────────────────────────── 지표 ───────────────────────────
_stats_lock = threading.Lock()
_counters: dict[str, int] = {}
_last_switch: dict[str, Any] = {}


def _count(key: str) -> None:
    with _stats_lock:
        _counters[key] = _counters.get(key, 0) + 1


def snapshot() -> dict[str, Any]:
    """프로세스 안 지표 — `{counters: {"ok:<op>:<backend>": n, "fail:<backend>:<reason>": n, "skip:<backend>:<why>": n}, last_switch, breakers}`.
    ★프로세스를 다시 띄우면 0 으로 돌아간다(영구 기록은 로그)."""
    with _breakers_lock:
        states = {f"{k[0]}": b.snapshot() for k, b in _breakers.items()}
    with _stats_lock:
        return {"counters": dict(_counters), "last_switch": dict(_last_switch), "breakers": states}


def reset_state() -> None:
    """시험용 — 서킷 · 지표를 비운다."""
    with _breakers_lock:
        _breakers.clear()
    with _stats_lock:
        _counters.clear()
        _last_switch.clear()
    with _clients_lock:
        _clients.clear()
    _path_var.set(None)


# ─────────────────────────── 실패 분류 ───────────────────────────
@dataclass
class Failure:
    reason: str
    retryable: bool = False          # 429 · 5xx — 한 번 더 시도할 수 있다
    counts: bool = True              # 서버 문제로 서킷에 센다(모양이 틀린 답은 안 센다 — 서버는 살아 있다)


class ModelNotLoaded(OllamaError):
    """로컬 모델이 메모리에 올라와 있지 않다 — 올리느라 오래 걸리므로 다음 경로로 간다(서버 장애가 아니라 서킷에 세지 않는다). `[2026-10-16]`"""


class ModelSkipped(OllamaError):
    """이 호출은 이 경로를 쓰지 않는다(예: 유료만 쓰는 호출의 로컬) — 서킷에 세지 않는다. `[2026-10-16]`"""


def classify(exc: BaseException) -> Failure:
    if isinstance(exc, ModelSkipped):
        return Failure("skipped", counts=False)
    if isinstance(exc, ModelNotLoaded):
        return Failure("not_loaded", counts=False)
    from app.infrastructure.model_stream import StreamStalled

    if isinstance(exc, StreamStalled):
        return Failure("timeout")                            # 조각이 끊겼다(첫 조각 · 조각 사이 · 맨 위 상한) — 서버가 멈춘 것으로 센다
    if isinstance(exc, OllamaContentError):
        return Failure("content", counts=False)
    if isinstance(exc, ModelCallError):
        return Failure(exc.reason, retryable=exc.reason in ("429", "5xx"), counts=exc.reason != "bad_request")
    cause = exc.__cause__
    if isinstance(cause, (httpx.ConnectError, httpx.ConnectTimeout)):
        return Failure("connect")
    if isinstance(cause, httpx.TimeoutException):
        return Failure("timeout")
    if isinstance(cause, httpx.HTTPError):
        return Failure("connect")
    text = str(exc)
    for code in ("500", "502", "503", "504", "505"):
        if f"HTTP {code}" in text:
            return Failure("5xx", retryable=True)
    if "HTTP 5" in text:
        return Failure("5xx", retryable=True)
    if "HTTP 429" in text:
        return Failure("429", retryable=True)
    if "빈 답" in text or "빈 받아쓰기" in text:
        return Failure("empty")
    if "HTTP 4" in text:
        return Failure("http_4xx")
    return Failure("error")


# ─────────────────────────── OpenAI 쪽 ───────────────────────────
def _api_error(exc: BaseException) -> ModelCallError:
    """OpenAI SDK 예외 → `ModelCallError`. ★`str(exc)` 를 싣지 않는다(잘못된 키 오류에는 키 앞뒤가 들어 있다)."""
    import openai

    status = getattr(exc, "status_code", None)
    if isinstance(exc, openai.APITimeoutError):
        reason = "timeout"
    elif isinstance(exc, openai.APIConnectionError):
        reason = "connect"
    elif isinstance(exc, openai.RateLimitError):
        reason = "429"
    elif isinstance(exc, openai.InternalServerError):
        reason = "5xx"
    elif isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
        reason = "auth"
    elif isinstance(exc, openai.BadRequestError):
        reason = "bad_request"
    elif isinstance(status, int) and status >= 500:
        reason = "5xx"
    else:
        reason = "error"
    return ModelCallError(f"OpenAI 호출 실패({reason}): {type(exc).__name__}" + (f" HTTP {status}" if status else ""), reason=reason)


_NO_TEMPERATURE = ("o1", "o3", "o4", "gpt-5", "gpt-6")  # 추론 모델에 샘플링 옵션을 보내지 않는다
_clients: dict[tuple[str, float], Any] = {}
_clients_lock = threading.Lock()


#: OpenAI 엄격 스키마가 받지 않는 말 — 떼고 보낸다. 범위 · 개수 검사는 부르는 쪽 검증(`decide` 등)이 한다
_STRICT_UNSUPPORTED = ("maxItems", "minItems", "minLength", "maxLength", "pattern", "format", "minimum", "maximum", "default")


def strict_schema(schema: Any) -> Any:
    """우리 스키마 → OpenAI 엄격 모드(`strict: True`) 스키마. `[2026-10-15]`
    엄격 모드는 객체마다 모든 키가 `required` 이고 `additionalProperties: false` 여야 한다 — 원래 선택 키는 null 을 허용해 필수로 둔다.
    ☆느슨한 모드에서 gpt-4o-mini 가 채팅 해석 스키마를 지키지 않았다(12/12 실패 — 스키마째 답하거나 사실 칸 값을 할 일 칸에 넣었다)."""
    if isinstance(schema, list):
        return [strict_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    out = {k: strict_schema(v) for k, v in schema.items() if k not in _STRICT_UNSUPPORTED}
    props = schema.get("properties")
    if schema.get("type") == "object" and isinstance(props, dict):
        required = set(schema.get("required") or [])
        out["properties"] = {k: (strict_schema(v) if k in required else _nullable(strict_schema(v)))
                             for k, v in props.items()}
        out["required"] = list(props)
        out["additionalProperties"] = False
    return out


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    options = schema.get("anyOf")
    if isinstance(options, list):
        return schema if any(o.get("type") == "null" for o in options) else {**schema, "anyOf": [*options, {"type": "null"}]}
    return {"anyOf": [schema, {"type": "null"}]}


def _drop_optional_nulls(value: Any, schema: Any) -> Any:
    """엄격 모드 답 → 원래 모양. 원래 선택 키가 null 이면 뺀다(부르는 쪽은 「없음」을 키가 없는 것으로 읽어 왔다)."""
    if not isinstance(schema, dict):
        return value
    if isinstance(value, list):
        return [_drop_optional_nulls(v, schema.get("items")) for v in value]
    if isinstance(value, dict):
        sub = schema
        if "properties" not in sub and isinstance(sub.get("anyOf"), list):
            sub = next((o for o in sub["anyOf"] if isinstance(o, dict) and o.get("type") == "object"), sub)
        props = sub.get("properties") or {}
        required = set(sub.get("required") or [])
        return {k: _drop_optional_nulls(v, props.get(k)) for k, v in value.items()
                if not (v is None and k not in required)}
    return value


class OpenAIChat:
    """`OllamaChat` 과 같은 메서드를 가진 OpenAI 쪽 — 서버용 키로 부른다. 클라이언트는 첫 호출 때 만든다(만드는 것 자체는 I/O 가 없다)."""

    def __init__(self, *, api_key: str, model: str, timeout: float = 8.0, client: Any = None) -> None:
        self.model, self.timeout = model, float(timeout)
        self._api_key, self._client = api_key, client

    def _api(self) -> Any:
        if self._client is None:
            # ★요청마다 새 `FailoverChat` 이 만들어지므로(`from_settings`) 클라이언트를 프로세스 안에서 나눠 쓴다 — 매번 TLS 연결을 새로 맺지 않게
            cache_key = (self._api_key, self.timeout)
            with _clients_lock:
                client = _clients.get(cache_key)
                if client is None:
                    from openai import OpenAI

                    client = _clients[cache_key] = OpenAI(api_key=self._api_key, timeout=self.timeout, max_retries=0)
            self._client = client
        return self._client

    def _complete(self, messages: list[dict[str, Any]], *, response_format: dict[str, Any] | None = None,
                  max_tokens: int = 600, timeout: float | None = None) -> str:
        authorize = _reader_attempt.get()
        if authorize is not None:
            remaining = authorize()
            timeout = min(timeout if timeout is not None else self.timeout, remaining)
        token_limit = "max_completion_tokens" if self.model.startswith("gpt-6") else "max_tokens"
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages, token_limit: int(max_tokens)}
        if self.model.startswith("gpt-6-luna"):
            # 짧은 문장·JSON 추출의 출력 예산을 추론 토큰이 먼저 소진하지 않도록 한다.
            kwargs["reasoning_effort"] = "none"
        if not self.model.startswith(_NO_TEMPERATURE):
            kwargs["temperature"] = 0
        if response_format is not None:
            kwargs["response_format"] = response_format
        if timeout is not None:
            kwargs["timeout"] = float(timeout)
        try:
            response = self._api().chat.completions.create(**kwargs)
        except ModelCallError:
            raise
        except Exception as exc:                                  # noqa: BLE001 — SDK 예외를 이유 이름으로 바꾼다
            raise _api_error(exc) from None
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError):
            raise ModelCallError("OpenAI 응답 모양이 다르다", reason="error") from None
        if not isinstance(content, str) or not content.strip():
            raise ModelCallError("OpenAI 가 빈 답을 냈다", reason="empty")
        return content.strip()

    @staticmethod
    def _object(text: str) -> dict[str, Any]:
        try:
            # ★`[2026-10-15]` 문자열 안의 줄바꿈 · 탭(제어 문자)을 받는다 — gpt-4o-mini 엄격 모드가 「text」 칸에 넣어 「JSON 이 아니다」로 실패했다
            value = json.loads(text, strict=False)
        except ValueError:
            raise OllamaContentError(f"JSON 이 아니다: {text[:80]}") from None
        if not isinstance(value, dict):
            raise OllamaContentError("JSON 객체가 아니다")
        return value

    def json(self, system: str, user: str) -> dict[str, Any]:
        # json_object 모드는 메시지 어딘가에 「JSON」이라는 말이 있어야 한다
        sys_text = system if "json" in system.lower() else system + "\nReply with a single JSON object only."
        text = self._complete([{"role": "system", "content": sys_text}, {"role": "user", "content": user}],
                              response_format={"type": "json_object"})
        return self._object(text)

    def json_stream(self, system: str, user: str, *, on_piece: Callable[[str], None] | None = None, first_wait: float = 15.0,
                    stall: float = 5.0, max_seconds: float = 180.0, max_tokens: int = 0) -> dict[str, Any]:
        """`json` 과 같은 답을 **조금씩 받는다**(`stream=True`) — 멈춤 감시는 로컬과 같다(`model_stream.collect`). `[2026-10-16]`
        ★`max_tokens` 를 부르는 쪽이 정한다(0 이면 `json` 과 같은 600) — `json` 의 600토큰은 긴 계획 읽기 답을 잘랐다(실측 6/6).
        답 상한에 걸려 끝나면(`finish_reason=length`) 잘린 JSON 이므로 `OllamaContentError`."""
        sys_text = system if "json" in system.lower() else system + "\nReply with a single JSON object only."
        text = self._stream_text([{"role": "system", "content": sys_text}, {"role": "user", "content": user}], {"type": "json_object"},
                                 max_tokens or 600, on_piece=on_piece, first_wait=first_wait, stall=stall, max_seconds=max_seconds)
        return self._object(text)

    def structured_stream(self, system: str, user: str, schema: dict[str, Any], *, num_predict: int = 160,
                          on_piece: Callable[[str], None] | None = None, first_wait: float = 15.0, stall: float = 5.0,
                          max_seconds: float = 180.0) -> dict[str, Any]:
        """`structured` 와 같은 답(엄격 스키마)을 **조금씩 받는다** — 계획 읽기 에이전트가 쓴다. `[2026-10-16]`
        답 토큰 상한은 `structured` 와 같다(`num_predict` × 4, 최소 300). 깨진 JSON 은 `structured` 처럼 **한 번만** 다시 받고,
        이 모델이 스키마를 거부하면(`bad_request`) 스키마를 글로 적어 JSON 모드로 다시 받는다."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        budget = max(300, int(num_predict) * 4)
        strict = {"type": "json_schema", "json_schema": {"name": "answer", "schema": strict_schema(schema), "strict": True}}
        watch = {"on_piece": on_piece, "first_wait": first_wait, "stall": stall, "max_seconds": max_seconds}
        try:
            text = self._stream_text(messages, strict, budget, **watch)
            try:
                return _drop_optional_nulls(self._object(text), schema)
            except OllamaContentError:
                text = self._stream_text(messages, strict, budget, **watch)
                return _drop_optional_nulls(self._object(text), schema)
        except ModelCallError as exc:
            if exc.reason != "bad_request":
                raise
            messages[0] = {"role": "system", "content": system + "\nReply with a single JSON object that matches this JSON schema:\n"
                           + json.dumps(schema, ensure_ascii=False)}
            return self._object(self._stream_text(messages, {"type": "json_object"}, budget, **watch))

    def structured_stream_validated(self, system: str, user: str, schema: dict[str, Any], *,
                                    validator: Callable[[dict[str, Any]], None], num_predict: int = 160,
                                    on_piece: Callable[[str], None] | None = None, first_wait: float = 15.0, stall: float = 5.0,
                                    max_seconds: float = 180.0) -> dict[str, Any]:
        """`structured_validated` 를 조금씩 받기로 — 받은 답을 `structured` 와 같이 스키마로 검사하고 근거 검사를 한다. `[2026-10-26 사용자 승인]`"""
        value = self.structured_stream(system, user, schema, num_predict=num_predict, on_piece=on_piece, first_wait=first_wait,
                                       stall=stall, max_seconds=max_seconds)
        return validate_content(validate_structured(value, schema), validator)

    def _stream_text(self, messages: list[dict[str, Any]], response_format: dict[str, Any], max_tokens: int, *,
                     on_piece: Callable[[str], None] | None, first_wait: float, stall: float, max_seconds: float) -> str:
        from app.infrastructure.model_stream import collect, StreamLifetime

        authorize = _reader_attempt.get()
        if authorize is not None:
            remaining = authorize()
            max_seconds = min(max_seconds, remaining)
            first_wait, stall = min(first_wait, remaining), min(stall, remaining)
        token_limit = "max_completion_tokens" if self.model.startswith("gpt-6") else "max_tokens"
        kwargs: dict[str, Any] = {"model": self.model, "stream": True, token_limit: int(max_tokens), "response_format": response_format,
                                  "timeout": float(max_seconds), "messages": messages}
        if self.model.startswith("gpt-6-luna"):
            kwargs["reasoning_effort"] = "none"
        if not self.model.startswith(_NO_TEMPERATURE):
            kwargs["temperature"] = 0
        held: dict[str, Any] = {}
        lifetime = StreamLifetime()

        def pieces():
            try:
                stream = self._api().chat.completions.create(**kwargs)
            except ModelCallError:
                raise
            except Exception as exc:                          # noqa: BLE001 — SDK 예외를 이유 이름으로 바꾼다
                raise _api_error(exc) from None
            if not lifetime.acquire(stream):
                return
            try:
                for chunk in lifetime.iterate(stream):
                    for choice in getattr(chunk, "choices", None) or []:
                        if getattr(choice, "finish_reason", None) == "length":
                            held["length"] = True
                        piece = getattr(choice.delta, "content", None) or ""
                        if piece:
                            yield piece
            except ModelCallError:
                raise
            except Exception as exc:                          # noqa: BLE001
                raise _api_error(exc) from None

        text = collect(pieces, first_wait=first_wait, stall=stall, max_seconds=max_seconds, on_piece=on_piece, lifetime=lifetime).strip()
        if held.get("length"):
            raise OllamaContentError(f"답이 상한({max_tokens}토큰)에 걸려 잘렸다")
        if not text:
            raise ModelCallError("OpenAI 가 빈 답을 냈다", reason="empty")
        return text

    def text(self, system: str, user: str) -> str:
        return self._complete([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=800)

    def structured(self, system: str, user: str, schema: dict[str, Any], *, num_predict: int = 160) -> dict[str, Any]:
        """스키마를 `response_format` 으로 준다 — ★`[2026-10-15]` 엄격 모드(`strict_schema`)로 보내고 선택 키의 null 은 지워 돌려준다.
        ☆전에는 `strict: False` 였다 — 모델이 스키마를 지키지 않았다(위 `strict_schema`). 검증은 여전히 부르는 쪽(`decide`)이 한다."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        budget = max(300, int(num_predict) * 4)
        strict = {"type": "json_schema", "json_schema": {"name": "answer", "schema": strict_schema(schema), "strict": True}}
        try:
            text = self._complete(messages, response_format=strict, max_tokens=budget)
            try:
                value = self._object(text)
            except OllamaContentError:
                # Existing parse retry applies only to malformed JSON, not schema/evidence failures.
                text = self._complete(messages, response_format=strict, max_tokens=budget)
                value = self._object(text)
            return validate_structured(_drop_optional_nulls(value, schema), schema)
        except ModelCallError as exc:
            if exc.reason != "bad_request":
                raise
            # 스키마 모양을 이 모델이 거부했다 — 스키마를 글로 적어 json_object 로 다시 한 번
            messages[0] = {"role": "system", "content": system + "\nReply with a single JSON object that matches this JSON schema:\n"
                           + json.dumps(schema, ensure_ascii=False)}
            text = self._complete(messages, response_format={"type": "json_object"}, max_tokens=budget)
        return validate_structured(self._object(text), schema)

    def structured_validated(self, system: str, user: str, schema: dict[str, Any], *,
                             validator: Callable[[dict[str, Any]], None], num_predict: int = 160) -> dict[str, Any]:
        return validate_content(self.structured(system, user, schema, num_predict=num_predict), validator)

    def see(self, prompt: str, image: bytes, *, timeout: float = 60.0) -> str:
        mime = "image/jpeg" if image[:3] == b"\xff\xd8\xff" else "image/png"
        url = f"data:{mime};base64,{base64.b64encode(image).decode('ascii')}"
        return self._complete([{"role": "user", "content": [{"type": "text", "text": prompt},
                                                          {"type": "image_url", "image_url": {"url": url}}]}],
                              max_tokens=2000, timeout=timeout)

    def loaded(self, *, timeout: float = 5.0) -> bool:      # noqa: ARG002 — API 는 늘 준비돼 있다
        return True

    def warm(self) -> None:
        return None


# ─────────────────────────── 넘김 본체 ───────────────────────────
@dataclass
class _Backend:
    name: str
    chat: Any
    breaker: CircuitBreaker
    is_api: bool = False
    timeout: float = 6.0
    #: 이 경로가 호출 하나에 최대로 쓰는 시간(초) — 다시 시도 · 넘김이 전체 시간 안에 드는지 가늠할 때 쓴다
    budget: Callable[[], bool] | None = field(default=None, repr=False)
    reader_budget: Callable[[], bool] | None = field(default=None, repr=False)


class FailoverChat:
    """`OllamaChat` 과 같은 겉모양. 경로를 앞에서부터 시도한다(Ollama들 → OpenAI)."""

    def __init__(self, backends: list[_Backend], *, total_seconds: float = 15.0, vision: bool = False,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 backoff_seconds: float = 0.4, warm_chat: Any = None) -> None:
        if not backends:
            raise ValueError("경로가 하나는 있어야 한다")
        self._backends, self.total_seconds, self.vision = backends, float(total_seconds), bool(vision)
        self._sleep, self._clock, self._backoff = sleep, clock, float(backoff_seconds)
        first = next((b.chat for b in backends if not b.is_api), backends[0].chat)
        self._primary = first
        #: ★`[2026-10-13]` 예열에 쓸 Ollama — 고객 응답을 기다리는 짧은 시간(`llm_failover_primary_timeout_seconds`)이 아니라
        #:  모델을 올리는 데 드는 시간(`ollama_timeout_seconds`)으로 기다린다. 짧은 시간으로 예열하면 식은 모델(x600 서버 실측: 첫 로딩 28초)이
        #:  올라가는 도중 끊겨 끝내 못 올라가고, 모든 호출이 유료 API 로 넘어갔다(2026-10-13 아침 웹 채팅 시험).
        self._warm_chat = warm_chat or first
        self.model = getattr(first, "model", None)

    def __getattr__(self, name: str) -> Any:                   # 예열 · 진단이 쓰는 나머지 속성은 첫 Ollama 의 것
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._primary, name)

    # ── 호출 ──
    def _run(self, op: str, call: Callable[..., Any], *, image: bool = False, deadline: float | None = None, reader: bool = False, reader_external: bool = False) -> Any:
        started = self._clock()
        reasons: list[tuple[str, str]] = []
        for index, backend in enumerate(self._backends):
            if reader and backend.is_api and not reader_external:
                reasons.append((backend.name, "reader_external_disabled"))
                _count(f"skip:{backend.name}:reader_external_disabled")
                continue
            if backend.is_api and image and not self.vision:
                reasons.append((backend.name, "vision_off"))
                _count(f"skip:{backend.name}:vision_off")
                continue
            if not backend.breaker.allow():
                reasons.append((backend.name, "circuit_open"))
                _count(f"skip:{backend.name}:circuit_open")
                continue
            if backend.is_api and not reader and backend.budget is not None and not backend.budget():
                backend.breaker.release()
                reasons.append((backend.name, "budget_exhausted"))
                _count(f"skip:{backend.name}:budget_exhausted")
                log.warning("llm_failover op=%s backend=%s skipped: call budget exhausted", op, backend.name)
                continue
            later_api = any(b.is_api for b in self._backends[index + 1:])
            attempt = 0
            while True:
                if deadline is not None and deadline <= self._clock():
                    backend.breaker.release()
                    reasons.append((backend.name, "deadline_exhausted"))
                    break
                if reader and backend.is_api and not isinstance(backend.chat, OpenAIChat):
                    try:
                        allowed = backend.reader_budget is not None and bool(backend.reader_budget())
                    except Exception:
                        allowed = False
                    if not allowed:
                        backend.breaker.release()
                        reasons.append((backend.name, "reader_budget_unavailable"))
                        break
                    if deadline is not None and deadline <= self._clock():
                        backend.breaker.release()
                        reasons.append((backend.name, "deadline_exhausted"))
                        break
                def authorize_sdk_attempt():
                    if deadline is not None and deadline <= self._clock():
                        raise ModelSkipped("reader deadline exhausted")
                    try:
                        allowed = backend.reader_budget is not None and bool(backend.reader_budget())
                    except Exception:
                        allowed = False
                    if not allowed:
                        raise ModelSkipped("reader strict budget unavailable")
                    remaining = deadline - self._clock() if deadline is not None else self.total_seconds
                    if remaining <= 0:
                        raise ModelSkipped("reader deadline exhausted")
                    return remaining
                token = _reader_attempt.set(authorize_sdk_attempt if reader and backend.is_api else None)
                try:
                    result = call(backend.chat, backend.is_api)
                except OllamaError as exc:
                    failure = classify(exc)
                    _count(f"fail:{backend.name}:{failure.reason}")
                    elapsed = self._clock() - started
                    tail = max((b.timeout for b in self._backends[index + 1:]), default=0.0) if later_api else 0.0
                    time_left = deadline - started if deadline is not None else self.total_seconds
                    if failure.retryable and attempt == 0 and elapsed + self._backoff + backend.timeout + tail <= time_left:
                        attempt += 1
                        self._sleep(self._backoff)
                        continue
                    if failure.counts:
                        backend.breaker.failure()
                    else:
                        backend.breaker.success()            # 서버는 답했다 — 모양만 틀렸다
                    reasons.append((backend.name, failure.reason))
                    break
                except BaseException:                                # 우리가 모르는 예외 — 시험(반쪽) 자리가 잠겨 서버가 영영 안 불리지 않게 돌려주고 그대로 올린다
                    backend.breaker.release()
                    raise
                finally:
                    _reader_attempt.reset(token)
                backend.breaker.success()
                self._record(op, backend, reasons, self._clock() - started)
                return result
        _path_var.set({"path": None, "backend": None, "op": op, "reasons": reasons, "seconds": round(self._clock() - started, 2)})
        raise OllamaError("모든 모델 경로가 실패했다: " + ", ".join(f"{b}={r}" for b, r in reasons))

    def _record(self, op: str, backend: _Backend, reasons: list[tuple[str, str]], seconds: float) -> None:
        path = "api" if backend.is_api else "local"
        _count(f"ok:{op}:{backend.name}")
        _path_var.set({"path": path, "backend": backend.name, "model": getattr(backend.chat, "model", None), "op": op, "reasons": list(reasons), "seconds": round(seconds, 2)})
        if reasons:
            with _stats_lock:
                _last_switch.update(op=op, to=backend.name, reasons=[list(r) for r in reasons], at=time.time())
            log.warning("llm_failover op=%s path=%s backend=%s reasons=%s seconds=%.2f", op, path, backend.name,
                        ",".join(f"{b}:{r}" for b, r in reasons), seconds)

    def json(self, system: str, user: str) -> dict[str, Any]:
        return self._run("json", lambda chat, api: chat.json(system, masked(user) if api else user))

    def reader_json(self, system: str, user: str, *, external_fallback_enabled: bool = False,
                    max_seconds: float | None = None) -> dict[str, Any]:
        """Reader compatibility path; existing blocking transport timeout still applies."""
        deadline = self._clock() + min(self.total_seconds, max_seconds if max_seconds is not None else self.total_seconds)
        return self._run("reader_json", lambda chat, api: chat.json(system, masked(user) if api else user),
                         deadline=deadline, reader=True, reader_external=external_fallback_enabled)

    def json_stream(self, system: str, user: str, *, on_piece: Callable[[str, str], None] | None = None, first_wait: float = 15.0,
                    stall: float = 5.0, max_seconds: float = 180.0, max_tokens: int = 0) -> dict[str, Any]:
        """`json` 을 **조금씩 받기 + 멈춤 감시**로. `[2026-10-16 2회차 합의 · 사용자 승인]`
        ★한 답은 한 경로가 처음부터 끝까지 쓴다 — 로컬이 멈추거나(조각 끊김) 실패하면 받다 만 답을 버리고 **다음 경로(유료)가 처음부터 다시** 읽는다.
        ★로컬 Ollama 는 부르기 전에 모델이 올라와 있나 본다(`loaded`) — 안 올라와 있으면 올리느라 수십 초 걸리므로 곧바로 다음 경로로 간다(서버 장애로 세지 않는다).
        `on_piece(지금까지 모은 글, 경로)` — 경로는 `local` · `api`. 경로가 바뀌면 글이 처음부터 다시 쌓인다.
        ★`[2026-10-26]` 계획 읽기(접수 원문)는 이것이 아니라 `reader_json_stream` 을 쓴다(외부 대체 기본 차단 · reader 예산)."""
        return self._run("json_stream", self._streaming(
            lambda chat, text, relay: chat.json_stream(system, text, on_piece=relay, first_wait=first_wait, stall=stall,
                                                       max_seconds=max_seconds, max_tokens=max_tokens), user, on_piece, api_only=False))

    def structured_stream(self, system: str, user: str, schema: dict[str, Any], *, num_predict: int = 160,
                          on_piece: Callable[[str, str], None] | None = None, first_wait: float = 15.0, stall: float = 5.0,
                          max_seconds: float = 180.0, api_only: bool = False) -> dict[str, Any]:
        """`structured` 를 **조금씩 받기 + 멈춤 감시**로 — 넘김 규칙은 `json_stream` 과 같다. `[2026-10-16]`
        `api_only` — 로컬을 건너뛰고 유료만 쓴다.
        ★`[2026-10-26]` 계획 읽기 에이전트(`intake/agent_read.read`)는 이것이 아니라 `reader_structured_stream` 을 쓴다.
          이 메서드는 일반 업무(예: 감시 분류 계획 `feedback._ollama_structured`)의 기존 넘김 그대로다(가린 글 · 일반 예산)."""
        return self._run("structured_stream", self._streaming(
            lambda chat, text, relay: chat.structured_stream(system, text, schema, num_predict=num_predict, on_piece=relay,
                                                             first_wait=first_wait, stall=stall, max_seconds=max_seconds),
            user, on_piece, api_only=api_only))

    # ── 계획 읽기(reader) 전용 입구 `[2026-10-26 L03]` ──
    #   고객이 쓴 계획서 원문은 이름 · 예약번호 · 구분자 없는 전화번호를 다 가린다고 보장할 수 없다 → 외부(유료) 대체는 기본 차단
    #   (`travel.intake_reader.external_fallback_enabled: false`). 켜면 매 유료 시도마다 reader 예산(`reader_budget`, 못 읽으면 거부)을 예약하고,
    #   넘김 · 다시 시도 모두 한 절대 시한(`min(max_seconds, total_seconds)`) 안에서 남은 시간만 쓴다.
    def reader_json_stream(self, system: str, user: str, *, on_piece: Callable[[str, str], None] | None = None,
                           first_wait: float = 15.0, stall: float = 5.0, max_seconds: float = 180.0, max_tokens: int = 0,
                           external_fallback_enabled: bool = False) -> dict[str, Any]:
        deadline = self._clock() + min(max_seconds, self.total_seconds)
        def stream(chat, text, relay):
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise ModelSkipped("reader deadline exhausted")
            return chat.json_stream(system, text, on_piece=relay, first_wait=min(first_wait, remaining),
                                    stall=min(stall, remaining), max_seconds=remaining, max_tokens=max_tokens)
        return self._run("reader_json_stream", self._streaming(stream, user, on_piece, api_only=False),
                         deadline=deadline, reader=True, reader_external=external_fallback_enabled)

    def reader_structured_stream(self, system: str, user: str, schema: dict[str, Any], *, num_predict: int = 160,
                                 on_piece: Callable[[str, str], None] | None = None, first_wait: float = 15.0,
                                 stall: float = 5.0, max_seconds: float = 180.0, api_only: bool = False,
                                 external_fallback_enabled: bool = False) -> dict[str, Any]:
        deadline = self._clock() + min(max_seconds, self.total_seconds)
        def stream(chat, text, relay):
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise ModelSkipped("reader deadline exhausted")
            return chat.structured_stream(system, text, schema, num_predict=num_predict, on_piece=relay,
                                          first_wait=min(first_wait, remaining), stall=min(stall, remaining), max_seconds=remaining)
        return self._run("reader_structured_stream", self._streaming(stream, user, on_piece, api_only=api_only),
                         deadline=deadline, reader=True, reader_external=external_fallback_enabled)

    def structured_stream_validated(self, system: str, user: str, schema: dict[str, Any], *,
                                    validator: Callable[[dict[str, Any]], None], num_predict: int = 160,
                                    on_piece: Callable[[str, str], None] | None = None, first_wait: float = 15.0,
                                    stall: float = 5.0, max_seconds: float = 180.0) -> dict[str, Any]:
        """채팅 해석(`decision_unit.decide`)의 **조금씩 받기 + 멈춤 감시** — `structured_validated` 와 같은 검사(스키마 · 근거)를 경로 안에서 한다. `[2026-10-26 사용자 승인]`
        ★넘김 규칙은 `json_stream` 과 같다 — 로컬이 끊기거나(조각 감시) 모양 · 근거가 틀리면 받다 만 답을 버리고 다음 경로(유료)가 처음부터 다시 답한다.
        로컬 모델이 안 올라와 있으면 곧바로 다음 경로로 간다. 고정 대기 호출(`structured`)로 다시 부르지 않는다.
        ☆이 메서드가 없으면 `__getattr__` 이 첫 Ollama 의 것을 돌려 넘김 없이 로컬로만 갔다."""
        return self._run("structured_stream", self._streaming(
            lambda chat, text, relay: chat.structured_stream_validated(system, text, schema, validator=validator, num_predict=num_predict,
                                                                       on_piece=relay, first_wait=first_wait, stall=stall,
                                                                       max_seconds=max_seconds),
            user, on_piece, api_only=False))

    def _streaming(self, call: Callable[[Any, str, Any], Any], user: str, on_piece: Callable[[str, str], None] | None, *,
                   api_only: bool) -> Callable[[Any, bool], Any]:
        def run(chat: Any, api: bool) -> Any:
            if not api and api_only:
                raise ModelSkipped("유료만 쓰는 호출이다")
            if not api and hasattr(chat, "loaded") and not chat.loaded(timeout=2.0):
                if chat is self._primary:                     # 예열은 첫 Ollama 만(`warm` 과 같다) — 이번 요청은 기다리지 않고 다음 경로로
                    _start_warm(self)
                raise ModelNotLoaded(f"모델이 올라와 있지 않다: {getattr(chat, 'model', '')}")
            path = "api" if api else "local"
            relay = (lambda text: on_piece(text, path)) if on_piece is not None else None
            return call(chat, masked(user) if api else user, relay)
        return run

    def text(self, system: str, user: str) -> str:
        return self._run("text", lambda chat, api: chat.text(system, masked(user) if api else user))

    def structured(self, system: str, user: str, schema: dict[str, Any], *, num_predict: int = 160) -> dict[str, Any]:
        return self._run("structured", lambda chat, api: chat.structured(system, masked(user) if api else user, schema, num_predict=num_predict))

    def structured_validated(self, system: str, user: str, schema: dict[str, Any], *,
                             validator: Callable[[dict[str, Any]], None], num_predict: int = 160) -> dict[str, Any]:
        def call(chat: Any, api: bool) -> dict[str, Any]:
            result = chat.structured(system, masked(user) if api else user, schema, num_predict=num_predict)
            return validate_content(result, validator)

        return self._run("structured", call)

    def see(self, prompt: str, image: bytes, *, timeout: float = 240.0) -> str:
        return self._run("see", lambda chat, api: chat.see(prompt, image, timeout=60.0 if api else timeout), image=True)

    # ── 예열 — 첫 Ollama 만 데운다(API 는 데울 것이 없다). 실패는 그대로 올린다(예열 응답이 이유를 싣는다) ──
    def loaded(self, *, timeout: float = 5.0) -> bool:
        return self._primary.loaded(timeout=timeout)

    def warm(self) -> None:
        self._warm_chat.warm()


# ─────────────────────────── 조립 ───────────────────────────
#: 호출 상한을 세는 장치를 만드는 함수 — **조립 루트(`composition.py`)가 꽂는다**. 인프라는 도메인의 `CallBudget` 을 모르기 때문이다(계층 규칙).
#: 꽂히지 않았으면(스크립트 · 좁은 시험) 상한 없이 부르고 경고를 남긴다.
_budget_provider: Callable[[Any], Callable[[], bool]] | None = None
_reader_budget_provider: Callable[[Any], Callable[[], bool]] | None = None


def register_reader_budget_provider(provider: Callable[[Any], Callable[[], bool]] | None) -> None:
    global _reader_budget_provider
    _reader_budget_provider = provider


def register_budget_provider(provider: Callable[[Any], Callable[[], bool]] | None) -> None:
    """`provider(settings)` 는 「이번 API 호출을 해도 되나」를 답하는 함수를 돌려준다. 한도 표를 못 읽으면 **부른다**(서비스를 살리는 쪽 — 경고를 남긴다)."""
    global _budget_provider
    _budget_provider = provider


#: 식은 첫 Ollama 를 뒤에서 데우는 함수 `(chat) -> Any` — **조립 루트가 꽂는다**(기존 `model_warmup.warmup` 의 중복 억제 · 웹 예열과 같은 상태).
#: 안 꽂혔으면(스크립트 · 좁은 시험) 데우지 않는다. `[2026-10-26]`
_warm_starter: Callable[[Any], Any] | None = None
_warm_lock = threading.Lock()
_warm_running = False


def register_warm_starter(starter: Callable[[Any], Any] | None) -> None:
    global _warm_starter
    _warm_starter = starter


def _start_warm(chat: Any) -> None:
    """뒤에서(데몬 스레드) 예열을 한 번 시작한다. 이미 하나가 도는 중이면 스레드를 더 만들지 않는다. 실패는 경고 로그만 — 요청은 그대로 다음 경로로 간다."""
    global _warm_running
    starter = _warm_starter
    if starter is None:
        return
    with _warm_lock:
        if _warm_running:
            return
        _warm_running = True

    def job() -> None:
        global _warm_running
        try:
            starter(chat)
        except Exception as exc:                                  # noqa: BLE001 — 예열 실패가 고객 응답을 깨지 않게
            log.warning("llm_failover background warm failed: %s", type(exc).__name__)
        finally:
            with _warm_lock:
                _warm_running = False

    try:
        threading.Thread(target=job, name="llm-failover-warm", daemon=True).start()
    except RuntimeError as exc:                                   # 스레드를 못 만들면 자리를 돌려준다
        with _warm_lock:
            _warm_running = False
        log.warning("llm_failover background warm not started: %s", type(exc).__name__)


def budget_gate(settings: Any) -> Callable[[], bool] | None:
    """`[2026-10-15]` 유료 호출을 해도 되나를 답하는 함수. 상한을 셀 장치(조립 루트가 꽂는다)가 없으면 `None` — 부르는 쪽이 유료 호출을 안 한다."""
    return _budget_provider(settings) if _budget_provider is not None else None


def server_api_ready(settings: Any) -> bool:
    """서버용 키의 준비 여부만 반환한다. 호출부에는 키 값을 넘기지 않는다."""
    return bool((getattr(settings, "openai_api_key_server", "") or "").strip())


def server_api_chat(settings: Any, *, model: str, timeout: float) -> OpenAIChat:
    """명시적으로 선택된 유료 경로의 클라이언트도 같은 키 접근 경계를 쓴다."""
    return OpenAIChat(api_key=settings.openai_api_key_server.strip(), model=model, timeout=timeout)


def wrap_from_settings(primary: OllamaChat, settings: Any, *, budget: Callable[[], bool] | None = None, api_client: Any = None,
                       clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
                       extra_urls: tuple[str, ...] = (), api_first: bool = False,
                       local_fallback: OllamaChat | None = None) -> Any:
    """스위치가 꺼져 있거나 서버용 키가 없으면 `primary` 를 **그대로** 돌려준다. 켜져 있으면 `FailoverChat`.

    ★`[2026-10-15]` 관리 콘솔 「모델 경로」 — `extra_urls` 는 `primary` 바로 뒤에 시도할 Ollama(SSH 를 골랐을 때 이 기계의 Ollama),
    `api_first` 는 API 를 **맨 앞**에 두고 Ollama 들을 넘김 순서로 쓴다(API 를 고른 것이라 넘김 스위치가 꺼져 있어도 만든다 — 키는 있어야 한다)."""
    if not getattr(settings, "llm_failover_enabled", False) and not api_first:
        return primary
    key = (getattr(settings, "openai_api_key_server", "") or "").strip()
    if not key and local_fallback is None:
        log.warning("llm_failover enabled but ACOP_OPENAI_API_KEY_SERVER is empty — failover is off")
        return primary
    threshold = int(settings.llm_failover_failures)
    open_seconds = float(settings.llm_failover_open_seconds)
    primary_timeout = min(float(settings.ollama_timeout_seconds), float(settings.llm_failover_primary_timeout_seconds))
    backends: list[_Backend] = []
    urls = ([primary.base_url] + [u.strip().rstrip("/") for u in extra_urls if u and u.strip()]
            + [u.strip().rstrip("/") for u in (getattr(settings, "ollama_fallback_base_urls", "") or "").split(",") if u.strip()])
    for number, url in enumerate(dict.fromkeys(urls)):
        chat = OllamaChat(base_url=url, model=primary.model, timeout=primary_timeout, keep_alive=primary.keep_alive,
                          num_ctx=getattr(primary, "num_ctx", 0), wait_when_cold=False,
                          transport=primary._post if (number == 0 and primary._injected) else None)
        name = "ollama" if number == 0 else f"ollama{number + 1}"
        backends.append(_Backend(name, chat, breaker_for(f"{name}@{url}", threshold=threshold, open_seconds=open_seconds, clock=clock),
                                 timeout=primary_timeout))
    api_timeout = float(settings.llm_failover_api_timeout_seconds)
    model = (getattr(settings, "llm_failover_model", "") or settings.llm_model).strip()
    gate = budget or (_budget_provider(settings) if _budget_provider is not None else None)
    if gate is None:
        log.warning("llm_failover has no call-budget gate registered — API calls are not capped")
    if key:
        api = _Backend("openai", OpenAIChat(api_key=key, model=model, timeout=api_timeout, client=api_client),
                       breaker_for("openai", threshold=threshold, open_seconds=open_seconds, clock=clock),
                       is_api=True, timeout=api_timeout, budget=gate,
                       reader_budget=_reader_budget_provider(settings) if _reader_budget_provider else None)
        backends = [api] + backends if api_first else backends + [api]
    else:
        log.warning("llm_failover server API key absent — preserving final internal model recovery")
    if local_fallback is not None:
        backends.append(_Backend("local", local_fallback,
                                 breaker_for(f"local@{local_fallback.base_url}", threshold=threshold,
                                             open_seconds=open_seconds, clock=clock),
                                 timeout=float(local_fallback.timeout)))
    return FailoverChat(backends, total_seconds=float(settings.llm_failover_total_seconds), vision=bool(settings.llm_failover_vision),
                        sleep=sleep, clock=clock, warm_chat=primary)


# ─────────────────────────── 규정 검색의 질문 임베딩 ───────────────────────────
def embedding_failover_enabled(settings: Any) -> bool:
    """스위치가 켜져 있고 서버용 키가 있다."""
    return bool(getattr(settings, "llm_failover_enabled", False)) and bool((getattr(settings, "openai_api_key_server", "") or "").strip())


def embed_with_api(settings: Any, text: str, *, client: Any = None, budget: Callable[[], bool] | None = None) -> list[float]:
    """질문 하나를 OpenAI 임베딩(서버용 키)으로 만든다 — Ollama 임베딩이 안 될 때 `rag/retriever.py` 가 부른다.
    ★차원은 1536(`embedding` 칸) — 그 칸이 채워져 있어야 쓸 수 있다(`scripts/embed_chunks_openai.py`). 호출 상한 · 가리기 · 키 비노출은 채팅과 같다.
    상한을 넘었거나 부르지 못하면 `OllamaError` 를 올린다(조용히 비우지 않는다)."""
    gate = budget or (_budget_provider(settings) if _budget_provider is not None else None)
    if gate is not None and not gate():
        _count("skip:openai:budget_exhausted")
        raise ModelCallError("OpenAI 임베딩 호출 상한을 넘었다", reason="budget_exhausted")
    try:
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key_server.strip(), timeout=float(settings.llm_failover_api_timeout_seconds), max_retries=0)
        vector = client.embeddings.create(model=settings.embedding_model, input=masked(text)).data[0].embedding
    except ModelCallError:
        raise
    except Exception as exc:                                      # noqa: BLE001
        raise _api_error(exc) from None
    return list(vector)


def record_fallback(op: str, reason: str, *, backend: str = "openai") -> None:
    """Ollama 쪽이 안 돼 API 로 넘겼다는 기록 — 로그와 지표(채팅 경로 밖에서 넘길 때 쓴다)."""
    _count(f"ok:{op}:{backend}")
    with _stats_lock:
        _last_switch.update(op=op, to=backend, reasons=[["ollama", reason]], at=time.time())
    log.warning("llm_failover op=%s path=api backend=%s reasons=ollama:%s", op, backend, reason)


__all__ = ["CircuitBreaker", "FailoverChat", "ModelCallError", "ModelNotLoaded", "ModelSkipped", "OpenAIChat", "breaker_for", "budget_gate", "classify", "clear_path", "current_path", "embed_with_api", "embedding_failover_enabled", "record_fallback", "register_budget_provider", "register_warm_starter", "reset_state",
           "snapshot", "wrap_from_settings"]

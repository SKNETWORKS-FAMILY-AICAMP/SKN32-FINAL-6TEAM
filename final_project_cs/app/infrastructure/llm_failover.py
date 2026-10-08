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
from app.infrastructure.ollama_chat import OllamaChat, OllamaContentError, OllamaError

log = logging.getLogger("app.llm_failover")

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


def classify(exc: BaseException) -> Failure:
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
            value = json.loads(text)
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

    def text(self, system: str, user: str) -> str:
        return self._complete([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=800)

    def structured(self, system: str, user: str, schema: dict[str, Any], *, num_predict: int = 160) -> dict[str, Any]:
        """스키마를 `response_format` 으로 준다(엄격하지 않게 — 우리 스키마는 키가 모두 필수가 아닌 곳이 있다). 검증은 부르는 쪽(`decide`)이 한다."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        budget = max(300, int(num_predict) * 4)
        try:
            text = self._complete(messages, response_format={"type": "json_schema",
                                                             "json_schema": {"name": "answer", "schema": schema, "strict": False}},
                                  max_tokens=budget)
        except ModelCallError as exc:
            if exc.reason != "bad_request":
                raise
            # 스키마 모양을 이 모델이 거부했다 — 스키마를 글로 적어 json_object 로 다시 한 번
            messages[0] = {"role": "system", "content": system + "\nReply with a single JSON object that matches this JSON schema:\n"
                           + json.dumps(schema, ensure_ascii=False)}
            text = self._complete(messages, response_format={"type": "json_object"}, max_tokens=budget)
        return self._object(text)

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


class FailoverChat:
    """`OllamaChat` 과 같은 겉모양. 경로를 앞에서부터 시도한다(Ollama들 → OpenAI)."""

    def __init__(self, backends: list[_Backend], *, total_seconds: float = 15.0, vision: bool = False,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 backoff_seconds: float = 0.4) -> None:
        if not backends:
            raise ValueError("경로가 하나는 있어야 한다")
        self._backends, self.total_seconds, self.vision = backends, float(total_seconds), bool(vision)
        self._sleep, self._clock, self._backoff = sleep, clock, float(backoff_seconds)
        first = next((b.chat for b in backends if not b.is_api), backends[0].chat)
        self._primary = first
        self.model = getattr(first, "model", None)

    def __getattr__(self, name: str) -> Any:                   # 예열 · 진단이 쓰는 나머지 속성은 첫 Ollama 의 것
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._primary, name)

    # ── 호출 ──
    def _run(self, op: str, call: Callable[[Any, bool], Any], *, image: bool = False) -> Any:
        started = self._clock()
        reasons: list[tuple[str, str]] = []
        for index, backend in enumerate(self._backends):
            if backend.is_api and image and not self.vision:
                reasons.append((backend.name, "vision_off"))
                _count(f"skip:{backend.name}:vision_off")
                continue
            if not backend.breaker.allow():
                reasons.append((backend.name, "circuit_open"))
                _count(f"skip:{backend.name}:circuit_open")
                continue
            if backend.is_api and backend.budget is not None and not backend.budget():
                backend.breaker.release()
                reasons.append((backend.name, "budget_exhausted"))
                _count(f"skip:{backend.name}:budget_exhausted")
                log.warning("llm_failover op=%s backend=%s skipped: call budget exhausted", op, backend.name)
                continue
            later_api = any(b.is_api for b in self._backends[index + 1:])
            attempt = 0
            while True:
                try:
                    result = call(backend.chat, backend.is_api)
                except OllamaError as exc:
                    failure = classify(exc)
                    _count(f"fail:{backend.name}:{failure.reason}")
                    elapsed = self._clock() - started
                    tail = max((b.timeout for b in self._backends[index + 1:]), default=0.0) if later_api else 0.0
                    if failure.retryable and attempt == 0 and elapsed + self._backoff + backend.timeout + tail <= self.total_seconds:
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
                backend.breaker.success()
                self._record(op, backend, reasons, self._clock() - started)
                return result
        _path_var.set({"path": None, "backend": None, "op": op, "reasons": reasons, "seconds": round(self._clock() - started, 2)})
        raise OllamaError("모든 모델 경로가 실패했다: " + ", ".join(f"{b}={r}" for b, r in reasons))

    def _record(self, op: str, backend: _Backend, reasons: list[tuple[str, str]], seconds: float) -> None:
        path = "api" if backend.is_api else "local"
        _count(f"ok:{op}:{backend.name}")
        _path_var.set({"path": path, "backend": backend.name, "op": op, "reasons": list(reasons), "seconds": round(seconds, 2)})
        if reasons:
            with _stats_lock:
                _last_switch.update(op=op, to=backend.name, reasons=[list(r) for r in reasons], at=time.time())
            log.warning("llm_failover op=%s path=%s backend=%s reasons=%s seconds=%.2f", op, path, backend.name,
                        ",".join(f"{b}:{r}" for b, r in reasons), seconds)

    def json(self, system: str, user: str) -> dict[str, Any]:
        return self._run("json", lambda chat, api: chat.json(system, masked(user) if api else user))

    def text(self, system: str, user: str) -> str:
        return self._run("text", lambda chat, api: chat.text(system, masked(user) if api else user))

    def structured(self, system: str, user: str, schema: dict[str, Any], *, num_predict: int = 160) -> dict[str, Any]:
        return self._run("structured", lambda chat, api: chat.structured(system, masked(user) if api else user, schema, num_predict=num_predict))

    def see(self, prompt: str, image: bytes, *, timeout: float = 240.0) -> str:
        return self._run("see", lambda chat, api: chat.see(prompt, image, timeout=60.0 if api else timeout), image=True)

    # ── 예열 — 첫 Ollama 만 데운다(API 는 데울 것이 없다). 실패는 그대로 올린다(예열 응답이 이유를 싣는다) ──
    def loaded(self, *, timeout: float = 5.0) -> bool:
        return self._primary.loaded(timeout=timeout)

    def warm(self) -> None:
        self._primary.warm()


# ─────────────────────────── 조립 ───────────────────────────
#: 호출 상한을 세는 장치를 만드는 함수 — **조립 루트(`composition.py`)가 꽂는다**. 인프라는 도메인의 `CallBudget` 을 모르기 때문이다(계층 규칙).
#: 꽂히지 않았으면(스크립트 · 좁은 시험) 상한 없이 부르고 경고를 남긴다.
_budget_provider: Callable[[Any], Callable[[], bool]] | None = None


def register_budget_provider(provider: Callable[[Any], Callable[[], bool]] | None) -> None:
    """`provider(settings)` 는 「이번 API 호출을 해도 되나」를 답하는 함수를 돌려준다. 한도 표를 못 읽으면 **부른다**(서비스를 살리는 쪽 — 경고를 남긴다)."""
    global _budget_provider
    _budget_provider = provider


def wrap_from_settings(primary: OllamaChat, settings: Any, *, budget: Callable[[], bool] | None = None, api_client: Any = None,
                       clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> Any:
    """스위치가 꺼져 있거나 서버용 키가 없으면 `primary` 를 **그대로** 돌려준다. 켜져 있으면 `FailoverChat`."""
    if not getattr(settings, "llm_failover_enabled", False):
        return primary
    key = (getattr(settings, "openai_api_key_server", "") or "").strip()
    if not key:
        log.warning("llm_failover enabled but ACOP_OPENAI_API_KEY_SERVER is empty — failover is off")
        return primary
    threshold = int(settings.llm_failover_failures)
    open_seconds = float(settings.llm_failover_open_seconds)
    primary_timeout = min(float(settings.ollama_timeout_seconds), float(settings.llm_failover_primary_timeout_seconds))
    backends: list[_Backend] = []
    urls = [primary.base_url] + [u.strip().rstrip("/") for u in (getattr(settings, "ollama_fallback_base_urls", "") or "").split(",") if u.strip()]
    for number, url in enumerate(dict.fromkeys(urls)):
        chat = OllamaChat(base_url=url, model=primary.model, timeout=primary_timeout, keep_alive=primary.keep_alive,
                          transport=primary._post if (number == 0 and primary._injected) else None)
        name = "ollama" if number == 0 else f"ollama{number + 1}"
        backends.append(_Backend(name, chat, breaker_for(f"{name}@{url}", threshold=threshold, open_seconds=open_seconds, clock=clock),
                                 timeout=primary_timeout))
    api_timeout = float(settings.llm_failover_api_timeout_seconds)
    model = (getattr(settings, "llm_failover_model", "") or settings.llm_model).strip()
    gate = budget or (_budget_provider(settings) if _budget_provider is not None else None)
    if gate is None:
        log.warning("llm_failover has no call-budget gate registered — API calls are not capped")
    backends.append(_Backend("openai", OpenAIChat(api_key=key, model=model, timeout=api_timeout, client=api_client),
                             breaker_for("openai", threshold=threshold, open_seconds=open_seconds, clock=clock), is_api=True, timeout=api_timeout,
                             budget=gate))
    return FailoverChat(backends, total_seconds=float(settings.llm_failover_total_seconds), vision=bool(settings.llm_failover_vision),
                        sleep=sleep, clock=clock)


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


__all__ = ["CircuitBreaker", "FailoverChat", "ModelCallError", "OpenAIChat", "breaker_for", "classify", "clear_path", "current_path", "embed_with_api", "embedding_failover_enabled", "record_fallback", "register_budget_provider", "reset_state",
           "snapshot", "wrap_from_settings"]

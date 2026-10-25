# -*- coding: utf-8 -*-
"""Ollama 자체 API(`/api/chat`) 한 번 부르기 — 분류·추출·번역이 같이 쓴다.

실측(2026-09-14, Gemma 4):
    OpenAI 호환 `/v1/chat/completions` → 본문에 생각(thinking)이 섞이거나(토큰 1500)
                                          비어서(토큰 300) 왔다 — **쓰지 않는다**
    자체 `/api/chat` + `think:false` + `format:"json"` → `gemma4:12b` 1.3초, JSON 정확
    모델을 바꿔 부르면 GPU 에서 갈아 끼우느라 첫 호출이 30초를 넘는다 — 한 모델만 쓴다

★실패는 예외(`OllamaError`)로 올린다. 부르는 쪽이 그것을 「모름」으로 바꾼다 —
  여기서 빈 값을 성공처럼 돌려주지 않는다.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

import httpx


class OllamaError(RuntimeError):
    """Ollama 를 못 불렀거나 답이 쓸 수 없는 모양이다."""


class OllamaContentError(OllamaError):
    """서버는 답했는데 **답의 모양이 틀렸다**(JSON 이 아님 · 객체가 아님). `[2026-10-07]` 서버 문제(연결 · 시간 초과 · 5xx · 빈 답)와 구분한다 —
    모델 서버 넘김 장치(`llm_failover.py`)가 이 한 번만 다음 경로로 넘기고 서킷에는 세지 않는다. 부르는 쪽에는 `OllamaError` 와 같다."""


def validate_structured(value: Any, schema: dict[str, Any]) -> dict[str, Any]:
    """Reject malformed model output while failover still owns the call."""
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError

    try:
        Draft202012Validator(schema).validate(value)
    except ValidationError as exc:
        # Values and model output may include personal data; report only the path and rule.
        location = ".".join(str(part) for part in exc.absolute_path) or "$"
        raise OllamaContentError(f"구조화 답의 스키마가 다르다: {location} ({exc.validator})") from None
    if not isinstance(value, dict):
        raise OllamaContentError("구조화 답이 JSON 객체가 아니다")
    return value


def validate_content(value: dict[str, Any], validator: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """Run caller evidence checks before a backend result becomes successful."""
    try:
        validator(value)
    except ValueError as exc:
        raise OllamaContentError(f"구조화 답의 근거 검증 실패: {type(exc).__name__}") from None
    return value


class OllamaChat:
    def __init__(self, *, base_url: str, model: str, timeout: float = 60.0,
                 transport: Callable[..., httpx.Response] | None = None, keep_alive: str = "", num_ctx: int = 0,
                 wait_when_cold: bool = True) -> None:
        if not base_url:
            raise OllamaError("Ollama 주소가 비어 있다")
        self.base_url, self.model, self.timeout = base_url.rstrip("/"), model, timeout
        #: ★`[2026-09-29]` 모델을 메모리에 붙잡아 둘 시간(Ollama `keep_alive`, 예 "30m"). 비우면 Ollama 기본(5분) —
        #:  5분 안 쓰이면 내려가서 다음 첫 호출이 30초 가까이 걸렸다(ui 세션 실측 29.8초). 원격 GPU 메모리를 그만큼 잡는다
        self.keep_alive = keep_alive
        #: ★`[2026-10-14]` 문맥 길이(Ollama `num_ctx`). 0 이면 Ollama 기본 — **12~16GB GPU 에서는 4,096**이고, 넘치는 입력은 **앞에서부터 잘린다.**
        #:  요청 해석 입력(지시문 + 일정 + 대화)은 약 4,600 토큰이라 기본값이면 지시문 앞부분(할 일 정의)이 잘려 「다음 일정 뭐야?」를
        #:  「규정 질문」으로 골랐다(2026-10-14 GPU 서버 B 실측: 기본 2,051 토큰만 들어감 → 8,192 주면 4,576 토큰 다 들어가 맞게 고름).
        #:  ★같은 모델에 호출마다 다른 값을 보내면 Ollama 가 모델을 다시 올린다 — 이 객체의 모든 호출(예열 포함)이 같은 값을 보낸다.
        self.num_ctx = int(num_ctx or 0)
        self._injected = transport is not None      # 시험이 넣은 가짜 — 받아쓰기도 이것을 쓴다
        #: ★`[2026-10-26]` 식은 모델이면 조각 감시 대신 적재를 기다릴지(`structured_stream_validated`). 넘김 장치의 경로들은 끈다 — 넘김 장치가 이미 `loaded` 를 보고
        #:  식은 로컬을 건너뛰므로(다음 경로가 있다) 두 번 묻지 않고, 그 사이 내려가도 짧은 제한시간의 고정 대기로 바뀌지 않는다
        self.wait_when_cold = bool(wait_when_cold)
        #: ★`[2026-10-07]` 연결은 5초 안에 안 되면 끊는다 — 서버가 꺼졌을 때 읽기 제한(60초)만큼 기다리지 않게(넘김 장치가 빨리 알아야 한다)
        self._post = transport or (lambda url, payload: httpx.post(url, json=payload,
                                                                  timeout=httpx.Timeout(self.timeout, connect=min(5.0, self.timeout))))

    @property
    def reader_provenance(self) -> dict[str, str]:
        """Identity of this configured local reader, without a provider call."""
        return {"path": "local", "backend": "ollama", "model": self.model}

    def _options(self, base: dict[str, Any]) -> dict[str, Any]:
        return {**base, "num_ctx": self.num_ctx} if self.num_ctx > 0 else base

    def _chat(self, system: str, user: str, *, json_mode: bool) -> str:
        payload: dict[str, Any] = {
            "model": self.model, "stream": False, "think": False,
            "options": self._options({"temperature": 0}),
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}]}
        if json_mode:
            payload["format"] = "json"
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        try:
            response = self._post(f"{self.base_url}/api/chat", payload)
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama 호출 실패: {type(exc).__name__}: {exc}") from exc
        if response.status_code != 200:
            raise OllamaError(f"Ollama HTTP {response.status_code}: {response.text[:160]}")
        try:
            content = response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise OllamaError(f"Ollama 응답 모양이 다르다: {response.text[:160]}") from exc
        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama 가 빈 답을 냈다")
        return content.strip()

    def json(self, system: str, user: str) -> dict[str, Any]:
        text = self._chat(system, user, json_mode=True)
        try:
            value = json.loads(text)
        except ValueError as exc:
            raise OllamaContentError(f"JSON 이 아니다: {text[:160]}") from exc
        if not isinstance(value, dict):
            raise OllamaContentError("JSON 객체가 아니다")
        return value

    def json_stream(self, system: str, user: str, *, on_piece: Callable[[str], None] | None = None, first_wait: float = 15.0,
                    stall: float = 5.0, max_seconds: float = 180.0, max_tokens: int = 0) -> dict[str, Any]:
        """`json` 과 같은 답을 **조금씩 받아** 모은다 — 첫 조각 · 조각 사이 · 맨 위 상한을 따로 본다(`model_stream.collect`). `[2026-10-16]`
        `max_tokens` 는 답 토큰 상한(Ollama `num_predict`) — 같은 말을 되풀이하는 답을 끊는다. 상한에 걸려 잘린 답은 JSON 이 아니어서 `OllamaContentError`.
        ★시험이 넣은 가짜(`transport`)는 조금씩 주지 못한다 — 그때는 `json` 으로 한 번에 받고 `on_piece` 를 한 번 부른다."""
        if self._injected:
            value = self.json(system, user)
            if on_piece is not None:
                on_piece(json.dumps(value, ensure_ascii=False))
            return value
        return self._stream(system, user, "json", max_tokens, on_piece=on_piece, first_wait=first_wait, stall=stall,
                            max_seconds=max_seconds)

    def structured_stream(self, system: str, user: str, schema: dict[str, Any], *, num_predict: int = 160,
                          on_piece: Callable[[str], None] | None = None, first_wait: float = 15.0, stall: float = 5.0,
                          max_seconds: float = 180.0) -> dict[str, Any]:
        """`structured`(JSON 스키마 강제)와 같은 답을 **조금씩 받는다** — 계획 읽기 에이전트(`intake/agent_read`)가 쓴다. `[2026-10-16]`
        `num_predict` 는 답 토큰 상한 그대로. 시험이 넣은 가짜(`transport`)는 `structured` 로 한 번에 받는다."""
        if self._injected:
            value = self.structured(system, user, schema, num_predict=num_predict)
            if on_piece is not None:
                on_piece(json.dumps(value, ensure_ascii=False))
            return value
        return self._stream(system, user, schema, num_predict, on_piece=on_piece, first_wait=first_wait, stall=stall,
                            max_seconds=max_seconds)

    def structured_stream_validated(self, system: str, user: str, schema: dict[str, Any], *,
                                    validator: Callable[[dict[str, Any]], None], num_predict: int = 160,
                                    on_piece: Callable[[str], None] | None = None, first_wait: float = 15.0, stall: float = 5.0,
                                    max_seconds: float = 180.0) -> dict[str, Any]:
        """`structured_validated` 를 **조금씩 받기 + 멈춤 감시**로 — 채팅 해석(`decision_unit.decide`)이 쓴다. `[2026-10-26 사용자 승인]`
        스키마는 `format` 으로 그대로 보내고, 받은 답을 `structured` 와 같이 스키마로 검사한 뒤 부르는 쪽 근거 검사(`validator`)를 한다.
        ★`[2026-10-26]` 모델이 안 올라와 있으면(`loaded`) 적재(수십 초) 동안 첫 조각 감시가 끊어 답을 못 한다 — 넘김이 꺼진 로컬 서빙은 다음 경로가 없으므로
          그때는 적재를 기다리는 고정 대기 호출(`structured_validated`, 제한시간 `timeout`)로 답하고 `on_piece` 에 검사를 지난 최종 글을 한 번 준다.
          넘김 장치의 경로들(`wait_when_cold=False`)은 이 갈래를 쓰지 않는다 — 넘김 장치가 이미 `loaded` 를 보고 식은 로컬을 건너뛴다. 상태를 못 물으면 그대로 조금씩 받는다."""
        if self.wait_when_cold and not self._injected:
            try:
                cold = not self.loaded(timeout=2.0)
            except OllamaError:
                cold = False
            if cold:
                value = self.structured_validated(system, user, schema, validator=validator, num_predict=num_predict)
                if on_piece is not None:
                    on_piece(json.dumps(value, ensure_ascii=False))
                return value
        value = self.structured_stream(system, user, schema, num_predict=num_predict, on_piece=on_piece, first_wait=first_wait,
                                       stall=stall, max_seconds=max_seconds)
        return validate_content(validate_structured(value, schema), validator)

    def _stream(self, system: str, user: str, fmt: Any, max_tokens: int, *, on_piece: Callable[[str], None] | None,
                first_wait: float, stall: float, max_seconds: float) -> dict[str, Any]:
        from app.infrastructure.model_stream import collect, StreamLifetime

        options: dict[str, Any] = {"temperature": 0}
        if max_tokens > 0:
            options["num_predict"] = int(max_tokens)
        payload: dict[str, Any] = {"model": self.model, "stream": True, "think": False, "format": fmt,
                                   "options": self._options(options),
                                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        lifetime = StreamLifetime()

        def pieces():
            try:
                with httpx.stream("POST", f"{self.base_url}/api/chat", json=payload,
                                  timeout=httpx.Timeout(max_seconds, connect=min(5.0, max_seconds))) as response:
                    if not lifetime.acquire(response):
                        return
                    if response.status_code != 200:
                        raise OllamaError(f"Ollama HTTP {response.status_code}: {response.read()[:160]!r}")
                    for line in lifetime.iterate(response.iter_lines()):
                        if not line:
                            continue
                        part = json.loads(line)
                        if part.get("error"):
                            raise OllamaError(f"Ollama 오류: {str(part['error'])[:160]}")
                        yield (part.get("message") or {}).get("content") or ""
            except httpx.HTTPError as exc:
                raise OllamaError(f"Ollama 호출 실패: {type(exc).__name__}: {exc}") from exc

        text = collect(pieces, first_wait=first_wait, stall=stall, max_seconds=max_seconds, on_piece=on_piece, lifetime=lifetime).strip()
        if not text:
            raise OllamaError("Ollama 가 빈 답을 냈다")
        try:
            value = json.loads(text)
        except ValueError as exc:
            raise OllamaContentError(f"JSON 이 아니다(답 상한에 잘렸을 수 있다): {text[-80:]}") from exc
        if not isinstance(value, dict):
            raise OllamaContentError("JSON 객체가 아니다")
        return value

    def text(self, system: str, user: str) -> str:
        return self._chat(system, user, json_mode=False)

    def structured(self, system: str, user: str, schema: dict[str, Any], *, num_predict: int = 160) -> dict[str, Any]:
        """★`[2026-09-29]` 결정 단위 — Ollama `format` 에 **JSON 스키마**를 준다(enum 밖 값을 못 낸다). `think:false` ·
        temperature 0 · 짧은 답(`num_predict`). 실측(화면 세션, gemma4:12b): 25문장 중 24 맞음, 2.0~3.2초."""
        payload: dict[str, Any] = {
            "model": self.model, "stream": False, "think": False, "format": schema,
            "options": self._options({"temperature": 0, "num_predict": int(num_predict)}),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        try:
            response = self._post(f"{self.base_url}/api/chat", payload)
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama 호출 실패: {type(exc).__name__}: {exc}") from exc
        if response.status_code != 200:
            raise OllamaError(f"Ollama HTTP {response.status_code}: {response.text[:160]}")
        try:
            value = json.loads(response.json()["message"]["content"])
        except (ValueError, KeyError, TypeError) as exc:
            raise OllamaContentError(f"구조화 답이 JSON 이 아니다: {response.text[:160]}") from exc
        return validate_structured(value, schema)

    def structured_validated(self, system: str, user: str, schema: dict[str, Any], *,
                             validator: Callable[[dict[str, Any]], None], num_predict: int = 160) -> dict[str, Any]:
        return validate_content(self.structured(system, user, schema, num_predict=num_predict), validator)

    # ── 예열 `[2026-09-29]` — 식은 모델의 첫 호출이 30초 넘게 걸렸다(ui 세션 실측). 화면이 채팅을 열 때 미리 깨운다 ──
    def loaded(self, *, timeout: float = 5.0) -> bool:
        """이 모델이 지금 메모리에 올라가 있나(`/api/ps`). 못 물으면 `OllamaError`."""
        try:
            response = httpx.get(f"{self.base_url}/api/ps", timeout=timeout)
            models = response.json().get("models") or []
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError(f"Ollama 상태 조회 실패: {type(exc).__name__}: {exc}") from exc
        return any(m.get("name") == self.model or m.get("model") == self.model for m in models)

    def warm(self) -> None:
        """아주 짧은 생성 한 번(한 토큰)으로 모델을 올린다. 실패하면 `OllamaError`(모델 서버가 준 이유 그대로)."""
        payload: dict[str, Any] = {"model": self.model, "stream": False, "think": False,
                                   "options": self._options({"temperature": 0, "num_predict": 1}),
                                   "messages": [{"role": "user", "content": "."}]}
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        try:
            response = self._post(f"{self.base_url}/api/chat", payload)
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama 호출 실패: {type(exc).__name__}: {exc}") from exc
        if response.status_code != 200:
            raise OllamaError(f"Ollama HTTP {response.status_code}: {response.text[:200]}")

    def see(self, prompt: str, image: bytes, *, timeout: float = 240.0) -> str:
        """이미지 한 장을 보고 글로 답한다(비전). `[2026-09-27]` 계획 읽기의 **받아쓰기** 전용.

        ★실측(2026-09-26, guguroute : RAG): 「사진 → 일정 JSON」을 한 번에 시키면 6항목 중 3을 잃었고,
          「한 줄씩 그대로 받아 적어라」만 시키면 6/6 을 그대로 적었다(쪽당 약 45초). 그래서 구조화를 시키지 않는다.
        ★실패는 예외(`OllamaError`) — 빈 받아쓰기를 성공처럼 돌려주지 않는다.
        """
        import base64

        payload: dict[str, Any] = {
            "model": self.model, "stream": False, "think": False, "options": self._options({"temperature": 0}),
            "messages": [{"role": "user", "content": prompt,
                          "images": [base64.b64encode(image).decode("ascii")]}]}
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        try:
            if self._injected:
                response = self._post(f"{self.base_url}/api/chat", payload)
            else:                                       # ★받아쓰기는 쪽당 45초 안팎 — 긴 제한시간
                response = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=httpx.Timeout(timeout, connect=5.0))
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama 호출 실패: {type(exc).__name__}: {exc}") from exc
        if response.status_code != 200:
            raise OllamaError(f"Ollama HTTP {response.status_code}: {response.text[:160]}")
        try:
            content = response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise OllamaError(f"Ollama 응답 모양이 다르다: {response.text[:160]}") from exc
        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama 가 빈 받아쓰기를 냈다")
        return content.strip()


# ─────────────────────────── 모델 경로 — 상황마다 고른다 `[2026-10-15 · 10-16 사용자 지시]` ───────────────────────────
#: 경로: local = 이 기계의 Ollama(우리 학습 E4B) · ssh = SSH 터널 너머 런팟 GPU 서버의 Ollama · api = 유료 API(서버용 키)
#: 상황(purpose): chat = 채팅 해석 · 계획 읽기 · 번역 · 분류 · 신고 추출 / pointer = 일정 짚기 / notice = 공지 「끝났나」 · 「여행 영향」 확인
#: ★정하는 순서: 관리 콘솔 값(그 상황의 운영 설정) → 콘솔이 「끔」이거나 값이 없으면 **환경 파일**(`ACOP_MODEL_ROUTE_<상황>`, 기본 local).
#: ★고른 경로가 **먼저**고 나머지는 넘김 순서다 — ssh 는 이 기계 Ollama → (넘김이 켜져 있으면) API, api 는 이 기계 Ollama 로 넘긴다.
#: ★SSH 터널은 앱이 열지 않는다. 같은 기계에서 앱과 따로 도는 터널 프로그램이 연 입구(`ollama_ssh_base_url`)만 부른다 — 앱에 SSH 키를 두지 않는다.
ROUTES = ("local", "ssh", "api")
PURPOSES = ("chat", "pointer", "notice")
#: 상황마다 고를 수 있는 경로 — 일정 짚기 · 공지 확인은 우리 학습 모델만 쓰므로 API 가 없다(학습 모델은 API 에 없다)
ALLOWED = {"chat": ROUTES, "pointer": ("local", "ssh"), "notice": ("local", "ssh")}

#: 운영자가 관리 콘솔에서 고른 값을 읽는 함수 `(상황) -> "off" | 경로` — **조립 루트가 꽂는다**(인프라는 운영 설정 표를 모른다).
#: 안 꽂혔으면 콘솔은 「끔」과 같다(환경 파일을 따른다).
_route_provider: Callable[[str], str] | None = None
_warned: set[str] = set()
_log = logging.getLogger("app.model_route")


def register_route_provider(provider: Callable[[str], str] | None) -> None:
    global _route_provider
    _route_provider = provider


def console_choice(purpose: str = "chat") -> str:
    """관리 콘솔에서 고른 값. 못 읽거나 목록 밖 값이면 `off`(환경 파일을 따른다) — 고객 응답을 멈추지 않는 쪽."""
    if _route_provider is None:
        return "off"
    try:
        value = str(_route_provider(purpose) or "off")
    except Exception as exc:                            # noqa: BLE001 — 설정 표를 못 읽어도 답은 나가야 한다
        _warn_once(f"read:{purpose}:{type(exc).__name__}", "model route unreadable for %s (%s) — following the env file", purpose,
                   type(exc).__name__)
        return "off"
    return value if value in ALLOWED.get(purpose, ROUTES) else "off"


def resolve_route(settings: Any, purpose: str = "chat") -> str:
    """이번 호출의 경로 — 콘솔 값이 있으면 그것, 「끔」이면 환경 파일(`model_route_<상황>`), 그것도 목록 밖이면 local."""
    chosen = console_choice(purpose)
    if chosen != "off":
        return chosen
    env = str(getattr(settings, f"model_route_{purpose}", "local") or "local")
    if env not in ALLOWED.get(purpose, ROUTES):
        _warn_once(f"env:{purpose}:{env}", "ACOP_MODEL_ROUTE_%s=%s is not allowed — using local", purpose.upper(), env)
        return "local"
    return env


def current_route(purpose: str = "chat") -> str:
    """콘솔 값만으로 본 경로(환경 파일 없이) — 진단용. 실제 호출은 `resolve_route` 를 쓴다."""
    chosen = console_choice(purpose)
    return "local" if chosen == "off" else chosen


def _warn_once(key: str, message: str, *args: Any) -> None:
    if key not in _warned:
        _warned.add(key)
        _log.warning(message, *args)


def route_base_url(settings: Any, purpose: str = "pointer", route: str | None = None) -> str:
    """우리 학습 모델만 쓰는 자리(일정 짚기 · 공지 확인)가 부를 Ollama 주소. ssh 면 터널 입구(비었으면 이 기계), 그 밖은 이 기계."""
    local = (getattr(settings, "ollama_base_url", "") or "").strip()
    ssh = (getattr(settings, "ollama_ssh_base_url", "") or "").strip()
    chosen = route or resolve_route(settings, purpose)
    if chosen == "ssh" and not ssh:
        _warn_once(f"ssh:empty:{purpose}", "model route 'ssh' chosen for %s but ACOP_OLLAMA_SSH_BASE_URL is empty — using local Ollama", purpose)
    return ssh if chosen == "ssh" and ssh else local


def _build(settings: Any, route: str) -> Any:
    """한 경로의 클라이언트. 이 기계 Ollama 주소가 없으면 `None`(지금까지와 같다 — 부르는 쪽이 「모름」으로 간다)."""
    base = (getattr(settings, "ollama_base_url", "") or "").strip()
    if not base:
        return None

    def ollama(url: str, model: str = "") -> OllamaChat:
        return OllamaChat(base_url=url, model=model or getattr(settings, "ollama_model", "tripilot-pointer:e4b-ft"),
                          timeout=float(getattr(settings, "ollama_timeout_seconds", 60.0)),
                          keep_alive=str(getattr(settings, "ollama_keep_alive", "") or ""),
                          num_ctx=int(getattr(settings, "ollama_num_ctx", 0) or 0))

    failover = bool(getattr(settings, "llm_failover_enabled", False))
    if route == "ssh":
        ssh = (getattr(settings, "ollama_ssh_base_url", "") or "").strip()
        if ssh:
            from app.infrastructure.llm_failover import wrap_from_settings

            # 넘김이 꺼져 있으면 지금처럼 한 경로만 — 넘김 순서는 넘김 장치 몫이다
            primary = ollama(ssh, str(getattr(settings, "ollama_ssh_model", "") or ""))
            if not failover:
                return primary
            if getattr(settings, "llm_failover_local_last", False):
                return wrap_from_settings(primary, settings, local_fallback=ollama(base))
            return wrap_from_settings(primary, settings, extra_urls=(base,))
        _warn_once("ssh:empty:chat", "model route 'ssh' chosen but ACOP_OLLAMA_SSH_BASE_URL is empty — using local Ollama")
    if route == "api":
        from app.infrastructure.llm_failover import server_api_ready, wrap_from_settings

        if server_api_ready(settings):
            return wrap_from_settings(ollama(base), settings, api_first=True)
        _warn_once("api:nokey", "model route 'api' chosen but ACOP_OPENAI_API_KEY_SERVER is empty — using local Ollama")
    chat = ollama(base)
    if not failover:
        return chat
    from app.infrastructure.llm_failover import wrap_from_settings

    return wrap_from_settings(chat, settings)


class RoutedChat:
    """부를 때마다 그 상황의 경로를 읽어 그 경로의 클라이언트에 맡긴다 — 조립 때 한 번 만들어 오래 들고 있는 자리(신고 추출기 등)도
    재기동 없이 콘솔 변경을 따른다(반영은 운영 설정 캐시 시간만큼 늦을 수 있다). 겉모양(`json` · `text` · `structured` · `see` · `loaded` · `warm`)은 맡긴 쪽과 같다."""

    def __init__(self, settings: Any, purpose: str = "chat") -> None:
        self._settings = settings
        self._purpose = purpose
        self._clients: dict[str, Any] = {}

    def target(self) -> Any:
        route = resolve_route(self._settings, self._purpose)
        if route not in self._clients:                    # 경로마다 한 번 — 서킷 상태는 넘김 장치가 프로세스 전역으로 들고 있다
            self._clients[route] = _build(self._settings, route)
        return self._clients[route]

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.target(), name)


def from_settings(settings: Any, purpose: str = "chat") -> Any:
    """설정에 주소가 있으면 클라이언트, 없으면 `None`.

    ★`[2026-10-07 사용자 지시]` 스위치(`llm_failover_enabled`)가 켜져 있고 서버용 OpenAI 키가 있으면 **같은 메서드를 가진 `FailoverChat`** 을 돌려준다 —
    Ollama 가 모두 안 될 때 서버용 키로 자동으로 넘어간다(`llm_failover.py`). 꺼져 있으면 지금까지와 똑같이 `OllamaChat` 이다.
    ★`[2026-10-15]` 조립 루트가 콘솔 값 읽는 함수를 꽂았으면(`register_route_provider`) 부를 때마다 경로를 고르는 `RoutedChat` 을 돌려준다.
    안 꽂혔으면 환경 파일(`ACOP_MODEL_ROUTE_CHAT`, 기본 local)의 경로로 한 번 만든다."""
    if not (getattr(settings, "ollama_base_url", "") or "").strip():
        return None
    if _route_provider is not None:
        return RoutedChat(settings, purpose)
    return _build(settings, resolve_route(settings, purpose))


__all__ = ["ALLOWED", "OllamaChat", "OllamaContentError", "OllamaError", "PURPOSES", "ROUTES", "RoutedChat", "console_choice",
           "current_route", "from_settings", "register_route_provider", "resolve_route", "route_base_url"]

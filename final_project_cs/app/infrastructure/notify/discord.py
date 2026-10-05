# -*- coding: utf-8 -*-
"""디스코드 웹훅 — v11 §6-A 의 알림 채널(무료 채널 중 가장 간단한 것 하나).

★바깥함 일꾼(`OutboxWorker`)의 발행자 자리에 끼운다. 일꾼의 규칙을 그대로 따른다:

    전송 성공(2xx)                   → 반환 → 일꾼이 `delivered`
    타임아웃·연결 끊김                → TimeoutError / ConnectionError
                                       → 일꾼이 **`unknown`** — 갔는지 모른다.
                                         성공으로 추정하지 않고 자동 재전송도 안 한다
                                         (CLAUDE.md §0.2). 같은 알림이 두 번 가는 것도
                                         사고다.
    너무 자주 보냄(429)               → RetryAfter → 일꾼이 **디스코드가 말한 시각**에
                                         다시 집는다. ★`[2026-10-03]` 전에는 이것도
                                         RuntimeError 로 올려 고정 1분 뒤에 다시 걸었다.
                                         디스코드 문서는 `Retry-After` 를 따르라고
                                         요구하고, 어기면 **IP 단위로 막는다**
                                         (유효하지 않은 요청 10분에 10,000건).
    그 밖의 실패(5xx·4xx)             → RuntimeError → 일꾼이 재시도, 한도 넘으면
                                         `dead_letter`

★★**웹훅이 설정돼 있지 않으면 실패로 올린다**(`NoticeNotConfigured`). 조용히 반환하면
  일꾼이 `delivered` 로 찍는다 — **보내지 않은 알림이 보낸 것으로 기록된다.** 그게
  이 저장소가 여러 번 데인 「조용한 성공 위장」이다.

★재생 통지에는 **`[재생]` 을 앞에 붙인다**(v11 §8-A). 시연 알림을 실제 사건 알림으로
  읽지 않게 한다.

★디스코드 메시지 본문 한도는 2,000자다. 넘으면 자르되 잘랐다는 표시를 남긴다.

★`[2026-09-22]` **문구틀·언어마다 한 번만 옮긴다**(wiki `architecture/notifications.md` 「언어」).
  payload 가 `template`+`values` 를 들고 오면(②·③ 안내) **틀만** 모델에 주고 값은 원값으로
  채운다 — 같은 언어의 다음 안내는 모델을 안 부른다. `text` 만 들고 오는 통지(① 변경 통지의
  대안 설명)는 그때그때 생성된 문장이라 **담아 두지 않고** 전처럼 매번 옮긴다.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

import httpx

from .phrase import Phrase, PhraseCache, fill
from .suppressed import NoticeSuppressed

logger = logging.getLogger(__name__)

MAX_CONTENT = 2000
#: 공급자가 말한 대기 시간을 받아들일 상한(초). ★그쪽이 이상한 값을 줘도 알림이
#:  하루 넘게 멈추면 안 된다. 15분을 넘기면 안 믿고 우리 기본 간격을 쓴다.
MAX_RETRY_AFTER_SECONDS = 900.0

#: 본문 밖에서 붙이는 줄(다른 안·버전·링크)의 값 자리 이름. ★본문 틀은 `_` 로 시작하는
#:  이름을 쓰지 않는다 — 겹치면 값이 엉킨다(`_compose` 가 막는다).
_OPTIONS, _VERSION, _URL = "_options", "_version", "_url"


class RetryAfter(RuntimeError):
    """디스코드가 「이때 다시 와라」고 한 경우(429).

    ★우리가 간격을 지어내지 않는다. 공급자가 정확한 값을 주는데 추측으로 덮으면
      더 자주 두드리거나(차단) 쓸데없이 늦어진다. 둘 다 손해다.
    ★`seconds` 는 **그쪽이 말한 값**이다. 못 읽으면 None 이고, 그때만 우리 기본값을 쓴다.
    """

    def __init__(self, message: str, seconds: float | None) -> None:
        super().__init__(message)
        self.seconds = seconds


def _retry_after(response: httpx.Response) -> float | None:
    """`Retry-After` 헤더 또는 본문 `retry_after` 를 초로 읽는다.

    ★둘 다 본다 — 디스코드는 헤더와 본문 양쪽에 같은 값을 싣는다고 적어 두었고,
      어느 한쪽이 없을 때를 대비한다. 음수·말도 안 되게 큰 값은 믿지 않는다.
    """
    raw: Any = response.headers.get("Retry-After")
    if raw is None:
        try:
            raw = (response.json() or {}).get("retry_after")
        except Exception:
            raw = None
    try:
        seconds = float(raw)
    except (TypeError, ValueError):
        return None
    # ★상한을 둔다. 공급자가 잘못된 값을 줘도 알림이 하루 넘게 멈추면 안 된다.
    if seconds < 0 or seconds > MAX_RETRY_AFTER_SECONDS:
        return None
    return seconds


class NoticeNotConfigured(RuntimeError):
    """보낼 곳이 설정되지 않았다. ★보낸 것으로 기록되면 안 된다."""


def _cut(content: str) -> str:
    if len(content) > MAX_CONTENT:
        return content[:MAX_CONTENT - 12] + "\n…(잘림)"
    return content


def phrase_of(payload: dict[str, Any]) -> Phrase:
    """통지 payload → **옮길 틀 + 옮기지 않을 원값**.

    ★두 갈래다.
      `template`+`values` 가 있으면(안내) 시각·장소·버전·링크가 전부 **값**으로 빠져 있어
      틀을 담아 둘 수 있다. `text` 만 있으면(변경 통지) 문장 자체가 매번 다른 생성물이라
      통째로 틀이 되고 `cacheable=False` 다 — 완성 문장을 캐시하지 않는다.
    """
    template = payload.get("template")
    values: dict[str, Any] = dict(payload.get("values") or {}) if template else {}
    if template:
        body, cacheable = str(template), True
        if any(str(name).startswith("_") for name in values):
            raise ValueError("본문 값 이름은 `_` 로 시작할 수 없다 — 덧붙이는 줄과 겹친다")
    else:
        body, cacheable = str(payload.get("text") or ""), False
    if not _filled(body, values):
        raise ValueError("통지 본문이 비어 있다 — 빈 알림을 보내지 않는다")
    return _compose(body.strip(), values, payload, cacheable=cacheable)


def _filled(body: str, values: dict[str, Any]) -> str:
    """값을 채운 뒤의 본문 — 비었는지·「다른 안」이 이미 들어 있는지는 채운 뒤로 본다."""
    return fill(body, values).strip()


def _compose(body: str, values: dict[str, Any], payload: dict[str, Any], *,
             cacheable: bool) -> Phrase:
    """본문에 덧붙는 줄(다른 안·버전·링크)을 얹는다.

    ★담아 둘 수 있는 통지에서는 덧붙는 줄의 **값도 자리로 뺀다** — 대안 이름·버전 번호·링크는
      알림마다 다르므로 틀에 박으면 캐시 열쇠가 알림마다 달라지고(재사용 0), 무엇보다
      값이 틀에 섞인다. 담아 두지 않는 통지는 전처럼 그대로 박는다(문구가 한 글자도 안 바뀐다).
    """
    lines = [("[재생] " if payload.get("replay") else "") + body]
    others = [str(option) for option in (payload.get("other_options") or [])]
    if others and "다른 안" not in _filled(body, values):
        if cacheable:
            values[_OPTIONS] = ", ".join(others)
            lines.append("다른 안: {%s}" % _OPTIONS)
        else:
            lines.append("다른 안: " + ", ".join(others))
    if payload.get("version") is not None:
        if cacheable:
            values[_VERSION] = payload["version"]
            lines.append("(일정 버전 {%s})" % _VERSION)
        else:
            lines.append(f"(일정 버전 {payload['version']})")
    if payload.get("plan_url"):
        # ★상태의 정본은 링크다(v11 §6-A) — 안내에는 늘 붙인다. 주소는 옮기지 않는다.
        if cacheable:
            values[_URL] = str(payload["plan_url"])
            lines.append("{%s}" % _URL)
        else:
            lines.append(str(payload["plan_url"]))
    return Phrase("\n".join(lines), values, cacheable=cacheable)


def render(payload: dict[str, Any]) -> str:
    """통지 payload → 사람에게 보일 한 덩어리 글(한국어 원문)."""
    return _cut(phrase_of(payload).render())


class DiscordWebhook:
    """`OutboxWorker` 의 발행자. 다룰 주제만 보내고 나머지는 넘긴다."""

    TOPICS = frozenset({"trip.notice"})

    #: 바깥으로 보낼 테넌트. ★`[2026-09-22]` **기본이 「운영 테넌트 하나」**다 — 시연·시험 테넌트의
    #:  통지가 실제 채널로 나간 사고가 있었다(8건). `None` 을 주면 전부 보낸다(옛 동작).
    def __init__(self, url: str, *, timeout: float = 8.0, allowed_tenants: set[str] | None = None,
                 transport: Callable[..., httpx.Response] | None = None,
                 fallback: Callable[[dict[str, Any]], Any] | None = None,
                 translator: Callable[[str, str], str] | None = None,
                 phrases: PhraseCache | None = None) -> None:
        self.url = url
        self.allowed_tenants = None if allowed_tenants is None else set(allowed_tenants)
        self._timeout = timeout
        self._post = transport or self._http_post
        # ★다른 주제는 원래 발행자에게 넘긴다. 이 파일이 모든 주제를 삼키지 않는다.
        self._fallback = fallback
        # ★보낼 때 고객 언어로 옮긴다(결정 14). 없으면 한국어 원문 그대로.
        self._translator = translator
        # ★문구틀·언어마다 한 번만 옮긴다. 담기는 것은 **틀**이지 완성 문장이 아니다.
        self.phrases = phrases if phrases is not None else PhraseCache()
        self.translation_failures = 0

    def _localize(self, phrase: Phrase, locale: str | None) -> str:
        """★번역이 실패해도 알림은 보낸다 — 원문에 실패 표시를 붙인다(안 보내는 것보다 낫다).
        실패는 세어 둔다(조용한 스킵 금지).

        ★값은 여기서 채운다 — 캐시에서 온 것은 옮겨진 **틀**뿐이라 이 알림의 시각·장소가
          다른 알림의 것으로 바뀔 길이 없다."""
        from .translate import is_korean

        if self._translator is None or is_korean(locale):
            return phrase.render()
        try:
            return self.phrases.localize(phrase, str(locale), self._translator)
        except Exception as exc:
            self.translation_failures += 1
            logger.warning("notice translation failed (%s): %s", locale, exc)
            return f"[번역 실패 — 한국어 원문] {phrase.render()}"

    def text_for(self, payload: dict[str, Any]) -> str:
        """통지 payload → 보낼 글(고객 언어로 옮긴 **평문**). 길이는 자르지 않는다 — 채널마다 한도가 다르다(디스코드 2,000 · 텔레그램 4,096).
        ★`[2026-10-05]` 고객별 발송(`travel_ops/notice_routing.py`)이 같은 문구 · 번역 · `[재생]` 규칙을 쓰려고 연 자리다."""
        return self._localize(phrase_of(payload), payload.get("locale"))

    def _http_post(self, url: str, json: dict[str, Any]) -> httpx.Response:
        return httpx.post(url, json=json, timeout=self._timeout)

    def __call__(self, message: dict[str, Any]) -> None:
        if message.get("topic") not in self.TOPICS:
            if self._fallback is not None:
                return self._fallback(message)
            return None
        tenant = str(message.get("tenant_id") or "")
        if self.allowed_tenants is not None and tenant not in self.allowed_tenants:
            raise NoticeSuppressed(
                f"보낼 대상이 아닌 테넌트({tenant or '이름 없음'}) — 바깥으로 보내지 않았다. "
                f"보내는 테넌트: {sorted(self.allowed_tenants)}")
        if not self.url:
            raise NoticeNotConfigured(
                "ACOP_DISCORD_WEBHOOK_URL 이 비어 있다 — 알림을 보내지 않았다")
        payload = message.get("payload") or {}
        # ★자르는 것은 **값을 채운 뒤**다 — 틀을 잘라 담아 두면 다음 알림까지 잘린다.
        content = _cut(self._localize(phrase_of(payload), payload.get("locale")))
        try:
            response = self._post(self.url, json={"content": content})
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"discord webhook timeout: {exc}") from exc
        except httpx.TransportError as exc:
            raise ConnectionError(f"discord webhook transport: {exc}") from exc
        if response.status_code == 429:
            seconds = _retry_after(response)
            raise RetryAfter(
                "discord webhook 429 — %s 뒤에 다시 보낸다"
                % ("%.3f초" % seconds if seconds is not None else "기본 간격"), seconds)
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f"discord webhook HTTP {response.status_code}: "
                               f"{response.text[:200]}")
        return None


__all__ = ["DiscordWebhook", "MAX_CONTENT", "MAX_RETRY_AFTER_SECONDS",
           "NoticeNotConfigured", "RetryAfter", "phrase_of", "render"]

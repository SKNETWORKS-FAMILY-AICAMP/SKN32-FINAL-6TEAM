# -*- coding: utf-8 -*-
"""공지 「끝났나」의 **2차 확인** — 우리 데이터로 가르친 모델이 규칙의 「끝남」을 한 번 더 본다 `[2026-10-13 사용자 지시]`.

★왜. 규칙은 「버스 파업으로 출근길 불편 … 마을버스는 정상운행」을 파업이 끝났다고 읽고, 「한 방향 통제 해제 … 반대 방향은 통행 불가」를
  전부 끝났다고 읽었다. 서울 재난 문자 190건(정답은 Claude, 2026-10-13)에서 「끝났다」를 잘못 낸 수가 규칙 5 · x600 의 가르친 E4B
  (`tripilot-pointer:e4b-ft`) 2 였고, 놓친 수는 둘 다 0 이었다. 규칙의 분명한 오류 2건을 모델은 둘 다 맞혔다
  (기록 `wiki/records/reports/2026-10-13_0100_끝남판정_규칙대모델_실수율.md`).
★어떻게 합치나 — **규칙과 모델이 둘 다 「끝남」일 때만 끝남**이다. 모델은 규칙의 「끝남」을 거부할 수만 있고, 규칙이 못 본 끝남을 새로 만들지 않는다
  (잘못된 「끝남」은 경고를 조용히 지운다 — 틀려도 경고가 남는 쪽으로 틀리게 한다). 같은 표본에서 이 방식은 모델 혼자와 결과가 같았다.
★모델이 「끝남」이라고 하려면 근거 조각이 본문에 있어야 한다(「…」로 이은 조각은 나눠서 하나씩 본다). 없으면 「끝남 아님」으로 본다.
★모델을 못 부르면(꺼짐 · 시간 초과 · 형식 오류) **규칙 결과를 그대로 쓴다** — 대신 실패를 세고 경고로 남긴다(조용히 넘기지 않는다).
★켜는 법: `.env` 의 `ACOP_OLLAMA_NOTICE_MODEL`(Ollama 에 올린 모델 이름) + 가드레일 `travel.notice_end.mode` —
  `off`(규칙만) · `shadow`(모델도 불러 다른 판정만 남기고 규칙 결과를 쓴다) · `on`(둘 다 끝남일 때만 끝남). 모델 이름이 비면 꺼진 것과 같다.
★같은 본문은 한 번만 부른다(본문 → 판정 캐시). 감시가 같은 문자를 몇 분마다 다시 읽어도 모델 호출은 한 번이다.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from collections import OrderedDict
from typing import Any, Callable

logger = logging.getLogger(__name__)

PROMPT_VERSION = "notice_end.v1-2026-10-13"
#: 2026-10-13 평가 때 모델에 준 기준서(`datasets/safety/disaster_msg_seoul_2026/eval/label_guide.md`)와 같은 글이다 — 지시문을 바꾸면 다시 잰다
SYSTEM = """# 재난 문자 「끝났나」 판정 기준

재난 문자 한 통을 읽고 다음을 정한다.

> 이 문자가 알리는 사건(도로 통제, 열차·버스 운행 중단, 정전, 파업, 화재, 시설 고장 등)이 **이 문자를 보낸 시점에 이미 완전히 끝나 정상으로 돌아왔다**고 알리는가?

## state (다섯 중 하나)

| state | 뜻 | 지어낸 예 |
|---|---|---|
| ended | 그 사건이 **전부** 끝났다고 알린다 | 「○○로 통제가 풀려 차량 통행이 가능합니다」 · 「○○선 운행이 정상화되었습니다」 |
| partial | **일부만** 풀리고 나머지는 계속된다 | 「4개 차로 중 2개 차로만 통행 가능」 |
| scheduled | **앞으로** 끝날 것이라는 예정·조건이다(아직 안 끝남) | 「17시에 통제를 풀 예정」 · 「복구될 때까지 운행 중지」 |
| unsettled | 끝을 말하지만 **아직 진행 중이거나 확정되지 않았다** | 「복구 작업 중」 · 「재개 여부는 확인 중」 |
| no_end_signal | 끝에 대한 말이 **없다** — 사건 발생 알림, 주의·대피 안내, 예방 홍보, 훈련 안내 등 | 「○○동 화재 발생, 주변 우회 바랍니다」 |

## 정할 때 지킬 것

- 본문에 쓰인 것만 본다. 보낸 기관이나 시각으로 짐작하지 않는다.
- 한 문자에 사건이 여럿이면 **문자가 주로 알리는 사건**을 기준으로 한다. 주로 알리는 사건이 아직 진행 중이면 다른 노선·구간이 정상이라는 말이 있어도 ended 가 아니다.
- 날씨 특보·경보가 「해제」되었다는 문자는 ended 다.
- 애매하면 ended 로 하지 않는다(끝났다는 말이 분명할 때만 ended).

## 답 모양 (JSON 하나만)

```json
{"state": "ended", "ended": true, "evidence": "본문에서 그대로 복사한 30자 이내 조각"}
```

- `ended` 는 `state == "ended"` 일 때만 true.
- `evidence` 는 판단의 근거가 된 본문 조각을 **글자 그대로** 복사한다. no_end_signal 이면 빈 문자열.
"""
PROMPT_SHA = hashlib.sha1(SYSTEM.encode("utf-8")).hexdigest()[:12]

#: 실행 중 센 값 — 「모델이 쓰이고 있나 · 실패가 얼마나 나나 · 규칙을 몇 번 거부했나」(조용한 폴백을 만들지 않는다)
STATS: dict[str, int] = {"calls": 0, "cache_hits": 0, "failed": 0, "agreed": 0, "vetoed": 0, "shadow_diff": 0}
_SPLIT = re.compile(r"\s*(?:\.{3}|…)\s*")


def evidence_in_text(evidence: str, text: str) -> bool:
    """근거 조각이 본문에 있나 — 「…」·「...」로 이은 조각은 나눠 하나씩 본다."""
    parts = [p for p in _SPLIT.split(str(evidence or "").strip()) if p]
    return bool(parts) and all(p in text for p in parts)


class NoticeEndModel:
    """`notice_status.set_second_opinion` 에 꽂는 호출 가능 객체. 규칙이 「끝남」이라 한 본문에만 불린다.

    돌려주는 값: True(모델도 끝남) · False(모델은 끝남 아님 — `on` 이면 규칙의 끝남을 거부) · None(못 정함 → 규칙 결과)."""

    def __init__(self, *, base_url: str, model: str, timeout: float = 90.0, keep_alive: str = "",
                 mode: Callable[[], str] | str = "on", post: Callable[[str, dict, float], Any] | None = None,
                 cache_size: int = 2048) -> None:
        self.base_url, self.model, self.timeout, self.keep_alive = base_url.rstrip("/"), model, timeout, keep_alive
        #: ★`[2026-10-15]` 관리 콘솔 「모델 경로」를 따를 때 조립이 꽂는 주소 함수(부를 때마다 읽는다). 비면 `base_url` 고정
        self.base_url_for: Callable[[], str] | None = None
        self._mode = mode if callable(mode) else (lambda: str(mode))
        self._post = post or self._http
        self._cache: OrderedDict[str, bool] = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()

    def current_base_url(self) -> str:
        """이번 호출이 부를 Ollama 주소 — 꽂힌 주소 함수가 있으면 그 값(비면 고정 주소), 없으면 고정 주소."""
        if self.base_url_for is not None:
            try:
                chosen = (self.base_url_for() or "").strip().rstrip("/")
            except Exception:                    # noqa: BLE001 — 경로를 못 읽으면 고정 주소로 부른다
                chosen = ""
            if chosen:
                return chosen
        return self.base_url

    @staticmethod
    def _http(url: str, payload: dict, timeout: float) -> Any:
        import httpx

        return httpx.post(url, json=payload, timeout=httpx.Timeout(timeout, connect=min(5.0, timeout)))

    def _ask(self, text: str) -> bool:
        """모델 한 번 — 끝남이면 True. 못 부르거나 형식이 틀리면 예외."""
        payload: dict[str, Any] = {"model": self.model, "stream": False, "think": False, "format": "json",
                                   "options": {"temperature": 0},
                                   "messages": [{"role": "system", "content": SYSTEM},
                                                {"role": "user", "content": "재난 문자:\n" + text}]}
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        response = self._post(f"{self.current_base_url()}/api/chat", payload, self.timeout)
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:120]}")
        answer = json.loads(response.json()["message"]["content"])
        if not isinstance(answer, dict):
            raise ValueError("JSON 객체가 아니다")
        said = answer.get("state") == "ended" or answer.get("ended") is True
        return said and evidence_in_text(str(answer.get("evidence") or ""), text)

    def __call__(self, text: str) -> bool | None:
        mode = self._mode()
        if mode not in ("shadow", "on"):
            return None
        with self._lock:
            if text in self._cache:
                self._cache.move_to_end(text)
                STATS["cache_hits"] += 1
                verdict: bool | None = self._cache[text]
            else:
                verdict = None
        if verdict is None:
            STATS["calls"] += 1
            try:
                verdict = self._ask(text)
            except Exception as exc:                       # noqa: BLE001 — 모델 실패는 규칙 결과로 돌아간다(세고 남긴다)
                STATS["failed"] += 1
                logger.warning("공지 끝남 2차 확인 실패 — 규칙 결과를 씀 (%s · %s): %s", self.model, PROMPT_VERSION, exc)
                return None
            with self._lock:
                self._cache[text] = verdict
                while len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
        if verdict:
            STATS["agreed"] += 1
        elif mode == "on":
            STATS["vetoed"] += 1
            logger.info("공지 끝남 2차 확인: 모델이 규칙의 「끝남」을 거부 (%s) — %s", self.model, text[:80])
        else:
            STATS["shadow_diff"] += 1
            logger.info("공지 끝남 2차 확인(비교만): 모델은 「끝남 아님」 (%s) — %s", self.model, text[:80])
        return verdict if mode == "on" else None


IMPACT_PROMPT_VERSION = "notice_impact.v1-2026-10-13"
#: 2026-10-13 전국 평가 때 모델에 준 기준서(`datasets/safety/disaster_msg_korea_2023_2026/eval/gita_label_guide.md`)와 같은 글 — 바꾸면 다시 잰다
IMPACT_SYSTEM = """# 재난 문자 「여행에 영향이 있나」 판정 기준

한국을 여행 중인 사람(관광 · 식당 · 이동 일정이 있는 사람)이 받았다고 생각하고 재난 문자 한 통을 읽는다.

> 이 문자가 알리는 일이 **여행 일정(가는 길 · 장소 이용 · 야외 활동 · 안전)에 영향을 줄 수 있는가?**

## impact (하나 고른다)

| impact | 뜻 | 지어낸 예 |
|---|---|---|
| road | 도로 통제 · 정체 · 우회(공사, 행사, 마라톤, 사고, 집회로 막힌 길) | 「○○대로 마라톤으로 09~13시 통제」 |
| bus | 버스 운행 중단 · 파업 · 노선 변경 | 「시내버스 파업으로 운행 중단」 |
| rail | 지하철 · 열차 운행 중단 · 무정차 · 지연 | 「○호선 ○○역 무정차 통과」 |
| utility | 정전 · 단수 · 가스 누출 | 「○○동 일대 정전 발생」 |
| crowd | 인파 밀집 · 혼잡 경고 | 「○○역 인파 밀집, 이동 자제」 |
| hazard | 화재 · 붕괴 · 폭발 등 근처 위험, 대피 안내 | 「○○동 화재, 주민 대피」 |
| outdoor | 날씨 · 대기 · 더위 · 추위로 야외 활동이 위험해짐 | 「폭염 경보, 야외 활동 자제」 |
| none | 여행 일정에 영향 없음 — 일반 생활 수칙, 홍보, 병원 안내, 사기 주의, 훈련 소음 안내 등 | 「물놀이 시 구명조끼 착용」 · 「연휴에 문 여는 병원 안내」 |

## 정할 때 지킬 것

- 본문에 쓰인 것만 본다. 보낸 기관으로 짐작하지 않는다.
- 이미 끝난 일을 알리는 문자(「통제 해제」 · 「파업 종료」)도 그 일의 종류로 고른다. 끝났는지는 `ended` 로 따로 적는다.
- 예고(「내일 마라톤으로 통제 예정」)도 영향이 있다 — 그 종류로 고른다.
- 여러 가지면 여행에 가장 크게 영향을 주는 하나를 고른다.
- 애매하면 none 으로 하지 않는다 — 영향이 있을 수 있으면 그 종류를 고른다.

## 답 모양 (JSON 하나만)

```json
{"impact": "road", "relevant": true, "ended": false, "place": "본문에 적힌 장소 그대로(없으면 빈 문자열)", "evidence": "본문에서 그대로 복사한 30자 이내 조각"}
```

- `relevant` 는 `impact != "none"` 일 때 true.
- `evidence` 는 판단의 근거가 된 본문 조각을 글자 그대로 복사한다.
"""
IMPACT_PROMPT_SHA = hashlib.sha1(IMPACT_SYSTEM.encode("utf-8")).hexdigest()[:12]
IMPACT_KINDS = ("road", "bus", "rail", "utility", "crowd", "hazard", "outdoor")
#: 실행 중 센 값 — 「기타」 여행 영향 2차 확인
IMPACT_STATS: dict[str, int] = {"calls": 0, "cache_hits": 0, "failed": 0, "added": 0, "none": 0, "shadow_diff": 0}


class NoticeImpactModel:
    """`notice_impact.set_second_opinion` 에 꽂는 호출 가능 객체 `[2026-10-13 사용자 결정 — 규칙 또는 모델]`.

    규칙이 「영향 없음」이라 한 본문에만 불린다. 돌려주는 값: 영향 종류(IMPACT_KINDS) · "none" · None(못 정함 → 규칙 결과).
    ★근거 조각이 본문에 없으면 「영향 없음」으로 본다(지어낸 근거로 일정을 흔들지 않는다). `shadow` 면 기록만 하고 None 을 돌려준다.
    전국 재난 문자 holdout 99건: 규칙 놓침 2 · 모델 0 · 규칙 또는 모델 0(잘못 보냄 13/28)."""

    prompt_version = IMPACT_PROMPT_VERSION

    def __init__(self, *, base_url: str, model: str, timeout: float = 90.0, keep_alive: str = "",
                 mode: Callable[[], str] | str = "on", post: Callable[[str, dict, float], Any] | None = None,
                 cache_size: int = 2048) -> None:
        self.base_url, self.model, self.timeout, self.keep_alive = base_url.rstrip("/"), model, timeout, keep_alive
        #: ★`[2026-10-15]` 관리 콘솔 「모델 경로」를 따를 때 조립이 꽂는 주소 함수(부를 때마다 읽는다). 비면 `base_url` 고정
        self.base_url_for: Callable[[], str] | None = None
        self._mode = mode if callable(mode) else (lambda: str(mode))
        self._post = post or NoticeEndModel._http
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()

    def current_base_url(self) -> str:
        """이번 호출이 부를 Ollama 주소 — 꽂힌 주소 함수가 있으면 그 값(비면 고정 주소), 없으면 고정 주소."""
        if self.base_url_for is not None:
            try:
                chosen = (self.base_url_for() or "").strip().rstrip("/")
            except Exception:                    # noqa: BLE001 — 경로를 못 읽으면 고정 주소로 부른다
                chosen = ""
            if chosen:
                return chosen
        return self.base_url

    def _ask(self, text: str) -> str:
        payload: dict[str, Any] = {"model": self.model, "stream": False, "think": False, "format": "json",
                                   "options": {"temperature": 0},
                                   "messages": [{"role": "system", "content": IMPACT_SYSTEM},
                                                {"role": "user", "content": "재난 문자:\n" + text}]}
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        response = self._post(f"{self.current_base_url()}/api/chat", payload, self.timeout)
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:120]}")
        answer = json.loads(response.json()["message"]["content"])
        if not isinstance(answer, dict):
            raise ValueError("JSON 객체가 아니다")
        kind = str(answer.get("impact") or "").strip()
        if kind not in IMPACT_KINDS:
            return "none"
        return kind if evidence_in_text(str(answer.get("evidence") or ""), text) else "none"

    def __call__(self, text: str) -> str | None:
        mode = self._mode()
        if mode not in ("shadow", "on"):
            return None
        with self._lock:
            cached = self._cache.get(text)
            if cached is not None:
                self._cache.move_to_end(text)
                IMPACT_STATS["cache_hits"] += 1
        verdict = cached
        if verdict is None:
            IMPACT_STATS["calls"] += 1
            try:
                verdict = self._ask(text)
            except Exception as exc:                       # noqa: BLE001 — 모델 실패는 규칙 결과로 돌아간다(세고 남긴다)
                IMPACT_STATS["failed"] += 1
                logger.warning("공지 여행 영향 2차 확인 실패 — 규칙 결과를 씀 (%s · %s): %s", self.model, IMPACT_PROMPT_VERSION, exc)
                return None
            with self._lock:
                self._cache[text] = verdict
                while len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
        if verdict == "none":
            IMPACT_STATS["none"] += 1
        elif mode == "on":
            IMPACT_STATS["added"] += 1
            logger.info("공지 여행 영향 2차 확인: 규칙은 영향 없음, 모델은 %s (%s) — %s", verdict, self.model, text[:80])
        else:
            IMPACT_STATS["shadow_diff"] += 1
            logger.info("공지 여행 영향 2차 확인(비교만): 모델은 %s (%s) — %s", verdict, self.model, text[:80])
        return verdict if mode == "on" else None


def register_from_settings(settings: Any, *, base_url_for: Callable[[], str] | None = None) -> NoticeEndModel | None:
    """조립 때 한 번. 설정에 모델 이름과 Ollama 주소가 있을 때만 꽂는다(없으면 규칙만 — 지금까지와 같다).
    `base_url_for` — 관리 콘솔 「모델 경로」를 따르는 주소 함수(`[2026-10-15]`, 조립이 넘긴다). 비면 `ollama_base_url` 고정."""
    from app.core.settings import get_guardrails
    from app.domains.travel_ops.ports.data_sources import notice_status

    model = (getattr(settings, "ollama_notice_model", "") or "").strip()
    base = (getattr(settings, "ollama_base_url", "") or "").strip()
    if not model or not base:
        from app.domains.travel_ops.ports.data_sources import notice_impact

        notice_status.set_second_opinion(None)
        notice_impact.set_second_opinion(None)
        return None

    def mode() -> str:
        raw = get_guardrails().get("travel.notice_end.mode")
        value = {True: "on", False: "off"}.get(raw, str(raw or "off")) if isinstance(raw, bool) else str(raw or "off")      # ★따옴표 없는 on/off 는 YAML 이 참/거짓으로 읽는다
        return value if value in ("off", "shadow", "on") else "off"

    judge = NoticeEndModel(base_url=base, model=model, timeout=float(getattr(settings, "ollama_notice_timeout_seconds", 90.0)),
                           keep_alive=str(getattr(settings, "ollama_keep_alive", "") or ""), mode=mode)
    judge.base_url_for = base_url_for
    notice_status.set_second_opinion(judge)
    logger.info("공지 끝남 2차 확인 모델 연결: %s (mode=%s · %s · 지시문 %s)", model, mode(), PROMPT_VERSION, PROMPT_SHA)

    # `[2026-10-13 사용자 결정]` 「기타」 여행 영향도 같은 모델로 2차 확인(규칙 또는 모델). 스위치는 따로(`travel.notice_impact.mode`)
    from app.domains.travel_ops.ports.data_sources import notice_impact

    def impact_mode() -> str:
        raw = get_guardrails().get("travel.notice_impact.mode")
        value = {True: "on", False: "off"}.get(raw, str(raw or "off")) if isinstance(raw, bool) else str(raw or "off")
        return value if value in ("off", "shadow", "on") else "off"

    impact = NoticeImpactModel(base_url=base, model=model, timeout=float(getattr(settings, "ollama_notice_timeout_seconds", 90.0)),
                               keep_alive=str(getattr(settings, "ollama_keep_alive", "") or ""), mode=impact_mode)
    impact.base_url_for = base_url_for
    notice_impact.set_second_opinion(impact)
    logger.info("공지 여행 영향 2차 확인 모델 연결: %s (mode=%s · %s · 지시문 %s)", model, impact_mode(), IMPACT_PROMPT_VERSION, IMPACT_PROMPT_SHA)
    return judge


__all__ = ["IMPACT_PROMPT_SHA", "IMPACT_PROMPT_VERSION", "IMPACT_STATS", "IMPACT_SYSTEM", "NoticeEndModel", "NoticeImpactModel", "PROMPT_SHA", "PROMPT_VERSION", "STATS", "SYSTEM", "evidence_in_text", "register_from_settings"]

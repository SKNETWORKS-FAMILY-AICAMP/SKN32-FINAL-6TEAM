# -*- coding: utf-8 -*-
"""일정 항목 짚기 — **우리 데이터로 가르친(파인튜닝) 모델**이 「이 말이 일정의 어느 항목인가」를 고른다. `[2026-10-07 사용자 지시]`

★왜. 전에는 `mentioned_item` 이 제목·장소 이름의 낱말이 문장에 그대로 나올 때만 항목을 찾았다(같은 질문 90개에서 33/90 = 37%).
  가르친 Gemma-4 E4B(QLoRA, Q8)는 같은 질문 769개에서 750~760개를 맞혔다(마스터 문서 §92). 이 모듈이 그 모델을 제품 길에 꽂는다.
★모델은 **번호만 고른다**(시각·장소를 만들지 않는다) — 일정 목록의 번호 하나 또는 「없음」. 값은 서버가 가진 사실로 만든다(근거 없는 문장 금지, CLAUDE.md §0).
★가르칠 때와 **같은 프롬프트**(오늘 날짜 + 번호 붙인 일정 + 고객 질문 + JSON 지시)를 쓴다 — 지시문이 다르면 가르친 효과가 줄어든다.
★켜는 법: `.env` 의 `ACOP_OLLAMA_POINTER_MODEL`(Ollama 에 올린 모델 이름) + 가드레일 `travel.pointer.mode` — `off`(규칙만) · `shadow`(모델도 불러 비교만 남기고 **규칙 결과를 쓴다**) · `on`(모델 결과를 쓴다).
★모델이 실패하면(시간 초과 · 형식 오류 · 목록 밖 번호) **옛 낱말 규칙으로 돌아간다** — 대신 실패는 세어 경고로 남긴다(조용히 넘기지 않는다, CLAUDE.md §3).
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import OrderedDict
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")
_WEEK = "월화수목금토일"
#: 가르칠 때 쓴 지시문 끝(마스터 문서 §91 · `distill_assemble.py` 와 같은 글자)
_ASK = ("이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. 질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. "
        "확실하지 않으면 null.")
_SUFFIX = '\n\n답은 JSON 한 줄로만: {"item": 번호} 또는 {"item": null}'
_SCHEMA = {"type": "object", "properties": {"item": {"type": ["integer", "null"]}}, "required": ["item"]}

#: 실행 중 센 값 — 운영이 「모델이 쓰이고 있나 · 실패가 얼마나 나나」를 볼 수 있게(조용한 폴백을 만들지 않는다)
STATS: dict[str, int] = {"calls": 0, "used": 0, "failed": 0, "cache_hits": 0, "shadow_diff": 0}


def _local(moment: datetime) -> datetime:
    return moment.astimezone(KST)


def build_prompt(items: list[Any], text: str, *, today: datetime | None = None) -> tuple[str, list[Any]]:
    """가르칠 때와 같은 모양의 프롬프트와, 번호(1부터) → 항목 표. 일정은 시각 순."""
    ordered = sorted(items, key=lambda i: (i.starts_at, getattr(i, "seq", 0)))
    first = _local(ordered[0].starts_at).date()
    lines = []
    for n, item in enumerate(ordered, start=1):
        at = _local(item.starts_at)
        place = (getattr(item, "place", None) or {}).get("name") or item.title
        lines.append(f"{n}. {(at.date() - first).days + 1}일차 {at.month}/{at.day}({_WEEK[at.weekday()]}) {at:%H:%M} [{item.kind}] {item.title} @ {place}")
    now = _local(today) if today else datetime.now(KST)
    prompt = (f"오늘은 {now.date().isoformat()} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n" + "\n".join(lines)
              + f"\n\n고객 질문: {text}\n\n{_ASK}{_SUFFIX}")
    return prompt, ordered


class OllamaItemPointer:
    """`mentioned_item(items, text)` 자리에 꽂는 호출 가능 객체. 결정했으면 항목 또는 None, 못 정했으면 `NotImplemented`(→ 옛 규칙)."""

    def __init__(self, *, base_url: str, model: str, timeout: float = 30.0, keep_alive: str = "",
                 mode: Callable[[], str] | str = "on", post: Callable[[str, dict], Any] | None = None, cache_size: int = 256) -> None:
        self.base_url, self.model, self.timeout, self.keep_alive = base_url.rstrip("/"), model, timeout, keep_alive
        self._mode = mode if callable(mode) else (lambda: str(mode))
        self._post = post or self._http
        self._cache: OrderedDict[tuple, Any] = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()

    def _http(self, url: str, payload: dict) -> Any:
        import httpx

        return httpx.post(url, json=payload, timeout=self.timeout)

    def _ask(self, prompt: str) -> int | None:
        """모델 한 번 — 번호(정수) 또는 None(없음). 못 부르거나 형식이 틀리면 예외."""
        payload: dict[str, Any] = {"model": self.model, "stream": False, "think": False, "format": _SCHEMA,
                                   "options": {"temperature": 0, "num_predict": 24}, "messages": [{"role": "user", "content": prompt}]}
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        response = self._post(f"{self.base_url}/api/chat", payload)
        if response.status_code != 200:
            raise RuntimeError(f"Ollama HTTP {response.status_code}: {response.text[:120]}")
        value = json.loads(response.json()["message"]["content"])
        item = value.get("item") if isinstance(value, dict) else None
        if item is not None and not isinstance(item, int):
            raise ValueError(f"item 이 정수가 아니다: {item!r}")
        return item

    def __call__(self, items: list[Any], text: str, rule: Callable[[], Any] | None = None) -> Any:
        mode = self._mode()
        if mode == "off" or not items or not (text or "").strip():
            return NotImplemented
        prompt, ordered = build_prompt(items, text)
        key = (tuple((str(i.item_id), i.title, i.starts_at.isoformat()) for i in ordered), text)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                STATS["cache_hits"] += 1
                picked = self._cache[key]
                return picked if mode == "on" else NotImplemented
        STATS["calls"] += 1
        started = time.perf_counter()
        try:
            number = self._ask(prompt)
            if number is not None and not (1 <= number <= len(ordered)):
                raise ValueError(f"목록 밖 번호 {number} (1..{len(ordered)})")
        except Exception as exc:  # noqa: BLE001 — 어떤 실패든 옛 규칙으로(대신 세고 경고를 남긴다)
            STATS["failed"] += 1
            logger.warning("일정 항목 짚기 모델 실패 → 낱말 규칙으로 돌아감 (model=%s · %s: %s · 실패 %d/%d)", self.model, type(exc).__name__, str(exc)[:120], STATS["failed"], STATS["calls"])
            return NotImplemented
        picked = None if number is None else ordered[number - 1]
        if picked is not None and picked.kind == "mobility":
            picked = None                  # 낱말 규칙도 이동 항목은 고르지 않는다(대상은 장소가 있는 일정)
        with self._lock:
            self._cache[key] = picked
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        logger.info("일정 항목 짚기 모델 %.2f초 → %s (mode=%s)", time.perf_counter() - started, number, mode)
        if mode == "shadow":
            ruled = rule() if rule else None
            if (getattr(ruled, "item_id", None)) != (getattr(picked, "item_id", None)):
                STATS["shadow_diff"] += 1
                logger.info("일정 항목 짚기 shadow 차이: 모델=%s · 규칙=%s · 문장=%r", getattr(picked, "title", None), getattr(ruled, "title", None), text[:60])
            return NotImplemented          # shadow — 결과는 규칙으로
        STATS["used"] += 1
        return picked


def register_from_settings(settings: Any) -> OllamaItemPointer | None:
    """조립 때 한 번. 설정에 모델 이름과 Ollama 주소가 있을 때만 꽂는다(없으면 규칙만 — 지금까지와 같다)."""
    from app.core.settings import get_guardrails
    from app.domains.travel_ops.instances._shared import itinerary_team

    model = (getattr(settings, "ollama_pointer_model", "") or "").strip()
    base = (getattr(settings, "ollama_base_url", "") or "").strip()
    if not model or not base:
        itinerary_team.set_item_pointer(None)
        return None

    def mode() -> str:
        raw = get_guardrails().get("travel.pointer.mode")
        value = {True: "on", False: "off"}.get(raw, str(raw or "off")) if isinstance(raw, bool) else str(raw or "off")      # ★따옴표 없는 on/off 는 YAML 이 참/거짓으로 읽는다
        return value if value in ("off", "shadow", "on") else "off"

    pointer = OllamaItemPointer(base_url=base, model=model, timeout=float(getattr(settings, "ollama_pointer_timeout_seconds", 30.0)),
                                keep_alive=str(getattr(settings, "ollama_pointer_keep_alive", "") or ""), mode=mode)
    itinerary_team.set_item_pointer(pointer)
    logger.info("일정 항목 짚기 모델 연결: %s (mode=%s)", model, mode())
    return pointer


__all__ = ["OllamaItemPointer", "STATS", "build_prompt", "register_from_settings"]

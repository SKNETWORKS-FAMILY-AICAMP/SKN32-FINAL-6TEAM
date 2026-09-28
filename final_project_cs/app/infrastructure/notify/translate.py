# -*- coding: utf-8 -*-
"""통지를 **보낼 때** 고객 언어로 옮긴다 — v11 결정 14.

★언어 목록을 미리 정하지 않는다. 여행의 `locale`(예: `zh-TW`)을 그대로 모델에 준다.
★시각·금액·고유명사·예약번호·버전 번호는 **옮기지 않고 원값을 싣는다** — 모델에 그렇게
  시키고, 결과에 원문의 숫자가 전부 남아 있는지 **검사한다.** 숫자가 빠지면 번역을 버린다
  (시각이 틀린 알림이 번역 실패보다 나쁘다).
★한국어면 옮기지 않는다.
"""
from __future__ import annotations

import re
from typing import Any, Callable

_DIGITS = re.compile(r"\d+")

SYSTEM = ("You translate a customer notice written in Korean into the language "
          "given by the BCP-47 tag. Output ONLY the translation. Keep every number, time "
          "(e.g. 14:10), amount, version number, reservation id and bracketed tag such as "
          "[재생] exactly as written. Keep proper nouns (place, station, road names) in their "
          "original form and you may add a translation in parentheses. "
          # ★`{leave}` 같은 자리는 **값이 들어갈 칸**이다(`phrase.py`). 옮기지도, 개수를
          #   바꾸지도 않는다 — 하나라도 사라지면 그 번역은 버린다(`PhraseSlotsLost`).
          "A placeholder written as {name} in curly braces is a slot for a value: copy it "
          "verbatim, keep the same number of occurrences, and never translate the word inside "
          "the braces.")


class TranslationRejected(RuntimeError):
    """번역이 원문의 숫자를 잃었다 — 쓰지 않는다."""


def is_korean(locale: str | None) -> bool:
    return not locale or locale.lower().split("-")[0] == "ko"


def make_translator(chat: Any) -> Callable[[str, str], str]:
    """`OllamaChat` 같은 `.text(system, user)` 를 가진 객체 → `(text, locale) → 번역`."""

    def translate(text: str, locale: str) -> str:
        translated = chat.text(SYSTEM, f"Target language: {locale}\n\n{text}")
        missing = sorted(set(_DIGITS.findall(text)) - set(_DIGITS.findall(translated)))
        if missing:
            raise TranslationRejected(f"번역에서 숫자가 빠졌다: {missing[:5]}")
        return translated

    return translate


__all__ = ["SYSTEM", "TranslationRejected", "is_korean", "make_translator"]

# -*- coding: utf-8 -*-
"""통지를 **보낼 때** 고객 언어로 옮긴다 — v11 결정 14.

★언어 목록을 미리 정하지 않는다. 여행의 `locale`(예: `zh-TW`)을 그대로 모델에 준다.
★시각·금액·고유명사·예약번호·버전 번호는 **옮기지 않고 원값을 싣는다** — 모델에 그렇게
  시키고, 결과의 숫자를 **출현 횟수까지** 원문과 대조한다(`[2026-10-02]`: 원문의 숫자가 횟수까지 남아 있어야 하고
  원문에 없던 숫자 값이 새로 생기면 안 된다). 어긋나면 번역을 버린다(시각이 틀린 알림이 번역 실패보다 나쁘다).
★한국어면 옮기지 않는다.
"""
from __future__ import annotations

import re
from collections import Counter
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
        # ★`[2026-10-02 결함 인계 #4]` 전에는 **집합 포함**만 봤다 — 원문 「5 5」 → 번역 「5 999」가 통과했다(5 가 하나 있으니 됐다고 봤고,
        #   새 숫자 999 는 아무도 안 봤다). 이제 ①원문의 숫자가 **출현 횟수까지** 남아 있어야 하고(`lost`) ②원문에 **없던 숫자 값**이
        #   새로 생기면 안 된다(`invented`). 이미 있는 값을 괄호로 되풀이하는 것(「(일정 버전 4)」)은 허용한다 — 새 사실이 아니다.
        original, got = Counter(_DIGITS.findall(text)), Counter(_DIGITS.findall(translated))
        lost = sorted((original - got).elements())
        invented = sorted(set(got) - set(original))
        if lost or invented:
            raise TranslationRejected(f"번역의 숫자가 원문과 다르다 — 빠짐 {lost[:5]} · 새로 생김 {invented[:5]}")
        return translated

    return translate


__all__ = ["SYSTEM", "TranslationRejected", "is_korean", "make_translator"]

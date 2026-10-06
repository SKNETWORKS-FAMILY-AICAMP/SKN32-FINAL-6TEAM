# -*- coding: utf-8 -*-
"""통지를 **보낼 때** 고객 언어로 옮긴다 — v11 결정 14.

★언어 목록을 미리 정하지 않는다. 여행의 `locale`(예: `zh-TW`)을 그대로 모델에 준다.
★시각·금액·고유명사·예약번호·버전 번호는 **옮기지 않고 원값을 싣는다** — 모델에 그렇게
  시키고, 결과의 숫자를 **출현 횟수까지** 원문과 대조한다(`[2026-10-02]`: 원문의 숫자가 횟수까지 남아 있어야 하고
  원문에 없던 숫자 값이 새로 생기면 안 된다). 어긋나면 번역을 버린다(시각이 틀린 알림이 번역 실패보다 나쁘다).
★`[2026-10-06 사용자 지시 — 서비스 평가 베이스라인]` **금액의 단위도 대조한다.** 실제 모델 120호출에서 일본어 「35,000원」→「35,000円」(원→엔)이 숫자 대조를 통과했다(숫자는 그대로라서) —
  일본어에서 35,000원이 엔으로 가면 약 9배 비싼 값으로 읽힌다. 원문에 「숫자+원」이 있으면 ①번역에 원 표기(원 · won · KRW · ₩ · ウォン · 韩元 …) 가 하나는 남아 있어야 하고
  ②원문에 없던 **다른 나라 통화 표기**(円 · 엔 · yen · ¥ · 元(중국) · NT$ · $ · € …)가 숫자 옆에 새로 생기면 안 된다. 어긋나면 번역을 버린다.
★한국어면 옮기지 않는다.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Callable

_DIGITS = re.compile(r"\d+")

#: 원문 속 금액 — 숫자(쉼표 · 소수점) 바로 뒤의 「원」(「1만 원」 · 「35,000원이에요」). 숫자 없는 「만원」은 보지 않는다(「만원 버스」 같은 다른 뜻이 있다)
_WON_AMOUNT = re.compile(r"\d[\d,.]*\s*(?:만\s*)?원")
#: 번역에 **원(won)을 말하는 표기**가 하나는 남아 있어야 한다 — 영어 · 일본어 · 중국어 · 태국어 · 러시아어 · 아랍어를 둔다(목록 밖 언어는 「원」 · 「won」 · 「KRW」 · 「₩」 중 하나를 남기게 모델에 시켰다)
_WON_MARKS = re.compile(r"원|\bwon\b|\bKRW\b|₩|ウォン|韩元|韓元|韩币|韓幣|วอน|вон|وون", re.IGNORECASE)
#: 숫자 옆에 있으면 **다른 나라 통화**로 읽히는 표기 — 일본 엔 · 중국 위안 · 달러 · 유로 · 바트 · 동 …(「韩元」의 「元」은 원이라 뺀다)
_OTHER_CURRENCY = re.compile(
    r"\d[\d,.]*\s*(?:円|엔|\byen\b|\bJPY\b|¥|(?<![韩韓])元(?![素宵旦])|人民币|人民幣|\bRMB\b|\bCNY\b|\bTWD\b|NT\$|HK\$|\$|\bUSD\b|\bdollars?\b|€|\bEUR\b|\beuros?\b|\bbaht\b|\bTHB\b|บาท|\bVND\b|đồng)"
    r"|(?:¥|NT\$|HK\$|US\$|\$|€)\s*\d",
    re.IGNORECASE)

SYSTEM = ("You translate a customer notice written in Korean into the language "
          "given by the BCP-47 tag. Output ONLY the translation. Keep every number, time "
          "(e.g. 14:10), amount, version number, reservation id and bracketed tag such as "
          "[재생] exactly as written. Keep proper nouns (place, station, road names) in their "
          "original form and you may add a translation in parentheses. "
          # ★`{leave}` 같은 자리는 **값이 들어갈 칸**이다(`phrase.py`). 옮기지도, 개수를
          #   바꾸지도 않는다 — 하나라도 사라지면 그 번역은 버린다(`PhraseSlotsLost`).
          "A placeholder written as {name} in curly braces is a slot for a value: copy it "
          "verbatim, keep the same number of occurrences, and never translate the word inside "
          "the braces. Amounts written in Korean won (원) stay in won — never convert them to "
          "another currency and never change the unit; write the unit as won/KRW/₩/원 or the "
          "language's standard word for the Korean won.")


class TranslationRejected(RuntimeError):
    """번역이 원문의 숫자를 잃었다 — 쓰지 않는다."""


def is_korean(locale: str | None) -> bool:
    return not locale or locale.lower().split("-")[0] == "ko"


def currency_problem(source: str, translated: str) -> str | None:
    """금액의 **단위**가 바뀌었으면 그 이유(없으면 None). 원문에 「숫자+원」이 있을 때만 본다 — 금액이 없는 알림은 건드리지 않는다.

    ①원 표기가 번역에서 다 사라졌다 ②원문에 없던 다른 나라 통화 표기가 숫자 옆에 새로 생겼다. 둘 다 숫자 대조(`lost`·`invented`)가 못 보는 것이다(숫자는 그대로라서)."""
    if not _WON_AMOUNT.search(source):
        return None
    if not _WON_MARKS.search(translated):
        return "번역에서 금액의 단위(원)가 사라졌다 — 다른 통화로 바뀌었을 수 있다"
    other = {m.group(0).strip() for m in _OTHER_CURRENCY.finditer(translated)} - {m.group(0).strip() for m in _OTHER_CURRENCY.finditer(source)}
    if other:
        return f"번역에 원문에 없던 다른 통화 표기가 생겼다 — {sorted(other)[:3]}"
    return None


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
        problem = currency_problem(text, translated)
        if problem:
            raise TranslationRejected(problem)
        return translated

    return translate


__all__ = ["SYSTEM", "TranslationRejected", "currency_problem", "is_korean", "make_translator"]

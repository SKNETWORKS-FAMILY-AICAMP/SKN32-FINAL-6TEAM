# -*- coding: utf-8 -*-
"""고객 **자유 문장** → 여행 창구가 받는 구조화된 신고.

「팝업스토어 줄이 길어서 점심에 70분 늦을 것 같아요」 → `{"type": "delay", "minutes": 70}`

★뽑는 것은 **고객이 말한 것뿐**이다. 모델이 채운 값은 규칙으로 다시 본다:
    delay      분(1~1440 정수)이 있어야 한다
    closed     추가 값 없음
    stock_out  상품 이름이 하나 이상 있어야 하고, 각 이름이 **고객 문장에 실제로 나와야** 한다
    other      여행 창구가 받지 않는다
  규칙에 안 맞으면 `None` — 추측으로 채워 일정을 바꾸지 않는다(CLAUDE.md §0.1).
★분·상품 이름이 문장에 없는데 모델이 만들어 내는 경우를 막으려고, 분 숫자도 문장에
  나오는지 본다.
"""
from __future__ import annotations

import re
from typing import Any

SYSTEM = (
    "You extract a structured report from a traveller's message (usually Korean). "
    "Return JSON with keys: type, minutes, products.\n"
    "type: 'delay' (they will be late), 'closed' (the place they are at is closed today), "
    "'stock_out' (items they wanted are sold out and they ask where else to buy), "
    "'change' (they ask to switch a plan we already changed to a different option, e.g. "
    "'다른 식당으로 바꿔줘', '다른 걸로 해줘'), or 'other'.\n"
    "minutes: integer minutes of delay if stated, else null.\n"
    "products: list of product names they could not buy, copied from the message, else []."
)

TYPES = frozenset({"delay", "closed", "stock_out", "change", "other"})


def validate(raw: Any, message: str) -> dict[str, Any] | None:
    """모델 출력 → 검증된 신고. 규칙에 안 맞으면 `None`."""
    if not isinstance(raw, dict) or raw.get("type") not in TYPES:
        return None
    kind = raw["type"]
    if kind == "other":
        return {"type": "other"}
    if kind == "delay":
        minutes = raw.get("minutes")
        if isinstance(minutes, str) and minutes.strip().isdigit():
            minutes = int(minutes)
        if not isinstance(minutes, int) or not 1 <= minutes <= 24 * 60:
            return None
        if str(minutes) not in re.findall(r"\d+", message):
            return None                      # ★문장에 없는 숫자를 만들어 냈다
        return {"type": "delay", "minutes": minutes}
    if kind == "closed":
        return {"type": "closed"}
    if kind == "change":
        # ★재요청(v11 §1) — 무엇으로 바꿀지는 우리가 들고 있던 「다른 안」에서 고른다.
        #   모델이 새 장소를 지어내게 두지 않는다.
        return {"type": "change"}
    products = [str(p).strip() for p in raw.get("products") or [] if str(p).strip()]
    compact = message.replace(" ", "")
    products = [p for p in products if p.replace(" ", "") in compact]
    if not products:
        return None                          # ★문장에 없는 상품 이름을 만들어 냈다
    return {"type": "stock_out", "products": products}


def extract(message: str, chat: Any) -> dict[str, Any] | None:
    """`chat.json(system, user)` 로 뽑고 검증한다. 모델 호출 실패는 예외 그대로 올린다."""
    return validate(chat.json(SYSTEM, message), message)


__all__ = ["SYSTEM", "TYPES", "extract", "validate"]

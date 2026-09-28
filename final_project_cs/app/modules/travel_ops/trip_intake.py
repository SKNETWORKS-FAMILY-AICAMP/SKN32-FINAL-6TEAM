# -*- coding: utf-8 -*-
"""고객 **자유 문장** → 여행 창구가 받는 구조화된 신고.

「팝업스토어 줄이 길어서 점심에 70분 늦을 것 같아요」 → `{"type": "delay", "minutes": 70}`

★뽑는 것은 **고객이 말한 것뿐**이다. 모델이 채운 값은 규칙으로 다시 본다:
    delay      분(1~1440 정수)이 있어야 한다
    closed     추가 값 없음
    stock_out  상품 이름이 하나 이상 있어야 하고, 각 이름이 **고객 문장에 실제로 나와야** 한다
    rollback   되돌릴 일정 버전 번호가 있어야 하고 그 숫자가 **문장에 나와야** 한다(`[2026-09-17]` —
               실제 Gemma 가 「6번 일정으로 되돌려 주세요」를 `change` 로 뽑았다. 종류가 없었다)
    question   `[2026-09-25]` 규정·조건·가능 여부를 **묻는다**(「비 오면 취소돼요?」「아이 데려가도 되나요」).
               일정을 바꾸지 않고 규정 근거로 답한다(`*.itinerary_question`)
    other      여행 창구가 받지 않는다

★★`[2026-09-25]` **묻는 꼴이면 상태 신고로 받지 않는다.** 모델이 `closed`·`delay`·`other` 로 뽑아도
  문장이 질문(물음표 · 「되나요」「아니에요」「있나요」 …)이면 `question` 으로 바꾼다. 실측(triPilot : RAG
  세션, 2026-09-25): 「내일 경복궁 휴관 아니에요?」가 `closed` 로 읽혀 **대체안 계산으로 갈 수 있었고**,
  「비 오면 카약 취소돼요? 위약금 있어요?」「저녁 식당에 아이 데려가도 되나요」는 `other` → 사람이었다.
  `change`·`rollback`·`stock_out` 은 그대로 둔다 — 「다른 걸로 바꿔줄 수 있어요?」는 묻는 꼴의 **요청**이고
  품절 신고는 원래 「다른 데 없어?」라고 묻는다.
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
    "'다른 식당으로 바꿔줘', '다른 걸로 해줘'), 'rollback' (they ask to go back to an earlier "
    "version of the itinerary by its number, e.g. '6번 일정으로 되돌려 주세요'), "
    "'question' (they ASK about rules, conditions or whether something is possible, open or "
    "cancellable, e.g. '비 오면 취소돼요? 위약금 있어요?', '아이 데려가도 되나요', '내일 휴관 아니에요?'), "
    "or 'other'.\n"
    "A question is NEVER 'closed' or 'delay' — use those only when they REPORT a fact that already "
    "happened ('오늘 임시휴무래요', '70분 늦을 것 같아요').\n"
    "minutes: integer minutes of delay if stated, else null.\n"
    "to_version: integer itinerary version to go back to if stated, else null.\n"
    "products: list of product names they could not buy, copied from the message, else []."
)

TYPES = frozenset({"delay", "closed", "stock_out", "change", "rollback", "question", "other"})

#: 묻는 꼴 — 물음표, 또는 묻는 어미. ★상태 신고(`closed`·`delay`)와 `other` 를 `question` 으로 돌리는 데만 쓴다
_QUESTION = re.compile(r"[?？]|(나요|가요|까요|인가|되나|돼요\?|아니에요|아닌가|아니죠|있나|없나|있을까|"
                       r"없을까|어때|어떡|어떻게|궁금|되는지|인지|는지)")

#: 묻는 꼴이면 받지 않는 종류 — 일정을 **바꾸는** 신고이거나, 답할 길이 없던 것
_REPORTS_THAT_A_QUESTION_IS_NOT = frozenset({"closed", "delay", "other"})


def looks_like_question(message: str) -> bool:
    return bool(_QUESTION.search(message or ""))


def validate(raw: Any, message: str) -> dict[str, Any] | None:
    """모델 출력 → 검증된 신고. 규칙에 안 맞으면 `None`."""
    if not isinstance(raw, dict) or raw.get("type") not in TYPES:
        return None
    kind = raw["type"]
    if kind == "question" or (kind in _REPORTS_THAT_A_QUESTION_IS_NOT and looks_like_question(message)):
        # ★묻는 꼴이면 「닫혔다」·「늦는다」로 받지 않는다 — 질문이 일정을 바꾸지 못하게
        return {"type": "question"}
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
    if kind == "rollback":
        version = raw.get("to_version")
        if isinstance(version, str) and version.strip().isdigit():
            version = int(version)
        if not isinstance(version, int) or version < 1:
            return None
        if str(version) not in re.findall(r"\d+", message):
            return None                      # ★문장에 없는 버전 번호를 만들어 냈다
        return {"type": "rollback", "to_version": version}
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


__all__ = ["SYSTEM", "TYPES", "extract", "looks_like_question", "validate"]

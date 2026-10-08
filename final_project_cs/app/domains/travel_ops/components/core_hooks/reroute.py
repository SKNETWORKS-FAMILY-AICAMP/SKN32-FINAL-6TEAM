# -*- coding: utf-8 -*-
"""라우팅이 어긋났을 때 **한 번 더 고르는** 여행 재배분기. `[2026-10-06]`

★왜 있나. 분류가 붙인 대상 종류로 받는 팀이 없으면 Case 는 `escalated` 로 끝났다. 그런데 이
  제품에는 **사람 운영자 큐가 없다** — 고객은 알림과 계획서 링크만 보고, 그 Case 는 아무도 받지
  않는다. 그래서 「받는 팀이 없다」를 마지막 답으로 두지 않고 한 번 더 묻는다.

★계층. 언제 부르고 · 실패를 어떻게 처리하고 · 어느 상태로 보내는가는 **코어**가 정한다
  (`app/application/controller.py` `_reroute_once`). 이 파일은 **어휘와 프롬프트**만 갖는다 —
  `feedback.py`(인라인 분류)와 같은 경계다.

★**지어내지 않는다.** 모델은 **지금 등록된 팀이 실제로 받는 종류** 안에서만 고를 수 있다(목록은
  코어가 넘긴다). 목록 밖을 내면 한 번만 다시 묻고, 그래도 밖이면 `None` 이다 — 그러면 Case 는
  종전대로 `escalated` 로 간다. 아무 팀에나 보내는 것보다 낫다.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from app.domains.travel_ops.components.core_hooks.feedback import INTENTS, LLM, _default_llm, masked

logger = logging.getLogger(__name__)

_SYSTEM = (
    "A traveller's support case could not be routed to any team. "
    "Pick the one team that should handle it, using ONLY the teams listed. "
    "Answer as JSON: {\"case_type\": <one value from the allowed list>, "
    "\"intent\": <one of the allowed intents, or null>, \"why\": <one short sentence>}. "
    "If none of the teams can genuinely handle it, answer {\"case_type\": null, \"why\": ...}. "
    "Never invent a team or a value that is not in the lists."
)


def _ask(provider: LLM, subject: str, allowed: list[str], teams: list[dict[str, Any]],
         case_type: str, failure: str, extra: str = "") -> dict[str, Any]:
    body = (
        f"{_SYSTEM}\n\n"
        f"Traveller's message: {masked(subject)}\n"
        f"Classifier picked target type: {case_type or '(none)'} — no team accepts it ({failure}).\n"
        f"Allowed case_type values: {', '.join(allowed)}\n"
        f"Allowed intent values: {', '.join(sorted(INTENTS))}\n"
        f"Teams: {json.dumps(teams, ensure_ascii=False)}"
        + extra
    )
    raw = provider(body)
    return raw if isinstance(raw, dict) else {}


def reroute(*, subject: str, case_type: str, intent: str | None, teams: list[dict[str, Any]],
            failure: str, llm: LLM | None = None) -> dict[str, Any] | None:
    """코어가 부르는 모양. 고른 대상 종류를 돌려주거나, 못 고르면 `None`.

    ★고를 수 있는 값은 **등록된 팀이 실제로 받는 종류**뿐이다 — 선언이 바뀌면 이 목록도 같이
      바뀐다(새 어휘를 여기에 적어 두지 않는다).
    ★목록 밖을 내면 **한 번만** 다시 묻는다(`feedback.classify` 와 같은 규칙). 그래도 밖이면 `None`.
    """
    allowed = sorted({str(value) for team in teams for value in (team.get("accepts") or [])})
    if not allowed or not (subject or "").strip():
        return None                                        # 고를 것이 없거나 읽을 문장이 없다
    provider: LLM = llm or _default_llm()
    raw = _ask(provider, subject, allowed, teams, case_type, failure)
    picked = raw.get("case_type")
    if picked is not None and str(picked) not in allowed:
        raw = _ask(provider, subject, allowed, teams, case_type, failure,
                   extra=f"\n\n(Your previous answer '{picked}' is not in the allowed list. "
                         f"case_type must be exactly one of: {', '.join(allowed)}, or null.)")
        picked = raw.get("case_type")
    if picked is None or str(picked) not in allowed:
        logger.info("reroute declined: picked=%r allowed=%s", picked, allowed)
        return None                                        # 모델도 못 골랐다 — 종전대로 escalated
    chosen_intent = raw.get("intent")
    if chosen_intent is not None and str(chosen_intent) not in INTENTS:
        chosen_intent = None                               # 요청 종류는 못 믿겠으면 원래 것을 쓴다(코어가 채운다)
    why = raw.get("why")
    return {"case_type": str(picked), "intent": chosen_intent,
            "why": str(why)[:200] if why else None, "by": "llm"}


def build(llm: LLM | None = None) -> Callable[..., dict[str, Any] | None]:
    """조립이 Controller 에 넘길 모양으로 묶는다(시험이 모델을 바꿔 끼울 수 있게)."""
    def _call(**kwargs: Any) -> dict[str, Any] | None:
        return reroute(llm=llm, **kwargs)
    return _call


__all__ = ["build", "reroute"]

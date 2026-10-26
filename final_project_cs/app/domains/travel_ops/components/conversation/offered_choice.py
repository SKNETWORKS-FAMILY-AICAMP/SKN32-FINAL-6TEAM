# -*- coding: utf-8 -*-
"""바로 앞 답이 보인 「다른 안」 선택지를 누른 것 — 모델 없이 그 안으로 확정한다. `[2026-10-26 x600 74b2b232]`

☆x600: 식당 「다른 데로 바꿔줘」 → 하나면옥으로 바꾸고 「다른 안」 선택지 셋(조선옥 · 순라길비비 · 인사동 옥정). 「식당 조선옥」을 누르면
  웹은 선택지 문장 「하나면옥 대신 조선옥(으)로 바꿔 줘」를 같은 채팅 입구로 보낸다 — 이 문장이 해석 모델을 다시 타서 대상을 잃고
  다른 곳(한일옥)으로 바뀌었고, 고른 조선옥은 다시 「다른 안 1)」로 나왔다.

규칙(공개 선택지 모양 {label, message, item_id?} 은 그대로):
- **바로 앞 assistant 턴**의 Case 기록에서 그 답이 실제로 보인 「다른 안」(`case_dispatch.offered_alternates`)을 다시 만든다.
- 들어온 문장이 그중 **하나의 선택지 문장과 정확히 같을 때만**(기존 되묻기 선택 `conversation_work._choice` 와 같은 일치) 그 안의 후보 key 를 고른다.
- 그 key 를 들고 있는(`detail.alternates`) 일정이 지금 판에 **딱 하나**이고, 화면에서 고른 일정이 있으면 그 일정과 같아야 한다.
- 맞으면 `Decision(apply_change, raw={source: offered_choice, model_called: False, choice: key})` — 하루 요약 버튼(`summary_request`)과 같은
  모델 없는 결정이다. 실행은 기존 팀 경로(`plan_swap(choice=key)`)가 한다. 하나라도 어긋나면 None(지금처럼 해석한다).
낱말을 보지 않는다 — 서버가 낸 선택지 문장과의 정확 일치 · 후보 key · 일정 기록만 본다.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from .decision_unit import Decision


def decide(conn, *, tenant: str, trip_id: UUID, items: list[Any], message: str,
           selected: UUID | None = None, turns: list[dict[str, Any]] | None = None) -> Decision | None:
    from app.infrastructure.db import repository

    from . import case_dispatch, chat_log

    if turns is None:
        turns = chat_log.recent(conn, tenant_id=tenant, trip_id=trip_id, limit=2)
    last = next((t for t in reversed(turns) if t.get("role") == "assistant"), None)
    if not last or not last.get("case_id"):
        return None
    case = repository.get_case(conn, tenant_id=tenant, case_id=UUID(str(last["case_id"])))
    state = (case or {}).get("state_json") or {}
    if (state.get("trip_message") or {}).get("trip_id") != str(trip_id):
        return None
    hits = [key for choice, key in case_dispatch.offered_alternates(state) if choice["message"] == message]
    if len(hits) != 1:
        return None
    holders = [i for i in items if any(isinstance(a, dict) and str(a.get("key")) == hits[0]
                                       for a in ((getattr(i, "detail", None) or {}).get("alternates") or []))]
    if len(holders) != 1 or (selected is not None and holders[0].item_id != selected):
        return None
    return Decision("apply_change", holders[0], None, "none", None, "",
                    raw={"source": "offered_choice", "model_called": False, "choice": hits[0],
                         "offered_case_id": str(last["case_id"])})


__all__ = ["decide"]

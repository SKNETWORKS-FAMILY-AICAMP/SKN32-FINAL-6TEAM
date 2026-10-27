# -*- coding: utf-8 -*-
"""바로 앞 답의 종류 확인 선택지(숙박 · 활동 · 식사)를 누른 것 — 모델 없이 고른 종류로 넣는다. `[2026-10-27 B 채팅 전수검사]`

☆사용자 보고: 등록한 여행 채팅 「○○호텔 넣어 줘」가 액티비티로 들어갔다. 이제 숙소를 넣을 때 원문이 종류를 하나로 정하지 않으면
  `chat_edit` 이 넣지 않고 「어떤 일정으로 넣을까요?」(선택지 셋)로 묻는다. 고객이 누른 선택지 문장이 해석 모델을 다시 타면
  지연(로컬 E4B 수십 초) · 오해석 · 되묻기 루프가 생긴다 — Codex 검토(codex/q1.out 1-2): 정확히 같은 선택지 문장만 저장한 넣기로 실행한다.

규칙(`offered_choice` 와 같은 모양):
- **바로 앞 assistant 턴**의 Case 기록 `trip_outcome.kind_offer` — 그 답이 실제로 보인 선택지와, 선택지마다 그 종류로 정한 넣기(`chat_edit.ADD_FIELDS`).
- 들어온 문장이 그중 **하나의 선택지 문장과 정확히 같을 때만**. 그 답을 낸 판(`version`)이 지금 판과 같아야 한다(판이 바뀌었으면 — 이미 넣었거나
  다른 변경이 있었다 — 받지 않는다: 같은 넣기를 두 번 하지 않고 낡은 날짜 · 시각으로 넣지 않는다).
- 맞으면 `Decision(add_item, raw={source: kind_choice, model_called: False, ops})`. 하나라도 어긋나면 None(지금처럼 해석한다).
낱말을 보지 않는다 — 서버가 낸 선택지 문장과의 정확 일치 · 판 번호 · 저장한 넣기만 본다.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from .decision_unit import Decision


def pick(state: dict[str, Any], *, message: str, version: int) -> dict[str, Any] | None:
    """그 Case 기록의 종류 확인 선택지 가운데 `message` 와 정확히 같은 것 — 판이 같고 저장한 넣기가 온전할 때만. 아니면 None."""
    from .chat_edit import op_from_spec

    offer = (state.get("trip_outcome") or {}).get("kind_offer") if isinstance(state, dict) else None
    if not isinstance(offer, dict) or offer.get("version") != version or not isinstance(offer.get("options"), list):
        return None
    hits = [o for o in offer["options"] if isinstance(o, dict) and o.get("message") == message]
    if len(hits) != 1 or not isinstance(hits[0].get("ops"), list) or not hits[0]["ops"]:
        return None
    try:
        for spec in hits[0]["ops"]:
            op_from_spec(spec)
    except (TypeError, ValueError):
        return None
    return hits[0]


def decide(conn, *, tenant: str, trip_id: UUID, version: int, message: str,
           turns: list[dict[str, Any]] | None = None) -> Decision | None:
    from app.infrastructure.db import repository

    from . import chat_log

    if turns is None:
        turns = chat_log.recent(conn, tenant_id=tenant, trip_id=trip_id, limit=2)
    last = next((t for t in reversed(turns) if t.get("role") == "assistant"), None)
    if not last or not last.get("case_id"):
        return None
    case = repository.get_case(conn, tenant_id=tenant, case_id=UUID(str(last["case_id"])))
    state = (case or {}).get("state_json") or {}
    if (state.get("trip_message") or {}).get("trip_id") != str(trip_id):
        return None
    chosen = pick(state, message=message, version=int(version))
    if chosen is None:
        return None
    return Decision("add_item", None, None, "none", None, "",
                    raw={"source": "kind_choice", "model_called": False, "ops": chosen["ops"],
                         "offered_case_id": str(last["case_id"])})


__all__ = ["decide", "pick"]

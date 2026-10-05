# -*- coding: utf-8 -*-
"""항로 지킴이 — 일정이 꼬이면 **알아서 대체안을 적용**하는 모드를 등록된 여행에서 켜고 끈다. `[결정 2026-10-06 사용자]`

계획서 `wiki/records/plans/2026-10-05_설문_계획서에서_읽고_로딩에서_묻기_기획.md` 「★★ 결정 2026-10-06」 · 「서버 몫」 2·3.

★새 판정 값이 아니다. 설문 15번 `on_disruption` 을 **이름 붙은 모드**로 바꾼 것이라 켜짐 = `replace` · 꺼짐 = `ask_first` 이고,
  판정(`pending.decide` · `survey.auto_on_disruption`)은 그대로 이 값을 읽는다. 이 모듈이 하는 일은 둘이다.
    ① 등록된 여행의 `constraints.survey.on_disruption` 을 바꾸고 `survey_answered` 에 넣는다 — **직접 고른 것**이 된다(2026-09-29 규칙).
    ② **누가 · 언제 · 어디서(via)** 눌렀는지를 `trip_guardian_changes`(추가만 하는 표)에 남긴다.
★「건너뛰기 = 꺼짐」은 값을 안 보내는 것이 아니라 `ask_first` 를 **명시**한다 — 미응답은 기본 `replace` 로 읽혀 휴무 · 재난 · 교통 통제가 자동 적용된다.
★고정한 일정(`protected`)과 안전 사건은 켜져 있어도 먼저 묻는다 — 그 판정은 `pending.decide` 가 한다(여기서 건드리지 않는다).
★옛 여행(설문이 없는 여행)의 동작은 그대로다 — 이 모듈은 부를 때만 값을 바꾼다.
"""
from __future__ import annotations

import json
from typing import Any, Literal, Mapping
from uuid import UUID

from app.domains.travel_ops.components.planning.survey import SURVEY_VERSION, auto_on_disruption

Via = Literal["card", "header", "notice", "settings"]
VIAS: tuple[str, ...] = ("card", "header", "notice", "settings")
#: 켜기·끄기 기록이 없는데 등록 때 이미 답한 값이 있는 여행 — 등록(계획 담기)의 카드가 보낸 값이다. 이 값은 조회 응답에서만 쓴다(`POST` 로 보내는 값이 아니다)
REGISTRATION = "registration"


def is_on(constraints: Mapping[str, Any] | None) -> bool:
    """켜져 있나 — `survey.auto_on_disruption` 과 **같은 판정**이다(직접 답했고 `replace`). 판정이 읽는 것과 화면이 보이는 것이 갈라지지 않게 한 곳을 쓴다."""
    return auto_on_disruption(constraints)


#: 꺼 둔 사용자에게 가는 알림의 「항로 지킴이 켜기」 단추 글. ★웹 화면이 알림줄에 이 글로 그린다 — 바꾸면 웹 시험도 같이 본다
OFFER_LABEL = "항로 지킴이 켜기"


def offer_for(trip_id: UUID) -> dict[str, Any]:
    """「항로 지킴이 켜기」 — 알림에서 켜는 길. `path` 는 웹 앱 안의 주소(웹이 확인 패널을 띄운 뒤 `POST …/guardian` 을 부른다 — **링크만으로는 켜지지 않는다**).
    `url` 은 디스코드 · 텔레그램처럼 웹 밖으로 나가는 알림용 절대 주소 — 웹 주소(`web_origin`)가 설정돼 있을 때만 있다(없으면 None, 그 알림에는 이 줄이 안 붙는다)."""
    from app.core import settings as settings_module

    path = f"/trips/{trip_id}?guardian=on"
    origin = (settings_module.get_settings().web_origin or "").strip().rstrip("/")
    return {"label": OFFER_LABEL, "via": "notice", "path": path, "url": f"{origin}{path}" if origin else None}


def _kinds(payload: Mapping[str, Any]) -> tuple[bool, bool]:
    """(우리가 자동으로 바꾼 알림인가, 「다른 안」을 보내며 먼저 묻는 알림인가). 자동 변경에만 `rollback` 이 실린다(`pending.rollback_offer`) — 고객이 고른 변경에는 없다."""
    kind = payload.get("type")
    return (kind == "change_notice" and bool(payload.get("rollback")),
            kind == "proposal_request" and payload.get("reason") == "ask_first" and bool(payload.get("options")))


def relevant(payload: Mapping[str, Any]) -> bool:
    """이 알림에 항로 지킴이 몫이 붙을 수 있나 — 아니면 여행 제약을 읽지 않아도 된다(알림마다 조회를 더하지 않는다)."""
    return "guardian" not in payload and any(_kinds(payload))


def annotate(payload: dict[str, Any], *, constraints: Mapping[str, Any] | None, trip_id: UUID) -> dict[str, Any]:
    """★`[2026-10-06 사용자 결정 · 항로 지킴이]` 알림에 항로 지킴이 몫을 **구조값**으로 싣는다(`payload.guardian`) — 알림 문장은 건드리지 않는다.

      ① 우리가 **자동으로 바꾼** 알림이고 항로 지킴이가 **켜져 있으면** → `{"changed": true}` (「항로 지킴이가 바꿨어요 · 되돌리기」)
      ② 「다른 안」을 보내며 먼저 묻는 알림(이유 `ask_first`)이고 **꺼져 있으면** → `{"offer": {label, via, path, url}}` (「항로 지킴이 켜기」)
    ★켜 두지 않은 여행의 자동 변경(옛 여행의 기본 `replace`)에는 ①을 싣지 않는다 — 항로 지킴이가 한 일이 아니다.
    ★고정한 일정(`protected`) · 안전 알림 · 「바꿀까요?」(실내외 모름)에는 ②를 싣지 않는다 — 켜도 그 경우는 먼저 묻거나 달라지지 않는다.
    부르는 쪽이 이미 `guardian` 을 줬으면 그대로 둔다. 알림이 만들어지는 **모든 길**(`TripStore.enqueue_*` · Case 버전의 `itinerary_actions`)이 이 한 곳을 쓴다."""
    if "guardian" in payload:
        return payload
    changed, offered = _kinds(payload)
    if not (changed or offered):
        return payload
    on = is_on(constraints)
    if changed and on:
        return {**payload, "guardian": {"changed": True}}
    if offered and not on:
        return {**payload, "guardian": {"offer": offer_for(trip_id)}}
    return payload


def _answered(constraints: Mapping[str, Any] | None) -> bool:
    return "on_disruption" in set((constraints or {}).get("survey_answered") or [])


def view(conn, *, tenant_id: str, trip_id: UUID, constraints: Mapping[str, Any] | None) -> dict[str, Any]:
    """여행 조회 응답의 `guardian` — `{enabled, since, via}`. 상단 아이콘이 읽는다.

    - 켜고 끈 기록이 있으면 **마지막 행**의 시각 · 곳.
    - 기록은 없는데 등록 때 이미 답했으면(카드가 설문과 함께 보냈다) 여행 만든 시각 · `registration`.
    - 한 번도 답하지 않았으면(옛 여행 · 에이전트가 만든 여행) `since`·`via` 는 null — 꺼짐이고, 문제가 생기면 먼저 묻는다.
    """
    enabled = is_on(constraints)
    with conn.cursor() as cur:
        cur.execute("SELECT via, at FROM trip_guardian_changes WHERE tenant_id=%s AND trip_id=%s ORDER BY seq DESC LIMIT 1",
                    (tenant_id, trip_id))
        last = cur.fetchone()
        if last is not None:
            return {"enabled": enabled, "since": last[1].isoformat(), "via": last[0]}
        if _answered(constraints):
            cur.execute("SELECT created_at FROM trips WHERE tenant_id=%s AND trip_id=%s", (tenant_id, trip_id))
            created = cur.fetchone()
            return {"enabled": enabled, "since": created[0].isoformat() if created else None, "via": REGISTRATION}
    return {"enabled": enabled, "since": None, "via": None}


def set_enabled(conn, *, tenant_id: str, trip_id: UUID, customer_id: UUID, enabled: bool, via: str) -> dict[str, Any] | None:
    """켜거나 끈다. 돌려주는 값은 `view` 와 같다. **본인 여행이 아니거나 없으면 None**(같은 404).

    ★한 트랜잭션 — 호출자가 `with conn.transaction():` 으로 감싼다. 여행 행을 잠근다(`FOR UPDATE`).
    ★이미 그 상태로 **직접 답해 둔** 여행이면 아무것도 바꾸지 않고 행도 더하지 않는다(같은 값을 다시 눌러도 「언제부터」가 밀리지 않는다).
      반대로 **답한 적 없는** 여행에 끄기(`ask_first`)를 보내면 바뀌는 것은 없어 보여도 「직접 골랐다」가 처음 기록되므로 행을 더한다.
    ★`survey` 전체를 `apply_survey` 로 다시 거치지 않는다 — 그러면 저장본에 기본값으로 채워진 다른 키까지 「직접 답한 것」이 된다
      (`on_disruption` 기본 `replace` 가 대표적). 여기서는 `on_disruption` 한 키만 건드린다.
    """
    if via not in VIAS:
        raise ValueError(f"via 는 {VIAS} 중 하나여야 한다: {via!r}")
    with conn.cursor() as cur:
        cur.execute("SELECT constraints FROM trips WHERE tenant_id=%s AND trip_id=%s AND customer_id=%s FOR UPDATE",
                    (tenant_id, trip_id, customer_id))
        row = cur.fetchone()
        if row is None:
            return None
        constraints: dict[str, Any] = dict(row[0] or {})
        value = "replace" if enabled else "ask_first"
        survey = dict(constraints.get("survey") or {})
        if not (_answered(constraints) and survey.get("on_disruption") == value):
            survey.setdefault("version", SURVEY_VERSION)
            survey["on_disruption"] = value
            constraints["survey"] = survey
            constraints["survey_answered"] = sorted(set(constraints.get("survey_answered") or []) | {"on_disruption"})
            cur.execute("UPDATE trips SET constraints=%s::jsonb WHERE tenant_id=%s AND trip_id=%s",
                        (json.dumps(constraints, ensure_ascii=False), tenant_id, trip_id))
            cur.execute("INSERT INTO trip_guardian_changes (tenant_id, trip_id, actor_customer_id, enabled, via) "
                        "VALUES (%s,%s,%s,%s,%s)", (tenant_id, trip_id, customer_id, enabled, via))
    return view(conn, tenant_id=tenant_id, trip_id=trip_id, constraints=constraints)


__all__ = ["OFFER_LABEL", "REGISTRATION", "VIAS", "Via", "annotate", "is_on", "offer_for", "relevant", "set_enabled", "view"]

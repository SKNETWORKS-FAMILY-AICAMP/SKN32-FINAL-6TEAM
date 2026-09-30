# -*- coding: utf-8 -*-
"""결정 단위 — 고객 문장 하나를 **여행 상태를 보며** 한 번에 읽고 「할 일 + 대상」을 고른다. `[2026-09-29]`

★왜(사용자 지시 — 「규칙 땜질 말고 근본 해결」, Codex 두 계정 1회차 합의). 전에는 분류기 · 추출기 모델이 **문장만** 보고,
  대상은 낱말 규칙(끼니 · 서수 · 종류 · 날)이 메웠다. 모델이 일정 · 변경 이력 · 앞 대화 · 화면 선택을 몰라 「그 식당」
  「원래대로」「첫 식당」「이전에 요청한 거」를 못 풀었고, 새 표현마다 규칙이 늘었다.
  계획: `wiki/records/plans/2026-09-29_1640_채팅_결정단위_실행계획.md`.

★모델은 **고르기만** 한다 — 일정 목록의 짧은 id(i1 …) · 변경 id(c2 …) · 정해진 할 일 · 사실 종류 중에서(Ollama `format` 의
  JSON 스키마 enum — 목록 밖 값을 낼 수 없다). 값(시각 · 장소 · 버전 번호)은 만들지 않는다. 늦는 분은 **문장에 있는 숫자**만 받는다.
★검증 · 실행은 서버다(`trip_messages._run_decision`) — id 가 가리키는 항목의 종류 · 보호 · 버전을 보고 기존 실행 함수를 부른다.
  확정이 안 되면 되묻는다. ★모델 실패 · 검증 실패에 옛 규칙 경로로 넘기지 않는다(옛 오처리를 되살린다 — Codex 지적).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

ACTIONS = ("apply_change", "propose_alternatives", "rollback", "redo", "answer_fact", "ask_policy",
           "report_delay", "report_closed", "clarify", "other")
FACTS = ("detail", "address", "phone", "hours", "time", "next", "booking", "day", "move", "none")
KIND_KO = {"dining": "식당", "activity": "활동", "lodging": "숙소"}
#: 변경 이력에 싣는 최근 변경 수 — ★우리가 고른 값. 고객이 가리키는 변경은 대개 최근이다
RECENT_CHANGES = 8

SYSTEM = """너는 여행 일정 서비스의 요청 해석기다. 고객 문장 하나를 읽고 할 일(action)과 대상을 고른다. 추측으로 채우지 말고, 할 일이나 대상이 분명하지 않으면 clarify.
할 일(action):
- apply_change: 일정을 다른 곳으로 바꿔 달라(「바꿔」「변경해」「다른 데로」「다른 걸로」).
- propose_alternatives: 바꾸지 말고 후보만 알아봐 달라(「알아봐 줘」「추천」「뭐 있어」「어디가 좋아」).
- rollback: 앞서 바뀐 것을 원래대로 되돌려 달라(「원래대로」「되돌려」「이전 걸로」). target_change 에 되돌릴 변경 id — 문장이 어느 변경인지 말하지 않으면 (가장 최근) 표시가 붙은 변경.
- redo: 되돌렸던 변경을 다시 적용해 달라(「다시 진행」「다시 바꿔」). target_change 에 다시 적용할 변경 id.
- answer_fact: 이 여행의 사실을 묻는다 — fact 에 **물은 것 하나**를 고른다(가장 좁은 칸):
  address(위치 — 「어디 있어」「어딨어」「어디야」「어디쯤」「위치」「주소」) · phone(전화·연락처) ·
  hours(운영시간 — 「몇 시까지 해」「언제 열어·닫아」「쉬는 날」) · time(그 일정에 몇 시에 가나) · next(다음 일정) ·
  booking(예약) · day(하루 일정·요약) · move(이동 — 「어떻게 가」「얼마나 걸려」「가는 길」) ·
  detail(무엇을 묻는지 **특정하지 않을 때만** — 「알려줘」「자세히」「세부정보」「어떤 곳이야」).
  애매하면 detail 이 아니라 가장 좁은 칸을 고른다 — 「그건 어딧는거야」는 앞 대화의 장소를 가리키는 address 다.
  이름만 대고 「알려줘」면(「경복궁 알려줘」) 앞 대화와 상관없이 detail 이다.
- ask_policy: 규정·조건을 묻는다(취소·위약금·환불·동반·날씨 기준).
- report_delay: 늦는다고 알린다 — minutes 에 문장에 적힌 분(없으면 0).
- report_closed: 장소가 닫았다고 알린다.
- clarify: 무엇을 할지나 어느 일정인지 분명하지 않다 — choices 에 **이해한 범위 안의 해석 후보**
  1~3개(가장 그럴듯한 것부터 — 각각 action · target_item · target_change · fact). 「이거」「그거」가 무엇인지 화면 선택이나
  직전 대화로 정할 수 없으면 clarify.
- other: 여행 일정과 무관한 말 · 인사 · 이 서비스에 대한 질문(「뭘 할 수 있어?」「너는 누구야」).
대상(target_item)은 일정 목록의 id 중 하나이거나 none. 목록의 「그날 식당 N번째」「그날 활동 N번째」「끼니」를 그대로 써라 —
「둘째 날 두 번째 활동」은 2일차 줄 중 「그날 활동 2번째」인 줄이다. 날을 말하지 않은 「첫/두 번째」는 1일차에서 찾는다.
아침·점심·저녁은 그 끼니 표시가 붙은 식당이다. 「마지막 일정」은 목록의 마지막 줄이다.
확실하지 않은 채로 바꾸지 마라 — 할 일은 분명한데 대상이 둘 이상으로 읽히면 clarify 로 후보를 내라.
「그 식당」「거기」「방금 바꾼 거」처럼 가리키는 말은 직전 대화와 변경 이력에서 찾는다.
화면에서 고른 일정은 문장이 대상을 말하지 않을 때만 쓴다. 문장이 식당을 말했는데 고른 일정이 활동이면 쓰지 않는다."""


@dataclass
class Stop:
    alias: str
    item: Any


@dataclass
class Change:
    alias: str
    version: int
    reason: str
    target_item_id: UUID | None
    line: str


@dataclass
class Decision:
    action: str
    item: Any | None
    change: Change | None
    fact: str
    minutes: int | None
    question: str
    raw: dict[str, Any] = field(default_factory=dict)
    #: 되물을 때 **이해한 범위 안의 해석 후보** — [{action, item, change, fact}] (목록 밖 값은 서버가 버린다)
    choices: list[dict[str, Any]] = field(default_factory=list)
    seconds: float = 0.0

    def record(self) -> dict[str, Any]:
        """Case 에 남기는 모양 — 모델이 낸 그대로(`raw`)와 서버가 푼 값."""
        return {"raw": self.raw, "action": self.action, "item": getattr(self.item, "title", None),
                "item_id": str(self.item.item_id) if self.item is not None else None,
                "change": self.change.alias if self.change else None, "fact": self.fact, "minutes": self.minutes,
                "choices": [{"action": c["action"], "item": getattr(c["item"], "title", None),
                             "change": c["change"].alias if c["change"] else None, "fact": c["fact"]}
                            for c in self.choices],
                "seconds": round(self.seconds, 2)}


class DecisionFailed(RuntimeError):
    """모델을 못 불렀거나 답이 스키마 밖이다 — 부르는 쪽은 **바꾸지 않고** 묻는다."""


def _local(moment: datetime) -> datetime:
    return moment.astimezone(KST)


def stops_of(items: list[Any]) -> list[Stop]:
    """이동을 뺀 일정 — 시각 순으로 i1 … 을 붙인다."""
    stops = sorted((i for i in items if i.kind != "mobility"), key=lambda i: (i.starts_at, i.seq))
    return [Stop(f"i{n}", item) for n, item in enumerate(stops, start=1)]


def _day_no(item: Any, first: datetime | None) -> int:
    return (_local(item.starts_at).date() - _local(first).date()).days + 1 if first else 1


def changes_of(store: Any, conn: Any, trip_id: UUID, items: list[Any]) -> list[Change]:
    """버전마다 **장소가 바뀐 항목**(이동 제외)을 「N일차 HH:MM 종류: 전 → 후 (이유)」로. 최근 `RECENT_CHANGES` 개."""
    labels = {"customer_request": "고객 요청", "rollback": "되돌림", "customer_choice": "고객 선택",
              "auto_adjusted": "자동 변경", "customer_report": "고객 신고"}
    history = store.versions(conn, trip_id)[-(RECENT_CHANGES + 1):]     # ★최근 판만 — 판마다 항목을 읽는다
    current_ids = {i.item_id for i in items}
    first = min((i.starts_at for i in items), default=None)
    out: list[Change] = []
    previous = None
    for row in history:
        version = row["version"]
        now = [i for i in store.items(conn, trip_id, version) if i.kind != "mobility"]
        if previous is not None and row["reason"] != "created":    # 첫 줄은 비교 기준으로만 쓴다
            before_ids = {i.item_id for i in previous}
            added = {i.seq: i for i in now if i.item_id not in before_ids}
            removed = {i.seq: i for i in previous if i.item_id not in {x.item_id for x in now}}
            for seq, new in sorted(added.items()):
                old = removed.get(seq)
                old_name = (old.place or {}).get("name", old.title) if old else "(없음)"
                new_name = (new.place or {}).get("name", new.title)
                out.append(Change(f"c{version}", version, row["reason"],
                                  new.item_id if new.item_id in current_ids else None,
                                  f"{_day_no(new, first)}일차 {_local(new.starts_at):%H:%M} "
                                  f"{KIND_KO.get(new.kind, new.kind)}: {old_name} → {new_name} "
                                  f"({labels.get(row['reason'], row['reason'])})"))
        previous = now
    return out[-RECENT_CHANGES:]


def _meal(item: Any) -> str:
    hour = _local(item.starts_at).hour
    return "아침" if hour < 11 else "점심" if hour < 16 else "저녁"


def item_lines(stops: list[Stop], selected: str = "none") -> list[str]:
    """★모델이 **세지 않게** 서버가 센다 — 날 · 그날 같은 종류 안의 순번 · 끼니를 줄마다 적는다.
    ☆`[2026-09-29 재생 시험]` 7일 · 42항목 여행에서 「둘째 날 두 번째 활동」「셋째 날 세 번째 식당」을 모델이 세다 틀렸다
      (엉뚱한 대상 3건). 세는 일은 계산이지 해석이 아니다 — 모델은 적힌 표시를 고르기만 한다."""
    first = stops[0].item.starts_at if stops else None
    counts: dict[tuple[int, str], int] = {}
    out = []
    last_day = _day_no(stops[-1].item, first) if stops else 1
    for s in stops:
        day = _day_no(s.item, first)
        kind = KIND_KO.get(s.item.kind, s.item.kind)
        counts[(day, kind)] = counts.get((day, kind), 0) + 1
        mark = f"그날 {kind} {counts[(day, kind)]}번째" + (f" · {_meal(s.item)}" if s.item.kind == "dining" else "")
        tag = "(첫날)" if day == 1 else "(마지막 날)" if day == last_day else ""
        out.append(f"{s.alias} | {day}일차{tag} {_local(s.item.starts_at):%m-%d %H:%M} | {kind} · {mark} | "
                   f"{(s.item.place or {}).get('name') or s.item.title}" + (" | (화면에서 고름)" if s.alias == selected else ""))
    return out


def _prompt(stops: list[Stop], changes: list[Change], history: list[dict[str, Any]], selected: str,
            message: str) -> str:
    lines = item_lines(stops, selected)
    change_lines = [f"{c.alias} | 대상 {next((s.alias for s in stops if s.item.item_id == c.target_item_id), 'none')}"
                    f" | {c.line}" + (" (가장 최근)" if c is changes[-1] else "")
                    # ★`[2026-09-29 ui 세션 지적]` 그 변경의 결과가 지금 일정에 없으면(이미 되돌렸거나 다시 바뀜) 적는다 —
                    #   모델이 이미 되돌린 변경을 또 되돌리려 했다
                    + (" (지금 일정에 없음 — 이미 되돌렸거나 다시 바뀜)" if c.target_item_id is None else "")
                    for c in changes]
    from .chat_log import TURN_CHARS

    talk = "\n".join(f"{'고객' if t['role'] == 'customer' else 'triPilot'}: {t['text'][:TURN_CHARS]}"
                     for t in history) or "(없음)"
    return ("일정 목록:\n" + ("\n".join(lines) or "(없음)")
            + "\n\n바뀐 이력(아래가 최근):\n" + ("\n".join(change_lines) or "(없음)")
            + f"\n\n직전 대화:\n{talk}\n\n화면에서 고른 일정: {selected}\n\n고객 문장: {message}")


def _schema(stops: list[Stop], changes: list[Change]) -> dict[str, Any]:
    items = [s.alias for s in stops] + ["none"]
    change_ids = sorted({c.alias for c in changes}) + ["none"]
    choice = {"type": "object", "properties": {
        "action": {"type": "string", "enum": [a for a in ACTIONS if a != "clarify"]},
        "target_item": {"type": "string", "enum": items},
        "target_change": {"type": "string", "enum": change_ids},
        "fact": {"type": "string", "enum": list(FACTS)}},
        "required": ["action", "target_item", "target_change", "fact"]}
    return {"type": "object", "properties": {
        "action": {"type": "string", "enum": list(ACTIONS)},
        "target_item": {"type": "string", "enum": items},
        "target_change": {"type": "string", "enum": change_ids},
        "fact": {"type": "string", "enum": list(FACTS)},
        "minutes": {"type": "integer"},
        "choices": {"type": "array", "items": choice, "maxItems": 3}},
        # ★되묻는 문장은 모델이 쓰지 않는다 — 서버가 후보로 만든다(답이 길어져 p95 가 7초였다, 재생 시험 2026-09-29)
        "required": ["action", "target_item", "target_change", "fact", "minutes", "choices"]}


def decide(chat: Any, *, stops: list[Stop], changes: list[Change], history: list[dict[str, Any]],
           selected_item_id: UUID | None, message: str, num_predict: int = 400) -> Decision:
    """모델 한 번. 스키마 밖 · 목록 밖 값이면 `DecisionFailed`."""
    from app.modules.travel_ops.feedback import masked

    selected = next((s.alias for s in stops if selected_item_id and s.item.item_id == selected_item_id), "none")
    started = time.monotonic()
    try:
        raw = chat.structured(SYSTEM, _prompt(stops, changes, history, selected, masked(message)),
                              _schema(stops, changes), num_predict=num_predict)
    except Exception as exc:                          # noqa: BLE001 — 모델 장애는 부르는 쪽이 「바꾸지 않고 묻기」로 답한다
        raise DecisionFailed(f"{type(exc).__name__}: {str(exc)[:160]}") from exc
    seconds = time.monotonic() - started
    action = raw.get("action")
    if action not in ACTIONS:
        raise DecisionFailed(f"할 일이 목록 밖이다: {action!r}")
    by_alias = {s.alias: s.item for s in stops}
    target = raw.get("target_item") or "none"
    if target != "none" and target not in by_alias:
        raise DecisionFailed(f"대상이 목록 밖이다: {target!r}")
    changes_by = {c.alias: c for c in changes}
    change_alias = raw.get("target_change") or "none"
    if change_alias != "none" and change_alias not in changes_by:
        raise DecisionFailed(f"변경이 목록 밖이다: {change_alias!r}")
    fact = raw.get("fact") if raw.get("fact") in FACTS else "none"
    minutes = raw.get("minutes")
    # ★늦는 분은 **문장에 적힌 숫자**만 — 모델이 만든 수를 받지 않는다
    if not isinstance(minutes, int) or minutes <= 0 or str(minutes) not in re.findall(r"\d+", message or ""):
        minutes = None
    choices = []
    for option in raw.get("choices") or []:
        if not isinstance(option, dict) or option.get("action") not in ACTIONS or option.get("action") == "clarify":
            continue                                   # ★목록 밖 후보는 버린다(지어낸 해석을 보이지 않는다)
        item = by_alias.get(option.get("target_item") or "none")
        change = changes_by.get(option.get("target_change") or "none")
        if (option.get("target_item") or "none") != "none" and item is None:
            continue
        choices.append({"action": option["action"], "item": item, "change": change,
                        "fact": option.get("fact") if option.get("fact") in FACTS else "none"})
    return Decision(action=action, item=by_alias.get(target), change=changes_by.get(change_alias), fact=fact,
                    minutes=minutes, question=str(raw.get("question") or "").strip()[:200], raw=raw, seconds=seconds,
                    choices=choices[:3])


_FACT_KO = {"detail": "자세히", "address": "주소", "phone": "전화번호", "hours": "운영시간", "time": "몇 시에 가는지",
            "next": "다음 일정", "booking": "예약", "day": "하루 일정", "move": "가는 길"}


#: 사실 답 뒤에 「혹시 이런 뜻이었나요?」로 붙이는 가까운 질문 종류 — ★우리가 고른 짝(2026-09-29 사용자 제안). 앞의 것부터
NEAR_FACTS = {"address": ("move", "detail", "hours"), "hours": ("time", "detail", "address"),
              "detail": ("address", "hours", "next"), "phone": ("address", "detail"), "time": ("hours", "detail"),
              "next": ("day", "detail"), "day": ("next", "booking"), "booking": ("detail", "day"),
              "move": ("address", "time")}


def fact_first(decision: Decision) -> Decision:
    """★`[2026-09-29 사용자 지시]` 되묻는 대신 **먼저 답한다** — 모델이 되묻기를 골랐어도 후보가 **모두 사실 질문**이면
    (「2026-09-30 예약 표시를 알려 주세요」가 두 일정 중 어느 것인지 되물었다) 첫 후보로 답하고 나머지는 「혹시 이런 뜻이었나요?」로
    붙인다. 사실 답은 일정을 바꾸지 않아 잘못 짚어도 잃는 것이 없다. **바꾸기 · 되돌리기는 지금처럼 묻는다**(잘못 짚으면 일정이 바뀐다)."""
    choices = decision.choices
    if decision.action != "clarify" or not choices or any(c["action"] != "answer_fact" for c in choices):
        return decision
    first = choices[0]
    return replace(decision, action="answer_fact", item=first["item"], change=None,
                   fact=first["fact"] if first["fact"] != "none" else "detail", choices=choices[1:])


def maybe_meant(decision: Decision, fact: str, first: datetime | None, limit: int = 3) -> list[dict[str, str]]:
    """사실 답에 붙일 「혹시 이런 뜻이었나요?」 — 모델이 낸 다른 해석 먼저, 모자라면 같은 일정의 가까운 질문 종류. 버튼 모양."""
    options = [c for c in decision.choices if c["action"] == "answer_fact"]
    options += [{"action": "answer_fact", "item": decision.item, "change": None, "fact": near}
                for near in NEAR_FACTS.get(fact, ())]
    out: list[dict[str, str]] = []
    for option in options:
        if option["item"] is decision.item and option["fact"] == fact:
            continue
        text = choice_message(option, first)
        if text and all(text != c["message"] for c in out):
            out.append({"label": text, "message": text})
        if len(out) >= limit:
            break
    return out


def choice_message(choice: dict[str, Any], first: datetime | None) -> str | None:
    """해석 후보 → **그대로 보내면 한 번에 알아듣는 문장**(웹 버튼 · 「1번」 답의 뜻). 만들 수 없으면 None."""
    item, change, action = choice.get("item"), choice.get("change"), choice["action"]
    where = (f"{_day_no(item, first)}일차 {_local(item.starts_at):%H:%M} "
             f"{(item.place or {}).get('name') or item.title}") if item is not None else None
    if action == "apply_change" and where:
        return f"{where} 다른 곳으로 바꿔 줘"
    if action == "propose_alternatives" and where:
        return f"{where} 대신 갈 곳 알아봐 줘"
    if action == "rollback" and change is not None:
        return f"「{change.line}」 변경을 되돌려 줘"
    if action == "redo" and change is not None:
        return f"「{change.line}」 변경을 다시 적용해 줘"
    if action == "answer_fact":
        what = _FACT_KO.get(choice.get("fact") or "detail", "자세히")
        return f"{where} {what} 알려 줘" if where else f"{what} 알려 줘"
    if action == "report_closed" and where:
        return f"{where} 문 닫았어요"
    return None


def labels(decision: Decision) -> dict[str, str]:
    """Case 분류 표지 — 할 일과 대상 종류에서 **정해진 규칙으로** 만든다(모델을 또 부르지 않는다).

    요청 종류(intent): 바꾸기 · 알아보기 · 되돌리기 · 다시 적용 → 조정 거부(adjust_reject) / 사실 · 규정 → 확인 요청 /
    늦음 · 휴무 → 사건 신고 / 되묻기 · 그 밖 → other. 사건 코드 접두는 **대상의 실제 종류**(없으면 other — 여행 창구).
    """
    intent = {"apply_change": "adjust_reject", "propose_alternatives": "adjust_reject", "rollback": "adjust_reject",
              "redo": "adjust_reject", "answer_fact": "confirm_request", "ask_policy": "confirm_request",
              "report_delay": "incident_report", "report_closed": "incident_report"}.get(decision.action, "other")
    kind = getattr(decision.item, "kind", None)
    if decision.action == "report_delay":
        code = "dining_hours"                  # 늦음은 다음 식사가 그 시각에 되는지를 본다(식당 팀)
    elif kind == "dining":
        code = "dining_hours" if decision.action in ("report_closed",) or decision.fact == "hours" else "dining_other"
    elif kind == "activity":
        code = "activity_cancel_or_change" if intent == "adjust_reject" else "activity_other"
    elif kind == "mobility":
        code = "mobility_other"
    else:
        code = "other"
    sentiment = "negative" if intent == "incident_report" else "neutral"
    return {"intent": intent, "issue_code": code, "sentiment": sentiment}


__all__ = ["ACTIONS", "Change", "Decision", "DecisionFailed", "FACTS", "NEAR_FACTS", "fact_first", "maybe_meant", "Stop", "SYSTEM", "changes_of", "choice_message",
           "decide", "item_lines", "labels", "stops_of"]

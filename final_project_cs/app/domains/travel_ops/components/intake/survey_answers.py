# -*- coding: utf-8 -*-
"""로딩 중 질문 — 무엇을 묻고 · 답을 어디에 모으고 · 등록 때 설문에 어떻게 합치나. `[2026-10-06 사용자 지시 · uiux 인계]`

기획 `wiki/records/plans/2026-10-05_설문_계획서에서_읽고_로딩에서_묻기_기획.md` 「서버 몫」 1 · 계약 `wiki/external/rest-endpoints.md` 「설문 질문」.

★**쓰는 문항만 묻는다.** 설문 문항 가운데 판정에 실제로 이어진 것(`survey.py` 머리말)만 — 지금은 둘이다.
    preferred_mobility  「이동은 주로 어떻게 하세요?」   → `priority_details.mobility`   (이동 계산기 수단 — `mobility/wiring.modes_from_survey`)
    priority            「대체할 곳은 무엇을 먼저…」       → `priority`                  (대체 활동 비슷함의 가중 — `activity/similarity.preference_of`)
  받기만 하고 쓰는 곳이 없는 문항(테마 · 동행 · 실내외 · 세부 테마)과 거의 영향이 없는 문항(내국인 여부 — 판정은 값을 로그 문맥으로만 쓴다)은 **묻지 않는다.**
★**식사 제한(채식 · 할랄)과 접근성은 묻지 않는다** — 읽어서 채우지도 않는다. 민감 정보라 동의 화면(`consents`)이 있는 곳에서만 받는다.
★`on_disruption` · `pace` 는 **묻는 문항이 아니다**(항로 지킴이 카드 · 계획 담기 화면이 보낸다). 다만 같은 입구가 그 값도 **받는다**(`DIRECT`) —
  카드의 답을 접수에 실어 두었다가 등록 때 합치기 위해서다. 문항 목록(`questions[]`)에는 없다.
★답은 **고른 선택지 번호 그대로** `trip_intakes.survey` 에 둔다. 설문의 모양으로 바꾸는 것은 `to_survey` 한 곳이다.
★모르는 문항 · 모르는 선택지는 **거절**한다(422) — 조용히 흘리지 않는다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping
from uuid import UUID

from app.domains.travel_ops.components.planning.survey import SURVEY_VERSION

log = logging.getLogger(__name__)

#: 한 번에 묻는 문항 수의 상한 — 화면이 3개까지 담는다(기획 「최대 3문항」)
MAX_QUESTIONS = 3


@dataclass(frozen=True)
class Question:
    id: str
    title: str
    why: str
    #: (선택지 번호, 화면에 보일 글)
    options: tuple[tuple[str, str], ...]

    def option_ids(self) -> tuple[str, ...]:
        return tuple(option for option, _ in self.options)


#: 묻는 문항 — 앞이 먼저 나간다. ★렌트카(`car`)는 이동 계산기가 아직 못 다뤄 선택지에 없다(`wiring.SURVEY_MODES`)
QUESTIONS: tuple[Question, ...] = (
    Question("preferred_mobility", "이동은 주로 어떻게 하세요?", "계획서만으로는 이동 방법을 알 수 없어서 여쭤요",
             (("public", "대중교통"), ("taxi", "택시"), ("walk", "걷기 위주"))),
    Question("priority", "일정이 바뀔 때 대체할 곳은 무엇을 먼저 볼까요?", "계획서만으로는 알 수 없어요",
             (("activity", "하고 싶은 활동이 비슷한 곳"), ("mobility", "이동이 편한 곳"))),
)
_BY_ID = {question.id: question for question in QUESTIONS}

#: 묻지는 않지만 같은 입구가 받는 값 — 항로 지킴이 카드(`on_disruption`) · 계획 담기 화면(`pace`)
DIRECT: dict[str, tuple[str, ...]] = {
    "on_disruption": ("replace", "ask_first"),
    "pace": ("relaxed", "moderate", "packed"),
}


class InvalidAnswers(ValueError):
    """모르는 문항 · 모르는 선택지. `problems` = `[{key, reason}]`."""

    def __init__(self, problems: list[dict[str, str]]) -> None:
        super().__init__("; ".join(f"{p['key']}: {p['reason']}" for p in problems))
        self.problems = problems


def check(answers: Mapping[str, Any]) -> dict[str, str]:
    """받은 답을 확인해 `{문항: 선택지 번호}` 로 돌려준다. 틀린 것이 하나라도 있으면 **전부 거절**한다(일부만 저장하지 않는다)."""
    problems: list[dict[str, str]] = []
    clean: dict[str, str] = {}
    for key, value in answers.items():
        allowed = _BY_ID[key].option_ids() if key in _BY_ID else DIRECT.get(key)
        if allowed is None:
            problems.append({"key": str(key), "reason": "모르는 문항이다"})
        elif not isinstance(value, str) or value not in allowed:
            problems.append({"key": str(key), "reason": f"선택지는 {', '.join(allowed)} 중 하나여야 한다"})
        else:
            clean[key] = value
    if problems:
        raise InvalidAnswers(problems)
    return clean


def stored(conn, *, tenant_id: str, intake_id: UUID) -> dict[str, str]:
    """이 접수에 모아 둔 답. ★마이그레이션 051 이 안 올라간 DB 에서도 접수 조회는 되게 — 못 읽으면 빈 답 + 경고(질문 없이 가는 옛 동작)."""
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT survey FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s", (tenant_id, intake_id))
            row = cur.fetchone()
    except Exception:                                                  # noqa: BLE001
        log.warning("intake survey answers unreadable intake=%s (migration 051?)", intake_id, exc_info=True)
        return {}
    return {k: v for k, v in dict((row[0] if row else None) or {}).items() if isinstance(v, str)}


def questions(answers: Mapping[str, str]) -> list[dict[str, Any]]:
    """`GET /v1/web/trip-intakes/{id}` 의 `questions[]`. 이미 답한 문항도 **그대로 둔다**(`answer` 에 고른 번호) — 화면이 새로 고쳐져도 앞 질문으로 돌아가 고칠 수 있게.

    ★목록은 접수와 상관없이 같은 순서 · 같은 문항이다(문항이 답에 따라 사라지지 않는다) — 화면의 `i / N` 이 흔들리지 않는다."""
    return [{"id": q.id, "kind": "single", "title": q.title, "why": q.why,
             "options": [{"id": option, "label": label} for option, label in q.options],
             "answer": answers.get(q.id)}
            for q in QUESTIONS[:MAX_QUESTIONS]]


def save(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID, answers: Mapping[str, str]) -> list[str] | None:
    """답을 모은다(같은 문항은 덮어쓴다). 돌려주는 값 = 지금까지 답한 **모든** 문항 번호(정렬). 남의 접수 · 없는 접수면 None.

    ★한 트랜잭션 — 호출자가 `with conn.transaction():` 으로 감싼다. 접수 행을 잠근다(`FOR UPDATE`) — 탭 둘이 동시에 다른 문항을 저장해도 서로를 덮지 않는다.
    ★`updated_at` 은 안 건드린다(마이그레이션 051 설명). 이미 등록된 접수(`confirmed`)는 `IntakeClosed` — 답이 여행에 닿지 못한다."""
    import json

    with conn.cursor() as cur:
        cur.execute("SELECT status, survey FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s AND customer_id=%s FOR UPDATE",
                    (tenant_id, intake_id, customer_id))
        row = cur.fetchone()
        if row is None:
            return None
        if row[0] == "confirmed":
            raise IntakeClosed()
        merged = {**{k: v for k, v in dict(row[1] or {}).items() if isinstance(v, str)}, **answers}
        cur.execute("UPDATE trip_intakes SET survey=%s::jsonb WHERE tenant_id=%s AND intake_id=%s",
                    (json.dumps(merged, ensure_ascii=False), tenant_id, intake_id))
    return sorted(merged)


class IntakeClosed(Exception):
    """이미 등록된 접수 — 답을 더할 수 없다."""


def to_survey(answers: Mapping[str, str]) -> dict[str, Any]:
    """모아 둔 답(`{문항: 선택지}`)을 설문(`TripSurvey`)의 조각으로. ★`version` 은 합칠 때 붙인다."""
    out: dict[str, Any] = {}
    if "preferred_mobility" in answers:
        out["priority_details"] = {"mobility": [answers["preferred_mobility"]]}
    if "priority" in answers:
        out["priority"] = [answers["priority"]]
    for key in DIRECT:
        if key in answers:
            out[key] = answers[key]
    return out


def merged_survey(answers: Mapping[str, str], request_survey: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """등록 때 쓸 설문 = 접수에 모아 둔 답 + 등록 요청이 직접 준 설문. **요청이 준 값이 이긴다**(가장 나중의 직접 입력).

    - 둘 다 없으면 None(설문 없이 등록 — 옛 동작 그대로).
    - 세부 선택(`priority_details`)은 영역마다 합친다 — 요청이 `food` 만 줘도 모아 둔 `mobility` 가 남는다.
    - ★설문 안 문항을 **채워 넣지 않는다** — 안 답한 문항은 없는 채로 둔다(`apply_survey` 가 「직접 답한 문항」을 가르는 기준이다)."""
    mine = to_survey(answers)
    if not mine and request_survey is None:
        return None
    given = dict(request_survey or {})
    survey: dict[str, Any] = {"version": SURVEY_VERSION, **mine, **given}
    details = {**(mine.get("priority_details") or {}), **(given.get("priority_details") or {})}
    if details:
        survey["priority_details"] = details
    return survey


__all__ = ["DIRECT", "IntakeClosed", "InvalidAnswers", "MAX_QUESTIONS", "QUESTIONS", "Question", "check", "merged_survey",
           "questions", "save", "stored", "to_survey"]

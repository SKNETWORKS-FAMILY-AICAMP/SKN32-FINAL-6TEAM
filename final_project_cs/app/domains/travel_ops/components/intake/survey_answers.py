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
★`[2026-10-06 uiux 요청 · 맞춤 질문 의논 §7]` **문항 번호(`Question.id`)와 슬롯(`Question.slot` — 구조화 값이 들어가는 자리)은 다른 칸이다.** 선택지 번호 ↔ 구조화 값(`Option.value`)의 매핑은
  **서버가 소유**한다 — 웹은 `questions[]` 만 그리고 뜻을 모른다. 문구를 바꿔도 문항 · 선택지 번호를 새로 만들지 않고 **같은 선택지 번호의 뜻을 바꾸지 않는다.**
  뜻이 바뀌는 변경(값 매핑 · 선택지 추가/삭제 · 문항 추가/삭제)은 **`QUESTION_SET_VERSION` 을 올린다.**
★저장할 때 그때의 묶음 버전 · 문구 · 라벨 · 슬롯 · 해석한 값을 `trip_intake_survey_answers` 에 남기고(053), **등록 때는 저장 때 해석한 값으로 설문을 만든다** — 묶음이 바뀐 뒤에도 옛 답이 새 매핑으로 잘못 읽히지 않는다.
  이력이 없는 옛 답(053 이 안 올라간 DB)은 지금 묶음의 매핑으로 읽는다(경고를 남긴다).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Mapping
from uuid import UUID

from app.domains.travel_ops.components.planning.survey import SURVEY_VERSION

log = logging.getLogger(__name__)

#: 한 번에 묻는 문항 수의 상한 — 화면이 3개까지 담는다(기획 「최대 3문항」)
MAX_QUESTIONS = 3


#: 질문 묶음 버전 — 문구만 고치면 안 올린다. **선택지 목록 · 값 매핑 · 문항의 추가/삭제**처럼 답의 뜻이 달라지면 올린다(옛 답은 저장 때 해석한 값으로 남는다)
QUESTION_SET_VERSION = "2"
CUSTOM_PREFIX = "custom:"
CLEARED_ANSWER = "__cleared__"
MAX_CUSTOM_LENGTH = 1000


@dataclass(frozen=True)
class Option:
    id: str                    # 화면이 아는 선택지 번호 — 한 번 내보내면 뜻을 바꾸지 않는다
    label: str                 # 화면에 보일 글
    value: str                 # 서버가 소유하는 구조화 값(설문에 들어가는 코드). 번호와 우연히 같아도 다른 칸이다


@dataclass(frozen=True)
class Question:
    id: str                    # 화면이 아는 문항 번호
    slot: str                  # 구조화 값이 들어가는 자리(`to_survey` 가 안다)
    title: str
    why: str
    options: tuple[Option, ...]
    kind: str = "single"

    def option_ids(self) -> tuple[str, ...]:
        return tuple(option.id for option in self.options)

    def value_of(self, option_id: str) -> str | None:
        return next((option.value for option in self.options if option.id == option_id), None)


#: 묻는 문항 — 앞이 먼저 나간다. ★렌트카(`car`)는 이동 계산기가 아직 못 다뤄 선택지에 없다(`wiring.SURVEY_MODES`)
QUESTIONS: tuple[Question, ...] = (
    Question("preferred_mobility", "preferred_mobility", "이동은 주로 어떻게 하세요?", "계획서만으로는 이동 방법을 알 수 없어서 여쭤요",
             (Option("public", "대중교통", "public"), Option("taxi", "택시", "taxi"), Option("walk", "걷기 위주", "walk"))),
    Question("priority", "priority", "일정이 바뀔 때 대체할 곳은 무엇을 먼저 볼까요?", "계획서만으로는 알 수 없어요",
             (Option("activity", "하고 싶은 활동이 비슷한 곳", "activity"), Option("mobility", "이동이 편한 곳", "mobility"))),
)


def _by_id() -> dict[str, Question]:
    """지금 묶음의 문항 번호 표 — 부를 때마다 만든다(시험이 묶음을 바꿔 끼운다)."""
    return {question.id: question for question in QUESTIONS}


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


def check(answers: Mapping[str, Any]) -> dict[str, str | None]:
    """받은 답을 확인해 `{문항: 선택지 번호}` 로 돌려준다. 틀린 것이 하나라도 있으면 **전부 거절**한다(일부만 저장하지 않는다)."""
    problems: list[dict[str, str]] = []
    clean: dict[str, str | None] = {}
    known = _by_id()
    for key, value in answers.items():
        allowed = known[key].option_ids() if key in known else DIRECT.get(key)
        if allowed is None:
            problems.append({"key": str(key), "reason": "모르는 문항이다"})
        elif value is None and key in known:
            clean[key] = None
        elif key in known and isinstance(value, dict) and set(value) == {"custom"}:
            raw = value["custom"]
            if not isinstance(raw, str) or not raw.strip() or len(raw) > MAX_CUSTOM_LENGTH:
                problems.append({"key": key, "reason": f"직접 입력은 1~{MAX_CUSTOM_LENGTH}자로 적어 주세요"})
            else:
                clean[key] = CUSTOM_PREFIX + raw.strip()
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


def inherit(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID) -> None:
    """같은 고객의 저장된 로딩 설문을 이어받는다. 뜻·묶음이 바뀐 답과 직접 설정은 새로 묻는다."""
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT ON (a.question_id) a.question_id, a.option_id, a.slot, a.value, a.bundle_version "
                    "FROM trip_intake_survey_answers a JOIN trip_intakes i ON i.intake_id=a.intake_id AND i.tenant_id=a.tenant_id "
                    "WHERE a.tenant_id=%s AND i.customer_id=%s AND a.intake_id<>%s "
                    "ORDER BY a.question_id, a.seq DESC", (tenant_id, customer_id, intake_id))
        previous = cur.fetchall()
    known = _by_id()
    answers = {key: option for key, option, slot, value, version in previous
               if key in known and version == QUESTION_SET_VERSION and resolve(key, option) == (slot, value)}
    if answers:
        save(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, answers=answers)


def questions(answers: Mapping[str, str]) -> list[dict[str, Any]]:
    """`GET /v1/web/trip-intakes/{id}` 의 `questions[]`. 이미 답한 문항도 **그대로 둔다**(`answer` 에 고른 번호) — 화면이 새로 고쳐져도 앞 질문으로 돌아가 고칠 수 있게.

    ★목록은 접수와 상관없이 같은 순서 · 같은 문항이다(문항이 답에 따라 사라지지 않는다) — 화면의 `i / N` 이 흔들리지 않는다."""
    return [{"id": q.id, "kind": q.kind, "title": q.title, "why": q.why,
             "options": [{"id": option.id, "label": option.label} for option in q.options],
             "allow_custom": True, "custom_max_length": MAX_CUSTOM_LENGTH,
             "answer": None if str(answers.get(q.id) or "").startswith(CUSTOM_PREFIX) else answers.get(q.id),
             "custom_answer": answers[q.id][len(CUSTOM_PREFIX):] if str(answers.get(q.id) or "").startswith(CUSTOM_PREFIX) else None}
            for q in QUESTIONS[:MAX_QUESTIONS]]


def save(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID, answers: Mapping[str, str | None]) -> list[str] | None:
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
        merged = {k: v for k, v in merged.items() if v is not None}
        cur.execute("UPDATE trip_intakes SET survey=%s::jsonb WHERE tenant_id=%s AND intake_id=%s",
                    (json.dumps(merged, ensure_ascii=False), tenant_id, intake_id))
        _record(cur, tenant_id=tenant_id, intake_id=intake_id, answers=answers)
    return sorted(merged)


def _record(cur, *, tenant_id: str, intake_id: UUID, answers: Mapping[str, str | None]) -> None:
    """답 이력(053)에 **그때의 묶음 버전 · 문구 · 라벨 · 슬롯 · 해석한 값**을 남긴다. 같은 묶음 · 같은 선택지를 또 보낸 것(멱등 재전송)은 줄을 더하지 않는다."""
    known = _by_id()
    for key, option_id in answers.items():
        if option_id is None:
            slot, value = known[key].slot, ""
            option_id = CLEARED_ANSWER
        else:
            slot, value = resolve(key, option_id) or (None, None)
        if slot is None or value is None:                                # check() 를 지났으니 일어날 수 없다 — 일어나면 조용히 흘리지 않는다
            raise ValueError(f"해석할 수 없는 답: {key}={option_id}")
        cur.execute("SELECT option_id, bundle_version FROM trip_intake_survey_answers WHERE tenant_id=%s AND intake_id=%s AND question_id=%s "
                    "ORDER BY seq DESC LIMIT 1", (tenant_id, intake_id, key))
        last = cur.fetchone()
        if last is not None and tuple(last) == (option_id, QUESTION_SET_VERSION):
            continue
        question = known.get(key)
        label = (option_id[len(CUSTOM_PREFIX):] if option_id.startswith(CUSTOM_PREFIX)
                 else next((o.label for o in question.options if o.id == option_id), None) if question else None)
        cur.execute("INSERT INTO trip_intake_survey_answers (tenant_id, intake_id, question_id, option_id, slot, value, question_text, option_label, bundle_version) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (tenant_id, intake_id, key, option_id, slot, value, question.title if question else None, label, QUESTION_SET_VERSION))


def resolve(key: str, option_id: str) -> tuple[str, str] | None:
    """지금 묶음에서 이 답이 **어느 슬롯의 어떤 값**인가 — `(슬롯, 값)`. 모르면 None. 직접 값(`on_disruption` · `pace`)은 이름이 슬롯이고 값은 그대로다."""
    question = _by_id().get(key)
    if question is not None:
        if option_id.startswith(CUSTOM_PREFIX) and option_id[len(CUSTOM_PREFIX):].strip():
            return question.slot, option_id
        value = question.value_of(option_id)
        return None if value is None else (question.slot, value)
    if key in DIRECT and option_id in DIRECT[key]:
        return key, option_id
    return None


def stored_resolved(conn, *, tenant_id: str, intake_id: UUID) -> dict[str, tuple[str, str, str]]:
    """문항마다 **저장 때 해석해 둔** 최신 답 `{문항: (선택지 번호, 슬롯, 값)}`. ★묶음이 바뀐 뒤에도 옛 답을 그때의 뜻으로 읽게 한다.
    053 이 안 올라간 DB 는 빈 결과 + 경고(그러면 지금 묶음의 매핑으로 읽는다)."""
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT DISTINCT ON (question_id) question_id, option_id, slot, value FROM trip_intake_survey_answers "
                        "WHERE tenant_id=%s AND intake_id=%s ORDER BY question_id, seq DESC", (tenant_id, intake_id))
            return {key: (option, slot, value) for key, option, slot, value in cur.fetchall()}
    except Exception:                                                  # noqa: BLE001
        log.warning("intake survey answer history unreadable intake=%s (migration 053?)", intake_id, exc_info=True)
        return {}


class IntakeClosed(Exception):
    """이미 등록된 접수 — 답을 더할 수 없다."""


def _place(survey: dict[str, Any], slot: str, value: str) -> None:
    """슬롯의 값을 설문(`TripSurvey`)의 자리에 둔다 — 슬롯이 어디로 가는지는 여기 한 곳이다."""
    if value.startswith(CUSTOM_PREFIX):
        raw = value[len(CUSTOM_PREFIX):]
        survey.setdefault("custom_answers", {})[slot] = raw
        # 원문을 보존하고 구분된 기존 단어만 계산용 코드에 대응시킨다.
        tokens = re.split(r"[+/,、·&\s]+", raw.lower())
        if slot == "preferred_mobility":
            aliases = {"택시": "taxi", "taxi": "taxi", "버스": "bus", "bus": "bus",
                       "지하철": "subway", "subway": "subway", "대중교통": "public", "public": "public",
                       "도보": "walk", "걷기": "walk", "walk": "walk"}
            codes = list(dict.fromkeys(aliases[token] for token in tokens if token in aliases))
            if codes:
                survey.setdefault("priority_details", {})["mobility"] = codes
        elif slot == "priority":
            aliases = {"활동": "activity", "activity": "activity", "이동": "mobility", "mobility": "mobility",
                       "음식": "food", "식사": "food", "food": "food"}
            codes = list(dict.fromkeys(aliases[token] for token in tokens if token in aliases))
            if codes:
                survey["priority"] = codes
        return
    if slot == "preferred_mobility":
        survey["priority_details"] = {"mobility": [value]}
    elif slot == "priority":
        survey["priority"] = [value]
    elif slot in DIRECT:
        survey[slot] = value
    else:                                                              # 묶음이 모르는 슬롯 — 조용히 버리지 않는다
        log.warning("intake survey answer for an unknown slot=%s", slot)


def to_survey(answers: Mapping[str, str], resolved: Mapping[str, tuple[str, str, str]] | None = None) -> dict[str, Any]:
    """모아 둔 답(`{문항: 선택지}`)을 설문(`TripSurvey`)의 조각으로. ★`version` 은 합칠 때 붙인다.

    `resolved` = 저장 때 해석한 값(`stored_resolved`). 그 문항의 선택지가 지금 답과 같으면 **그것을 쓴다**(묶음이 바뀌어도 옛 뜻 그대로). 없으면 지금 묶음의 매핑."""
    out: dict[str, Any] = {}
    for key, option_id in answers.items():
        saved = (resolved or {}).get(key)
        if saved is not None and saved[0] == option_id:
            slot, value = saved[1], saved[2]
        else:
            now = resolve(key, option_id)
            if now is None:
                log.warning("intake survey answer cannot be read key=%s option=%s (question set changed, no history)", key, option_id)
                continue
            slot, value = now
        _place(out, slot, value)
    return out


def merged_survey(answers: Mapping[str, str], request_survey: Mapping[str, Any] | None,
                  resolved: Mapping[str, tuple[str, str, str]] | None = None) -> dict[str, Any] | None:
    """등록 때 쓸 설문 = 접수에 모아 둔 답 + 등록 요청이 직접 준 설문. **요청이 준 값이 이긴다**(가장 나중의 직접 입력).

    - 둘 다 없으면 None(설문 없이 등록 — 옛 동작 그대로).
    - 세부 선택(`priority_details`)은 영역마다 합친다 — 요청이 `food` 만 줘도 모아 둔 `mobility` 가 남는다.
    - ★설문 안 문항을 **채워 넣지 않는다** — 안 답한 문항은 없는 채로 둔다(`apply_survey` 가 「직접 답한 문항」을 가르는 기준이다)."""
    mine = to_survey(answers, resolved)
    if not mine and request_survey is None:
        return None
    given = dict(request_survey or {})
    survey: dict[str, Any] = {"version": SURVEY_VERSION, **mine, **given}
    details = {**(mine.get("priority_details") or {}), **(given.get("priority_details") or {})}
    if details:
        survey["priority_details"] = details
    return survey


__all__ = ["DIRECT", "IntakeClosed", "InvalidAnswers", "MAX_QUESTIONS", "Option", "QUESTIONS", "QUESTION_SET_VERSION", "Question", "check", "merged_survey",
           "questions", "resolve", "save", "stored", "stored_resolved", "to_survey"]

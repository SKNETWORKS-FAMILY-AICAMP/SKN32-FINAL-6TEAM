# -*- coding: utf-8 -*-
"""로딩 중 질문 — 무엇을 묻고 · 답을 어디에 모으고 · 등록 때 설문에 어떻게 합치나. `[2026-10-06 사용자 지시 · uiux 인계]` · `[2026-10-19 개편]`

계약 `wiki/external/rest-endpoints/web-intakes.md` 「설문 질문」 · 설계 `wiki/records/plans/2026-10-19_로딩설문_읽은칸빼고_빈칸만묻기.md`.

★`[2026-10-19 사용자 지시]` **계획서에서 읽은 칸은 빼고 빈 칸만 묻는다 — 상한 없음.** 후보는 시작 설문(웹 `features/onboarding/model.ts`)에서
  「일정이 꼬이면」(항로 지킴이 카드 몫)을 뺀 네 문항이다 — 문구 · 선택지가 시작 설문과 같다(활동 세부는 관광 분류 일곱 코드).
  ★`[2026-10-19 UI 팀 4문항에 맞춰 theme 제외]` 처음 구현은 「여행 테마」까지 다섯이었다. UI 팀이 시작 설문에서 테마를 뺐고(712206795) 로딩 문항 = 시작 설문 − 일정이 꼬이면 이 원칙이라 같이 뺐다.
  테마 답은 **받아 두기만 하는 입구**(`DIRECT`)로 남긴다 — 옛 화면 · 외부가 보내도 거절하지 않는다.
    party           누구와 함께                → survey.party                         (읽은 아이 · 어르신 성향으로 추정해 채우지 않는다)
    priority        우선순위(분야 순서 + 세부)  → survey.priority · priority_details     (세부만 읽어 채운다: 이동 ← 이동 수단, 음식 ← 식당 취향)
    indoor_outdoor  실내 · 실외(식당 · 활동)    → survey.indoor_outdoor                (활동 칸 ← 「비 오면 실내」)
    pace            여유                       → survey.pace                          (통째로 ← 읽은 일정 여유)
★고르는 규칙 — 문항마다: 첫 조회 때 이미 답이 있다 → 뺀다 / 계획서 읽기가 채웠다 → 빼고 `skipped_by_reading` 에 싣는다 / 나머지 → 묻는다.
  **두 번에 정한다** — 처음(접수 직후)은 읽기와 상관없는 `phase=1` 문항, 이해 단계 결과가 나온 뒤 `phase=2` 문항을 **뒤에 붙인다**(`loading_questions`).
  정한 목록은 접수 행(`trip_intakes.survey_plan`, 907)에 두어 그 접수에서 흔들리지 않게 한다 — 이미 보인 문항은 지워지지 않는다.
★**식사 제한(채식 · 할랄)과 접근성 · 덜 걷게는 묻지 않는다** — 민감 정보라 동의 화면(`consents`)이 있는 곳에서만 받는다. 하루 시작 · 끝 시각은 문항이 없다.
★`on_disruption` 은 **묻는 문항이 아니다**(항로 지킴이 카드가 보낸다). 다만 같은 입구가 그 값도 **받는다**(`DIRECT`). `pace` 는 이제 문항이다(계획 담기 화면도 같은 선택지로 보낸다).
★답은 **고른 선택지 번호 그대로** `trip_intakes.survey` 에 둔다 — 여러 칸 답(`priority` · `pair`)은 키를 정렬한 JSON 글로. 설문의 모양으로 바꾸는 것은 `to_survey` 한 곳이다.
★모르는 문항 · 모르는 선택지 · 모양이 틀린 답은 **거절**한다(422) — 조용히 흘리지 않는다.
★`[2026-10-06 uiux 요청 · 맞춤 질문 의논 §7]` **문항 번호(`Question.id`)와 슬롯(`Question.slot` — 구조화 값이 들어가는 자리)은 다른 칸이다.** 선택지 번호 ↔ 구조화 값(`Option.value`)의 매핑은
  **서버가 소유**한다 — 웹은 `questions[]` 만 그리고 뜻을 모른다. 문구를 바꿔도 문항 · 선택지 번호를 새로 만들지 않고 **같은 선택지 번호의 뜻을 바꾸지 않는다.**
  뜻이 바뀌는 변경(값 매핑 · 선택지 추가/삭제 · 문항 추가/삭제)은 **`QUESTION_SET_VERSION` 을 올린다.**
  ☆묶음 3의 `priority` 는 묶음 2의 `priority`(대체할 곳 — 활동/이동 하나)와 번호는 같고 **슬롯이 다르다**(`priority_rank`) — 옛 답은 이력의 해석 값(슬롯 `priority`)으로 읽힌다.
★저장할 때 그때의 묶음 버전 · 문구 · 라벨 · 슬롯 · 해석한 값을 `trip_intake_survey_answers` 에 남기고(053), **등록 때는 저장 때 해석한 값으로 설문을 만든다** — 묶음이 바뀐 뒤에도 옛 답이 새 매핑으로 잘못 읽히지 않는다.
  이력이 없는 옛 답(053 이 안 올라간 DB)은 지금 묶음의 매핑으로 읽는다(경고를 남긴다).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping
from uuid import UUID

from app.domains.travel_ops.components.planning.survey import ACTIVITY_DETAILS, SURVEY_VERSION

from . import reading_prefs

log = logging.getLogger(__name__)

#: 질문 묶음 버전 — 문구만 고치면 안 올린다. **선택지 목록 · 값 매핑 · 문항의 추가/삭제**처럼 답의 뜻이 달라지면 올린다(옛 답은 저장 때 해석한 값으로 남는다)
#: ☆"2"(2026-10-06~10-18): 이동 수단 · 대체할 곳 두 문항, 최대 3. "3"(2026-10-19): 시작 설문의 네 문항(누구와 · 우선순위 · 실내외 · 여유) · 읽은 칸은 뺀다 · 상한 없음
#:   ("3" 은 어느 서버에도 배포된 적 없다 — 다섯 문항에서 테마만 뺀 지금 판이 "3" 의 첫 모양이다)
QUESTION_SET_VERSION = "3"
CUSTOM_PREFIX = "custom:"
CLEARED_ANSWER = "__cleared__"
MAX_CUSTOM_LENGTH = 1000


@dataclass(frozen=True)
class Option:
    id: str                    # 화면이 아는 선택지 번호 — 한 번 내보내면 뜻을 바꾸지 않는다
    label: str                 # 화면에 보일 글
    value: str                 # 서버가 소유하는 구조화 값(설문에 들어가는 코드). 번호와 우연히 같아도 다른 칸이다


@dataclass(frozen=True)
class Group:
    """여러 칸 문항의 칸 하나 — 우선순위의 분야별 세부(`priority`) · 실내외의 식당/활동 칸(`pair`)."""
    id: str
    label: str
    options: tuple[Option, ...]
    #: 계획서 읽기의 열쇠(`reading_prefs.LABELS`) — 읽기가 이 칸을 채우면 이 칸은 묻지 않는다. 없으면 늘 묻는다
    reads: str | None = None

    def option_ids(self) -> tuple[str, ...]:
        return tuple(option.id for option in self.options)


@dataclass(frozen=True)
class Question:
    id: str                    # 화면이 아는 문항 번호
    slot: str                  # 구조화 값이 들어가는 자리(`to_survey` 가 안다)
    title: str
    why: str
    options: tuple[Option, ...]
    #: `single`(하나 고르기) · `priority`(분야를 순서대로 + 분야별 세부를 순서대로) · `pair`(칸마다 하나씩)
    kind: str = "single"
    groups: tuple[Group, ...] = ()
    allow_custom: bool = False
    custom_label: str | None = None
    #: 언제 정하나 — 1 = 접수 직후(읽기와 상관없음) · 2 = 이해 단계 결과가 나온 뒤(읽기가 채울 수 있는 칸)
    phase: int = 1
    #: 문항 통째로를 채우는 계획서 읽기 열쇠(`pace` ← `survey.pace`)
    reads: str | None = None

    def option_ids(self) -> tuple[str, ...]:
        return tuple(option.id for option in self.options)

    def value_of(self, option_id: str) -> str | None:
        return next((option.value for option in self.options if option.id == option_id), None)


def _opts(*pairs: tuple[str, str]) -> tuple[Option, ...]:
    return tuple(Option(code, label, code) for code, label in pairs)


_INDOOR = _opts(("indoor", "실내"), ("outdoor", "실외"), ("any", "상관없음"))

#: 묻는 문항 — 앞이 먼저 나간다. 문구 · 선택지는 시작 설문 화면(`features/onboarding/model.ts`)과 같다(활동 세부만 2026-10-19 관광 분류 코드).
#: ★렌트카(`car`)는 시작 설문처럼 선택지에 있지만 이동 계산기가 아직 못 다룬다(`mobility/wiring.SURVEY_MODES` — 계산기 기본 수단으로 간다)
QUESTIONS: tuple[Question, ...] = (
    Question("party", "party", "누구와 함께 떠나나요?", "함께 떠나는 사람을 하나 골라 주세요.",
             _opts(("alone", "혼자"), ("partner", "연인"), ("friends", "친구"), ("family", "가족")),
             allow_custom=True, custom_label="기타"),
    Question("priority", "priority_rank", "어떤 것을 더 중요하게 생각하나요?", "중요한 순서대로 분야와 세부 항목을 선택해 주세요.",
             _opts(("food", "음식"), ("activity", "활동"), ("mobility", "이동")), kind="priority",
             groups=(Group("food", "음식", _opts(("taste", "맛"), ("kindness", "친절"), ("clean", "청결"), ("michelin", "미쉐린"),
                                                 ("nopo", "노포")), reads="constraints.meal_preference"),
                     Group("activity", "활동", _opts(*ACTIVITY_DETAILS.items())),
                     Group("mobility", "이동", _opts(("public", "대중교통"), ("walk", "도보"), ("car", "렌트카"), ("taxi", "택시")),
                           reads="survey.priority_details.mobility"))),
    Question("indoor_outdoor", "indoor_outdoor", "실내와 실외 중 어디가 좋으세요?", "식당과 액티비티에서 각각 하나씩 골라 주세요.",
             _INDOOR, kind="pair", phase=2,
             groups=(Group("dining", "식당", _INDOOR), Group("activity", "액티비티", _INDOOR, reads="survey.indoor_outdoor.activity"))),
    Question("pace", "pace", "여행할 때 어느 정도 여유가 좋으세요?", "하루에 담을 일정의 양을 정할 때 쓰여요.",
             _opts(("relaxed", "여유롭게"), ("moderate", "적당히"), ("packed", "꽉 차게")), phase=2, reads="survey.pace"),
)

#: ★활동 팀이 채팅에서 다시 묻는 질문(대체할 곳을 무엇을 먼저 볼까) — **로딩 문항이 아니다.** 묶음 2의 로딩 문항을 그대로 옮겨 두었다.
#:  지난 답(`last_answer("priority")`)은 새 묶음의 우선순위 답에서 활동 · 이동 가운데 앞선 것을 이 선택지로 돌려준다
REPLACEMENT_QUESTION = Question("priority", "priority", "일정이 바뀔 때 대체할 곳은 무엇을 먼저 볼까요?", "계획서만으로는 알 수 없어요",
                                (Option("activity", "하고 싶은 활동이 비슷한 곳", "activity"), Option("mobility", "이동이 편한 곳", "mobility")))


def _by_id() -> dict[str, Question]:
    """지금 묶음의 문항 번호 표 — 부를 때마다 만든다(시험이 묶음을 바꿔 끼운다)."""
    return {question.id: question for question in QUESTIONS}


#: 묻지는 않지만 같은 입구가 받는 값 — 항로 지킴이 카드(`on_disruption`) · 옛 화면의 여행 테마(`theme` — 받아 두기만 한다, 설문 `theme` 칸으로)
DIRECT: dict[str, tuple[str, ...]] = {
    "on_disruption": ("replace", "ask_first"),
    "theme": ("food", "nature", "culture", "activity", "shopping", "local"),
}


def _encode(value: Mapping[str, Any]) -> str:
    """여러 칸 답의 저장 글 — 키를 정렬한 JSON. 같은 답은 늘 같은 글이다(멱등 재전송 · 이어받기 비교)."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _decode(text: Any) -> Any:
    try:
        return json.loads(text) if isinstance(text, str) and text.startswith("{") else None
    except ValueError:
        return None


def _unique_strings(value: Any, allowed: tuple[str, ...], what: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"{what}는 글자 목록이어야 한다")
    if len(set(value)) != len(value):
        raise ValueError(f"{what}에 같은 값이 두 번 있다")
    if any(v not in allowed for v in value):
        raise ValueError(f"{what}는 {', '.join(allowed)} 중에서 골라야 한다")
    return list(value)


def _priority_value(question: Question, value: Any) -> dict[str, Any]:
    """우선순위 답 `{areas: [분야, 순위대로], details: {분야: [세부, 순위대로]}}` 를 확인해 정리한 모양으로. 틀리면 ValueError(이유)."""
    if not isinstance(value, Mapping) or not set(value) <= {"areas", "details"} or "areas" not in value:
        raise ValueError("답은 {areas, details} 모양이어야 한다")
    areas = _unique_strings(value["areas"], question.option_ids(), "분야")
    if not areas:
        raise ValueError("분야를 하나 이상 골라야 한다")
    details = value.get("details") or {}
    if not isinstance(details, Mapping):
        raise ValueError("세부는 분야별 목록이어야 한다")
    groups = {group.id: group for group in question.groups}
    out: dict[str, list[str]] = {}
    for area, picked in details.items():
        if area not in areas:
            raise ValueError(f"고르지 않은 분야({area})의 세부다")
        chosen = _unique_strings(picked, groups[area].option_ids(), f"{groups[area].label} 세부")
        if chosen:
            out[area] = chosen
    return {"areas": areas, "details": out}


def _pair_value(question: Question, value: Any) -> dict[str, str]:
    """칸마다 하나 `{칸: 선택지}` — 한 칸 이상. 틀리면 ValueError(이유)."""
    groups = {group.id: group for group in question.groups}
    if not isinstance(value, Mapping) or not value or not set(value) <= set(groups):
        raise ValueError(f"답은 {', '.join(groups)} 칸에 하나씩이어야 한다")
    out: dict[str, str] = {}
    for group in question.groups:
        if group.id in value:
            picked = value[group.id]
            if not isinstance(picked, str) or picked not in group.option_ids():
                raise ValueError(f"{group.label} 칸은 {', '.join(group.option_ids())} 중 하나여야 한다")
            out[group.id] = picked
    return out


def _structured(question: Question, value: Any) -> dict[str, Any]:
    return _priority_value(question, value) if question.kind == "priority" else _pair_value(question, value)


class InvalidAnswers(ValueError):
    """모르는 문항 · 모르는 선택지. `problems` = `[{key, reason}]`."""

    def __init__(self, problems: list[dict[str, str]]) -> None:
        super().__init__("; ".join(f"{p['key']}: {p['reason']}" for p in problems))
        self.problems = problems


def check(answers: Mapping[str, Any]) -> dict[str, str | None]:
    """받은 답을 확인해 `{문항: 선택지 번호(여러 칸 답은 JSON 글)}` 로 돌려준다. 틀린 것이 하나라도 있으면 **전부 거절**한다(일부만 저장하지 않는다)."""
    problems: list[dict[str, str]] = []
    clean: dict[str, str | None] = {}
    known = _by_id()
    for key, value in answers.items():
        question = known.get(key)
        if question is None:
            allowed = DIRECT.get(key)
            if allowed is None:
                problems.append({"key": str(key), "reason": "모르는 문항이다"})
            elif not isinstance(value, str) or value not in allowed:
                problems.append({"key": str(key), "reason": f"선택지는 {', '.join(allowed)} 중 하나여야 한다"})
            else:
                clean[key] = value
        elif value is None:
            clean[key] = None
        elif question.kind != "single":
            try:
                clean[key] = _encode(_structured(question, value))
            except ValueError as exc:
                problems.append({"key": key, "reason": str(exc)})
        elif isinstance(value, dict) and set(value) == {"custom"} and question.allow_custom:
            raw = value["custom"]
            if not isinstance(raw, str) or not raw.strip() or len(raw) > MAX_CUSTOM_LENGTH:
                problems.append({"key": key, "reason": f"직접 입력은 1~{MAX_CUSTOM_LENGTH}자로 적어 주세요"})
            else:
                clean[key] = CUSTOM_PREFIX + raw.strip()
        elif not isinstance(value, str) or value not in question.option_ids():
            problems.append({"key": key, "reason": f"선택지는 {', '.join(question.option_ids())} 중 하나여야 한다"})
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


def last_answer(conn, *, tenant_id: str, customer_id: UUID, question_id: str) -> dict[str, str] | None:
    """같은 고객이 이 문항에 마지막으로 고른 답 `{option_id, value, label}`. 없거나 뜻이 바뀐 답이면 `None`. `[2026-10-14]`

    ★`inherit` 과 같은 조건이다 — 지금 질문 묶음 버전이고, 지금 매핑으로 읽어도 저장 때 해석과 같은 답만. 직접 쓴 답(`custom:`)은
      선택지가 아니라 「미리 골라 둘」 수 없으므로 뺀다. 활동 팀이 여행을 못 찾은 예약에서 질문을 다시 물을 때 지난 답을 알려 준다
      (활동 → 코어 전달 8번 회신 `wiki/records/reports/2026-10-13_활동_전달8_설문전달_회신.md`).
    ★`[2026-10-19]` `priority` 는 대체할 곳 질문(`REPLACEMENT_QUESTION`)의 선택지로 돌려준다 — 우선순위 답에서 활동 · 이동 가운데 **앞선 것**.
      둘 다 고르지 않았으면 `None`. 다른 여러 칸 문항은 하나로 「미리 골라 둘」 수 없어 `None`.
    """
    question = _by_id().get(question_id)
    if question is None:
        return None
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT a.option_id, a.slot, a.value, a.bundle_version FROM trip_intake_survey_answers a "
                        "JOIN trip_intakes i ON i.intake_id=a.intake_id AND i.tenant_id=a.tenant_id "
                        "WHERE a.tenant_id=%s AND i.customer_id=%s AND a.question_id=%s ORDER BY a.seq DESC LIMIT 1",
                        (tenant_id, customer_id, question_id))
            row = cur.fetchone()
    except Exception:                                                  # noqa: BLE001
        log.warning("intake survey answer history unreadable customer=%s (migration 053?)", customer_id, exc_info=True)
        return None
    if row is None:
        return None
    option_id, slot, value, version = row
    if version != QUESTION_SET_VERSION or option_id.startswith(CUSTOM_PREFIX) or resolve(question_id, option_id) != (slot, value):
        return None
    if question.kind == "priority" and question_id == REPLACEMENT_QUESTION.id:
        areas = (_decode(option_id) or {}).get("areas") or []
        first = next((area for area in areas if area in REPLACEMENT_QUESTION.option_ids()), None)
        option = next((o for o in REPLACEMENT_QUESTION.options if o.id == first), None)
        return {"option_id": option.id, "value": option.value, "label": option.label} if option else None
    if question.kind != "single":
        return None
    label = next((o.label for o in question.options if o.id == option_id), None)
    return {"option_id": option_id, "value": value, "label": label} if label else None


def _shown_answer(question: Question, answer: str | None) -> dict[str, Any]:
    """화면에 내려 줄 지금 답 — 하나 고르기는 선택지 id · 직접 쓴 글, 여러 칸은 정리한 모양."""
    if question.kind != "single":
        return {"answer": _decode(answer)}
    custom = isinstance(answer, str) and answer.startswith(CUSTOM_PREFIX)
    return {"answer": None if custom else answer, "custom_answer": answer[len(CUSTOM_PREFIX):] if custom else None}


def questions(answers: Mapping[str, str], plan: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """`GET /v1/web/trip-intakes/{id}` 의 `questions[]`. 이미 답한 문항도 **그대로 둔다**(`answer` 에 고른 번호) — 화면이 새로 고쳐져도 앞 질문으로 돌아가 고칠 수 있게.

    `plan` = 이 접수에서 정한 목록(`loading_questions`) — 물을 문항 번호(`asked`)와 읽은 칸(`skipped_by_reading`). 없으면 네 문항 모두(읽은 칸 없음).
    ★목록은 `plan.asked` 순서 그대로다 — 둘째에 정한 문항은 뒤에 붙으므로 화면의 앞 번호가 흔들리지 않는다."""
    known = _by_id()
    asked = list((plan or {}).get("asked") or [q.id for q in QUESTIONS])
    read = {(entry["question"], entry["part"]): entry for entry in (plan or {}).get("skipped_by_reading") or [] if entry.get("part")}
    out = []
    for question_id in asked:
        q = known.get(question_id)
        if q is None:                                                  # 묶음이 바뀌어 모르는 번호 — 그리지 않는다(경고)
            log.warning("loading question plan names an unknown question=%s", question_id)
            continue
        shown: dict[str, Any] = {"id": q.id, "kind": q.kind, "title": q.title, "why": q.why,
                                 "options": [{"id": option.id, "label": option.label} for option in q.options]}
        if q.kind == "single":
            shown.update({"allow_custom": q.allow_custom, "custom_max_length": MAX_CUSTOM_LENGTH, "custom_label": q.custom_label})
        else:
            parts = [{"id": group.id, "label": group.label, "options": [{"id": o.id, "label": o.label} for o in group.options],
                      "read": _read_mark(read.get((q.id, group.id)))} for group in q.groups]
            if q.kind == "pair":
                shown.pop("options")
            shown["groups" if q.kind == "priority" else "parts"] = parts
        shown.update(_shown_answer(q, answers.get(q.id)))
        out.append(shown)
    return out


def _read_mark(entry: Mapping[str, Any] | None) -> dict[str, Any] | None:
    return None if entry is None else {k: entry.get(k) for k in ("key", "value", "text", "quotes")}


# ── 이 접수에서 물을 목록 — 두 번에 정한다 ───────────────────────────────

def _skip(question: str, part: str | None, found: Mapping[str, Any]) -> dict[str, Any]:
    """읽은 칸 한 줄 — 문항 id · 칸 · 읽기 열쇠 · 읽은 값 · 고객 말 · 원문 조각."""
    return {"question": question, "part": part, "key": found["key"], "value": found["value"],
            "text": reading_prefs.value_text(found["key"], found["value"]), "quotes": list(found.get("quotes") or [])}


def first_plan(answered: Iterable[str]) -> dict[str, Any]:
    """접수 직후 — 읽기와 상관없는 문항(`phase=1`) 중 아직 답이 없는 것."""
    done = set(answered)
    return {"version": QUESTION_SET_VERSION, "phase": 1, "skipped_by_reading": [],
            "asked": [q.id for q in QUESTIONS if q.phase == 1 and q.id not in done]}


def second_plan(plan: Mapping[str, Any], answered: Iterable[str], found: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """이해 단계 결과가 나온 뒤 — 읽은 칸을 표시하고 `phase=2` 문항 중 비어 있는 것을 **뒤에 붙인다.** 이미 정한 문항은 그대로 둔다.

    `found` = 계획서 읽기 결과(`reading_prefs.proposals`). 문항 통째로를 채웠으면(`reads`) 넣지 않고, 칸을 채웠으면 그 칸만 읽은 칸이 된다.
    칸이 모두 읽혔으면(`pair`) 문항도 넣지 않는다. 우선순위는 세부를 모두 읽어도 **분야 순서를 묻는다.**"""
    done = set(answered)
    by_key = {item["key"]: item for item in found}
    asked = list(plan.get("asked") or [])
    skipped: list[dict[str, Any]] = []
    for q in QUESTIONS:
        if q.id in done and q.id not in asked:
            continue                                                    # 이미 답했다 — 묻지도, 읽은 칸으로 적지도 않는다
        if q.reads and q.reads in by_key:
            if q.id not in asked:
                skipped.append(_skip(q.id, None, by_key[q.reads]))
            continue
        parts = [_skip(q.id, group.id, by_key[group.reads]) for group in q.groups if group.reads and group.reads in by_key]
        if q.kind == "pair" and q.groups and len(parts) == len(q.groups) and q.id not in asked:
            skipped.append({**parts[0], "part": None})
            continue
        if q.id in asked or (q.phase == 2 and q.id not in done):
            skipped.extend(parts)
            if q.id not in asked:
                asked.append(q.id)
    return {"version": QUESTION_SET_VERSION, "phase": 2, "asked": asked, "skipped_by_reading": skipped}


def _load_plan(conn, *, tenant_id: str, intake_id: UUID) -> tuple[dict[str, Any] | None, bool]:
    """저장해 둔 목록과 저장할 수 있는가. ★마이그레이션 907 이 안 올라간 DB — 저장 없이 그때그때 계산한다(경고)."""
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT survey_plan FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s", (tenant_id, intake_id))
            row = cur.fetchone()
    except Exception:                                                  # noqa: BLE001
        log.warning("loading question plan unreadable intake=%s (migration 907?)", intake_id, exc_info=True)
        return None, False
    plan = row[0] if row else None
    if isinstance(plan, dict) and plan.get("version") == QUESTION_SET_VERSION:
        return plan, True
    return None, True                                                   # 처음이거나 묶음이 바뀐 옛 목록 — 새로 정한다


def _store_plan(conn, *, tenant_id: str, intake_id: UUID, plan: dict[str, Any]) -> dict[str, Any]:
    """목록을 저장한다 — 이미 같은 묶음 · 같은 단계 이상으로 저장돼 있으면(다른 조회가 먼저 정했다) 그것을 돌려준다."""
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET survey_plan=%s::jsonb WHERE tenant_id=%s AND intake_id=%s "
                    "AND (survey_plan IS NULL OR survey_plan->>'version' IS DISTINCT FROM %s "
                    "OR COALESCE((survey_plan->>'phase')::int, 0) < %s) RETURNING survey_plan",
                    (json.dumps(plan, ensure_ascii=False), tenant_id, intake_id, QUESTION_SET_VERSION, plan["phase"]))
        if cur.fetchone() is not None:
            return plan
        cur.execute("SELECT survey_plan FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s", (tenant_id, intake_id))
        row = cur.fetchone()
    return row[0] if row and isinstance(row[0], dict) else plan


def loading_questions(conn, *, tenant_id: str, intake_id: UUID, reading_done: bool,
                      found: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """접수 조회의 `questions[]` · `skipped_by_reading[]` · `questions_phase`. `[2026-10-19]`

    `reading_done` — 이해 단계 결과가 원본마다 다 나왔거나 읽기가 끝났다(확인 화면 · 실패). 그때 한 번 둘째 목록을 정한다.
    `found` — 계획서 읽기 결과(`reading_prefs.carry` — 이해 에이전트를 실제로 쓴 결과만. 그림자 · 실패면 비어 있어 다 묻는다)."""
    answers = stored(conn, tenant_id=tenant_id, intake_id=intake_id)
    plan, keep = _load_plan(conn, tenant_id=tenant_id, intake_id=intake_id)
    if plan is None:
        plan = first_plan(answers)
        if keep:
            plan = _store_plan(conn, tenant_id=tenant_id, intake_id=intake_id, plan=plan)
    if int(plan.get("phase") or 1) < 2 and reading_done:
        plan = second_plan(plan, answers, list(found))
        if keep:
            plan = _store_plan(conn, tenant_id=tenant_id, intake_id=intake_id, plan=plan)
    return {"questions": questions(answers, plan), "skipped_by_reading": list(plan.get("skipped_by_reading") or []),
            "phase": int(plan.get("phase") or 1)}


def save(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID, answers: Mapping[str, str | None]) -> list[str] | None:
    """답을 모은다(같은 문항은 덮어쓴다). 돌려주는 값 = 지금까지 답한 **모든** 문항 번호(정렬). 남의 접수 · 없는 접수면 None.

    ★한 트랜잭션 — 호출자가 `with conn.transaction():` 으로 감싼다. 접수 행을 잠근다(`FOR UPDATE`) — 탭 둘이 동시에 다른 문항을 저장해도 서로를 덮지 않는다.
    ★`updated_at` 은 안 건드린다(마이그레이션 051 설명). 이미 등록된 접수(`confirmed`)는 `IntakeClosed` — 답이 여행에 닿지 못한다."""
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


def _label_of(question: Question | None, option_id: str) -> str | None:
    """이력에 남길 그때 화면의 글 — 직접 쓴 답은 그 글, 여러 칸 답은 「음식 > 활동 / 음식: 맛 · 청결」 같은 한 줄."""
    if option_id.startswith(CUSTOM_PREFIX):
        return option_id[len(CUSTOM_PREFIX):]
    if question is None:
        return None
    if question.kind == "single":
        return next((o.label for o in question.options if o.id == option_id), None)
    value = _decode(option_id) or {}
    groups = {group.id: group for group in question.groups}

    def word(options: Iterable[Option], code: str) -> str:
        return next((o.label for o in options if o.id == code), code)

    if question.kind == "priority":
        head = " > ".join(word(question.options, area) for area in value.get("areas") or [])
        tails = [f"{groups[a].label}: {' · '.join(word(groups[a].options, c) for c in codes)}"
                 for a, codes in (value.get("details") or {}).items() if a in groups]
        return " / ".join([head, *tails])
    return " / ".join(f"{groups[k].label}: {word(groups[k].options, v)}" for k, v in value.items() if k in groups)


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
        label = None if option_id == CLEARED_ANSWER else _label_of(question, option_id)
        cur.execute("INSERT INTO trip_intake_survey_answers (tenant_id, intake_id, question_id, option_id, slot, value, question_text, option_label, bundle_version) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (tenant_id, intake_id, key, option_id, slot, value, question.title if question else None, label, QUESTION_SET_VERSION))


def resolve(key: str, option_id: str) -> tuple[str, str] | None:
    """지금 묶음에서 이 답이 **어느 슬롯의 어떤 값**인가 — `(슬롯, 값)`. 모르면 None. 직접 값(`on_disruption`)은 이름이 슬롯이고 값은 그대로다.
    여러 칸 답은 저장 글(JSON)을 다시 확인해 정리한 글이 값이다 — 모양이 틀리면(옛 묶음의 단일 답 등) None(새 매핑으로 잘못 읽지 않는다)."""
    question = _by_id().get(key)
    if question is not None:
        if question.kind != "single":
            try:
                return question.slot, _encode(_structured(question, _decode(option_id)))
            except ValueError:
                return None
        if option_id.startswith(CUSTOM_PREFIX) and option_id[len(CUSTOM_PREFIX):].strip():
            return (question.slot, option_id) if question.allow_custom else None
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


#: 직접 쓴 답에서 알아보는 말 — 구분된 낱말만 계산용 코드로 옮긴다(원문은 `custom_answers` 에 그대로)
_CUSTOM_WORDS = {
    "preferred_mobility": {"택시": "taxi", "taxi": "taxi", "버스": "bus", "bus": "bus", "지하철": "subway", "subway": "subway",
                           "대중교통": "public", "public": "public", "도보": "walk", "걷기": "walk", "walk": "walk"},
    "priority": {"활동": "activity", "activity": "activity", "이동": "mobility", "mobility": "mobility",
                 "음식": "food", "식사": "food", "food": "food"},
}


def _place(survey: dict[str, Any], slot: str, value: str) -> None:
    """슬롯의 값을 설문(`TripSurvey`)의 자리에 둔다 — 슬롯이 어디로 가는지는 여기 한 곳이다.

    ★옛 묶음 2의 슬롯(`preferred_mobility` · 단일 `priority`)도 읽는다 — 이력에 남은 옛 답을 그때의 뜻으로 등록하기 위해서다."""
    if value.startswith(CUSTOM_PREFIX):
        raw = value[len(CUSTOM_PREFIX):]
        survey.setdefault("custom_answers", {})[slot] = raw
        if slot in ("theme", "party"):                                   # 받기만 하는 자유 글 칸 — 고객이 쓴 그대로(시작 설문의 「기타」와 같다)
            survey[slot] = raw
            return
        # 원문을 보존하고 구분된 기존 단어만 계산용 코드에 대응시킨다.
        tokens = re.split(r"[+/,、·&\s]+", raw.lower())
        aliases = _CUSTOM_WORDS.get(slot) or {}
        codes = list(dict.fromkeys(aliases[token] for token in tokens if token in aliases))
        if codes and slot == "preferred_mobility":
            survey.setdefault("priority_details", {})["mobility"] = codes
        elif codes and slot == "priority":
            survey["priority"] = codes
        return
    if slot == "preferred_mobility":                                     # 묶음 2
        survey.setdefault("priority_details", {})["mobility"] = [value]
    elif slot == "priority":                                             # 묶음 2 — 대체할 곳 하나
        survey["priority"] = [value]
    elif slot == "priority_rank":
        ranked = _decode(value) or {}
        survey["priority"] = list(ranked.get("areas") or [])
        details = {area: list(codes) for area, codes in (ranked.get("details") or {}).items() if codes}
        if details:
            survey.setdefault("priority_details", {}).update(details)
    elif slot == "indoor_outdoor":
        survey["indoor_outdoor"] = dict(_decode(value) or {})
    elif slot in ("theme", "party", "pace", "on_disruption"):
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


__all__ = ["DIRECT", "Group", "IntakeClosed", "InvalidAnswers", "Option", "QUESTIONS", "QUESTION_SET_VERSION", "Question",
           "REPLACEMENT_QUESTION", "check", "first_plan", "last_answer", "loading_questions", "merged_survey", "questions", "resolve",
           "save", "second_plan", "stored", "stored_resolved", "to_survey"]

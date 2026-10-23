# -*- coding: utf-8 -*-
"""**해석 확인 질문** — 읽기 AI 와 규칙이 같은 줄을 다르게 읽었을 때 AI 의 읽기를 1안(추천)으로 두고 고객에게 고르게 한다. `[2026-10-20 사용자 지시]`

사용자: 「13시 정도」는 시간의 뜻 · 실제 식당 「정도」 · 「정돈」 오타가 모두 가능하다 — AI 가 최선의 안 하나를 내고, 코드는 규칙으로 덮지 말고
AI 가 잘 했는지 검사만 한다. 확인 화면은 로딩 중 확인이 필요한 곳에서 멈추고 AI 가 판단한 안들을 보이되 가장 유력한 1안을 맨 위에 둔다.
서버는 그동안 1안으로 계속 계산하고, 다른 안을 고르면 그 지점부터 다시 계산한다(첫 기다림 안이면 기다림이 늘지 않는다).

    읽기(`pipeline._agent_rows`)  규칙이 시각을 읽은 줄을 AI 가 일정이 아니라 빈 시간 · 추천 요청 · 질문 · 잡담으로 읽었다
                                  →  규칙의 일정은 **뺀 채로**(`items[n].removed`, 방법 `llm_agent`) 남기고 질문 한 줄(`reading.question:{id}`)
                                  ☆전에는 그 줄을 「AI 가 빠뜨린 줄」로 보고 규칙 일정을 그대로 넣었다 — 「오후 13시~16시 정도」가 장소 「정도」 →
                                    오타 고침 「정돈 대학로본점」이 됐다(2026-10-19 오라클 ARM 접수)
    조회 · 진행 이벤트            `interpretations[]` · `interpretation` 이벤트 — 선택지는 그때의 값 줄(뺐나 · 찾은 장소)로 만든다
    답(`POST …/interpretations`)  로딩 중이면 저장만(`reading.answer:{id}`, 방법 `customer`) → 읽기 끝(첫 검사 직후, 아직 첫 기다림)에 `apply_pending`
                                  로딩 뒤면 그 자리에서 새 판(`pipeline.edit` — 뺀 일정을 되살리거나 뺀다) · 1안을 고르면 판을 만들지 않는다

★서버는 뜻을 판단하지 않는다 — 1안은 AI 의 읽기이고, 선택지는 이미 읽은 값(AI 인용 · 규칙 일정 · 그 일정에서 찾은 장소)뿐이다. 장소 이름을 지어내지 않는다.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable
from uuid import UUID

QUESTION_FIELD = "reading.question:"
ANSWER_FIELD = "reading.answer:"
#: AI 가 일정이 아닌 것으로 읽은 조각 — 이 조각이 덮는 줄에서 규칙이 일정을 읽었으면 묻는다
CONTEST_PIECES = ("plan_ask", "question", "chitchat")
#: 줄 하나가 조각에 든다고 볼 최소 글자 수(공백 뺀) — 「숙소」 같은 짧은 줄이 긴 인용에 우연히 들어가는 것을 막는다(우리가 고른 값)
MIN_LINE_CHARS = 4

_READING_LABEL = {"free_slot": "빈 시간", "meal_place": "식당을 추천받을 끼니", "activity_place": "추천받을 활동 시간",
                  "plan_ask": "추천 요청", "question": "질문", "chitchat": "일정이 아닌 말"}


class InvalidAnswers(ValueError):
    def __init__(self, problems: list[dict[str, str]]) -> None:
        super().__init__("invalid_answers")
        self.problems = problems


def _flat(text: str | None) -> str:
    return re.sub(r"\s+", "", text or "")


def contested_lines(lines: list[str], out: Any) -> dict[int, dict[str, Any]]:
    """AI 가 일정이 아닌 것(빈칸 · 추천 요청 · 질문 · 잡담)으로 읽은 줄 → {줄 번호: AI 의 읽기}. 인용이 여러 줄을 이으면(「…정도 약 3시간…」) 그 줄 모두.
    ★여기서는 줄만 고른다 — 그 줄에 규칙 일정이 있을 때만 질문이 된다(`_agent_rows`)."""
    readings: list[dict[str, Any]] = []
    for gap in getattr(out, "gaps", None) or []:
        readings.append({"kind": gap.get("kind"), "quote": gap.get("quote"), "day": gap.get("day"),
                         "start": gap.get("start"), "end": gap.get("end")})
    for piece in getattr(out, "pieces", None) or []:
        if piece.get("kind") in CONTEST_PIECES:
            readings.append({"kind": piece["kind"], "quote": piece.get("quote"), "day": None, "start": None, "end": None})
    found: dict[int, dict[str, Any]] = {}
    for reading in readings:
        quote = _flat(reading.get("quote"))
        if not quote:
            continue
        for number, line in enumerate(lines, start=1):
            flat = _flat(line)
            if len(flat) >= MIN_LINE_CHARS and (flat in quote or quote in flat):
                found.setdefault(number, reading)                 # 빈칸이 조각보다 앞에 들어간다 — 더 구체적인 읽기가 이긴다
    return found


def question_rows(*, index: int, position: int, line: int, line_text: str, reading: dict[str, Any],
                  rule_title: str | None, rule_start: str | None) -> list[dict[str, Any]]:
    """규칙 일정을 **뺀 채로** 두는 값 줄 + 질문 값 줄. 방법은 `llm_agent` — 빼는 근거가 AI 의 읽기다."""
    qid = f"q-{position}-{line}"
    label = _READING_LABEL.get(str(reading.get("kind")), "일정이 아닌 말")
    question = {"id": qid, "index": index, "line": line, "quote": line_text.strip(),
                "reading": {k: reading.get(k) for k in ("kind", "quote", "day", "start", "end")},
                "rule": {"title": rule_title, "starts_at": rule_start}}
    return [
        {"field": f"items[{index}].removed", "value": True, "method": "llm_agent",
         "evidence": {"source": "model", "line": line, "reading": question["reading"], "question": qid},
         "needs_review": False,
         "note": f"읽기 AI 는 이 줄을 「{label}」으로 읽었어요 — 일정에서 뺐어요(다른 뜻이면 확인 질문에서 고를 수 있어요)"},
        {"field": QUESTION_FIELD + qid, "value": question, "method": "llm_agent",
         "evidence": {"source": "model", "line": line}, "needs_review": False,
         "note": "읽기 AI 와 규칙이 이 줄을 다르게 읽었다 — AI 의 읽기를 1안으로 두고 묻는다"},
    ]


# ── 화면 모양 ──────────────────────────────────────────────────────
def _item_fields(claims: list[dict[str, Any]], source_id: Any, index: int) -> dict[str, dict[str, Any]]:
    prefix = f"items[{index}]."
    return {c["field"][len(prefix):]: c for c in claims if str(c["source_id"]) == str(source_id) and c["field"].startswith(prefix)}


def _clock(value: Any) -> str | None:
    text = str(value or "")
    match = re.search(r"(\d{1,2}):(\d{2})", text)
    return f"{int(match.group(1)):02d}:{match.group(2)}" if match else None


def options_of(question: dict[str, Any], fields: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """선택지 — 1안은 AI 의 읽기(추천), 그다음 규칙 일정(찾은 장소로), 찾은 이름이 원문과 다르면 「이름 그대로 찾기」."""
    from .places import normalize_full

    reading = question.get("reading") or {}
    kind = str(reading.get("kind"))
    label = _READING_LABEL.get(kind, "일정이 아닌 말")
    start, end = _clock(reading.get("start")), _clock(reading.get("end"))
    span = f"{start}~{end} " if start and end else ""
    if kind == "free_slot":
        first_label, effect = f"{span}빈 시간", f"일정에 넣지 않고 {span}빈 시간으로 둬요"
    elif kind in ("meal_place", "activity_place"):
        first_label, effect = f"{span}{label}", "일정에 넣지 않고 추천으로 채울 자리로 둬요"
    else:
        first_label, effect = label, "일정에 넣지 않아요"
    out = [{"id": "reading", "label": first_label.strip(), "recommended": True, "action": None, "query": None,
            "reason": f"읽기 AI 가 「{reading.get('quote') or question.get('quote')}」를 {label}으로 읽었어요", "effect": effect}]
    rule = question.get("rule") or {}
    title = (fields.get("title") or {}).get("value") or rule.get("title") or ""
    clock = _clock((fields.get("starts_at") or {}).get("value")) or _clock(rule.get("starts_at"))
    at = f"{clock} " if clock else ""
    place_claim = fields.get("place") or {}
    place = place_claim.get("value") if isinstance(place_claim.get("value"), dict) else None
    how = (place_claim.get("evidence") or {}).get("method")
    if place and place.get("name"):
        typo = how == "typo"
        out.append({"id": "item", "label": f"「{place['name']}」 {at}일정" + (f"(「{title}」을 오타로 볼 때)" if typo else ""),
                    "recommended": False, "action": None, "query": None, "reason": None,
                    "effect": f"{at}일정으로 넣고 영업시간 · 이동을 확인해요".strip()})
        if title and normalize_full(place["name"]) != normalize_full(title):
            out.append({"id": "item_search", "label": f"「{title}」 이름 그대로 찾기", "recommended": False,
                        "action": "pick_myself", "query": title, "reason": None,
                        "effect": f"{at}일정으로 넣고 「{title}」을 장소 검색에서 직접 골라요".strip()})
    else:
        out.append({"id": "item", "label": f"「{title}」 {at}일정".strip(), "recommended": False, "action": "pick_myself",
                    "query": title or None, "reason": None, "effect": "일정으로 넣고 장소는 직접 골라요"})
    return out


def view(raw_claims: list[dict[str, Any]], positions: dict[str, int]) -> list[dict[str, Any]]:
    """`GET …/{id}` 의 `interpretations[]` · 진행 이벤트 `interpretation` 의 몸통(같은 모양). 질문 순서는 원본 · 줄 순."""
    from .assemble import effective

    claims = effective(raw_claims)
    answers = {c["field"][len(ANSWER_FIELD):]: c["value"] for c in claims if c["field"].startswith(ANSWER_FIELD)}
    out = []
    for claim in claims:
        if not claim["field"].startswith(QUESTION_FIELD) or not isinstance(claim.get("value"), dict):
            continue
        question = claim["value"]
        sid = str(claim["source_id"])
        fields = _item_fields(claims, sid, int(question["index"]))
        removed = (fields.get("removed") or {}).get("value") is True
        options = options_of(question, fields)
        answer = answers.get(question["id"])
        applied = "reading" if removed else (answer if answer in ("item", "item_search") else "item")
        out.append({"id": question["id"], "kind": "interpretation",
                    "question": f"계획서의 「{question.get('quote')}」를 어떻게 이해할까요?",
                    "quote": question.get("quote"), "line": question.get("line"),
                    "item": f"{positions.get(sid, 0)}-{question['index']}", "source_id": sid, "index": question["index"],
                    "options": options, "answer": answer, "applied": applied, "actions": ["pick_myself"]})
    out.sort(key=lambda q: (positions.get(q["source_id"], 0), q["line"] or 0))
    return out


# ── 답 ────────────────────────────────────────────────────────────
def check(answers: Any, questions: list[dict[str, Any]]) -> dict[str, str]:
    """`{질문 id: 선택지 id}` — 모르는 질문 · 선택지는 하나라도 있으면 전부 거절."""
    if not isinstance(answers, dict) or not answers:
        raise InvalidAnswers([{"key": "answers", "reason": "empty"}])
    known = {q["id"]: {o["id"] for o in q["options"]} for q in questions}
    problems = []
    for key, value in answers.items():
        if key not in known:
            problems.append({"key": str(key), "reason": "unknown_question"})
        elif not isinstance(value, str) or value not in known[key]:
            problems.append({"key": str(key), "reason": "unknown_option"})
    if problems:
        raise InvalidAnswers(problems)
    return {str(k): str(v) for k, v in answers.items()}


def edits_for(answers: dict[str, str], questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """답 → 지금 판과 다른 것만 `items[n].removed` 고치기. 1안(AI 의 읽기) = 뺀 채로 · 규칙 일정 = 되살리기."""
    by_id = {q["id"]: q for q in questions}
    edits = []
    for qid, option in answers.items():
        question = by_id[qid]
        want_removed = option == "reading"
        if want_removed != (question["applied"] == "reading"):
            edits.append({"source_id": question["source_id"], "field": f"items[{question['index']}].removed", "value": want_removed})
    return edits


def _insert_answers(cur, *, tenant_id: str, intake_id: UUID, revision: int, answers: dict[str, str],
                    questions: list[dict[str, Any]]) -> None:
    by_id = {q["id"]: q for q in questions}
    for qid, option in answers.items():
        cur.execute("INSERT INTO intake_claims (intake_id, tenant_id, revision, source_id, field, value_json, method, evidence, "
                    "needs_review, note, created_at) VALUES (%s,%s,%s,%s,%s,%s,'customer',%s,false,%s, clock_timestamp())",
                    (intake_id, tenant_id, revision, by_id[qid]["source_id"], ANSWER_FIELD + qid, json.dumps(option),
                     json.dumps({"source": "customer", "question": qid}), "고객이 고른 해석"))


def _questions_at(conn, tenant_id: str, intake_id: UUID, revision: int) -> list[dict[str, Any]]:
    from .pipeline import _claims, _sources

    positions = {str(s["source_id"]): int(s["position"]) for s in _sources(conn, tenant_id, intake_id)}
    return view(_claims(conn, tenant_id, intake_id, revision), positions)


def loading(status: str, stage: str) -> bool:
    """아직 첫 기다림 안인가 — 읽는 중이거나 검사 · 먼저 채우기 중(고객에게는 「읽는 중」)."""
    return status == "reading" or (status == "review" and stage == "checking")


def answer(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID, revision: int, answers: Any,
           tour: Any = None, kakao: Any = None, dining: Any = None,
           on_stage: Callable[[str], None] | None = None) -> dict[str, Any]:
    """답을 저장하고 · 로딩 뒤면 그 자리에서 반영한다. 돌려주는 값 = `{applied, pending, revision}`.

    ★접수 행을 잠근 채 상태를 본다 — 읽기 일꾼이 「검사 끝」으로 바꾸는 순간과 겹쳐도 답이 빠지지 않는다(일꾼은 상태를 바꾼 뒤 한 번 더 `apply_pending`)."""
    from .pipeline import IntakeConflict, edit

    say = on_stage or (lambda name: None)
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT status, stage, revision FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s AND customer_id=%s FOR UPDATE",
                    (tenant_id, intake_id, customer_id))
        row = cur.fetchone()
        if row is None:
            raise LookupError("intake")
        status, stage, current = row
        if status not in ("reading", "review"):
            raise IntakeConflict("intake_not_editable", f"지금은 고를 수 없습니다(상태 {status})", status=status)
        if revision != current:
            raise IntakeConflict("stale_revision", "그 사이 다른 화면에서 고쳤습니다 — 새로 불러와 주세요", current_revision=current)
        questions = _questions_at(conn, tenant_id, intake_id, current)
        picked = check(answers, questions)
        changes = edits_for(picked, questions)
        if loading(status, stage) or not changes:
            _insert_answers(cur, tenant_id=tenant_id, intake_id=intake_id, revision=current, answers=picked, questions=questions)
            return {"applied": not changes, "pending": bool(changes), "revision": current}
        say("applying")
        new = edit(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=current, edits=changes,
                   tour=tour, kakao=kakao, dining=dining, via="interpretation", learn_aliases=False)
        _insert_answers(cur, tenant_id=tenant_id, intake_id=intake_id, revision=new, answers=picked, questions=questions)
        return {"applied": True, "pending": False, "revision": new}


def apply_pending(conn, *, tenant_id: str, intake_id: UUID, tour: Any = None, kakao: Any = None, dining: Any = None) -> int | None:
    """로딩 중에 저장만 해 둔 답을 반영한다(읽기 일꾼이 첫 검사 · 먼저 채우기 뒤에 부른다). 바꿀 것이 없으면 None, 있으면 새 판 번호."""
    from .pipeline import edit

    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT status, revision, customer_id FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s FOR UPDATE",
                    (tenant_id, intake_id))
        row = cur.fetchone()
        if row is None or row[0] != "review":
            return None
        _status, current, customer_id = row
        questions = _questions_at(conn, tenant_id, intake_id, current)
        answers = {q["id"]: q["answer"] for q in questions if q.get("answer")}
        changes = edits_for(answers, questions) if answers else []
        if not changes:
            return None
        return edit(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=current, edits=changes,
                    tour=tour, kakao=kakao, dining=dining, via="interpretation", learn_aliases=False)


__all__ = ["ANSWER_FIELD", "QUESTION_FIELD", "InvalidAnswers", "answer", "apply_pending", "check", "contested_lines",
           "edits_for", "loading", "options_of", "question_rows", "view"]

# -*- coding: utf-8 -*-
"""정답 조건 문장 → 규칙 언어(`conditions.py`) 옮기기 — **규칙으로 옮길 수 있는 것만** 여기서 옮긴다. `[2026-10-19]`

옮기는 순서:
  1. 이 파일의 규칙(정규식) — 결정적이라 같은 문장은 늘 같은 조건이 된다.
  2. 남은 문장은 모델이 옮긴 파일(`compile_model.py` 가 만든 `compiled_*.jsonl`)을 읽는다. 작성 모델 · 시각을 기록한다.
  3. 둘 다 없으면 `{"op": "manual"}` = 판정 불가(사람 검수 대상).

금지 목록은 「하면 안 되는 일」이다. 채점은 **지켜야 할 조건**(위반이 아니면 통과)으로 옮겨 적는다 —
  「요청 안 한 일정 변경 금지」 → 요청 대상(`targets`)을 뺀 나머지 항목이 그대로(`unchanged_except`).
"""
from __future__ import annotations

import re
from typing import Any

from .patterns import norm

_SEQS = r"seq\s*=\s*(\d+(?:\s*,\s*\d+)*)"
_HM = r"([0-2]?\d:[0-5]\d)"

NO_CHANGE_RE = re.compile(r"^(일정 변경 없음|items\s*==\s*start_state\.items|일정 변경 금지|일정 저장 호출 0회|저장 호출 0회)")
SAVES_RE = re.compile(r"^(?:일정 )?저장 호출\s*(\d+)\s*회")
COUNT_RE = re.compile(r"^항목 수\s*=?\s*(\d+)\s*개?$")
KIND_RE = re.compile(r"^seq\s*=\s*(\d+)\s*\.\s*kind\s*=\s*(activity|dining|lodging|mobility)\s*$")
INDOOR_RE = re.compile(r"^seq\s*=\s*(\d+)\s*\.\s*indoor\s*=\s*(true|false)\s*$")
PLACE_NE_RE = re.compile(r"^seq\s*=\s*(\d+)\s*\.\s*place\s*!=\s*(.+?)\s*$")
TIME_RE = re.compile(rf"^seq\s*=\s*(\d+)\s*(?:시작\s*{_HM}\s*,\s*종료\s*{_HM}|s\s*=\s*{_HM}\s*,\s*e\s*=\s*{_HM}|시간\s*{_HM}\s*~\s*{_HM}\s*유지)\s*$")
ABSENT_SEQ_RE = re.compile(rf"^{_SEQS}\s*(?:항목)?\s*없음$")
SAME_RE = re.compile(rf"^{_SEQS}\s*(?:의 모든 필드|전체)?\s*그대로$")
ANSWER_RE = re.compile(r"^답에\s+(\S{1,20})\s+포함$")
PINNED_RE = re.compile(r"^(고객이 고정한 항목 변경 금지|잠금 항목 변경 금지|고정 항목 변경 금지)")
FALSE_DONE_RE = re.compile(r"^(저장된 (변경|일정)과 완료 답변 일치|저장 없이 완료 주장|저장하지 않고 완료 주장|저장 안 하고 완료 주장)")
OTHERS_RE = re.compile(r"^(요청 안 한 일정 변경 금지|다른 일정 그대로|나머지 일정 그대로|요청하지 않은 일정 변경 금지)$")


def _seq_list(text: str) -> list[int]:
    return [int(x) for x in re.findall(r"\d+", text)]


def rule(text: str, *, targets: list[dict[str, Any]] | None = None, kind: str = "end") -> dict[str, Any] | None:
    """규칙으로 옮긴 조건(없으면 None). `targets` — 요청 대상 고르기(M) 목록. None 이면 「요청 안 한 …」을 옮기지 않는다."""
    t = (text or "").strip()
    if NO_CHANGE_RE.match(t):
        return {"op": "no_change"}
    if m := SAVES_RE.match(t):
        n = int(m.group(1))
        return {"op": "saves", "max": n, "min": n}
    if m := COUNT_RE.match(t):
        return {"op": "count", "eq": int(m.group(1))}
    if m := KIND_RE.match(t):
        return {"op": "field", "match": {"seq": int(m.group(1))}, "field": "kind", "eq": m.group(2)}
    if m := INDOOR_RE.match(t):
        return {"op": "field", "match": {"seq": int(m.group(1))}, "field": "indoor", "eq": m.group(2) == "true"}
    if m := PLACE_NE_RE.match(t):
        return {"op": "field", "match": {"seq": int(m.group(1))}, "field": "place", "ne": m.group(2).strip("「」\"' ")}
    if m := TIME_RE.match(t):
        hm = [g for g in m.groups()[1:] if g]
        return {"op": "time", "match": {"seq": int(m.group(1))}, "start": hm[0], "end": hm[1], "tol": 0}
    if m := ABSENT_SEQ_RE.match(t):
        return {"op": "absent", "match": {"seq": _seq_list(m.group(1))}}
    if m := SAME_RE.match(t):
        return {"op": "unchanged", "match": {"seq": _seq_list(m.group(1))}}
    if m := ANSWER_RE.match(t):
        return {"op": "answer", "any": [m.group(1)]}
    if FALSE_DONE_RE.match(t):
        return {"op": "no_false_done"}
    if PINNED_RE.match(t):
        return {"op": "pinned_unchanged"}
    if OTHERS_RE.match(t) and targets is not None:
        return {"op": "unchanged_except", "match": targets}
    return None


VALID_OPS = {"no_change", "absent", "present", "unchanged", "unchanged_except", "time", "field", "count", "answer",
             "trip_title", "saves", "pinned_unchanged", "any_of", "all_of", "not", "manual", "no_false_done", "no_invented_fact", "answer_judge"}
VALID_FIELDS = {"kind", "place", "title", "indoor", "category"}
MATCH_KEYS = {"seq", "name", "date", "kind", "around", "window", "all", "mobility"}


def validate(cond: Any) -> str | None:
    """조건 모양 검사 — 문제가 있으면 이유, 없으면 None. 모델이 옮긴 조건은 이 검사를 통과한 것만 쓴다."""
    if not isinstance(cond, dict) or cond.get("op") not in VALID_OPS:
        return f"모르는 op: {cond.get('op') if isinstance(cond, dict) else type(cond).__name__}"
    op = cond["op"]

    def _m(m: Any) -> str | None:
        if not isinstance(m, dict) or not m or set(m) - MATCH_KEYS:
            return f"고르기 모양 틀림: {m}"
        if "around" in m and not re.fullmatch(r"[0-2]?\d:[0-5]\d", str(m["around"])):
            return "around 는 HH:MM"
        if "date" in m and not re.fullmatch(r"\d\d-\d\d", str(m["date"])):
            return "date 는 MM-DD"
        return None

    if op in ("absent", "present", "unchanged", "time", "field"):
        if (why := _m(cond.get("match"))):
            return why
    if op == "unchanged_except":
        if not isinstance(cond.get("match"), list):
            return "unchanged_except.match 는 목록"
        for m in cond["match"]:
            if (why := _m(m)):
                return why
    if op == "time":
        for key in ("start", "end"):
            if cond.get(key) is not None and not re.fullmatch(r"[0-2]?\d:[0-5]\d", str(cond[key])):
                return f"time.{key} 는 HH:MM"
    if op == "field":
        if cond.get("field") not in VALID_FIELDS:
            return "field 이름 틀림"
        if not any(k in cond for k in ("eq", "ne", "contains", "not_contains", "in")):
            return "field 비교 없음"
    if op == "answer_judge" and not str(cond.get("criterion") or "").strip():
        return "answer_judge.criterion 없음"
    if op == "answer" and not any(cond.get(k) for k in ("any", "all", "none")):
        return "answer 비교 없음"
    if op == "count" and not isinstance(cond.get("eq"), int):
        return "count.eq 는 정수"
    if op in ("any_of", "all_of"):
        if not isinstance(cond.get("of"), list) or not cond["of"]:
            return f"{op}.of 는 목록"
        for c in cond["of"]:
            if (why := validate(c)):
                return why
    if op == "not" and (why := validate(cond.get("of"))):
        return why
    return None


def compile_episode(ep: dict[str, Any], model_file: dict[str, Any] | None = None) -> dict[str, Any]:
    """에피소드 하나의 조건 묶음 — {"targets": [...], "end": [{"text", "dsl", "by"}], "forbidden": [...]}.

    `model_file` — 모델이 옮긴 같은 에피소드 줄(`compiled_*.jsonl`). 규칙이 먼저, 모델이 다음, 둘 다 없으면 manual.
    """
    mf = model_file or {}
    targets = mf.get("targets")
    if targets is None and ep.get("goal_type") in ("질문", "잡담"):
        targets = []
    model_end = {c.get("text"): c.get("dsl") for c in mf.get("end") or []}
    model_forb = {c.get("text"): c.get("dsl") for c in mf.get("forbidden") or []}

    def one(text: str, kind: str, table: dict[str, Any]) -> dict[str, Any]:
        got = rule(text, targets=targets, kind=kind)
        if got is not None:
            return {"text": text, "dsl": got, "by": "rule"}
        cand = table.get(text)
        if cand is not None and validate(cand) is None:
            return {"text": text, "dsl": cand, "by": mf.get("compiled_by", "model")}
        why = "옮긴 조건 없음" if cand is None else f"모양 검사 실패: {validate(cand)}"
        return {"text": text, "dsl": {"op": "manual", "why": why}, "by": "none"}

    forb_texts = list(ep.get("forbidden") or []) + list(ep.get("forbidden_from_state") or [])
    return {"episode_id": ep["episode_id"], "targets": targets,
            "end": [one(t, "end", model_end) for t in ep.get("end_state") or []],
            "forbidden": [one(t, "forbidden", model_forb) for t in forb_texts]}


def is_condition_text(text: str) -> bool:
    """조건 위반 칸(①)에 넣을 금지 · 조건인가 — 실내 · 야외 · 비 · 귀가 · 마감 · 종류 · 근처 · 메뉴."""
    return bool(re.search(r"야외|실내|indoor|비 |비가|우천|귀가|마감|늦어도|시까지|근처|걸어|먼 |면 요리|돈까스|종류|식당이 아닌|"
                          r"카페|메뉴|채식|비건|할랄|아이|유모차|휠체어|무릎", text or ""))


def coverage(compiled: list[dict[str, Any]]) -> dict[str, int]:
    out = {"end": 0, "end_rule": 0, "end_model": 0, "end_manual": 0, "forbidden": 0, "forbidden_rule": 0,
           "forbidden_model": 0, "forbidden_manual": 0}
    for c in compiled:
        for part in ("end", "forbidden"):
            for x in c[part]:
                out[part] += 1
                by = "rule" if x["by"] == "rule" else ("manual" if x["by"] == "none" else "model")
                out[f"{part}_{by}"] += 1
    return out


def name_in(text: str, names: list[str]) -> list[str]:
    nt = norm(text)
    return [n for n in names if norm(n) and norm(n) in nt]

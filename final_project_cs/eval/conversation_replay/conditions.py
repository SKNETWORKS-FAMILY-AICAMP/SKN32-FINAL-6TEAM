# -*- coding: utf-8 -*-
"""끝 상태 조건 · 금지 목록을 코드로 검사하는 작은 규칙 언어. 결과는 셋 — `pass` · `fail` · `unknown`(판정 불가). `[2026-10-19]`

정답 초안의 조건은 한국어 문장이다(「10-14 남산서울타워 없음」 「답에 명동교자 포함」). 문장을 그대로 채점할 수 없으므로
**한 번 이 언어로 옮겨 적은 파일**(`compile.py` — 규칙으로 옮기고, 남은 것은 모델이 옮긴 판을 사람 검수 대상으로 남긴다)로 채점한다.
옮기지 못한 조건은 `{"op": "manual"}` = 판정 불가다. **판정 불가는 통과로 세지 않는다**(재생 시험 계획 「채점」 ①).

조건 한 개(JSON):
  {"op": "no_change"}                                    일정(이동 구간 제외)이 시작 판과 같다
  {"op": "absent",  "match": M}                          끝 판에 M 에 맞는 항목이 없다
  {"op": "present", "match": M}                          끝 판에 M 에 맞는 항목이 있다
  {"op": "unchanged", "match": M}                        시작 판에서 M 에 맞는 항목이 끝 판에 그대로(같은 id · 시각 · 이름) 있다
  {"op": "unchanged_except", "match": [M, …]}            M 들에 맞지 않는 시작 판 항목은 모두 그대로(이동 구간은 빼고 본다)
  {"op": "time", "match": M, "start": "HH:MM", "end": "HH:MM"|null, "tol": 분, "date": "MM-DD"|null}
  {"op": "field", "match": M, "field": kind|place|title|indoor|category, "eq"|"ne"|"contains"|"not_contains"|"in": 값}
  {"op": "count", "eq": n}                               끝 판 항목 수(이동 구간 제외)
  {"op": "answer", "any": [...], "all": [...], "none": [...], "scope": "last"|"any"}   봇 답 글
  {"op": "trip_title", "eq": "…"}
  {"op": "saves", "max": n | "min": n}                   에피소드 동안 저장(새 판) 횟수
  {"op": "pinned_unchanged"}                             고객 고정 항목은 그대로
  {"op": "any_of", "of": [조건, …]} · {"op": "all_of", "of": [조건, …]} · {"op": "not", "of": 조건}
  {"op": "no_false_done"}                                완료를 말한 답이 모두 실제 저장과 맞다(거짓 완료 0)
  {"op": "answer_judge", "criterion": "…"}               뜻을 봐야 하는 답 조건(「위약금 기준에 직접 답함」) — 판정 모델이 있을 때만, 없으면 판정 불가
  {"op": "no_invented_fact"}                             조회 근거 없는 사실 값(영업시간 · 가격 · 주소 · 날씨)이 답에 없다
  {"op": "manual", "why": "…"}                           판정 불가 — 사람 검수로 보낸다

항목 고르기 M:
  {"seq": 2}                         시작 판의 2번 항목(끝 판에서는 그 계보의 후손)
  {"name": "남산서울타워", "date": "10-14", "kind": "dining", "around": "12:40", "window": 90}
                                     이름(제목 또는 장소 이름에 들어 있음) · 날짜 · 종류 · 시각 근처(±window 분, 기본 60)
  {"all": true}
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from .patterns import norm
from .state import KST, Item, TripView, same_items

PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"


def _hm(moment: datetime | None) -> str | None:
    return moment.astimezone(KST).strftime("%H:%M") if moment else None


def _md(moment: datetime | None) -> str | None:
    return moment.astimezone(KST).strftime("%m-%d") if moment else None


def _minutes(hm: str) -> int:
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


def _match_items(m: dict[str, Any], view: TripView, start: TripView | None = None) -> list[Item]:
    """M 에 맞는 항목. `seq` 는 시작 판 기준 — `view` 가 끝 판이면 계보 후손을 돌려준다."""
    if not m:
        return []
    if m.get("all"):
        return list(view.items)
    if "seq" in m:
        seqs = m["seq"] if isinstance(m["seq"], list) else [m["seq"]]
        out = []
        for s in seqs:
            origin = (start or view).by_seq(int(s))
            if origin is None:
                continue
            got = origin if (start is None or view is start) else view.descendant(origin)
            if got is not None:
                out.append(got)
        return out
    out = []
    for item in view.items:
        if m.get("kind") and item.kind != m["kind"]:
            continue
        if m.get("kind") is None and item.kind == "mobility" and not m.get("mobility"):
            continue
        if m.get("date") and _md(item.start) != m["date"]:
            continue
        if m.get("name"):
            want = norm(m["name"])
            if not want or not any(want in norm(n) for n in item.names()):
                continue
        if m.get("around") and item.start:
            gap = abs(_minutes(_hm(item.start)) - _minutes(m["around"]))
            if gap > int(m.get("window", 60)):
                continue
        out.append(item)
    return out


def _start_matches(m: dict[str, Any], start: TripView) -> list[Item]:
    return _match_items(m, start, None)


def evaluate(cond: dict[str, Any], *, start: TripView, end: TripView, answers: list[str], saves: int,
             false_done: int | None = None, invented: int | None = None, judge: Any = None) -> str:
    """조건 하나 → pass · fail · unknown. `false_done` — 이 에피소드의 거짓 완료 수(모르면 None)."""
    op = cond.get("op")
    if op == "no_false_done":
        return UNKNOWN if false_done is None else (PASS if false_done == 0 else FAIL)
    if op == "answer_judge":
        # 뜻을 봐야 하는 답 조건 — 평가 대상과 다른 판정 모델(`judge`)이 있을 때만 판정한다. 없으면 판정 불가
        if judge is None or not answers:
            return UNKNOWN
        return judge(str(cond.get("criterion") or ""), answers)
    if op == "no_invented_fact":
        return UNKNOWN if invented is None else (PASS if invented == 0 else FAIL)
    if op == "manual" or op is None:
        return UNKNOWN
    if op == "no_change":
        return PASS if same_items(start, end) else FAIL
    if op in ("absent", "present"):
        found = _match_items(cond.get("match") or {}, end, start)
        if "seq" in (cond.get("match") or {}) and op == "absent":
            # 시작 판 항목이 없어졌거나(후손 없음) 다른 것으로 바뀌었다
            origin = _start_matches(cond["match"], start)
            if not origin:
                return UNKNOWN
            return PASS if all(end.descendant(o) is None for o in origin) else FAIL
        if not (cond.get("match") or {}).get("name") and "seq" not in (cond.get("match") or {}) \
                and not (cond.get("match") or {}).get("kind"):
            return UNKNOWN
        return PASS if (bool(found) == (op == "present")) else FAIL
    if op == "unchanged":
        origin = _start_matches(cond.get("match") or {}, start)
        if not origin:
            return UNKNOWN
        for o in origin:
            d = end.descendant(o)
            if d is None or d.item_id != o.item_id or d.key() != o.key():
                return FAIL
        return PASS
    if op == "unchanged_except":
        excluded: set[str] = set()
        for m in cond.get("match") or []:
            excluded |= {i.item_id for i in _start_matches(m, start)}
        for o in start.stops():
            if o.item_id in excluded:
                continue
            d = end.descendant(o)
            if d is None or d.item_id != o.item_id or d.key() != o.key():
                return FAIL
        return PASS
    if op == "pinned_unchanged":
        pinned = [o for o in start.items if o.pinned]
        for o in pinned:
            d = end.descendant(o)
            if d is None or d.item_id != o.item_id or d.key() != o.key():
                return FAIL
        return PASS
    if op == "time":
        found = _match_items(cond.get("match") or {}, end, start)
        if not found:
            return FAIL if cond.get("must_exist", True) else UNKNOWN
        tol = int(cond.get("tol", 5))
        ok = False
        for item in found:
            if cond.get("date") and _md(item.start) != cond["date"]:
                continue
            s_ok = cond.get("start") is None or (item.start is not None and abs(_minutes(_hm(item.start)) - _minutes(cond["start"])) <= tol)
            e_ok = cond.get("end") is None or (item.end is not None and abs(_minutes(_hm(item.end)) - _minutes(cond["end"])) <= tol)
            ok = ok or (s_ok and e_ok)
        return PASS if ok else FAIL
    if op == "field":
        found = _match_items(cond.get("match") or {}, end, start)
        if not found:
            return FAIL if cond.get("must_exist", True) else UNKNOWN
        field = cond.get("field")
        results = []
        for item in found:
            value = getattr(item, field, None)
            if value is None:
                results.append(UNKNOWN)
                continue
            results.append(_compare(value, cond))
        if FAIL in results:
            return FAIL
        return UNKNOWN if UNKNOWN in results else PASS
    if op == "count":
        return PASS if len(end.stops()) == int(cond["eq"]) else FAIL
    if op == "answer":
        texts = answers[-1:] if cond.get("scope", "any") == "last" else answers
        blob = norm("\n".join(texts))
        if not texts:
            return FAIL
        if cond.get("any") and not any(norm(x) in blob for x in cond["any"] if norm(x)):
            return FAIL
        if cond.get("all") and not all(norm(x) in blob for x in cond["all"] if norm(x)):
            return FAIL
        if cond.get("none") and any(norm(x) in blob for x in cond["none"] if norm(x)):
            return FAIL
        return PASS
    if op == "trip_title":
        return PASS if norm(end.title) == norm(cond.get("eq")) else FAIL
    if op == "saves":
        if "max" in cond and saves > int(cond["max"]):
            return FAIL
        if "min" in cond and saves < int(cond["min"]):
            return FAIL
        return PASS
    if op in ("any_of", "all_of"):
        got = [evaluate(c, start=start, end=end, answers=answers, saves=saves, false_done=false_done, invented=invented, judge=judge) for c in cond.get("of") or []]
        if op == "any_of":
            return PASS if PASS in got else (UNKNOWN if UNKNOWN in got else FAIL)
        return FAIL if FAIL in got else (UNKNOWN if UNKNOWN in got else PASS)
    if op == "not":
        got = evaluate(cond["of"], start=start, end=end, answers=answers, saves=saves, false_done=false_done, invented=invented, judge=judge)
        return {PASS: FAIL, FAIL: PASS}.get(got, UNKNOWN)
    return UNKNOWN


def _compare(value: Any, cond: dict[str, Any]) -> str:
    if isinstance(value, bool) or "eq" in cond and isinstance(cond.get("eq"), bool):
        if "eq" in cond:
            return PASS if value == cond["eq"] else FAIL
        if "ne" in cond:
            return PASS if value != cond["ne"] else FAIL
    v = norm(str(value))
    if "eq" in cond:
        return PASS if v == norm(str(cond["eq"])) else FAIL
    if "ne" in cond:
        return PASS if norm(str(cond["ne"])) not in v else FAIL
    if "contains" in cond:
        return PASS if norm(str(cond["contains"])) in v else FAIL
    if "not_contains" in cond:
        return PASS if norm(str(cond["not_contains"])) not in v else FAIL
    if "in" in cond:
        return PASS if any(norm(str(x)) == v or norm(str(x)) in v for x in cond["in"]) else FAIL
    return UNKNOWN


def evaluate_all(conds: Iterable[dict[str, Any]], **kw) -> list[str]:
    return [evaluate(c, **kw) for c in conds]


def overall(results: list[str]) -> str:
    """전부 통과면 pass, 하나라도 위반이면 fail, 나머지는 unknown."""
    if not results:
        return UNKNOWN
    if FAIL in results:
        return FAIL
    return UNKNOWN if UNKNOWN in results else PASS

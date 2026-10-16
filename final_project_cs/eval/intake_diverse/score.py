# -*- coding: utf-8 -*-
"""채점기 — 구조와 상관없는 **중립 모양** 예측을 정답과 맞춘다. 지금 구조 · 새 구조 모두 이 모양으로 바꿔 넣는다(어댑터는 각 실행기 몫).

예측 한 건(`prediction`):
  {"case_id", "error": None | "읽기 실패 사유", "seconds": 걸린 초,
   "items": [{"title": 원문 조각, "date": "YYYY-MM-DD"|None, "start": "HH:MM"|None, "end": …, "kind": activity|dining|lodging|None,
              "place_name": 찾은 장소 이름|None}],
   "moves": [{"scope", "mode", "from", "to", "day"}], "conditions": [{"code", "target"}], "preferences": [code…],
   "requests": [label…], "missing": [code…], "trip": {"party_size", "days", "nights"}}

★엄격 계수: `error` 가 있으면(읽기 실패) 그 건의 정답 칸은 **전부 틀림**으로 센다 — 실패를 분모에서 빼지 않는다.
★맞춤 규칙(항목): 정답 `place` 와 예측 `title` 을 정규화(NFKC · 소문자 · 공백 · 문장부호 제거)해 **같거나 한쪽이 다른 쪽을 품으면** 후보,
  같으면 3점 · 품으면 2점(짧은 쪽이 긴 쪽의 60% 이상) 또는 1점, 날짜가 같으면 +1. 점수 높은 짝부터 하나씩 맺는다.
  찾은 장소 이름(`place_name`)이 정답 `canon` 과 같아도 후보(2점)다. `optional` 정답은 맺어지면 예측 쪽 오답에서 빼고, 안 맺어져도 정답 분모에 넣지 않는다.
★`items_tight`: 맺어진 항목 중 읽은 조각이 정답 장소 말과 **거의 같은**(위 2점 이상) 것 — 느슨한 맞춤이 긴 조각을 맞음으로 치는 것을 보정한다.
★값 변조: 예측 `title` 이 원문(`source_text`)의 부분 문자열이 아니면 변조(원문에 없는 글자)다.
"""
from __future__ import annotations

from collections import defaultdict
import re
import unicodedata
from typing import Any

PUNCT = re.compile(r"[\s·・\-_'\"()\[\]{}<>~,.!?/|:;→▶⏰📍☕🍢🚲+]+")
FIELDS = ("items", "items_tight", "items_precision", "time", "end", "date", "kind", "place_found", "tamper", "moves", "moves_precision",
          "conditions", "preferences", "requests", "requests_exact", "missing", "trip")


def norm(value: str | None) -> str:
    return PUNCT.sub("", unicodedata.normalize("NFKC", value or "").lower())


def _text_score(gold: dict[str, Any], pred: dict[str, Any]) -> int:
    """원문 조각끼리만 — 3 같음 · 2 거의 같음(짧은 쪽이 긴 쪽의 60% 이상 품음) · 1 품기만 함 · 0 다름."""
    g, p = norm(gold["place"]), norm(pred.get("title"))
    if not (g and p):
        return 0
    if g == p:
        return 3
    if len(p) >= 2 and (g in p or p in g):
        short, long_ = sorted((len(g), len(p)))
        return 2 if short / long_ >= 0.6 else 1
    return 0


def _pair_score(gold: dict[str, Any], pred: dict[str, Any]) -> int:
    g, p = norm(gold["place"]), norm(pred.get("title"))
    score = 0
    if g and p:
        if g == p:
            score = 3
        elif len(p) >= 2 and (g in p or p in g):
            short, long_ = sorted((len(g), len(p)))
            score = 2 if short / long_ >= 0.6 else 1
    if not score and pred.get("place_name") and norm(pred["place_name"]) in {norm(c) for c in gold.get("canon") or []}:
        score = 2
    if score and gold.get("date") and pred.get("date"):
        if gold["date"] == pred["date"]:
            score += 1
        else:
            score = max(0, score - 1)
    return score


def match_items(gold: list[dict[str, Any]], pred: list[dict[str, Any]]) -> dict[int, int]:
    """정답 번호 → 예측 번호."""
    pairs = sorted(((_pair_score(g, p), -gi, -pi, gi, pi) for gi, g in enumerate(gold) for pi, p in enumerate(pred)), reverse=True)
    used_g, used_p, out = set(), set(), {}
    for score, _, _, gi, pi in pairs:
        if score <= 0 or gi in used_g or pi in used_p:
            continue
        used_g.add(gi)
        used_p.add(pi)
        out[gi] = pi
    return out


def _move_match(gold: dict[str, Any], pred: dict[str, Any]) -> bool:
    if gold["mode"] != pred.get("mode"):
        return False
    if gold["scope"] in ("all", "day"):
        return pred.get("scope") in ("all", "day") and (gold["scope"] != "day" or pred.get("day") in (None, gold.get("day")))
    if pred.get("scope") != "segment":
        return False
    to_ok = not gold.get("to") or (norm(gold["to"]) and (norm(gold["to"]) in norm(pred.get("to")) or norm(pred.get("to")) in norm(gold["to"])) and norm(pred.get("to")))
    from_ok = not gold.get("from") or not pred.get("from") or norm(gold["from"]) in norm(pred["from"]) or norm(pred["from"]) in norm(gold["from"])
    return bool(to_ok and from_ok)


def score_case(case: dict[str, Any], pred: dict[str, Any]) -> dict[str, list[int]]:
    """칸마다 [맞음, 분모]. 분모 0 인 칸은 그 건에 해당 없음."""
    g = case["gold"]
    failed = bool(pred.get("error"))
    p_items = [] if failed else list(pred.get("items") or [])
    gold_items = g["items"]
    pairs = match_items(gold_items, p_items)
    required = [i for i, it in enumerate(gold_items) if not it.get("optional")]
    out: dict[str, list[int]] = {k: [0, 0] for k in FIELDS}

    out["items"] = [sum(1 for i in required if i in pairs), len(required)]
    # ★느슨한 맞춤(품기만 함)은 「서울역 도착, 남산타워까지 … 저녁 기차」 같은 긴 조각도 서울역으로 쳐 준다 — 조각이 장소 말과 거의 같은 것만 따로 센다
    out["items_tight"] = [sum(1 for i in required if i in pairs and _text_score(gold_items[i], p_items[pairs[i]]) >= 2), len(required)]
    optional_hits = {pairs[i] for i, it in enumerate(gold_items) if it.get("optional") and i in pairs}
    counted_preds = [pi for pi in range(len(p_items)) if pi not in optional_hits]
    out["items_precision"] = [sum(1 for pi in counted_preds if pi in set(pairs.values())), len(counted_preds)]
    for i in required:
        it = gold_items[i]
        got = p_items[pairs[i]] if i in pairs else {}
        if it.get("start"):
            out["time"][1] += 1
            out["time"][0] += int(got.get("start") == it["start"])
        if it.get("end"):
            out["end"][1] += 1
            out["end"][0] += int(got.get("end") == it["end"])
        if it.get("date"):
            out["date"][1] += 1
            out["date"][0] += int(got.get("date") == it["date"])
        out["kind"][1] += 1
        out["kind"][0] += int(i in pairs and (got.get("kind") or "activity") == it["kind"])
        if it.get("canon"):
            out["place_found"][1] += 1
            out["place_found"][0] += int(bool(got.get("place_name")) and norm(got["place_name"]) in {norm(c) for c in it["canon"]})
    source = case.get("source_text") or ""
    titles = [p.get("title") for p in p_items if p.get("title")]
    out["tamper"] = [sum(1 for t in titles if t not in source), len(titles)]      # ★이 칸만 「틀린 수 / 분모」(낮을수록 좋다)

    p_moves = [] if failed else list(pred.get("moves") or [])
    hit_moves = sum(1 for m in g["moves"] if any(_move_match(m, p) for p in p_moves))
    out["moves"] = [hit_moves, len(g["moves"])]
    out["moves_precision"] = [sum(1 for p in p_moves if any(_move_match(m, p) for m in g["moves"])), len(p_moves)]
    p_conds = {c.get("code") for c in ([] if failed else pred.get("conditions") or [])}
    out["conditions"] = [sum(1 for c in g["conditions"] if c["code"] in p_conds), len(g["conditions"])]
    p_prefs = set([] if failed else pred.get("preferences") or [])
    out["preferences"] = [sum(1 for c in g["preferences"] if c in p_prefs), len(g["preferences"])]
    p_req = set([] if failed else pred.get("requests") or [])
    want, free = set(g["requests"]), set(g["requests_optional"])
    out["requests"] = [len(want & p_req), len(want)]
    out["requests_exact"] = [int((p_req - free) == want), 1]
    p_miss = set([] if failed else pred.get("missing") or [])
    out["missing"] = [len(set(g["missing"]) & p_miss), len(g["missing"])]
    trip = {} if failed else (pred.get("trip") or {})
    for key, value in g["trip"].items():
        out["trip"][1] += 1
        out["trip"][0] += int(trip.get(key) == value)
    return out


def score_all(cases: list[dict[str, Any]], preds: dict[str, dict[str, Any]]) -> dict[str, Any]:
    per_case, totals = {}, defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for case in cases:
        pred = preds.get(case["case_id"]) or {"error": "예측 없음"}
        got = score_case(case, pred)
        per_case[case["case_id"]] = got
        for group in ("전체", f"origin:{case['origin']}", f"shape:{case['shape']}"):
            for key, (a, b) in got.items():
                totals[group][key][0] += a
                totals[group][key][1] += b
            totals[group]["cases"][1] += 1
            totals[group]["cases"][0] += int(not pred.get("error"))
    return {"per_case": per_case, "totals": {g: dict(v) for g, v in totals.items()}}


def pct(pair: list[int]) -> str:
    a, b = pair
    return "해당 없음" if b == 0 else f"{a}/{b} = {100 * a / b:.0f}%"


__all__ = ["FIELDS", "match_items", "norm", "pct", "score_all", "score_case"]

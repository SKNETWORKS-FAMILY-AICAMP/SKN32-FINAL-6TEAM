# -*- coding: utf-8 -*-
"""에피소드 읽기 — 실제 대화(`episodes_v*.jsonl`)와 표적 에피소드(`targets_v*.jsonl`)를 한 모양으로. `[2026-10-19]`

자료는 git 밖(`datasets/travel/chat_replay_20261019/`)에 있다. 이 모듈은 읽기만 한다.
한 모양(dict):
  episode_id · set(real|target) · env · now · start(TripView dict) · seed(시험 DB 에 넣을 시작 상태 원본) · script[{text, role, at}]
  · orig_bot · goal · goal_type · end_state · forbidden · forbidden_from_state · unneeded_reask · exposure
  · real_human_questions · author · flags{angry, multi_step, confidence, needs_start_items, field_test, risk_type}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from .state import Item, TripView, parse_dt

ROLES = ("새 요청", "직전 봇 질문의 답", "같은 요청 반복", "항의", "잡담")


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def _real_items(ep: dict[str, Any]) -> list[Item]:
    ss = ep.get("start_state") or {}
    v2 = ss.get("v2") or {}
    rows = v2.get("items") or []
    out = []
    for r in rows:
        detail = r.get("detail") or {}
        prov = (detail.get("provenance") or {}).get("place") or {}
        place = (detail.get("place") or {}).get("name") if isinstance(detail.get("place"), dict) else None
        out.append(Item(item_id=str(r.get("item_id")), seq=int(r.get("seq") or 0), kind=str(r.get("kind") or ""),
                        title=str(r.get("title") or ""), place=place or prov.get("query"),
                        start=parse_dt(r.get("starts_at")), end=parse_dt(r.get("ends_at")),
                        pinned=bool(r.get("locked") or detail.get("customer_pinned")),
                        replaces=r.get("replaces_item_id"), place_id=r.get("place_id")))
    if not out:   # 추가 조회 전 사본(v1)만 있는 에피소드
        for r in ss.get("items") or []:
            out.append(Item(item_id=f"seq{r.get('seq')}", seq=int(r.get("seq") or 0), kind=str(r.get("kind") or ""),
                            title=str(r.get("title") or ""), start=parse_dt(r.get("s")), end=parse_dt(r.get("e")),
                            pinned=bool(r.get("locked"))))
    return out


def _target_items(ep: dict[str, Any]) -> list[Item]:
    out = []
    for r in (ep.get("start_state") or {}).get("items") or []:
        out.append(Item(item_id=f"T{ep['episode_id']}-{r.get('seq')}", seq=int(r.get("seq") or 0), kind=str(r.get("kind") or ""),
                        title=str(r.get("title") or ""), place=r.get("place"), start=parse_dt(r.get("s")), end=parse_dt(r.get("e")),
                        pinned=bool(r.get("pinned")), indoor=r.get("indoor")))
    return out


def normalize(ep: dict[str, Any]) -> dict[str, Any]:
    is_target = ep.get("set") == "target"
    items = _target_items(ep) if is_target else _real_items(ep)
    ss = ep.get("start_state") or {}
    version = int((ss.get("v2") or {}).get("version") or ss.get("version") or 1)
    start = TripView(version=version, items=items, title=str(ep.get("trip_title") or ""))
    script = [{"text": s.get("text", ""), "role": s.get("role") or "새 요청", "at": s.get("at"), "n": s.get("n")}
              for s in ep.get("script") or []]
    return {
        "episode_id": ep["episode_id"], "set": "target" if is_target else "real", "env": ep.get("env") or "synthetic",
        "now": ep.get("now"), "start": start.as_dict(), "seed": ss, "trip_id": ep.get("trip_id"), "trip_title": ep.get("trip_title"),
        "script": script, "orig_bot": ep.get("orig_bot") or [], "goal": ep.get("goal"),
        "goal_type": ep.get("goal_type") or ({"T6": "질문"}.get(ep.get("risk_type")) if is_target else None),
        "end_state": list(ep.get("end_state") or []), "forbidden": list(ep.get("forbidden") or []),
        "forbidden_from_state": list(ep.get("forbidden_from_state") or []),
        "unneeded_reask": list(ep.get("unneeded_reask") or []), "exposure": ep.get("exposure") or {},
        "real_human_questions": bool(ep.get("real_human_questions")) and not is_target,
        "author": ep.get("author") or (ep.get("source") or {}).get("label_by"),
        "flags": {"angry": bool(ep.get("angry")), "multi_step": bool(ep.get("multi_step")), "confidence": ep.get("confidence"),
                  "needs_start_items": bool(ep.get("needs_start_items")), "field_test": bool(ep.get("field_test")),
                  "risk_type": ep.get("risk_type"), "orig_outcome": ep.get("orig_outcome")},
    }


def load(path: Path) -> list[dict[str, Any]]:
    return [normalize(e) for e in _iter_jsonl(path)]


def turn_cap(episodes: list[dict[str, Any]]) -> int:
    """B 방식 턴 상한 = 실제 고객 턴 수의 95번째 백분위 + 2(재생 시험 계획). 실제 대화 묶음에서만 센다."""
    import math

    xs = sorted(len(e["script"]) for e in episodes if e["set"] == "real")
    if not xs:
        return 4
    k = (len(xs) - 1) * 0.95
    lo, hi = math.floor(k), math.ceil(k)
    p95 = xs[lo] + (xs[hi] - xs[lo]) * (k - lo)
    return int(math.ceil(p95)) + 2

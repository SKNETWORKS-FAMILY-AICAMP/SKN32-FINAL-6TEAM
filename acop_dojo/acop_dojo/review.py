"""간격 반복.

근거는 있지만 조심해서 쓴다. 인출·간격·교차 연습이 장기 보존에 유리하다는 것은
여러 연구가 지지하지만, **자발적 CLI 사용자가 1·3·7일 뒤 실제로 돌아왔다는 사례는
찾지 못했다.** 그래서 1·3·7·21은 기본값일 뿐이고, 실제 재방문을 기록해 나중에 조정한다.

두 가지를 구분해 기록한다.
- 안 돌아온 것은 '실패'가 아니라 '미관찰'이다. 사람이 안 온 것과 틀린 것은 다르다.
- 같은 문제를 다시 묻지 않는다. 같은 규칙을 **다른 코드에서** 회상하게 한다.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from . import defects as defects_mod
from . import progress

#: 기본 간격(일). 교육 효과를 주장하는 값이 아니라 출발점이다.
INTERVALS = [1, 3, 7, 21]


def now() -> datetime:
    return datetime.now(UTC)


def _iso(moment: datetime) -> str:
    return moment.replace(microsecond=0).isoformat()


def schedule(concept: str, *, source: str, moment: datetime | None = None) -> dict[str, Any]:
    """개념 하나를 복습 대기에 올린다. 이미 있으면 간격을 한 칸 늘린다."""
    data = progress.load()
    items = data.setdefault("reviews", {})
    entry = items.get(concept, {"step": -1, "history": [], "source": source})
    entry["step"] = min(entry["step"] + 1, len(INTERVALS) - 1)
    entry["source"] = source
    base = moment or now()
    entry["due_at"] = _iso(base + timedelta(days=INTERVALS[entry["step"]]))
    entry["scheduled_at"] = _iso(base)
    items[concept] = entry
    progress.save(data)
    return entry


def due(moment: datetime | None = None) -> list[tuple[str, dict[str, Any]]]:
    data = progress.load()
    limit = _iso(moment or now())
    return sorted(
        (concept, entry) for concept, entry in data.get("reviews", {}).items()
        if entry.get("due_at", "") <= limit
    )


def record(concept: str, *, recalled: bool, moment: datetime | None = None) -> None:
    """회상 결과를 남긴다. 맞으면 간격을 늘리고 틀리면 처음으로 되돌린다."""
    data = progress.load()
    entry = data.setdefault("reviews", {}).get(concept)
    if entry is None:
        return
    base = moment or now()
    entry.setdefault("history", []).append({"at": _iso(base), "recalled": recalled})
    entry["visited_at"] = _iso(base)
    entry["step"] = min(entry["step"] + 1, len(INTERVALS) - 1) if recalled else 0
    entry["due_at"] = _iso(base + timedelta(days=INTERVALS[entry["step"]]))
    progress.save(data)


def stats() -> dict[str, Any]:
    """재방문이 실제로 일어나는지 본다. 안 온 것은 실패가 아니라 미관찰이다."""
    data = progress.load()
    items = data.get("reviews", {})
    visited = [e for e in items.values() if e.get("visited_at")]
    attempts = [h for e in items.values() for h in e.get("history", [])]
    return {
        "scheduled": len(items),
        "visited": len(visited),
        "unobserved": len(items) - len(visited),
        "recalled": sum(1 for h in attempts if h["recalled"]),
        "attempts": len(attempts),
    }


def other_defect_for(concept: str, exclude: str | None) -> str | None:
    """같은 불변식을 다른 코드에서 묻기 위해 다른 결함을 찾는다."""
    from . import defect_stage

    catalog = defects_mod.load_catalog()
    playable = set(defect_stage.playable(catalog))
    candidates = [d.defect_id for d in defects_mod.DEFECTS
                  if d.invariant == concept and d.defect_id in playable
                  and d.defect_id != exclude]
    return candidates[0] if candidates else None

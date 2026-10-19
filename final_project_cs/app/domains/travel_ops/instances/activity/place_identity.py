# -*- coding: utf-8 -*-
"""같은 장소 판정 — 이름이 달라도 **같은 곳**인가(「N서울타워」 = 「남산서울타워」). `[2026-10-19 사용자 결정]`

☆왜: 대체 장소 후보에서 「이미 일정에 있는 곳」을 뺄 때 contentid 와 **이름 문자열 완전 일치**만 봤다. 일정의 카카오 장소
  「N서울타워」(contentid 없음)와 원장의 「남산서울타워」는 이름이 달라 안 빠지고 같은 곳이 또 추천됐다. 이름이 닮은 것만으로는
  같은 곳을 가를 수 없다 — 남산도서관 · 용산도서관(유사도 0.92 · 121m)이 다른 곳이고 남산서울타워 · N서울타워(0.80)가 같은 곳이다.

세 단계다(`verdict`):
    same       — 같은 contentid, 또는 정규화한 이름이 같다. 규칙이 정한다.
    different  — 좌표를 모르거나 `NEAR_M` 밖이거나 이름이 안 닮았다. 규칙이 정한다.
    ambiguous  — `NEAR_M` 안이고 이름이 `NAME_SIM_MIN` 이상 닮았는데 이름이 다르다. **이것만** LLM 에 묻는다(`kind_modes.same_place: llm`).

★**계산만 한다.** 이 파일은 LLM · DB 를 부르지 않는다 — 묻는 일은 `replacement.py` 가 하고, 여기는 입력(`payload`) · 답 검증(`apply`) · 기억(`remember`)만 한다.
★LLM 이 답하지 못하거나 꺼져 있으면 **빼지 않고** 남긴다(경고만) — 짐작으로 후보를 지우지 않는다. 잘못 빼도 후보가 한 곳 줄 뿐이고,
  잘못 남겨도 같은 곳이 한 번 더 나올 뿐이다.
★좌표 · 주소는 모델에 보내지 않는다 — 이름 · 분류 · 거리(m)만.
★기억(`remember`)은 **프로세스 메모리**뿐이다(재기동하면 사라진다). 영구 저장은 DB 표가 필요해 코어와 정할 일이다.
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Iterable

from app.domains.travel_ops.components.intake.places import distance_m, normalize_full

#: 판정 종류 · 프롬프트 키 — `kind_modes.same_place` 로 켜고 끈다(표에 없으면 `rule` = 부르지 않음). 프롬프트 허용 목록은 코어 몫이다.
KIND = "same_place"
PROMPT_KEY = f"activity_judge.{KIND}"
#: 같은 곳일 수 있는 거리(m). ★우리가 고른 값 — 카카오 · 관광공사 좌표는 입구 · 주차장 차이로 수십~수백 m 어긋난다.
#:  `itinerary_changes.SAME_SITE_M`(30m)와 다르다 — 그쪽은 「확실히 같은 곳」, 여기는 「물어볼 만한 거리」다.
NEAR_M = 300
#: 이름이 이만큼 닮아야 물어본다(공통 부분열 ÷ 짧은 이름). ★우리가 고른 값 — 이름만으로는 같은 곳을 못 가르므로 **물을 쌍을 좁히는 문턱**일 뿐이다.
NAME_SIM_MIN = 0.8
#: 한 번에 묻는 쌍의 수 상한 — 가까운 쌍부터. 넘는 쌍은 묻지 않고 남긴다.
MAX_PAIRS = 6
#: 이름 두 개가 이보다 짧으면 닮았는지 따지지 않는다(「남산」 같은 짧은 말이 아무 데나 붙는다)
MIN_NAME_LEN = 3
#: 프로세스 메모리 기억의 크기
CACHE_SIZE = 2000


@dataclass(frozen=True)
class Spot:
    """같은 곳인지 따질 장소 하나 — 일정 항목 또는 대체 후보."""
    name: str
    latitude: float | None
    longitude: float | None
    content_id: str | None = None
    kind: str | None = None          # 분류(모델에 넘기는 보조 단서) — 없어도 된다


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def spot_of(place: dict[str, Any] | None) -> Spot | None:
    """일정 항목의 장소(`name` · `latitude` · `longitude` · `source_content_id`)나 후보 행(`title` · `mapy` · `mapx` · `contentid`)을 `Spot` 으로."""
    if not isinstance(place, dict):
        return None
    attributes = place.get("attributes") if isinstance(place.get("attributes"), dict) else {}
    name = str(place.get("name") or place.get("title") or "").strip()
    if not name:
        return None
    content_id = place.get("source_content_id") or attributes.get("source_content_id") or place.get("contentid")
    lat = _float(place.get("latitude") if place.get("latitude") is not None else place.get("mapy"))
    lon = _float(place.get("longitude") if place.get("longitude") is not None else place.get("mapx"))
    kind = place.get("lclsSystm3") or place.get("lclsSystm2") or place.get("kind")
    return Spot(name, lat, lon, str(content_id) if content_id else None, str(kind) if kind else None)


def _lcs(a: str, b: str) -> int:
    previous = [0] * (len(b) + 1)
    for ca in a:
        current = [0]
        for j, cb in enumerate(b, start=1):
            current.append(previous[j - 1] + 1 if ca == cb else max(previous[j], current[-1]))
        previous = current
    return previous[-1]


def name_similarity(a: str, b: str) -> float:
    """정규화한 두 이름의 닮은 정도 0~1 — 공통 부분열 길이 ÷ 짧은 이름. 한쪽이 다른 쪽의 부분열이면 1."""
    key_a, key_b = normalize_full(a), normalize_full(b)
    if min(len(key_a), len(key_b)) < MIN_NAME_LEN:
        return 0.0
    return _lcs(key_a, key_b) / min(len(key_a), len(key_b))


def distance_between(a: Spot, b: Spot) -> float | None:
    if None in (a.latitude, a.longitude, b.latitude, b.longitude):
        return None
    return distance_m(a.latitude, a.longitude, b.latitude, b.longitude)


def verdict(item: Spot, candidate: Spot) -> str:
    """`same` · `different` · `ambiguous` — 규칙만. 모르는 값은 같다고 읽지 않는다."""
    if item.content_id and item.content_id == candidate.content_id:
        return "same"
    a, b = normalize_full(item.name), normalize_full(candidate.name)
    if not a or not b:
        return "different"
    if a == b:
        return "same"                      # 지금까지의 동작 — 이름이 같으면 같은 곳으로 본다(거리와 상관없이)
    d = distance_between(item, candidate)
    if d is None or d > NEAR_M:
        return "different"
    return "ambiguous" if name_similarity(item.name, candidate.name) >= NAME_SIM_MIN else "different"


# ── 기억(프로세스 메모리) ─────────────────────────────────────────

_cache: "OrderedDict[tuple[str, str], bool]" = OrderedDict()
_cache_lock = threading.Lock()


def _pair_key(a: Spot, b: Spot) -> tuple[str, str]:
    return tuple(sorted((normalize_full(a.name), normalize_full(b.name))))   # type: ignore[return-value]


def recalled(a: Spot, b: Spot) -> bool | None:
    """이 이름 쌍을 앞서 판정했나 — 같다 `True` · 다르다 `False` · 모른다 `None`."""
    with _cache_lock:
        return _cache.get(_pair_key(a, b))


def remember(a: Spot, b: Spot, same: bool) -> None:
    with _cache_lock:
        _cache[_pair_key(a, b)] = same
        _cache.move_to_end(_pair_key(a, b))
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)


def forget_all() -> None:
    """기억을 비운다 — 시험용."""
    with _cache_lock:
        _cache.clear()


# ── 후보 가르기 ──────────────────────────────────────────────────

@dataclass(frozen=True)
class Pair:
    """모델에 묻는 쌍 — 일정에 있는 곳 · 대체 후보 · 거리."""
    id: str
    item: Spot
    candidate: Spot
    candidate_id: str
    distance_m: float


def split(items: Iterable[Spot], candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, list[Pair]]:
    """후보를 `(남길 후보, 규칙으로 뺀 수, 물어볼 쌍)` 으로 가른다. 기억에 답이 있는 쌍은 묻지 않고 바로 처리한다.

    ★물어볼 쌍은 후보 하나에 가장 가까운 일정 항목 하나만, 거리 가까운 순으로 `MAX_PAIRS` 개까지다. 넘는 쌍은 묻지 않고 남긴다.
    """
    spots = [s for s in items if s is not None]
    kept: list[dict[str, Any]] = []
    removed = 0
    ask: list[Pair] = []
    for row in candidates:
        cand = spot_of(row)
        if cand is None or not spots:
            kept.append(row)
            continue
        states = [(verdict(item, cand), item) for item in spots]
        if any(state == "same" for state, _ in states):
            removed += 1
            continue
        near = [item for state, item in states if state == "ambiguous"]
        if not near:
            kept.append(row)
            continue
        answers = [recalled(item, cand) for item in near]
        if any(answer is True for answer in answers):
            removed += 1
        elif all(answer is False for answer in answers):
            kept.append(row)
        else:
            nearest = min((i for i, answer in enumerate(answers) if answer is None),
                          key=lambda i: distance_between(near[i], cand) or 0.0)
            ask.append(Pair(str(len(ask)), near[nearest], cand, str(row.get("contentid")),
                            round(distance_between(near[nearest], cand) or 0.0)))
            kept.append(row)               # 답이 올 때까지는 남겨 둔다 — 호출부가 `drop_same` 으로 뺀다
    ask.sort(key=lambda p: p.distance_m)
    return kept, removed, ask[:MAX_PAIRS]


# ── 모델 입력 · 출력 ─────────────────────────────────────────────

def payload(pairs: list[Pair]) -> dict[str, Any]:
    """모델에게 보낼 입력 — 이름 · 분류 · 거리(m)만. 좌표 · 주소는 보내지 않는다."""
    return {"kind": KIND,
            "pairs": [{"id": p.id, "in_plan": {"name": p.item.name, "class": p.item.kind},
                       "candidate": {"name": p.candidate.name, "class": p.candidate.kind},
                       "distance_m": p.distance_m} for p in pairs]}


def schema() -> dict[str, Any]:
    """Structured Outputs(strict) — 쌍마다 같은 곳인지 · 이유 한 줄."""
    return {
        "type": "object", "additionalProperties": False,
        "properties": {"answers": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"id": {"type": "string"}, "same": {"type": "boolean"}, "reason": {"type": "string"}},
            "required": ["id", "same", "reason"]}}},
        "required": ["answers"],
    }


def apply(pairs: list[Pair], output: Any) -> dict[str, bool] | None:
    """모델 답을 검증해 `{쌍 id: 같은 곳인가}` 로. 목록에 없는 id · 형식이 틀린 항목은 버린다. 쓸 수 있는 답이 하나도 없으면 `None`.

    ★답이 확실히 `true`/`false` 인 쌍만 기억한다(`remember`). 이유가 비면 받지 않는다 — 근거 없는 확정을 쓰지 않는다.
    """
    if not isinstance(output, dict) or not isinstance(output.get("answers"), list):
        return None
    by_id = {p.id: p for p in pairs}
    out: dict[str, bool] = {}
    for row in output["answers"]:
        if not isinstance(row, dict) or str(row.get("id")) not in by_id or not isinstance(row.get("same"), bool):
            continue
        if not str(row.get("reason") or "").strip():
            continue
        pair = by_id[str(row["id"])]
        out[pair.id] = row["same"]
        remember(pair.item, pair.candidate, row["same"])
    return out or None


def drop_same(candidates: list[dict[str, Any]], pairs: list[Pair], answers: dict[str, bool]) -> tuple[list[dict[str, Any]], int]:
    """묻고 받은 답에서 「같은 곳」으로 확인된 후보를 뺀다. `(남은 후보, 뺀 수)`."""
    gone = {p.candidate_id for p in pairs if answers.get(p.id) is True}
    kept = [c for c in candidates if str(c.get("contentid")) not in gone]
    return kept, len(candidates) - len(kept)

# -*- coding: utf-8 -*-
"""서울 대표 장소 정답표 · 숙소 말 · 이동 말 — 장소를 **찾기 전에** 종류와 가리키는 곳을 정한다. `[2026-10-19 계획서 읽기 진단 포인트 2]`

★왜. 장소 찾기(`places.resolve`)는 이름이 비슷한 곳을 자료 순서대로 받았다. 그래서
    · 「경복궁스테이 체크인」이 요식 원장(인허가 자료)의 같은 이름 식당이 돼 일정이 「식사」가 됐고(숙소 묶기에서도 빠졌다),
    · 「창덕궁」이 서울 운현궁, 「국립중앙박물관」이 그곳에서 열린 축제, 「명동 롯데호텔 서울」이 「명동」이 됐고,
    · 「광장시장」이 시장 안 가게 하나(삼모녀꼬마김밥)로 좁혀졌고,
    · 「택시로 이동」 · 「공항철도 타고 인천공항」이 장소로 찾혔다.
  근거: `wiki/records/reports/2026-10-19_chat-intake-secretary-review.md` 「2. 장소를 엉뚱한 곳·엉뚱한 종류로 붙인다」.
★D-025 와의 관계: 뜻(무엇이 숙소 · 식사 · 이동인가)은 가르친 E4B 가 읽고(`agent_read` 의 `kind`), 이 모듈은 **원문 글자로 확인되는 사실**만 본다 —
  숙소 말 · 이동 말 · 정답표의 이름. 모델이 「숙소」라고 했거나 원문에 숙소 말이 있으면 숙소다. 원문에 없는 이름을 만들지 않는다.
★말은 표(`config/seoul_landmarks.yaml`)에 있다 — 코드에 박지 않는다. 표가 없거나 깨지면 빈 표다(옛 길로 찾는다).
"""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from app.core.settings import REPO_ROOT

from .places import normalize_full

log = logging.getLogger(__name__)

LANDMARKS_PATH = REPO_ROOT / "config" / "seoul_landmarks.yaml"
_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

#: 이동 수단 말 — 이 말로 시작해 이동 말로 끝나는 줄은 **장소가 아니다**(「택시로 이동」). 수단 이름이라 표가 아니라 여기 둔다(이동 판정의 수단 목록과 같은 뜻)
_MODE = (r"(?:카카오\s*택시|택시|지하철|전철|버스|공항\s*철도|공항\s*버스|리무진\s*버스|리무진|AREX|KTX|SRT|ITX|기차|열차|"
         r"도보|걸어서|따릉이|자전거|렌터카|렌트카|자차|자가용|차|셔틀\s*버스|셔틀)")
_PARTICLE = r"(?:(?:으로|로)(?:\s*(?:타고서|타고|타서))?|(?:을|를)?\s*(?:타고서|타고|타서))?"
_MOVE_ONLY = re.compile(rf"^\s*{_MODE}\s*{_PARTICLE}\s*(?:이동(?:하기|함|해요|합니다)?|가기|간다|가요|출발|탑승|환승)?\s*$", re.IGNORECASE)
#: 「공항철도 타고 인천공항」 · 「택시로 김포공항」 — 앞의 수단 말을 떼고 남은 말이 목적지다.
#: ★수단 말과 목적지 사이에 「로 · 타고」가 **있어야** 한다 — 「차 마시고 인사동」의 「차」는 수단이 아니다(「걸어서」만 이어 주는 말 없이 쓴다)
_MOVE_LEAD = re.compile(rf"^\s*(?:(?P<mode>{_MODE})\s*(?:(?:으로|로)(?:\s*(?:타고서|타고|타서))?|(?:을|를)?\s*(?:타고서|타고|타서))|(?P<walk>걸어서))"
                        r"\s+(?P<dest>\S.*?)\s*(?:으로|로|까지|에)?\s*(?:이동|가기|출발)?\s*$", re.IGNORECASE)
#: 이동의 끝점(공항 · 역 · 터미널) — 수단 말 뒤에 이것이 오면 그 줄은 **이동**이다(방문할 장소가 아니다)
_TRANSIT_END = re.compile(r"(?:공항|국제공항|터미널|기차역|버스터미널|정류장|역)$")


@dataclass(frozen=True)
class Hours:
    source: str
    checked: str
    week: dict[str, Any] = field(default_factory=dict)
    closed: tuple[str, ...] = ()
    seasons: tuple[dict[str, Any], ...] = ()
    always_open: bool = False
    varies: str | None = None
    conditions: tuple[str, ...] = ()            # 방문 전에 알아야 할 조건(후원 예약 · 비 오면 잠김) — 휴무 줄에 「확인해 주세요」로 보인다
    notes: tuple[str, ...] = ()                 # 출처끼리의 차이 같은 기록 — 화면 조건으로 띄우지 않는다


@dataclass(frozen=True)
class Landmark:
    name: str
    kind: str                                  # place · zone · lodging
    accept: tuple[str, ...] = ()               # 자료가 이 이름으로 내도 같은 곳으로 받는다(「창덕궁과 후원」 = 「창덕궁」)
    hours: Hours | None = None

    def same_place(self, found_name: str | None) -> bool:
        """자료가 낸 이름이 이 대표 장소인가 — 정답 이름 · 받는 이름과 **정확히** 같을 때만(지점 표시 · 띄어쓰기만 무시)."""
        key = normalize_full(found_name or "")
        return bool(key) and key in {normalize_full(n) for n in (self.name, *self.accept)}


@dataclass(frozen=True)
class Table:
    by_alias: dict[str, Landmark] = field(default_factory=dict)
    by_name: dict[str, Landmark] = field(default_factory=dict)
    lodging_words: frozenset[str] = frozenset()
    lodging_suffixes: tuple[str, ...] = ()
    lodging_brands: tuple[str, ...] = ()
    lodging_strip: frozenset[str] = frozenset()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Table":
        by_alias: dict[str, Landmark] = {}
        by_name: dict[str, Landmark] = {}
        for entry in raw.get("landmarks") or []:
            hours = entry.get("hours")
            landmark = Landmark(
                str(entry["name"]), str(entry.get("kind") or "place"), tuple(str(a) for a in entry.get("accept") or ()),
                Hours(str(hours.get("source") or ""), str(hours.get("checked") or ""), dict(hours.get("week") or {}),
                      tuple(str(d) for d in hours.get("closed") or ()), tuple(dict(s) for s in hours.get("seasons") or ()),
                      bool(hours.get("always_open")), hours.get("varies"), tuple(str(c) for c in hours.get("conditions") or ()),
                      tuple(str(n) for n in hours.get("notes") or ()))
                if isinstance(hours, dict) else None)
            for alias in [landmark.name, *(entry.get("aliases") or [])]:
                by_alias.setdefault(normalize_full(str(alias)), landmark)
            for name in (landmark.name, *landmark.accept):
                by_name.setdefault(normalize_full(name), landmark)
        lodging = raw.get("lodging") or {}
        return cls(by_alias, by_name,
                   frozenset(normalize_full(str(w)) for w in lodging.get("words") or ()),
                   tuple(normalize_full(str(w)) for w in lodging.get("suffixes") or ()),
                   tuple(normalize_full(str(w)) for w in lodging.get("brands") or ()),
                   frozenset(normalize_full(str(w)) for w in lodging.get("strip") or ()))


_lock = threading.Lock()
_cached: Table | None = None


def load_table(path: Path | None = None) -> Table:
    """표를 읽는다 — 한 번 읽고 기억한다(`reset()`). 파일이 없거나 깨지면 **빈 표**(옛 길로 찾는다 — 계획 읽기를 막지 않는다)."""
    global _cached
    if path is not None:
        return _read(path)
    with _lock:
        if _cached is None:
            _cached = _read(LANDMARKS_PATH)
        return _cached


def _read(path: Path) -> Table:
    try:
        return Table.from_dict(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    except Exception:                              # noqa: BLE001 — 표 장애가 계획 읽기를 막지 않는다
        log.warning("seoul landmarks table unreadable path=%s", path, exc_info=True)
        return Table()


def reset() -> None:
    """시험용 — 기억한 표를 비운다."""
    global _cached
    with _lock:
        _cached = None


# ── 대표 장소 ───────────────────────────────────────────────────────
@dataclass(frozen=True)
class LandmarkHit:
    landmark: Landmark
    phrase: str                                 # 원문에서 대표 장소를 가리킨 조각(「남산타워」)
    rest: tuple[str, ...]                        # 그 조각 밖의 말(「명동」 · 「점심」 · 「빈대떡」)


def find_landmark(title: str | None, table: Table | None = None) -> LandmarkHit | None:
    """원문 조각 안의 대표 장소 — 띄어 쓴 조각을 **이어 붙인 가장 긴 덩이**가 별칭과 같으면 그것(「명동 롯데호텔 서울」 → 롯데호텔 서울).
    덩이가 여럿이면 긴 것, 같은 길이면 앞의 것. 없으면 None."""
    table = table or load_table()
    words = (title or "").split()
    if not words or not table.by_alias:
        return None
    for size in range(len(words), 0, -1):
        for start in range(0, len(words) - size + 1):
            phrase = " ".join(words[start:start + size])
            landmark = table.by_alias.get(normalize_full(phrase))
            if landmark is not None:
                return LandmarkHit(landmark, phrase, tuple(words[:start] + words[start + size:]))
    return None


def landmark_named(name: str | None, table: Table | None = None) -> Landmark | None:
    """자료가 낸 장소 이름이 표의 대표 장소인가(운영시간 대체에 쓴다)."""
    return (table or load_table()).by_name.get(normalize_full(name or ""))


# ── 숙소 말 ────────────────────────────────────────────────────────
def is_lodging_text(text: str | None, table: Table | None = None) -> bool:
    """원문 조각에 숙소 말이 있나 — 조각이 숙소 말과 같거나(「호텔」 · 「체크인」), 끝이 숙소 말이거나(「경복궁스테이」), 숙소 상표로 시작한다(「트레블로지」).
    ★「호텔 조식」도 숙소다(장소는 숙소 안 — 일정 종류는 식사로 따로 남는다)."""
    table = table or load_table()
    for word in re.split(r"[\s,·/()]+", text or ""):
        key = normalize_full(word)
        if len(key) < 2:
            continue
        if key in table.lodging_words or any(key.endswith(s) for s in table.lodging_suffixes) \
                or any(key.startswith(b) for b in table.lodging_brands):
            return True
    return False


def lodging_query(title: str, table: Table | None = None) -> str:
    """숙소 줄에서 찾을 이름 — 이름이 아닌 숙소 말(「숙소」 · 「체크인」)을 뗀다. 다 떼면 원문 그대로(이름 없는 줄은 앞 단계가 다룬다)."""
    table = table or load_table()
    kept = [w for w in title.split() if normalize_full(w) not in table.lodging_strip]
    return " ".join(kept) if kept else title


def is_only_stay_words(text: str, table: Table | None = None) -> bool:
    """숙소 동작 · 일반 말(「체크아웃」 · 「숙소」 · 「호텔」)뿐이라 찾을 숙소 이름이 없는가."""
    table = table or load_table()
    words = [normalize_full(w) for w in (text or "").split()]
    return bool(words) and all(w in table.lodging_strip or w in table.lodging_words for w in words)


# ── 이동 말 ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class MoveText:
    mode: str | None                            # 원문의 수단 말(「택시」 · 「공항철도」)
    destination: str | None                     # 수단 말 뒤의 목적지(「인천공항」) — 없으면 None
    is_move: bool                               # True 면 방문할 장소가 아니라 이동이다 — 장소를 찾지 않는다


def read_move(title: str | None) -> MoveText | None:
    """원문 조각이 이동을 적은 말인가.
        「택시로 이동」 · 「지하철 타고」          → 이동(목적지 없음)
        「공항철도 타고 인천공항」 · 「택시로 김포공항」 → 이동(끝점이 공항 · 역 · 터미널)
        「따릉이 타고 한강」                        → 이동이 아니다 — 목적지(한강)를 장소로 찾는다(`destination`)
    수단 말로 시작하지 않으면 None(「버스킹」 · 「차 마시기」는 수단 말 뒤가 이동 말이 아니라 해당하지 않는다)."""
    text = (title or "").strip()
    if not text:
        return None
    if _MOVE_ONLY.match(text):
        mode = re.match(_MODE, text, re.IGNORECASE)
        return MoveText(mode.group(0) if mode else None, None, True)
    lead = _MOVE_LEAD.match(text)
    if lead is None:
        return None
    dest = lead.group("dest").strip()
    if len(dest) < 2:
        return None
    return MoveText(lead.group("mode") or lead.group("walk"), dest, bool(_TRANSIT_END.search(normalize_full(dest))))


#: 원문의 수단 말 → 확인 화면이 고를 수 있는 구간 수단(`review.MOVE_MODES` — 지하철 · 버스 · 택시 · 도보). 화면 칸이 없는 수단은 None
_SCREEN_MODE = (("taxi", r"택시"), ("subway", r"지하철|전철|공항\s*철도|AREX"), ("bus", r"버스|리무진|셔틀"), ("walk", r"도보|걸어서"))


def move_mode(mode_text: str | None) -> str | None:
    """「택시」 · 「공항철도」 · 「걸어서」 → taxi · subway · walk. 자전거 · 렌터카 · 기차처럼 화면 칸이 없는 수단은 None(구간에 넣지 않는다)."""
    for mode, words in _SCREEN_MODE:
        if mode_text and re.search(words, mode_text, re.IGNORECASE):
            return mode
    return None


# ── 운영시간 ────────────────────────────────────────────────────────
def hours_attributes(landmark: Landmark, day: date) -> tuple[dict[str, Any] | None, list[str]]:
    """그날의 운영시간을 판정기가 읽는 모양(`hours_week`)으로 — `(속성, 조건 문장)`. 표에 그날 값이 없으면 `(None, 조건)`.
    `varies`(점포마다 다름)는 값을 만들지 않는다 — `(None, [이유])`."""
    hours = landmark.hours
    if hours is None or hours.varies:
        return None, ([str(hours.varies)] if hours and hours.varies else [])
    conditions = list(hours.conditions)
    key = _DAYS[day.weekday()]
    if key in hours.closed:
        return {"hours_week": {key: "closed"}}, conditions
    if hours.always_open:
        return {"hours_week": {key: {"open": "00:00", "close": "23:59"}}}, conditions
    for season in hours.seasons:
        if day.month in season.get("months", ()):
            entry = {"open": season["open"], "close": season["close"],
                     **({"last_entry": season["last_entry"]} if season.get("last_entry") else {})}
            return {"hours_week": {key: entry}}, conditions
    week = hours.week
    entry = week.get(key) or (week.get("weekend") if key in ("sat", "sun") else None)
    if isinstance(entry, dict) and entry.get("open") and entry.get("close"):
        return {"hours_week": {key: dict(entry)}}, conditions
    return None, conditions


__all__ = ["Hours", "Landmark", "LandmarkHit", "MoveText", "Table", "find_landmark", "hours_attributes", "is_lodging_text",
           "is_only_stay_words", "landmark_named", "load_table", "lodging_query", "move_mode", "read_move", "reset"]

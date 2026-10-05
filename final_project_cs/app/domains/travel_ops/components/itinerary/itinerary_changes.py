# -*- coding: utf-8 -*-
"""일정을 **어떻게 바꿀지 계산만** 한다 — DB 도 바깥 소스도 부르지 않는다.

★왜 뺐나(`[결정 2026-09-17]`). 이 계산은 두 곳이 쓴다.

    시나리오용 여행 버전   trip_watch.py(감시) · trip_desk.py(신고·재요청)  → 계산 후 직접 쓴다
    Case 버전             activity · dining · mobility Team               → 계산 후 제안으로 낸다

  두 벌로 두면 문구와 판단이 조용히 갈린다(RULE §3.3 — 같은 기능의 두 구현 금지).
  그래서 계산은 여기 하나만 두고, 읽기와 쓰기는 부르는 쪽이 한다.
  옮기기 전 원본: `legacy/final_project_cs/app/domains/travel_ops/components/conversation/trip_desk.py`·`trip_watch.py`.

★입력은 **이미 읽은 값**이다(항목·장소·점검 결과). 점검을 다시 해야 하는 자리(대안 재검증)만
  `check` 콜러블을 받는다 — 시나리오 버전은 점검기를 직접, Team 은 읽기 도구를 넣는다.

★결과는 둘 중 하나다.
    ItineraryChange  새 일정 버전으로 쓸 것(바꾼 항목 · 원인 · 통지)
    NoChange         바꾸지 않는 이유(status 는 옮기기 전 반환값과 같은 문자열)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import UUID

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.itinerary.itinerary_checks import seoul
from app.domains.travel_ops.components.planning.replan import (SEATING_BUFFER_MIN, WALK_M_PER_MIN, DiningStateLookup, activity_candidates, alternate_record,
                     apply_google_prices, brand_of, change_notice, choose, dining_candidates, dining_fits, dining_notice,
                     route_candidates, route_notice, store_candidates)

#: 구글 가격 조회 — 장소 목록 → {place_id: {level, low, high}}. ★선택 기능(스위치 기본 꺼짐 — `replan` 머리말)
PriceLookup = Callable[[list[dict[str, Any]]], "dict[str, dict[str, int | None] | None] | None"]

#: 대안 식당을 찾는 반경(미터). ★우리가 고른 값이다 — 도보 약 9분.
DINING_RADIUS_M = 700
#: 새벽에 닫힌 것을 확인한 활동의 대체를 찾는 거리. ★우리가 고른 값(2026-09-28) — 기상 대체(600m, 같은 건물·근처
#: 실내로 피한다)보다 넓다. 원인이 날씨가 아니라 「그날 안 연다」라 근처 실내일 필요가 없고, 대체 후보는 **그날 그 시각에
#: 연다고 아는 곳**만 남아 좁은 반경이면 거의 비었다
ACTIVITY_CLOSED_RADIUS_M = 1500


@dataclass
class ItineraryChange:
    """새 일정 버전 하나. `replacements` 는 바뀌는 항목만, `full_items` 는 되돌림처럼 통째로 쓸 때."""

    reason: str
    causes: list[dict[str, Any]]
    notice: dict[str, Any]
    replacements: dict[UUID, Item] = field(default_factory=dict)
    full_items: list[Item] | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    #: ★`[2026-10-03]` 같은 문제를 푸는 **다음 순위 안**들(최대 2) — 최고 안이 일정 **전체** 재판정에 걸리면 앞에서부터 같은 판정에 넣어 통과하는 첫 안을 쓴다(`itinerary_fit.fit_change`).
    #:  각 안은 알림 · 「다른 안」 목록까지 완성된 변경이다(그 안보다 **낮은** 순위만 다른 안으로 보인다 — 이미 안 맞는다고 본 안을 고객에게 다른 안으로 보이지 않는다).
    fallbacks: list["ItineraryChange"] = field(default_factory=list)

    def new_items(self, current: list[Item]) -> list[Item]:
        if self.full_items is not None:
            return list(self.full_items)
        out = [self.replacements.get(item.item_id, item) for item in current]
        return refresh_moves_around(current, out, self.replacements)


def _with_fallbacks(build: Callable[[Any, list[Any]], "ItineraryChange"], ranked: list[Any]) -> "ItineraryChange":
    """순위순 후보 목록 → 최고 안의 변경 + 다음 순위 안들의 변경. 각 안의 「다른 안」은 **그보다 낮은 순위**만이다(이미 안 맞는다고 본 위 순위 안은 안 보인다)."""
    change = build(ranked[0], ranked[1:])
    change.fallbacks = [build(ranked[i], ranked[i + 1:]) for i in range(1, len(ranked))]
    return change


def _leg_place(item: Item) -> dict[str, Any] | None:
    p = item.place or {}
    if p.get("latitude") is None or p.get("longitude") is None:
        return None
    return {"key": str(p.get("place_id") or item.place_id), "name": p.get("name") or item.title,
            "lat": float(p["latitude"]), "lon": float(p["longitude"])}


def _basis_of(move: Item, basis: str, travel_min: int | None) -> dict[str, Any]:
    """이동 항목의 산출 근거(`detail.planner`)를 새 상태에 맞게 — 옛 근거가 남으면 채팅(`trip_facts._move_line`)이 어림값
    경로를 「시간표 판정」이라고 답한다(장소를 바꾼 뒤 실제로 그랬다). 시각 계산 칸(day·leave_rule 등)은 그대로 둔다."""
    old = dict(move.detail.get("planner") or {})
    out = {**old, "transfer_basis": basis}
    if travel_min is not None:
        out["travel_min"] = travel_min
    return out


def refresh_moves_around(before: list[Item], after: list[Item], replacements: dict[UUID, Item]) -> list[Item]:
    """☆`[2026-09-29 이동 계산기 문제목록 #44]` 장소가 바뀐 항목의 **바로 앞뒤 이동**을 새 장소 기준으로 다시 만든다.

    앞 판은 장소 항목만 바꾸고 이동 항목은 옛 장소로 가는 경로(탈 노선 uses · 소요)를 그대로 둬, 식당을 바꿨는데
    출발 안내가 옛 경로로 나갔다. 이동 계산기가 켜져 있으면 시간표로 다시 판정하고(출발·도착·경로), 못 하면
    옛 노선 정보를 떼고 직선 어림값 경로(추정 · uses 없음)로 바꾼다 — 옛 경로를 새 장소의 경로처럼 두지 않는다.
    시각은 계산기가 채울 때만 바꾼다(어림값으로 일정을 옮기지 않는다).

    ☆`[2026-09-29 오후 — 실서버 결함]` 앞 판은 새 장소가 옛 장소에서 **걸어갈 거리 안이면 이동을 통째로 건너뛰어**
      제목·목적지가 옛 장소로 남았다(여행 f81afc61… — 일품당프리미엄 → 7 m 옆 금용문으로 바꿨는데 이동 제목이
      「… → 일품당프리미엄」, 출발 알림도 옛 이름). v11 §6-C 재계획 2번(영향 범위는 깨진 항목의 앞뒤 이동까지) ·
      4번(이동은 고른 조합에 맞춰 새로 만들고 옛 경로를 재사용하지 않는다)에 따라 **거리와 상관없이 늘 새 판**을 만든다.
        · 계산기가 켜져 있으면 가까워도 새 장소로 다시 판정한다
        · 계산기가 꺼져 있거나 못 찾을 때 — 걸어갈 거리 안이면 탈 노선(uses)·소요·시각은 둔다(같은 역 권역이라
          여전히 맞다 · 시나리오의 90 m·450 m 교체). 제목·목적지 이름은 새 장소로 바꾸고, 옛 경로를 둔 것을
          `route_basis: "kept_nearby"` 로 드러낸다. 멀면 종전대로 어림값.
    """
    from app.domains.travel_ops.components.planning.replan import distance_m, walk_minutes
    olds = {i.item_id: i for i in before}
    # 「옛 경로를 둘 수 있는 거리」 = 이동 계산기의 도보 상한(guardrails mobility.limits.walk_m.default) — 새 수치를 만들지 않는다
    from app.domains.travel_ops.instances.mobility.engine.guardrails import GuardrailMissing, lookup
    try:
        keep_m = float(lookup("mobility.limits.walk_m.default"))
    except GuardrailMissing:
        keep_m = 0.0                                     # 못 읽으면 늘 어림값으로(보수적)

    def moved_far(old_id: UUID, new: Item) -> bool:
        a, b = _leg_place(olds[old_id]) if old_id in olds else None, _leg_place(new)
        if a is None or b is None:
            return True
        return distance_m({"latitude": a["lat"], "longitude": a["lon"]},
                          {"latitude": b["lat"], "longitude": b["lon"]}) > keep_m

    changed = {old_id: moved_far(old_id, new) for old_id, new in replacements.items()
               if new.kind != "mobility" and old_id in olds and olds[old_id].place_id != new.place_id}
    if not changed:
        return after
    seq_sorted = sorted(after, key=lambda i: i.seq)
    far_of_new = {replacements[i].item_id: far for i, far in changed.items()}
    targets: dict[int, bool] = {}                      # 이동 자리 → 옆의 바뀐 장소 중 하나라도 멀리 갔나
    for k, it in enumerate(seq_sorted):
        if it.item_id in far_of_new:
            for j in (k - 1, k + 1):
                if 0 <= j < len(seq_sorted) and seq_sorted[j].kind == "mobility":
                    targets[j] = targets.get(j, False) or far_of_new[it.item_id]
    if not targets:
        return after
    from app.domains.travel_ops.instances.mobility.wiring import leg_planner
    engine = leg_planner(None, {})
    fresh: dict[UUID, Item] = {}
    for j, far in sorted(targets.items()):
        move = seq_sorted[j]
        prev = next((i for i in reversed(seq_sorted[:j]) if i.kind != "mobility"), None)
        nxt = next((i for i in seq_sorted[j + 1:] if i.kind != "mobility"), None)
        a, b = (_leg_place(prev) if prev else None), (_leg_place(nxt) if nxt else None)
        if a is None or b is None:
            continue
        got = None
        if engine is not None:
            got, _why = engine(a, b, nxt.starts_at, prev.ends_at or prev.starts_at)
        if got is not None:
            detail = {**move.detail, "route_def": got["route"], "refreshed_for": "place_changed",
                      "route_basis": "rejudged",
                      "planner": _basis_of(move, "시간표 판정(이동 계산기)", int(got["eta_min"]))}
            detail.pop("route", None)
            detail.pop("option", None)
            fresh[move.item_id] = move.replaced_by(place=None, title=f"{a['name']} → {b['name']}",
                                                   starts_at=got["starts_at"], ends_at=got["ends_at"], detail=detail)
        elif not far:
            # 걸어갈 거리 안 — 탈 노선·소요·시각은 두고 이름만 새 장소로(옛 이름이 출발 알림에 나가지 않게)
            suffix = f" · {move.title.split(' · ', 1)[1]}" if " · " in move.title else ""
            detail = {**move.detail, "refreshed_for": "place_changed", "route_basis": "kept_nearby",
                      "planner": _basis_of(move, "옛 경로 유지 — 새 장소가 걸어갈 거리 안이라 다시 판정하지 않았다 [추정]", None)}
            if isinstance(detail.get("route_def"), dict):
                detail["route_def"] = {**detail["route_def"], "from": a["name"], "to": b["name"]}
            fresh[move.item_id] = move.replaced_by(place=None, title=f"{a['name']} → {b['name']}{suffix}",
                                                   detail=detail)
        else:
            # 일정 짜기의 어림 규칙(planner._transfer_minutes)과 같다 — 도보 환산이 상한을 넘으면 상한 · 「대중교통 권장」
            from app.domains.travel_ops.components.planning.planner import TRANSFER_MAX_MIN
            meters = distance_m({"latitude": a["lat"], "longitude": a["lon"]}, {"latitude": b["lat"], "longitude": b["lon"]})
            m = walk_minutes(meters)
            label = "도보 기준 [추정]" if m <= TRANSFER_MAX_MIN else "대중교통 권장 [추정]"
            basis = (f"직선 {round(meters)}m ÷ 도보 80m/분 [추정]" if m <= TRANSFER_MAX_MIN else
                     f"직선 {round(meters)}m — 도보 {m}분이라 대중교통 구간, {TRANSFER_MAX_MIN}분 상한 [추정]")
            route = {"from": a["name"], "to": b["name"], "planned": "estimate",
                     "options": [{"id": "estimate", "label": label, "eta_min": min(m, TRANSFER_MAX_MIN), "uses": []}]}
            detail = {**move.detail, "route_def": route, "refreshed_for": "place_changed", "route_basis": "estimate",
                      "planner": _basis_of(move, basis, min(m, TRANSFER_MAX_MIN))}
            detail.pop("route", None)
            detail.pop("option", None)
            fresh[move.item_id] = move.replaced_by(place=None, title=f"{a['name']} → {b['name']}", detail=detail)
    return [fresh.get(i.item_id, i) for i in after]


@dataclass
class NoChange:
    status: str
    detail: dict[str, Any] = field(default_factory=dict)


Plan = ItineraryChange | NoChange


# ── 작은 도우미 ────────────────────────────────────────────────
def minutes_between(start: datetime, end: datetime | None, default: int = 60) -> int:
    return default if end is None else int((end - start).total_seconds() // 60)


def object_particle(word: str) -> str:
    """을/를. 마지막 글자가 한글이 아니면 「을(를)」로 둔다 — 틀리게 붙이지 않는다."""
    last = word.strip()[-1:] if word.strip() else ""
    if not ("가" <= last <= "힣"):
        return "을(를)"
    return "을" if (ord(last) - 0xAC00) % 28 else "를"


def round_up_5(moment: datetime) -> datetime:
    extra = (-moment.minute) % 5
    return (moment + timedelta(minutes=extra)).replace(second=0, microsecond=0)


def with_request(cause: dict[str, Any], request_id: str | None) -> dict[str, Any]:
    return {**cause, "request_id": request_id} if request_id else cause


def option_label(item: Item) -> str:
    """이동 항목 제목 「A → B · 수단」에서 수단 부분."""
    return item.title.split(" · ", 1)[1] if " · " in item.title else item.title


def applied_record(item: Item) -> dict[str, Any]:
    """지금 적용된 항목을 「다른 안」 하나로 적는다 — 바꾼 뒤 되돌아올 수 있게."""
    mobility = item.kind == "mobility"
    return {"key": (item.detail.get("option") if mobility else None)
            or (str(item.place_id) if item.place_id else str(item.item_id)),
            "name": option_label(item) if mobility else (item.place or {}).get("name", item.title),
            "place_id": None if mobility or item.place_id is None else str(item.place_id),
            "option": item.detail.get("option") if mobility else None,
            "option_label": option_label(item) if mobility else None,
            "starts_at": item.starts_at.isoformat(),
            "ends_at": item.ends_at.isoformat() if item.ends_at else None,
            "walk_min": None,
            **({"card_payment": item.detail["card_payment"]} if item.detail.get("card_payment") is not None else {}),
            **({"warnings": list(item.detail["warnings"])} if item.detail.get("warnings") else {}),
            # ★`[2026-10-05]` 이 항목을 고른 이유 한 줄(활동 대체 때만 있다)
            **({"reason": item.detail["pick_reason"]} if item.detail.get("pick_reason") else {})}


def title_for(item: Item, name: str) -> str:
    # ★`[2026-09-29 ui 세션 지적]` 원래 제목 모양을 따른다 — 일정 짜기는 가게 이름만 쓰는데(「일품당프리미엄」) 바꾼 항목만
    #   「광화문 세종클럽 식사」라 한 여행 안에서 모양이 갈렸다. 원래 제목이 장소 이름 그대로면 새 이름만 쓴다
    if item.kind in ("activity", "dining") and item.title.strip() == str((item.place or {}).get("name") or "").strip():
        return name
    if item.kind == "activity":
        return f"{name} 관람"
    if item.kind == "dining":
        return f"{name} 식사"
    if item.kind == "mobility":
        return f"{item.title.split(' · ', 1)[0]} · {name}"
    return name


def next_after(items: list[Item], item: Item) -> Item | None:
    later = [other for other in items if other.seq > item.seq]
    return min(later, key=lambda other: other.seq) if later else None


def place_before(items: list[Item], item: Item) -> Item | None:
    """이 항목 앞의 **장소 항목**(이동 아님) — 경로를 다시 찾을 때 출발지(#38·#39)."""
    earlier = [other for other in items if other.seq < item.seq and other.kind != "mobility"]
    return max(earlier, key=lambda other: other.seq) if earlier else None


def unused_places(places: list[dict[str, Any]], items: list[Item] | None, current: Item | None) -> list[dict[str, Any]]:
    """대체 후보에서 **같은 여행에 이미 들어 있는 장소**를 뺀다(바꾸려는 항목 자신은 남긴다 — 원래 곳은 각 계산이 뺀다).

    ★`[2026-09-29 ui 세션 지적]` 점심을 바꿨더니 같은 날 18:00 저녁 식당(일품당프리미엄)이 골라져 하루에 같은 식당이
      두 번 들어갔다. 일정 짜기의 규칙(「같은 곳을 이틀 넣지 않는다」 — `planner.py` 의 `used`)과 같게 **여행 전체**로 본다.
    ★같은 식당이 다른 장소 행으로 있을 수 있다(여행 전용 행 · 공용 행 · 원장 연결) — id 와 함께 **이름**과
      원장 식별자(`dining_place_uid`)로도 가린다.
    """
    others = [i for i in (items or []) if i is not current and i.kind != "mobility" and i.place]
    if not others:
        return places
    ids = {str(i.place["place_id"]) for i in others}
    names = {str(i.place.get("name") or "").strip() for i in others} - {""}
    uids = {str((i.place.get("attributes") or {}).get("dining_place_uid") or "") for i in others} - {""}
    return [p for p in places
            if str(p["place_id"]) not in ids and str(p.get("name") or "").strip() not in names
            and str((p.get("attributes") or {}).get("dining_place_uid") or "") not in uids]


#: 같은 곳으로 보는 거리(미터) — ★우리가 고른 값(2026-09-29). 경복궁 · 건청궁(경복궁 안 전각)의 좌표가 약 10m 떨어져 있었다.
#:  ☆처음 150m 로 두었더니 확정 시나리오의 「전망대 → 90m 옆 아쿠아리움」(같은 건물의 **다른** 활동)까지 막았다 — 좌표가
#:  사실상 같은 곳만 본다
SAME_SITE_M = 30
#: 이름 첫 낱말이 겹칠 때 같은 곳으로 보는 거리 — 「창덕궁과 후원」 · 「창덕궁 다래나무」(약 1km). ★우리가 고른 값
SAME_NAME_SITE_M = 1500


def _site_word(name: str) -> str:
    import re

    word = re.split(r"[\s\[\(]", (name or "").strip(), maxsplit=1)[0]
    return re.sub(r"[과와의]$", "", word)


def same_site(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """두 활동 장소가 **같은 곳**인가 — 한쪽이 다른 쪽 안에 있는 곳(경복궁 ↔ 건청궁, 창덕궁과 후원 ↔ 창덕궁 다래나무).

    ★`[2026-09-29 ui 세션 지적]` 「건청궁 대신 경복궁」으로 바꿨다 — 사실상 같은 곳이다. 셋 중 하나면 같은 곳:
      ①주소가 같다(괄호 · 빈칸 빼고) ②`SAME_SITE_M` 안 ③이름 첫 낱말이 같고(2자 이상) `SAME_NAME_SITE_M` 안.
    ★활동에만 쓴다 — 식당은 같은 건물에 다른 가게가 흔하다.
    """
    import re

    from app.domains.travel_ops.components.planning.replan import distance_m

    def address(place):
        text = (place.get("attributes") or {}).get("address") or place.get("address") or ""
        return re.sub(r"\([^)]*\)|\s+", "", text)

    if address(a) and address(a) == address(b):
        return True
    if None in (a.get("latitude"), a.get("longitude"), b.get("latitude"), b.get("longitude")):
        return False
    meters = distance_m({"latitude": float(a["latitude"]), "longitude": float(a["longitude"])},
                        {"latitude": float(b["latitude"]), "longitude": float(b["longitude"])})
    if meters <= SAME_SITE_M:
        return True
    word_a, word_b = _site_word(a.get("name")), _site_word(b.get("name"))
    return len(word_a) >= 2 and word_a == word_b and meters <= SAME_NAME_SITE_M


class SiteIndex:
    """`same_site` 를 많은 장소에 빨리 — 주소는 사전, 거리는 1.5km 칸으로 나눠 이웃 칸만 본다(판정은 `same_site` 와 같다).
    ☆`[2026-09-29 실측]` 일정 짜기 후보 1,598곳을 서로 다 비교하니 11.6초였다."""

    CELL_DEG = SAME_NAME_SITE_M / 111_000

    def __init__(self) -> None:
        self._addresses: set[str] = set()
        self._cells: dict[tuple[int, int], list[tuple[dict[str, Any], str]]] = {}

    @staticmethod
    def _address(place: dict[str, Any]) -> str:
        import re

        text = (place.get("attributes") or {}).get("address") or place.get("address") or ""
        return re.sub(r"\([^)]*\)|\s+", "", text)

    def _cell(self, place: dict[str, Any]) -> tuple[int, int] | None:
        if place.get("latitude") is None or place.get("longitude") is None:
            return None
        return int(float(place["latitude"]) // self.CELL_DEG), int(float(place["longitude"]) // self.CELL_DEG)

    def seen(self, place: dict[str, Any]) -> bool:
        from app.domains.travel_ops.components.planning.replan import distance_m

        address = self._address(place)
        if address and address in self._addresses:
            return True
        cell = self._cell(place)
        if cell is None:
            return False
        word = _site_word(place.get("name"))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for other, other_word in self._cells.get((cell[0] + dy, cell[1] + dx), ()):
                    meters = distance_m(place, other)
                    if meters <= SAME_SITE_M or (len(word) >= 2 and word == other_word and meters <= SAME_NAME_SITE_M):
                        return True
        return False

    def add(self, place: dict[str, Any]) -> None:
        address = self._address(place)
        if address:
            self._addresses.add(address)
        cell = self._cell(place)
        if cell is not None:
            point = {"latitude": float(place["latitude"]), "longitude": float(place["longitude"])}
            self._cells.setdefault(cell, []).append((point, _site_word(place.get("name"))))


def other_sites(places: list[dict[str, Any]], original: dict[str, Any] | None,
                items: list[Item] | None = None) -> list[dict[str, Any]]:
    """활동 대체 후보에서 원래 장소와 **같은 곳**(`same_site`)을 뺀다. 원래 장소 자신은 남긴다(각 계산이 뺀다).

    ★`[2026-09-29 ui 세션 지적]` `items` 를 주면 **그 일정의 다른 활동과 같은 곳**도 뺀다 — 경복궁을 국립고궁박물관으로
      바꾼 다음 「건청궁도 바꿔」에서 경복궁 안팎이나 이미 든 박물관과 같은 건물이 다시 나오지 않게."""
    if not original:
        return places
    keep = str(original.get("place_id"))
    others = [i.place for i in items or [] if i.kind == "activity" and i.place
              and str(i.place.get("place_id")) != keep]
    return [p for p in places if str(p.get("place_id")) == keep
            or p.get("kind") != "activity"
            or not (same_site(original, p) or any(same_site(o, p) for o in others))]


def _same_activity_site(a, b) -> bool:
    """`choose(distinct=…)` 용 — 두 활동 후보가 같은 곳인가. ★`[2026-10-05]` **같은 브랜드는 한 곳으로 센다** —
    순위가 앞선(가까운) 매장 하나만 남는다. 올리브영 셋이 다른 안 자리를 다 차지하지 않게(활동 팀 `one_per_brand` 규칙)."""
    if not (a.place and b.place):
        return False
    brand = brand_of(a.place)
    return same_site(a.place, b.place) or bool(brand and brand == brand_of(b.place))


# ── 감시 — 활동 ────────────────────────────────────────────────
def plan_activity_adjustment(*, item: Item, report: dict[str, Any], places: list[dict[str, Any]],
                             check: Callable[..., dict[str, Any]], now: datetime,
                             items: list[Item] | None = None,
                             similarity: Callable[[Any, Any], int] | None = None,
                             proposal: bool = False, limit: int | None = None,
                             radius_m: int = 600, distance_first: bool = False) -> Plan:
    """성립 점검이 `disrupted` 인 활동 항목 — 대안 후보 → 탈락·재검증·사전식 비교로 **하나**.

    `similarity` — ★`[2026-09-29]` 활동 팀이 넘기는 「비슷한 정도」 점수(설문 선호 반영). 순위에만 쓴다.
    `proposal` — 고객이 고르는 제안이면 가격·영업시간 모름을 경고로 남긴다(자동 적용은 탈락).
    `limit` — 재점검(후보마다 바깥 점검)을 앞 순위 몇 곳에만 — 관광공사 목록까지 넣으면 후보가 많아 비용이 커진다.
    """
    # ★일정의 장소는 등록 때 사본이라 분류(`catalog_class`)가 없을 수 있다 — 방금 읽은 목록에서 찾아 붙인다
    origin = dict(item.place)
    fresh = next((p for p in places if str(p.get("place_id")) == str(origin.get("place_id"))), None)
    if fresh is not None and fresh.get("catalog_class") and not origin.get("catalog_class"):
        origin["catalog_class"] = fresh["catalog_class"]
    places = unused_places(places, items, item)  # 같은 여행에 이미 있는 곳은 대체 후보가 아니다
    places = other_sites(places, item.place, items)  # 원래 곳 · 일정의 다른 활동과 같은 곳(경복궁 ↔ 건청궁)도 아니다
    causes = report.get("disruptions", [])
    candidates = activity_candidates(original=origin, places=places,
                                     start=item.starts_at, end=item.ends_at, causes=causes,
                                     similarity=similarity, proposal=proposal, radius_m=radius_m,
                                     distance_first=distance_first)
    if limit is not None:
        from app.domains.travel_ops.components.planning.replan import Candidate

        alive = sorted((c for c in candidates if not c.rejected), key=Candidate.rank)
        candidates = alive[:limit] + [c for c in candidates if c.rejected]
    best, alternates, rejected = choose(
        candidates, lambda c: check(place=c.place, starts_at=item.starts_at), distinct=_same_activity_site)
    if best is None:
        # ★못 풀면 부분 반영하지 않는다(§6-C-5). 사람에게 넘길 재료를 남긴다.
        return NoChange("unresolved", {"causes": causes,
                                       "rejected": {c.name: c.rejected for c in rejected}})
    replay = any(cause.get("mode") == "replay" for cause in causes)

    def build(chosen: "Candidate", others: list["Candidate"]) -> ItineraryChange:
        notice = change_notice(original=item.place, replacement=chosen.place,
                               start=item.starts_at, causes=causes,
                               alternates=others, replay=replay)
        replacement = item.replaced_by(
            place=chosen.place, title=title_for(item, chosen.place["name"]),
            detail={"auto_adjusted_at": now.isoformat(),
                    "other_options": notice["other_options"],
                    **({"pick_reason": chosen.reason} if chosen.reason else {}),
                    "alternates": [alternate_record(c) for c in others]})
        return ItineraryChange(reason="auto_adjusted", causes=causes, notice=notice,
                               replacements={item.item_id: replacement},
                               summary={"from": item.place["name"], "to": chosen.place["name"]})

    return _with_fallbacks(build, [best, *alternates])


# ── 감시 — 이동 ────────────────────────────────────────────────
def route_of(item: Item, routes: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """★경로 정의는 항목이 들고 온다(`route_def`). 밖에서 준 `routes` 가 있으면 그것이 먼저다."""
    return (routes or {}).get(str(item.detail.get("route"))) or item.detail.get("route_def")


def route_targets(route: dict[str, Any]) -> list[str]:
    return sorted({target for option in route["options"] for target in option.get("uses", [])})


def planned_option(item: Item, route: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    options = {option["id"]: option for option in route["options"]}
    chosen = str(item.detail.get("option") or route["planned"])
    return chosen, options.get(chosen, {})


def plan_route_adjustment(*, item: Item, following: Item | None, route: dict[str, Any],
                          events: dict[str, Any], now: datetime, previous: Item | None = None) -> Plan:
    """계획한 수단이 쓰는 구간에 사건이 걸렸으면 경로를 다시 고른다. 안 걸렸으면 `clear`.

    ☆`[2026-09-29 이동 계산기 문제목록 #38·#39]` 저장된 후보가 모두 막히면(unresolved) 이동 계산기가 켜져 있고 앞뒤
      장소를 알 때 **사고를 반영해 새 경로를 찾는다**(사건 → 계산기 사고 조건 변환은 뜻이 같은 것만 — wiring).
      출발은 지금·앞 일정 끝 중 늦은 쪽 이후. 옮기지 못한 사건(도로 통제)은 결과에 이름으로 남긴다."""
    chosen, planned = planned_option(item, route)
    hit = {target: events[target] for target in planned.get("uses", []) if target in events}
    if not hit:
        return NoChange("clear")
    causes = [{"category": "route_event", "target": target, **event}
              for target, event in hit.items()]
    candidates = route_candidates(
        route={**route, "planned": chosen}, depart=item.starts_at,
        planned_arrival=item.ends_at or item.starts_at,
        next_start=following.starts_at if following else None, events=events)
    best, alternates, rejected = choose(candidates)
    if best is None:
        rerouted = _engine_reroute(item=item, previous=previous, following=following, events=events, now=now,
                                   causes=causes, rejected=rejected, planned=planned)
        if rerouted is not None:
            return rerouted
        return NoChange("unresolved", {"causes": causes,
                                       "rejected": {c.name: c.rejected for c in rejected}})
    replay = any(cause.get("mode") == "replay" for cause in causes)

    def build(picked: "Candidate", others: list["Candidate"]) -> ItineraryChange:
        notice = route_notice(route={**route, "planned": chosen}, planned=planned, best=picked,
                              alternates=others, rejected=rejected, causes=causes,
                              planned_arrival=item.ends_at or item.starts_at,
                              next_title=following.title if following else None, replay=replay)
        replacement = item.replaced_by(
            place=None, title=f"{route['from']} → {route['to']} · {(picked.option or {}).get('label')}",
            starts_at=picked.starts_at, ends_at=picked.ends_at,
            detail={**item.detail, "option": picked.key,
                    "auto_adjusted_at": now.isoformat(),
                    "other_options": notice["other_options"],
                    "alternates": [alternate_record(c) for c in others]})
        return ItineraryChange(reason="auto_adjusted", causes=causes, notice=notice,
                           replacements={item.item_id: replacement},
                           summary={"from": planned.get("label"),
                                    "to": (picked.option or {}).get("label")})

    return _with_fallbacks(build, [best, *alternates])


def _engine_reroute(*, item: Item, previous: Item | None, following: Item | None, events: dict[str, Any],
                    now: datetime, causes: list[dict[str, Any]], rejected: list, planned: dict[str, Any]
                    ) -> ItineraryChange | None:
    """저장된 후보가 다 막혔을 때 이동 계산기로 사고를 피하는 새 경로를 찾는다. 못 찾으면 None(종전 unresolved)."""
    if previous is None or following is None:
        return None
    from app.domains.travel_ops.instances.mobility import wiring
    from app.domains.travel_ops.components.planning.replan import Candidate
    a, b = _leg_place(previous), _leg_place(following)
    if a is None or b is None:
        return None
    disruptions, unmapped = wiring.disruptions_from_events(events)
    leg = wiring.leg_planner(None, {}, disruptions=disruptions)
    if leg is None:
        return None
    start_floor = max(now, previous.ends_at or previous.starts_at)
    got, _why = leg(a, b, following.starts_at, start_floor)
    if got is None:
        return None
    new_route = got["route"]
    option = next(o for o in new_route["options"] if o["id"] == new_route["planned"])
    best = Candidate(key=option["id"], place=None, changed_items=1, extra_cost_krw=None,
                     shift_minutes=max(0, int((got["ends_at"] - (item.ends_at or item.starts_at)).total_seconds() // 60)),
                     option=dict(option), starts_at=got["starts_at"], ends_at=got["ends_at"])
    notice = route_notice(route=new_route, planned=planned, best=best, alternates=[], rejected=rejected,
                          causes=causes, planned_arrival=item.ends_at or item.starts_at,
                          next_title=following.title, replay=False)
    detail = {**item.detail, "route_def": new_route, "option": best.key, "auto_adjusted_at": now.isoformat(),
              "other_options": notice["other_options"], "alternates": [],
              "rerouted_by": "mobility_engine", **({"unmapped_events": unmapped} if unmapped else {}),
              "planner": _basis_of(item, "시간표 판정(이동 계산기)", int(got["eta_min"]))}
    detail.pop("route", None)                    # 새 경로 정의를 들고 간다 — 옛 routes 키를 가리키지 않는다
    replacement = item.replaced_by(place=None, title=f"{a['name']} → {b['name']} · {option.get('label')}",
                                   starts_at=got["starts_at"], ends_at=got["ends_at"], detail=detail)
    return ItineraryChange(reason="auto_adjusted", causes=causes, notice=notice,
                           replacements={item.item_id: replacement},
                           summary={"from": planned.get("label"), "to": option.get("label"),
                                    "rerouted_by": "mobility_engine"})


# ── 고객 신고 — 식당 ───────────────────────────────────────────
def _dining_change(meal: Item, best, alternates, notice: dict[str, Any], *,
                   reason: str = "customer_report") -> ItineraryChange:
    replacement = meal.replaced_by(
        place=best.place, title=f"{best.name} 식사", starts_at=best.starts_at,
        ends_at=best.ends_at,
        detail={"other_options": notice["other_options"],
                **({"customer_reported": True} if reason == "customer_report" else {}),
                **({"price_compare": best.price_compare} if best.price_compare else {}),
                **({"warnings": list(best.warnings)} if best.warnings else {}),
                **({"card_payment": best.card_payment} if best.card_payment is not None else {}),
                "alternates": [alternate_record(c) for c in alternates]})
    # ★가격은 비교 결과만(`won` · `same_or_lower` · `higher` · `unknown`) — 구글 가격대 원값은 남기지 않는다
    summary = {"to": best.name, **({"price": best.price_compare} if best.price_compare else {}),
               **({"price_basis": best.price_basis} if best.price_basis else {})}
    return ItineraryChange(reason=reason, causes=notice["causes"], notice=notice,
                           replacements={meal.item_id: replacement}, summary=summary)


def plan_delay(*, trip: dict[str, Any], items: list[Item], places: list[dict[str, Any]],
               at: datetime, minutes: int, message: str, request_id: str | None,
               price_lookup: PriceLookup | None = None, state_lookup: DiningStateLookup | None = None) -> Plan:
    """「N분 늦는다」. 다음 식사 항목이 그 도착 시각에 성립하는지 보고, 안 되면 바꾼다."""
    from zoneinfo import ZoneInfo

    kst = ZoneInfo("Asia/Seoul")
    today = at.astimezone(kst).date()
    stops = sorted((i for i in items if i.kind != "mobility"), key=lambda i: i.starts_at)
    if not any(i.starts_at.astimezone(kst).date() == today for i in stops):
        # ★`[2026-09-28]` 늦는다는 말은 **오늘** 일이다. 전에는 여행 전(9-28)의 「30분 늦어요」가 일주일 뒤(10-05) 점심을
        #   30분 늦춰 판정했고, 그 식당 영업시간을 몰라 대체를 찾다 못 찾아 사람 대기로 끝났다(ui 세션 실서버 시험)
        later = [i for i in stops if i.starts_at.astimezone(kst).date() > today]
        first = later[0].starts_at.astimezone(kst) if later else None
        when = (f"다음 일정: {first.month}월 {first.day}일 {first:%H:%M} {later[0].title}. " if first else "남은 일정이 없어요. ")
        return NoChange("not_today", {"text": f"오늘({today.month}월 {today.day}일)은 이 여행의 일정이 없어서 바꾸지 "
                                              f"않았어요. {when}늦으시는 날 다시 알려 주세요."})
    meal = next((i for i in items if i.kind == "dining" and i.starts_at >= at
                 and i.starts_at.astimezone(kst).date() == today), None)
    if meal is None or meal.place is None:
        return NoChange("no_meal", {"message": "늦어지는 시각 뒤에 식사 일정이 없다"})
    places = unused_places(places, items, meal)  # 같은 여행에 이미 있는 곳은 대체 후보가 아니다
    arrival = (meal.starts_at + timedelta(minutes=minutes)).astimezone(kst)       # ★서울 시각 — 알림 문장의 「점심 도착이 HH:MM」도 서울 시계다(DB 세션이 UTC 여도)
    duration = minutes_between(meal.starts_at, meal.ends_at)
    place_id = str(meal.place["place_id"])
    states = (state_lookup([{"place_id": place_id, "at": arrival,
                             "until": arrival + timedelta(minutes=duration)}]) if state_lookup else None) or {}
    fits, why = dining_fits(meal.place, arrival, duration, state=states.get(place_id))
    cause = with_request({"category": "customer_report", "type": "delay", "minutes": minutes,
                          "message": message, "evidence": "고객 신고"}, request_id)
    if fits is True:
        # ★`[2026-10-03 체크리스트 L2]` 이 식사가 괜찮아도 **뒤 일정**이 밀려 겹치거나 문 닫는 시각에 걸릴 수 있다 — 전에는 식사 하나만 보고 「그대로 괜찮아요」로 끝났다.
        #   일정은 바꾸지 않고 무엇이 걸리는지만 알린다(`itinerary_delay`)
        from app.domains.travel_ops.components.itinerary.itinerary_delay import delay_knock_on, knock_on_text

        knocks = delay_knock_on(items, meal, minutes)
        if knocks:
            return NoChange("knock_on", {"arrival": arrival.isoformat(), "text": knock_on_text(meal, minutes, knocks),
                                         "knocked": [knock.sentence() for knock in knocks]})
        return NoChange("still_fits", {"arrival": arrival.isoformat()})
    if fits is None:
        # ★`[2026-10-01 팀]` 확인하지 못했다는 이유만으로 이미 정한 식당을 바꾸지 않는다 — 전에는 영업시간을 몰라 바꾸려다
        #   후보를 못 찾고 끝났다. 바꾸지 않고 확인이 필요하다고 알린다(「사람 대기」가 아니라 고객이 아는 상태로 남긴다)
        return NoChange("needs_check", {
            "arrival": arrival.isoformat(),
            "message": f"{meal.place['name']}의 {seoul(arrival):%H:%M} 도착 시 영업 여부는 확인이 필요해요. "
                       "기존 일정은 바꾸지 않았어요.",
            "warnings": [why]})
    following = next((i for i in items if i.seq > meal.seq), None)
    candidates = dining_candidates(
        original=meal.place, places=places, arrival=arrival, minutes=duration,
        constraints=trip.get("constraints") or {}, radius_m=DINING_RADIUS_M,
        next_start=following.starts_at if following else None, state_lookup=state_lookup)
    if price_lookup is not None:
        apply_google_prices(candidates, original=meal.place, lookup=price_lookup)
    best, alternates, rejected = choose(candidates)
    if best is None:
        return NoChange("unresolved", {"reason": why,
                                       "rejected": {c.name: c.rejected for c in rejected}})
    notice = dining_notice(
        original=meal.place, best=best, alternates=alternates,
        reason=f"점심 도착이 {arrival:%H:%M}(으)로 늦어져 {meal.place['name']}은 {why}",
        cause=cause, after=None, constraint_note="브레이크타임 없는")
    return _dining_change(meal, best, alternates, notice)


def plan_closed(*, trip: dict[str, Any], items: list[Item], places: list[dict[str, Any]],
                at: datetime, message: str, request_id: str | None,
                price_lookup: PriceLookup | None = None, state_lookup: DiningStateLookup | None = None) -> Plan:
    """「오늘 임시휴무」. 지금 식사 항목을 걸어갈 수 있는 대체 식당으로 바꾼다."""
    meal = next((i for i in items if i.kind == "dining"
                 and i.starts_at <= at < (i.ends_at or i.starts_at + timedelta(hours=1))), None)
    if meal is None or meal.place is None:
        return NoChange("no_meal", {"message": "지금 시각에 식사 일정이 없다"})
    places = unused_places(places, items, meal)  # 같은 여행에 이미 있는 곳은 대체 후보가 아니다
    duration = minutes_between(meal.starts_at, meal.ends_at)
    following = next((i for i in items if i.seq > meal.seq), None)
    cause = with_request({"category": "customer_report", "type": "closed_today",
                          "message": message, "evidence": "고객 신고 — 현장 안내문"},
                         request_id)
    # 후보마다 도보 시간이 달라 입장 시각도 다르다 — 후보별 입장 시각(`arrival_for`)을 계산 안에서 잡는다.
    candidates = dining_candidates(
        original=meal.place, places=places, arrival=at, minutes=duration,
        constraints=trip.get("constraints") or {}, radius_m=DINING_RADIUS_M,
        next_start=following.starts_at if following else None, state_lookup=state_lookup,
        arrival_for=lambda walk: round_up_5(at + timedelta(minutes=walk + SEATING_BUFFER_MIN)))
    if price_lookup is not None:
        apply_google_prices(candidates, original=meal.place, lookup=price_lookup)
    best, alternates, rejected = choose(candidates)
    if best is None:
        return NoChange("unresolved", {"rejected": {c.name: c.rejected for c in rejected}})
    after = None
    later_activity = next((i for i in items if i.seq > meal.seq and i.kind == "activity"), None)
    if later_activity and best.ends_at and best.ends_at <= later_activity.starts_at:
        after = later_activity.place["name"] if later_activity.place else later_activity.title
    payment = (trip.get("constraints") or {}).get("payment")
    notice = dining_notice(
        original=meal.place, best=best, alternates=alternates,
        reason=f"{meal.place['name']}이(가) 오늘 임시휴무라고 알려 주셨습니다",
        cause=cause, after=after,
        constraint_note="카드 결제가 가능한" if payment == "card" else None)
    return _dining_change(meal, best, alternates, notice)


# ── 새벽 확인 — 그날 그 시각에 안 연다 (D-020, 2026-09-25) ──────────
def plan_closed_on_day(*, trip: dict[str, Any], items: list[Item], places: list[dict[str, Any]],
                       meal: Item, source: str, detail: str, checked_at: datetime,
                       exclude: set[str] = frozenset(), price_lookup: PriceLookup | None = None,
                       state_lookup: DiningStateLookup | None = None) -> Plan:
    """새벽 확인에서 **계획한 시각에 안 여는** 식당 — 같은 시각에 근처 대체 식당으로 바꾼다.

    ★고객 신고(`plan_closed`)와 다르다 — 그쪽은 고객이 **지금 가게 앞에** 있어 걸어갈 시간만큼 입장을
      뒤로 민다. 여기는 새벽이라 고객이 아직 나서지 않았다 → **계획한 입장 시각 그대로** 찾는다.
    ★근거는 바깥 소스의 판정이다(고객 문장이 아니다). 원인에 소스와 확인 시각을 남긴다.
    """
    if meal.place is None:
        return NoChange("no_meal", {"message": "장소가 없는 식사 일정이다"})
    places = unused_places(places, items, meal)  # 같은 여행에 이미 있는 곳은 대체 후보가 아니다
    duration = minutes_between(meal.starts_at, meal.ends_at)
    following = next((i for i in items if i.seq > meal.seq and i.kind != "mobility"), None)
    cause = {"category": "place_closed", "type": "closed_on_day", "source": source,
             "checked_at": checked_at.isoformat(), "detail": detail,
             "evidence": f"{source} 새벽 확인 — {detail}"}
    candidates = dining_candidates(
        original=meal.place, places=places, arrival=meal.starts_at, minutes=duration,
        constraints=trip.get("constraints") or {}, radius_m=DINING_RADIUS_M,
        next_start=following.starts_at if following else None, exclude=set(exclude), state_lookup=state_lookup)
    if price_lookup is not None:
        apply_google_prices(candidates, original=meal.place, lookup=price_lookup)
    best, alternates, rejected = choose(candidates)
    if best is None:
        return NoChange("unresolved", {"causes": [cause],
                                       "rejected": {c.name: c.rejected for c in rejected}})
    payment = (trip.get("constraints") or {}).get("payment")
    notice = dining_notice(
        original=meal.place, best=best, alternates=alternates,
        reason=(f"{meal.place['name']}이(가) {seoul(meal.starts_at):%m월 %d일 %H:%M}에 영업하지 않는 것으로 "
                f"새벽에 확인했습니다({detail})"),
        cause=cause, after=None,
        constraint_note="카드 결제가 가능한" if payment == "card" else None)
    return _dining_change(meal, best, alternates, notice, reason="auto_adjusted")


#: 낮 감시가 식사 대체 후보를 다시 점검하는 곳 수 — ★우리가 고른 값(2026-09-29). 식당 Team 의 도구 예산(12)
#:  안에서 일정 · 점검 · 장소 목록 · 원장 후보 · 원장 판정(후보마다)을 쓰고 남는 몫이다. 넘으면 「안 봤다」로 떨어뜨린다
#:  (점검 안 한 곳을 「괜찮다」로 고르지 않는다).
DINING_RECHECK_LIMIT = 3
#: ★`[2026-10-02 결함 인계 #1]` 활동 대체의 후보 재점검은 **앞 순위 이 만큼만** — 후보마다 바깥 점검(도구 호출 한 번)을 불러, 후보가 많으면 팀의 도구 예산(`max_steps`)이
#:  바닥나 예외로 터졌다(`ToolBudgetExceeded`). 채팅 「다른 곳」 제안 경로(`pending._consented`)가 이미 쓰던 6 과 같다 — 예산 12 에서 읽기 셋(일정 · 점검 · 목록)을 빼도 6 이 남는다.
ACTIVITY_RECHECK_LIMIT = 6


def plan_dining_disrupted(*, trip: dict[str, Any], items: list[Item], places: list[dict[str, Any]], meal: Item,
                          report: dict[str, Any], check: Callable[..., dict[str, Any]],
                          state_lookup: DiningStateLookup | None = None) -> Plan:
    """★`[2026-09-29 사용자 지적 · ui 세션 전달]` 낮 감시(1분마다, 90분 앞)의 성립 점검이 **식사 항목**을
    `disrupted` 로 본 경우 — 재난문자(화재 · 통제 등 모든 장소에 걸리는 것) · 지진 · 도로 통제.

    ☆왜 — 전에는 감시가 식사 항목을 `unhandled` 로 **세기만** 했다(식당 Team 에 감시 Case 처리가 없었다).
      같은 점검에 걸린 활동은 바꾸면서 바로 옆 식당은 그대로 두었다.
    ★새벽 확인 대체(`plan_closed_on_day`)와 같게 **계획한 입장 시각 그대로** 근처 식당을 찾는다 — 고객은 아직
      그 식당 앞에 있지 않다(90분 앞을 본다). 후보는 요식 원장 먼저, 원래 곳은 뺀다.
    ★후보도 **같은 점검을 다시** 통과해야 한다 — 같은 동에 난 재난문자면 옆집도 걸린다. 순위 순으로 최대
      `DINING_RECHECK_LIMIT` 곳까지 다시 보고, 못 본 곳은 고르지 않는다.
    """
    if meal.place is None:
        return NoChange("no_meal", {"message": "장소가 없는 식사 일정이다"})
    places = unused_places(places, items, meal)  # 같은 여행에 이미 있는 곳은 대체 후보가 아니다
    causes = list(report.get("disruptions") or [])
    duration = minutes_between(meal.starts_at, meal.ends_at)
    following = next((i for i in items if i.seq > meal.seq and i.kind != "mobility"), None)
    used = {"n": 0}

    def recheck(candidate) -> dict[str, Any]:
        if used["n"] >= DINING_RECHECK_LIMIT:
            return {"verdict": "not_checked"}
        used["n"] += 1
        return check(place=candidate.place, starts_at=candidate.starts_at or meal.starts_at)

    # ★순위 순으로 넘긴다 — `choose` 는 받은 순서대로 재점검하므로, 앞 순위부터 봐야 한도 안에서 최선을 고른다
    candidates = sorted(dining_candidates(
        original=meal.place, places=places, arrival=meal.starts_at, minutes=duration,
        constraints=trip.get("constraints") or {}, radius_m=DINING_RADIUS_M,
        next_start=following.starts_at if following else None, exclude={str(meal.place["place_id"])},
        state_lookup=state_lookup), key=lambda c: c.rank())
    best, alternates, rejected = choose(candidates, recheck)
    if best is None:
        return NoChange("unresolved", {"causes": causes, "rejected": {c.name: c.rejected for c in rejected}})
    kinds = ", ".join(sorted({str(c.get("kind") or c.get("category")) for c in causes})) or "운영 상황 변화"
    payment = (trip.get("constraints") or {}).get("payment")

    def build(chosen: "Candidate", others: list["Candidate"]) -> ItineraryChange:
        notice = dining_notice(
            original=meal.place, best=chosen, alternates=others,
            reason=f"{meal.place['name']} 주변에 {kinds} 소식이 있어 {seoul(meal.starts_at):%H:%M} 식사 장소를 바꿨습니다",
            cause=causes[0] if causes else {"category": "disruption"}, after=None,
            constraint_note="카드 결제가 가능한" if payment == "card" else None)
        notice["causes"] = causes or notice["causes"]
        return _dining_change(meal, chosen, others, notice, reason="auto_adjusted")

    return _with_fallbacks(build, [best, *alternates])


def plan_activity_closed_on_day(*, items: list[Item], places: list[dict[str, Any]], item: Item, source: str,
                                detail: str, checked_at: datetime, exclude: set[str] = frozenset()) -> Plan:
    """★`[2026-09-28]` 새벽 확인에서 **그날 안 여는** 활동 — 같은 시각에 근처에서 **그 시각에 연다고 아는** 활동으로.

    ☆왜 — 새벽 확인이 식당만 봤다. 영업시간을 모르는 활동이 쉬는 날에 들어가도 당일까지 아무도 몰랐다
      (「13:00~17:00 · 일~목 휴무」인 곳이 월요일 09:00). 사용자 결정: 최종 판정은 당일 새벽 구글 확인이 한다.
    ★가격을 모르는 후보도 받는다(결정 15 — 불확실해도 하나를 고른다). 기상 대체(`plan_activity_adjustment`)는
      추가 비용을 계산하려고 가격 모름을 탈락시키지만, 여기서 그러면 관광공사 장소가 전부 빠진다(가격 칸이 없다).
      **그 시각 영업**은 그대로 요구한다 — 닫힌 곳을 닫힌 곳으로 바꾸지 않는다.
    """
    if item.place is None:
        return NoChange("no_place", {"message": "장소가 없는 활동이다"})
    places = unused_places(places, items, item)  # 같은 여행에 이미 있는 곳은 대체 후보가 아니다
    places = other_sites(places, item.place, items)  # 원래 곳 · 일정의 다른 활동과 같은 곳(경복궁 ↔ 건청궁)도 아니다
    cause = {"category": "place_closed", "type": "closed_on_day", "source": source,
             "checked_at": checked_at.isoformat(), "detail": detail,
             "evidence": f"{source} 새벽 확인 — {detail}"}
    candidates = [c for c in activity_candidates(original=item.place, places=places, start=item.starts_at,
                                                 end=item.ends_at, causes=[cause],
                                                 radius_m=ACTIVITY_CLOSED_RADIUS_M)
                  if str(c.place["place_id"]) not in {str(x) for x in exclude}]
    for candidate in candidates:
        candidate.rejected = [r for r in candidate.rejected if not r.startswith("가격을 몰라")]
    best, alternates, rejected = choose(candidates, distinct=_same_activity_site)
    if best is None:
        return NoChange("unresolved", {"causes": [cause],
                                       "rejected": {c.name: c.rejected for c in rejected}})
    notice = change_notice(original=item.place, replacement=best.place, start=item.starts_at,
                           causes=[cause], alternates=alternates, replay=False)
    notice["text"] = (f"{item.place['name']}이(가) {seoul(item.starts_at):%m월 %d일 %H:%M}에 운영하지 않는 것으로 새벽에 "
                      f"확인했습니다({detail}). 같은 시각 {best.place['name']}(으)로 바꿨습니다.")
    replacement = item.replaced_by(
        place=best.place, title=title_for(item, best.place["name"]),
        detail={"auto_adjusted_at": checked_at.isoformat(), "other_options": notice["other_options"],
                "alternates": [alternate_record(c) for c in alternates]})
    return ItineraryChange(reason="auto_adjusted", causes=[cause], notice=notice,
                           replacements={item.item_id: replacement},
                           summary={"from": item.place["name"], "to": best.place["name"]})


# ── 고객 신고 — 품절(일정은 안 바꾼다) ─────────────────────────
def plan_nearby_store(*, items: list[Item], places: list[dict[str, Any]], at: datetime,
                      products: list[str], message: str, request_id: str | None) -> dict[str, Any]:
    """품절 상품을 **취급할 만한** 매장을 귀가 동선에서 고른다. 일정은 안 바꾼다.

    ★재고는 확인하지 않는다 — 재고 소스가 없다(§7-C 3단계). 그래서 답에
      `[미확인]` 을 붙인다. 「있다」고 말하지 않는다.
    """
    here_item = next((i for i in items if i.kind == "activity"
                      and i.starts_at <= at < (i.ends_at or at)), None)
    home = next((i.place for i in items if i.place and i.place.get("kind") == "lodging"), None)
    if here_item is None or here_item.place is None or home is None:
        return {"status": "unresolved", "message": "지금 위치나 숙소를 알 수 없다"}
    candidates = store_candidates(here=here_item.place, home=home, places=places,
                                  products=products, at=at)
    best, alternates, rejected = choose(candidates)
    if best is None:
        return {"status": "unresolved", "rejected": {c.name: c.rejected for c in rejected}}
    detour = (best.option or {}).get("detour_m") or 0
    # ★100m 안쪽이면 「돌아가는 거리」를 숫자로 말하지 않는다 — 9m·1분 같은 값은
    #   정밀해 보이지만 좌표 근사에서 나온 잡음이다.
    extra = ("거의 돌아가지 않아도 됩니다" if detour < 100 else
             f"돌아가는 거리 약 {detour}m 추가, 도보 약 {max(1, round(detour / WALK_M_PER_MIN))}분")
    listed = ", ".join(products)
    text = (f"{best.name}이(가) 호텔로 돌아가는 동선 위에 있습니다({extra}). "
            f"{listed}{object_particle(listed)} 취급하는 매장이지만 지금 재고는 확인하지 "
            f"못했습니다[미확인].")
    return {"status": "answered", "text": text, "recommendation": best.name,
            "stock": "unverified", "other_options": [c.name for c in alternates],
            "rejected": {c.name: c.rejected for c in rejected},
            "cause": with_request({"category": "customer_report", "type": "stock_out",
                                   "products": products, "message": message}, request_id)}


# ── 재요청 ① — 다른 안으로 ─────────────────────────────────────
def plan_swap(*, trip_version: int, base_version: int, items: list[Item],
              places_by_id: dict[str, dict[str, Any]], item_id: UUID, choice: str | None,
              message: str | None, request_id: str | None,
              check: Callable[..., dict[str, Any]] | None) -> Plan:
    """적용된 안을 들고 있던 「다른 안」으로 바꾼다. 원래 안은 다시 「다른 안」이 된다.

    ★고객이 **본 버전**(`base_version`)을 기준으로만 바꾼다. 그 사이 일정이 또
      바뀌었으면 `stale` — 고객이 보지 못한 일정 위에 요청을 얹지 않는다.
    """
    if trip_version != base_version:
        return NoChange("stale", {"version": trip_version})
    current = next((i for i in items if i.item_id == item_id), None)
    if current is None:
        return NoChange("not_found")
    alternates = list(current.detail.get("alternates") or [])
    if not alternates:
        return NoChange("no_alternate")
    pick = alternates[0] if choice is None else next(
        (a for a in alternates if a["key"] == choice), None)
    if pick is None:
        return NoChange("unknown_choice", {"choices": [a["key"] for a in alternates]})
    starts = datetime.fromisoformat(pick["starts_at"]) if pick.get("starts_at") else current.starts_at
    ends = datetime.fromisoformat(pick["ends_at"]) if pick.get("ends_at") else current.ends_at
    # ★`[2026-09-29 ui 세션 지적]` 시각을 늦춘 안(조건 풀기 「08:30으로 늦추면」)은 **뒤따르는 이동을 함께 민다** — 전에는 바로 다음
    #   항목(09:00 출발 이동)과 겹친다고 `conflicts_next` 로 막아, 제안에 올린 안을 고를 수 없었다. 이동은 소요를 그대로 두고
    #   새 끝 시각 뒤로 옮기며, 그래도 **다음 장소 일정**에 늦으면 그때 막는다(`shift_moves_after` — 제안을 만들 때도 같은 기준).
    shifted, late_for = shift_moves_after(items, current, ends)
    if late_for is not None:
        return NoChange("conflicts_next", {"next": late_for.title})
    place = places_by_id.get(str(pick["place_id"])) if pick.get("place_id") else None
    if pick.get("place_id") and place is None:
        return NoChange("not_found")
    rechecked = None
    if place is not None and current.kind == "activity" and check is not None:
        # ★계산한 뒤로 시간이 흘렀다 — 그 시각에 다시 점검한다.
        report = check(place=place, starts_at=starts)
        rechecked = (report or {}).get("verdict")
        if rechecked != "clear":
            return NoChange("alternate_invalid", {"verdict": rechecked, "report": report})
    applied = applied_record(current)
    remaining = [a for a in alternates if a is not pick] + [applied]
    name = pick.get("option_label") or pick["name"]
    detail = {**current.detail, "alternates": remaining,
              "other_options": [a["name"] for a in remaining], "customer_requested": True}
    detail.pop("warnings", None)
    if pick.get("warnings"):
        detail["warnings"] = list(pick["warnings"])
    if current.kind == "mobility":
        detail["option"] = pick.get("option") or pick["key"]
    cause = with_request({"category": "customer_request", "type": "alternate",
                          "from": applied["name"], "to": name, "message": message},
                         request_id)
    text = (f"요청하신 대로 {applied['name']} 대신 {name}(으)로 바꿨습니다"
            f"({seoul(starts):%H:%M} 시작).")
    warnings = [f"{name}: {warning}" for warning in pick.get("warnings") or []]
    if warnings:
        text += " " + " ".join(warnings)
    notice = {"text": text, "language": "ko", "causes": [cause],
              "changed": {"from": applied["name"], "to": name, "at": starts.isoformat()},
              "other_options": [a["name"] for a in remaining], "replay": False,
              **({"warnings": warnings} if warnings else {})}
    replacement = current.replaced_by(place=place, title=title_for(current, name),
                                      detail=detail, starts_at=starts, ends_at=ends)
    return ItineraryChange(reason="customer_request", causes=[cause], notice=notice,
                           replacements={current.item_id: replacement, **shifted},
                           summary={"to": name, "rechecked": rechecked})


def shift_moves_after(items: list[Item], current: Item, ends: datetime | None) -> tuple[dict[UUID, Item], Item | None]:
    """`current` 가 `ends` 에 끝나면 — 바로 뒤 이동 항목들을 소요 그대로 뒤로 민다. (민 이동들, 늦게 되는 다음 항목 또는 None).

    ★다음 **장소** 일정은 옮기지 않는다 — 그 시각에 못 닿으면 그 안은 안 된다(부르는 쪽이 막거나 제안에서 뺀다).
    ★이동이 없으면 다음 항목과 바로 비교한다(예전과 같다).
    """
    later = sorted((i for i in items if i.seq > current.seq), key=lambda i: i.seq)
    moves = []
    for item in later:
        if item.kind != "mobility":
            break
        moves.append(item)
    after = next((i for i in later if i.kind != "mobility"), None)
    if ends is None:
        return {}, None
    shifted: dict[UUID, Item] = {}
    cursor = ends
    for move in moves:
        span = (move.ends_at or move.starts_at) - move.starts_at
        start = max(move.starts_at, cursor)
        if start != move.starts_at:
            shifted[move.item_id] = move.replaced_by(place=move.place, title=move.title,
                                                     detail={**move.detail, "shifted_for": "earlier_item_later"},
                                                     starts_at=start, ends_at=start + span)
        cursor = start + span
    if after is not None and cursor > after.starts_at:
        return shifted, after
    return shifted, None


#: 「다른 데로 바꿔 줘」 — 후보가 0곳이면 넓혀 다시 찾는 반경(미터). ★우리가 고른 값(2026-09-29) — 식사 첫 판은 대체 식당
#:  반경(`DINING_RADIUS_M`, 도보 약 9분)과 같고, 3km 는 지하철 두세 정거장 거리다. 설계 문서의 근거는 없다
ALTERNATE_RADII_M = {"dining": (DINING_RADIUS_M, 1500, 3000), "activity": (ACTIVITY_CLOSED_RADIUS_M, 3000)}


#: 조건을 풀어 찾을 때 — 늦추는 시간(분)과 반경(미터). ★우리가 고른 값(2026-09-29): 30분 단위로 두 시간까지, 반경은 식사 둘째 판
RELAX_SHIFTS_MIN = (30, 60, 90, 120)
RELAX_RADIUS_M = 1500
#: 반경을 넓힌 안의 반경 · 고르게 할 안 수 — ★우리가 고른 값(2026-09-29 사용자 요구 「3개를 뽑아 추천」). 5km 는 지하철 네댓 정거장
RELAX_WIDE_M = 5000
RELAX_WANT = 3


def plan_nearby(kind: str, *, trip: dict[str, Any], places: list[dict[str, Any]], origin: dict[str, Any],
                at: datetime, state_lookup: DiningStateLookup | None = None) -> tuple[list[Any], int | None, int]:
    """고객의 **현재 위치**(`origin` — `latitude` · `longitude` 를 가진 가짜 장소) 둘레에서 **지금 갈 수 있는** 곳. `[2026-09-30]`
    돌려주는 것: (후보들 좋은 순 — 최선 + 다른 안, 찾은 반경 m 또는 None, 살펴본 곳 수). `kind` = `dining` | `activity`.

    ★「다른 데로 바꿔」와 같은 후보 계산이다(식당은 요식 원장 판정, 활동은 그 시각 영업) — 다른 것은 **기준점이 좌표**라는 것뿐이다.
      일정을 바꾸지 않는다(부르는 쪽이 목록만 답한다). 반경은 식당 700m → 1.5km → 3km, 활동 1.5km → 3km.
    ★좌표는 여기서 거리 계산에만 쓰고 어디에도 담지 않는다(`trip_here` 머리 — 개인정보)."""
    if kind == "dining":
        minutes = 60
        seen = 0
        for radius in ALTERNATE_RADII_M["dining"]:
            candidates = dining_candidates(
                original=origin, places=places, arrival=at, minutes=minutes,
                constraints=trip.get("constraints") or {}, radius_m=radius, next_start=None, exclude=set(),
                state_lookup=state_lookup)
            best, alternates, rejected = choose(candidates)
            seen = len(rejected) + (1 if best is not None else 0) + len(alternates)
            if best is not None:
                return [best] + list(alternates), radius, seen
        return [], ALTERNATE_RADII_M["dining"][-1], seen
    end = at + timedelta(minutes=90)
    seen = 0
    for radius in ALTERNATE_RADII_M["activity"]:
        candidates = activity_candidates(original=origin, places=places, start=at, end=end, causes=[], radius_m=radius)
        for candidate in candidates:
            candidate.rejected = [r for r in candidate.rejected if not r.startswith("가격을 몰라")]
        best, alternates, rejected = choose(candidates, distinct=_same_activity_site)
        seen = len(rejected) + (1 if best is not None else 0) + len(alternates)
        if best is not None:
            return [best] + list(alternates), radius, seen
    return [], ALTERNATE_RADII_M["activity"][-1], seen


def relaxed_options(*, trip: dict[str, Any], items: list[Item], places: list[dict[str, Any]], current: Item,
                    state_lookup: DiningStateLookup | None = None, exclude: set[str] = frozenset(),
                    causes: list[dict[str, Any]] = ()) -> list[dict[str, Any]]:
    """같은 조건으로 0곳일 때 **조건을 하나씩 풀어** 실제로 되는 안. `[2026-09-29 사용자 지적 — ui 세션 전달]`

    ☆왜 — 「08:00에 갈 수 있는 식당이 3km 안에 없어요」로 끝나면 고객이 할 수 있는 것이 없다. 되는 안을 계산해 준다.
      ① **시각을 늦추기** — 30 · 60 · 90 · 120분 늦춰 처음 되는 시각(다음 일정과 겹치지 않는 범위). 예: 08:00 → 09:00
      ② **다음 일정 근처** — 같은 시각에 다음 일정 장소 둘레에서
      ③ **반경 넓히기** — 같은 시각에 5km 안에서(모자라면 여기서 더 채운다). 셋까지 모아 고르게 한다
    ★고객이 원한 조건을 바꾸는 안이라 **바로 적용하지 않는다** — 부르는 쪽이 묻는다(`pending`, 이유 `relaxed`).
    ★종류를 넓히는 안(아침엔 카페 · 베이커리)은 아직 없다 — 장소 분류로 가를 자료가 정리되면 더한다.
    ★`causes` `[2026-10-03]` — 감시가 부를 때 **깨진 원인**을 넘긴다. 날씨 원인이면 활동 후보는 실내만 본다(`activity_candidates` 와 같은 규칙) — 시각 · 거리를 푸는 것이지 **안전 조건을 푸는 것이 아니다**.
      고객 요청 길은 원인이 없어 전과 같다(빈 목록).
    돌려주는 것: 적용에 필요한 값을 그대로 적은 안(`alternate_record` 모양 + `relaxed` · `note`), 되는 것만.
    """
    following = next((i for i in items if i.seq > current.seq and i.kind != "mobility"), None)
    duration = minutes_between(current.starts_at, current.ends_at)
    original = str(current.place["place_id"])
    constraints = trip.get("constraints") or {}

    def best_at(center: dict[str, Any], start: datetime, radius: int):
        end = start + timedelta(minutes=duration)
        if current.kind == "dining":
            found = dining_candidates(original=center, places=places, arrival=start, minutes=duration,
                                      constraints=constraints, radius_m=radius,
                                      next_start=following.starts_at if following else None,
                                      exclude={original, str(center["place_id"])}, state_lookup=state_lookup)
        else:
            found = [c for c in activity_candidates(original=center, places=places, start=start, end=end, causes=list(causes),
                                                    radius_m=radius)
                     if str(c.place["place_id"]) not in (original, str(center["place_id"]))]
            for candidate in found:
                candidate.rejected = [r for r in candidate.rejected if not r.startswith("가격을 몰라")]
        # `exclude` — 이미 고른 곳(바꾼 뒤의 다른 안을 모을 때 바꾼 곳 · 통과한 나머지)은 다시 내지 않는다
        found = [c for c in found if c.key not in exclude]
        best, alternates, _ = choose(found, distinct=_same_activity_site if current.kind == "activity" else None)
        return ([best] + list(alternates)) if best is not None else [], end

    out: list[dict[str, Any]] = []
    picked: list[Any] = []                          # 고른 후보 — 안 셋이 같은 곳(같은 건물)을 두 번 싣지 않게

    def add(ranked: list, start: datetime, end: datetime, relaxed: str, note: str, take: int) -> None:
        for candidate in ranked[:take]:
            if len(out) >= RELAX_WANT or any(o["key"] == candidate.key for o in out):
                continue
            if current.kind == "activity" and any(_same_activity_site(candidate, other) for other in picked):
                continue
            picked.append(candidate)
            out.append({**alternate_record(candidate), "starts_at": start.isoformat(), "ends_at": end.isoformat(),
                        "relaxed": relaxed, "note": note})

    for shift in RELAX_SHIFTS_MIN:
        start = current.starts_at + timedelta(minutes=shift)
        # ★고를 때(`plan_swap`)와 같은 기준 — 뒤 이동을 밀고도 다음 장소 일정에 닿아야 올린다(고를 수 없는 안을 보이지 않는다)
        if shift_moves_after(items, current, start + timedelta(minutes=duration))[1] is not None:
            break
        ranked, end = best_at(current.place, start, RELAX_RADIUS_M)
        if ranked:
            add(ranked, start, end, "time", f"{seoul(start):%H:%M}으로 늦추면", take=1)
            break
    if following is not None and following.place and following.place.get("latitude") is not None:
        ranked, end = best_at(following.place, current.starts_at, RELAX_RADIUS_M)
        add(ranked, current.starts_at, end, "near_next", f"다음 일정({following.place['name']}) 근처", take=1)
    # ★`[2026-09-29 사용자 요구 — ui 세션 전달]` 반경을 넓힌 안까지 더해 **3개**를 고르게 한다(「범위를 넓혀 찾아서 알려 주고」)
    ranked, end = best_at(current.place, current.starts_at, RELAX_WIDE_M)
    add(ranked, current.starts_at, end, "wider", f"{RELAX_WIDE_M / 1000:g}km 안으로 넓히면", take=RELAX_WANT)
    return out


def _top_reason(rejected: list) -> str | None:
    """떨어진 후보들의 가장 많은 이유 한 줄 — 「그 시각 영업하지 않아서」 같은. 없으면 None."""
    from collections import Counter

    reasons = Counter(r.split(":")[0].split("(")[0].strip() for c in rejected for r in (c.rejected or [])[:1])
    if not reasons:
        return None
    reason, count = reasons.most_common(1)[0]
    return f"{count}곳은 「{reason}」"


# ── 재요청 ①-2 — 들고 있던 안이 없으면 그 자리에서 찾는다 (2026-09-29) ─────────────
def plan_fresh_alternate(*, trip: dict[str, Any], trip_version: int, base_version: int, items: list[Item],
                         places: list[dict[str, Any]], item_id: UUID, message: str | None,
                         request_id: str | None, state_lookup: DiningStateLookup | None = None,
                         price_lookup: PriceLookup | None = None) -> Plan:
    """「다른 데로 바꿔 줘」 — 그 항목에 들고 있던 「다른 안」이 없으면 **지금 후보를 계산해** 하나로 바꾼다.

    ★`[2026-09-29 사용자 지적 · ui 세션 전달]` 전에는 들고 있던 안(`detail.alternates`)만 봐서, 감시가 한 번도 안 고친
      항목(일정 짜기·등록으로 막 만든 것)은 늘 「바꿀 수 있는 다른 안이 없어요」였다. 고객이 달라고 하면 **그때 찾는다.**
    ★계산은 이미 있는 것을 쓴다 — 식사는 `dining_candidates`(요식 원장 판정 `state_lookup` — 같은 시각 · 동선 ·
      동행 조건), 활동은 `activity_candidates` + `choose`(새벽 확인 대체와 같은 방식, 가격 모름은 탈락시키지 않는다 ·
      **그 시각 영업**은 요구한다). 원래 곳은 후보에서 뺀다.
    ★`no_alternate` 는 후보를 **실제로 다 뒤져도** 없을 때만 — 무엇이 왜 떨어졌는지(`rejected`)를 같이 싣는다.
    """
    if trip_version != base_version:
        return NoChange("stale", {"version": trip_version})
    current = next((i for i in items if i.item_id == item_id), None)
    if current is None:
        return NoChange("not_found")
    if current.place is None or current.kind not in ("dining", "activity"):
        return NoChange("no_alternate", {"reason": "장소를 바꿀 수 있는 일정(식사·활동)이 아니다"})
    places = unused_places(places, items, current)  # 같은 여행에 이미 있는 곳은 대체 후보가 아니다
    if current.kind == "activity":
        places = other_sites(places, current.place, items)  # 원래 곳 · 일정의 다른 활동과 같은 곳도 아니다
    cause = with_request({"category": "customer_request", "type": "alternate", "from": current.place["name"],
                          "message": message, "evidence": "고객 요청"}, request_id)
    original = str(current.place["place_id"])
    following = next((i for i in items if i.seq > current.seq and i.kind != "mobility"), None)
    # ★`[2026-09-29 ui 세션 지적]` 0곳이면 **반경을 넓혀 다시** 찾는다 — 700m 는 설계 근거 없는 구현 선택이었고, 08:00 아침처럼
    #   그 시각에 여는 곳이 드문 때 「없어요」가 쉽게 나왔다(실서버 「첫날 아침 일정 바꿔」). 식사 700m → 1.5km → 3km,
    #   활동 1.5km → 3km.
    best, rejected, radius = None, [], 0
    if current.kind == "dining":
        duration = minutes_between(current.starts_at, current.ends_at)
        for radius in ALTERNATE_RADII_M["dining"]:
            candidates = dining_candidates(
                original=current.place, places=places, arrival=current.starts_at, minutes=duration,
                constraints=trip.get("constraints") or {}, radius_m=radius,
                next_start=following.starts_at if following else None, exclude={original},
                state_lookup=state_lookup)
            if price_lookup is not None:
                apply_google_prices(candidates, original=current.place, lookup=price_lookup)
            best, alternates, rejected = choose(candidates)
            if best is not None:
                break
    else:
        for radius in ALTERNATE_RADII_M["activity"]:
            candidates = [c for c in activity_candidates(original=current.place, places=places, start=current.starts_at,
                                                         end=current.ends_at, causes=[cause], radius_m=radius)
                          if str(c.place["place_id"]) != original]
            for candidate in candidates:
                candidate.rejected = [r for r in candidate.rejected if not r.startswith("가격을 몰라")]
            best, alternates, rejected = choose(candidates, distinct=_same_activity_site)
            if best is not None:
                break
    if best is None:
        kind = "식당" if current.kind == "dining" else "활동"
        why = _top_reason(rejected)
        # ★`[2026-09-29 ui 세션 지적]` 「후보가 아예 없음」과 「살펴봤는데 다 떨어짐」을 가른다 — 기록의 rejected 가 {} 이면
        #   어느 쪽인지 알 수 없었다
        # ★`[2026-09-29 ui 세션 지적]` 「살펴본 2곳 중 1곳은 …」처럼 일부만 말하지 않는다 — 셋 이하면 곳마다 이유를 적는다
        detail = ("(살펴본 곳: " + " · ".join(f"{c.name} — {(c.rejected or ['조건에 맞지 않음'])[0]}" for c in rejected) + ")"
                  if 0 < len(rejected) <= 3 else
                  f"(살펴본 {len(rejected)}곳 중 {why})" if why else
                  f"(살펴본 {len(rejected)}곳이 모두 조건에 맞지 않아요)" if rejected else "(그 안에 후보 장소가 하나도 없어요)")
        text = (f"바꿀 수 있는 다른 곳을 찾지 못했어요 — {seoul(current.starts_at):%H:%M}에 갈 수 있는 {kind}이 "
                f"{radius / 1000:g}km 안에 없어요{detail}.")
        facts = {"radius_m": radius, "seen": len(rejected), "rejected": {c.name: c.rejected for c in rejected[:20]}}
        # ★`[2026-09-29 사용자 지적]` 막다른 답 대신 **조건을 풀어 되는 안**을 계산한다 — 있으면 묻는다(`relaxed`)
        options = relaxed_options(trip=trip, items=items, places=places, current=current, state_lookup=state_lookup)
        if options:
            listed = " · ".join(f"{n}) {o['note']} {o['name']}" + (f"(도보 {o['walk_min']}분)" if o.get("walk_min") else "")
                                for n, o in enumerate(options, start=1))
            ask = (f"{radius / 1000:g}km 안에서 {seoul(current.starts_at):%H:%M}에 갈 수 있는 {kind}이 없어요{detail}. "
                   f"대신 이런 곳이 있어요 — {listed}. 고르시면 바꿀게요. 답이 없으면 원래 일정을 그대로 둡니다.")
            return NoChange("relaxed", {"text": ask, "reason": text, "options": options, "causes": [cause], **facts})
        return NoChange("no_alternate", {"reason": text, "text": text, **facts})
    name = best.place["name"] if best.place else best.name
    starts = best.starts_at or current.starts_at
    # ★`[2026-09-29 사용자 제안 — ui 세션 전달]` 바꾼 뒤에도 **고를 수 있는 다른 안을 셋까지** — 조건을 다 통과한 나머지 먼저,
    #   모자라면 조건을 푼 안(시각 늦추기 · 다음 일정 근처 · 반경 넓히기 — `note` 에 무엇을 풀었는지). 원래 곳은 넣지 않는다
    #   (되돌리기 몫). ☆전에는 조건을 다 통과한 곳이 한 곳뿐이면 「다른 안」 없이 끝났다(아침 장군숯불족발 → 먹고을 한 곳).
    more = [alternate_record(c) for c in alternates]
    if len(more) < RELAX_WANT:
        by_id = {str(p["place_id"]): p for p in places}
        taken = [best.place] + [c.place for c in alternates if c.place]
        for option in relaxed_options(trip=trip, items=items, places=places, current=current, state_lookup=state_lookup,
                                      exclude={best.key} | {m["key"] for m in more}):
            if len(more) >= RELAX_WANT:
                break
            spot = by_id.get(str(option.get("place_id")))
            if option["key"] in {m["key"] for m in more} | {best.key}:
                continue
            if current.kind == "activity" and spot and any(t and same_site(t, spot) for t in taken):
                continue
            more.append(option)
            if spot:
                taken.append(spot)
    labels = [f"{m['note']} {m['name']}" if m.get("note") else m["name"] for m in more]
    others = [m["name"] for m in more]
    text = (f"요청하신 대로 {current.place['name']} 대신 {name}(으)로 바꿨습니다({seoul(starts):%H:%M} 시작)."
            + (" 다른 안: " + " · ".join(f"{n}) {label}" for n, label in enumerate(labels, start=1))
               + " — 다른 곳이 좋으면 고르세요. 답이 없으면 지금대로 둡니다." if labels else ""))
    notice = {"text": text, "language": "ko", "causes": [cause],
              "changed": {"from": current.place["name"], "to": name, "at": starts.isoformat()},
              "other_options": others, "replay": False}
    replacement = current.replaced_by(
        place=best.place, title=title_for(current, name),
        detail={"customer_requested": True, "other_options": others,
                **({"warnings": list(best.warnings)} if getattr(best, "warnings", None) else {}),
                "alternates": more + [applied_record(current)]},
        starts_at=starts, ends_at=best.ends_at or current.ends_at)
    # ★`[2026-09-29 ui 세션 요청]` 바꾼 뒤에도 몇 곳을 봤고 무엇이 왜 떨어졌는지 남긴다(왜 한 곳뿐이었는지 나중에 보게).
    #   `seen` = 떨어진 곳 + 통과한 곳(통과한 곳은 셋까지만 센다 — `choose` 가 셋만 돌려준다)
    return ItineraryChange(reason="customer_request", causes=[cause], notice=notice,
                           replacements={current.item_id: replacement},
                           summary={"from": current.place["name"], "to": name,
                                    "more_options": more, "radius_m": radius,
                                    "seen": len(rejected) + 1 + len(alternates),
                                    "rejected": {c.name: c.rejected for c in rejected[:20]}})


# ── 재요청 ② — 되돌려 줘 ───────────────────────────────────────
def _slot(item: Item, first_day: Any) -> str:
    """고객 말로 그 항목의 자리 — 「1일차 저녁」 · 「2일차 10:00 경복궁 자리」."""
    start = seoul(item.starts_at)                          # ★서울 시각 — 날짜 · 시계 숫자 모두(DB 세션이 UTC 여도 같은 자리 이름이 나온다)
    day = (start.date() - first_day).days + 1
    hour = start.hour
    if item.kind == "dining":
        meal = "아침" if hour < 11 else "점심" if hour < 16 else "저녁"
        return f"{day}일차 {meal}"
    return f"{day}일차 {start:%H:%M} 일정"


def plan_rollback(*, trip_version: int, base_version: int, current_items: list[Item],
                  old_items: list[Item], to_version: int, message: str | None,
                  request_id: str | None, redo: bool = False) -> Plan:
    """옛 버전의 항목을 **새 버전으로 다시 쓴다**(append-only — 옛 버전을 지우지 않는다).

    ★되살린 항목은 `customer_pinned` 로 표시한다. 감시 루프가 다음 틱에 같은 원인으로
      다시 바꾸면 되돌림이 무의미해진다 — 고객이 알고 고른 것이다.
    """
    if trip_version != base_version:
        return NoChange("stale", {"version": trip_version})
    if not 1 <= to_version < trip_version:
        return NoChange("invalid_version", {"version": trip_version})
    current_ids = {i.item_id for i in current_items}
    restored = []
    for item in old_items:
        if item.item_id not in current_ids:
            item.detail = {**item.detail, "customer_pinned": True}
            restored.append(item.title)
    cause = with_request({"category": "customer_request", "type": "rollback",
                          "to_version": to_version, "message": message}, request_id)
    # ★`[2026-09-29 ui 세션 지적]` 고객 말로 쓴다 — 「버전 1」·이동 항목 제목(「경복궁 → 일품당프리미엄」)을 싣지 않고,
    #   장소가 바뀐 항목만 「자리: 전 → 후」로. 앞서 되돌린 것을 다시 적용하는 경우(`redo`)는 「다시 적용했어요」
    old_ids = {i.item_id for i in old_items}
    leaving = {i.seq: i for i in current_items if i.item_id not in old_ids and i.kind != "mobility" and i.place}
    first_day = min((seoul(i.starts_at) for i in [*current_items, *old_items]), default=None)
    pairs = []
    for item in old_items:
        if item.item_id in current_ids or item.kind == "mobility" or not item.place:
            continue
        now = leaving.get(item.seq)
        if now is not None and first_day is not None:
            pairs.append((_slot(item, first_day.date()), now.place["name"], item.place["name"]))
    if redo:
        text = ("요청하신 변경을 다시 적용했어요 — " + " · ".join(f"{slot} {a} → {b}" for slot, a, b in pairs) + "."
                if pairs else "요청하신 변경을 다시 적용했어요.")
    else:
        text = (" · ".join(f"{slot}{object_particle(slot)} {a}에서 {b}(으)로" for slot, a, b in pairs) + " 되돌렸어요."
                if pairs else "일정을 바꾸기 전 상태로 되돌렸어요.")
    notice = {"text": text, "language": "ko", "causes": [cause],
              "changed": {"rollback_to": to_version, "restored": restored},
              "other_options": [], "replay": False}
    return ItineraryChange(reason="rollback", causes=[cause], notice=notice,
                           full_items=list(old_items), summary={"restored": restored})


__all__ = ["DINING_RADIUS_M", "ItineraryChange", "NoChange", "Plan", "applied_record",
           "minutes_between", "next_after", "object_particle", "plan_activity_adjustment",
           "plan_closed", "plan_closed_on_day", "plan_delay", "plan_nearby_store", "plan_rollback",
           "plan_route_adjustment", "plan_swap", "planned_option", "route_of", "route_targets",
           "title_for", "with_request"]

# -*- coding: utf-8 -*-
"""채점이 보는 여행 상태 — 판(일정 항목 목록)과 항목의 계보(바뀐 항목이 어느 항목을 대신하나). `[2026-10-19]`

★제품은 판마다 항목을 다시 쓰고, 그대로인 항목은 같은 `item_id` 를, 바뀐 항목은 새 `item_id` + `replaces_item_id`(앞 항목)를 쓴다
  (x600 서버 기록 `496ba7b1` 판 1→2→3 으로 확인). 그래서 「시작 판의 2번 항목은 끝 판에서 무엇이 됐나」는 계보로 찾는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .patterns import norm

KST = timezone(timedelta(hours=9))


def parse_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=KST)
    text = str(value).replace(" ", "T", 1) if "T" not in str(value) else str(value)
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=KST)


@dataclass
class Item:
    item_id: str
    seq: int
    kind: str
    title: str
    place: str | None = None          # 연결된 장소 이름(없으면 None)
    start: datetime | None = None
    end: datetime | None = None
    pinned: bool = False               # 고객 고정(`locked` 또는 세부 정보 `customer_pinned`)
    indoor: bool | None = None         # 실내 여부(장소 자료 · 표적 에피소드 표시 — 모르면 None)
    replaces: str | None = None
    place_id: str | None = None
    category: str | None = None        # 장소 분류 말(식당 · 카페 · 박물관 …) — 조건 검사용, 모르면 None

    def key(self) -> tuple:
        """「그대로인가」를 볼 때 비교하는 칸."""
        iso = lambda m: m.astimezone(KST).isoformat() if m else ""  # noqa: E731
        return (self.kind, norm(self.title), norm(self.place), iso(self.start), iso(self.end))

    def label(self) -> str:
        when = self.start.astimezone(KST).strftime("%m-%d %H:%M") if self.start else "?"
        place = f" @{self.place}" if self.place and norm(self.place) != norm(self.title) else ""
        return f"#{self.seq} {when} {self.kind} {self.title}{place}"

    def names(self) -> list[str]:
        return [n for n in (self.title, self.place) if n]

    def as_dict(self) -> dict[str, Any]:
        return {"item_id": self.item_id, "seq": self.seq, "kind": self.kind, "title": self.title, "place": self.place,
                "start": self.start.isoformat() if self.start else None, "end": self.end.isoformat() if self.end else None,
                "pinned": self.pinned, "indoor": self.indoor, "replaces": self.replaces, "place_id": self.place_id,
                "category": self.category}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Item":
        return cls(item_id=str(d.get("item_id") or f"seq{d.get('seq')}"), seq=int(d.get("seq") or 0), kind=str(d.get("kind") or ""),
                   title=str(d.get("title") or ""), place=d.get("place"), start=parse_dt(d.get("start") or d.get("s") or d.get("starts_at")),
                   end=parse_dt(d.get("end") or d.get("e") or d.get("ends_at")), pinned=bool(d.get("pinned") or d.get("locked")),
                   indoor=d.get("indoor"), replaces=d.get("replaces") or d.get("replaces_item_id"), place_id=d.get("place_id"),
                   category=d.get("category"))


@dataclass
class TripView:
    version: int
    items: list[Item]
    title: str = ""
    #: 판을 넘나드는 계보 — 새 item_id → 대신한 item_id (모든 판의 항목에서 모은다)
    lineage: dict[str, str] = field(default_factory=dict)

    def by_seq(self, seq: int) -> Item | None:
        return next((i for i in self.items if i.seq == seq), None)

    def descendant(self, item: Item) -> Item | None:
        """시작 판 항목이 이 판에서 무엇이 됐나 — 같은 id, 또는 계보를 거슬러 올라가 그 id 에 닿는 항목."""
        for cand in self.items:
            cur, hops = cand.item_id, 0
            while cur and hops < 50:
                if cur == item.item_id:
                    return cand
                cur = self.lineage.get(cur) or (cand.replaces if cur == cand.item_id else None)
                hops += 1
        return None

    def stops(self) -> list[Item]:
        return [i for i in self.items if i.kind != "mobility"]

    def as_dict(self) -> dict[str, Any]:
        return {"version": self.version, "title": self.title, "items": [i.as_dict() for i in self.items],
                "lineage": dict(self.lineage)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TripView":
        items = [Item.from_dict(x) for x in d.get("items") or []]
        lineage = dict(d.get("lineage") or {})
        for i in items:
            if i.replaces and i.item_id not in lineage:
                lineage[i.item_id] = i.replaces
        return cls(version=int(d.get("version") or 0), items=items, title=str(d.get("title") or ""), lineage=lineage)


def same_items(a: TripView, b: TripView, *, ignore_mobility: bool = True) -> bool:
    pick = (lambda v: v.stops()) if ignore_mobility else (lambda v: v.items)
    return sorted(i.key() for i in pick(a)) == sorted(i.key() for i in pick(b))

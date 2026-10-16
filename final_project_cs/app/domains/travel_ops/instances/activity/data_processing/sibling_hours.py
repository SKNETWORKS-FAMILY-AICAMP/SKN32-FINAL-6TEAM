# -*- coding: utf-8 -*-
"""쇼핑(38) 지점끼리 운영시간 · 휴무를 옮겨 적는다 — 같은 입점 매장(백화점 · 아울렛 · 몰)이나 같은 브랜드.

`[2026-10-16 사용자]` 「같은 브랜드 다른 지점이면 운영시간이나 휴무를 같게 반영할 수 있는 부분이 있다」.
받아 둔 쇼핑 1,232곳으로 재 보니(2026-10-16) **입점 매장**이 브랜드보다 훨씬 잘 맞았다 —
  입점 매장 2곳 이상 묶음 40개 중 29개가 70% 이상 같은 시간(NC 신구로 22곳 모두 10:30~21:00, 휴무는 대부분 「명절」),
  입점 밖 단독 지점의 브랜드 묶음은 67개 중 22개(다이소 · 롯데마트는 맞고 나이키 · 아트박스는 지점마다 다르다).
그래서 묶음은 입점 매장이 먼저, 그다음 `brand` 칸이고 옮기는 기준도 다르다(`VENUE_SHARE` · `BRAND_SHARE`).

★옮기는 칸은 `business_hours` · `closed_days` 둘뿐이다. 연락처는 지점마다 달라 옮기지 않는다.
★옮긴 값은 `field_sources` 에 `{"by": "sibling", "group": 묶음, "basis": [근거 contentid…], "checked": 날짜}` 로 남긴다.
  그 지점을 TourAPI 로 직접 받으면 `fill_tourapi_details.apply_cache` 가 TourAPI 값으로 바꾸고 출처를 지운다(사람 값과 같은 규칙).
★근거는 **TourAPI 가 직접 준 값**뿐이다(숫자 contentid · 그 칸에 출처 표시가 없는 행). 옮긴 값이 다시 근거가 되지 않는다.
★다시 돌리면 같은 결과다 — 이미 옮긴 칸은 지금 근거로 다시 정하고, 근거가 더는 맞지 않으면 비운다.

호출 순서(`call_order`) — 하루 한도로 나눠 받을 때 앞에서부터 받는다:
  0 표본(묶음마다 `SAMPLE_SIZE` 곳) → 1 묶음이 없거나 혼자인 곳 → 2 표본이 엇갈린 묶음의 나머지 → 3 옮겨 적은 곳(직접 확인용)
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

SHOPPING = "38"
COLUMNS = ("business_hours", "closed_days")
SIBLING_BY = "sibling"
#: 묶음마다 먼저 받는 지점 수
SAMPLE_SIZE = 3
#: 옮기려면 근거가 적어도 이만큼
MIN_BASIS = 3
#: 입점 매장 — 가장 많은 값이 근거의 이만큼 이상이면 옮긴다(3곳 중 2곳)
VENUE_SHARE = 2 / 3
#: 브랜드 — 지점마다 다른 브랜드가 많아 더 엄하게. 표본 3곳이면 3곳 모두 같아야 하고, 많이 받은 뒤에는 한두 곳 다른 것을 넘긴다
#: (다이소 52곳 중 50곳이 10:00~22:00 — 2026-10-16)
BRAND_SHARE = 0.9
#: 옮긴 값의 근거로 적는 contentid 최대 수
BASIS_LIMIT = 5

#: 입점 매장 이름 — 뒤에 붙는 지점 이름(「잠실점」)까지 한 묶음 이름으로 쓴다. 앞에서 먼저 나온 이름이 이긴다.
_VENUE = re.compile(
    r"(현대백화점|롯데백화점|신세계백화점|갤러리아백화점|갤러리아|AK플라자|더현대|현대아울렛|현대시티아울렛|롯데아울렛|"
    r"마리오아울렛|(?<![A-Za-z])NC(?![A-Za-z])|뉴코아|IFC몰|롯데월드몰|롯데몰|스타필드|아이파크몰|타임스퀘어|가든파이브|"
    r"W몰|엔터식스|디큐브)\s*([^\s()]*)")


def venue_of(title: str) -> str | None:
    """제목의 입점 매장(「롯데백화점 잠실점」 → 「롯데백화점잠실」). 없으면 None."""
    match = _VENUE.search(title or "")
    if not match:
        return None
    return re.sub(r"점$", "", match.group(1) + match.group(2))


def group_of(row: dict[str, str]) -> str | None:
    """쇼핑 행의 묶음 — `venue:…` 가 먼저, 없으면 `brand:…`(`brand` 칸이 있을 때만 — 제목으로 짐작하지 않는다)."""
    if row.get("contenttypeid") != SHOPPING:
        return None
    venue = venue_of(row.get("title") or "")
    if venue:
        return f"venue:{venue}"
    brand = (row.get("brand") or "").strip()
    return f"brand:{brand}" if brand else None


def same_text(text: str) -> str:
    """같은 값인지 볼 때만 쓰는 모양 — `<br>` · 공백 · 「-」/「~」 · 「매일」 차이를 없앤다. 적는 값은 원문이다."""
    text = re.sub(r"<br\s*/?>", " ", text or "", flags=re.IGNORECASE)
    return re.sub(r"\s+", "", text).replace("-", "~").replace("매일", "")


def _is_basis(row: dict[str, str], column: str, sources: dict[str, Any]) -> bool:
    return row["contentid"].isdigit() and bool((row.get(column) or "").strip()) and column not in sources


def consensus(values: list[str], share: float) -> str | None:
    """근거 원문들에서 옮길 값(가장 흔한 원문). 근거가 모자라거나 기준에 못 미치면 None."""
    if len(values) < MIN_BASIS:
        return None
    counts = Counter(same_text(v) for v in values)
    top, count = counts.most_common(1)[0]
    if count / len(values) < share:
        return None
    return Counter(v for v in values if same_text(v) == top).most_common(1)[0][0]


def _share(group: str) -> float:
    return VENUE_SHARE if group.startswith("venue:") else BRAND_SHARE


def propagate(rows: list[dict[str, str]], checked: str, read_sources, write_sources) -> Counter:
    """빈 칸(또는 전에 옮겨 적은 칸)을 같은 묶음 근거의 값으로 채운다. 사람 · Claude 가 채운 칸 · 「해당 없음」은 건드리지 않는다.

    `read_sources(row)` · `write_sources(row, sources)` 는 `fill_tourapi_details` 의 `field_sources` 읽기 · 쓰기다.
    """
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if group := group_of(row):
            groups[group].append(row)
    stats: Counter = Counter()
    for group, members in groups.items():
        all_sources = [read_sources(r) for r in members]
        for column in COLUMNS:
            basis = [(r, r[column].strip()) for r, s in zip(members, all_sources) if _is_basis(r, column, s)]
            value = consensus([v for _, v in basis], _share(group))
            ids = sorted(r["contentid"] for r, v in basis if value is not None and same_text(v) == same_text(value))
            for row, sources in zip(members, all_sources):
                entry = sources.get(column)
                ours = isinstance(entry, dict) and entry.get("by") == SIBLING_BY
                if entry is not None and not ours:
                    continue                                  # 사람 · Claude 값 · 「해당 없음」
                if not ours and (row.get(column) or "").strip():
                    continue                                  # TourAPI 값
                if value is None:
                    if ours:                                  # 근거가 더는 맞지 않는다 — 옮긴 값을 거둔다
                        row[column] = ""
                        del sources[column]
                        stats[f"{column} 거둠"] += 1
                    continue
                new_entry = {"by": SIBLING_BY, "group": group, "basis": ids[:BASIS_LIMIT], "checked": checked}
                if ours and row[column] == value and {**entry, "checked": checked} == new_entry:
                    continue                                  # 그대로다 — 확인한 날도 옛 날짜로 둔다
                stats[f"{column} {'다시 정함' if ours else '옮김'}({group.split(':')[0]})"] += 1
                row[column] = value
                sources[column] = new_entry
        for row, sources in zip(members, all_sources):
            write_sources(row, sources)
    return stats


def call_order(todo: list[dict[str, str]], rows: list[dict[str, str]], fetched: set[str],
               read_sources) -> dict[str, int]:
    """쇼핑 행의 호출 순서(작을수록 먼저). `fetched` 는 이미 받은 contentid.

    표본은 묶음마다 이미 받은 곳을 먼저 세고, 모자란 만큼 contentid 순으로 고른다(다시 돌려도 같은 곳).
    """
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        group = group_of(row)
        if group and row["contentid"].isdigit():
            groups[group].append(row)
    rank: dict[str, int] = {}
    for group, members in groups.items():
        if len(members) < 2:
            continue
        have = [r for r in members if r["contentid"] in fetched]
        picks = sorted((r for r in members if r["contentid"] not in fetched), key=lambda r: int(r["contentid"]))
        samples = {r["contentid"] for r in picks[:max(0, SAMPLE_SIZE - len(have))]}
        settled = {column: consensus([r[column].strip() for r in members if _is_basis(r, column, read_sources(r))],
                                     _share(group)) is not None for column in COLUMNS}
        for row in members:
            cid = row["contentid"]
            if cid in samples:
                rank[cid] = 0
            elif all(settled.values()):
                rank[cid] = 3
            else:
                rank[cid] = 2
    return {r["contentid"]: rank.get(r["contentid"], 1) for r in todo if r.get("contenttypeid") == SHOPPING}

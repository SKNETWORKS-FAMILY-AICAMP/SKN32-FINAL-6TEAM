# -*- coding: utf-8 -*-
"""장소 정보 채우기 **배치의 부품** — 곧 시작하는 활동 일정에 든 장소 이름을 모아 `place_enrichment.enrich_place` 로 채운다. `[2026-10-19]`

    손으로  `scripts/activity/enrich_places.py`  (대상 세기 · 채우기, 출력은 글)

★왜 배치인가. 웹 검색은 한 번에 15~40초 · 간혹 429 · 호출당 약 $0.03 이다. 고객 응답 중에 부르지 않고, **일정에 든 장소를 미리** 채워 둔다 —
  고객 요청은 저장된 값만 읽는다(`ledger._merge_web`). 같은 장소는 한 번이다(채운 칸 · 「못 찾음」 표시가 만료 전이면 다시 부르지 않는다).
★대상은 원장에 없는 장소(카카오로만 찾은 곳)도 포함한다 — 코어 장소 행의 **이름**이 곧 고객이 쓴 이름이다.
★못 물어본 것(`unknown` · 웹 오류 · 시간 초과 · 예산 초과)은 센다. 예산이 차면 거기서 멈추고 남은 곳을 보고한다.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from . import place_enrichment as pe

#: 지금부터 N시간 안에 시작하는 활동 항목의 (장소 이름, 관광공사 번호 — 없을 수 있다). 일정은 버전으로 쌓이므로 최신 버전만 본다.
_NAMES_SQL = """
SELECT p.name, COALESCE(p.source_content_id, p.attributes->>'source_content_id') AS content_id, min(i.starts_at) AS starts_at
FROM trips t
JOIN itinerary_items i ON i.trip_id = t.trip_id AND i.version = t.latest_version
JOIN places p ON p.place_id = i.place_id
WHERE t.status = 'active' AND i.kind = 'activity'
  AND i.starts_at >= %s AND i.starts_at < %s + (%s || ' hours')::interval
  AND (%s::text IS NULL OR t.tenant_id = %s::text)
  AND btrim(coalesce(p.name, '')) <> ''
GROUP BY 1, 2
ORDER BY min(i.starts_at), p.name
"""


@dataclass(frozen=True)
class Candidate:
    name: str
    content_id: str | None
    starts_at: datetime


def find_names(conn: Any, now: datetime, within_hours: float, *, tenant_id: str | None = None) -> list[Candidate]:
    """채울 장소 이름들 — 같은 이름 · 같은 번호는 한 번(가장 이른 시각)."""
    with conn.cursor() as cur:
        cur.execute(_NAMES_SQL, (now, now, str(within_hours), tenant_id, tenant_id))
        rows = cur.fetchall()
    seen: set[tuple[str, str | None]] = set()
    out: list[Candidate] = []
    for name, content_id, starts_at in rows:
        key = (str(name).strip(), str(content_id) if content_id else None)
        if key in seen:
            continue
        seen.add(key)
        out.append(Candidate(key[0], key[1], starts_at))
    return out


def run(candidates: list[Candidate], enrich: Callable[[str], dict[str, Any]], *, limit: int | None = None) -> dict[str, Any]:
    """하나씩 채운다(`enrich(이름) → enrich_place 결과`). 한 곳이 실패해도 멈추지 않고 센다 — 단, 예산이 차면 거기서 멈춘다.
    반환 `{"targets", "asked", "by_status": {상태: 수}, "left"}`. `asked` 는 실제로 웹 검색을 부른 곳(`enriched` · `no_info` · 웹 실패)이다."""
    by_status: Counter[str] = Counter()
    asked = 0
    left = 0
    for index, candidate in enumerate(candidates):
        if limit is not None and asked >= limit:
            left = len(candidates) - index
            break
        result = enrich(candidate.name)
        status = str(result.get("status"))
        by_status[status] += 1
        if status in (pe.ENRICHED, pe.NO_INFO, pe.WEB_ERROR, pe.WEB_TIMEOUT, pe.BUSY, pe.TABLE_MISSING):
            asked += 1
        if status in (pe.BUDGET, pe.WEB_OFF):
            left = len(candidates) - index - 1                      # 예산이 찼거나 웹 검색이 꺼져 있다 — 더 불러도 같다
            break
        if status == pe.TABLE_MISSING:
            left = len(candidates) - index - 1                      # 저장할 곳이 없다 — 더 불러도 돈만 나간다
            break
    return {"targets": len(candidates), "asked": asked, "by_status": dict(by_status), "left": left}

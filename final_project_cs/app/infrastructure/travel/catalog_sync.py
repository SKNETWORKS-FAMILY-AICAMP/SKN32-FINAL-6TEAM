# -*- coding: utf-8 -*-
"""장소 카탈로그 동기화 — **처음엔 전부, 그 뒤엔 바뀐 것만.**

★설계 근거는 실측이다(2026-09-10, 실 키).

      areaBasedList2  서울 → 총 2,063건 (콜 하나에 페이지 단위로)
      가장 최근 수정   2025-11-21   ← 오늘 기준 10개월 전

  장소 기본정보는 **거의 안 바뀐다.** 사용자 계획서를 순회하며 매번 부르면
  콜 수가 **사용자 수에 비례**해 늘고 하루 한도를 바로 태운다. 지역 단위로
  한 번 받아 DB 에 두고, 계획서는 그 표를 읽는다. 그러면 사용자가 1명이든
  10,000명이든 **콜 수가 같다.**

★**재개 가능해야 한다.** 속도 제한이 하루 한도를 하루에 걸쳐 펴므로
  (TourAPI 1,000/일 → 86.4초 간격) 서울 2,063건을 한 번에 못 받는다.
  페이지마다 진행 상태를 저장하고, 끊기면 다음 실행이 이어받는다.

★★**델타를 무조건 믿지 않는다.**
  `areaBasedSyncList2` 는 2026-09-10 에 **7가지 조합을 다 시도해도 0건**이었다
  (8/14자리 `modifiedtime`, `showflag` 1/0/생략, 지역 서울/제주/생략,
  기준일 2025-01~2026-09). 같은 키로 `areaBasedList2` 는 2,063건이 오므로
  키 문제가 아니라 **우리가 파라미터를 못 맞춘 것**이다.

  그래서 「0건」을 「안 바뀜」으로 읽지 않는다. 주기적으로 **전체를 다시 받아
  대조**해서, 델타가 0 이라 했는데 실제로 달라진 게 있으면 `delta_trusted` 를
  내리고 그 사실을 남긴다. 이것이 없으면 델타가 조용히 고장 난 채로
  「최신입니다」라고 답하게 된다 — 신호 없는 축소는 폴백이다(`RULE.md` §3.2).
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

#: 한 페이지에 받을 수. ★크게 잡을수록 콜이 준다. 공급자 상한을 넘으면
#:  조용히 잘리므로 실제로 받은 건수를 세어 확인한다.
PAGE_SIZE = 100

#: 전체 재수집으로 델타를 검증하는 주기(일). ★공짜가 아니라 콜을 쓴다.
#:  장소 정보가 10개월째 안 바뀌는 것을 감안하면 주 1회로 충분하다.
AUDIT_EVERY_DAYS = 7


@dataclass
class SyncOutcome:
    """한 번 돌린 결과. ★무엇을 했고 무엇을 **못 했는지** 둘 다 담는다."""

    source: str
    scope: str
    mode: str                 # bootstrap | delta | audit | idle
    pages_fetched: int = 0
    rows_written: int = 0
    finished: bool = False    # 부트스트랩이 끝났나
    delta_trusted: bool | None = None
    note: str = ""

    def __str__(self) -> str:
        return (f"[{self.source}/{self.scope}] {self.mode} "
                f"페이지 {self.pages_fetched} · 행 {self.rows_written}"
                f"{' · 완료' if self.finished else ''}"
                f"{' · ' + self.note if self.note else ''}")


class PlaceCatalogSync:
    """`place_catalog` 를 채우고 유지한다.

    ★DB 접근을 주입받는다 — 시험이 진짜 DB 없이 돌 수 있어야 한다.
    """

    def __init__(self, *, source: Any, connection_factory: Callable[[], Any],
                 tenant_id: str, page_size: int = PAGE_SIZE) -> None:
        self.source, self._connect = source, connection_factory
        self.tenant_id, self.page_size = tenant_id, page_size

    # ── 진입점 ──────────────────────────────────────────────────
    def run(self, area_code: str, *, max_pages: int = 5) -> SyncOutcome:
        """한 번 돌린다. **부트스트랩이 안 끝났으면 그것부터.**

        ★`max_pages` 로 한 번에 하는 일을 제한한다. 속도 제한 때문에 페이지
          하나에 수십 초가 걸리므로, 한 실행이 몇 시간씩 물고 있으면 안 된다.
          남은 것은 다음 실행이 이어받는다.
        """
        state = self._load_state(area_code)
        if not state["bootstrap_done"]:
            return self._bootstrap(area_code, state, max_pages=max_pages)
        return self._delta(area_code, state)

    # ── 부트스트랩 ──────────────────────────────────────────────
    def _bootstrap(self, area_code: str, state: dict[str, Any],
                   *, max_pages: int) -> SyncOutcome:
        outcome = SyncOutcome(self.source.name, area_code, "bootstrap")
        page = int(state["next_page"])
        total = state.get("total_expected")

        for _ in range(max_pages):
            body = self.source.area_page(area_code, page=page,
                                         rows=self.page_size)
            if body is None:
                # ★못 받았으면 **진행을 앞으로 옮기지 않는다.** 옮기면 그
                #   페이지가 영영 빈 채로 남는다.
                outcome.note = "받지 못했다(속도 제한이거나 공급자 문제). 다음에 이어서 한다"
                self._save_state(area_code, next_page=page, last_error=outcome.note)
                return outcome

            rows = body.get("items") or []
            total = body.get("total_count", total)
            outcome.pages_fetched += 1
            outcome.rows_written += self._upsert(rows)

            if not rows:
                # ★빈 페이지 = 끝. 총건수만 믿고 끝내지 않는다 —
                #   공급자가 말한 수와 실제로 준 수가 다른 경우가 있다.
                self._save_state(area_code, next_page=page, bootstrap_done=True,
                                 total_expected=total, last_error=None)
                outcome.finished = True
                outcome.note = f"완료. 공급자 총건수 {total}"
                return outcome

            page += 1
            self._save_state(area_code, next_page=page, total_expected=total,
                             rows_add=len(rows), last_error=None)

        outcome.note = f"{max_pages}페이지까지 하고 멈췄다. 다음 실행이 {page}쪽부터 잇는다"
        return outcome

    # ── 델타 ────────────────────────────────────────────────────
    def _delta(self, area_code: str, state: dict[str, Any]) -> SyncOutcome:
        outcome = SyncOutcome(self.source.name, area_code, "delta")
        since = state.get("high_water")
        if not since:
            outcome.mode, outcome.note = "idle", "기준 시각이 없다. 감사(전체 대조)를 먼저 돌린다"
            return outcome

        body = self.source.changed_since(area_code, since=since,
                                         rows=self.page_size)
        if body is None:
            outcome.note = "변경분을 받지 못했다"
            self._save_state(area_code, last_error=outcome.note)
            return outcome

        rows = body.get("items") or []
        outcome.rows_written = self._upsert(rows)
        outcome.pages_fetched = 1
        outcome.delta_trusted = bool(state.get("delta_trusted"))

        if not rows and not outcome.delta_trusted:
            # ★★여기가 핵심. 0건인데 **델타를 아직 못 믿는 상태**면
            #   「최신입니다」라고 말하지 않는다.
            outcome.note = ("변경 0건이지만 델타를 아직 검증하지 못했다 — "
                            "「안 바뀜」인지 「델타가 안 도는지」 구분할 수 없다. "
                            "전체 대조(audit)가 필요하다")
        self._save_state(area_code, last_delta_at_now=True, last_error=None)
        return outcome

    # ── 감사: 전체를 다시 받아 대조한다 ──────────────────────────
    def audit(self, area_code: str, *, max_pages: int = 30) -> SyncOutcome:
        """전체를 다시 받아 캐시와 대조하고, 델타를 믿을지 정한다.

        ★델타가 0 이라 했는데 실제로 달라진 게 있으면 **델타가 거짓말하고
          있는 것**이다. 그때 `delta_trusted` 를 내린다.
        """
        outcome = SyncOutcome(self.source.name, area_code, "audit")
        seen: dict[str, str] = {}
        page = 1
        for _ in range(max_pages):
            body = self.source.area_page(area_code, page=page, rows=self.page_size)
            if body is None:
                outcome.note = "전체를 다 받지 못해 판정하지 않았다"
                return outcome
            rows = body.get("items") or []
            outcome.pages_fetched += 1
            if not rows:
                break
            for row in rows:
                content_id = str(row.get("content_id") or "")
                if content_id:
                    seen[content_id] = str(row.get("source_modified_at") or "")
            outcome.rows_written += self._upsert(rows)
            page += 1
        else:
            outcome.note = f"{max_pages}페이지에서 멈췄다 — 판정하지 않았다"
            return outcome

        cached = self._cached_versions(area_code)
        differing = [cid for cid, stamp in seen.items() if cached.get(cid) != stamp]
        missing = [cid for cid in seen if cid not in cached]
        high_water = max(seen.values(), default="")

        trusted = not differing and not missing
        note = (f"대조 {len(seen)}건 · 어긋남 {len(differing)} · 캐시에 없음 {len(missing)}")
        if not trusted:
            note += " → 델타를 믿지 않는다"
        self._save_state(area_code, high_water=high_water, delta_trusted=trusted,
                         delta_note=note, last_error=None)
        outcome.delta_trusted, outcome.note, outcome.finished = trusted, note, True
        return outcome

    # ── DB ──────────────────────────────────────────────────────
    def _upsert(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        written = 0
        with self._connect() as conn, conn.transaction(), conn.cursor() as cur:
            for row in rows:
                content_id = str(row.get("content_id") or "").strip()
                if not content_id or not str(row.get("title") or "").strip():
                    continue      # ★식별자나 이름이 없으면 안 넣는다
                cur.execute(
                    "INSERT INTO place_catalog (tenant_id, source, content_id, "
                    "content_type_id, area_code, title, address, latitude, longitude, "
                    "large_class_code, large_class_name, "
                    "source_modified_at, raw_json) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (tenant_id, source, content_id) DO UPDATE SET "
                    "content_type_id=EXCLUDED.content_type_id, "
                    "area_code=EXCLUDED.area_code, title=EXCLUDED.title, "
                    "address=EXCLUDED.address, latitude=EXCLUDED.latitude, "
                    "longitude=EXCLUDED.longitude, "
                    "large_class_code=EXCLUDED.large_class_code, "
                    "large_class_name=EXCLUDED.large_class_name, "
                    "source_modified_at=EXCLUDED.source_modified_at, "
                    "raw_json=EXCLUDED.raw_json, fetched_at=now()",
                    (self.tenant_id, self.source.name, content_id,
                     row.get("content_type_id"), row.get("area_code"),
                     row.get("title"), row.get("address"),
                     row.get("latitude"), row.get("longitude"),
                     row.get("large_class_code"), row.get("large_class_name"),
                     row.get("source_modified_at"),
                     json.dumps(row.get("raw") or {}, ensure_ascii=False)))
                written += 1
        return written

    def _cached_versions(self, area_code: str) -> dict[str, str]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT content_id, coalesce(source_modified_at,'') FROM place_catalog "
                "WHERE tenant_id=%s AND source=%s AND area_code=%s",
                (self.tenant_id, self.source.name, area_code))
            return dict(cur.fetchall())

    def _load_state(self, area_code: str) -> dict[str, Any]:
        columns = ("bootstrap_done", "next_page", "total_expected", "rows_seen",
                   "high_water", "delta_trusted")
        with self._connect() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "INSERT INTO source_sync_state (tenant_id, source, scope) "
                "VALUES (%s,%s,%s) ON CONFLICT (tenant_id, source, scope) DO NOTHING",
                (self.tenant_id, self.source.name, area_code))
            cur.execute(
                f"SELECT {', '.join(columns)} FROM source_sync_state "
                "WHERE tenant_id=%s AND source=%s AND scope=%s",
                (self.tenant_id, self.source.name, area_code))
            return dict(zip(columns, cur.fetchone()))

    def _save_state(self, area_code: str, **changes: Any) -> None:
        sets, params = ["updated_at=now()"], []
        mapping = {
            "next_page": "next_page=%s", "bootstrap_done": "bootstrap_done=%s",
            "total_expected": "total_expected=%s", "high_water": "high_water=%s",
            "delta_trusted": "delta_trusted=%s", "delta_note": "delta_note=%s",
            "last_error": "last_error=%s",
        }
        for key, clause in mapping.items():
            if key in changes:
                sets.append(clause)
                params.append(changes[key])
        if changes.get("rows_add"):
            sets.append("rows_seen = rows_seen + %s")
            params.append(int(changes["rows_add"]))
        if changes.get("last_delta_at_now"):
            sets.append("last_delta_at = now()")

        with self._connect() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute(
                f"UPDATE source_sync_state SET {', '.join(sets)} "
                "WHERE tenant_id=%s AND source=%s AND scope=%s",
                (*params, self.tenant_id, self.source.name, area_code))


__all__ = ["AUDIT_EVERY_DAYS", "PAGE_SIZE", "PlaceCatalogSync", "SyncOutcome"]

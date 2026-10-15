# -*- coding: utf-8 -*-
"""수정 접수의 「완료」 — 같은 여행의 **새 판**을 쓴다. 웹 「일정 수정」과 채팅 고치기가 **같은 함수**를 쓴다. `[2026-10-15]`

    store_place  장소 한 곳 → 장소 행 id(등록 · 수정 「완료」 · 채팅 고치기가 같은 규칙)
    commit       수정 접수의 그 판 → 새 판(장소 행 · 판정 · 판 · 변경 이력 · 알림 하나). 바뀐 것이 없으면 판을 쓰지 않는다

☆왜 떼어 냈나: 「완료」가 웹 경로(`trip_api._confirm_reopened`) 안에만 있어 채팅이 쓸 수 없었다. 그래서 채팅은 시각 옮기기 · 넣기 · 빼기 ·
  이름 말한 곳으로 바꾸기를 「아직 채팅에서 하지 못해요」로 막고 있었다(x600 재시험 10-14: 옮기기 51건 중 40건 · 넣기 8/8 · 빼기 10/11 막힘).
  `[2026-10-13 사용자 결정]` 「일정 수정은 계획 확인 단계의 기능을 그대로 쓴다 · 채팅 변경이 쓰는 반영 길을 그대로 쓴다」를 채팅 쪽에도 지킨다.
"""
from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Callable
from uuid import UUID

#: ★외부 서비스에서 받은 장소 — 공용 장소 표에 쌓지 않고 **그 여행 전용 행**으로 넣는다(마이그레이션 029).
#:  `places[].attributes.source` 로 가린다. 일정 생성기의 관광공사 후보도 이 값을 단다(`planner.py`). `trip_api` 가 이 이름을 그대로 다시 내보낸다.
EXTERNAL_PLACE_SOURCES = frozenset({"tour_api", "kakao", "google_places",
                                    # ★`[2026-10-02]` 고객이 확인 화면에서 후보 · 검색 · 지도로 고른 장소(`intake/assemble._place_in`)
                                    "customer_pick",
                                    # ★`[2026-10-01 · 10-05 병합]` 요식 원장(`dining_ledger`)에서 찾은 가게도 여행 전용 행이다 — 공용 표에 쌓으면
                                    #   일정 접수의 이름 찾기 · 오타 교정이 그 이름들을 먼저 보게 된다(액티비티 항목까지 영향)
                                    "dining_ledger",
                                    # ★`[2026-10-05]` 인허가(사업자 등록) 자료에서 이름으로 찾은 식당 — 역시 그 여행 전용 행(영업시간 모름)
                                    "dining_license"})


class CommitRefused(Exception):
    """「완료」를 할 수 없다 — `status` 는 웹이 돌려줄 HTTP 상태(422 · 409), `code` · `message` · `detail` 은 오류 몸통 그대로."""

    def __init__(self, status: int, code: str, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.detail = status, code, message, detail


def store_place(conn, cur, tenant: str, trip_id: UUID, *, name: str, kind: str, lat: float, lon: float,
                weather_sensitive: bool | None, attributes: dict[str, Any]) -> UUID:
    """장소 한 곳 → 장소 행 id. 등록(`trip_api._insert`) · 수정 모드의 「완료」 · 채팅 고치기가 **같은 규칙**으로 넣는다."""
    # ★장소는 테넌트 안에서 (이름, 종류)로 하나다(UNIQUE). 이미 있으면 **그것을 쓴다.**
    #   ☆2026-09-14 — 처음엔 무조건 INSERT 해서, 두 번째 여행이 경복궁을 적자
    #     500 이 났다(개발 서버에서 발견. 시험은 여행마다 테넌트를 새로 만들어
    #     못 잡았다). 보낸 속성은 **빈 칸만 채운다** — 카탈로그 값을 고객 한 명의
    #     제출이 덮어쓰지 않게(`EXCLUDED || places` 는 오른쪽이 이긴다).
    if str(attributes.get("source") or "") in EXTERNAL_PLACE_SOURCES:
        # ☆같은 여행 안에서 같은 장소를 두 번 적을 수 있다 — 그 여행 행을 다시 쓴다
        cur.execute(
            "INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,"
            "attributes,trip_scope) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (tenant_id, trip_scope, name, kind) WHERE trip_scope IS NOT NULL "
            "DO UPDATE SET attributes = EXCLUDED.attributes || places.attributes "
            "RETURNING place_id",
            (tenant, name, kind, lat, lon, weather_sensitive,
             json.dumps(attributes, ensure_ascii=False), trip_id))
    else:
        cur.execute(
            "INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,"
            "attributes) VALUES (%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (tenant_id, name, kind) WHERE trip_scope IS NULL "
            # ★`[2026-09-28]` 요식 식당 행은 이 유일 조건 밖이다(마이그레이션 222) — 충돌 대상을 맞춘다
            "AND source_name IS DISTINCT FROM 'dining_ledger' DO UPDATE "
            "SET attributes = EXCLUDED.attributes || places.attributes "
            "RETURNING place_id",
            (tenant, name, kind, lat, lon, weather_sensitive,
             json.dumps(attributes, ensure_ascii=False)))
    place_id = cur.fetchone()[0]
    # ★`[2026-10-02]` 원장에서 고른 식당은 원장 가게와 바로 잇는다 — 새벽 확인 · 하루 점검이 코어 장소로
    #   원장을 찾는다(`dining.ledger.resolve_place`). 관광공사 ID 가 없는 원장 가게는 이렇게만 이어진다
    if attributes.get("dining_place_uid"):
        from app.domains.travel_ops.components.team_hooks import dining_ledger

        dining_ledger.link_core_place(conn, tenant, str(place_id), str(attributes["dining_place_uid"]))
    return place_id


def commit(*, store: Any, connect: Callable[[], Any], tenant: str, intake_id: UUID, revision: int,
           reopened: dict[str, Any], status: str, built: Any, now: datetime, cause_extra: dict[str, Any] | None = None,
           before_write: Callable[[], None] | None = None) -> tuple[int, bool, Any]:
    """수정 접수의 그 판 → 같은 여행의 새 판. (판 번호, 바꿨나, 새 판 계산(`reopen.EditPlan` · 바꾼 것 없으면 None)).

    쓰기는 채팅 변경과 같다(판 · 변경 이력 · 알림 하나, 낡은 판이면 409). 판정도 채팅 변경과 같이 **이번 변경으로 새로 생긴 위반**만 막는다.
    - `request_id` = `intake:{접수}:r{판}` — 두 번 불러도 판은 하나. 바뀐 것이 없으면 판을 쓰지 않는다
    - 지난 일정(끝 ≤ 지금)을 바꾸거나 빼거나 지난 때에 더하면 422 `item_in_past`
    - `before_write` — 새 판을 쓰기 직전에 한 번(웹의 비싼 작업 횟수 세기). `cause_extra` — 변경 이유에 덧붙일 값(채팅이면 `via: chat` · 고객 문장)
    """
    from app.domains.travel_ops.components.actions.itinerary_actions import introduced_violations
    from app.domains.travel_ops.components.intake import reopen
    from app.domains.travel_ops.components.itinerary.itinerary import StaleItinerary, fill_weather_sensitive
    from app.domains.travel_ops.components.itinerary.itinerary_changes import with_request

    trip_id, base_version = UUID(str(reopened["trip_id"])), int(reopened["version"])
    request_id = f"intake:{intake_id}:r{revision}"
    with connect() as conn:
        applied = store.version_for_request(conn, trip_id, request_id)
    if applied is not None:
        return applied, True, None                      # 이미 쓴 판 — 같은 「완료」를 다시 눌렀다
    if status == "confirmed":
        return base_version, False, None                # 이미 「완료」했고 바뀐 것이 없어 판을 안 쓴 접수
    # 고정 일정(지난 일정 등)이 남아 있으면 앞으로의 일정을 다 빼도 된다 — 「읽은 일정이 없어요」로 막지 않는다
    problems = [p for p in built.problems if not (p.code == "no_items" and reopened["frozen_item_ids"])]
    if problems:
        raise CommitRefused(422, "intake_incomplete", "등록 전에 채워야 할 값이 있습니다",
                            problems=[p.as_dict() for p in problems])
    with connect() as conn:
        trip, base_items = store.latest(conn, trip_id)
        if trip["version"] != base_version:
            raise CommitRefused(409, "stale_itinerary", "그 사이 일정이 바뀌었어요 — 일정 수정을 다시 열어 주세요",
                                version=trip["version"])
        plan = reopen.prepare(conn, tenant_id=tenant, intake_id=intake_id, revision=revision,
                              base_items=base_items, frozen_ids=set(reopened["frozen_item_ids"]), now=now)
    if plan.past:
        raise CommitRefused(422, "item_in_past", "지난 일정은 바꿀 수 없어요: " + ", ".join(plan.past), items=plan.past)
    if plan.unchanged:
        return base_version, False, None
    if before_write is not None:
        before_write()
    if any(spec["attributes"].get("dining_place_uid") for spec in plan.places.values()):
        from app.domains.travel_ops.components.team_hooks import dining_ledger

        dining_ledger.require_link_core_place()
    summary = plan.summary()
    cause = with_request({"category": "customer_request", "type": "edit", "summary": summary,
                          "intake_id": str(intake_id), **(cause_extra or {})}, request_id)
    with connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                for item in plan.items:
                    spec = plan.places.get(item.item_id)
                    if spec is None:
                        continue
                    found = None
                    if spec.get("place_id"):
                        # 접수가 아는 행 — 공용 행이거나 이 여행의 행일 때만 그대로 쓴다(다른 여행 전용 행을 가리키지 않게, 029)
                        cur.execute("SELECT place_id FROM places WHERE tenant_id=%s AND place_id=%s "
                                    "AND (trip_scope IS NULL OR trip_scope=%s)", (tenant, spec["place_id"], trip_id))
                        row = cur.fetchone()
                        found = row[0] if row else None
                    item.place_id = found or store_place(
                        conn, cur, tenant, trip_id, name=spec["name"], kind=spec["kind"], lat=spec["lat"],
                        lon=spec["lon"], weather_sensitive=spec["weather_sensitive"], attributes=spec["attributes"])
            fill_weather_sensitive(conn, tenant)           # 등록과 같다 — 방금 넣은 장소의 실내·야외 모름을 확실한 분류로 채운다
            placed = store.places_by_id(conn, [i.place_id for i in plan.items if i.item_id in plan.places])
            for item in plan.items:
                if item.item_id in plan.places:
                    item.place = placed.get(item.place_id)
            violations = introduced_violations(trip, base_items, plan.items)
            if violations:
                raise CommitRefused(422, "itinerary_infeasible",
                                    "이 일정은 그대로 수행할 수 없습니다: " + " / ".join(v.reason for v in violations),
                                    violations=[v.as_dict() for v in violations])
            try:
                version = store.append_version(conn, trip_id=trip_id, base_version=base_version, items=plan.items,
                                               reason="customer_request", causes=[cause])
            except StaleItinerary:
                now_trip, _ = store.latest(conn, trip_id)
                raise CommitRefused(409, "stale_itinerary", "그 사이 일정이 바뀌었어요 — 일정 수정을 다시 열어 주세요",
                                    version=now_trip["version"]) from None
            store.enqueue_notice(conn, trip_id=trip_id, version=version, payload={
                "text": summary + ".", "language": "ko", "causes": [cause],
                "changed": {"edit": {"changed": plan.changed, "added": plan.added, "removed": plan.removed}},
                "other_options": [], "replay": False, "version": version})
    return version, True, plan


__all__ = ["CommitRefused", "EXTERNAL_PLACE_SOURCES", "commit", "store_place"]

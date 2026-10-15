# -*- coding: utf-8 -*-
"""장소 닫힘 재난문자가 **DB 에 저장된 여행의 감시**까지 가서 그 장소만 막는다 `[2026-10-14 활동 팀 전달 1번 · 사용자 지시]`.

단위 시험(`tests/unit/travel/test_notice_place_closure.py`)은 판정 함수만 본다. 여기서는 실제 경로를 잇는다:

    재해구분 「기타」 문자(샘플 CSV 와 같은 열) → `DisasterMsgCsv.active` → `notice_impact`(closure)
    → `DisruptionCheck` → `TripWatcher.tick` 의 활동 재판정(`activity_disasters.rejudge` → 활동 팀 `disaster_verdict`)

★지키려는 것
 ①「경복궁 임시 휴관」은 경복궁 항목만 이상이다 — 같은 날 국립중앙박물관 항목은 영향 없음
 ②활동 판정이 등록되지 않았으면 공유 점검 결과 그대로(두 항목 다 이상 — 모름을 지우지 않는다)
 ③「하천변 · 해안가 출입금지」 같은 안전 수칙은 장소 닫힘으로 바뀌지 않는다(전국 5만 건 1판 오판 — 실내 장소에 걸리면 안 된다)

재현:

    python -m pytest tests/scenario/test_place_closure_watch.py -v
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.itinerary.itinerary import Item, TripStore
from app.domains.travel_ops.components.team_hooks import activity_ledger
from app.domains.travel_ops.components.watch.activity_disasters import rejudge
from app.domains.travel_ops.instances.activity.verdicts import disaster_verdict
from app.domains.travel_ops.ports.data_sources import notice_impact
from app.domains.travel_ops.ports.data_sources.base import TravelSources
from app.domains.travel_ops.ports.data_sources.disaster_msg import DisasterMsgCsv
from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck
from app.domains.travel_ops.scenarios.case_engine import cleanup_tenant
from app.infrastructure.db.session import get_connection

KST = ZoneInfo("Asia/Seoul")
DAY = "2026-10-20"
PLACES = [  # (이름, 실내 여부) — 둘 다 종로 · 용산 관광지
    ("경복궁", True),
    ("국립중앙박물관", False),
]


def _at(hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{DAY}T{hhmm}:00").replace(tzinfo=KST)


def _csv(tmp_path, *messages: tuple[str, str]):
    """샘플 CSV 와 같은 열(1행 영문 · 2행 한국어 열 이름). 문자는 그날 09시에 서울 전체로 온다."""
    path = tmp_path / "disaster.csv"
    cols = ["SN", "CRT_DT", "MSG_CN", "RCPTN_RGN_NM", "EMRG_STEP_NM", "DST_SE_NM"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        out = csv.writer(f)
        out.writerow(cols)
        out.writerow(["일련번호", "생성일시", "메시지내용", "수신지역명", "긴급단계명", "재해구분명"])
        for n, (kind, text) in enumerate(messages, 1):
            out.writerow([n, f"{DAY.replace('-', '/')} 09:00:00", text, "서울특별시 전체", "안전안내", kind])
    return DisasterMsgCsv(path)


@pytest.fixture()
def world():
    tenant = "closure_" + uuid4().hex[:10]
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "place closure watch"))
            cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",
                        (tenant, "closure-guest"))
            customer = cur.fetchone()[0]
            ids = {}
            for name, weather_sensitive in PLACES:
                cur.execute("INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,attributes) "
                            "VALUES (%s,%s,'attraction',37.57,126.97,%s,%s) RETURNING place_id",
                            (tenant, name, weather_sensitive, json.dumps({"district": "종로구"}, ensure_ascii=False)))
                ids[name] = cur.fetchone()[0]
        store = TripStore(tenant)
        items = [Item(item_id=uuid4(), seq=1, kind="activity", title="경복궁", place_id=ids["경복궁"],
                      starts_at=_at("10:00"), ends_at=_at("12:00"), detail={}),
                 Item(item_id=uuid4(), seq=2, kind="activity", title="국립중앙박물관", place_id=ids["국립중앙박물관"],
                      starts_at=_at("14:00"), ends_at=_at("16:00"), detail={})]
        with conn.transaction():
            trip_id, _ = store.create_trip(conn, customer_id=customer, title="경복궁과 박물관", locale="ko",
                                           party_size=2, items=items, constraints={})
    notice_impact.set_second_opinion(None)                 # 규칙만 — 모델은 따로 잰다(보고서)
    yield {"tenant": tenant, "store": store, "trip_id": trip_id}
    activity_ledger.clear()
    cleanup_tenant(tenant)


def _verdicts(world, source) -> dict[str, dict]:
    """DB 에 저장된 여행의 항목마다 공유 점검 → 활동 재판정. 감시(`TripWatcher.tick`)가 항목마다 하는 두 단계 그대로."""
    check = DisruptionCheck(TravelSources(disaster=source), limits=lambda: (60, 30)).check
    with get_connection() as conn:
        _, items = world["store"].latest(conn, world["trip_id"])
    out = {}
    for item in items:
        report = check(place=item.place, starts_at=item.starts_at)
        out[item.title] = rejudge(report, item)
    return out


def _closure_rows(report):
    return [d for d in report.get("disruptions") or [] if d.get("category") == "disaster_msg"]


def test_closure_message_blocks_only_the_named_place(world, tmp_path):
    activity_ledger.register(state=lambda *a, **k: None, indoor=lambda *a, **k: None, disaster=disaster_verdict)
    result = _verdicts(world, _csv(tmp_path, ("기타", "[국가유산청] 경복궁 임시 휴관합니다")))
    assert _closure_rows(result["경복궁"]), result["경복궁"]
    assert _closure_rows(result["경복궁"])[0]["impact"] == "closure"
    assert not _closure_rows(result["국립중앙박물관"]), result["국립중앙박물관"]
    assert result["국립중앙박물관"].get("activity_rejudged", {}).get("dropped") == 1


def test_without_activity_verdict_the_shared_check_keeps_both(world, tmp_path):
    activity_ledger.clear()
    result = _verdicts(world, _csv(tmp_path, ("기타", "[국가유산청] 경복궁 임시 휴관합니다")))
    assert _closure_rows(result["경복궁"]) and _closure_rows(result["국립중앙박물관"])


def test_beach_safety_rule_is_not_a_place_closure(world, tmp_path):
    activity_ledger.register(state=lambda *a, **k: None, indoor=lambda *a, **k: None, disaster=disaster_verdict)
    text = "[창원시] 많은 비와 강풍이 예상됩니다. 배수로 점검, 낙하물 주의, 해안가, 하천변 출입금지 등 안전에 유의하시기 바랍니다."
    result = _verdicts(world, _csv(tmp_path, ("기타", text)))
    for title in ("경복궁", "국립중앙박물관"):
        assert all(row.get("impact") != "closure" for row in _closure_rows(result[title])), result[title]

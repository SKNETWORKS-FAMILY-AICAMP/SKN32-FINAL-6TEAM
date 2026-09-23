# -*- coding: utf-8 -*-
"""확정 시나리오 하루를 재생한다 — 시연·동작 확인용.

    python -m scripts.replay_scenario                # 재생하고 통지를 화면에 보인다
    python -m scripts.replay_scenario --send         # 통지를 디스코드 웹훅으로 실제 보낸다
    python -m scripts.replay_scenario --keep         # 끝나도 데이터를 지우지 않는다

★`team_branch/jh/확정_시나리오_액티비티_수정_버전.md` 의 여섯 장면을 시각 순서대로
  흘린다. 사건은 사후에 정한 재생 입력이고, 통지 앞에 `[재생]` 이 붙는다(v11 §8-A).

★전용 테넌트(`scenario-demo-…`)에 심고 끝나면 지운다. 운영 테넌트를 건드리지 않는다.
  `--send` 는 그 테넌트의 바깥함만 비운다(`OutboxWorker(tenant_id=…)`).
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.infrastructure.db.session import get_connection
from app.infrastructure.travel.base import TravelSources
from app.infrastructure.travel.disruptions import DisruptionCheck
from app.infrastructure.travel.replay import (ReplayAir, ReplayRouteEvents, ReplayTimeline,
                                              ReplayWarning, ReplayWeather)
from app.modules.travel_ops.itinerary import Item, TripStore
from app.modules.travel_ops.trip_desk import TripDesk
from app.modules.travel_ops.trip_watch import TripWatcher

KST = ZoneInfo("Asia/Seoul")
SCENARIO_PATH = (Path(__file__).resolve().parents[1] / "app" / "modules" / "travel_ops"
                 / "scenarios" / "seoul_day_taiwan_friends.json")


class Clock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now


def seed(tenant: str, scenario: dict, day: str) -> tuple[TripStore, object]:
    at = lambda hhmm: datetime.fromisoformat(f"{day}T{hhmm}:00").replace(tzinfo=KST)  # noqa: E731
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "scenario demo"))
            cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) "
                        "RETURNING customer_id", (tenant, "taiwan-friends"))
            customer = cur.fetchone()[0]
            ids = {}
            for place in scenario["places"]:
                cur.execute(
                    "INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,"
                    "attributes) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING place_id",
                    (tenant, place["name"], place["kind"], place["lat"], place["lon"],
                     place["weather_sensitive"], json.dumps(place["attributes"], ensure_ascii=False)))
                ids[place["key"]] = cur.fetchone()[0]
        store = TripStore(tenant)
        items = [Item(item_id=uuid4(), seq=it["seq"], kind=it["kind"], title=it["title"],
                      place_id=ids.get(it.get("place")), starts_at=at(it["start"]),
                      ends_at=at(it["end"]),
                      detail={**it.get("detail", {}),
                              **({"route": it["route"]} if "route" in it else {})})
                 for it in scenario["items"]]
        with conn.transaction():
            trip_id, _ = store.create_trip(
                conn, customer_id=customer, title=scenario["trip"]["title"],
                locale=scenario["trip"]["locale"], party_size=scenario["trip"]["party_size"],
                items=items, constraints=scenario["trip"].get("constraints"))
    return store, trip_id


def cleanup(tenant: str) -> None:
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for sql in ("DELETE FROM outbox WHERE tenant_id=%s", "DELETE FROM trips WHERE tenant_id=%s",
                    "DELETE FROM places WHERE tenant_id=%s", "DELETE FROM customers WHERE tenant_id=%s",
                    "DELETE FROM tenants WHERE tenant_id=%s"):
            cur.execute(sql, (tenant,))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="통지를 디스코드로 실제 보낸다")
    parser.add_argument("--keep", action="store_true", help="끝나도 재생 데이터를 남긴다")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    scenario = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    day = scenario["trip"]["date"]
    at = lambda hhmm: datetime.fromisoformat(f"{day}T{hhmm}:00").replace(tzinfo=KST)  # noqa: E731
    tenant = "scenario-demo-" + uuid4().hex[:8]
    clock = Clock(at("08:00"))
    store, trip_id = seed(tenant, scenario, day)
    timeline = ReplayTimeline(scenario["timeline"], clock)
    check = DisruptionCheck(TravelSources(weather=ReplayWeather(timeline),
                                          warning=ReplayWarning(timeline),
                                          air=ReplayAir(timeline)),
                            limits=lambda: (60, 30)).check
    watcher = TripWatcher(store=store, check=check, connection_factory=get_connection, clock=clock,
                          routes=scenario["routes"], route_events=ReplayRouteEvents(timeline))
    desk = TripDesk(store=store, connection_factory=get_connection)
    reports = {report["type"]: report for report in scenario["customer_reports"]}

    print(f"[재생] {scenario['trip']['title']} · {day} · 테넌트 {tenant}\n")
    steps = [
        ("09:00", "액-02", lambda: watcher.tick()),
        ("10:45", "이동-B1", lambda: watcher.tick()),
        ("13:00", "요식-P3", lambda: desk.report_delay(
            trip_id=trip_id, at=at("13:00"), minutes=reports["delay"]["minutes"],
            message=reports["delay"]["message"])),
        ("14:50", "(성수→경복궁 정상)", lambda: watcher.tick()),
        ("17:10", "이동-A6", lambda: watcher.tick()),
        ("18:00", "요식-P7", lambda: desk.report_closed(
            trip_id=trip_id, at=at("18:00"), message=reports["closed"]["message"])),
        ("19:40", "액-08", lambda: desk.ask_nearby_store(
            trip_id=trip_id, at=at("19:40"), products=reports["stock_out"]["products"],
            message=reports["stock_out"]["message"])),
    ]
    try:
        for hhmm, scene, run in steps:
            clock.now = at(hhmm)
            outcome = run()
            texts = []
            if hasattr(outcome, "adjusted"):
                texts = [change["notice"]["text"] for change in outcome.adjusted]
                if outcome.fatal or outcome.unresolved:
                    texts.append(f"(치명 {len(outcome.fatal)} · 못 품 {len(outcome.unresolved)})")
            elif isinstance(outcome, dict):
                texts = [outcome.get("notice", {}).get("text") or outcome.get("text")
                         or f"({outcome.get('status')})"]
            print(f"{hhmm}  {scene}")
            for text in texts or ["변화 없음"]:
                print(f"       → {text}")
        with get_connection() as conn:
            trip, items = store.latest(conn, trip_id)
        print(f"\n최종 일정 (버전 {trip['version']})")
        for item in items:
            print(f"  {item.starts_at:%H:%M}~{(item.ends_at or item.starts_at):%H:%M}  {item.title}")
        if args.send:
            from app.core.settings import REPO_ROOT, get_settings
            from app.infrastructure.messaging.worker import OutboxWorker
            from app.infrastructure.notify import DiscordWebhook, PhraseCache
            from app.infrastructure.notify.translate import make_translator
            from app.infrastructure.ollama_chat import from_settings

            # ★여행 언어(zh-TW)로 옮겨 보낸다(결정 14) — Ollama(Gemma 4)가 있을 때.
            settings = get_settings()
            chat = from_settings(settings)
            # ★문구틀은 언어마다 한 번만 옮긴다 — 하루치 안내가 여러 건이라 여기서 바로 재사용된다.
            phrases = PhraseCache(path=(REPO_ROOT / settings.notice_phrasebook_path)
                                  if settings.notice_phrasebook_path else None)
            phrases.load()
            hook = DiscordWebhook(settings.discord_webhook_url, phrases=phrases,
                                  translator=make_translator(chat) if chat else None)
            worker = OutboxWorker(get_connection, hook, tenant_id=tenant)
            sent = 0
            while worker.process_once():
                sent += 1
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT status, count(*) FROM outbox WHERE tenant_id=%s GROUP BY status",
                            (tenant,))
                print(f"\n디스코드 전송: 처리 {sent}건 · 상태 {dict(cur.fetchall())}")
            phrases.save()
            print(f"문구틀 캐시: {phrases.stats()}")
    finally:
        if not args.keep:
            cleanup(tenant)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

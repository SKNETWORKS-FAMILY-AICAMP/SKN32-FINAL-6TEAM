"""멈춘 Case 를 되잡는다: python -m scripts.run_sweepers --once

    --once      한 번 돌고 끝난다(cron·수동 실행용). 기본값이다.
    --interval  N 초마다 되돌린다(상주 실행용).
    --only      classifying | routing | trip | trip_cases | trip_safety | trip_dawn | trip_reminders | place_facts | catalog_hours | trip_places | web_guard | retention 중 하나만 돌린다.

★`retention` 은 **약관의 보관 기간 · 회원 자료 정리**다(`[2026-10-07 사용자 결정]`, 마이그레이션 056). 마지막 이용 뒤 `retention.member_idle_days` 가 지난 회원의 자료를 지우는데,
  **기본 모드는 `dry_run`(대상을 세기만 하고 `retention_runs` 에 건수를 남긴다 — 아무것도 안 지운다)** 이고 `on` 은 사용자가 건수를 보고 승인한 뒤 관리 화면에서 켠다.
  평소 실행에서는 `web_guard` 안에서 **하루에 한 번만** 돈다(주기 문). `--only retention` 은 문을 건너뛰고 바로 한 번 돈다(수동 건수 확인).

★`trip_safety` 는 **재난 시 일정 정지**다(`[2026-10-06 사용자 결정]`). 진행 중인(그리고 아직 시작하지 않은 — 이때는 여행 전체 정지만) 여행마다 재난문자 · 지진을 점검해, 재난이 난 시각에 그 지역에 여행객이 있었으면 그날 일정을 정지하고
  (전쟁 · 활화산 폭발 같은 심각한 사건은 여행 전체) 대피 장소를 안내하는 안전 알림을 낸다. 기본 실행에서는 **감시 주기 문을 지난 회차에 감시 앞에서** 같이 돈다.

★`catalog_hours` 는 **관광공사 목록 운영시간 새벽 읽기**다(`[2026-09-29 사용자 지시]`, 마이그레이션 036). 03:00~08:00 창 안에서
  처음 보는 곳 · 목록 수정 시각이 바뀐 곳만 한 번에 10곳, 하룻밤 600곳까지 읽어 `catalog_hours` 에 적는다. 활동 「다른 데로 바꿔」는
  요청 자리에서 관광공사를 부르지 않고 이 표만 읽는다(`catalog_pool`).

★`trip_dawn` 은 **새벽 식당 영업 확인**이다(`[2026-09-25]`, D-020). 03:00~08:00 창 안에서만 구글 장소로
  그날 식사 일정이 계획한 시각에 여는지 보고, 안 열면 같은 판정 문으로 바꾸거나 묻는다. 항목·날짜마다
  한 번만 부른다. ★키(`ACOP_GOOGLE_MAPS_API_KEY`)가 비어 있으면 `disabled` 로 답한다. 하루 시작 알림
  **앞에** 돈다 — 새벽에 고친 것을 하루 시작 알림이 싣는다.

★`trip_reminders` 는 **일정 안내**(v11 §6-B ②하루 시작 · ③항목 출발)다(`[2026-09-18]`).
  Case 를 만들지 않고 LLM 을 부르지 않는다. 최신 일정 버전을 읽어 때가 된 안내를 바깥함에
  넣는다 — 같은 안내는 `outbox` UNIQUE 가 한 번만 받는다. 감시 뒤에 돈다.

★`[2026-10-03 사용자 결정]` **감시는 3분 주기**다 — 이 일꾼은 1분마다 돌지만 `--only` 없이 돌 때 감시(`trip_cases`)는 주기 문(`job_gate`)을 지난 회차에만 돈다.
  멈춘 Case 되잡기 · 일정 안내는 그대로 1분이다.

★`trip_cases` 는 **Case 버전의 감시 루프**다(`[2026-09-17]`). 점검은 `trip` 과 같고, 깨진
  항목을 직접 고치지 않고 **시스템 Case 를 열어** Controller → Team → 코어 적용으로 보낸다
  (v11 §6-A ① 「되잡기 작업은 Case 를 만들기만 한다」). `trip` 과 **함께 돌리지 않는다** —
  같은 사건을 두 경로가 다룬다.
  ★`[결정 2026-09-18]` **`--only` 없이 돌 때 들어가는 감시는 이쪽이다**(전에는 `trip`).
  실제 gemma4:12b 로 하루를 3회 돌려 감시 Case 3건이 매번 `resolved` 였다
  (wiki `records/evidence/CASE-VERSION-ITINERARY_이식검증.md` §7). `trip` 은 `--only trip` 으로 남는다.

★`trip` 은 v11 §6-A 의 **감시 루프**의 시나리오용 여행 버전이다(되잡기 작업 넷째, `--only trip`). 앞으로 90분 안에 시작할
  일정 항목을 실제 소스(기상·특보·재난문자·교통·대기)로 점검하고, 깨졌으면 새 일정
  버전 + 통지를 한 트랜잭션으로 쓴다. 보내는 일은 배달 루프(`run_outbox_worker`)다.
  `fatal`(결정 15 — 대체 소스까지 실패)은 고치지 않고 세어 알린다 → `--once` 면 exit 1.
  경로 사건: **도로 통제는 UTIC 가 답한다**(2026-09-14). `[미구현]` 지하철 무정차는
  실시간 소스가 없다 — 그 대상은 `unchecked` 로 센다(「사건 없음」이라 하지 않는다).

★두 sweeper 는 경계를 나누며 생긴 틈을 막는 장치다:

    분류를 Case 생성 트랜잭션 밖으로  →  `classifying` 잔류
    실행을 접수 응답 뒤로              →  `routing` 잔류

  자세한 경위는 `wiki/records/reports/2026-09-03_경계를_나누며_생긴_틈과_승인이_막혀있던_제안.md`.

★**돌리는 주기는 이 파일이 정하지 않는다.** 임계값은
  `config/guardrails.yaml` 의 `reliability.*_stuck_after_seconds` 이고, 얼마나
  자주 부를지는 운영이 정한다. 기본 `--once` 인 이유가 그것이다 — 상주 루프를
  기본으로 두면 "언제 도는지" 가 코드에 숨는다.

★출력은 JSON 한 줄이다. `run_daily_feedback` 과 같은 관례이며, 세는 칸을 그대로
  낸다 — 특히 `errored` 는 **아무것도 기록하지 못한** 수라서 다음 회차에 또
  걸린다. 0 이 아니면 사람이 봐야 한다.

★**그 "사람이 봐야 한다" 를 실제로 전달한다**(2026-09-07). 전에는 세어서 찍기만
  하고 **exit 0** 이었다 — cron 에 걸어 두면 실패가 로그 속에만 남아 아무도 안
  본다. 세는 것과 알리는 것은 다르다(`CLAUDE.md` §3).

    --once      `errored` 가 있으면 **exit 1**. cron 이 실패로 본다
    --interval  **죽지 않는다.** 상주 sweeper 가 첫 실패에 멈추면 되잡기 자체가
                멈춘다 — 대신 stderr 로 알리고 계속 돈다

  어느 쪽이든 사유는 **stderr** 로 나간다. stdout 은 JSON 한 줄이라는 계약을
  지켜야 파이프로 받아 쓰는 쪽이 안 깨진다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from app.application.classification_sweeper import sweep_stuck_classifying
from app.application.routing_sweeper import sweep_stuck_routing
from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection


def _run_once(tenant_id: str, only: str | None) -> dict[str, dict[str, int]]:
    from app import composition

    result: dict[str, dict[str, int]] = {}
    if only in (None, "classifying"):
        classifier = composition.build_classifier()
        with get_connection() as conn:
            result["classifying"] = sweep_stuck_classifying(
                conn, tenant_id=tenant_id, classifier=classifier, actor_id="sweeper")
    if only in (None, "routing"):
        controller = composition.build_controller()

        def run_case(*, tenant_id: str, case_id, actor_id: str):
            # ★Controller 의 run_case 는 coroutine 이다. sweeper 는 동기 루프라
            #   여기서 돌려 준다 — sweeper 가 asyncio 를 알 필요가 없다.
            import asyncio

            return asyncio.run(controller.run_case(
                tenant_id=tenant_id, case_id=case_id, actor_id=actor_id))

        with get_connection() as conn:
            result["routing"] = sweep_stuck_routing(
                conn, tenant_id=tenant_id, run_case=run_case, actor_id="sweeper")
    # ★`[결정 2026-09-18]` 기본 감시는 **Case 버전**(`trip_cases`)이다. 시나리오용 여행 버전(`trip`)은
    #   `--only trip` 으로만 돈다. 둘을 함께 돌리지 않는다 — 같은 사건을 두 경로가 다룬다.
    if only == "trip":
        result["trip"] = _run_trip_watch(tenant_id)
    if only == "trip_safety":
        result["trip_safety"] = _run_trip_safety(tenant_id)
    if only in (None, "trip_cases"):
        # ★`[2026-10-03 사용자 결정]` 감시는 **3분 주기**(D-017) — 일꾼은 1분마다 돌지만 감시는 주기 문을 지난 회차에만 돈다. `--only trip_cases` 는 문을 안 본다(손으로 부르는 것)
        result["trip_cases"] = _watch_if_due(tenant_id, forced=only == "trip_cases")
    # ★새벽 식당 확인 — 창(03:00~08:00) 밖이면 아무것도 안 부른다. 하루 시작 알림보다 **먼저** 돈다
    if only in (None, "trip_dawn"):
        result["trip_dawn"] = _run_trip_dawn(tenant_id)
    # ★감시 **뒤에** 돈다 — 변경 통지가 먼저 나가고, 안내는 바뀐 최신 일정으로 계산된다(v11 §6-B).
    if only in (None, "trip_reminders"):
        result["trip_reminders"] = _run_trip_reminders(tenant_id)
    # ★`[2026-09-29]` 여행에 새로 들어온 장소의 운영시간 · 문의 전화를 관광공사에서 한 번 읽어 적는다(`place_info.py`)
    #   — 일정 상세에 보이고 판정기 · 새벽 확인이 쓴다. 새 장소만 읽으므로 평소에는 0건이다
    if only in (None, "place_facts"):
        result["place_facts"] = _run_place_facts(tenant_id)
    if only in (None, "catalog_hours"):
        # ★`[2026-09-29 사용자 지시]` 관광공사 목록 운영시간 새벽 읽기 — 창(03:00~08:00) 밖이면 아무것도 안 한다
        result["catalog_hours"] = _run_catalog_hours(tenant_id)
    # ★끝난 여행의 전용 장소 행(029)에서 외부 서비스 값(좌표·식별자)을 비운다 — 약관, `trip_places.py` 머리
    if only in (None, "trip_places"):
        result["trip_places"] = _run_trip_places(tenant_id)
    # ★`[2026-09-28]` 웹 남용 방어 — 여행을 하나도 안 만든 사용자 키 정리 + 오래된 사용량 줄(주소 해시 48시간) 삭제
    if only in (None, "web_guard"):
        result["web_guard"] = _run_web_guard(tenant_id)
    if only == "retention":
        result["retention"] = _run_retention(tenant_id, forced=True)
    return result


def _run_place_facts(tenant_id: str) -> dict[str, object]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.infrastructure.ollama_chat import from_settings
    from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
    from app.domains.travel_ops.components.places.place_info import fill_missing_facts

    settings = get_settings()
    with get_connection() as conn:
        return fill_missing_facts(conn, tenant_id, source=build_travel_sources(settings).place,
                                  chat=from_settings(settings), now=datetime.now(ZoneInfo("Asia/Seoul")))


def _run_catalog_hours(tenant_id: str) -> dict[str, object]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.core.settings import get_guardrails
    from app.infrastructure.ollama_chat import from_settings
    from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
    from app.domains.travel_ops.components.places.catalog_hours import prefill

    settings, guard = get_settings(), get_guardrails()
    with get_connection() as conn:
        return prefill(conn, tenant_id=tenant_id, source=build_travel_sources(settings).place,
                       chat=from_settings(settings), now=datetime.now(ZoneInfo("Asia/Seoul")),
                       start=str(guard.get("travel.catalog_hours.start")),
                       until=str(guard.get("travel.catalog_hours.until")),
                       per_night=int(guard.get("travel.catalog_hours.per_night")),
                       per_tick=int(guard.get("travel.catalog_hours.per_tick")),
                       retry_days=int(guard.get("travel.catalog_hours.retry_days")))


def _run_retention(tenant_id: str, *, forced: bool) -> dict[str, object]:
    """회원 자료 정리(모드에 따라 세기만 · 지움 · 안 함) — 하루에 한 번. `forced` 면 주기 문을 건너뛴다."""
    from app.application.job_gate import claim
    from app.domains.travel_ops.modules.web_account import member_cleanup

    with get_connection() as conn:
        if not forced:
            with conn.transaction():
                if not claim(conn, tenant_id=tenant_id, gate="member_retention", min_seconds=23 * 3600):
                    return {"skipped_until_due": 1}
        return member_cleanup.run(conn, tenant_id)


def _run_web_guard(tenant_id: str) -> dict[str, object]:
    from app.domains.travel_ops.components.customer.consents import purge_expired
    from app.domains.travel_ops.modules.web_account.guest_cleanup import cleanup_guests
    from app.domains.travel_ops.modules.web_account.web_guard import prune_usage

    with get_connection() as conn:
        # ★`[2026-10-04 D-CS-011]` 옛 「빈 키 정리」를 게스트 정리가 대신한다 — 마지막 사용 뒤 `web.guest_idle_hours` 가 지난 게스트의 여행 · 세션 · 키 · 사용자
        # ★`[2026-10-05]` 보관 기간(`consent.evidence_retention_days`)이 지난 동의 기록도 여기서 지운다 — 동의 기록을 지우는 곳은 이 함수 하나뿐이다
        out = {**prune_usage(conn, tenant_id), "guests": cleanup_guests(conn, tenant_id), "consent_events_purged": purge_expired(conn, tenant_id)}
    # ★`[2026-10-07]` 회원 자료 정리 — 하루 한 번(주기 문) · 기본은 세기만(dry_run). 별도 연결로 돈다(위 정리와 트랜잭션이 섞이지 않게)
    return {**out, "retention": _run_retention(tenant_id, forced=False)}


def _run_trip_places(tenant_id: str) -> dict[str, object]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.core.settings import get_guardrails
    from app.domains.travel_ops.components.itinerary.trip_places import scrub_ended

    with get_connection() as conn:
        return scrub_ended(conn, tenant_id=tenant_id, now=datetime.now(ZoneInfo("Asia/Seoul")),
                           retention_hours=float(get_guardrails().get("travel.trip_place_retention_hours")))


def _run_trip_dawn(tenant_id: str) -> dict[str, object]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.core.settings import get_guardrails
    from app.domains.travel_ops.ports.data_sources.google_places import GooglePlaces
    from app.domains.travel_ops.components.watch.dawn_check import DawnCheck
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore

    from app.domains.travel_ops.ports.data_sources.base import build_travel_sources

    settings = get_settings()
    key = settings.google_maps_api_key
    # ★하루 호출 상한(`ACOP_RATE_GOOGLE_PLACES_PER_DAY`)을 **같은 제한기**로 건다 — 넘으면 부르지 않고
    #   `rate_limited` 로 세며, 그 항목은 `fatal` 로 남아 창 안에서 다시 시도된다(요금이 새지 않게).
    from app.domains.travel_ops.ports.data_sources.call_budget import CallBudget, google_caps

    # ★무료 한도 보호 — DB 예산(027)을 **반드시** 건다. 프로세스 안 제한기는 매분 새로 차서 못 지킨다
    budget = CallBudget(connection_factory=get_connection, caps=google_caps())
    source = (GooglePlaces(api_key=key, budget=budget, limiter=build_travel_sources(settings).limiter,
                           match_radius_m=float(get_guardrails().get("travel.dawn_check.match_radius_m")))
              if key else None)
    outcome = DawnCheck(store=TripStore(tenant_id), connection_factory=get_connection,
                        clock=lambda: datetime.now(ZoneInfo("Asia/Seoul")), source=source).tick()
    return outcome.counts()


def _run_trip_reminders(tenant_id: str) -> dict[str, int]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore
    from app.domains.travel_ops.entry.trip_api import plan_url
    from app.domains.travel_ops.components.watch.trip_reminders import TripReminders

    sources = build_travel_sources(get_settings())
    reminders = TripReminders(store=TripStore(tenant_id), connection_factory=get_connection,
                              clock=lambda: datetime.now(ZoneInfo("Asia/Seoul")),
                              route_events=sources.route_events,
                              link=lambda trip_id: plan_url(tenant_id, trip_id))
    outcome = reminders.tick()
    return {"trips": outcome.trips, "sent": len(outcome.sent), "already": outcome.already,
            "held": len(outcome.held), "fatal": len(outcome.fatal), "no_route": outcome.no_route}


def _watch_if_due(tenant_id: str, *, forced: bool) -> dict[str, int]:
    """감시(`trip_cases`)를 주기 문 뒤에서 돌린다. 문이 닫혀 있으면 `{"skipped_until_due": 1}` — 아무것도 안 부른다(외부 소스 포함).

    ☆왜: 이 일꾼은 1분마다 도는데 감시는 3분 주기다(`reliability.watch_interval_seconds`). 일꾼 전체를 3분으로 바꾸면 일정 출발 안내와 멈춘 Case 되잡기가
      늦어져서 감시만 막는다. 일꾼은 회차마다 새 프로세스라 마지막 실행 시각은 DB 에 둔다(`job_gates`, 마이그레이션 041).
    """
    if not forced:
        from app.application.job_gate import WATCH_GATE, claim, interval_seconds
        from app.core.settings import get_guardrails

        _, min_seconds = interval_seconds(get_guardrails())
        with get_connection() as conn, conn.transaction():
            if not claim(conn, tenant_id=tenant_id, gate=WATCH_GATE, min_seconds=min_seconds):
                return {"skipped_until_due": 1}
    return _run_trip_watch_cases(tenant_id)


def _run_trip_safety(tenant_id: str) -> dict[str, int]:
    """진행 중인 여행의 재난 · 지진 사건을 점검해 일정을 정지하고 안전 알림을 낸다(`SafetySweep`)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
    from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore
    from app.domains.travel_ops.components.watch.safety_pause import SafetySweep

    check = DisruptionCheck(build_travel_sources(get_settings()))
    sweep = SafetySweep(store=TripStore(tenant_id), check=check.check_safety, release=check.released,
                        connection_factory=get_connection, clock=lambda: datetime.now(ZoneInfo("Asia/Seoul")))
    return sweep.tick().counts()


def _run_trip_watch_cases(tenant_id: str) -> dict[str, int]:
    import asyncio
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app import composition
    from app.infrastructure.db import repository
    from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
    from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore
    from app.domains.travel_ops.components.watch.trip_watch_cases import TripWatchCaseOpener

    # ★`[2026-10-06 사용자 결정]` 재난 정지 점검은 감시 **앞에** 같은 주기로 돈다 — 정지가 먼저 걸려야 같은 회차의 감시가 그 여행을 건너뛴다(`TripStore.due`).
    #   실패해도 감시는 돈다(정지 점검의 예외가 일정 감시를 막지 않는다 — 실패는 세고 로그에 남긴다). 결과는 `safety_*` 칸으로 감시 결과에 합친다
    try:
        safety = {f"safety_{key}": value for key, value in _run_trip_safety(tenant_id).items()}
    except Exception:                                    # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception("safety sweep failed")
        safety = {"safety_errored": 1}
    sources = build_travel_sources(get_settings())
    controller = composition.build_controller()

    def run_case(**kwargs):
        # ★Controller 의 run_case 는 coroutine 이다 — sweeper 는 동기 루프라 여기서 돌린다.
        return asyncio.run(controller.run_case(**kwargs))

    opener = TripWatchCaseOpener(
        store=TripStore(tenant_id), check=DisruptionCheck(sources).check,
        connection_factory=get_connection, clock=lambda: datetime.now(ZoneInfo("Asia/Seoul")),
        repository=repository, run_case=run_case, route_events=sources.route_events)
    outcome = opener.tick()
    escalated = sum(1 for run in outcome.ran if run.get("status") == "escalated")
    return {**safety, "checked": outcome.checked, "opened": len(outcome.opened), "existing": len(outcome.existing),
            "ran": len(outcome.ran), "escalated": escalated, "fatal": len(outcome.fatal),
            "unhandled": len(outcome.unhandled), "pinned": len(outcome.pinned),
            "unchecked": len(outcome.unchecked)}


def _run_trip_watch(tenant_id: str) -> dict[str, int]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
    from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore
    from app.domains.travel_ops.components.watch.trip_watch import TripWatcher

    sources = build_travel_sources(get_settings())
    watcher = TripWatcher(
        store=TripStore(tenant_id),
        check=DisruptionCheck(sources).check,
        connection_factory=get_connection,
        clock=lambda: datetime.now(ZoneInfo("Asia/Seoul")),
        # ★도로 통제는 UTIC 가 답한다. 지하철 무정차는 소스가 없어 `unchecked` 로 센다.
        route_events=sources.route_events)
    outcome = watcher.tick()
    return {"checked": outcome.checked, "adjusted": len(outcome.adjusted),
            "fatal": len(outcome.fatal), "unresolved": len(outcome.unresolved),
            "unhandled": len(outcome.unhandled), "pinned": len(outcome.pinned),
            "unchecked": len(outcome.unchecked), "rechecked": len(outcome.rechecked)}


def _report_errors(result: dict[str, dict[str, int]]) -> int:
    """`errored` 를 stderr 로 알리고 총합을 돌려준다.

    ★`errored` 와 `failed` 는 다르다. `failed` 는 실패를 **기록까지 한** 것이라
      Case 가 escalated 로 넘어가 사람 손에 들어간다. `errored` 는 아무것도
      기록하지 못한 것이라 Case 가 그 상태에 그대로 남고 **다음 회차에 또 걸린다** —
      아무도 안 보면 영원히 돈다.
    """
    total = 0
    for name, counts in sorted(result.items()):
        # ★결정 15 — 대체 소스까지 실패한 치명은 **사람이 봐야 한다.** 세기만 하고 넘기지 않는다.
        fatal = int(counts.get("fatal", 0))
        if fatal:
            total += fatal
            print(f"★{name} sweeper: fatal={fatal} — 소스가 대체까지 실패해 판정하지 못한 "
                  f"일정 항목이 있다(결정 15)", file=sys.stderr, flush=True)
        errored = int(counts.get("errored", 0))
        if errored:
            total += errored
            print(f"★{name} sweeper: errored={errored} · scanned={counts.get('scanned')} "
                  f"— 아무것도 기록하지 못했다. 다음 회차에 또 걸린다",
                  file=sys.stderr, flush=True)
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", default=True)
    parser.add_argument("--interval", type=int, default=None,
                        help="N 초마다 반복한다. 주면 --once 를 덮는다")
    parser.add_argument("--only", choices=("classifying", "routing", "trip", "trip_cases", "trip_safety", "trip_dawn", "place_facts",
                                           "catalog_hours",
                                           "trip_reminders", "trip_places", "web_guard", "retention"),
                        default=None)
    args = parser.parse_args()

    tenant_id = get_settings().tenant_id
    if args.interval is None:
        result = _run_once(tenant_id, args.only)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        # ★한 번 돌고 끝나는 모드는 exit code 가 유일한 신호다. cron 이 이걸 본다.
        return 1 if _report_errors(result) else 0

    # ★상주 모드에서도 한 회차의 결과를 그때그때 낸다. 다 끝나고 모아 내면
    #   중간에 죽었을 때 아무 기록도 안 남는다.
    while True:
        result = _run_once(tenant_id, args.only)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        # ★여기서는 **끝내지 않는다.** 상주 sweeper 가 첫 실패에 멈추면 되잡기
        #   자체가 멈춘다 — 멈춘 Case 를 되잡는 장치가 멈추는 것이 더 나쁘다.
        _report_errors(result)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

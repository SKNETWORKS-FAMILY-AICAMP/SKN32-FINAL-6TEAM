"""멈춘 Case 를 되잡는다: python -m scripts.run_sweepers --once

    --once      한 번 돌고 끝난다(cron·수동 실행용). 기본값이다.
    --interval  N 초마다 되돌린다(상주 실행용).
    --only      classifying | routing | trip | trip_cases | trip_safety | trip_dawn | trip_reminders | place_facts | catalog_hours | trip_places | web_guard | retention 중 하나만 돌린다.
                `team:<이름>` 은 팀이 끼운 정기 작업 하나를 시간대와 상관없이 지금 돌린다(`team_hooks/scheduled_jobs`).

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
import logging
import threading
from contextvars import ContextVar
from functools import wraps

from app.core.service_bindings import bind_services, current_bindings
from app.core.team_availability import TeamUnavailable
from app.application.classification_sweeper import sweep_stuck_classifying
from app.application.routing_sweeper import sweep_stuck_routing
from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection


_round_controller: ContextVar[object | None] = ContextVar("sweeper_controller", default=None)
logger = logging.getLogger(__name__)
_features_ready = False
_features_lock = threading.Lock()


class _CompositionFailed(RuntimeError):
    """작업 실행 전에 후보 조립이 실패했음을 구분한다."""


class _FeaturesFailed(RuntimeError):
    """감시 범위 연결까지 포함한 기능 초기화 실패를 구분한다."""


def _wire_features():
    """프로세스 설정의 상태 있는 제공자를 성공 후 교체하지 않는다. 실패는 재시도한다."""
    global _features_ready
    from app import composition
    with _features_lock:
        if _features_ready:
            return
        try:
            composition.wire_optional_features()
        except Exception as exc:
            logger.error("sweeper_features_failed error_type=%s", type(exc).__name__)
            raise _FeaturesFailed() from exc
        _features_ready = True


def _in_round(method):
    """한 회차의 Controller와 계산 표를 함께 보존한다. 중첩 작업도 같은 판이다."""
    @wraps(method)
    def call(*args, **kwargs):
        if _round_controller.get() is not None:
            return method(*args, **kwargs)
        from app import composition

        try:
            controller = composition.build_controller()
        except Exception as exc:
            logger.error("sweeper_composition_failed error_type=%s", type(exc).__name__)
            raise _CompositionFailed() from exc
        _wire_features()
        token = _round_controller.set(controller)
        try:
            with bind_services(getattr(controller, "service_bindings", None)):
                return method(*args, **kwargs)
        finally:
            _round_controller.reset(token)
    return call


def _team_job(method):
    """필수 계산 불가는 성공으로 바꾸지 않고, 독립 작업은 다음으로 진행한다."""
    @wraps(method)
    def call(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except TeamUnavailable as exc:
            table = current_bindings()
            logger.warning("sweeper_team_unavailable job=%s team_id=%s reason=%s composition_revision=%s",
                           method.__name__, exc.team_id, exc.reason, getattr(table, "revision", None))
            counts = {"team_unavailable": 1, "skipped": 1}
            if exc.reason in {"engine_unavailable", "composition_unbound"}:
                counts["fatal"] = 1  # 활성 Team의 필수 데이터 장애는 의도적 비활성과 구분한다.
            return counts
    return call


def _run_once(tenant_id: str, only: str | None) -> dict[str, dict[str, int]]:
    # 독립 정리 작업만 요청한 회차에는 Team 조립을 요구하지 않는다.
    # ★`[2026-10-14]` 팀 정기 작업(`team:<이름>`)도 조립이 필요하다 — 작업 목록이 조립 판(`bind_services`) 안에만 있다.
    #   전에는 `--only team:<이름>` 이 조립 없이 돌아 등록된 작업을 못 찾고 빈 결과(`{}`)로 끝났다(손으로 부르는 입구가 아무것도 안 했다).
    if only in (None, "routing", "trip", "trip_cases", "trip_dawn", "trip_reminders") or (only or "").startswith("team:"):
        try:
            return _run_bound_once(tenant_id, only)
        except _CompositionFailed:
            failed = {"composition": {"fatal": 1}}
            try:
                _wire_features()
            except _FeaturesFailed:
                failed["features"] = {"fatal": 1}
            return {**failed, **_run_jobs(tenant_id, only, composition_failed=True,
                                         features_failed="features" in failed)}
        except _FeaturesFailed:
            return {"features": {"fatal": 1}, **_run_jobs(tenant_id, only, features_failed=True)}
    try:
        _wire_features()
    except _FeaturesFailed:
        return {"features": {"fatal": 1}, **_run_jobs(tenant_id, only, features_failed=True)}
    return _run_jobs(tenant_id, only)


@_in_round
def _run_bound_once(tenant_id: str, only: str | None) -> dict[str, dict[str, int]]:
    return _run_jobs(tenant_id, only)


def _run_jobs(tenant_id: str, only: str | None, *, composition_failed=False,
              features_failed=False) -> dict[str, dict[str, int]]:
    from app import composition

    result: dict[str, dict[str, int]] = {}

    def run(name, work, *, team=False):
        if team and (composition_failed or features_failed):
            reason = "features_unavailable" if features_failed else "composition_unavailable"
            result[name] = {reason: 1, "skipped": 1, "fatal": 1}
            return
        try:
            result[name] = work()
        except TeamUnavailable as exc:
            logger.warning("sweeper_job_unavailable job=%s team_id=%s reason=%s composition_revision=%s",
                           name, exc.team_id, exc.reason, getattr(current_bindings(), "revision", None))
            result[name] = {"team_unavailable": 1, "skipped": 1}
            if exc.reason in {"engine_unavailable", "composition_unbound"}:
                result[name]["fatal"] = 1
        except Exception as exc:
            logger.error("sweeper_job_failed job=%s error_type=%s composition_revision=%s",
                         name, type(exc).__name__, getattr(current_bindings(), "revision", None))
            result[name] = {"fatal": 1}

    if only in (None, "classifying"):
        def classify():
            classifier = composition.build_classifier()
            with get_connection() as conn:
                return sweep_stuck_classifying(conn, tenant_id=tenant_id, classifier=classifier, actor_id="sweeper",
                                               diagnostic_recorder=composition.build_operations_recorder())
        run("classifying", classify)
    if only in (None, "routing"):
        def route():
            controller = _round_controller.get()
            if controller is None:
                raise RuntimeError("routing sweeper requires a bound composition")

            def run_case(*, tenant_id: str, case_id, actor_id: str):
                import asyncio
                return asyncio.run(controller.run_case(tenant_id=tenant_id, case_id=case_id, actor_id=actor_id))

            with get_connection() as conn:
                return sweep_stuck_routing(conn, tenant_id=tenant_id, run_case=run_case, actor_id="sweeper")
        run("routing", route, team=True)
    # ★`[결정 2026-09-18]` 기본 감시는 **Case 버전**(`trip_cases`)이다. 시나리오용 여행 버전(`trip`)은
    #   `--only trip` 으로만 돈다. 둘을 함께 돌리지 않는다 — 같은 사건을 두 경로가 다룬다.
    if only == "trip":
        run("trip", lambda: _run_trip_watch(tenant_id), team=True)
    if only == "trip_safety":
        run("trip_safety", lambda: _run_trip_safety(tenant_id), team=features_failed)
    if only in (None, "trip_cases"):
        # ★`[2026-10-03 사용자 결정]` 감시는 **3분 주기**(D-017) — 일꾼은 1분마다 돌지만 감시는 주기 문을 지난 회차에만 돈다. `--only trip_cases` 는 문을 안 본다(손으로 부르는 것)
        if features_failed:
            result["trip_cases"] = {"features_unavailable": 1, "skipped": 1, "fatal": 1}
        elif composition_failed:
            run("trip_cases", lambda: _watch_if_due(tenant_id, forced=only == "trip_cases", composition_failed=True))
        else:
            run("trip_cases", lambda: _watch_if_due(tenant_id, forced=only == "trip_cases"))
    # ★새벽 식당 확인 — 창(03:00~08:00) 밖이면 아무것도 안 부른다. 하루 시작 알림보다 **먼저** 돈다
    if only in (None, "trip_dawn"):
        run("trip_dawn", lambda: _run_trip_dawn(tenant_id), team=True)
    # ★감시 **뒤에** 돈다 — 변경 통지가 먼저 나가고, 안내는 바뀐 최신 일정으로 계산된다(v11 §6-B).
    if only in (None, "trip_reminders"):
        run("trip_reminders", lambda: _run_trip_reminders(tenant_id), team=True)
    # ★`[2026-09-29]` 여행에 새로 들어온 장소의 운영시간 · 문의 전화를 관광공사에서 한 번 읽어 적는다(`place_info.py`)
    #   — 일정 상세에 보이고 판정기 · 새벽 확인이 쓴다. 새 장소만 읽으므로 평소에는 0건이다
    if only in (None, "place_facts"):
        run("place_facts", lambda: _run_place_facts(tenant_id))
    if only in (None, "catalog_hours"):
        # ★`[2026-09-29 사용자 지시]` 관광공사 목록 운영시간 새벽 읽기 — 창(03:00~08:00) 밖이면 아무것도 안 한다
        run("catalog_hours", lambda: _run_catalog_hours(tenant_id))
    # ★`[2026-10-13]` 에이전트 팀이 끼운 정기 작업(`instances/<팀>/jobs.py` → `team_hooks/scheduled_jobs`). 시간대 밖이면 부르지 않는다.
    #   `--only team:<이름>` 은 시간대를 보지 않는다(손으로 부르는 것). 활동의 웹 확인 배치 등 — 활동 → 코어 전달 사항(10-13) 2번
    if only is None or only.startswith("team:"):
        from app.domains.travel_ops.components.team_hooks import scheduled_jobs

        for job in scheduled_jobs.registered():
            key = f"team:{job.name}"
            if only in (None, key):
                run(key, lambda job=job: _run_team_job(tenant_id, job, forced=only == key))
    # ★끝난 여행의 전용 장소 행(029)에서 외부 서비스 값(좌표·식별자)을 비운다 — 약관, `trip_places.py` 머리
    if only in (None, "trip_places"):
        run("trip_places", lambda: _run_trip_places(tenant_id))
    # ★`[2026-09-28]` 웹 남용 방어 — 여행을 하나도 안 만든 사용자 키 정리 + 오래된 사용량 줄(주소 해시 48시간) 삭제
    if only in (None, "web_guard"):
        run("web_guard", lambda: _run_web_guard(tenant_id))
    if only == "retention":
        run("retention", lambda: _run_retention(tenant_id, forced=True))
    # ★`[2026-10-14 사용자 지시]` 일일 정기점검이 03:30 까지 안 끝났으면 관리자 웹앱에 보고 — 모든 작업이 돈 **뒤** 이 회차 결과로 판정한다
    if only is None:
        try:
            deadline = _daily_check_deadline(tenant_id, result)
        except Exception as exc:                          # noqa: BLE001 — 보고가 터져도 회차 결과는 남긴다. 세어서 남긴다
            logger.error("sweeper_job_failed job=daily_check error_type=%s", type(exc).__name__)
            deadline = {"fatal": 1}
        if deadline is not None:
            result["daily_check"] = deadline
    return result


def _run_place_facts(tenant_id: str) -> dict[str, object]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.infrastructure.ollama_chat import from_settings
    from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
    from app.domains.travel_ops.components.places.place_info import fill_missing_facts

    from app.core.settings import get_guardrails
    from app.domains.travel_ops.components.places.place_info import FILL_PER_TICK
    from app.domains.travel_ops.components.watch import daily_check

    settings, now, guard = get_settings(), datetime.now(ZoneInfo("Asia/Seoul")), get_guardrails()
    # ★`[2026-10-14 사용자 지시]` 일일 정기점검(03시 시작 · 가능하면 03:30 까지 · 08:00 멈춤) — 고객이 일정에 넣은 장소는 그날 03시 전에 읽은 값이면
    #   창 안에서 하루 한 번 다시 읽는다. 창 밖에서는 새로 들어온 장소만 읽는다(정기점검이 아니다)
    win = daily_check.from_guardrails(now, guard)
    cap = int(guard.get("travel.daily_check.max_per_tick"))
    with get_connection() as conn:
        return fill_missing_facts(conn, tenant_id, source=build_travel_sources(settings).place,
                                  chat=from_settings(settings), now=now,
                                  refresh_from=win.started_at.isoformat() if win.open else None,
                                  pace=lambda left: daily_check.paced(left, base=FILL_PER_TICK, cap=cap, win=win))


def _run_catalog_hours(tenant_id: str) -> dict[str, object]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.core.settings import get_guardrails
    from app.infrastructure.ollama_chat import from_settings
    from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
    from app.domains.travel_ops.components.places.catalog_hours import prefill

    from app.domains.travel_ops.components.watch import daily_check

    settings, guard = get_settings(), get_guardrails()
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    win = daily_check.from_guardrails(now, guard)
    base, cap = int(guard.get("travel.catalog_hours.per_tick")), int(guard.get("travel.daily_check.max_per_tick"))
    with get_connection() as conn:
        # ★`[2026-10-14 사용자 지시]` 일일 정기점검 — 03시 시작 · 가능하면 03:30 까지 끝나게 양을 맞추고 · 08:00 에 멈춘다(`travel.daily_check`)
        return prefill(conn, tenant_id=tenant_id, source=build_travel_sources(settings).place,
                       chat=from_settings(settings), now=now,
                       start=str(guard.get("travel.daily_check.start")),
                       until=str(guard.get("travel.daily_check.stop")),
                       per_night=int(guard.get("travel.catalog_hours.per_night")),
                       per_tick=base,
                       retry_days=int(guard.get("travel.catalog_hours.retry_days")),
                       pace=lambda left: daily_check.paced(left, base=base, cap=cap, win=win))


def _daily_check_deadline(tenant_id: str, result: dict, *, now=None) -> dict[str, object] | None:
    """일일 정기점검이 `finish_by`(03:30)까지 안 끝났으면 관리자 웹앱 「운영 진단」에 **하루 한 건** 보고한다. `[2026-10-14 사용자 지시]`

    ★판정은 03:30 이 지난 **첫 회차**에 한 번 한다(주기 문 `daily_check_deadline`) — 그 회차 결과에서 아직 남은 일이 있는 작업을 고른다(`daily_check.unfinished`).
    ★보고는 운영 진단 사건(`processing_error` · `DAILY_CHECK_OVERDUE`)이고, 조건에 안 끝난 작업 코드를 싣는다. 사건 번호를 날짜로 정해 같은 날 두 번 세지 않는다.
    ★08:00 이 지났거나 03:30 전이면 아무것도 안 한다(멈춤은 각 작업의 창이 지킨다)."""
    from datetime import datetime
    from uuid import NAMESPACE_URL, uuid5
    from zoneinfo import ZoneInfo

    from app.application.job_gate import claim
    from app.core.settings import get_guardrails
    from app.domains.travel_ops.components.watch import daily_check

    now = now or datetime.now(ZoneInfo("Asia/Seoul"))
    win = daily_check.from_guardrails(now, get_guardrails())
    if not win.past_finish_by:
        return None
    with get_connection() as conn, conn.transaction():
        if not claim(conn, tenant_id=tenant_id, gate="daily_check_deadline", min_seconds=20 * 3600):
            return None
    late, unknown = daily_check.unfinished(result)
    out: dict[str, object] = {"day": win.day, "late": late, "unknown": unknown}
    if not late:
        return out
    from app import composition
    from app.application import operations_diagnostics as diagnostics

    event = diagnostics.Event(
        event_id=uuid5(NAMESPACE_URL, f"triPilot:daily_check_overdue:{tenant_id}:{win.day}"), tenant_id=tenant_id,
        kind="processing_error", code="DAILY_CHECK_OVERDUE", deployment=diagnostics.deployment_version(),
        policy_version=composition.config_revision(composition.load_project_config()),
        conditions=[daily_check.code_of(name) for name in late])
    out["report"] = diagnostics.record(event, connection_factory=get_connection)["status"]
    logger.warning("daily_check_overdue day=%s late=%s", win.day, ",".join(late))
    return out


def _in_window(now, start: str, until: str) -> bool:
    """서울 시각 `now` 가 `start`~`until`("HH:MM") 안인가. 자정을 넘는 시간대(22:00~02:00)도 받는다."""
    from datetime import time as clock

    begin, end = clock.fromisoformat(start), clock.fromisoformat(until)
    at = now.time()
    return begin <= at < end if begin <= end else (at >= begin or at < end)


def _run_team_job(tenant_id: str, job, *, forced: bool = False, now=None) -> dict[str, object]:
    """팀 정기 작업 한 회차 — 시간대(`guardrails travel.team_jobs.windows.<job.window>`) 밖이면 부르지 않는다."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.core.settings import get_guardrails

    now = now or datetime.now(ZoneInfo("Asia/Seoul"))
    if not forced:
        window = get_guardrails().get(f"travel.team_jobs.windows.{job.window}")
        if not isinstance(window, dict) or not window.get("start") or not window.get("until"):
            raise ValueError(f"team job '{job.name}' window '{job.window}' is not configured")   # 모르는 시간대에 돌지 않는다
        if not _in_window(now, str(window["start"]), str(window["until"])):
            return {"outside_window": 1}
    return dict(job.tick(tenant_id, now))


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
    # 원본 정리를 먼저 끝낸다. 합성본 정리 실패가 원본 파기를 막지 않는다.
    out["retention"] = _run_retention(tenant_id, forced=False)
    from app.domains.travel_ops.components.customer.service_improvement import prune_expired
    with get_connection() as conn:
        out["synthetic_batches_purged"] = prune_expired(conn, tenant_id)
    return out


def _run_trip_places(tenant_id: str) -> dict[str, object]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.core.settings import get_guardrails
    from app.domains.travel_ops.components.itinerary.trip_places import scrub_ended

    with get_connection() as conn:
        return scrub_ended(conn, tenant_id=tenant_id, now=datetime.now(ZoneInfo("Asia/Seoul")),
                           retention_hours=float(get_guardrails().get("travel.trip_place_retention_hours")))


@_in_round
@_team_job
def _run_trip_dawn(tenant_id: str) -> dict[str, object]:
    table = current_bindings()
    if table is not None:
        table.registry.require_runnable("dining")
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
    from app import composition

    # ★무료 한도 보호 — DB 예산(027)을 **반드시** 건다. 프로세스 안 제한기는 매분 새로 차서 못 지킨다
    budget = CallBudget(connection_factory=get_connection, caps=google_caps())
    source = (GooglePlaces(api_key=key, budget=budget, limiter=build_travel_sources(settings).limiter,
                           match_radius_m=float(get_guardrails().get("travel.dawn_check.match_radius_m")))
              if key else None)
    outcome = DawnCheck(store=TripStore(tenant_id), connection_factory=get_connection,
                        clock=lambda: datetime.now(ZoneInfo("Asia/Seoul")), source=source,
                        place_status=composition.build_place_status(source)).tick()
    return outcome.counts()


@_in_round
@_team_job
def _run_trip_reminders(tenant_id: str) -> dict[str, int]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore
    from app.domains.travel_ops.entry.trip_api import plan_url
    from app.domains.travel_ops.components.watch.trip_reminders import TripReminders

    from app.composition import build_dining_trial_live, build_mobility_departure_observer
    settings = get_settings()
    sources = build_travel_sources(settings)
    # `[2026-10-19]` 다음 식당의 캐치테이블 시험 값을 안내에 참고 한 줄로 — 관리 콘솔 스위치(기본 꺼짐)가 켜졌을 때만
    reminders = TripReminders(store=TripStore(tenant_id), connection_factory=get_connection,
                              clock=lambda: datetime.now(ZoneInfo("Asia/Seoul")),
                              route_events=sources.route_events,
                              departure_observer=build_mobility_departure_observer(settings, sources),
                              link=lambda trip_id: plan_url(tenant_id, trip_id),
                              trial_live=build_dining_trial_live(tenant_id))
    outcome = reminders.tick()
    return {"trips": outcome.trips, "sent": len(outcome.sent), "already": outcome.already,
            "held": len(outcome.held), "fatal": len(outcome.fatal), "no_route": outcome.no_route,
            "stale": len(outcome.stale)}


def _watch_if_due(tenant_id: str, *, forced: bool, composition_failed=False) -> dict[str, int]:
    """감시(`trip_cases`)를 주기 문 뒤에서 돌린다. 문이 닫혀 있으면 `{"skipped_until_due": 1}` — 아무것도 안 부른다(외부 소스 포함).

    ☆왜: 이 일꾼은 1분마다 도는데 감시는 3분 주기다(`reliability.watch_interval_seconds`). 일꾼 전체를 3분으로 바꾸면 일정 출발 안내와 멈춘 Case 되잡기가
      늦어져서 감시만 막는다. 일꾼은 회차마다 새 프로세스라 마지막 실행 시각은 DB 에 둔다(`job_gates`, 마이그레이션 041).
    """
    from app.application.job_gate import WATCH_GATE, claim, interval_seconds
    from app.core.settings import get_guardrails
    from app.domains.travel_ops.components.watch.monitoring import execute

    interval, min_seconds = interval_seconds(get_guardrails())
    if not forced:
        with get_connection() as conn, conn.transaction():
            if not claim(conn, tenant_id=tenant_id, gate=WATCH_GATE, min_seconds=min_seconds):
                return {"skipped_until_due": 1}
    def work():
        if not composition_failed:
            return _run_trip_watch_cases(tenant_id)
        # 조립이 실패해도 재난 점검은 같은 주기 문 안에서 수행한다.
        counts = {"composition_unavailable": 1, "skipped": 1, "fatal": 1}
        try:
            counts.update({f"safety_{key}": value for key, value in _run_trip_safety(tenant_id).items()})
        except Exception as exc:
            logger.error("sweeper_job_failed job=trip_safety error_type=%s", type(exc).__name__)
            counts["safety_errored"] = 1
        return counts
    return execute(tenant_id, forced=forced, interval=interval, work=work, connection_factory=get_connection)


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
    outcome = sweep.tick()
    from app.domains.travel_ops.components.watch.monitoring import outcomes
    outcomes('safety_action', outcome)
    return outcome.counts()


@_in_round
@_team_job
def _run_trip_watch_cases(tenant_id: str) -> dict[str, int]:
    import asyncio
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.infrastructure.db import repository
    from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
    from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore
    from app.domains.travel_ops.components.watch.trip_watch_cases import TripWatchCaseOpener
    from app import composition

    # ★`[2026-10-06 사용자 결정]` 재난 정지 점검은 감시 **앞에** 같은 주기로 돈다 — 정지가 먼저 걸려야 같은 회차의 감시가 그 여행을 건너뛴다(`TripStore.due`).
    #   실패해도 감시는 돈다(정지 점검의 예외가 일정 감시를 막지 않는다 — 실패는 세고 로그에 남긴다). 결과는 `safety_*` 칸으로 감시 결과에 합친다
    try:
        safety = {f"safety_{key}": value for key, value in _run_trip_safety(tenant_id).items()}
    except Exception:                                    # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception("safety sweep failed")
        safety = {"safety_errored": 1}
    sources = build_travel_sources(get_settings())
    controller = _round_controller.get()

    def run_case(**kwargs):
        # ★Controller 의 run_case 는 coroutine 이다 — sweeper 는 동기 루프라 여기서 돌린다.
        return asyncio.run(controller.run_case(**kwargs))

    opener = TripWatchCaseOpener(
        store=TripStore(tenant_id), check=DisruptionCheck(sources).check,
        connection_factory=get_connection, clock=lambda: datetime.now(ZoneInfo("Asia/Seoul")),
        repository=repository, run_case=run_case, route_events=sources.route_events,
        diagnostic_recorder=composition.build_operations_recorder(),
        place_status=composition.build_place_status(),
        departure_observer=composition.build_mobility_departure_observer(get_settings(), sources))
    outcome = opener.tick()
    from app.domains.travel_ops.components.watch.monitoring import outcomes
    outcomes('schedule_action', outcome)
    escalated = sum(1 for run in outcome.ran if run.get("status") == "escalated")
    return {**safety, "checked": outcome.checked, "opened": len(outcome.opened), "existing": len(outcome.existing),
            "ran": len(outcome.ran), "escalated": escalated, "fatal": len(outcome.fatal),
            "unhandled": len(outcome.unhandled), "pinned": len(outcome.pinned),
            "unchecked": len(outcome.unchecked), "team_unavailable": len(getattr(outcome, "unavailable", []))}


@_in_round
@_team_job
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
            "unchecked": len(outcome.unchecked), "rechecked": len(outcome.rechecked),
            "team_unavailable": len(getattr(outcome, "unavailable", []))}


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
            print(f"★{name} sweeper: fatal={fatal} — 필수 조립·계산 또는 작업이 실패했다. "
                  "작업별 운영 로그를 확인해야 한다", file=sys.stderr, flush=True)
        errored = int(counts.get("errored", 0))
        if errored:
            total += errored
            print(f"★{name} sweeper: errored={errored} · scanned={counts.get('scanned')} "
                  f"— 아무것도 기록하지 못했다. 다음 회차에 또 걸린다",
                  file=sys.stderr, flush=True)
    return total


def _round_result(tenant_id, only):
    try:
        return _run_once(tenant_id, only)
    except Exception as exc:
        logger.error("sweeper_round_failed error_type=%s", type(exc).__name__)
        return {"round": {"errored": 1}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", default=True)
    parser.add_argument("--interval", type=int, default=None,
                        help="N 초마다 반복한다. 주면 --once 를 덮는다")
    fixed = ("classifying", "routing", "trip", "trip_cases", "trip_safety", "trip_dawn", "place_facts", "catalog_hours",
             "trip_reminders", "trip_places", "web_guard", "retention")

    def job_name(value: str) -> str:
        # `team:<이름>` — 팀이 끼운 정기 작업 하나(시간대를 보지 않고 지금 부른다)
        if value in fixed or (value.startswith("team:") and len(value) > len("team:")):
            return value
        raise argparse.ArgumentTypeError(f"{value!r} 는 {', '.join(fixed)} 또는 team:<이름> 중 하나여야 한다")

    parser.add_argument("--only", type=job_name, default=None)
    args = parser.parse_args()

    tenant_id = get_settings().tenant_id
    if args.interval is None:
        result = _round_result(tenant_id, args.only)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        # ★한 번 돌고 끝나는 모드는 exit code 가 유일한 신호다. cron 이 이걸 본다.
        return 1 if _report_errors(result) else 0

    # ★상주 모드에서도 한 회차의 결과를 그때그때 낸다. 다 끝나고 모아 내면
    #   중간에 죽었을 때 아무 기록도 안 남는다.
    while True:
        result = _round_result(tenant_id, args.only)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        # ★여기서는 **끝내지 않는다.** 상주 sweeper 가 첫 실패에 멈추면 되잡기
        #   자체가 멈춘다 — 멈춘 Case 를 되잡는 장치가 멈추는 것이 더 나쁘다.
        _report_errors(result)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

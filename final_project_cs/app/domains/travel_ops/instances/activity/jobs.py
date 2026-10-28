# -*- coding: utf-8 -*-
"""활동 팀 **정기 작업** — 조립이 이 파일의 `JOBS` 를 찾아 등록하고(`team_hooks/scheduled_jobs`), 작업 실행기가 새벽 창에서 1분마다 부른다.

    activity_live_status   앞으로 72시간 안에 시작하는 활동 장소의 임시휴무 · 폐업을 웹 공지로 한 번 확인해 저장한다
                           (전에는 `scripts/activity/check_live_status.py` 를 손으로 돌려야 했다 — 활동 → 코어 전달 사항 10-13 2번)

★일일 정기점검 규칙(`watch/daily_check.py`, 2026-10-14 사용자 지시)을 따른다 — 03:00 시작 · 03:30 까지 끝나게 한 번에 하는 양을 맞추고 ·
  결과에 `remaining`(아직 확인하지 않은 곳의 수)을 싣는다. 실행기는 03:30 뒤 첫 회차에 `remaining > 0` 이면 「안 끝남」으로 보고한다.
  남은 건수는 팀에게 묻지 않고 **대상 목록에서 직접 센다**(최근 6시간 안에 본 곳은 뺀다 — `live_batch.pending`).
★연결 · 판정 LLM · 웹 예산은 조립이 `configure` 로 꽂는다 — 팀 폴더는 인프라를 직접 열지 않는다(DoD-22, `team.live_lookup` 과 같은 방식).
  꽂히지 않았으면 `not_wired` 를 싣는다(정기점검 판정에서는 「모름」으로 센다 — 조용히 「끝남」이 되지 않는다).
★꺼져 있으면(관리 콘솔 스위치 꺼짐 — 기본 · 판정 종류 `live_status` 가 `rule` · 판정 LLM 없음 — 전역 판정 모드 `rule` 이거나 OpenAI 키 없음) 아무것도 부르지 않고
  `disabled` 를 싣는다 — 정기점검 판정에서 빠진다(안 끝난 것이 아니다).
    activity_read_hours    관광공사 운영시간 원문을 요일표로 미리 편다 — **규칙 단계만**(모델을 부르지 않는다). 아직 안 읽은 곳만 한다
    activity_decide_indoor 활동 장소 실내외를 관광공사 분류로 한 번 정해 저장한다 — **분류 단계만**(모델을 부르지 않는다). 이미 줄이 있는 곳은 건너뛴다
    activity_refresh_places 관광공사 원문이 바뀐 장소만 운영시간 · 휴무를 다시 받는다 — 하루 한 번 · **기본 꺼짐**(`travel.activity_batch.refresh_places_enabled`)
    (세 작업은 전에 `scripts/activity/{read_hours,decide_indoor,refresh_places}.py` 를 손으로 돌렸다 — 활동 → 코어 전달 사항 6번 · ST4F-538.
     한 회차의 일은 그 스크립트의 함수(`run` · `refresh`)를 그대로 부른다 — 로직을 복사하지 않는다)

★웹 예산(하루 50회)이 다 차면 `skipped` 를 싣는다 — 오늘 몫을 다 쓴 것이라 「안 끝남」으로 보고하지 않는다. 남은 곳은 `remaining` 에 그대로 남는다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from app.domains.travel_ops.components.team_hooks.scheduled_jobs import TeamJob

#: 한 회차(1분)에 확인하는 곳 — 웹 검색 한 번이 15~40초 걸린다(10-06 측정 p50 15.7초 · p95 40.7초).
#: 03:30 까지 끝나게 늘리되(`daily_check.paced`) 많아야 `PER_TICK_CAP` — 한 회차가 몇 분씩 늘어지지 않게. ★우리가 고른 값
PER_TICK_BASE = 2
PER_TICK_CAP = 4
#: 이 시간 안에 확인한 곳은 다시 보지 않는다(스크립트 기본값과 같다)
RECHECK_HOURS = 6.0

_wired: dict[str, Any] = {}


def configure(*, connection_factory: Callable[[], Any], judge_llm: Any | None,
              budget: Callable[[str], bool], claim: Callable[..., bool]) -> None:
    """조립이 부른다 — 연결 · 판정 LLM(없으면 `None`) · 웹 예산(종류 → 불러도 되나) · 주기 문(`job_gate.claim` — 하루 한 번 작업이 쓴다)."""
    _wired.clear()
    _wired.update(connection_factory=connection_factory, judge_llm=judge_llm, budget=budget, claim=claim)


def _script(name: str):
    """`scripts/activity/<name>.py` — 한 회차의 일은 손으로 돌리던 스크립트의 함수를 그대로 쓴다(복사하지 않는다).
    실행기(`python -m scripts.run_sweepers`)는 프로젝트 루트에서 돌아 `scripts` 를 import 할 수 있다(이미지에도 들어 있다 — `deploy/Dockerfile.api`)."""
    import importlib

    return importlib.import_module(f"scripts.activity.{name}")


def read_hours_tick(tenant_id: str, now: datetime, *, wired: dict[str, Any] | None = None, runner: Callable[..., dict] | None = None
                    ) -> dict[str, int]:
    """한 회차 — 규칙 단계(`read_hours.run(conn)` 의 모델 없는 길). DB 만 읽고 쓴다.

    아직 안 읽은 곳(`hours_read IS NULL`)은 이 회차에 전부 처리되므로 남은 일은 없다(`remaining: 0`). 모델 단계(못 편 곳을 LLM 으로 펴기)는 유료라 넣지 않았다."""
    wired = _wired if wired is None else wired
    if not wired:
        return {"not_wired": 1}
    runner = runner or _script("read_hours").run
    with wired["connection_factory"]() as conn:
        out = {key: int(value) for key, value in runner(conn).items()}
    out["remaining"] = 0
    return out


def decide_indoor_tick(tenant_id: str, now: datetime, *, wired: dict[str, Any] | None = None, runner: Callable[..., dict] | None = None
                       ) -> dict[str, int]:
    """한 회차 — 분류 단계(`decide_indoor.run(conn)` 의 모델 없는 길). DB 만 읽고 쓴다.

    분류로 정해지지 않은 곳(`unknown`)은 모델(`--model`)이 있어야 정해진다 — 정기 작업에서는 모델을 부르지 않으므로 그대로 두고 센다.
    그것은 밀린 일이 아니라 이 단계의 범위 밖이다(`remaining: 0`)."""
    wired = _wired if wired is None else wired
    if not wired:
        return {"not_wired": 1}
    runner = runner or _script("decide_indoor").run
    with wired["connection_factory"]() as conn:
        out = {key: int(value) for key, value in runner(conn).items()}
    out["remaining"] = 0
    return out


#: 장소 원문 다시 받기를 한 번 하고 나면 이 시간 동안 다시 하지 않는다 — 하루 한 번(새벽 창 8시간 안에서 두 번 돌지 않게 하되 매일은 돈다)
REFRESH_EVERY_SECONDS = 20 * 3600
REFRESH_GATE = "activity_refresh_places"


def refresh_places_tick(tenant_id: str, now: datetime, *, wired: dict[str, Any] | None = None,
                        script: Any | None = None, fetch_listing: Callable[[str, str], list] | None = None,
                        fetch_intro: Callable[[str, str], Any] | None = None) -> dict[str, int]:
    """한 회차 — 하루 한 번. 꺼져 있으면(기본) 아무것도 부르지 않는다. `script` · `fetch_*` 는 시험이 바꿔 끼우는 자리다.

    ★시도를 시작할 때 시각을 적는다(`job_gate.claim`) — 중간에 터져도 다음 시도는 하루 뒤다(터진 일을 1분마다 되풀이해 관광공사를 때리지 않게).
    ★상세 호출이 상한(`refresh_places_max_calls`)에 걸려 못 다시 받은 곳은 `over_limit` 로 싣는다. 다음 날 원문이 여전히 다르면 다시 대상이 되므로
      밀린 일(`remaining`)로 세지 않는다 — 정기점검 「안 끝남」에 들지 않는다."""
    from app.core.settings import get_guardrails, get_settings

    guard = get_guardrails()
    if guard.get("travel.activity_batch.refresh_places_enabled") is not True:
        return {"disabled": 1}
    wired = _wired if wired is None else wired
    if not wired:
        return {"not_wired": 1}
    # ★ST4F-574 — 다른 관광공사 호출과 같은 규칙(서비스별 키 > 공통 키 `ACOP_DATA_GO_KR_KEY`)으로 고른다.
    #   전에는 `tour_api_key` 만 읽어 공통 키만 있는 서버에서 켜면 「키 없음」으로 터졌다.
    settings = get_settings()
    override = getattr(settings, "tour_api_key", "") or ""
    resolve = getattr(settings, "public_data_key", None)
    key = resolve(override) if callable(resolve) else override
    if not key:
        raise RuntimeError("travel.activity_batch.refresh_places_enabled 가 켜져 있는데 관광공사 키(ACOP_TOUR_API_KEY 또는 공통 ACOP_DATA_GO_KR_KEY)가 없다")
    with wired["connection_factory"]() as conn:
        with conn.transaction():
            if not wired["claim"](conn, tenant_id=tenant_id, gate=REFRESH_GATE, min_seconds=REFRESH_EVERY_SECONDS):
                return {"skipped_until_due": 1}
    script = script or _script("refresh_places")
    if fetch_listing is None or fetch_intro is None:
        from scripts.fetch_tourapi_list import fetch_category

        from app.domains.travel_ops.instances.activity.data_processing.tourapi_client import call_tourapi

        fetch_listing = fetch_listing or (lambda api_key, cat: fetch_category(api_key, cat)[1])
        fetch_intro = fetch_intro or (lambda cid, type_id: call_tourapi("detailIntro2", {"contentId": cid, "contentTypeId": type_id}, key))
    listed: list = []
    for category in script.CATEGORIES:
        listed.extend(fetch_listing(key, category))
    max_calls = int(guard.get("travel.activity_batch.refresh_places_max_calls"))
    with wired["connection_factory"]() as conn:
        out = {k: int(v) for k, v in script.refresh(conn, listed, fetch_intro, max_calls=max_calls).items()}
        out.update({f"listing_{k}": int(v) for k, v in
                    script.mark_listing(conn, {str(r.get("contentid")) for r in listed}).items()})
    out["listed"] = len(listed)
    out["remaining"] = 0
    return out


def live_status_tick(tenant_id: str, now: datetime, *, parts=None, wired: dict[str, Any] | None = None) -> dict[str, int]:
    """한 회차. `parts` · `wired` 는 시험이 부품(대상 · 판정 · 예산 · 저장)과 연결을 바꿔 끼우는 자리다."""
    from app.core.settings import get_guardrails
    from app.domains.travel_ops.components.watch import daily_check
    from app.domains.travel_ops.instances.activity import live_batch
    from app.domains.travel_ops.instances.activity.judge.modes import kind_mode

    parts = parts or live_batch
    wired = _wired if wired is None else wired
    if kind_mode("live_status") == "rule":
        return {"disabled": 1}
    if not _console_on(tenant_id):
        return {"disabled": 1, "console_off": 1}               # 관리 콘솔 「운영 설정」 스위치가 꺼짐(기본)
    if not wired:
        return {"not_wired": 1}
    judge = parts.judge_runner(wired["judge_llm"])
    if judge is None:
        return {"disabled": 1}
    guard = get_guardrails()
    within = float(guard.get("travel.activity_judge.live_status_within_hours"))
    connect = wired["connection_factory"]

    with connect() as conn:
        targets = parts.find_targets(conn, now, within, tenant_id=tenant_id)
    read_row = parts.row_reader(connect)
    left = parts.pending(targets, read_row=read_row, now=now, recheck_hours=RECHECK_HOURS)
    if left == 0:
        return {"targets": len(targets), "checked": 0, "remaining": 0}
    win = daily_check.from_guardrails(now, guard)
    limit = daily_check.paced(left, base=PER_TICK_BASE, cap=PER_TICK_CAP, win=win)
    result = parts.check_targets(targets, read_row=read_row, judge=judge, budget=wired["budget"],
                                 record=parts.recorder(connect), now=now, recheck_hours=RECHECK_HOURS, limit=limit)
    out = {key: int(value) for key, value in result.items()}
    out["remaining"] = max(0, left - result["checked"])          # 실패한 곳은 저장되지 않았으니 남은 일이다
    if result["budget_stop"]:
        out["skipped"] = 1                                       # 오늘 웹 예산을 다 썼다 — 늦은 것이 아니다
    return out


def _console_on(tenant_id: str) -> bool:
    """관리 콘솔 스위치(`travel.activity_judge.live_status_batch_enabled`, 기본 꺼짐) — 유료 웹 검색이라 운영자가 켤 때만 돈다."""
    from app.domains.travel_ops.components.settings_hook import activity_live_check_enabled

    return activity_live_check_enabled(tenant_id)


#: 새벽 창에서 돈다. ★순서가 뜻이 있다 — 원문을 다시 받고(`refresh_places`) → 요일표를 펴고(`read_hours`) → 실내외를 정한다(`decide_indoor`).
#  (실행기는 이름 순으로 부르므로 순서가 아니라 서로 독립적으로 안전하다 — 원문이 바뀐 곳은 요일표가 비워져 다음 회차 `read_hours` 가 다시 편다)
JOBS = [TeamJob(name="activity_live_status", tick=live_status_tick, window="dawn"),
        TeamJob(name="activity_refresh_places", tick=refresh_places_tick, window="dawn"),
        TeamJob(name="activity_read_hours", tick=read_hours_tick, window="dawn"),
        TeamJob(name="activity_decide_indoor", tick=decide_indoor_tick, window="dawn")]

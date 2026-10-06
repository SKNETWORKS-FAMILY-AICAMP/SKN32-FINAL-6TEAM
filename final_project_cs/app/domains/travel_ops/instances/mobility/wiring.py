# -*- coding: utf-8 -*-
"""이동 계산기(engine/) 연결 — 서버 기동 때 켜고, 이동 에이전트가 구조화된 구간 입력을 판정할 때 쓴다.

☆`[2026-09-29 이동 계산기 문제목록 #34·#35·#31·#24]`
  #34 에이전트 본체가 계산기를 한 번도 부르지 않았다 → team.py 가 `current_state.mobility` 입력이 오면 여기로 판정한다.
  #35 구간 확인·막차 판정(check_route·exception)은 조회 도구가 비어 늘 「모름」이었다 → 계산기 판정으로 답한다.
  #31 첫 고객 요청이 자료 적재(약 33초)를 기다렸다 → 기동 때 적재한다.
  #24 자료가 없으면 첫 호출에서 멈췄다 → 기동 때 확인하고, 없거나 판 명세와 다르면 **서버를 띄우지 않는다**(결정 15).

켜고 끄기는 설정 `mobility_data_dir` 하나가 정한다. 비우면 꺼짐 — 계산기를 부르지 않고, 구조화 입력이 와도
「계산기가 꺼져 있다」는 오류로 올린다(지어낸 답을 내지 않는다). ★꺼짐에서 명령줄 관례(.env)로 새지 않는다(paths.disable).

★ 계약 타입(TeamResult)은 여기서 만들지 않는다 — 계산기 어댑터가 준 dict 를 team.py 가 계약으로 옮긴다.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from .engine import datacheck, paths
from .engine.timeutil import CalendarOutOfRange
from .engine import guardrails as engine_guardrails
from .engine import runtime as engine_runtime

CS_ROOT = Path(__file__).resolve().parents[5]          # mobility → instances → travel_ops → domains → app → final_project_cs (2026-10-06 D-CS-013 로 한 칸 깊어짐)

_STATE: dict[str, Any] = {"mode": "unconfigured", "kw": None, "datacheck": None}


#: ★서버 콘솔이 실제로 보여 주는 로거를 쓴다 — 앱 로거(`__name__`)는 INFO 가 콘솔에 안 나와 「적재가 됐는지」 운영에서 보이지 않았다
# ★이 로거로 찍는 글에는 「—」(U+2014)를 쓰지 않는다 — 윈도 cp949 콘솔이 못 옮겨 글자 그대로 깨져 나온다(화면 세션이 실콘솔에서 확인)
_SERVER_LOG = logging.getLogger("uvicorn.error")
_ANNOUNCED: set[tuple] = set()


def _announce(key: tuple, message: str, *args: Any) -> None:
    """같은 상태는 한 번만 — 조립(build_registry)이 여러 번 불려도 줄이 쌓이지 않게."""
    if key not in _ANNOUNCED:
        _ANNOUNCED.add(key)
        _SERVER_LOG.info(message, *args)


class MobilityUnavailable(RuntimeError):
    """이동 자료가 없거나 판 명세와 다르다 — 켜라고 했는데 켤 수 없다. 기동을 멈춘다(결정 15)."""


def configure(*, data_dir: str | None, gh_url: str = "", seoul_key: str = "",
              guardrails_path: str | Path | None = None, preload: bool = True,
              verify_hash: bool = True, local_router: bool = True, warm_router: bool = False,
              bike_gate: Any = None) -> dict[str, Any]:
    """계산기를 켜거나 끈다. 켤 때는 자료를 확인하고(없거나 다르면 MobilityUnavailable) 적재까지 한다."""
    if not data_dir:
        paths.disable()
        _STATE.update(mode="disabled", kw=None, datacheck=None)
        _announce(("disabled",), "이동 계산기 꺼짐 - 설정 mobility_data_dir 가 비어 있다(일정 짜기·재경로는 직선 어림값)")
        return {"mode": "disabled"}
    paths.configure(data_dir)
    if guardrails_path:
        engine_guardrails.use(guardrails_path)
    dc = datacheck.check(verify_hash=verify_hash)
    if not dc["ok"]:
        _STATE.update(mode="broken", kw=None, datacheck=dc)
        raise MobilityUnavailable(f"이동 자료 확인 실패 - 서버를 띄우지 않는다(결정 15): 없음 {dc['missing']} · "
                                  f"다름 {dc['mismatched']} · 자료 폴더 {dc['data_dir']}")
    kw = {"quiet": True, "data_dir": data_dir, "gh_url": gh_url or "", "seoul_key": seoul_key or "",
          "guardrails_path": str(guardrails_path) if guardrails_path else None, "local_router": bool(local_router),
          "bike_gate": bike_gate}
    _STATE.update(mode="enabled", kw=kw, datacheck=dc)
    if preload:
        started = time.monotonic()
        rt = engine_runtime.get_verifier(**kw)
        _announce(("enabled", str(paths.DATA_DIR)),
                  "이동 계산기 켜짐 - 자료 %s(출처 %s) · 명세 %s · 시간표 판 %s%s · 적재 %.1f초",
                  paths.DATA_DIR, paths.SOURCE, Path(dc["manifest"]).name if dc.get("manifest") else "없음",
                  getattr(rt, "timetable_built_at", "?"), " · ★오래됨" if getattr(rt, "timetable_stale", False) else "",
                  time.monotonic() - started)
        if warm_router:
            _warm_local_router(rt)
    return {"mode": "enabled", "datacheck": dc}


def _warm_local_router(rt) -> None:
    """☆`[2026-10-04]` 파이썬 로컬 라우터(도로 그래프)를 백그라운드로 미리 올린다 - 서버를 띄운 직후 첫 택시·도보 물음이 10초 멈추지 않게.

    스레드는 기동을 막지 않는다(daemon). 올리다 실패해도 서버는 산다 - 라우터는 첫 호출 때 다시 올려 보고, 안 되면 RouterDown 으로 근거없음이다."""
    router = getattr(getattr(getattr(rt, "_v", None), "bike_router", None), "router", None)
    if router is None or not hasattr(router, "warm") or getattr(router, "_warm_started", False):
        return                                                   # 라우터는 프로세스당 하나를 나눠 쓰므로 스레드도 한 번만
    router._warm_started = True

    def run():
        started = time.monotonic()
        try:
            router.warm()
            _announce(("router_warm", id(router)), "이동 계산기 길찾기(로컬 도로 그래프) 준비됨 - %.1f초", time.monotonic() - started)
        except Exception as ex:                                  # noqa: BLE001 - 서버를 죽이지 않는다(원인은 로그에)
            _SERVER_LOG.warning("이동 계산기 길찾기 미리 올리기 실패(첫 호출 때 다시 시도): %s", type(ex).__name__)

    import threading
    threading.Thread(target=run, name="mobility-router-warm", daemon=True).start()


def configure_from_settings(settings: Any, *, preload: bool = True, bike_gate: Any = None) -> dict[str, Any]:
    """서버 설정(app.core.settings.Settings)으로 켠다. 설정 객체를 받기만 한다 — 여기서 설정을 읽지 않는다."""
    # 칸이 없는 설정(시험이 넣는 일부 칸짜리 대역)은 이동 칸이 빈 것과 같다 — 꺼짐
    gp = Path(getattr(settings, "guardrails_path", "config/guardrails.yaml"))
    if not gp.is_absolute():
        gp = CS_ROOT / gp
    seoul_key = getattr(settings, "seoul_openapi_key", "")
    if seoul_key and bike_gate is None:
        # ★`[2026-10-05]` 따릉이 실시간 조회는 `TravelSource` 를 거치지 않아 호출 한도 문이 필요하다. 문은 조립(`composition.py`)이 만들어 넘긴다
        #   (Team 코드는 infrastructure 를 직접 import 하지 않는다 — 구조 시험). 문 없이는 **부르지 않는다** — 거치 대수는 근거없음이고 서비스는 계속된다.
        _SERVER_LOG.warning("따릉이 실시간 호출 한도 문이 없어 실시간 조회를 끈다(조립이 bike_gate 를 넘겨야 켜진다)")
        seoul_key = ""
    return configure(data_dir=getattr(settings, "mobility_data_dir", ""),
                     gh_url=getattr(settings, "mobility_gh_url", ""),
                     seoul_key=seoul_key, bike_gate=bike_gate, guardrails_path=gp, preload=preload,
                     local_router=getattr(settings, "mobility_local_router", True),
                     warm_router=getattr(settings, "mobility_local_router", True))


def mode() -> str:
    return _STATE["mode"]


#: 설문 우선순위 「이동」 세부 코드(화면 PREFERENCES_CONTRACT) → 계산기 수단. 택시는 `[2026-10-04 #47]` 부터 넣는다. 렌트카(car)는 아직 못 다룬다
SURVEY_MODES = {"public": ("subway", "bus"), "walk": ("walk",), "taxi": ("taxi",)}


def modes_from_survey(constraints: dict[str, Any] | None) -> list[str] | None:
    """☆`[2026-09-29 문제목록 #46]` 설문의 이동 선호를 계산기 수단으로. 앞 판은 받아 두기만 했다.

    화면은 `preferred_mobility[]` 를 보내지 않고 `priority_details.mobility`(public·walk·car·taxi)로 보낸다 — 둘 다 본다.
    옮길 수 있는 것이 하나도 없으면(렌트카만) None — 계산기 기본 수단(지하철·버스·도보). 도보는 늘 넣는다
    (역·정류장까지 걷기는 어느 수단에도 들어간다)."""
    survey = (constraints or {}).get("survey") or {}
    codes = list(((survey.get("priority_details") or {}).get("mobility") or []))
    ko = {"대중교통": "public", "도보": "walk"}
    codes += [ko.get(x, x) for x in (survey.get("preferred_mobility") or [])]
    modes = {m for c in codes for m in SURVEY_MODES.get(c, ())}
    return sorted(modes | {"walk"}) if modes else None


def engine_line(name: str) -> str:
    """uses 노선명 → 계산기(시간표) 노선명. '2호선' → '02호선' · '경의중앙선' → '경의선'(options.line_name 의 반대)."""
    from .engine.options import LINE_OFFICIAL
    back = {v: k for k, v in LINE_OFFICIAL.items()}
    if name in back:
        return back[name]
    if name.endswith("호선") and name[:-2].isdigit():
        return f"{int(name[:-2]):02d}호선"
    return name


def disruptions_from_events(events: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """☆`[2026-09-29 문제목록 #39]` 우리 경로 사건(대상 표기 → effect) → 계산기 사고 조건(kind). (옮긴 것, 못 옮긴 대상).

    뜻이 같은 것만 옮긴다 — 이름만 바꾸지 않는다.
      N호선:역 + skip_station  → station_skip{line, station}   (그 역에 안 선다 — 양쪽 같은 뜻)
      N호선:*  + line_closed   → line_closed{line}
      버스:노선 + 운행 중단      → route_closed{route}
      도로:…   + road_control  → 못 옮김 — 우리 쪽은 「느려진다」, 계산기에는 대중교통이 지나는 도로 정보가 없다
    못 옮긴 대상은 부르는 쪽이 드러낸다(조용히 버리지 않는다).
    """
    out, unmapped = [], []
    for target, ev in (events or {}).items():
        head, _, rest = str(target).partition(":")
        effect = (ev or {}).get("effect")
        meta = {"note": (ev or {}).get("summary"), "source": (ev or {}).get("source_id") or "trip_watch",
                "grade": (ev or {}).get("grade", "추정"), "observed_at": (ev or {}).get("observed_at")}
        if head == "버스" and effect in ("route_closed", "line_closed", "skip_station"):
            out.append({"kind": "route_closed", "route": rest, **meta})
        elif head not in ("버스", "도로") and effect == "skip_station" and rest:
            out.append({"kind": "station_skip", "line": engine_line(head), "station": rest, **meta})
        elif head not in ("버스", "도로") and effect == "line_closed":
            out.append({"kind": "line_closed", "line": engine_line(head), **meta})
        else:
            unmapped.append(str(target))
    return out, unmapped


def leg_planner(party_size: int | None, constraints: dict[str, Any] | None, *, disruptions=None):
    """일정 짜기(planner.add_moves)가 부를 **구간 계산기**. 꺼져 있으면 None — 부르는 쪽이 직선 어림값으로 간다.

    돌려주는 함수 leg(a_place, b_place, arrive_dt, not_before_dt) → (결과 dict, None) 또는 (None, 이유 dict).
      결과: starts_at · ends_at(도착 목표 − 여유 기준 출발 · 도착) · eta_min · route(options·uses 포함) · left_out
      route 에 밀도 검사(density.py)가 읽는 칸을 채운다 — average_eta_min(계획 수단 소요) · p95_eta_min(최악 소요) ·
      distance_m(계획 수단 도보 거리). ☆`[2026-09-29 문제목록 #43]` 앞 판 계산기는 이 칸을 내지 않았다.
    """
    if _STATE["mode"] != "enabled":
        return None
    from .engine.plan import Planner, iso_of, party_of
    rt = engine_runtime.get_verifier(**_STATE["kw"])
    c = dict(constraints or {})
    planner = Planner(rt, stage="planning", modes=modes_from_survey(c))
    if disruptions:
        planner.disruptions = tuple(dict(d) for d in disruptions)     # #38 — 사고를 모든 판정 호출에 싣는다
    party = party_of(party_size, c)
    first_visit = c.get("first_visit", True)
    buffer = rt._v.rv("buffer", "by_stage", "planning")
    counter = {"n": 0}

    def leg(a_place, b_place, arrive_dt, not_before_dt=None):
        counter["n"] += 1
        planner.trace = []
        try:
            got, why = planner.leg(a_place, b_place, arrive_dt, party, first_visit,
                                   case_id=f"{a_place.get('key')}_to_{b_place.get('key')}_{counter['n']}",
                                   not_before_dt=not_before_dt)
        except CalendarOutOfRange as ex:
            # ☆`[2026-09-29 자료 폴더를 켜자 시험이 잡음]` 공휴일 표가 덮지 않는 해(2028~)의 여행이면 계산기는 평일·휴일을 짐작하지
            #   않고 멈춘다(#5). 그 오류를 위로 올리면 장소 교체·일정 짜기 전체가 터진다 — 「계산기가 못 채움」으로 돌려 부르는 쪽이
            #   종전 대체 소스(어림값)로 가게 한다. 이유는 남는다(조용히 삼키지 않는다)
            return None, {"code": "no_data", "reason": f"계산기가 그 날짜를 판정하지 못한다 — {ex}"}
        if got is None:
            return None, why
        route, start, end, sdate, left = got
        planned = next(o for o in route["options"] if o["id"] == route["planned"])
        tr = next((o for o in (planner.trace[-1]["options"] if planner.trace else []) if o["id"] == planned["id"]), {})
        spread = max(0, int((tr.get("margin_min") or buffer) - buffer))
        route = dict(route, average_eta_min=planned["eta_min"], p95_eta_min=planned["eta_min"] + spread,
                     **({"distance_m": planned["walk_m"]} if planned.get("walk_m") is not None else {}))
        from datetime import datetime
        return {"route": route, "starts_at": datetime.fromisoformat(iso_of(sdate, start)),
                "ends_at": datetime.fromisoformat(iso_of(sdate, end)), "eta_min": int(planned["eta_min"]),
                "left_out": left}, None
    return leg


def basis() -> dict[str, Any]:
    """판정기의 상태와 근거 판 — 읽기 입구(MCP 이동 판정)가 「어느 시간표로 판정했나」를 밝힌다. 꺼져 있으면 `mode` 만."""
    if _STATE["mode"] != "enabled":
        return {"mode": _STATE["mode"]}
    rt = engine_runtime.get_verifier(**_STATE["kw"])
    built = rt.timetable_built_at
    return {"mode": "enabled", "timetable_built_at": built.isoformat() if hasattr(built, "isoformat") else str(built),
            "rules_version": rt.rules_version, "timetable_stale": bool(rt.timetable_stale)}


def team_result(task: Any) -> dict[str, Any] | None:
    """구조화 입력(current_state.mobility)을 계산기로 판정해 TeamResult 모양 dict 를. 꺼져 있으면 None."""
    if _STATE["mode"] != "enabled":
        return None
    from .engine.adapter import MobilityAdapter
    rt = engine_runtime.get_verifier(**_STATE["kw"])
    adapter = MobilityAdapter(rt.verify_case, basis={"timetable_built_at": rt.timetable_built_at,
                                                     "rules_version": rt.rules_version})
    out = adapter.run(task)
    if rt.timetable_stale:                      # #32 — 오래된 시간표로 낸 판정이면 드러낸다
        out["warnings"] = list(out.get("warnings") or []) + ["MOB_W_TIMETABLE_STALE"]
    return out

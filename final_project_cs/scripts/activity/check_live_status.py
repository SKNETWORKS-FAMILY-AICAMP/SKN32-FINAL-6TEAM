"""앞으로 곧 시작하는 활동 장소의 **실시간 운영 상태(임시휴무 · 폐업)** 를 웹 공지로 한 번 확인해 저장한다 — `activity.ac_live_status`. `[2026-10-13]`

★왜. 관광공사 운영 정보는 「매주 화요일 휴무」 같은 정기 규칙이라 수요일 당일 사고(임시휴무 · 공사 · 폐업)를 담지 못한다.
  그렇다고 고객 요청마다 웹을 부르면 비용이 요청 수에 비례하고 응답이 느리다(p95 40.7초 · 429). 그래서 **장소 · 날짜당 한 번**
  이 배치가 확인해 저장하고, 고객 요청(`team._live_status_check`)은 저장된 값만 읽는다. 경복궁을 100명이 가도 한 번이다.

★대상. 지금부터 `travel.activity_judge.live_status_within_hours`(기본 72시간) 안에 시작하는 활동 일정 항목의 (장소, 날짜).
  이미 `--recheck-hours`(기본 6시간) 안에 확인한 줄은 건너뛴다. 모름(`unknown`)도 줄로 남겨 같은 곳을 계속 다시 부르지 않는다.
★예산. 호출마다 `activity_judge_web` 예산(`CallBudget` — DB)을 확인한다. 넘으면 거기서 멈추고 남은 곳을 보고한다.
★켜는 법. 전역 `ACOP_ACTIVITY_JUDGE_MODE` 가 `rule` 이면(기본) 판정 LLM 이 없어 아무것도 하지 않는다 — `shadow` 로 두고 돌린다.
  `kind_modes.live_status` 가 `rule` 이면 이 배치도 돌지 않는다. 저장 결과를 고객 답에 쓰는 것은 `llm` 일 때만이다(`shadow` 는 기록만).

사용법 (작업 시간 — 03:00~08:00 새벽 창 또는 코어의 15시 점검 뒤)
    python scripts/activity/check_live_status.py --dry-run    대상만 센다(웹을 부르지 않는다)
    python scripts/activity/check_live_status.py              확인해 저장
    python scripts/activity/check_live_status.py --limit 20   20곳만
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))                       # final_project_cs
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ★`[2026-10-14]` 대상 세기 · 확인 · 저장 부품은 팀 폴더(`instances/activity/live_batch.py`)로 옮겼다 — 새벽 정기 작업
#   (`instances/activity/jobs.py`)도 같은 부품을 쓴다. 이 스크립트는 손으로 돌리는 껍데기다(시험이 `check_targets` · `Target` 을 여기서 부른다).
from app.domains.travel_ops.instances.activity.live_batch import (  # noqa: E402
    Target, check_targets,  # noqa: F401 — Target 은 시험이 이 스크립트에서 부른다
    find_targets, judge_runner, recorder, row_reader)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="대상만 센다 — 웹을 부르지 않고 저장도 하지 않는다")
    parser.add_argument("--limit", type=int, default=None, help="이번에 확인할 최대 곳 수")
    parser.add_argument("--within-hours", type=float, default=None,
                        help="지금부터 N시간 안에 시작하는 일정(기본: guardrails travel.activity_judge.live_status_within_hours)")
    parser.add_argument("--recheck-hours", type=float, default=6.0, help="이 시간 안에 확인한 곳은 건너뛴다")
    args = parser.parse_args()

    from app.core.settings import get_guardrails
    from app.domains.travel_ops.instances.activity.judge.modes import kind_mode
    from app.infrastructure.db.session import get_connection

    if kind_mode("live_status") == "rule":
        raise SystemExit("kind_modes.live_status 가 rule 이다 — 실시간 운영 확인이 꺼져 있다")
    within = args.within_hours or float(get_guardrails().get("travel.activity_judge.live_status_within_hours"))
    now = datetime.now(timezone.utc)

    with get_connection() as conn:
        targets = find_targets(conn, now, within)
    print(f"앞으로 {within:g}시간 안에 시작하는 활동 (장소 · 날짜) {len(targets):,}곳")
    if args.dry_run:
        for t in targets[:20]:
            print(f"  {t.visit_date} {t.name} ({t.content_id})")
        return
    from app.composition import build_activity_judge_budget, build_activity_judge_llm

    judge = judge_runner(build_activity_judge_llm())
    if judge is None:
        raise SystemExit("판정 LLM 이 없다 — ACOP_ACTIVITY_JUDGE_MODE 를 shadow 로 두고 OpenAI 키를 확인한다")
    model = os.environ.get("ACOP_ACTIVITY_JUDGE_MODEL") or None

    result = check_targets(targets, read_row=row_reader(get_connection), judge=judge, budget=build_activity_judge_budget(),
                           record=recorder(get_connection, model), now=now, recheck_hours=args.recheck_hours, limit=args.limit)
    print(f"확인 {result['checked']:,}곳 (닫힘 {result['closed']:,} · 열림 {result['open']:,} · 모름 {result['unknown']:,})"
          f" · 최근에 확인해 건너뜀 {result['fresh']:,} · 실패 {result['failed']:,} · 남음 {result['left']:,}")
    if result["budget_stop"]:
        print("★웹 검색 예산이 다 찼다 — 남은 곳은 다음 실행에서 확인한다(travel.activity_judge.budget.web)")


if __name__ == "__main__":
    main()

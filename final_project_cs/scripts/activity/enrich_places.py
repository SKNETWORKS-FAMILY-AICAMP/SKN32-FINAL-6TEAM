"""곧 시작하는 활동 일정에 든 장소의 **빈 정보를 웹 검색으로 채운다** — `activity.ac_place_web_info`. `[2026-10-19]`

흐름(장소마다): 활동 원장에 있다 → **비어 있는 칸만** 웹 검색 · 없다 → 카카오로 **실존만** 확인 → 웹 검색(주소 · 운영시간 · 휴무 · 예약 …) → 주소를 브이월드로 좌표.
웹 값 · 좌표는 별도 표에 출처 · 인용 · 만료와 함께 저장한다. 고객 요청은 저장된 값만 읽는다(`ledger._merge_web`) — 응답 중에 웹을 부르지 않는다.

★대상: 지금부터 `--within-hours`(기본 168 = 7일, 우리가 고른 값) 안에 시작하는 활동 일정 항목의 장소 이름. 원장에 없는 장소도 포함한다.
★이미 채운 칸 · 「못 찾음」 표시(7일)가 만료 전이면 다시 검색하지 않는다 — 같은 장소는 한 번이다.
★예산: 웹 검색마다 `activity_judge_web` 예산(DB)을 확인한다. 넘으면 거기서 멈추고 남은 곳을 보고한다.
★켜는 법: 전역 `ACOP_ACTIVITY_JUDGE_MODE` 가 `rule` 이면(기본) 판정 LLM 이 없어 아무것도 하지 않는다 — `shadow` 로 두고 OpenAI 키를 확인한다.
★**프롬프트 `activity_judge.place_info` 가 등록돼 있어야 한다**(코어 `ALLOWED_PROMPT_KEYS` + `prompts/activity_judge/place_info.v1.md`). 안 돼 있으면 모든 곳이 `web_error` 로 센다.
★카카오는 「있다/없다」만 쓴다 — 응답(이름 · 주소 · 좌표)은 저장하지 않는다. 좌표는 브이월드(`vworld_api_key`)다.

사용법 (작업 시간 — 03:00~08:00 새벽 창 또는 코어의 15시 점검 뒤)
    python scripts/activity/enrich_places.py --dry-run     대상 이름만 센다(웹 · 카카오를 부르지 않는다)
    python scripts/activity/enrich_places.py --limit 5     5곳만 채워 본다
    python scripts/activity/enrich_places.py               전부
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
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="대상 이름만 센다 — 웹 · 카카오를 부르지 않고 저장도 하지 않는다")
    parser.add_argument("--limit", type=int, default=None, help="이번에 웹 검색을 부를 최대 곳 수")
    parser.add_argument("--within-hours", type=float, default=168.0, help="지금부터 N시간 안에 시작하는 일정(기본 168 — 우리가 고른 값)")
    args = parser.parse_args()

    from app.domains.travel_ops.instances.activity import enrich_batch
    from app.infrastructure.db.session import get_connection

    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        names = enrich_batch.find_names(conn, now, args.within_hours)
    print(f"앞으로 {args.within_hours:g}시간 안에 시작하는 활동 장소 이름 {len(names):,}곳")
    if args.dry_run:
        for c in names[:20]:
            print(f"  {c.starts_at:%m-%d %H:%M} {c.name} ({c.content_id or '원장 연결 없음'})")
        return

    from app.composition import build_activity_judge_budget, build_activity_judge_llm, build_kakao_local
    from app.domains.travel_ops.instances.activity import place_enrichment as pe
    from app.domains.travel_ops.instances.activity.geocode import VWorldGeocoder

    llm = build_activity_judge_llm()
    if llm is None:
        raise SystemExit("판정 LLM 이 없다 — ACOP_ACTIVITY_JUDGE_MODE 를 shadow 로 두고 OpenAI 키를 확인한다")
    geocoder = VWorldGeocoder.from_settings()
    if not geocoder._key:
        print("★브이월드 키(ACOP_VWORLD_API_KEY)가 없다 — 원장 밖 장소의 좌표는 채우지 못한다(웹 정보는 채운다)")
    kakao = build_kakao_local()
    if kakao is None:
        print("★카카오 키가 없다 — 원장 밖 장소는 실존을 못 물어봐 `unknown` 이 된다(원장에 있는 장소만 채운다)")
    # 코어 회사(tenant)는 이름 찾기가 쓰지 않는다 — 원장은 공용이다
    io = pe.PlaceIO(get_connection, "", kakao)
    budget = build_activity_judge_budget()

    result = enrich_batch.run(names, lambda name: pe.enrich_place(name, io, llm, geocoder, budget=budget, now=datetime.now(timezone.utc)),
                              limit=args.limit)
    print(f"웹 검색 {result['asked']:,}곳 · 상태 {result['by_status']} · 남음 {result['left']:,}")
    if pe.BUDGET in result["by_status"]:
        print("★웹 검색 예산이 다 찼다 — 남은 곳은 다음 실행에서 채운다(travel.activity_judge.budget.web)")


if __name__ == "__main__":
    main()

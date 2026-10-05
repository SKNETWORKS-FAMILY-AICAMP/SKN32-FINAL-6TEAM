# -*- coding: utf-8 -*-
"""소스(=키)별 호출 예산 여유 보고 — 읽기 전용. `[2026-10-05 사용자 지시 — 키별 호출 횟수 DB 추적]`

    python -m scripts.report_source_budget            # 표
    python -m scripts.report_source_budget --json     # 기계가 읽는 모양
    python -m scripts.report_source_budget --only its,utic

★무엇을 보나: `external_call_budget`(DB — 모든 프로세스가 같이 센다)의 **오늘(한국 시각)** 줄과 **이번 달** 줄. 소스마다 사용 / 상한(여유율) · 실패 수 · 거절 수(한도가 차서 안 부른 수).
  단계: ok · 경보(≥80%) · 위험(≥95%) · 찼음. 상한이 「모름」(월 한도 env 가 0)인 월 줄은 세기만 한다(`—`).
★`⛔제공처 한도 초과`: 제공처(예: ITS 월 한도 4001)가 한도 초과를 알려 그 기간 호출을 **그날 한국 자정까지 멈춘** 상태. 표의 사용 수가 **제공처가 실제로 허락한 한도의 관측값**이다
  (포털에서 한도를 조회하는 API 는 없고, ITS 공식 매뉴얼에도 숫자가 없다 — 월 한도는 로그인한 포털의 인증키 상세정보에만 있다).
★이 PC 의 DB 와 서버의 DB 는 **따로**다 — 같은 키를 두 곳이 쓰면 이 표는 **이 DB 에서 센 만큼**만 보인다(합이 키 한도를 넘을 수 있다 — 환경별로 한도를 나눠 둔다).
★소스 목록은 설정 `travel.source_budget_sources` + 따릉이(`seoul_bike`). 한도 env 가 0 이하인 소스는 안 센다.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.settings import get_guardrails, get_settings
from app.infrastructure.db.session import get_connection
from app.infrastructure.travel.call_budget import UNLIMITED, usage_report

KST = ZoneInfo("Asia/Seoul")
_LEVEL = {"ok": "정상", "warn": "경보", "critical": "위험", "exhausted": "찼음"}


def build_report(only: list[str] | None = None, *, now: datetime | None = None) -> list[dict]:
    settings, guardrails = get_settings(), get_guardrails()
    limits, monthly = settings.source_rate_limits(), settings.source_monthly_limits()
    names = [*(guardrails.get("travel.source_budget_sources") or []), "seoul_bike"]
    names = [name for name in dict.fromkeys(names) if limits.get(name, 0) > 0 and (not only or name in only)]
    caps = {name: {"day": int(limits[name]), "month": int(monthly.get(name) or UNLIMITED)} for name in names}
    return usage_report(get_connection, now=(now or datetime.now(KST)).astimezone(KST), meters=names, caps=caps)


def _cell(part: dict) -> str:
    cap = "—" if part["cap"] >= UNLIMITED else str(part["cap"])
    pct = "" if part["ratio"] is None else f" ({part['ratio'] * 100:.0f}%)"
    # ★제공처가 오늘 「한도 초과」를 알렸으면 우리 상한과 상관없이 멈춘 상태다 — 그때까지 센 사용 수가 제공처가 허락한 한도의 관측값(`learned_cap`)이다
    seen = f" ⛔제공처 한도 초과(관측 한도 {part['learned_cap']})" if part.get("provider_exhausted") else ""
    return f"{part['used']}/{cap}{pct}{seen}"


def render(rows: list[dict]) -> str:
    head = f"{'소스':<22}{'오늘 사용/상한':<20}{'이번 달 사용/상한':<22}{'실패(오늘)':<10}{'거절(오늘)':<10}단계"
    lines = [head, "-" * len(head)]
    for row in rows:
        lines.append(f"{row['meter']:<22}{_cell(row['day']):<20}{_cell(row['month']):<22}{row['day']['failed']:<10}{row['day']['rejected']:<10}{_LEVEL[row['level']]}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="소스별 호출 예산 여유 보고(읽기 전용)")
    parser.add_argument("--json", action="store_true", help="표 대신 JSON")
    parser.add_argument("--only", default="", help="쉼표로 구분한 소스 이름만")
    args = parser.parse_args()
    rows = build_report([name.strip() for name in args.only.split(",") if name.strip()] or None)
    print(json.dumps(rows, ensure_ascii=False, indent=2) if args.json else render(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

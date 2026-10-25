# -*- coding: utf-8 -*-
"""웹이 세션 없이 읽는 기능 스위치 — 공개 읽기(키 없음 · 개인 정보 없음). `[2026-10-19 사용자 결정 — ST4F-613]`

    GET   /v1/web/features   → {guardian: true|false, risk_panel: true|false, plan_input_extras: true|false}

★왜. 운영자가 항로 지킴이를 끄면 등록 전 화면(계획 담기의 카드 · 읽는 중 · 계획 확인의 머리 아이콘)도 숨겨야 하는데, 그 화면에는
  세션이 없을 수 있다(새 고객의 첫 계획). 등록한 여행 화면은 여행 조회의 `guardian` 칸으로 안다(끈 동안은 칸이 없다).
★값은 판정과 같은 곳에서 읽는다(`settings_hook.guardian_enabled` — 관리 콘솔 값이 먼저, 없거나 못 읽으면 가드레일).
  횟수를 세지 않는다 — 운영 설정 캐시(`web_guard.cache_seconds`)만 읽는다.
★`[2026-10-22 사용자 지시]` `risk_panel` — 계획 확인 화면(등록 전 · 수정 모드)의 위험 점검 칸을 보일지(`settings_hook.trip_risk_panel_enabled`).
  등록한 여행 화면은 여행 조회의 `risk_panel` 로 안다.
★`[2026-10-25 사용자 지시 — ST4F-739]` `plan_input_extras` — 계획 담기 화면의 보조 칸(파일 선택 · 계획 짜 주기 · 읽는 기준 · 여행 취향)을 보일지
  (`settings_hook.plan_input_extras_enabled`, 기본 꺼짐). 접수 자체는 막지 않는다.
계약 `wiki/external/rest-endpoints/web-trips.md` 「항로 지킴이 운영 스위치」 · 「여행 화면 위험 점검 칸」 · 「계획 담기 화면 보조 칸」.
"""
from __future__ import annotations

from fastapi import APIRouter

import app.core.settings as settings_module
from app.domains.travel_ops.components import settings_hook


def build_public_features_router() -> APIRouter:
    router = APIRouter(tags=["web-features"])

    @router.get("/v1/web/features")
    def public_features():
        tenant = settings_module.get_settings().tenant_id
        return {"guardian": settings_hook.guardian_enabled(tenant), "risk_panel": settings_hook.trip_risk_panel_enabled(tenant),
                "plan_input_extras": settings_hook.plan_input_extras_enabled(tenant)}

    return router


__all__ = ["build_public_features_router"]

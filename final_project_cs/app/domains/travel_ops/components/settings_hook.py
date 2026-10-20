# -*- coding: utf-8 -*-
"""운영자가 화면에서 바꾼 값을 읽는 **끼움 자리**. `[2026-10-06]` D-CS-013

★왜 있나. 전에는 대화 부품이 웹 남용 방어 모듈의 설정 표를 직접 읽었다(`web_guard.values`).
  채팅 동작 하나가 「끌 수 있는 기능」의 저장소 모양에 묶여 있었던 셈이다.

지금은 이렇게 돈다.

    부품            "이 값 운영자가 바꿨나?"  →  여기(`operator_setting`)
    설정 화면 기능  "내가 그 표를 들고 있다"  →  조립 때 `register()`

  아무도 꽂지 않으면 `None` 을 돌려준다 — 부르는 쪽이 가드레일 기본값을 쓴다.
  **값을 지어내지 않는다.** 표를 못 읽는 상황과 「조정값이 없다」를 같은 `None` 으로 돌려주는 것은
  의도한 것이다. 둘 다 「기본값으로 간다」가 정답이고, 그 사실은 부르는 쪽 주석이 적는다.
"""
from __future__ import annotations

from typing import Any, Callable

#: (tenant_id, 이름) -> 값 또는 None
Reader = Callable[[str, str], Any]

_reader: Reader | None = None


def register(reader: Reader) -> None:
    """조립 때 한 번. 다시 부르면 교체한다(재조립 대비)."""
    global _reader
    _reader = reader


def clear() -> None:
    global _reader
    _reader = None


def is_registered() -> bool:
    return _reader is not None


def operator_setting(tenant_id: str, name: str) -> Any:
    if _reader is None:
        return None
    try:
        return _reader(tenant_id, name)
    except Exception:                                   # noqa: BLE001 — 표를 못 읽으면 기본값으로 간다
        return None


GOOGLE_PRICE = "travel.dining.google_price_enabled"


def google_price_enabled(tenant_id: str) -> bool:
    """식당 대체 후보의 구글 가격 조회를 켰나. `[2026-10-13 사용자 지시]` 유료 결제 뒤 관리 콘솔에서 켠다.

    운영자가 화면에서 바꾼 값이 먼저, 없거나 못 읽으면 가드레일(`app.core.settings.google_price_enabled`, 기본 꺼짐).
    ★참/거짓이 아닌 값은 바꾼 값으로 보지 않는다 — 켜는 것은 명시한 경우뿐이다.
    """
    value = operator_setting(tenant_id, GOOGLE_PRICE)
    if isinstance(value, bool):
        return value
    from app.core.settings import google_price_enabled as guardrail_default

    return guardrail_default()


LODGING_MODE = "travel.lodging.alternatives_mode"
#: 숙소 모드 값 — demo(숙소 시연 모드) · test(테스트 모드) · off(끄기)
LODGING_MODES = ("demo", "test", "off")


def lodging_mode(tenant_id: str) -> str:
    """숙소 모드 — "demo"(숙소 시연 모드) · "test"(테스트 모드) · "off"(끄기). `[2026-10-19 사용자 결정]`

    숙소 팀 · 숙소 대안이 구글 호텔(SerpApi)을 부를지 정한다 — off 는 부르지 않음, test 는 하루 한도(확인 화면은 몫)까지,
    demo 는 하루 한도 · 몫 없이 월 한도만. 읽는 곳: 구글 호텔 어댑터의 호출 문(조립이 `operator_modes` 에 꽂는다) · `composition._lodging_rank`.
    운영자가 화면에서 바꾼 값이 먼저, 없거나 못 읽거나 목록 밖이면 가드레일(`lodging_mode_default`, 기본 off).
    """
    value = operator_setting(tenant_id, LODGING_MODE)
    if isinstance(value, str) and value in LODGING_MODES:
        return value
    return lodging_mode_default()


def lodging_mode_default() -> str:
    """숙소 모드 기본값 — 가드레일 `travel.candidates.lodging_mode`. 못 읽거나 목록 밖이면 **off**(켜는 것은 명시한 경우뿐).
    ★공통 설정(`app/core`)에 두지 않는다 — 업무 낱말(숙소)은 도메인 쪽에 둔다(구조 시험 `test_basement_is_domain_free`)."""
    from app.core.settings import ConfigError, get_guardrails

    try:
        raw = get_guardrails().get("travel.candidates.lodging_mode")
    except ConfigError:
        return "off"
    value = "off" if raw is None or raw is False else str(raw)
    return value if value in LODGING_MODES else "off"


UNLIMITED_MODE = "api.unlimited_mode"


def unlimited_mode(tenant_id: str) -> bool:
    """언리미티드 모드 — 켜면 바깥 API 호출 한도를 풀고 세기만 한다. `[2026-10-19 사용자 결정]` 기본 꺼짐.

    운영자가 화면에서 바꾼 값이 먼저, 없거나 못 읽으면 가드레일(`app.core.settings.unlimited_mode`, 기본 꺼짐).
    ★참/거짓이 아닌 값은 바꾼 값으로 보지 않는다 — 켜는 것은 명시한 경우뿐이다.
    """
    value = operator_setting(tenant_id, UNLIMITED_MODE)
    if isinstance(value, bool):
        return value
    from app.core.settings import unlimited_mode as guardrail_default

    return guardrail_default()


TAXI_CALL_PRODUCT = "travel.mobility.taxi_call_product_enabled"


def taxi_call_product_enabled(tenant_id: str) -> bool:
    """확인 화면에서 택시 호출 상품을 고르게 하나. `[2026-10-14 사용자 지시 · 핫픽스]` 택시 요금 계산 확인 뒤 관리 콘솔에서 켠다.

    운영자가 화면에서 바꾼 값이 먼저, 없거나 못 읽으면 가드레일(`app.core.settings.taxi_call_product_enabled`, 기본 꺼짐).
    ★참/거짓이 아닌 값은 바꾼 값으로 보지 않는다 — 켜는 것은 명시한 경우뿐이다.
    """
    value = operator_setting(tenant_id, TAXI_CALL_PRODUCT)
    if isinstance(value, bool):
        return value
    from app.core.settings import taxi_call_product_enabled as guardrail_default

    return guardrail_default()


TRIP_NOW_LABEL = "travel.trip_screen.now_label_enabled"


def trip_now_label_enabled(tenant_id: str) -> bool:
    """여행 화면에 「지금 HH:MM」 시각 꼬리표를 보이나. `[2026-10-15 사용자 결정 — ST4F-494]` 시험 기간에 켜 두고 배포 때 관리 콘솔에서 끈다.

    운영자가 화면에서 바꾼 값이 먼저, 없거나 못 읽으면 가드레일(`app.core.settings.trip_now_label_enabled`, 기본 켜짐).
    ★참/거짓이 아닌 값은 바꾼 값으로 보지 않는다. 읽는 곳은 여행 조회 응답의 `now_label`(`trip_api._trip_view`) 하나다.
    """
    value = operator_setting(tenant_id, TRIP_NOW_LABEL)
    if isinstance(value, bool):
        return value
    from app.core.settings import trip_now_label_enabled as guardrail_default

    return guardrail_default()


GUARDIAN = "travel.guardian.enabled"


def guardian_enabled(tenant_id: str) -> bool:
    """항로 지킴이를 쓰나. `[2026-10-19 사용자 결정 — ST4F-613]` 끄면 웹에서 숨기고 서버의 자동 일정 변경도 멈춘다(켠 기록은 그대로).

    운영자가 화면에서 바꾼 값이 먼저, 없거나 못 읽으면 가드레일(`app.core.settings.guardian_enabled`, 기본 켜짐).
    ★참/거짓이 아닌 값은 바꾼 값으로 보지 않는다 — 끄는 것은 `false` 로 명시한 경우뿐이다.
    읽는 곳: 판정(`planning/survey.on_disruption` · `auto_on_disruption` — 서비스 테넌트로) · 여행 조회의 `guardian` · 켜기 입구 ·
    알림(`planning/guardian.annotate` · 알림 목록) · 공개 읽기 `GET /v1/web/features`. 계약 `rest-endpoints/web-trips.md` 「항로 지킴이 운영 스위치」.
    """
    value = operator_setting(tenant_id, GUARDIAN)
    if isinstance(value, bool):
        return value
    from app.core.settings import guardian_enabled as guardrail_default

    return guardrail_default()


ACTIVITY_LIVE_CHECK = "travel.activity_judge.live_status_batch_enabled"


def activity_live_check_enabled(tenant_id: str) -> bool:
    """활동 장소 임시휴무 · 폐업 새벽 웹 확인을 돌리나. `[2026-10-14 사용자 지시]` 유료 웹 검색이라 관리 콘솔에서 켤 때만.

    운영자가 화면에서 바꾼 값이 먼저, 없거나 못 읽으면 가드레일(`app.core.settings.activity_live_check_enabled`, 기본 꺼짐).
    ★참/거짓이 아닌 값은 바꾼 값으로 보지 않는다 — 켜는 것은 명시한 경우뿐이다.
    """
    value = operator_setting(tenant_id, ACTIVITY_LIVE_CHECK)
    if isinstance(value, bool):
        return value
    from app.core.settings import activity_live_check_enabled as guardrail_default

    return guardrail_default()


#: 상황마다의 운영 설정 이름 — 채팅(옛 이름 그대로 두어 이미 저장된 값을 잇는다) · 일정 짚기 · 공지 확인
MODEL_ROUTE = "llm.model_route"
MODEL_ROUTE_KEYS = {"chat": MODEL_ROUTE, "pointer": "llm.model_route.pointer", "notice": "llm.model_route.notice"}
MODEL_ROUTE_CHOICES = {"chat": ("off", "local", "ssh", "api"), "pointer": ("off", "local", "ssh"), "notice": ("off", "local", "ssh")}


def model_route_choice(tenant_id: str, purpose: str = "chat") -> str:
    """관리 콘솔에서 그 상황(chat · pointer · notice)에 고른 모델 경로 — off(환경 파일 따름) · local · ssh · api. `[2026-10-15 · 10-16 사용자 지시]`

    콘솔 값이 없거나 못 읽거나 목록 밖이면 가드레일 기본(`web_guard.model_route.default`, 기본 off).
    ★off 를 경로로 바꾸는 일(환경 파일 `ACOP_MODEL_ROUTE_<상황>` 읽기)은 `app.infrastructure.ollama_chat.resolve_route` 가 한다 — 조립 루트가 이 함수를 꽂는다.
    """
    choices = MODEL_ROUTE_CHOICES.get(purpose)
    if choices is None:
        return "off"
    value = operator_setting(tenant_id, MODEL_ROUTE_KEYS[purpose])
    if value in choices:
        return str(value)
    from app.core.settings import get_guardrails

    default = str((get_guardrails().get("web_guard.model_route") or {}).get("default") or "off")
    return default if default in choices else "off"

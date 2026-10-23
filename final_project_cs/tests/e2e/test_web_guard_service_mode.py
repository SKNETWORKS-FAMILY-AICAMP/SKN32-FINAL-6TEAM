# -*- coding: utf-8 -*-
"""서비스 모드 — 회원 · 게스트 한 시간 한도. `[2026-10-22 사용자 지시]`

「무료 계정은 시간당으로 제한 · 로그인 안 하면 빡시게 · 지금은 테스트 모드라 상관없음 · 양은 관리자 웹앱에서 설정」.
코드 `web_guard.count` · 기본값 가드레일 `web_guard.service_mode` · 계약 `wiki/external/rest-endpoints/web-access.md` 「서비스 모드」.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.modules.web_account import web_guard

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_guard import _client, _key, _member, _set, _web_trip

KST = ZoneInfo("Asia/Seoul")
WHERE = "service-mode-test-address"          # 주소 칸은 HMAC 으로만 남는다 — 실제 주소 대신 글자


@pytest.fixture(autouse=True)
def _fresh_cache():
    web_guard.clear_cache()
    yield
    web_guard.clear_cache()


def _customer(api, *, guest: bool):
    """게스트 = `web:` 고객 + 소셜 연결 없음(`guest_policy.is_guest`). 회원 = 같은 고객에 소셜 연결."""
    customer = uuid4()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO customers (customer_id, tenant_id, external_id) VALUES (%s,%s,%s)",
                    (customer, api["tenant"], f"web:service-mode-{customer}"))
        if not guest:
            cur.execute("INSERT INTO web_social_links (tenant_id, provider, subject_hash, customer_id) VALUES (%s,'google',%s,%s)",
                        (api["tenant"], "h-" + uuid4().hex, customer))
    return customer


def _hour_rows(api):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT who, action, used FROM web_usage WHERE tenant_id=%s AND period LIKE 'hour:%%' AND action='place_search'",
                    (api["tenant"],))
        return cur.fetchall()


def test_the_switch_and_every_tier_limit_are_operator_settings_and_guests_get_less():
    table = web_guard.specs()
    assert table[web_guard.SERVICE_MODE_NAME].default is False                       # 지금은 시험 단계 — 꺼짐
    for action in web_guard.ACTIONS:
        member = table[web_guard.tier_limit_name("member", action)].default
        guest = table[web_guard.tier_limit_name("guest", action)].default
        assert 1 <= guest < member, action                                              # 게스트가 늘 더 빡빡하다


def test_off_means_no_hourly_counting_and_no_hourly_block(api):
    _set(api, web_guard.tier_limit_name("guest", "place_search"), 1)
    guest = _customer(api, guest=True)
    for _ in range(3):
        web_guard.count(api["tenant"], "place_search", customer_id=guest, ip=WHERE)
    assert _hour_rows(api) == []


def test_on_a_guest_is_stopped_by_the_hour_and_told_when_it_opens(api):
    _set(api, web_guard.SERVICE_MODE_NAME, True)
    _set(api, "web.place_search.per_key_day", 1000)
    _set(api, "web.place_search.per_ip_day", 1000)
    _set(api, "web.place_search.service_day", 1000)
    _set(api, web_guard.tier_limit_name("guest", "place_search"), 2)
    _set(api, web_guard.tier_limit_name("member", "place_search"), 5)
    guest, member = _customer(api, guest=True), _customer(api, guest=False)
    now = datetime(2030, 1, 5, 14, 40, tzinfo=KST)
    for _ in range(2):
        web_guard.count(api["tenant"], "place_search", customer_id=guest, ip=WHERE, now=now)
    with pytest.raises(web_guard.UsageRefused) as refused:
        web_guard.count(api["tenant"], "place_search", customer_id=guest, ip=WHERE, now=now)
    assert (refused.value.status, refused.value.code, refused.value.limit, refused.value.cap) == (429, "hourly_limit", "guest_hour", 2)
    assert refused.value.retry_after == 20 * 60 + 1                                   # 15:00 정시까지
    # 회원은 자기 한도(5)까지 — 게스트가 막혀도 상관없다
    for _ in range(3):
        web_guard.count(api["tenant"], "place_search", customer_id=member, ip=WHERE, now=now)
    # 다음 정시에는 게스트도 다시 된다
    web_guard.count(api["tenant"], "place_search", customer_id=guest, ip=WHERE, now=now.replace(hour=15, minute=1))
    # ★막힌 요청은 하루 칸도 올리지 않았다 — 게스트의 하루 칸은 통과한 3번뿐
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT used FROM web_usage WHERE tenant_id=%s AND who_kind='key' AND who=%s AND action='place_search' "
                    "AND period LIKE 'day:%%'", (api["tenant"], str(guest)))
        assert [row[0] for row in cur.fetchall()] == [3]


def test_on_also_turns_the_daily_limits_on(api):
    _set(api, "web.limits_enabled", False)
    _set(api, web_guard.SERVICE_MODE_NAME, True)
    _set(api, "web.place_search.per_key_day", 1)
    member = _customer(api, guest=False)
    web_guard.count(api["tenant"], "place_search", customer_id=member, ip=WHERE)
    with pytest.raises(web_guard.UsageRefused) as refused:
        web_guard.count(api["tenant"], "place_search", customer_id=member, ip=WHERE)
    assert refused.value.code == "usage_limit"


def test_the_web_answer_is_429_hourly_limit_with_retry_after(api):
    _set(api, web_guard.SERVICE_MODE_NAME, True)
    for scope in ("per_key_day", "per_ip_day", "service_day"):
        _set(api, f"web.trip_create.{scope}", 100)
    _set(api, web_guard.tier_limit_name("member", "trip_create"), 1)
    client = _client()
    headers = _member(api, _key(client))
    assert client.post("/v1/web/trips", json=_web_trip(api, "svc-mode-1"), headers=headers).status_code == 201
    refused = client.post("/v1/web/trips", json=_web_trip(api, "svc-mode-2"), headers=headers)
    assert refused.status_code == 429, refused.text
    error = refused.json()["error"]
    assert (error["code"], error["limit"], error["cap"]) == ("hourly_limit", "member_hour", 1)
    assert 0 < int(refused.headers["retry-after"]) <= 3601

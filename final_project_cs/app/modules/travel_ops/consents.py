# -*- coding: utf-8 -*-
"""약관 동의 기록 · 사용 조건(게이트). `[2026-10-05 사용자 지시 — ui 세션 요청서 「동의 기록 · 위치 수집」]` 마이그레이션 046

계약 `wiki/records/plans/2026-10-05_동의기록_위치수집_백엔드_요청.md` · HTTP `consents_api.py` · 게이트 `web_cookie.authenticate`.

★동의 항목 다섯 — 필수 둘(`service_terms` · `privacy`)은 **지금 약관 버전으로** 동의돼 있어야 앱을 쓴다. 선택 셋(`sensitive` · `location` · `alert_channel`)은 앱을 막지 않는다
  (개인정보 보호법이 「꼭 필요한 최소한을 넘는 정보에 동의하지 않는다고 서비스를 거부하는 것」을 금한다는 알려진 규정 — ★조문을 읽어 확인하지 않았다 `[법무 확인 필요]`).
★기록은 **추가만** 한다(`consent_events`): 철회도 새 줄이고 지우지도 고치지도 않는다(DB 트리거가 지킨다). 현재 상태는 사용자 · 코드별 가장 최근 줄(`consent_current`).
  주소는 원문이 아니라 서버 비밀로 만든 해시(`ip_hash`)만 둔다. 사용자 행에는 외래키를 걸지 않는다 — 게스트가 정리돼도 증빙은 보관 기간 동안 남는다.
★게이트(`gate_check`)는 설정 `consent.gate_enabled` 가 **켜져 있을 때만** 막는다(기본 꺼짐 — 웹이 동의 화면을 내보내기 전에 켜면 모두 갇힌다). 켜면 게스트 · 회원 · 옛 키 · 에이전트 키 모두
  **사용자의 동의 상태**를 따른다(에이전트 키는 키 주인). 동의 · 로그인 · 세션 만들기 길은 면제다(`EXEMPT_PREFIXES`) — 그래야 동의하러 갈 수 있다.
★철회 효과: `alert_channel` → 저장한 알림 채널(디스코드 웹훅)을 지운다 · `sensitive` → 여행의 식사 제한 · 설문 음식 답(`trips.constraints`)을 지운다 ·
  `location` → 위치 점(2단계 구현이 `PURGERS["location"]` 에 등록한다). 효과는 **동의 기록과 한 트랜잭션**에서 일어난다 — 기록만 남고 삭제가 안 됐거나 그 반대가 되지 않게.
  `[미확인]` 설문 답이 다른 복사본(일정 버전 스냅샷 · 접수 원문)에도 남는지는 이번에 확인하지 않았다.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import UUID

import app.core.settings as settings_module
from app.core.settings import get_guardrails

log = logging.getLogger(__name__)

CODES = ("service_terms", "privacy", "sensitive", "location", "alert_channel")
_SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_USER_AGENT = 300
#: 게이트를 면제하는 길 — 동의하러 가는 길(동의 · 로그인 · 세션 만들기)은 막을 수 없다. 건강 확인 · 공개 계획서 링크 · 메신저 웹훅은 사용자 인증을 안 거치므로 게이트에 닿지 않는다
EXEMPT_PREFIXES = ("/v1/web/consents", "/v1/web/auth", "/v1/web/session")
#: 철회 때 지울 것을 부르는 자리 — `{코드: [함수(conn, tenant_id, user_id) -> 지운 개수]}`. 위치 수집이 `location` 을 등록한다
PURGERS: dict[str, list[Callable[..., int]]] = {}


class ConsentError(Exception):
    def __init__(self, status: int, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra


# ── 설정 ────────────────────────────────────────────────────────
def current_version() -> str:
    return str(get_guardrails().get("consent.terms_version"))


def required_codes() -> tuple[str, ...]:
    return tuple(str(code) for code in get_guardrails().get("consent.required"))


def gate_enabled() -> bool:
    return bool(get_guardrails().get("consent.gate_enabled"))


def ip_hash(ip: str | None) -> str | None:
    """증빙용 주소 해시 — 서버 비밀로 만든 HMAC(날짜를 섞지 않는다: 같은 사용자의 같은 주소를 이어 볼 수 있어야 증빙이다). 주소 원문은 어디에도 두지 않는다."""
    if not ip:
        return None
    secret = settings_module.get_settings().secret_key.encode()
    return hmac.new(secret, f"consent-ip:{ip}".encode(), hashlib.sha256).hexdigest()


# ── 조회 ────────────────────────────────────────────────────────
def _current_rows(conn, tenant_id: str, user_id: UUID) -> dict[str, tuple[bool, str, str, datetime]]:
    with conn.cursor() as cur:
        cur.execute("SELECT code, agreed, terms_version, text_sha256, at FROM consent_current WHERE tenant_id=%s AND user_id=%s",
                    (tenant_id, user_id))
        return {row[0]: (row[1], row[2], row[3], row[4]) for row in cur.fetchall()}


def _is_ok(rows: dict[str, tuple[bool, str, str, datetime]]) -> bool:
    version = current_version()
    return all(code in rows and rows[code][0] and rows[code][1] == version for code in required_codes())


def state(conn, tenant_id: str, user_id: UUID) -> dict[str, Any]:
    """`GET /v1/web/consents` 의 모양. 기록이 없는 항목은 `agreed:false` · 나머지 null. `ok` = 필수가 모두 **지금 버전으로** 동의됨."""
    rows = _current_rows(conn, tenant_id, user_id)
    items = []
    for code in CODES:
        row = rows.get(code)
        items.append({"code": code, "agreed": bool(row and row[0]), "version": row[1] if row else None,
                      "agreed_at": row[3].isoformat() if row else None})
    return {"current_version": current_version(), "required": list(required_codes()), "items": items, "ok": _is_ok(rows)}


def is_ok(conn, tenant_id: str, user_id: UUID) -> bool:
    return _is_ok(_current_rows(conn, tenant_id, user_id))


def has(conn, tenant_id: str, user_id: UUID, code: str) -> bool:
    """이 항목에 **지금 버전으로** 동의돼 있나 — 선택 항목(위치 등)을 쓰기 전에 본다."""
    row = _current_rows(conn, tenant_id, user_id).get(code)
    return bool(row and row[0] and row[1] == current_version())


# ── 기록 ────────────────────────────────────────────────────────
def record(conn, *, tenant_id: str, user_id: UUID, session_kind: str, version: Any, items: Any, ip: str | None,
           user_agent: str | None) -> dict[str, Any]:
    """동의 · 철회를 기록하고 새 상태를 돌려준다. ★전부 맞아야 하나도 기록한다(일부만 남지 않는다). 바뀌지 않은 항목은 줄을 더하지 않는다(같은 동의를 되풀이해 늘리지 않는다).

    오류: 버전이 지금과 다르면 409 `terms_version_changed`(지금 버전을 싣는다) · 모르는 코드 · 모양이 틀린 입력 422."""
    if version != current_version():
        raise ConsentError(409, "terms_version_changed", "약관 버전이 바뀌었어요 — 새 약관을 보고 다시 동의해 주세요", current_version=current_version())
    if not isinstance(items, list) or not items or len(items) > len(CODES):
        raise ConsentError(422, "invalid_items", "동의 항목이 비었거나 모양이 틀려요")
    parsed: dict[str, tuple[bool, str]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ConsentError(422, "invalid_items", "동의 항목 모양이 틀려요")
        code, agreed, digest = item.get("code"), item.get("agreed"), item.get("text_sha256")
        if code not in CODES:
            raise ConsentError(422, "unknown_code", "모르는 동의 항목이 있어요")
        if not isinstance(agreed, bool):
            raise ConsentError(422, "invalid_items", "agreed 는 true 또는 false 여야 해요")
        if not isinstance(digest, str) or not _SHA.match(digest):
            raise ConsentError(422, "invalid_text_sha256", "text_sha256 은 소문자 16진수 64자여야 해요")
        if code in parsed:
            raise ConsentError(422, "invalid_items", "같은 항목이 두 번 들어 있어요")
        parsed[code] = (agreed, digest)
    before = _current_rows(conn, tenant_id, user_id)
    agent = (user_agent or "")[:MAX_USER_AGENT] or None
    withdrawn: list[str] = []
    with conn.transaction(), conn.cursor() as cur:
        for code, (agreed, digest) in parsed.items():
            old = before.get(code)
            if old is not None and old[0] == agreed and old[1] == version and old[2] == digest:
                continue                                                     # 바뀐 것이 없다
            cur.execute("INSERT INTO consent_events (tenant_id, user_id, session_kind, code, agreed, terms_version, text_sha256, ip_hash, user_agent) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (tenant_id, user_id, session_kind, code, agreed, version, digest, ip_hash(ip), agent))
            if not agreed and old is not None and old[0]:
                withdrawn.append(code)
        for code in withdrawn:
            purge(conn, tenant_id, user_id, code)
    return state(conn, tenant_id, user_id)


# ── 철회 효과 ───────────────────────────────────────────────────
def _purge_alert_channel(conn, tenant_id: str, user_id: UUID) -> int:
    """저장한 알림 채널(디스코드 웹훅)을 지운다 — 같은 경로(`customer_profile.update`)로 null 을 준다."""
    from . import customer_profile

    view = customer_profile.read(conn, tenant_id, user_id)
    if not view.webhook_set:
        return 0
    customer_profile.update(conn, tenant_id, user_id, {"discord_webhook_url": None})
    return 1


def _purge_sensitive(conn, tenant_id: str, user_id: UUID) -> int:
    """여행의 식사 제한(`dietary`)과 설문 음식 답(`survey.priority_details.food`)을 지운다 — 종교(할랄)나 식이 정보가 들어 있다."""
    with conn.cursor() as cur:
        cur.execute("UPDATE trips SET constraints = (constraints - 'dietary') #- '{survey,priority_details,food}' "
                    "WHERE tenant_id=%s AND customer_id=%s AND (constraints ? 'dietary' OR constraints #> '{survey,priority_details,food}' IS NOT NULL)",
                    (tenant_id, user_id))
        return cur.rowcount


PURGERS.setdefault("alert_channel", []).append(_purge_alert_channel)
PURGERS.setdefault("sensitive", []).append(_purge_sensitive)


def purge(conn, tenant_id: str, user_id: UUID, code: str) -> int:
    """이 항목의 철회 효과를 실행한다 — 지운 개수의 합. 하나가 실패하면 예외가 올라가 **동의 기록도 함께 되돌아간다**."""
    return sum(fn(conn, tenant_id, user_id) for fn in PURGERS.get(code, []))


# ── 사용 조건(게이트) ───────────────────────────────────────────
def gate_check(conn, *, tenant_id: str, user_id: UUID, path: str) -> None:
    """게이트가 켜져 있고 이 길이 면제가 아니면, 필수 동의가 지금 버전으로 없을 때 403 `consent_required`."""
    if not gate_enabled():
        return
    if any(path == prefix or path.startswith(prefix + "/") for prefix in EXEMPT_PREFIXES):
        return
    if not is_ok(conn, tenant_id, user_id):
        raise ConsentError(403, "consent_required", "약관에 동의해야 쓸 수 있어요", current_version=current_version(),
                           required=list(required_codes()))


# ── 정리 ────────────────────────────────────────────────────────
def purge_expired(conn, tenant_id: str, now: datetime | None = None) -> int:
    """보관 기간(`consent.evidence_retention_days`)이 지난 동의 기록을 지운다 — 삭제는 이 함수만 한다(트리거가 이 트랜잭션에서만 허용)."""
    days = int(get_guardrails().get("consent.evidence_retention_days"))
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SET LOCAL app.consent_purge = 'on'")
        cur.execute("DELETE FROM consent_events WHERE tenant_id=%s AND at < %s", (tenant_id, cutoff))
        return cur.rowcount


__all__ = ["CODES", "ConsentError", "EXEMPT_PREFIXES", "PURGERS", "current_version", "gate_check", "gate_enabled", "has", "ip_hash",
           "is_ok", "purge", "purge_expired", "record", "required_codes", "state"]

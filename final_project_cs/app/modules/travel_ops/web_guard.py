# -*- coding: utf-8 -*-
"""웹 남용 방어 — 비싼 작업 횟수 · 키 발급 · 사람 확인 · 빈 키 정리. `[2026-09-28]` 사용자 지시

계획 `wiki/records/plans/2026-09-28_2130_웹_남용방어_실행계획.md` · 계약 `wiki/external/rest-endpoints.md` 「남용 방어」 ·
저장 `web_usage` · `runtime_limits` · `runtime_limit_events`(마이그레이션 031).

★왜. 웹은 로그인 없이 키를 받아 쓰는데, 키를 받은 뒤 사진 읽기 · 일정 짜기 · 채팅을 몇 번이든 부를 수 있었다.
  아까운 것은 돈보다 **공용 하루 한도**다(관광공사 1,000) — 한 사람이 다 쓰면 모든 사용자가 멈춘다.
★세는 곳은 DB 한 곳이다(027 `external_call_budget` 과 같은 방식) — 재시작해도, 프로세스가 여럿이어도 이어서 센다.
  전에는 키 발급만 **프로세스 메모리**에서 셌고 재시작하면 풀렸다.
★횟수 제한은 **기본 꺼짐**(사용자 결정 — 개발 단계). 꺼져 있어도 센다(운영 API 의 오늘 사용량 · 비용 산정 재료).
★주소는 원문을 두지 않는다 — `HMAC(서버 비밀키, 날짜|주소)` 만, 48시간 뒤 지운다.
★값: 기본값·범위는 가드레일 `web_guard`(정본), 운영자가 바꾼 값은 `runtime_limits`(`web_limits_api.py`).
"""
from __future__ import annotations

import hashlib
import hmac
import threading
import time as _time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg.errors import ForeignKeyViolation

import app.core.settings as settings_module
from app.core.settings import get_guardrails
from app.infrastructure.db.session import get_connection

KST = ZoneInfo("Asia/Seoul")

#: 세는 작업 — 계약의 이름 그대로
ACTIONS = ("intake", "plan", "confirm", "trip_create", "message", "warmup")
ACTION_LABELS = {"intake": "계획 읽기", "plan": "일정 짜기", "confirm": "확인(등록)", "trip_create": "여행 만들기",
                 "message": "채팅 메시지", "warmup": "모델 예열"}
SCOPE_LABELS = {"per_key_day": "키당 하루", "per_ip_day": "주소당 하루", "service_day": "서비스 전체 하루"}


# ── 제한값 ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class LimitSpec:
    name: str
    label: str
    unit: str
    type: str                # int · bool · choice
    default: Any
    min: int | None = None
    max: int | None = None
    #: ★`[2026-09-29]` `choice` 의 고를 수 있는 값 — 목록 밖 글자는 받지 않는다
    choices: tuple[str, ...] | None = None

    def check(self, value: Any) -> str | None:
        """맞으면 None, 아니면 거절 이유 코드."""
        if self.type == "bool":
            return None if isinstance(value, bool) else "wrong_type"
        if self.type == "choice":
            if not isinstance(value, str):
                return "wrong_type"
            return None if value in (self.choices or ()) else "not_a_choice"
        if isinstance(value, bool) or not isinstance(value, int):
            return "wrong_type"
        if (self.min is not None and value < self.min) or (self.max is not None and value > self.max):
            return "out_of_range"
        return None

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "label": self.label, "unit": self.unit, "type": self.type,
                "default": self.default, "min": self.min, "max": self.max,
                **({"choices": list(self.choices)} if self.choices else {})}


def _mode_text(raw: Any) -> str:
    """YAML 이 참/거짓으로 읽은 on/off 를 글자로(따옴표를 빠뜨려도 꺼지지 않게)."""
    if isinstance(raw, bool):
        return "on" if raw else "off"
    return str(raw or "off")


def specs() -> dict[str, LimitSpec]:
    """바꿀 수 있는 이름 전부 — 가드레일에서 만든다(목록에 없는 이름은 받지 않는다)."""
    guard = get_guardrails()
    count = guard.get("web_guard.bounds.count")
    out: dict[str, LimitSpec] = {
        "web.limits_enabled": LimitSpec("web.limits_enabled", "횟수 제한 켜기", "", "bool",
                                        bool(guard.get("web_guard.limits_enabled")))}
    for action in ACTIONS:
        for scope, label in SCOPE_LABELS.items():
            name = f"web.{action}.{scope}"
            out[name] = LimitSpec(name, f"{ACTION_LABELS[action]} — {label}", "회", "int",
                                  int(guard.get(f"web_guard.limits.{action}.{scope}")),
                                  int(count["min"]), int(count["max"]))
    session = guard.get("web_guard.bounds.session_per_ip_hour")
    out["web.session.per_ip_hour"] = LimitSpec(
        "web.session.per_ip_hour", "키 발급 — 주소당 한 시간", "개", "int",
        int(guard.get("security.web_session_issue_per_hour")), int(session["min"]), int(session["max"]))
    idle = guard.get("web_guard.bounds.idle_key_days")
    out["web.idle_key_days"] = LimitSpec("web.idle_key_days", "빈 키 보관 일수", "일", "int",
                                         int(guard.get("web_guard.idle_key_days")), int(idle["min"]), int(idle["max"]))
    out["web.idle_key_cleanup_enabled"] = LimitSpec("web.idle_key_cleanup_enabled", "빈 키 정리 켜기", "", "bool",
                                                    bool(guard.get("web_guard.idle_key_cleanup_enabled")))
    # ★`[2026-09-29 사용자 결정]` 화면 안 지도 종류 — 개발 콘솔에서 구글 ↔ 무료 지도(OSM)를 바꾼다. 기본은 무료 지도
    choices = tuple(guard.get("web_guard.map_provider.choices"))
    out["web.map_provider"] = LimitSpec("web.map_provider", "화면 지도 종류", "", "choice",
                                        str(guard.get("web_guard.map_provider.default")), choices=choices)
    # ★`[2026-09-29 사용자 지시]` 개발 모드 — 켜면 웹 채팅 응답에 근거(`basis`)를 싣는다. 고객 문장에는 늘 싣지 않는다
    out["web.dev_mode"] = LimitSpec("web.dev_mode", "개발 모드(근거 보이기)", "", "choice", "off", choices=("off", "on"))
    # ★`[2026-09-29 Codex 3회차 합의]` 채팅 결정 단위 — 재기동 없이 끄고 켠다(오변경이 보이면 곧바로 shadow 로)
    out["chat.decision_mode"] = LimitSpec("chat.decision_mode", "채팅 해석 방식(결정 단위)", "", "choice",
                                          _mode_text(guard.get("travel.decision_unit.mode")),
                                          choices=("off", "shadow", "on"))
    return out


_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def overrides(conn, tenant_id: str) -> dict[str, dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT name, value, updated_at, updated_by FROM runtime_limits WHERE tenant_id=%s", (tenant_id,))
        return {r[0]: {"value": r[1], "updated_at": r[2], "updated_by": r[3]} for r in cur.fetchall()}


def values(tenant_id: str) -> dict[str, Any]:
    """지금 쓰는 값 — 운영자가 바꾼 값(범위 안)이 있으면 그것, 없으면 가드레일 기본값. `cache_seconds` 캐시."""
    wait = float(get_guardrails().get("web_guard.cache_seconds"))
    with _cache_lock:
        hit = _cache.get(tenant_id)
        if hit and _time.monotonic() - hit[0] < wait:
            return dict(hit[1])
    table = specs()
    with get_connection() as conn:
        stored = overrides(conn, tenant_id)
    out = {}
    for name, spec in table.items():
        value = stored.get(name, {}).get("value", spec.default)
        # ★가드레일 범위가 나중에 좁아져 저장값이 밖이 되면 기본값을 쓴다 — 범위 밖 값으로 돌지 않는다
        out[name] = value if spec.check(value) is None else spec.default
    with _cache_lock:
        _cache[tenant_id] = (_time.monotonic(), dict(out))
    return out


# ── 주소 ────────────────────────────────────────────────────────
def client_ip(host: str | None, forwarded_for: str | None) -> str:
    """원 주소. ★`trusted_proxies` 에 적힌 주소에서 온 요청만 `X-Forwarded-For` 를 믿는다 — 오른쪽부터 믿는 프록시를
    건너뛰고 처음 나오는 주소. 믿는 프록시가 없으면 연결 주소(머리를 속여 한도를 피하지 못하게)."""
    trusted = {p.strip() for p in (getattr(settings_module.get_settings(), "trusted_proxies", "") or "").split(",") if p.strip()}
    host = host or "unknown"
    if not trusted or host not in trusted or not forwarded_for:
        return host
    chain = [p.strip() for p in forwarded_for.split(",") if p.strip()] + [host]
    for address in reversed(chain):
        if address not in trusted:
            return address
    return chain[0]


def ip_token(ip: str, day: str) -> str:
    """주소 원문 대신 남기는 값. 날짜가 섞여 다른 날의 같은 주소와 이어지지 않는다."""
    secret = settings_module.get_settings().secret_key.encode()
    return hmac.new(secret, f"{day}|{ip}".encode(), hashlib.sha256).hexdigest()[:32]


# ── 세기 ────────────────────────────────────────────────────────
class UsageRefused(Exception):
    def __init__(self, *, status: int, code: str, limit: str, action: str, used: int, cap: int,
                 retry_after: int) -> None:
        super().__init__(code)
        self.status, self.code, self.limit, self.action = status, code, limit, action
        self.used, self.cap, self.retry_after = used, cap, retry_after

    def detail(self) -> dict[str, Any]:
        return {"limit": self.limit, "action": self.action, "used": self.used, "cap": self.cap,
                "retry_after_seconds": self.retry_after}


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(KST)).astimezone(KST)


def _seconds_to(moment: datetime, now: datetime) -> int:
    return max(1, int((moment - now).total_seconds()) + 1)


def _bump(cur, tenant_id: str, kind: str, who: str, action: str, period: str, cap: int | None) -> int | None:
    """한 칸 올린다. `cap` 이 있으면 `used < cap` 일 때만 — 못 올리면 None."""
    cur.execute("INSERT INTO web_usage (tenant_id, who_kind, who, action, period) VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT DO NOTHING", (tenant_id, kind, who, action, period))
    if cap is None:
        cur.execute("UPDATE web_usage SET used = used + 1, updated_at = now() WHERE tenant_id=%s AND who_kind=%s "
                    "AND who=%s AND action=%s AND period=%s RETURNING used", (tenant_id, kind, who, action, period))
    else:
        cur.execute("UPDATE web_usage SET used = used + 1, updated_at = now() WHERE tenant_id=%s AND who_kind=%s "
                    "AND who=%s AND action=%s AND period=%s AND used < %s RETURNING used",
                    (tenant_id, kind, who, action, period, cap))
    row = cur.fetchone()
    return None if row is None else int(row[0])


def count(tenant_id: str, action: str, *, customer_id: UUID | str, ip: str,
          now: datetime | None = None) -> dict[str, Any]:
    """비싼 작업 한 번. 켜져 있으면 서비스 → 주소 → 키 순으로 **모두** 자리가 있을 때만 올린다(한 트랜잭션).
    막히면 `UsageRefused`(아무것도 안 올라간다). 꺼져 있으면 막지 않고 세기만 한다."""
    if action not in ACTIONS:
        raise ValueError(f"모르는 작업: {action}")
    now = _now(now)
    day = f"day:{now:%Y-%m-%d}"
    limits = values(tenant_id)
    enabled = bool(limits["web.limits_enabled"])
    rows = [("all", "*", "service_day"), ("ip", ip_token(ip, day), "per_ip_day"),
            ("key", str(customer_id), "per_key_day")]
    midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=KST)
    used: dict[str, int] = {}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for kind, who, scope in rows:
            cap = int(limits[f"web.{action}.{scope}"])
            got = _bump(cur, tenant_id, kind, who, action, day, cap if enabled else None)
            if got is None:
                cur.execute("SELECT used FROM web_usage WHERE tenant_id=%s AND who_kind=%s AND who=%s AND action=%s "
                            "AND period=%s", (tenant_id, kind, who, action, day))
                current = int(cur.fetchone()[0])
                # ★예외가 트랜잭션을 되돌린다 — 앞에서 올린 서비스·주소 칸도 올라가지 않는다
                raise UsageRefused(status=503 if kind == "all" else 429,
                                   code="service_daily_cap" if kind == "all" else "usage_limit",
                                   limit=scope.replace("_day", ""), action=action, used=current, cap=cap,
                                   retry_after=_seconds_to(midnight, now))
            used[scope] = got
    return {"enabled": enabled, "used": used}


def count_session(tenant_id: str, *, ip: str, now: datetime | None = None) -> None:
    """키 발급 — 주소당 한 시간(`web.session.per_ip_hour`). ★이 한도는 **늘 켜져 있다**(2026-09-24 D-020 부터 있던 것 —
    끄는 것은 개발용 `web_session_issue_unlimited` 뿐). 막히면 `UsageRefused`(429 `too_many_sessions`)."""
    now = _now(now)
    hour = f"hour:{now:%Y-%m-%dT%H}"
    cap = None if settings_module.get_settings().web_session_issue_unlimited else int(values(tenant_id)["web.session.per_ip_hour"])
    who = ip_token(ip, f"day:{now:%Y-%m-%d}")
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        if _bump(cur, tenant_id, "ip", who, "session", hour, cap) is None:
            next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            raise UsageRefused(status=429, code="too_many_sessions", limit="per_ip_hour", action="session",
                               used=int(cap or 0), cap=int(cap or 0), retry_after=_seconds_to(next_hour, now))


def usage_today(conn, tenant_id: str, now: datetime | None = None) -> dict[str, Any]:
    """서비스 전체 오늘 사용량만 — 키·주소별은 싣지 않는다(개인정보)."""
    day = f"day:{_now(now):%Y-%m-%d}"
    with conn.cursor() as cur:
        cur.execute("SELECT action, used FROM web_usage WHERE tenant_id=%s AND who_kind='all' AND period=%s",
                    (tenant_id, day))
        found = dict(cur.fetchall())
    return {"day": day[4:], "all": {action: int(found.get(action, 0)) for action in ACTIONS}}


# ── 정리(되잡기 작업) ──────────────────────────────────────────
def prune_usage(conn, tenant_id: str, now: datetime | None = None) -> dict[str, int]:
    """주소 줄은 `ip_retention_hours`, 나머지는 `usage_retention_days` 뒤 지운다."""
    now = _now(now)
    guard = get_guardrails()
    ip_cut = now - timedelta(hours=float(guard.get("web_guard.ip_retention_hours")))
    rest_cut = now - timedelta(days=float(guard.get("web_guard.usage_retention_days")))
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM web_usage WHERE tenant_id=%s AND who_kind='ip' AND updated_at < %s",
                    (tenant_id, ip_cut))
        ips = cur.rowcount
        cur.execute("DELETE FROM web_usage WHERE tenant_id=%s AND who_kind<>'ip' AND updated_at < %s",
                    (tenant_id, rest_cut))
        rest = cur.rowcount
    return {"ip_rows_deleted": ips, "usage_rows_deleted": rest}


def cleanup_idle_keys(conn, tenant_id: str, now: datetime | None = None) -> dict[str, Any]:
    """여행을 하나도 안 만든 사용자 키 — 발급 · 마지막 사용 · 마지막 계획 읽기가 모두 `web.idle_key_days` 보다 오래됐으면 지운다.

    ★사용자 행은 **다른 표가 가리키지 않을 때만** 지운다(계획 읽기 등이 남아 있으면 키만 지우고 사용자 행은 둔다).
      사용자 행을 가리키는 외래키는 전부 「가리키면 거부」다(2026-09-28 `pg_constraint` 조회) — 딸려서 지워지는 데이터가 없다.
    ★지운 수 · 남긴 수를 센다(조용히 넘기지 않는다). 꺼져 있으면 아무것도 안 지운다.
    """
    limits = values(tenant_id)
    if not limits["web.idle_key_cleanup_enabled"]:
        return {"skipped": "disabled"}
    cut = _now(now) - timedelta(days=int(limits["web.idle_key_days"]))
    out = {"customers": 0, "keys_deleted": 0, "customers_deleted": 0, "customers_kept": 0}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT k.customer_id FROM web_user_keys k WHERE k.tenant_id=%s GROUP BY k.customer_id "
            "HAVING max(k.created_at) < %s AND coalesce(max(k.last_used_at), max(k.created_at)) < %s "
            "AND NOT EXISTS (SELECT 1 FROM trips t WHERE t.tenant_id=%s AND t.customer_id=k.customer_id) "
            "AND NOT EXISTS (SELECT 1 FROM trip_intakes i WHERE i.tenant_id=%s AND i.customer_id=k.customer_id "
            "                AND i.updated_at >= %s)",
            (tenant_id, cut, cut, tenant_id, tenant_id, cut))
        idle = [row[0] for row in cur.fetchall()]
    out["customers"] = len(idle)
    for customer in idle:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM web_user_keys WHERE tenant_id=%s AND customer_id=%s", (tenant_id, customer))
            out["keys_deleted"] += cur.rowcount
            try:
                with conn.transaction():          # 저장점 — 가리키는 행이 있으면 이 삭제만 되돌린다
                    cur.execute("DELETE FROM customers WHERE tenant_id=%s AND customer_id=%s", (tenant_id, customer))
                out["customers_deleted"] += cur.rowcount
            except ForeignKeyViolation:          # 계획 읽기 등이 이 사용자를 가리킨다 — 키만 지우고 사용자 행은 둔다
                out["customers_kept"] += 1
    return out


# ── 사람 확인(Cloudflare Turnstile) ────────────────────────────
class HumanCheckFailed(Exception):
    def __init__(self, reasons: list[str]) -> None:
        super().__init__(", ".join(reasons))
        self.reasons = reasons


class HumanCheckUnavailable(Exception):
    pass


def human_check_required() -> bool:
    settings = settings_module.get_settings()
    # ★새 설정 칸은 없으면 기본값으로 읽는다 — 설정을 간이 객체로 바꿔 끼우는 시험·도구가 있다(Composer 시험 19건이 깨졌다)
    return bool(getattr(settings, "turnstile_required", False)) or str(getattr(settings, "env", "")).lower() in ("prod", "production")


def assert_human_check_configured() -> None:
    """★운영에서 비밀키 없이 뜨지 않는다 — 모르게 꺼진 사람 확인이 가장 나쁘다(조립 때 부른다)."""
    if human_check_required() and not getattr(settings_module.get_settings(), "turnstile_secret", ""):
        raise RuntimeError("사람 확인이 필요한 환경인데 ACOP_TURNSTILE_SECRET 이 비어 있다 — 서버를 켜지 않는다")


Verify = Callable[..., dict[str, Any]]


def human_check(token: str | None, *, ip: str, verify: Verify | None = None) -> str:
    """`passed` · `skipped`(비밀키 없음 — 개발). 실패 `HumanCheckFailed`, Cloudflare 불통 `HumanCheckUnavailable`."""
    from app.infrastructure.turnstile import TurnstileUnavailable, siteverify

    settings = settings_module.get_settings()
    if not getattr(settings, "turnstile_secret", ""):
        assert_human_check_configured()
        return "skipped"
    guard = get_guardrails()
    token = (token or "").strip()
    if not token:
        raise HumanCheckFailed(["missing-input-response"])
    if len(token) > int(guard.get("web_guard.turnstile.max_token_chars")):
        raise HumanCheckFailed(["invalid-input-response"])
    try:
        answer = (verify or siteverify)(url=str(guard.get("web_guard.turnstile.verify_url")),
                                        secret=settings.turnstile_secret, token=token, remote_ip=ip,
                                        timeout=float(guard.get("web_guard.turnstile.timeout_seconds")))
    except TurnstileUnavailable as exc:
        raise HumanCheckUnavailable(str(exc)) from exc
    if not answer.get("success"):
        raise HumanCheckFailed([str(code) for code in answer.get("error-codes") or []] or ["unknown"])
    hosts = {h.strip() for h in (getattr(settings, "turnstile_hostnames", "") or "").split(",") if h.strip()}
    if hosts and answer.get("hostname") not in hosts:
        raise HumanCheckFailed(["hostname-mismatch"])
    return "passed"


__all__ = ["ACTIONS", "HumanCheckFailed", "HumanCheckUnavailable", "LimitSpec", "UsageRefused",
           "assert_human_check_configured", "cleanup_idle_keys", "clear_cache", "client_ip", "count",
           "count_session", "human_check", "human_check_required", "ip_token", "overrides", "prune_usage", "specs",
           "usage_today", "values"]

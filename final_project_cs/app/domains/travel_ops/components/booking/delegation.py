# -*- coding: utf-8 -*-
"""위임 범위 판정 — 자동 실행을 열어도 되는가 (v11 §12 DoD-18·19 · wiki `teams/booking-handoff.md`).

★**무엇을 「자동 실행」이라 부르는가.** 승인 뒤 적용기가 **공급자 원장을 사람 손 없이
  바꾸는 분기**다(`booking_actions.BookingCancel`). 승인은 여전히 필요하다 — v11 §4-C 를
  뒤집지 않는다(`auto_apply=False`). 승인은 "이 변경을 해도 된다" 이고, 위임은 "그 변경을
  우리가 업체 원장에 직접 반영해도 된다" 다. **문이 둘이다.**

    1) 공급자 등급  `supplier_bookings.tier == 'simulated'`   ← 017 · `require_simulated_tier`
    2) 위임 범위    금액 · 대상 종류 · 횟수 · 되돌림 조건      ← 019 · 이 모듈

★**코어는 이 판정을 모른다.** 금액·예약 종류·무료 취소 구간은 도메인 어휘다. 코어는
  적용기가 `ActionRejected` 를 내면 savepoint 를 통째로 되돌리고 `action_rejected` 로
  사람에게 넘기는 지금 구조를 그대로 쓴다(wiki `actions/approval.md` 「승인 뒤 실행」).

★**상한 값은 여기 없다.** `config/guardrails.yaml` `travel.delegation` 이 정본이다
  (RULE.md §3.1). 이 모듈은 그 값을 읽어 **비교만** 한다 — 숫자를 두 곳에 쓰지 않는다.

★**「위임이 살아 있는가」는 데이터다** — `delegations` 테이블(019). 행이 없으면 위임이
  없다. 017 의 `tier DEFAULT 'real'` 과 같은 방향이다 — 잊음의 대가가 돈인 쪽으로
  기울이지 않는다.

★**철회(DoD-19)는 「진행 중」을 어떻게 다루나.** 판정을 **제안 시점이 아니라 적용
  순간에** 한다. 적용은 한 트랜잭션이라 「반쯤 나간 자동 실행」이 존재하지 않고, 승인과
  적용 사이(사람이 누른 뒤 재개가 도는 사이)에 철회되면 적용이 열리지 않는다. 제안 둘이
  한 Case 에 있고 둘째가 철회에 걸리면 **첫째까지 되돌린다**(코어의 savepoint) — 위임이
  없는 상태에서 하나라도 원장에 남는 쪽이 더 나쁘다. 위임 행은 `FOR UPDATE` 로 잠가
  읽으므로 같은 트랜잭션 안에서 뒤집히지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping

from app.core.actions import ActionRejected
from app.core.settings import get_guardrails

#: 위임 범위를 벗어난 사유 이름. ★측정(DoD-18)이 이 이름으로 센다 — 문장을 세지 않는다.
LIMIT_DELEGATION_ABSENT = "delegation_absent"
LIMIT_DELEGATION_REVOKED = "delegation_revoked"
LIMIT_KIND = "kind_not_delegated"
LIMIT_AMOUNT_UNKNOWN = "amount_unknown"
LIMIT_PER_ACTION = "over_per_action_cap"
LIMIT_TOTAL = "over_total_cap"
LIMIT_COUNT = "over_change_count"
LIMIT_FREE_CANCELLATION = "outside_free_cancellation_window"

#: 이력(021)에 쌓이는 **행위** 이름. ★마이그레이션 021 의 CHECK 와 같은 값이어야 한다.
GRANTED = "granted"
REVOKED = "revoked"

#: 순서가 곧 판정 순서다. 앞의 것이 걸리면 뒤는 보지 않는다.
LIMITS: tuple[str, ...] = (
    LIMIT_DELEGATION_ABSENT, LIMIT_DELEGATION_REVOKED, LIMIT_KIND, LIMIT_AMOUNT_UNKNOWN,
    LIMIT_PER_ACTION, LIMIT_TOTAL, LIMIT_COUNT, LIMIT_FREE_CANCELLATION,
)


@dataclass(frozen=True)
class Scope:
    """설정에서 읽은 위임 한계. ★기본값을 코드에 두지 않는다 — 없으면 기동이 실패한다."""

    max_per_action_cents: int
    max_total_cents: int
    max_changes_per_booking: int
    kinds: tuple[str, ...]
    free_cancellation_lead_hours: int
    revert_window_hours: int

    @classmethod
    def from_guardrails(cls) -> "Scope":
        read = get_guardrails().get
        return cls(
            max_per_action_cents=int(read("travel.delegation.max_per_action_cents")),
            max_total_cents=int(read("travel.delegation.max_total_cents")),
            max_changes_per_booking=int(read("travel.delegation.max_changes_per_booking")),
            kinds=tuple(read("travel.delegation.kinds")),
            free_cancellation_lead_hours=int(read("travel.delegation.free_cancellation_lead_hours")),
            revert_window_hours=int(read("travel.delegation.revert_window_hours")),
        )


@dataclass(frozen=True)
class Decision:
    """판정 결과. ★`checks` 가 **무엇을 무엇과 비교했나**를 든다 — 결과만 남기면 검증할 수 없다."""

    allowed: bool
    #: 벗어난 한계의 이름(위 `LIMIT_*`). 범위 안이면 None
    limit: str | None
    #: 사람이 읽는 한 줄. 금액은 **원값**을 싣는다(지어내지 않는다)
    observed: str
    checks: dict[str, Any] = field(default_factory=dict)
    #: 얼마에. ★None 은 0 이 아니라 「확인되지 않았다」다
    amount_cents: int | None = None
    amount_source: str | None = None
    #: 되돌림 기한. 범위 밖이면 None(실행되지 않으므로 되돌릴 것이 없다)
    revert_deadline: datetime | None = None

    def record(self) -> dict[str, Any]:
        """`action_requests.delegation_json` 에 그대로 들어가는 근거."""
        return {"allowed": self.allowed, "limit": self.limit, "observed": self.observed,
                **self.checks}


def _delegation_row(conn: Any, *, tenant_id: str, customer_id: Any) -> dict[str, Any] | None:
    """위임 행을 **잠가서** 읽는다 — 읽은 뒤 같은 트랜잭션 안에서 철회가 끼어들지 못한다."""
    with conn.cursor() as cur:
        cur.execute("SELECT granted_at, revoked_at, revoked_by FROM delegations "
                    "WHERE tenant_id=%s AND customer_id=%s FOR UPDATE", (tenant_id, str(customer_id)))
        row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(("granted_at", "revoked_at", "revoked_by"), row))


def _spent_cents(conn: Any, *, tenant_id: str, customer_id: Any) -> int:
    """이 고객에게 **이미 나간** 자동 실행 금액 합.

    ★`delegation_json IS NOT NULL` 이 「위임을 써서 실행된 행」의 표식이다 — 인계·되돌림처럼
      위임을 쓰지 않은 작업은 여기 안 들어온다.
    ★되돌린 건을 **빼지 않는다.** 되돌림이 원장을 원래대로 돌려도 누적은 줄이지 않는다 —
      줄이면 「취소 → 되돌림」을 반복해 상한을 무한히 쓸 수 있다. 상한을 실제보다 **빨리**
      채우는 쪽이므로 틀리는 방향이 안전한 쪽이다.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(ar.amount_cents), 0) FROM action_requests ar "
                    "JOIN customer_cases c ON c.case_id = ar.case_id "
                    "WHERE ar.tenant_id=%s AND c.customer_id=%s AND ar.status='succeeded' "
                    "AND ar.delegation_json IS NOT NULL AND ar.amount_cents IS NOT NULL",
                    (tenant_id, str(customer_id)))
        return int(cur.fetchone()[0])


def _change_count(conn: Any, *, tenant_id: str, booking_id: str) -> int:
    """같은 예약에 자동 실행이 몇 번 성공했나."""
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM action_requests WHERE tenant_id=%s AND status='succeeded' "
                    "AND delegation_json IS NOT NULL AND arguments_json->>'booking_id' = %s",
                    (tenant_id, str(booking_id)))
        return int(cur.fetchone()[0])


def judge(conn: Any, *, tenant_id: str, customer_id: Any, booking: Mapping[str, Any],
          now: datetime | None = None, scope: Scope | None = None) -> Decision:
    """자동 실행이 위임 범위 안인가. **원장을 바꾸기 전에** 부른다.

    `booking` 은 이미 `FOR UPDATE` 로 잠근 예약 행이어야 한다 —
    `booking_id` · `kind` · `starts_at` · `amount_cents` 를 읽는다.
    """
    scope = scope or Scope.from_guardrails()
    now = now or datetime.now(UTC)
    booking_id = str(booking["booking_id"])
    kind = booking.get("kind")
    amount = booking.get("amount_cents")
    starts_at = booking.get("starts_at")
    free_until = (starts_at - timedelta(hours=scope.free_cancellation_lead_hours)
                  if starts_at is not None else None)
    checks: dict[str, Any] = {
        "booking_id": booking_id, "kind": kind,
        "amount_cents": amount, "kinds_allowed": list(scope.kinds),
        "max_per_action_cents": scope.max_per_action_cents,
        "max_total_cents": scope.max_total_cents,
        "max_changes_per_booking": scope.max_changes_per_booking,
        "free_cancellation_until": free_until.isoformat() if free_until else None,
        "judged_at": now.isoformat(),
    }

    def no(limit: str, observed: str) -> Decision:
        return Decision(allowed=False, limit=limit, observed=observed, checks=checks)

    row = _delegation_row(conn, tenant_id=tenant_id, customer_id=customer_id)
    if row is None:
        # ★행이 없으면 위임이 없다. 「아직 안 적었을 뿐」로 해석하지 않는다.
        return no(LIMIT_DELEGATION_ABSENT, "이 고객의 위임 기록이 없다 — 자동 실행 대상이 아니다")
    checks["granted_at"] = row["granted_at"].isoformat() if row["granted_at"] else None
    if row["revoked_at"] is not None and row["revoked_at"] <= now:
        checks["revoked_at"] = row["revoked_at"].isoformat()
        return no(LIMIT_DELEGATION_REVOKED,
                  f"위임이 {row['revoked_at'].isoformat()} 에 철회됐다"
                  + (f" (철회자 {row['revoked_by']})" if row["revoked_by"] else ""))

    if kind not in scope.kinds:
        return no(LIMIT_KIND, f"예약 종류 {kind!r} 는 위임 대상이 아니다 — 위임된 종류: {list(scope.kinds)}")

    if amount is None:
        # ★금액을 모르면 상한 안이라고 **단정할 수 없다.** 모름을 0 으로 읽지 않는다.
        return no(LIMIT_AMOUNT_UNKNOWN, "예약 금액이 확인되지 않았다 — 상한 안인지 판정할 수 없다")
    amount = int(amount)
    if amount > scope.max_per_action_cents:
        return no(LIMIT_PER_ACTION, f"건당 상한 초과: {amount} > {scope.max_per_action_cents}(전)")

    spent = _spent_cents(conn, tenant_id=tenant_id, customer_id=customer_id)
    checks["spent_cents"] = spent
    if spent + amount > scope.max_total_cents:
        return no(LIMIT_TOTAL, f"누적 상한 초과: 이미 {spent} + 이번 {amount} > {scope.max_total_cents}(전)")

    count = _change_count(conn, tenant_id=tenant_id, booking_id=booking_id)
    checks["changes_so_far"] = count
    if count >= scope.max_changes_per_booking:
        return no(LIMIT_COUNT, f"같은 예약 자동 실행 횟수 초과: 이미 {count}회 >= {scope.max_changes_per_booking}회")

    if free_until is None or free_until <= now:
        # ★되돌릴 수 없는 것을 사람 손 없이 하지 않는다(wiki 「되돌림 조건 — 무료 취소 구간 안에서만」).
        return no(LIMIT_FREE_CANCELLATION,
                  f"무료 취소 구간이 아니다 — 구간 끝 {free_until.isoformat() if free_until else '확인되지 않았다'}")

    # 되돌림 기한은 **이른 쪽**이다. 창을 넉넉히 줘도 무료 취소 구간을 넘길 수 없다.
    deadline = min(now + timedelta(hours=scope.revert_window_hours), free_until)
    checks["revert_deadline"] = deadline.isoformat()
    return Decision(allowed=True, limit=None,
                    observed=f"위임 범위 안 — {amount}(전) · 종류 {kind} · 누적 {spent} · {count}회째",
                    checks=checks, amount_cents=amount, amount_source="bookings.amount_cents",
                    revert_deadline=deadline)


def require(conn: Any, *, tenant_id: str, customer_id: Any, booking: Mapping[str, Any],
            now: datetime | None = None, scope: Scope | None = None) -> Decision:
    """범위 밖이면 `ActionRejected` — 코어가 전부 되돌리고 사람에게 넘긴다.

    ★`ActionRejected` 를 쓰는 이유는 「대상이 그새 바뀐 것」(`ActionConflict`)이 아니기
      때문이다. 위임 범위 밖인 건은 **다시 시도해도 범위 밖**이다 — 재계산으로 풀리지 않는다.
    """
    decision = judge(conn, tenant_id=tenant_id, customer_id=customer_id, booking=booking,
                     now=now, scope=scope)
    if not decision.allowed:
        raise ActionRejected(f"delegation {decision.limit}: {decision.observed} "
                             f"(v11 §12 DoD-18 · wiki teams/booking-handoff.md 「위임 범위」)")
    return decision


def _record(conn: Any, *, tenant_id: str, customer_id: Any, action: str,
            actor: str | None, note: str | None) -> None:
    """이력 한 줄을 **덧붙인다**(021, append-only).

    ★`delegations` 한 행은 **지금 상태**만 든다 — 다시 주면 `ON CONFLICT DO UPDATE` 가
      `revoked_at`·`revoked_by` 를 지운다. 「주기 → 거두기 → 다시 주기」를 하면 누가 언제
      거뒀는지가 덮여 사라지므로, 상태를 바꾼 **행위**를 따로 쌓는다.
    """
    with conn.cursor() as cur:
        cur.execute("INSERT INTO delegation_events (tenant_id, customer_id, action, actor_id, note) "
                    "VALUES (%s,%s,%s,%s,%s)", (tenant_id, str(customer_id), action, actor, note))


def grant(conn: Any, *, tenant_id: str, customer_id: Any, by: str | None = None,
          note: str | None = None) -> None:
    """위임을 준다(다시 주면 철회를 지운다). 시연·시험·운영 도구가 쓴다."""
    with conn.cursor() as cur:
        cur.execute("INSERT INTO delegations (tenant_id, customer_id, granted_by, note) "
                    "VALUES (%s,%s,%s,%s) ON CONFLICT (tenant_id, customer_id) DO UPDATE "
                    "SET granted_at=now(), revoked_at=NULL, revoked_by=NULL, "
                    "granted_by=EXCLUDED.granted_by, note=EXCLUDED.note",
                    (tenant_id, str(customer_id), by, note))
    _record(conn, tenant_id=tenant_id, customer_id=customer_id, action=GRANTED, actor=by, note=note)


def revoke(conn: Any, *, tenant_id: str, customer_id: Any, by: str | None = None,
           note: str | None = None, at: datetime | None = None) -> bool:
    """위임을 철회한다. ★행을 **지우지 않는다** — 언제 누가 거뒀는지가 남아야 한다.

    돌려주는 값은 「철회할 위임이 있었나」다. 없었으면 False — 이미 자동 실행이 막힌
    상태이므로 오류가 아니다. 다만 **조용히 True 라고 하지 않는다.**

    ★이력(021)은 **실제로 거둔 때만** 쌓는다. 거둘 것이 없었는데 「거뒀다」를 남기면
      이력이 거짓이 된다.
    """
    with conn.cursor() as cur:
        cur.execute("UPDATE delegations SET revoked_at=COALESCE(%s, now()), revoked_by=%s, "
                    "note=COALESCE(%s, note) WHERE tenant_id=%s AND customer_id=%s "
                    "AND revoked_at IS NULL",
                    (at, by, note, tenant_id, str(customer_id)))
        changed = cur.rowcount > 0
    if changed:
        _record(conn, tenant_id=tenant_id, customer_id=customer_id, action=REVOKED,
                actor=by, note=note)
    return changed


# ── 읽기 — 운영 화면·API 가 쓰는 자리 ────────────────────────────────────────
#: ★`delegations` 한 행이 답하는 것은 셋뿐이다 — 있다 / 살아 있다 / 거뒀다.
STATE_ABSENT = "absent"
STATE_LIVE = "live"
STATE_REVOKED = "revoked"


def _state_of(row: Mapping[str, Any] | None) -> str:
    if row is None:
        return STATE_ABSENT
    return STATE_REVOKED if row.get("revoked_at") is not None else STATE_LIVE


def spent_cents(conn: Any, *, tenant_id: str, customer_id: Any) -> int:
    """이 고객에게 **이미 나간** 자동 실행 금액 합. 판정이 쓰는 것과 **같은 셈**이다."""
    return _spent_cents(conn, tenant_id=tenant_id, customer_id=customer_id)


def listing(conn: Any, *, tenant_id: str) -> list[dict[str, Any]]:
    """테넌트의 위임 전부 — 살아 있는 것이 위로. 누적 사용액을 함께 센다.

    ★누적은 판정(`_spent_cents`)과 **같은 조건**으로 센다 — 화면의 수와 게이트의 수가
      갈라지면 운영자가 본 것이 판정의 근거가 아니게 된다.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT d.customer_id, d.granted_at, d.revoked_at, d.granted_by, d.revoked_by, d.note, "
            "COALESCE((SELECT SUM(ar.amount_cents) FROM action_requests ar "
            "          JOIN customer_cases c ON c.case_id = ar.case_id "
            "          WHERE ar.tenant_id = d.tenant_id AND c.customer_id = d.customer_id "
            "            AND ar.status='succeeded' AND ar.delegation_json IS NOT NULL "
            "            AND ar.amount_cents IS NOT NULL), 0) AS spent_cents "
            "FROM delegations d WHERE d.tenant_id=%s "
            "ORDER BY (d.revoked_at IS NOT NULL), d.granted_at DESC", (tenant_id,))
        keys = ("customer_id", "granted_at", "revoked_at", "granted_by", "revoked_by", "note",
                "spent_cents")
        rows = [dict(zip(keys, row)) for row in cur.fetchall()]
    for row in rows:
        row["state"] = _state_of(row)
    return rows


def state(conn: Any, *, tenant_id: str, customer_id: Any) -> dict[str, Any]:
    """한 고객의 지금 상태 + 누적 사용액. ★행이 없으면 `absent` — 「모름」이 아니다."""
    with conn.cursor() as cur:
        cur.execute("SELECT granted_at, revoked_at, granted_by, revoked_by, note FROM delegations "
                    "WHERE tenant_id=%s AND customer_id=%s", (tenant_id, str(customer_id)))
        row = cur.fetchone()
    found = None if row is None else dict(
        zip(("granted_at", "revoked_at", "granted_by", "revoked_by", "note"), row))
    out: dict[str, Any] = {"customer_id": str(customer_id), "state": _state_of(found),
                           "granted_at": None, "revoked_at": None, "granted_by": None,
                           "revoked_by": None, "note": None}
    out.update(found or {})
    out["spent_cents"] = spent_cents(conn, tenant_id=tenant_id, customer_id=customer_id)
    return out


def history(conn: Any, *, tenant_id: str, customer_id: Any, limit: int = 50) -> list[dict[str, Any]]:
    """누가·언제·왜 주고 거뒀나(021). 최신이 위."""
    with conn.cursor() as cur:
        cur.execute("SELECT action, actor_id, note, at FROM delegation_events "
                    "WHERE tenant_id=%s AND customer_id=%s ORDER BY seq DESC LIMIT %s",
                    (tenant_id, str(customer_id), int(limit)))
        return [dict(zip(("action", "actor_id", "note", "at"), row)) for row in cur.fetchall()]


__all__ = ["Decision", "GRANTED", "LIMITS", "LIMIT_AMOUNT_UNKNOWN", "LIMIT_COUNT",
           "LIMIT_DELEGATION_ABSENT", "LIMIT_DELEGATION_REVOKED", "LIMIT_FREE_CANCELLATION",
           "LIMIT_KIND", "LIMIT_PER_ACTION", "LIMIT_TOTAL", "REVOKED", "STATE_ABSENT",
           "STATE_LIVE", "STATE_REVOKED", "Scope", "grant", "history", "judge", "listing",
           "require", "revoke", "spent_cents", "state"]

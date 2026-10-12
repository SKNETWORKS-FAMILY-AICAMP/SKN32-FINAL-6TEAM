"""합성 철도 패스·승차권 정책을 같은 검증 엔진에 주입한다.

실제 제품의 패스 기능 구현이나 모든 산업의 범용성을 증명하지 않는다.
기존 여행 예약 정책과 다른 참조·금액·인원 상한을 처리하는지만 검사한다.
원본 시험은 legacy/commerce_cleanup_2026-10-11/에 보존했다.
"""
from __future__ import annotations

from decimal import Decimal

from app.core.verification import (Facts, QuantityRule, VerificationPolicy,
                                   verify_proposal)

RAIL_PASS_POLICY = VerificationPolicy(
    references={"rail_pass_id": "rail_passes", "ticket_id": "tickets"},
    quantities=(
        QuantityRule(field="fare_refund", reference="rail_pass_id",
                     limit_key="paid_cents", scale=Decimal(100)),
        QuantityRule(field="travelers", reference="rail_pass_id",
                     limit_key="seat_limit", scale=Decimal(1)),
    ),
    opaque=frozenset({"park_permit_id"}),          # 아직 대조 수단이 없다
    ignored=frozenset({"reason", "memo"}),
)

PASS = "pass-1001"
TICKET = "ticket-77"


def rail_pass_facts(**over) -> Facts:
    base = dict(
        collections={
            "rail_passes": {PASS: {"rail_pass_id": PASS, "paid_cents": 5_000_000, "seat_limit": 3}},
            "tickets": {TICKET: {"ticket_id": TICKET, "status": "issued"}},
        },
        evidence_ids=frozenset({"rail-evidence-1"}),
    )
    base.update(over)
    return Facts(**base)


def check(**kwargs):
    kwargs.setdefault("policy", RAIL_PASS_POLICY)
    kwargs.setdefault("rationale_evidence_ids", ["rail-evidence-1"])
    kwargs.setdefault("facts", rail_pass_facts())
    return verify_proposal(**kwargs)


def fields(problems) -> set[str]:
    return {p.field for p in problems}


def test_declared_pass_identifier_is_verified():
    """선언된 패스 식별자를 여행 예약 정책과 별개로 확인한다."""
    assert check(arguments={"rail_pass_id": PASS}) == []


# invariant: INV-CS-VER-001
def test_unknown_pass_is_rejected():
    assert "rail_pass_id" in fields(check(arguments={"rail_pass_id": "pass-does-not-exist"}))


# invariant: INV-CS-VER-002
def test_refund_over_the_pass_payment_is_rejected():
    """5만원 결제한 철도 패스에 7만원 환급 제안이면 거부한다."""
    problems = check(arguments={"rail_pass_id": PASS, "fare_refund": 70_000})
    assert "fare_refund" in fields(problems)


# invariant: INV-CS-VER-003
def test_partial_refund_passes():
    assert check(arguments={"rail_pass_id": PASS, "fare_refund": 20_000}) == []


# invariant: INV-CS-VER-004
def test_travelers_over_the_seat_limit_are_rejected():
    """★수량 규칙이 금액 전용이 아니다 — 같은 엔진이 개수도 잰다."""
    assert "travelers" in fields(
        check(arguments={"rail_pass_id": PASS, "travelers": 5}))


# invariant: INV-CS-VER-005
def test_travelers_within_the_seat_limit_pass():
    assert check(arguments={"rail_pass_id": PASS, "travelers": 2}) == []


# invariant: INV-CS-VER-006
def test_ticket_ownership_is_checked():
    assert check(arguments={"ticket_id": TICKET}) == []
    assert "ticket_id" in fields(check(arguments={"ticket_id": "ticket-other"}))


# invariant: INV-CS-VER-007
def test_this_domains_opaque_field_is_rejected():
    """대조 수단이 선언되지 않은 공원 허가증은 거부한다."""
    assert "park_permit_id" in fields(check(arguments={"park_permit_id": "permit-1"}))


def test_undeclared_travel_field_is_rejected():
    """다른 여행 기능의 식별자도 정책에 선언되지 않았으면 거부한다."""
    problems = check(arguments={"hotel_stay_id": "stay-1", "nights": 2})
    assert "hotel_stay_id" in fields(problems)
    assert any("선언되지 않은" in p.reason for p in problems)


# invariant: INV-CS-ARCH-005
def test_engine_source_has_no_domain_vocabulary():
    """같은 엔진이 정책별 여행 필드를 직접 분기하지 않는지 확인한다."""
    from pathlib import Path
    source = Path("app/core/verification.py").read_text(encoding="utf-8")
    for word in ("rail_pass_id", "ticket_id", "hotel_stay_id", "fare_refund", "paid_cents"):
        # 주석·docstring 제외한 실행부에 없어야 한다
        code = "\n".join(line for line in source.splitlines()
                         if not line.strip().startswith(("#", "★", '"""')))
        assert word not in code, f"엔진에 도메인 어휘 '{word}' 가 있다"

def test_policy_changes_control_the_verdict_without_engine_changes():
    from app.domains.travel_ops.components.core_hooks.verification_policy import TRAVEL_OPS_POLICY
    assert set(RAIL_PASS_POLICY.references).isdisjoint(TRAVEL_OPS_POLICY.references)
    facts = rail_pass_facts(collections={"rail_passes": {PASS: {"paid_cents": 1_000_000, "seat_limit": 1}}})
    assert "fare_refund" in fields(check(arguments={"rail_pass_id": PASS, "fare_refund": 20_000}, facts=facts))
    assert "travelers" in fields(check(arguments={"rail_pass_id": PASS, "travelers": 2}, facts=facts))
    assert check(arguments={"rail_pass_id": PASS, "fare_refund": 20_000, "travelers": 2}) == []

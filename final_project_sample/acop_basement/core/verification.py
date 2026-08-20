"""제안을 사실과 대조하는 **범용 규칙 엔진** (v7 §9-E).

★이 파일은 basement 다. **어떤 업무 도메인도 몰라야 한다.**

  처음엔 구독·결제 도메인의 필드 이름을 여기 박아 뒀다.
  v7 §9-E 표가 그 필드들을 **예시로** 든 것을 스펙으로 잘못 읽은 탓이다.
  그 결과 **다른 도메인으로 복사하면 그 도메인의 핵심 식별자가
  basement 의 "확인 불가 → 자동 거부" 목록에 걸렸다.** 정확히 거꾸로다.

  지금은 **규칙만** 여기 있고, 필드 이름은 도메인이 선언한다(`VerificationPolicy`).

규칙 세 가지:
  1. 참조(reference) — 선언된 컬렉션에 그 id 가 실재해야 한다
  2. 수량(quantity) — 참조 대상의 상한을 넘을 수 없고 0 이하일 수 없다
  3. 확인 불가(opaque) — 대조할 수단이 없는 필드는 **거부**한다.
     "확인 못 함" 을 "괜찮음" 으로 바꾸지 않는다(설계 원칙 §0.1)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


def digest(value: Any) -> str:
    """감사 로그용 짧은 해시.

    ★기대값·실제값을 **원문으로 남기지 않는다.** 금액·식별자가 감사 로그에
      그대로 들어가면 설계 원칙 §1 을 어긴다.
    """
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Mismatch:
    """대조 실패 한 건. 무엇이 왜 틀렸는지 남긴다."""

    field: str
    reason: str
    expected_digest: str
    actual_digest: str

    def as_audit(self) -> dict[str, str]:
        return {"field": self.field, "reason": self.reason,
                "expected_digest": self.expected_digest, "actual_digest": self.actual_digest}


@dataclass(frozen=True)
class QuantityRule:
    """수량 필드 하나의 검사 규칙.

    `field`      제안에 나오는 수량 키
    `reference`  상한을 가진 대상을 가리키는 키
    `limit_key`  그 대상 레코드에서 상한을 담은 컬럼
    `scale`      제안 값에 곱해 상한과 같은 단위로 맞추는 배수 (원→cents 면 100)

    ★예시는 도메인 선언 파일에 있다. basement 는 예시로도 특정 도메인을 쓰지 않는다.
    """

    field: str
    reference: str
    limit_key: str
    scale: Decimal = Decimal(1)


@dataclass(frozen=True)
class VerificationPolicy:
    """★도메인이 선언하는 대조 규칙. basement 는 이 선언을 **읽을 뿐** 만들지 않는다.

    `references`  제안 키 → 사실 컬렉션 이름
    `quantities`  수량 규칙 목록
    `opaque`      대조 수단이 없는 키 — 나오면 거부한다
    `ignored`     대조 대상이 아닌 키 (자유 텍스트 등)
    """

    references: Mapping[str, str] = field(default_factory=dict)
    quantities: tuple[QuantityRule, ...] = ()
    opaque: frozenset[str] = frozenset()
    ignored: frozenset[str] = frozenset()

    @property
    def quantity_fields(self) -> frozenset[str]:
        return frozenset(rule.field for rule in self.quantities)


@dataclass
class Facts:
    """도메인이 재조회해 넘기는 사실.

    ★컬렉션 이름은 **선언에서 온다.** 여기에 `payments` 같은 필드를 두지 않는다 —
      그러면 basement 가 그 도메인만 알게 된다.

    ★`loaded` 는 "조회했는데 없다" 와 "조회 자체가 실패했다" 를 가른다.
      후자를 전자로 읽으면 **없는 사실을 단정**하게 된다.
    """

    collections: dict[str, Mapping[str, Mapping[str, Any]]] = field(default_factory=dict)
    evidence_ids: frozenset[str] = frozenset()
    loaded: bool = True

    def records(self, name: str) -> Mapping[str, Mapping[str, Any]]:
        return self.collections.get(name, {})


def _to_decimal(value: Any) -> Decimal | None:
    """★`Decimal("NaN")`/`Decimal("Infinity")` 는 예외 없이 만들어진다 — 그런데
    이후 비교(`>`)나 `int()` 변환에서 각각 `InvalidOperation`/`OverflowError` 를
    던진다. 검증 함수 자체가 죽으면 "확인 불가 → 거부" 가 아니라 500 이 된다 —
    방어선이 없는 것과 같다(버그사냥 2026-08-17, verification.py:106 대상).
    비유한 수만 통과시킨다."""
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return decimal_value if decimal_value.is_finite() else None


def verify_proposal(
    *,
    arguments: Mapping[str, Any],
    rationale_evidence_ids: list[str],
    facts: Facts,
    policy: VerificationPolicy,
) -> list[Mismatch]:
    """제안을 사실과 대조하고 **불일치 목록**을 돌려준다. 빈 목록이면 통과다.

    ★예외를 던지지 않는다. 호출자가 전부 모아 감사 로그에 남길 수 있어야 한다 —
      첫 번째에서 멈추면 나머지 문제를 다음 라운드에나 발견한다.
    """
    problems: list[Mismatch] = []

    # ★조회 자체가 실패했으면 통과시키지 않는다. 사실을 모르는 상태다.
    if not facts.loaded:
        return [Mismatch("__facts__", "사실 조회 실패 — 대조할 수 없다",
                         digest("loaded"), digest("not_loaded"))]

    known = set(policy.references) | policy.quantity_fields | policy.opaque | policy.ignored

    for key, value in arguments.items():
        if value is None or key in policy.ignored or key in policy.quantity_fields:
            continue

        # 1) 대조 수단이 없는 필드 — 확인 못 하면 거부한다
        if key in policy.opaque:
            problems.append(Mismatch(
                key, "이 시스템에 대응 데이터가 없어 확인할 수 없다", digest("verifiable"), digest(value)))
            continue

        # 2) 참조 — 실재·소유권. 사실은 tenant/customer 범위로만 조회된다
        collection = policy.references.get(key)
        if collection is not None:
            if str(value) not in facts.records(collection):
                problems.append(Mismatch(
                    key, f"{collection} 에 이 고객 소유의 행이 없다", digest("exists"), digest(value)))
            continue

        # 3) ★선언에 없는 키. 모르는 것을 통과시키지 않는다 —
        #    새 필드가 조용히 들어와 검사 없이 실행되는 것을 막는다.
        if key not in known:
            problems.append(Mismatch(
                key, "선언되지 않은 필드다 — 검사 규칙이 없으면 실행하지 않는다",
                digest("declared"), digest(key)))

    problems.extend(_verify_quantities(arguments, facts, policy))

    # 4) 근거 id — ContextPack 에 실재하는 evidence 여야 한다
    for evidence_id in sorted(set(rationale_evidence_ids) - facts.evidence_ids):
        problems.append(Mismatch(
            "evidence_ids", "ContextPack 에 없는 근거를 든다", digest("in_context"), digest(evidence_id)))

    return problems


def _verify_quantities(arguments: Mapping[str, Any], facts: Facts,
                       policy: VerificationPolicy) -> list[Mismatch]:
    """수량이 참조 대상의 상한을 넘지 않는지 본다.

    ★수량만 있고 참조 대상이 없으면 거부한다 — 무엇에 대한 수량인지 모르면 확인할 수 없다.
    """
    problems: list[Mismatch] = []
    for rule in policy.quantities:
        if rule.field not in arguments or arguments[rule.field] is None:
            continue

        reference_value = arguments.get(rule.reference)
        if reference_value is None:
            problems.append(Mismatch(
                rule.field, f"대상({rule.reference})이 없어 값을 확인할 수 없다",
                digest(rule.reference), digest(None)))
            continue

        collection = policy.references.get(rule.reference)
        record = facts.records(collection or "").get(str(reference_value)) if collection else None
        if record is None:
            continue  # 실재 검사에서 이미 잡혔다 — 같은 문제를 두 번 세지 않는다

        proposed = _to_decimal(arguments[rule.field])
        if proposed is None:
            problems.append(Mismatch(rule.field, "값이 숫자가 아니다",
                                     digest("number"), digest(arguments[rule.field])))
            continue

        limit = _to_decimal(record.get(rule.limit_key))
        if limit is None:
            problems.append(Mismatch(rule.field, f"대상에 {rule.limit_key} 가 없어 상한을 모른다",
                                     digest(rule.limit_key), digest(None)))
            continue

        scaled = proposed * rule.scale
        if scaled > limit:
            problems.append(Mismatch(rule.field, "실제 값보다 큰 값을 제안했다",
                                     digest(limit), digest(int(scaled))))
        elif scaled <= 0:
            problems.append(Mismatch(rule.field, "0 이하 값은 제안할 수 없다",
                                     digest("positive"), digest(int(scaled))))
    return problems

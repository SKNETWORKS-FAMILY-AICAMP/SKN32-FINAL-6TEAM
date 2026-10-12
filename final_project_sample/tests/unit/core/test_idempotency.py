"""idempotency_key() 가 필드 경계를 실제로 지키는지 검사한다.

★버그사냥 2026-08-17 — 구분자 없는 문자열 결합은 서로 다른 논리 요청을
같은 key 로 만들 수 있다: ("ab","c") 와 ("a","bc") 는 둘 다 "abc" 다.
"""
from __future__ import annotations

from acop_basement.core.idempotency import idempotency_key


def test_field_boundary_shift_does_not_collide():
    a = idempotency_key(tenant_id="ab", request_id="c", action_type="d", business_subject="e")
    b = idempotency_key(tenant_id="a", request_id="bc", action_type="d", business_subject="e")
    assert a != b, "필드 경계가 다른 두 입력이 같은 key 를 냈다"


def test_same_input_is_still_deterministic():
    kwargs = dict(tenant_id="t1", request_id="r1", action_type="case.create", business_subject="c1:hello")
    assert idempotency_key(**kwargs) == idempotency_key(**kwargs)


def test_key_length_is_a_single_sha256_hexdigest():
    key = idempotency_key(tenant_id="t", request_id="r", action_type="a", business_subject="s")
    assert len(key) == 64
    int(key, 16)  # ★hex 가 아니면 여기서 ValueError

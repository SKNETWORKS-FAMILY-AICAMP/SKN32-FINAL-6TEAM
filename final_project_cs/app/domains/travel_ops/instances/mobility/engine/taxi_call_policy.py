"""서울 즉시호출의 플랫폼 이용료 범위와 호출자가 확인한 사전 견적.

``depart``는 datetime이며 naive 값은 기존 엔진과 같이 KST로 해석합니다.
카탈로그의 서울 범위를 다른 지역·예약 상품에 적용하면 안 됩니다.

``quoted_fee``는 기존 normalize_fees의 정확한6필드(from,to,fee_won,
valid_from,valid_until,source)에 quoted_at을 더한 dict입니다. 시각3개는
오프셋 있는 ISO 문자열이며 quoted_at <= valid_from <= depart < valid_until,
quoted_at <= 현재시각을 만족해야 합니다. 유효기간은 호출자가 확인한 범위이며
공급자가 보장한 TTL이 아닙니다. source는 자유 식별자이므로 이 검사로 공급자
진위·해당 상품·구간 일치를 인증하지 않습니다. 호출부에서 선택 구간과 상품을
맞춰야 합니다. actual_fee_known은 입력된 옵션료가 있다는 뜻이며 미터/통행료를
포함한 최종 결제액 보장이 아닙니다. API·앱 호출이나 현재 위치 조회는 없습니다.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from .errors import CaseInputError
from .taxi_budget import aware_time, normalize_fees

KST = timezone(timedelta(hours=9))
_QUOTE_KEYS = {"from", "to", "fee_won", "valid_from", "valid_until", "source", "quoted_at"}


def _now_kst():
    """시험에서 교체 가능한 실제 현재시각. 공급자 견적 유효시간은 만들지 않습니다."""
    return datetime.now(KST)


def _kst(value):
    if not isinstance(value, datetime):
        raise CaseInputError("택시 호출료 출발시각은 datetime이어야 합니다")
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=KST)
    try:
        return value.astimezone(KST)
    except (ValueError, OverflowError) as exc:
        raise CaseInputError("택시 호출료 시각을 KST로 변환할 수 없습니다") from exc


@lru_cache(maxsize=1)
def _catalog():
    path = Path(__file__).with_name("rules") / "taxi_call_policies_v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def validate_quoted_fee(value, depart):
    """7필드 사전견적을 검사하여 원본과 분리된 dict를 반환합니다.

    유효기간은 시작 포함·끝 제외. 사후 영수증을 quoted_at 없이 사전견적으로
    승격하지 않습니다. 과거의 quoted_at을 사용자가 허위로 쓰는 것까지 탐지하는
    공급자 서명 검증은 아니므로 상품·구간 선택의 책임은 호출부에 있습니다.
    """
    depart = _kst(depart)
    if not isinstance(value, dict) or set(value) != _QUOTE_KEYS:
        raise CaseInputError("택시 사전 견적은 기존6필드와 quoted_at이 정확히 필요합니다")
    base = normalize_fees([{k: v for k, v in value.items() if k != "quoted_at"}])[0]
    quoted_at = aware_time(value["quoted_at"])
    start, end = aware_time(base["valid_from"]), aware_time(base["valid_until"])
    if not quoted_at <= start <= depart < end:
        raise CaseInputError("택시 사전 견적 시각·유효기간이 출발시각과 맞지 않습니다")
    if quoted_at > _now_kst():
        raise CaseInputError("미래에 확인한 택시 견적을 사전 입력할 수 없습니다")
    base["quoted_at"] = value["quoted_at"]
    return base


def resolve_call_fee(product_id, depart, *, quoted_fee=None):
    """사전 플랫폼료 범위를 반환합니다. 예약·임의 상품은 견적이 있어도 거절합니다."""
    depart = _kst(depart)
    catalog = _catalog()
    if not isinstance(product_id, str) or product_id not in (
        set(catalog["products"]) | set(catalog["quote_only_products"])
    ):
        raise CaseInputError("지원 밖 택시 상품입니다. 해당 상품의 별도 사전 견적 경로가 필요합니다")
    policy = catalog["products"].get(product_id)
    if quoted_fee is not None:
        quote = validate_quoted_fee(quoted_fee, depart)
        if product_id == "kakao_general" and quote["fee_won"] != 0:
            raise CaseInputError("일반호출 플랫폼 이용료는0원입니다. 견적 상품을 다시 확인해 주세요")
        if policy is not None:
            minute=depart.hour*60+depart.minute
            period=next(p for p in policy['periods'] if p['start_minute']<=minute<p['end_minute'])
            if not period['minimum_won']<=quote['fee_won']<=period['maximum_won']:
                raise CaseInputError('사전 견적이 선택한 즉시호출 상품의 공식 시간대 범위를 넘습니다')
        return {
            "product_id": product_id,
            "minimum_won": quote["fee_won"], "maximum_won": quote["fee_won"],
            "basis": (f"호출자 확인 사전 앱 견적 플랫폼 이용료; 출처:{quote['source']}; "
                      "유효기간은 호출자가 확인한 범위(공식 TTL 미확인); 상품·구간·출처 진위 인증 아님"),
            "source_url": None,
            "actual_fee_known": True,
        }
    if policy is None:
        raise CaseInputError("이 브랜드는 확인된 사전 앱 견적이 필요합니다")
    minute = depart.hour * 60 + depart.minute
    for period in policy["periods"]:
        if period["start_minute"] <= minute < period["end_minute"]:
            return {
                "product_id": product_id,
                "minimum_won": period["minimum_won"], "maximum_won": period["maximum_won"],
                "basis": (f"서울 즉시호출 플랫폼 이용료 사전 범위; 확인일:{catalog['checked_on']}; "
                          f"{policy['verification_note']} {catalog['time_axis_note']}"),
                "source_url": policy["source_url"], "actual_fee_known": False,
            }
    raise CaseInputError("택시 호출료 카탈로그 시간대가 출발시각을 포함하지 않습니다")

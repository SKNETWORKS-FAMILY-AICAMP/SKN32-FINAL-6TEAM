"""등록 전 웹 입력의 택시 상품 계약. 실제 요율 계산은 이동 팀에 맡긴다."""
from copy import deepcopy
import json


# 마이캡 공식 승객약관 제9조, 시행2025-03-05/관측2026-10-12.
# https://www.blackpin.co.kr/?mode=policy — 과거 이용 당시 버전 확정 근거는 아니다.
PRODUCTS = frozenset({"kakao_general", "km_blue_immediate", "turu_blue_immediate", "capsi_immediate", "mycap_immediate"})


def default():
    return {"product": "kakao_general", "quotes": []}


def normalize(value):
    """웹 첫 판은 공식 범위가 있는 상품과 빈 견적 목록만 받는다."""
    if not isinstance(value, dict) or set(value) != {"product", "quotes"}:
        raise ValueError("택시 조건은 product와 quotes 두 칸이 필요합니다")
    if not isinstance(value["product"], str) or value["product"] not in PRODUCTS:
        raise ValueError("웹에서 지원하지 않는 택시 호출 상품입니다")
    if not isinstance(value["quotes"], list) or value["quotes"]:
        raise ValueError("웹에서는 사전 견적 입력을 지원하지 않습니다. quotes는 빈 목록이어야 합니다")
    return deepcopy(value)


def from_trip(trip):
    claim = trip.get("taxi_pricing")
    return normalize(claim.get("value")) if claim is not None else None


def constraints(value, base=None):
    """기존 설문·복구 제약을 보존하며 검증한 웹 상품만 더한다."""
    result = deepcopy(base or {})
    if value is not None:
        value = normalize(value)
        if "taxi_option_fees" in result:
            raise ValueError("기존 택시 옵션료와 웹 호출 상품을 함께 적용할 수 없습니다")
        result.update(taxi_call_product=value["product"], taxi_call_quotes=value["quotes"])
    return result


def signature(value):
    return "" if value is None else "#taxi=" + json.dumps(normalize(value), sort_keys=True, separators=(",", ":"))

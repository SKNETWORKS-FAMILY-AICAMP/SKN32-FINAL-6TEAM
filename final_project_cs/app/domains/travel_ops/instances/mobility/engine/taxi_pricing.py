"""사전에 선택한 즉시호출 상품과 같은 구간 견적을 제품 예산에 연결한다."""
from copy import deepcopy

from .errors import CaseInputError
from .taxi_budget import normalize_fees


def normalize_call_quotes(values):
    if values is None:
        return ()
    if not isinstance(values,(list,tuple)):
        raise CaseInputError('택시 사전 견적은 구간별 목록이어야 합니다')
    out=[]
    for value in values:
        keys={'from','to','fee_won','valid_from','valid_until','source','quoted_at'}
        if not isinstance(value,dict) or set(value)!=keys:
            raise CaseInputError('택시 사전 견적은 기존6필드와 quoted_at이 필요합니다')
        base={k:v for k,v in value.items() if k!='quoted_at'}
        normalize_fees([base])
        from .taxi_budget import aware_time
        if aware_time(value['quoted_at'])>aware_time(value['valid_from']):
            raise CaseInputError('견적 확인시각이 유효 시작보다 뒤입니다')
        out.append(deepcopy(value))
    normalize_fees([{k:v for k,v in value.items() if k!='quoted_at'} for value in out])
    return tuple(out)


def quote_for_route(values,origin,destination):
    for value in values:
        if (value['from'],value['to'])==(origin.get('key'),destination.get('key')):
            return deepcopy(value)
    return None


def matches_current_pricing(option,constraints,origin,destination):
    """현재 여행에서 바꾼 상품·견적을 예전 저장 가격으로 안내하지 않는다."""
    if not isinstance(constraints,dict):
        raise CaseInputError('현재 택시 조건은 객체여야 합니다')
    legacy=constraints.get('taxi_option_fees')
    product=constraints.get('taxi_call_product')
    quotes=constraints.get('taxi_call_quotes')
    if legacy is not None:
        if product is not None or quotes is not None:
            raise CaseInputError('기존 옵션료와 새 호출 상품·견적을 함께 적용할 수 없습니다')
        selected=quote_for_route(normalize_fees(legacy),origin,destination)
        return ('taxi_call_product' not in option and 'taxi_call_quote' not in option
                and option.get('taxi_option_fee')==selected)
    product='kakao_general' if product is None else product
    selected=quote_for_route(normalize_call_quotes(quotes),origin,destination)
    return ('taxi_option_fee' not in option and option.get('taxi_call_product')==product
            and option.get('taxi_call_quote')==selected)


def with_call_product(model,product_id,depart,quoted_fee=None):
    from .taxi_call_policy import resolve_call_fee
    from .car import taxi_fare_description
    pricing=resolve_call_fee(product_id,depart,quoted_fee=quoted_fee)
    if type(model.get('fare_won')) is not int or model['fare_won']<0:
        raise CaseInputError('호출료 합산에 필요한 택시 예산이 잘못됐습니다')
    if 'option_fee_won' in model or 'call_fee' in model:
        raise CaseInputError('택시 호출료를 중복 합산할 수 없습니다')
    result=deepcopy(model)
    result['call_fee']=pricing
    result['fare_won']+=pricing['maximum_won']
    result['fare_basis']=taxi_fare_description(result)
    return result

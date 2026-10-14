"""확인한 호출 옵션료를 같은 구간·유효 시각에만 예산에 합산한다."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from .errors import CaseInputError


def aware_time(value):
    if not isinstance(value, str):
        raise CaseInputError('택시 옵션료 시각은 오프셋 있는 ISO 문자열이어야 합니다')
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CaseInputError('택시 옵션료 시각 형식이 잘못됐습니다') from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise CaseInputError('택시 옵션료 시각에 시간대가 필요합니다')
    return result


def normalize_fees(values):
    if values is None:
        return ()
    if not isinstance(values, (list, tuple)):
        raise CaseInputError('택시 옵션료는 구간별 목록이어야 합니다')
    out, pairs = [], set()
    required = {'from', 'to', 'fee_won', 'valid_from', 'valid_until', 'source'}
    for value in values:
        if not isinstance(value, dict) or set(value) != required:
            raise CaseInputError('택시 옵션료의 구간·금액·유효기간·출처가 필요합니다')
        if any(not isinstance(value[key], str) or not value[key].strip()
               for key in ('from', 'to', 'source')):
            raise CaseInputError('택시 옵션료의 구간과 출처는 빈 문자열일 수 없습니다')
        if type(value['fee_won']) is not int or value['fee_won'] < 0:
            raise CaseInputError('택시 옵션료는 0 이상의 원 단위 정수여야 합니다')
        if aware_time(value['valid_from']) >= aware_time(value['valid_until']):
            raise CaseInputError('택시 옵션료 유효기간의 시작은 끝보다 빨라야 합니다')
        pair = (value['from'], value['to'])
        if pair in pairs:
            raise CaseInputError('같은 구간의 택시 옵션료를 중복 입력할 수 없습니다')
        pairs.add(pair)
        out.append(deepcopy(value))
    return tuple(out)


def selected_fee(values, origin, destination, depart):
    """시작 포함·끝 제외. 옵션료 부재를 0원으로 해석하지 않는다."""
    for value in values:
        if (value['from'], value['to']) != (origin.get('key'), destination.get('key')):
            continue
        if aware_time(value['valid_from']) <= depart < aware_time(value['valid_until']):
            return deepcopy(value)
    return None


def with_option_fee(model, fee):
    """미터·기존 여유·통행료는 유지하고 확인된 옵션료만 한 번 더한다."""
    if fee is None:
        return model
    from .car import taxi_fare_description
    result = deepcopy(model)
    if type(result.get('fare_won')) is not int or result['fare_won'] < 0:
        raise CaseInputError('옵션료 합산에 필요한 택시 예산이 잘못됐습니다')
    if 'option_fee_won' in result or 'call_fee' in result:
        raise CaseInputError('택시 옵션료를 중복 합산할 수 없습니다')
    result['option_fee_won'] = fee['fee_won']
    result['fare_won'] += fee['fee_won']
    result['fare_basis'] = taxi_fare_description(result)
    return result

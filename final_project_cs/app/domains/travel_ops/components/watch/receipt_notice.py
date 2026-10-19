"""저장 문자 원문과 일정 지역을 읽기 전용으로 대조한다. 실제 적용 완료는 추정하지 않는다."""
from __future__ import annotations

from app.domains.travel_ops.ports.data_sources.notice_area import place_area, relation


def review(payload: dict) -> dict:
    value = payload.get('value') if isinstance(payload.get('value'), dict) else {}
    target = place_area(payload.get('target_place') or payload.get('review_target') or {})
    messages: dict[tuple, dict] = {}
    sources = [value.get('for_region'), value.get('unclassified'), payload.get('disruptions'),
               payload.get('_disruptions'), payload.get('advisories'), payload.get('_advisories')]
    if payload.get('text'):
        sources.insert(0, [payload])
    stored = [message for rows in sources for message in rows or []
              if isinstance(message, dict) and message.get('category', 'disaster_msg') == 'disaster_msg']
    for rows in sources:
        for message in rows or []:
            if not isinstance(message, dict) or message.get('category', 'disaster_msg') != 'disaster_msg':
                continue
            if not message.get('text') and not (message.get('created_at') or message.get('published_at')):
                continue
            message = _with_receipt_identity(message, stored)
            key = _message_key(message)
            old = messages.get(key, {})
            messages[key] = {**message, **old, 'regions': old.get('regions') or message.get('regions') or []}
    rows = []
    for message in messages.values():
        raw_regions = message.get('regions') or []
        regions = [value for value in raw_regions if isinstance(value, str)] if isinstance(raw_regions, list) else []
        rows.append({k: message.get(k) for k in ('serial', 'text', 'kind', 'step', 'created_at', 'published_at')} |
                    {'regions': regions, 'relation': relation(regions, target)})
    matched = sum(row['relation'] == 'matched' for row in rows)
    unrelated = sum(row['relation'] == 'unrelated' for row in rows)
    unknown = sum(row['relation'] == 'unassessed' for row in rows)
    if rows and unrelated == len(rows):
        reason = '문자의 발송 지역과 대상 일정의 비교 지역이 달라 이 일정의 영향 사유에서 제외했습니다.'
    elif unknown and not matched:
        reason = '대상 지역 또는 문자의 적용 지역을 확인하지 못해 실제 일정 영향을 판단할 수 없습니다.'
    elif matched:
        reason = '발송 지역이 대상 일정의 비교 지역과 겹칩니다. 구 단위 비교이며 현장 접근·변경 완료를 뜻하지 않습니다.'
    else:
        reason = '이 점검에 저장된 재난문자 본문이 없습니다. 과거 내용을 재구성하지 않습니다.'
    return {'messages': rows, 'target': target, 'matched': matched, 'unrelated': unrelated,
            'unassessed': unknown, 'reason': reason}


def causes_in_area(causes: list[dict], result: dict) -> list[dict]:
    matched = {_message_key(row) for row in result['messages'] if row['relation'] == 'matched'}
    return [cause for cause in causes if _message_key(_with_receipt_identity(cause, result['messages'])) in matched]


def _with_receipt_identity(message: dict, stored: list[dict]) -> dict:
    """옛 원인의 누락 필드는 같은 원문 수신을 하나로 특정할 때만 보완한다."""
    key = _message_key(message)
    candidates = [row for row in stored if _message_key(row)[1:3] == key[1:3]
                  and (key[0] is None or _message_key(row)[0] == key[0])
                  and (not key[3] or _message_key(row)[3] == key[3])
                  and _message_key(row)[3]]
    if len({_message_key(row) for row in candidates}) != 1:
        return message
    found = candidates[0]
    return {**message, 'serial': message.get('serial') if key[0] is not None else found.get('serial'),
            'regions': message.get('regions') if key[3] else found.get('regions')}


def _message_key(message: dict) -> tuple:
    raw_regions = message.get('regions')
    regions = tuple(sorted({value.strip() for value in raw_regions if isinstance(value, str)})) if isinstance(raw_regions, list) else ()
    serial = message.get('serial')
    return (str(serial) if serial is not None else None, message.get('text'),
            message.get('created_at') or message.get('published_at'), regions)

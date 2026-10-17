"""운영자 기록의 영향 범위. 기존 안전 판정을 읽기 전용으로 재사용한다."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.planning.safety import SafetyRules, classify
from app.domains.travel_ops.components.watch.receipt_notice import causes_in_area, review

SCOPES = {'trip': '전체일정정지', 'day': '일일일정정지', 'item': '해당일정정지', 'none': '영향없음'}


def describe(*, category: str, status: str | None, record_type: str, mode: str,
             trip_id: str | None, stage: str, payload: dict, rules: SafetyRules) -> dict:
    """정지 완료를 추정하지 않는다. 수신·미확인과 정상 무영향을 구별한다."""
    trial = mode == 'simulation' or stage == 'simulation_full' or bool(payload.get('simulation_target'))
    target_mode = 'simulation' if trial else 'actual' if trip_id else None

    def result(scope: str, summary: str) -> dict:
        return {'scope': scope, 'label': SCOPES.get(scope, '영향 미판정'), 'summary': summary,
                'affects_itinerary': bool(trip_id and not trial and scope in ('trip', 'day', 'item')),
                'target_mode': target_mode}

    if record_type in ('disaster_message', 'api_receipt'):
        summary = ('재난문자 원문을 수신했습니다. 여행별 점검 전이므로 일정 영향은 아직 판단하지 않았습니다.'
                   if record_type == 'disaster_message' else 'API 수신 상태 기록입니다. 이 기록만으로 여행 영향을 판단하지 않습니다.')
        return result('unassessed', summary)
    if record_type != 'mock_input' and not trip_id:
        return result('unassessed', '공통 관측 기록입니다. 특정 여행에 연결한 영향 판정이 아닙니다.')
    if status == 'not_applicable':
        return result('none', '이 일정은 해당 소스의 점검 대상이 아닙니다.')
    if status != 'ok':
        return result('unassessed', 'API 조회를 확인하지 못해 일정 영향을 판단할 수 없습니다.')
    if payload.get('verdict') == 'fatal':
        return result('unassessed', '점검 실패로 일정 영향 판정을 완료하지 못했습니다.')
    value = payload.get('value') or {}
    partial = payload.get('partial_from') or isinstance(value, dict) and value.get('partial_from')

    def causes(field: str) -> list[dict]:
        values = payload.get(field) or payload.get('_' + field) or []
        return [value for value in values if isinstance(value, dict) and value.get('category') == category]

    disruptions, advisories = causes('disruptions'), causes('advisories')
    event = classify(disruptions, rules)
    if category == 'disaster_msg' and not trial and (stage != 'safety' or event is not None):
        notice = review(payload)
        if notice['messages'] and notice['unrelated'] == len(notice['messages']):
            return result('none', notice['reason'])
        if (disruptions or advisories) and not notice['matched']:
            return result('unassessed', '문자의 적용 지역과 일정 위치의 관련성을 확인하지 못했습니다.')
        disruptions = causes_in_area(disruptions, notice)
        advisories = causes_in_area(advisories, notice)
        if notice['unassessed'] and not (disruptions or advisories):
            return result('unassessed', '문자의 적용 지역과 일정 위치의 관련성을 확인하지 못했습니다.')
        event = classify(disruptions, rules)
    if stage == 'safety':
        if event is None:
            if partial:
                return result('unassessed', '일부 소스만 응답해 일정 영향이 없다고 확정할 수 없습니다.')
            return result('none', '이 안전 점검에서는 여행 전체·당일 일정 정지 기준에 해당하지 않았습니다.')
        if event.level == 'day':
            if payload.get('phase') == 'upcoming':
                return result('none', '아직 시작 전인 여행이므로 현재 날짜의 일일 정지 적용 대상이 아닙니다.')
            if payload.get('phase') != 'in_progress':
                return result('unassessed', '과거 기록에 여행 진행 단계가 없어 일일 정지 적용 여부를 판단할 수 없습니다.')
            try:
                checked = datetime.fromisoformat(str(payload.get('checked_at') or ''))
            except ValueError:
                checked = None
            if checked is None or checked.tzinfo is None or event.at and event.at.tzinfo is None:
                return result('unassessed', '실제 점검 날짜를 확인하지 못해 일일 정지 적용 여부를 판단할 수 없습니다.')
            if event.at and event.at.astimezone(ZoneInfo('Asia/Seoul')).date() != checked.astimezone(ZoneInfo('Asia/Seoul')).date():
                return result('none', '점검 날짜와 다른 날의 사건이므로 이 날짜의 일일 정지 사유가 아닙니다.')
    if event:
        extent = '여행 전체' if event.level == 'trip' else '당일 남은 일정'
        return result(event.level, f'{event.label}: {extent}의 안전정지 기준에 해당합니다. 실제 적용 여부는 별도입니다.')
    if disruptions:
        cause = disruptions[0]
        reason = cause.get('kind') or cause.get('road') or cause.get('warning') or '외부 사건'
        return result('item', f'{reason}: 해당 방문의 중단·변경 검토 대상입니다. 정지 완료를 뜻하지 않습니다.')
    if advisories:
        return result('item', '예보 주의 기준을 넘었습니다. 주의 안내·변경 제안 대상이며 자동 정지 완료를 뜻하지 않습니다.')
    if partial:
        return result('unassessed', '일부 소스만 응답해 일정 영향이 없다고 확정할 수 없습니다.')
    return result('none', '이 점검에서는 일정 정지·변경 사유가 확인되지 않았습니다.')

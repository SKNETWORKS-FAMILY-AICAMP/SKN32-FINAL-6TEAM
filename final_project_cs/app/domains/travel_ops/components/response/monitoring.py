"""기존 감시 업무의 확인된 결과만 공통 응대에 전달한다. I/O·모델 호출 없음."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Any

from app.domains.travel_ops.components.response.writing import QuestionResult, ResponseInput, write_response


def monitoring_payload(payload: dict[str, Any], *, status: str, version: int,
                       saved_version: int | None = None, scope: dict[str, str] | None = None,
                       workflow: dict[str, Any] | None = None,
                       execution: dict[str, Any] | None = None,
                       followup: dict[str, Any] | None = None) -> dict[str, Any]:
    """문구·승인·원값 불변. applied는 저장 결과판과 현재판이 일치할 때만 허용한다."""
    if status not in {'applied', 'awaiting_choice', 'failed', 'unknown'}:
        raise ValueError('Unsupported monitoring status')
    if status == 'applied' and (saved_version is None or saved_version != version):
        raise ValueError('applied requires matching saved_version')
    snapshot = deepcopy(payload)
    snapshot.pop('response', None)  # 재작성·재전송 때 이전 결과를 근거 안에 재귀 복사하지 않는다.
    payload = snapshot
    facts = {**deepcopy(execution or {}), 'status': status, 'saved_version': saved_version}
    target = {k: deepcopy(payload[k]) for k in ('item_id', 'items') if k in payload}
    linked = {k: deepcopy(payload[k]) for k in ('causes', 'proposal_id', 'options', 'reason', 'protected_by') if k in payload}
    linked.update(deepcopy(followup or {}))
    closure = 'answered' if status == 'applied' else 'needs_input' if status == 'awaiting_choice' else 'failed'
    question = QuestionResult(question_id='monitoring', request={'kind': 'monitoring'},
                              text=str(payload['text']), status=closure,
                              evidence=deepcopy(payload), checked_at=str(payload.get('checked_at') or ''), target=target)
    result = write_response(ResponseInput(source='monitoring', scope=scope, version=version,
                                         question_ids=('monitoring',), questions=(question,),
                                         execution=facts, workflow=deepcopy(workflow or {}), followup=linked))
    snapshot['text'] = result.answer
    snapshot['response'] = asdict(result)
    return snapshot


def batch_status(batch: dict[str, Any]) -> str | None:
    """안내 전용 종결. 일부 저장을 전체 해결로 승격하지 않는다."""
    kinds = {entry.get('kind') for entry in batch.get('outcomes', [])}
    known = {'applied', 'nothing', 'asked', 'consent', 'no_alternate', 'recheck_failed',
             'source_failed', 'error', 'retry', 'unavailable', 'unhandled'}
    if kinds - known or batch.get('unknown'):
        return 'unknown'
    if kinds & {'no_alternate', 'recheck_failed', 'source_failed', 'error', 'retry', 'unavailable', 'unhandled'} or any(
            batch.get(k) for k in ('no_alternate', 'recheck_failed', 'source_failed', 'error', 'retry', 'unavailable', 'unhandled')):
        return 'failed'
    if kinds & {'asked', 'consent'} or batch.get('asked') or batch.get('consent') or batch.get('consents'):
        return 'awaiting_choice'
    return None


def action_notice(payload: dict[str, Any], *, tenant_id: str, trip: Any, trip_id: Any,
                  version: int, status: str, saved_version: int | None = None,
                  execution: dict[str, Any] | None = None) -> dict[str, Any]:
    """기존 outbox 한 건만 장식한다. 작성 오류는 업무 적용 결과를 뒤집지 않는다."""
    from app.domains.travel_ops.components.response.public import response_status
    import logging
    snapshot = deepcopy(payload)
    # 이전 메타데이터는 새 저장 증거가 아니다.
    for key in ('response', 'response_status', 'question_status', 'writing_status', 'writing_error'):
        snapshot.pop(key, None)
    try:
        if saved_version is not None:
            status = batch_status((execution or {}).get('batch') or {}) or status
        workflow = {k: deepcopy(snapshot[k]) for k in ('approval_status', 'approval_required',
                    'required_input_schema', 'resume_token', 'options', 'protected_by') if k in snapshot}
        result = monitoring_payload(snapshot, status=status, version=version, saved_version=saved_version,
            scope={'tenant_id': tenant_id, 'customer_id': str(trip['customer_id']), 'trip_id': str(trip_id)},
            workflow=workflow, execution=execution)
        result.update(response_status({'basis': {'response': result['response']}}))
        return result
    except Exception as exc:
        logging.getLogger(__name__).error('monitoring_notice_writing_failed error=%s', type(exc).__name__)
        return {**snapshot, 'writing_status': 'failed', 'writing_error': type(exc).__name__}


def case_payload(*, case: dict[str, Any] | None, trip: dict[str, Any], scope: dict[str, str],
                 case_id: str, causes: list[dict[str, Any]], items: list[str], checked_at: str,
                 outcome: dict[str, Any] | None = None) -> dict[str, Any]:
    """재조회한 Case의 적용 기록만 쓴다. resolved·계산 digest는 저장 증거가 아니다."""
    state = (case or {}).get('state_json') or {}
    actions = state.get('applied_actions') or []
    last = actions[-1] if actions else {}
    summary = last.get('summary') or {}
    ref = str(last.get('result_ref') or '')
    prefix = f"trip:{scope['trip_id']}:v"
    suffix = ref[len(prefix):] if ref.startswith(prefix) else ''
    canonical = bool(suffix and suffix.isascii() and suffix.isdigit() and not suffix.startswith('0'))
    saved = int(suffix) if canonical and type(trip['version']) is int and trip['version'] > 0 else None
    workflow = {k: deepcopy(state[k]) for k in ('required_input_schema', 'resume_token', 'approval_status',
                'approval_required', 'action_proposals', 'pending_proposals', 'choices') if k in state}
    workflow['case_status'] = (case or {}).get('status')
    batch = summary.get('batch') or {}
    unresolved = batch_status(batch)
    proposal_prefix = f"trip:{scope['trip_id']}:proposal:"
    proposal = ref[len(proposal_prefix):] if ref.startswith(proposal_prefix) else ''
    proposals = [summary.get('proposal_id'), *(a.get('proposal_id') for a in batch.get('asked', []) if isinstance(a, dict))]
    valid_proposal = bool(proposal and ':' not in proposal and proposal in proposals)
    invalid_ref = bool(ref and saved is None and not valid_proposal)
    waiting = valid_proposal or (not invalid_ref and (summary.get('status') == 'asked' or unresolved == 'awaiting_choice'))
    status = 'unknown'
    if ((case or {}).get('status') == 'unknown' or (outcome or {}).get('status') == 'unknown'
            or summary.get('status') == 'unknown' or unresolved == 'unknown' or invalid_ref):
        pass
    elif ((case or {}).get('status') in {'failed', 'escalated'}
          or summary.get('status') == 'failed' or unresolved == 'failed'):
        status = 'failed'
    elif waiting or (case or {}).get('status') in {'waiting_input', 'waiting_approval'}:
        status = 'awaiting_choice'
    elif saved is not None and saved == trip['version']:
        status = 'applied'
    text = {'applied': state.get('answer') or '새 일정을 저장했어요. 계획서에서 확인해 주세요.',
            'awaiting_choice': '선택을 기다리고 있어요. 아직 선택하지 않은 일정은 바꾸지 않았어요.',
            'failed': '변경을 완료하지 못했어요. 계획서에서 현재 일정을 확인해 주세요.',
            'unknown': '변경 결과를 확인하지 못했어요. 계획서에서 현재 일정을 확인해 주세요.'}[status]
    return monitoring_payload({'text': text, 'causes': causes, 'items': items, 'checked_at': checked_at},
        status=status, version=trip['version'], saved_version=saved if saved == trip['version'] else None,
        scope=scope, workflow=workflow,
        execution={'case_id': case_id, 'case_status': (case or {}).get('status'),
                   'applied_actions': deepcopy(actions), 'outcome': deepcopy(outcome)},
        followup={'case_id': case_id, 'proposal_id': summary.get('proposal_id'),
                  'choices': deepcopy(batch.get('asked') or state.get('choices') or [])})

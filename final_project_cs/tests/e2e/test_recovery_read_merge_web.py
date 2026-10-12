"""복수 조회와 문맥으로 보정된 대상이 중단·재전송 뒤에도 유지되는지 확인한다."""
import pytest

from app.core.case_lifecycle.events import EventType
from .test_decision_unit_web import decided, _say  # noqa: F401
from .test_web_api import api, _fresh_limit_cache, _h  # noqa: F401
from .test_chat_read_requests import _model
from .test_web_conversation_resume import _post, _saved
from .test_fact_read_recovery_web import ReadInterrupted, _case_for


def interrupt_after_routing(monkeypatch):
    from app.core import transition as state_transitions
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore

    original=state_transitions.transition_case
    original_latest=TripStore.latest
    pending=[]
    armed=True
    def transition(conn, **kwargs):
        result=original(conn, **kwargs)
        if armed and kwargs['event_type'] is EventType.ROUTED:
            pending.append(conn)
        return result
    def latest(self,conn,*args,**kwargs):
        nonlocal armed
        if pending and conn is not pending[0]:
            pending.pop().commit()  # move() 내부의 짧은 transaction을 빠져나온 뒤 중단한다.
            armed=False
            raise ReadInterrupted('committed routing interruption')
        return original_latest(self,conn,*args,**kwargs)
    monkeypatch.setattr(state_transitions,'transition_case',transition)
    monkeypatch.setattr(TripStore,'latest',latest)
    def restore():
        monkeypatch.setattr(state_transitions,'transition_case',original)
        monkeypatch.setattr(TripStore,'latest',original_latest)
    return restore


def test_multi_question_http_retry_preserves_each_target_and_one_completion(decided,monkeypatch):

    _model(decided,[('time','성수 점심','explicit'),('duration','· 저녁','explicit')])
    original=interrupt_after_routing(monkeypatch)
    text='성수 점심은 언제고 저녁은 얼마나 머물러?'
    with pytest.raises(ReadInterrupted): _post(decided,text,'merged-multi-interruption')
    case_id=_case_for('merged-multi-interruption')
    assert _saved(case_id)[0]=='running'
    original()
    # 최초 모델 결과가 저장돼 있어 재전송은 모델을 다시 부르면 실패해야 한다.
    def forbidden(*args,**kwargs): raise AssertionError('model called during read retry')
    decided['decider'].structured=forbidden
    response=_post(decided,text,'merged-multi-interruption')
    assert response.status_code==200,response.text
    body=response.json()
    assert body['case_id']==case_id and body['case_status']=='resolved'
    assert '성수 점심' in body['answer'] and '저녁' in body['answer'] and '분 머무는' in body['answer']


def test_context_corrected_target_and_snapshot_are_committed_together(decided,monkeypatch):

    _model(decided,[('time','· 저녁','explicit')])
    _say(decided,'저녁은 몇 시야?','merged-context-first')
    # 단일 조회의 잘못된 모델 대상을 직전 사실 조회 대상(저녁)으로 보정한다.
    def structured(system,user,schema,**kwargs):
        return {'action':'answer_fact','target_item':decided['decider']._alias(user,'성수 점심'),
            'target_change':'none','fact':'address','minutes':0,'choices':[],'query':None,'reads':[],'social':''}
    decided['decider'].structured=structured
    original=interrupt_after_routing(monkeypatch)
    text='거기 주소 알려줘'
    with pytest.raises(ReadInterrupted): _post(decided,text,'merged-context-interruption')
    case_id=_case_for('merged-context-interruption')
    state=_saved(case_id)[3]
    assert state['decision']['item_id']==state['fact_read_snapshot']['item_id']
    original()
    response=_post(decided,text,'merged-context-interruption')
    assert response.status_code==200,response.text
    assert response.json()['case_id']==case_id and response.json()['case_status']=='resolved'
    assert '저녁' in response.json()['answer'] and '성수 점심' not in response.json()['answer']

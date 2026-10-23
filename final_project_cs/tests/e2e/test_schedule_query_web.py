"""모델 응답을 고정한 실제 앱·DB 통합 시험. 실제 모델 정확도 시험과 구분한다."""
from .test_decision_unit_web import decided, _say  # noqa: F401
from .test_web_api import api, _h  # noqa: F401


def test_scoped_read_returns_latest_items_without_changing_trip_or_dispatching_a_change(decided):
    client=decided['client']
    url=f"/v1/web/trips/{decided['trip']['trip_id']}"
    before=client.get(url,headers=_h(decided['key'])).json()
    def scoped(*args,**kwargs):
        return dict(action='answer_fact',fact='changeability',target_item='none',target_change='none',
                    minutes=0,choices=[],query=dict(day='all',period='afternoon',kind='all'))
    decided['decider'].structured=scoped
    response=_say(decided,'오후 일정 중에 바꿀 수 있는 일정이 뭐가 있어?','scope-read-1')
    assert response['status']=='answered',response
    assert response['decision']['query']['period']=='afternoon'
    assert response['basis']['source']=='latest_itinerary'
    assert '아직 바꾸지는 않았어요' in response['answer']
    assert '09:00' not in response['answer']
    after=client.get(url,headers=_h(decided['key'])).json()
    assert before['version']==after['version'] and before['items']==after['items']

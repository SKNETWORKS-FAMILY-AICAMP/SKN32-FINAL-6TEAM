from .test_decision_unit_web import decided, _say  # noqa: F401
from .test_web_api import api, _fresh_limit_cache, _h  # noqa: F401

def test_summary_button_answers_without_model_and_keeps_case(decided):
    client=decided['client'];url=f"/v1/web/trips/{decided['trip']['trip_id']}"
    before=client.get(url,headers=_h(decided['key'])).json()
    day=before['items'][0]['starts_at'][:10]
    body=_say(decided,f"{day} 하루 일정을 요약해 주세요.","summary-button-1",summary_day=day)
    assert body['status']=='answered',body
    assert body['case_id'] and body['answer']
    assert decided['decider'].prompts==[]
    again=_say(decided,f"{day} 하루 일정을 요약해 주세요.","summary-button-1",summary_day=day)
    assert again['case_id']==body['case_id'] and decided['decider'].prompts==[]
    after=client.get(url,headers=_h(decided['key'])).json()
    assert before['version']==after['version'] and before['items']==after['items']

def test_summary_metadata_cannot_hide_change_or_resume(decided):
    client=decided['client'];url=f"/v1/web/trips/{decided['trip']['trip_id']}"
    before=client.get(url,headers=_h(decided['key'])).json();day=before['items'][0]['starts_at'][:10]
    for extra in [{'message':f'{day} 하루 일정을 요약해 주세요. 식당 바꿔'}, {'message':f'{day} 하루 일정을 요약해 주세요.','resume_token':'bad'}]:
        response=client.post(url+'/messages',headers=_h(decided['key']),json={'request_id':'bad-summary','summary_day':day,**extra})
        assert response.status_code==422,response.text
    assert decided['decider'].prompts==[]

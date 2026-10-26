from datetime import timedelta
import pytest
from tests.unit.travel.test_intake_visit_time_restriction import _Conn, _at, _activity_team, _review, RESTRICT, ALWAYS, PLACE  # noqa: F401 (_activity_team: autouse fixture)
from app.domains.travel_ops.components.intake import review, candidates, hours

@pytest.mark.parametrize('end', ['09:00','10:00'])
def test_invalid_end_never_clears_the_visit_condition(end):
    assert _review([RESTRICT], '10:00', end)[0].conditions == [RESTRICT]

@pytest.mark.parametrize('text', [
 '2026-11-03 방문 제한시간 17:00~익일 10:00',
 '토·일 방문 제한시간 17:00~익일 10:00',
 '방문 제한시간 17:00~익일 10:00 단 특별행사 제외',
 '방문 제한시간 17:00~익일 10:00 및 매일 휴무',
 '방문 제한시간 17:00~익일 10:00, 다른 구역은 종일 출입금지',
 '방문 제한시간 17:00~익일 10:00 또는 정오 출입금지',
])
def test_unparsed_remainder_is_not_silently_cleared(text):
    assert _review([text], '10:00','11:30')[0].conditions == [text]

def test_multiday_and_24h_never_clear():
    for text in [RESTRICT, '방문 제한시간 00:00~24:00']:
        f=hours.facts_for(_Conn([text]),'t',dict(PLACE),'activity',_at('10:00'),_at('11:30')+timedelta(days=3))
        assert f.conditions == [text]

def _inputs():
    sources=[{'source_id':'s','position':0,'kind':'text','filename':None,'transcript':'2026-11-02 10:00–11:30 북촌한옥마을'}]
    values={'title':'북촌한옥마을','date':'2026-11-02','starts_at':'10:00','ends_at':'11:30','kind':'activity',
            'place':dict(PLACE,latitude=37.582,longitude=126.983)}
    claims=[{'source_id':'s','field':f'items[6].{k}','value':v,'method':'document','evidence':{'line':1},'needs_review':False,'note':None} for k,v in values.items()]
    return sources,claims

@pytest.mark.parametrize('conditions,expected_closed,expected_fits', [([RESTRICT,ALWAYS],'ok',True),([RESTRICT,'홈페이지 참조'],'warn',False)])
def test_samecase_real_build_ready_and_candidate_fits(conditions,expected_closed,expected_fits):
    sources,claims=_inputs()
    built=review.build(_Conn(conditions),tenant_id='t',intake_id='27107a20-d6aa-46fe-8533-667bb1d4fec2',revision=2,sources=sources,claims=claims,use_engine=False)
    item=built['items'][0]
    assert item['id']=='0-6'
    assert next(r for r in item['rows'] if r['row']=='hours')['result']=='ok'
    assert next(r for r in item['rows'] if r['row']=='closed')['result']==expected_closed
    assert built['ready'] is True and built['needs']=={'items':0,'moves':0,'total':0}
    assert item['status']=='keep' and item['can_lock'] is True
    got=candidates.assess(_Conn(conditions),'t',item,item['place'],None,None,None)
    assert got['fits'] is expected_fits
    assert next(r for r in got['rows'] if r['row']=='closed')['result']==expected_closed

def test_stored_review_requires_authorized_force_revalidate(monkeypatch):
    from copy import deepcopy
    from app.domains.travel_ops.components.intake import risks, dining_review
    sources, claims = _inputs()
    conn = _Conn([RESTRICT, ALWAYS])
    fresh = review.build(conn, tenant_id='t', intake_id='i', revision=2, sources=sources, claims=claims, use_engine=False)
    stale = deepcopy(fresh)
    closed = next(r for r in stale['items'][0]['rows'] if r['row']=='closed')
    closed.update(result='warn', text='휴무·운영 조건을 확인해 주세요 ('+RESTRICT+'; '+ALWAYS+')')
    writes=[]
    monkeypatch.setattr(review, 'load', lambda *a, **k: deepcopy(stale))
    # contract_correction(role-manager 이식): `_customer_inputs` 는 설문 답 소비 묶음(L10)에만 있다 — 없는 트리에서는 대역을 더하기만 한다(단언 불변)
    monkeypatch.setattr(review, '_customer_inputs', lambda c,t,i,p,cl: p, raising=False)
    monkeypatch.setattr(risks, 'decorate', lambda c, **k: k['review'])
    monkeypatch.setattr(dining_review, 'refresh', lambda c,t,i,r,p: p)
    monkeypatch.setattr(review, '_store_read', lambda *a, **k: pytest.fail('unexpected implicit write'))
    monkeypatch.setattr(review, 'store', lambda c,t,i,r,p: writes.append(deepcopy(p)))
    stale['risk_schema_version']=risks.SCHEMA_VERSION
    args=dict(tenant_id='t', intake_id='i', revision=2, sources=sources, claims=claims, use_engine=False)
    cached=review.ensure(conn, **args)
    assert next(r for r in cached['items'][0]['rows'] if r['row']=='closed')['result']=='warn'
    assert writes==[]
    checked=review.ensure(conn, force=True, **args)
    assert next(r for r in checked['items'][0]['rows'] if r['row']=='closed')['result']=='ok'
    assert checked['revision']==2 and checked['ready'] is True and len(writes)==1
    assert sources==_inputs()[0] and claims==_inputs()[1]


def test_unregistered_activity_keeps_both_conditions():
    from app.domains.travel_ops.components.team_hooks import activity_ledger
    activity_ledger.clear()
    assert _review([RESTRICT,ALWAYS],'10:00','11:30')[0].conditions == [RESTRICT,ALWAYS]

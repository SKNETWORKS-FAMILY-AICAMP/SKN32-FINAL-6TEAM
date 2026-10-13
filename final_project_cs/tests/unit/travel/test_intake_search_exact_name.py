"""명소·식당 이름 검색에서 가까운 부속 장소가 정확한 이름보다 먼저 나오지 않는다."""
import pytest
from app.domains.travel_ops.components.intake import candidates as c


@pytest.mark.parametrize('query,kind,prefix', [('경복궁','activity','경복궁 화장실'),('한식당','dining','한식당 별관')])
def test_exact_place_name_precedes_nearer_prefix_hit(monkeypatch, query, kind, prefix):
    exact=c._place(query,37.59,127.0,'places',kind=kind)
    nearby=c._place(prefix,37.50,127.0,'kakao',kind=kind)
    monkeypatch.setattr(c,'neighbours',lambda *a:(None,None))
    monkeypatch.setattr(c,'reference',lambda *a:(37.50,127.0))
    monkeypatch.setattr(c,'_taken',lambda *a,**kw:set())
    monkeypatch.setattr(c,'_db_places_by_name',lambda *a:[exact])
    monkeypatch.setattr(c,'_ledger_places',lambda *a,**kw:[])
    monkeypatch.setattr(c,'_kakao_places',lambda *a,**kw:[nearby])
    monkeypatch.setattr(c,'assess',lambda *a,**kw:{'status':'ok','fits':True})
    monkeypatch.setattr(c,'_present',lambda p,*a,**kw:{'place':p})
    item={'id':'probe','kind':kind,'parts':{},'place':None}
    result=c.search(None,tenant_id='probe',review={'items':[item]},item=item,query=query)
    assert result['results'][0]['place']['name']==query
    assert result['results'][1]['place']['name']==prefix


def test_prefix_only_results_retain_distance_order(monkeypatch):
    places=[c._place('경복궁 서쪽',37.59,127.,'places',kind='activity'),c._place('경복궁 동쪽',37.50,127.,'places',kind='activity')]
    monkeypatch.setattr(c,'neighbours',lambda *a:(None,None))
    monkeypatch.setattr(c,'reference',lambda *a:(37.50,127.))
    monkeypatch.setattr(c,'_taken',lambda *a,**kw:set())
    monkeypatch.setattr(c,'_db_places_by_name',lambda *a:places)
    monkeypatch.setattr(c,'_ledger_places',lambda *a,**kw:[])
    monkeypatch.setattr(c,'_kakao_places',lambda *a,**kw:[])
    monkeypatch.setattr(c,'assess',lambda *a,**kw:{'status':'ok','fits':True})
    monkeypatch.setattr(c,'_present',lambda p,*a,**kw:{'place':p})
    item={'id':'probe','kind':'activity','parts':{},'place':None}
    result=c.search(None,tenant_id='probe',review={'items':[item]},item=item,query='경복궁')
    assert [r['place']['name'] for r in result['results']]==['경복궁 동쪽','경복궁 서쪽']

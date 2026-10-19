from contextlib import nullcontext
from types import SimpleNamespace

from app.domains.travel_ops.components.intake import candidates, autofix
from app.domains.travel_ops.components.team_hooks import lodging_alternatives
from .test_intake_lodging_candidates import HOTEL, review, sources  # noqa: F401

REAL_TEAM_PICKER = candidates._team_lodging_places


class LocationConnection:
    def transaction(self):
        return nullcontext()

    def cursor(self):
        return nullcontext(self)

    def execute(self, *args):
        pass

    def fetchone(self):
        return ('서울 종로구 사직로 161',)


def test_registered_lodging_uses_next_coordinates_and_nearby_district(monkeypatch):
    import app.core.settings as settings
    monkeypatch.setattr(settings, 'get_guardrails', lambda: SimpleNamespace(get=lambda key: 15000 if key.endswith('radius_m') else True))
    asked=[]

    def rank(**kwargs):
        asked.append(kwargs)
        return {'alternatives': [dict(HOTEL)]}

    monkeypatch.setattr(lodging_alternatives, 'ranked', rank)
    view=review(meal=True)
    view['party_size']=2
    item=view['items'][0]
    got=REAL_TEAM_PICKER(LocationConnection(),'travel',view,item,None,view['items'])
    assert got and got[0]['basis']=='lodging'
    assert asked[0]['anchor']==(37.5796,126.9770)
    assert asked[0]['keyword']=='서울 종로구'
    assert asked[0]['adults']==2


def test_nameless_hotel_calls_registered_team_before_catalogue(sources,monkeypatch):  # noqa: F811
    calls,kakao=sources
    monkeypatch.setattr(candidates,'_team_lodging_places',lambda *args:[{**HOTEL,'basis':'lodging','content_type_id':'32'}])
    view=review(meal=True)
    got=candidates.alternatives(None,tenant_id='travel',review=view,item=view['items'][0],kakao=kakao,use_engine=False)
    assert got['candidates'] and 'team_ranked' in got['notes']
    assert not calls and not kakao.asked


def test_no_hotel_source_never_turns_breakfast_into_an_unrelated_restaurant(sources,monkeypatch):  # noqa: F811
    _,kakao=sources
    monkeypatch.setattr(candidates,'_catalog_places',lambda *args,**kwargs:[])
    monkeypatch.setattr(kakao,'search',lambda *args,**kwargs:[])
    got=autofix.plan(None,tenant_id='travel',review=review(meal=True),kakao=kakao,use_engine=False)
    assert got['changes']==[]
    assert got['kept'][0]['reason']=='no_candidates'

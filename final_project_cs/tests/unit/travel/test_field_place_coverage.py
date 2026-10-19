"""장소의 존재·정규 영업시간·임시휴무 관측을 섞지 않는다."""
from app.domains.travel_ops.components.watch.place_status import PlaceStatus
from app.domains.travel_ops.components.intake.pipeline import _checked_pick, IntakeRejected
from app.domains.travel_ops.components.intake.assemble import _place_in
from app.domains.travel_ops.components.intake.reopen import _place_value
import pytest


def test_missing_exceptional_closure_keeps_weekly_hours_without_claiming_open():
    report = {'verdict':'clear', 'hours':{'week':'10:00-21:00'}}
    got = PlaceStatus.merge(report,{'status':'unverifiable','reason':'free_unverifiable'})
    assert got['verdict']=='clear' and got['hours']==report['hours']
    assert got['place_status']['status']=='unverifiable'
    assert got['unverified_checks'][0]['category']=='temporary_closure'
    assert got['place_status']['status']!='open'


def test_independent_air_failure_is_not_erased_by_unknown_closure():
    got = PlaceStatus.merge({'verdict':'fatal','failed_categories':['air_quality']},
        {'status':'unverifiable','reason':'free_unverifiable'})
    assert got['verdict']=='fatal' and got['failed_categories']==['air_quality']


def test_actual_closure_still_disrupts_a_visit():
    got = PlaceStatus.merge({'verdict':'clear'},
        {'status':'closed','source':'dining_ledger','checked_at':'2026-10-17T19:58:00+09:00'})
    assert got['verdict']=='disrupted' and got['disruptions'][0]['kind']=='closed'


def test_customer_pick_provider_ref_survives_registration_and_reopening():
    value = _checked_pick('items[0].place',{'name':'선택한 다이소','latitude':37.485,'longitude':127.016,
        'source':'kakao','provider_ref':'kakao:123456'})
    stored = _place_in('p',value,'activity')
    place = {'place_id':'test-owned','name':stored['name'],'latitude':stored['lat'],
        'longitude':stored['lon'],'attributes':stored['attributes']}
    restored = _place_value(place,'activity')
    assert restored['provider_ref']=='kakao:123456'
    assert restored['source']=='customer_pick' and restored['origin']=='kakao'


def test_customer_pick_does_not_accept_a_url_or_another_trips_place_id_as_provider_ref():
    with pytest.raises(IntakeRejected):
        _checked_pick('items[0].place',{'name':'선택한 장소','latitude':37.485,'longitude':127.016,
            'source':'kakao','provider_ref':'https://private.invalid/token'})


def test_local_food_candidates_are_checked_before_a_unique_global_prefix():
    from app.domains.travel_ops.components.intake.places import resolve
    class Kakao:
        def search(self,query,**kwargs):
            return ([{"name":"지역 돈까스","latitude":37.485,"longitude":127.016,"category_group":"FD6"}]
                if kwargs.get("near") else
                [{"name":"돈까스의집","latitude":37.60,"longitude":126.90,"category_group":"FD6"}])
    result=resolve("돈까스",our_places=[],kakao=Kakao(),kind_hint="dining",near=(37.485,127.016),choose_near=True)
    assert result.name=="지역 돈까스" and result.latitude==37.485

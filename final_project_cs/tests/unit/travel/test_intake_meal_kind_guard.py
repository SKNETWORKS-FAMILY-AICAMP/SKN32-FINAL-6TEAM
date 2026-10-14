"""식사 요청에 동명 관광지·관광지 후보가 연결되지 않는지 확인한다."""
import pytest

from app.domains.travel_ops.components.intake.places import resolve
from tests.unit.travel.test_intake_resolve_dining import Lookup, Kakao, _hit


@pytest.mark.parametrize('title', ['광화문', '광화문 근처 한식', '광화믄'])
def test_meal_does_not_accept_exact_shortened_or_typo_tourist_place(title):
    places=[dict(name='광화문',kind='activity',place_id='gate',latitude=37.57,longitude=126.97)]
    found=resolve(title,our_places=places,tour=Lookup({'광화문':'광화문'},content_type='12'),kind_hint='dining')
    assert found.status=='unresolved'
    assert found.place_id is None and found.content_id is None


def test_non_food_kakao_hit_is_not_relabelled_as_dining():
    found=resolve('광화문',our_places=[],kakao=Kakao({'광화문':[_hit('광화문','AT4')]}),kind_hint='dining')
    assert found.status=='unresolved' and not found.candidates


def test_restaurant_hit_survives_its_tourist_namesake():
    found=resolve('경복궁',our_places=[],tour=Lookup({'경복궁':'경복궁'},content_type='12'),
                  kakao=Kakao({'경복궁':[_hit('경복궁 한식당')]}),kind_hint='dining')
    assert found.status=='resolved' and found.kind=='dining'
    assert found.name=='경복궁 한식당' and found.content_id is None


def test_romanized_meal_does_not_confirm_tourist_prefix():
    found=resolve('Gyeongbokgung',our_places=[],tour=Lookup({'경복궁':'경복궁'},content_type='12'),
                  kakao=Kakao({'Gyeongbokgung':[_hit('경복궁 한식당')]}),kind_hint='dining')
    assert found.kind!='activity' and found.content_id is None


def test_known_restaurant_and_tour_api_food_remain_usable():
    own=resolve('마지',our_places=[dict(name='마지',kind='dining',place_id='meal')],kind_hint='dining')
    tour=resolve('마지',our_places=[],tour=Lookup({'마지':'마지'},content_type='39'),kind_hint='dining')
    assert own.kind==tour.kind=='dining' and own.status==tour.status=='resolved'


def test_activity_request_keeps_the_tourist_match():
    found=resolve('광화문',our_places=[],tour=Lookup({'광화문':'광화문'},content_type='12'),kind_hint='activity')
    assert found.status=='resolved' and found.kind=='activity'

"""Menu spelling variants must keep the requested dish during nearby lookup."""
import pytest

from app.domains.travel_ops.components.planning.meal_likeness import dish_of
from app.domains.travel_ops.instances.dining.ledger import find_dish_near


@pytest.mark.parametrize("requested", ["돈까스", "돈가스", "돈카츠"])
def test_pork_cutlet_spellings_share_a_dish(requested):
    assert dish_of({"name": requested}) == "돈가스"


@pytest.mark.parametrize("requested", ["돈까스", "돈가스", "돈카츠"])
@pytest.mark.parametrize("listed", ["돈까스", "돈가스", "돈카츠"])
def test_nearby_lookup_accepts_menu_spelling_variants(requested, listed):
    shops = [{"place_uid": "cutlet", "name": f"가나{listed}", "key": f"가나{listed}",
              "latitude": 37.55, "longitude": 126.92, "address": "서울 마포구",
              "category": "일식", "content_id": None}]
    found = find_dish_near(None, f"홍대 쇼핑 후 근처에서 {requested} 먹기", (37.55, 126.92), shops=shops)
    assert found is not None
    assert found["dining_place_uid"] == "cutlet"
    assert found["needs_review"] is True


def test_menu_spelling_variants_do_not_allow_a_different_dish_or_far_shop():
    shops = [{"place_uid": "other", "name": "가나국밥", "key": "가나국밥",
              "latitude": 37.55, "longitude": 126.92},
             {"place_uid": "far", "name": "가나돈까스", "key": "가나돈까스",
              "latitude": 37.65, "longitude": 126.92}]
    assert find_dish_near(None, "근처 돈까스", (37.55, 126.92), shops=shops) is None


def test_intake_resolver_passes_the_hongdae_anchor_to_real_ledger_lookup(monkeypatch):
    from app.domains.travel_ops.components.intake.places import resolve
    from app.domains.travel_ops.instances.dining import ledger

    shops = [{"place_uid": "cutlet", "name": "가나돈카츠", "key": "가나돈카츠", "base": "가나돈카츠",
              "latitude": 37.55, "longitude": 126.92, "address": "서울 마포구",
              "category": "일식", "content_id": None}]
    monkeypatch.setattr(ledger, "_shops", lambda conn: shops)

    class Lookup:
        misses = {}

        def find(self, name, area_code=None, near=None):
            return ledger.find_place_by_name(None, name, near=near)

    found = resolve("돈까스", our_places=[], dining=Lookup(), kind_hint="dining", near=(37.55, 126.92))
    assert found.status == "resolved"
    assert found.name == "가나돈카츠"
    assert found.needs_review is True

"""실제 지점 선택과 이름/주소/좌표에 의한 제공자 중복의 경계."""
from copy import deepcopy
from contextlib import contextmanager
import importlib

import pytest

from tests.unit.travel.test_social_dining import OWNER, NOW, match, meal, restaurant, setup


def branch(name, ref, *, source="places", latitude=37.57, longitude=126.98,
           address="서울 중구 가상로 100", fits=True):
    result = match(name, ref=ref, fits=fits, result="ok" if fits else "unknown")
    result["place"].update(source=source, address=address, latitude=latitude, longitude=longitude)
    return result


def wish(*, picked=None, choices=(), name="가상식당", branch_hint=None, area=None):
    link = restaurant("wish", restaurants=[{"name": name, "area": area, "branch": branch_hint}])
    if picked:
        link.update(selected_ref=picked, choices=deepcopy(list(choices)), status="confirmed")
    return link


def test_same_building_main_and_annex_require_a_real_branch_choice(monkeypatch):
    main, annex = branch("가상식당 본점", "place:main"), branch("가상식당 별관", "kakao:annex", source="kakao")
    service, conn = setup(monkeypatch, links=[wish()], items=[meal(0)],
        search=lambda *args, **kwargs: {"results": [main, annex]})
    preview = service.preview(conn, **OWNER, revision=3, now=NOW)
    assert preview["changes"] == []
    assert preview["unplaced"][0]["reason"] == "place_choice_required"
    assert {p["ref"] for p in preview["links"][0]["choices"]} == {"place:main", "kakao:annex"}


@pytest.mark.parametrize("include_unlabelled", [False, True])
def test_selected_annex_survives_preview_and_apply(monkeypatch, include_unlabelled):
    main, annex = branch("가상식당 본점", "place:main"), branch("가상식당 별관", "kakao:annex", source="kakao")
    pool = ([branch("가상식당", "place:unlabelled")] if include_unlabelled else []) + [main, annex]
    link = wish(picked="kakao:annex", choices=[main["place"], annex["place"]])
    service, conn = setup(monkeypatch, links=[link], items=[meal(0)],
        search=lambda *args, **kwargs: {"results": pool})
    preview = service.preview(conn, **OWNER, revision=3, now=NOW)
    assert preview["links"][0]["selected_ref"] == "kakao:annex"
    assert preview["changes"][0]["to"]["ref"] == "kakao:annex"
    service.apply(conn, **OWNER, revision=3, proposal_id=preview["proposal_id"])
    assert conn.state["review"]["items"][0]["place"]["ref"] == "kakao:annex"


@pytest.mark.parametrize("address", ["서울 중구 가상로 100", "서울 다른구 가상로 100"])
def test_same_road_number_does_not_override_distant_coordinates(monkeypatch, address):
    near = branch("가상식당", "place:near")
    far = branch("가상식당", "place:far", latitude=37.64, longitude=127.08, address=address)
    service, conn = setup(monkeypatch, links=[wish()], items=[meal(0)],
        search=lambda *args, **kwargs: {"results": [near, far]})
    preview = service.preview(conn, **OWNER, revision=3, now=NOW)
    assert preview["changes"] == []
    assert preview["unplaced"][0]["reason"] == "place_choice_required"


def test_similar_brand_names_in_the_same_building_stay_distinct(monkeypatch):
    pool = [branch("가상식당", "place:one"), branch("가상식당 포차", "place:two")]
    service, conn = setup(monkeypatch, links=[wish()], items=[meal(0)],
        search=lambda *args, **kwargs: {"results": pool})
    preview = service.preview(conn, **OWNER, revision=3, now=NOW)
    assert preview["changes"] == []
    assert preview["unplaced"][0]["reason"] == "place_choice_required"


def test_same_complete_branch_label_from_two_providers_can_merge(monkeypatch):
    pool = [branch("가상식당 명동역점 신관 본점", "place:main"),
            branch("가상식당 명동역점 신관 본점", "kakao:main", source="kakao", latitude=37.5702)]
    service, conn = setup(monkeypatch, links=[wish()], items=[meal(0)],
        search=lambda *args, **kwargs: {"results": pool})
    preview = service.preview(conn, **OWNER, revision=3, now=NOW)
    assert [p["ref"] for p in preview["links"][0]["choices"]] == ["place:main"]
    assert preview["changes"][0]["to"]["ref"] == "place:main"


def test_selected_annex_with_a_shared_main_suffix_stays_distinct(monkeypatch):
    main = branch("가상식당 본점", "place:main")
    annex = branch("가상식당 별관 본점", "kakao:annex", source="kakao")
    service, conn = setup(monkeypatch,
        links=[wish(picked="kakao:annex", choices=[main["place"], annex["place"]])], items=[meal(0)],
        search=lambda *args, **kwargs: {"results": [main, annex]})
    preview = service.preview(conn, **OWNER, revision=3, now=NOW)
    assert preview["links"][0]["selected_ref"] == "kakao:annex"
    assert preview["changes"][0]["to"]["ref"] == "kakao:annex"
    service.apply(conn, **OWNER, revision=3, proposal_id=preview["proposal_id"])
    assert conn.state["review"]["items"][0]["place"]["name"] == "가상식당 별관 본점"


def test_selected_same_name_shop_at_another_street_number_is_not_aliased(monkeypatch):
    first = branch("가상식당", "place:first", address="서울 중구 가상로 100")
    chosen = branch("가상식당", "place:chosen", address="서울 중구 가상로 102", latitude=37.5701)
    service, conn = setup(monkeypatch,
        links=[wish(picked="place:chosen", choices=[first["place"], chosen["place"]])], items=[meal(0)],
        search=lambda *args, **kwargs: {"results": [first, chosen]})
    preview = service.preview(conn, **OWNER, revision=3, now=NOW)
    assert preview["links"][0]["selected_ref"] == "place:chosen"
    assert preview["changes"][0]["to"]["ref"] == "place:chosen"


def test_explicit_branch_can_reuse_verified_unlabelled_catalog_identity(monkeypatch):
    catalog = branch("가상식당", "place:catalog")
    mapped = branch("가상식당 본점", "kakao:main", source="kakao", fits=False)
    service, conn = setup(monkeypatch, links=[wish(branch_hint="본점")], items=[meal(0)],
        search=lambda *args, **kwargs: {"results": [catalog, mapped]})
    preview = service.preview(conn, **OWNER, revision=3, now=NOW)
    assert preview["changes"][0]["to"]["ref"] == "place:catalog"


def test_name_region_and_branch_are_separate_search_hints(monkeypatch):
    seen = []
    def search(*args, **kwargs):
        seen.append(kwargs)
        return {"results": []}
    service, conn = setup(monkeypatch,
        links=[wish(name="가상식당 본점", branch_hint="본점", area="중구")], items=[meal(0)], search=search)
    service.preview(conn, **OWNER, revision=3, now=NOW)
    assert seen[0]["query"] == "가상식당 본점 중구"
    assert seen[0]["name_hint"] == "가상식당"
    assert seen[0]["branch_hint"] == "본점"
    assert seen[0]["area_hint"] == "중구"


def test_branch_word_inside_the_brand_is_not_branch_evidence(monkeypatch):
    seen = []
    def search(*args, **kwargs):
        seen.append(kwargs)
        return {"results": [branch("본점식당", "place:unlabelled")]}
    service, conn = setup(monkeypatch,
        links=[wish(name="본점식당", branch_hint="본점")], items=[meal(0)], search=search)
    preview = service.preview(conn, **OWNER, revision=3, now=NOW)
    assert preview["changes"] == []
    assert preview["unplaced"][0]["reason"] == "branch_unverified"
    assert seen[0]["query"] == "본점식당 본점"


def test_another_branch_containing_the_requested_branch_name_is_not_selected(monkeypatch):
    service, conn = setup(monkeypatch, links=[wish(branch_hint="성수점")], items=[meal(0)],
        search=lambda *args, **kwargs: {"results": [branch("가상식당 뚝섬성수점", "place:different")]})
    preview = service.preview(conn, **OWNER, revision=3, now=NOW)
    assert preview["changes"] == []
    assert preview["unplaced"][0]["reason"] == "branch_unverified"


@pytest.mark.parametrize("note", ["area_unverified", "area_mismatch"])
def test_region_failure_reason_is_preserved(monkeypatch, note):
    service, conn = setup(monkeypatch, links=[wish(area="가상동")], items=[meal(0)],
        search=lambda *args, **kwargs: {"results": [], "notes": [note]})
    preview = service.preview(conn, **OWNER, revision=3, now=NOW)
    assert preview["unplaced"][0]["reason"] == note


def test_current_revision_constraints_join_original_and_saved_food_conditions(monkeypatch):
    service = importlib.import_module("app.domains.travel_ops.components.intake.social_dining")
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params):
            assert params == ("tenant", "intake", "customer")
        def fetchone(self):
            return ({"dietary": ["halal"]}, 3)
    class Connection:
        def cursor(self): return Cursor()
    def claims(conn, tenant, intake, revision):
        assert (tenant, intake, revision) == ("tenant", "intake", 3)
        return [{"source_id": "generated", "field": "trip.constraints", "value": {
            "dietary": ["vegetarian"], "allergies": ["peanut"]}, "method": "rule"}]
    monkeypatch.setattr(service.pipeline, "_claims", claims)
    monkeypatch.setattr(service.survey_answers, "stored", lambda *args, **kwargs: {})
    monkeypatch.setattr(service.survey_answers, "stored_resolved", lambda *args, **kwargs: {})
    assert set(service._dietary_requirements(Connection(), **OWNER)) == {"halal", "vegetarian", "allergy:peanut"}


def test_staged_diet_is_enforced_in_both_preview_and_apply(monkeypatch):
    service = importlib.import_module("app.domains.travel_ops.components.intake.social_dining")
    real_requirements = service._dietary_requirements
    service, conn = setup(monkeypatch, links=[wish()], items=[meal(0)],
        search=lambda *args, **kwargs: {"results": [branch("가상식당", "place:one")]})
    monkeypatch.setattr(service, "_dietary_requirements", real_requirements)
    class Cursor:
        def execute(self, sql, params): pass
        def fetchone(self): return (None, conn.state["revision"])
    @contextmanager
    def cursor(): yield Cursor()
    conn.cursor = cursor
    monkeypatch.setattr(service.pipeline, "_claims", lambda *args: [{"source_id": "generated",
        "field": "trip.constraints", "value": {"dietary": ["vegetarian"]}, "method": "rule"}])
    monkeypatch.setattr(service.survey_answers, "stored", lambda *args, **kwargs: {})
    monkeypatch.setattr(service.survey_answers, "stored_resolved", lambda *args, **kwargs: {})
    monkeypatch.setattr(service.dining_ledger, "find_by_name", lambda *args, **kwargs: None)
    monkeypatch.setattr(service.dining_ledger, "state", lambda *args, **kwargs: None)
    held = service.preview(conn, **OWNER, revision=3, now=NOW)
    assert held["changes"] == [] and held["unplaced"][0]["reason"] == "unknown_dietary"
    monkeypatch.setattr(service.dining_ledger, "state", lambda *args, **kwargs: {
        "source": "dining_ledger", "available": True, "linked": True, "dietary": ["vegetarian"]})
    ready = service.preview(conn, **OWNER, revision=3, now=NOW)
    assert len(ready["changes"]) == 1
    monkeypatch.setattr(service.dining_ledger, "state", lambda *args, **kwargs: None)
    with pytest.raises(service.pipeline.IntakeConflict) as caught:
        service.apply(conn, **OWNER, revision=3, proposal_id=ready["proposal_id"])
    assert caught.value.code == "unknown_dietary" and conn.state["edits"] == 0

"""SNS 희망 식당: 소유 경계, 실제 장소 선택, 변경안의 무저장/단일 적용."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import importlib
from zoneinfo import ZoneInfo

import pytest


OWNER = dict(tenant_id="tenant", customer_id="customer", intake_id="intake")
NOW = datetime(2026, 10, 15, 9, tzinfo=ZoneInfo("Asia/Seoul"))


def restaurant(key="a", *, priority="if_fits", restaurants=None):
    return {"key": key, "source_urls": [f"https://www.youtube.com/watch?v={key}"],
            "platform": "youtube", "status": "identified", "reason": None,
            "restaurants": restaurants or [{"name": key, "area": "서울", "branch": None}],
            "priority": priority, "checked_at": "2026-10-15T09:00:00+09:00"}


def meal(number, start="12:00", **extra):
    return {"id": f"0-{number}", "source_id": "source", "index": number,
            "title": "점심", "kind": "dining", "date": "2026-10-15",
            "starts_at": start, "ends_at": f"{int(start[:2]) + 1:02d}:00", "locked": False,
            "place": None, "rows": [], **extra}


def match(name, *, ref=None, result="ok", fits=True):
    return {"place": {"name": name, "ref": ref or f"place:{name}", "source": "places",
                      "kind": "dining", "address": "서울 종로구", "latitude": 37.57, "longitude": 126.98},
            "fits": fits, "status": "ok", "rows": [
                {"row": "place", "result": "ok", "text": "찾음"},
                {"row": "hours", "result": result, "text": "영업시간"},
                {"row": "closed", "result": "ok", "text": "휴무 아님"}]}


class MemoryConnection:
    """DB 저장점의 역할만 대체한다. 일정/후보 서비스 로직은 실제 부품을 실행한다."""
    def __init__(self, links, items):
        self.state = {"revision": 3, "links": deepcopy(links), "proposal": None, "applied": {},
                      "review": {"items": deepcopy(items), "moves": [], "ready": True}, "edits": 0}

    @contextmanager
    def transaction(self, **kwargs):
        before = deepcopy(self.state)
        try:
            yield
        except BaseException:
            self.state = before
            raise


def setup(monkeypatch, *, links=None, items=None, search=None, edit_effect=None):
    svc = importlib.import_module("app.domains.travel_ops.components.intake.social_dining")
    conn = MemoryConnection(links or [], items or [])
    monkeypatch.setattr(svc, "_owner", lambda conn, **kw: {"status": "review", "revision": conn.state["revision"]})
    monkeypatch.setattr(svc, "_load", lambda conn, **kw: deepcopy({k: conn.state[k] for k in ("links", "proposal", "applied")}))

    def save(conn, *, data, **kw):
        for key in ("links", "proposal", "applied"):
            conn.state[key] = deepcopy(data[key])
    monkeypatch.setattr(svc, "_save", save)
    monkeypatch.setattr(svc, "_limits", lambda: {"max_preview_pairs": 50, "max_links": 20})
    monkeypatch.setattr(svc, "_now", lambda: NOW)
    monkeypatch.setattr(svc, "_dietary_requirements", lambda *a, **kw: ())

    def current(conn, *, revision=None, **kw):
        if revision is not None and revision != conn.state["revision"]:
            raise svc.pipeline.IntakeConflict("stale_revision", "낡은 판")
        return {"status": "review", "revision": conn.state["revision"]}, deepcopy(conn.state["review"])
    monkeypatch.setattr(svc.pipeline, "current_review", current)

    def edit(conn, *, revision, edits, **kw):
        if revision != conn.state["revision"]:
            raise svc.pipeline.IntakeConflict("stale_revision", "낡은 판")
        for change in edits:
            index = int(change["field"].split("[")[1].split("]")[0])
            field = change["field"].rsplit(".", 1)[1]
            item = next(i for i in conn.state["review"]["items"] if i["index"] == index)
            item[field] = deepcopy(change["value"])
            if field == "place":
                item["rows"] = match(change["value"]["name"])["rows"]
        conn.state["revision"] += 1
        conn.state["edits"] += 1
        if edit_effect:
            edit_effect(conn)
        return conn.state["revision"]
    monkeypatch.setattr(svc.pipeline, "edit", edit)
    monkeypatch.setattr(svc.pipeline, "view", lambda conn, **kw: {
        "revision": conn.state["revision"], "check": {"ready": True}, "review": deepcopy(conn.state["review"])})
    monkeypatch.setattr(svc.candidates, "search", search or (lambda *a, query, **kw: {"results": [match(query.split()[0])]}))
    return svc, conn


def test_resolve_keeps_existing_links_and_never_changes_the_schedule(monkeypatch):
    svc, conn = setup(monkeypatch, links=[restaurant("old")], items=[meal(0)])
    conn.state["proposal"] = {"proposal_id": "obsolete"}
    monkeypatch.setattr(svc.social_links, "resolve_links", lambda entries, **kw: [restaurant("new")])
    got = svc.resolve(conn, **OWNER, entries=[{"url": "https://youtu.be/new"}])
    assert [link["key"] for link in got["links"]] == ["old", "new"]
    assert got["revision"] == 3 and conn.state["edits"] == 0
    assert conn.state["proposal"] is None


def test_a_recovered_link_does_not_keep_the_failure_of_the_earlier_attempt(monkeypatch):
    # [2026-10-15 브라우저 실측] 실패한 링크를 다시 보내 식당을 읽었는데 앞 시도의 response_too_large 가 남아 있었다.
    failed = {**restaurant("same"), "restaurants": [], "status": "failed", "reason": "model_failed",
              "source_failure": "response_too_large", "placement_status": "waiting"}
    svc, conn = setup(monkeypatch, links=[failed], items=[meal(0)])
    monkeypatch.setattr(svc.social_links, "resolve_links", lambda entries, **kw: [restaurant("same")])
    got = svc.resolve(conn, **OWNER, entries=[{"url": "https://youtu.be/same"}])
    link = got["links"][0]
    assert link["status"] == "identified" and link["reason"] is None
    assert "source_failure" not in link
    assert link["placement_status"] == "waiting"


def test_update_refuses_a_place_reference_that_the_server_never_saved(monkeypatch):
    svc, conn = setup(monkeypatch, links=[restaurant()])
    with pytest.raises(svc.pipeline.IntakeRejected) as exc:
        svc.update(conn, **OWNER, key="a", selected_ref="place:someone-else")
    assert exc.value.code == "invalid_place_choice"
    assert conn.state["links"][0].get("selected_ref") is None


def test_selecting_an_extracted_restaurant_invalidates_old_place_choices_and_proposal(monkeypatch):
    link = restaurant(restaurants=[{"name": "a"}, {"name": "b"}])
    link.update(choices=[match("a")["place"]], selected_ref="place:a")
    svc, conn = setup(monkeypatch, links=[link])
    conn.state["proposal"] = {"proposal_id": "old"}
    got = svc.update(conn, **OWNER, key="a", restaurant_index=1, priority="must")
    assert got["links"][0]["restaurant_index"] == 1
    assert got["links"][0].get("selected_ref") is None
    assert got["links"][0]["choices"] == [] and conn.state["proposal"] is None


def test_empty_schedule_retains_wishes_with_an_explicit_reason(monkeypatch):
    svc, conn = setup(monkeypatch, links=[restaurant(priority="must")])
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert got["changes"] == [] and got["proposal_id"] is None
    assert got["unplaced"][0]["reason"] == "no_meal_slots"
    assert got["unplaced"][0]["priority"] == "must" and len(got["links"]) == 1


def test_multiple_extracted_restaurants_are_not_silently_selected(monkeypatch):
    svc, conn = setup(monkeypatch, links=[restaurant(restaurants=[{"name": "a"}, {"name": "b"}])], items=[meal(0)])
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert not got["changes"] and got["unplaced"][0]["reason"] == "restaurant_choice_required"


def test_multiple_real_branches_require_selection_even_if_one_is_nearer(monkeypatch):
    def search(*a, **kw):
        return {"results": [match("a 서울역점", ref="place:seoul"), match("a 종로점", ref="place:jongno")]}
    svc, conn = setup(monkeypatch, links=[restaurant()], items=[meal(0)], search=search)
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert got["changes"] == [] and got["unplaced"][0]["reason"] == "place_choice_required"
    assert {choice["ref"] for choice in got["links"][0]["choices"]} == {"place:seoul", "place:jongno"}
    svc.update(conn, **OWNER, key="a", selected_ref="place:jongno")
    chosen = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert chosen["changes"][0]["to"]["ref"] == "place:jongno"


def test_the_same_shop_from_two_providers_is_one_choice_not_two_branches(monkeypatch):
    # [2026-10-15 브라우저 실측] 장소 목록의 「우래옥」과 카카오의 「우래옥 본점」(같은 주소 · 좌표 조금 다름)이 지점 둘로 보였다.
    def search(*a, **kw):
        ledger = match("우래옥", ref="place:ledger")
        kakao = match("우래옥 본점", ref="kakao:1")
        kakao["place"].update(latitude=37.5685, longitude=126.9985, source="kakao")
        ledger["place"].update(latitude=37.5690, longitude=126.9990)          # 약 70m
        return {"results": [ledger, kakao]}
    svc, conn = setup(monkeypatch, links=[restaurant(restaurants=[{"name": "우래옥", "area": None, "branch": None}])],
                      items=[meal(0)], search=search)
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert [choice["ref"] for choice in got["links"][0]["choices"]] == ["place:ledger"]
    assert got["changes"] and got["changes"][0]["to"]["ref"] == "place:ledger"


def test_same_road_address_cannot_merge_conflicting_provider_coordinates(monkeypatch):
    # [2026-10-15 브라우저 실측] 카카오 「명동교자 명동역점 신관 본점」 · 장소 목록 「명동교자 본점」 — 둘 다 퇴계로 129.
    def search(*a, **kw):
        ledger, kakao = match("명동교자 본점", ref="place:main"), match("명동교자 명동역점 신관 본점", ref="kakao:main")
        other = match("명동교자 분점", ref="place:annex")
        ledger["place"]["address"] = "서울특별시 중구 퇴계로 129, 명동교자 (충무로2가)"
        kakao["place"].update(address="서울 중구 퇴계로 129", latitude=37.5610)    # 좌표로는 1km 넘게 어긋난 제공자 값
        other["place"]["address"] = "서울특별시 중구 명동10길 29 (명동2가)"
        return {"results": [ledger, kakao, other]}
    svc, conn = setup(monkeypatch, links=[restaurant(restaurants=[{"name": "명동교자", "area": None, "branch": None}])],
                      items=[meal(0)], search=search)
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert [choice["ref"] for choice in got["links"][0]["choices"]] == ["place:main", "kakao:main", "place:annex"]
    assert got["changes"] == [] and got["unplaced"][0]["reason"] == "place_choice_required"


def test_merged_duplicates_keep_the_entry_that_passed_the_checks(monkeypatch):
    # [2026-10-15 브라우저 실측] 합친 선택지가 운영시간 없는 카카오 쪽으로 남아 전체 검증을 통과하지 못했다.
    def search(*a, **kw):
        kakao = match("명동교자 본점", ref="kakao:main", result="unknown", fits=False)
        kakao["place"].update(address="서울 중구 퇴계로 129", source="kakao")
        ledger = match("명동교자 본점", ref="place:main")
        ledger["place"]["address"] = "서울특별시 중구 퇴계로 129"
        return {"results": [kakao, ledger]}
    svc, conn = setup(monkeypatch, links=[restaurant(restaurants=[{"name": "명동교자", "area": None, "branch": None}])],
                      items=[meal(0)], search=search)
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert [choice["ref"] for choice in got["links"][0]["choices"]] == ["place:main"]


def test_a_meal_already_holding_a_chosen_wish_is_not_offered_to_another_wish(monkeypatch):
    # [2026-10-15 브라우저 실측] 점심에 넣은 「꼭 가기」 우래옥을 다음 반영안이 명동교자로 바꾸려 했다.
    placed = match("old")["place"]
    old = {**restaurant("old", priority="must"), "selected_ref": placed["ref"], "choices": [placed],
           "status": "confirmed", "placement_status": "applied"}
    svc, conn = setup(monkeypatch, links=[old, restaurant("new")], items=[meal(0, place=placed), meal(1, "18:00")])
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert [change["item_id"] for change in got["changes"]] == ["0-1"]
    targeted = svc.preview(conn, **OWNER, revision=3, now=NOW, target_item_id="0-0")     # 고객이 그 식사를 직접 고르면 바꿀 수 있다
    assert [change["item_id"] for change in targeted["changes"]] == ["0-0"]


def test_a_wish_already_on_the_itinerary_keeps_its_branch_and_is_not_asked_again(monkeypatch):
    # [2026-10-15 브라우저 실측] 점심에 넣은 명동교자 분점이, 그 점심이 검색에서 빠지자 고른 지점을 잃고 「골라 주세요」로 돌아갔다.
    placed = match("old")["place"]
    old = {**restaurant("old"), "selected_ref": placed["ref"], "choices": [placed], "status": "confirmed"}
    svc, conn = setup(monkeypatch, links=[old], items=[meal(0, place=placed), meal(1, "18:00")],
                      search=lambda *a, **kw: {"results": []})
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert got["unplaced"][0]["reason"] == "already_scheduled"
    assert got["links"][0]["selected_ref"] == placed["ref"] and got["links"][0]["status"] == "confirmed"


def test_a_chosen_branch_missing_from_this_search_is_kept_and_reported(monkeypatch):
    # [2026-10-15] 고른 지점이 이번 검색 결과에 없다고 고객의 선택을 지우지 않는다 — 그 후보만 보류하고 이유를 보인다.
    chosen = match("a 종로점", ref="place:jongno")["place"]
    picked = {**restaurant(), "selected_ref": "place:jongno", "choices": [chosen], "status": "confirmed"}
    svc, conn = setup(monkeypatch, links=[picked], items=[meal(0)],
                      search=lambda *a, **kw: {"results": [match("a 서울역점", ref="place:seoul")]})
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    link = got["links"][0]
    assert got["changes"] == [] and got["unplaced"][0]["reason"] == "selected_place_unavailable"
    assert link["selected_ref"] == "place:jongno"
    assert "place:jongno" in {choice["ref"] for choice in link["choices"]}


def test_same_name_different_branch_labels_stay_separate_even_when_close(monkeypatch):
    def search(*a, **kw):
        main, annex = match("우래옥 본점", ref="kakao:main"), match("우래옥 별관", ref="kakao:annex")
        annex["place"].update(latitude=37.5701)                                 # 약 30m
        return {"results": [main, annex]}
    svc, conn = setup(monkeypatch, links=[restaurant(restaurants=[{"name": "우래옥", "area": None, "branch": None}])],
                      items=[meal(0)], search=search)
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert {choice["ref"] for choice in got["links"][0]["choices"]} == {"kakao:main", "kakao:annex"}
    assert got["unplaced"][0]["reason"] == "place_choice_required"


def test_locked_and_already_started_meals_cannot_be_changed(monkeypatch):
    svc, conn = setup(monkeypatch, links=[restaurant()], items=[meal(0, "08:00"), meal(1, locked=True)])
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert got["changes"] == [] and got["unplaced"][0]["reason"] == "no_future_meal_slots"


def test_unknown_opening_facts_do_not_pass_even_when_existing_search_says_fits(monkeypatch):
    svc, conn = setup(monkeypatch, links=[restaurant()], items=[meal(0)],
                      search=lambda *a, **kw: {"results": [match("a", result="unknown", fits=True)]})
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert got["changes"] == [] and got["unplaced"][0]["reason"] == "unknown_facts"


def test_batch_matching_keeps_must_wish_and_uses_an_alternative_slot_for_flexible_wish(monkeypatch):
    def search(*a, query, item, **kw):
        name = query.split()[0]
        return {"results": [match(name, fits=not (name == "b" and item["id"] == "0-1"))]}
    svc, conn = setup(monkeypatch, links=[restaurant("a", priority="must"), restaurant("b"), restaurant("c")],
                      items=[meal(0), meal(1, "18:00")], search=search)
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert {(c["key"], c["item_id"]) for c in got["changes"]} == {("a", "0-1"), ("b", "0-0")}
    assert [u["key"] for u in got["unplaced"]] == ["c"]
    assert conn.state["revision"] == 3 and conn.state["edits"] == 0
    assert all(i["place"] is None for i in conn.state["review"]["items"])


def test_preview_rolls_back_if_direct_schedule_moves_an_activity(monkeypatch):
    activity = meal(1, "14:00", kind="activity", title="경복궁")
    def move_activity(conn):
        conn.state["review"]["items"][1]["starts_at"] = "14:20"
    svc, conn = setup(monkeypatch, links=[restaurant()], items=[meal(0), activity], edit_effect=move_activity)
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert not got["changes"] and got["unplaced"][0]["reason"] == "activity_change_required"
    assert conn.state["review"]["items"][1]["starts_at"] == "14:00" and conn.state["revision"] == 3


def test_apply_uses_only_the_stored_proposal_and_is_idempotent(monkeypatch):
    svc, conn = setup(monkeypatch, links=[restaurant()], items=[meal(0)])
    proposal = svc.preview(conn, **OWNER, revision=3, now=NOW)
    got = svc.apply(conn, **OWNER, revision=3, proposal_id=proposal["proposal_id"])
    replay = svc.apply(conn, **OWNER, revision=3, proposal_id=proposal["proposal_id"])
    assert got["revision"] == replay["revision"] == 4
    assert conn.state["edits"] == 1 and conn.state["review"]["items"][0]["place"]["name"] == "a"
    assert conn.state["links"][0]["placement_status"] == "applied"


def test_candidate_change_invalidates_a_previously_built_proposal(monkeypatch):
    svc, conn = setup(monkeypatch, links=[restaurant()], items=[meal(0)])
    proposal = svc.preview(conn, **OWNER, revision=3, now=NOW)
    svc.update(conn, **OWNER, key="a", priority="must")
    with pytest.raises(svc.pipeline.IntakeConflict) as exc:
        svc.apply(conn, **OWNER, revision=3, proposal_id=proposal["proposal_id"])
    assert exc.value.code == "proposal_not_found" and conn.state["edits"] == 0


def test_stale_revision_and_now_invalid_validation_cannot_apply(monkeypatch):
    svc, conn = setup(monkeypatch, links=[restaurant()], items=[meal(0)])
    proposal = svc.preview(conn, **OWNER, revision=3, now=NOW)
    conn.state["revision"] = 4
    with pytest.raises(svc.pipeline.IntakeConflict) as exc:
        svc.apply(conn, **OWNER, revision=3, proposal_id=proposal["proposal_id"])
    assert exc.value.code == "stale_revision" and conn.state["edits"] == 0
    conn.state["revision"] = 3
    monkeypatch.setattr(svc.pipeline, "view", lambda *a, **kw: {"check": {"ready": False}, "review": {"items": []}})
    with pytest.raises(svc.pipeline.IntakeConflict):
        svc.apply(conn, **OWNER, revision=3, proposal_id=proposal["proposal_id"])
    assert conn.state["revision"] == 3 and conn.state["edits"] == 0


def test_real_ownership_query_uses_both_tenant_and_customer():
    svc = importlib.import_module("app.domains.travel_ops.components.intake.social_dining")
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, args):
            assert "tenant_id=%s" in sql and "customer_id=%s" in sql
            self.row = ("review", 3) if args == ("tenant", "intake", "customer") else None
        def fetchone(self): return self.row
    class Connection:
        def cursor(self): return Cursor()
    with pytest.raises(LookupError):
        svc.list_links(Connection(), **{**OWNER, "customer_id": "other"})


def test_explicit_branch_cannot_be_replaced_by_a_different_branch(monkeypatch):
    link = restaurant(restaurants=[{"name": "식당가", "branch": "서초점", "area": "서울"}])
    svc, conn = setup(monkeypatch, links=[link], items=[meal(0)],
                      search=lambda *a, **kw: {"results": [match("식당가 종로점")]})
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert got["changes"] == [] and got["unplaced"][0]["reason"] == "branch_unverified"


def test_internal_place_id_omitted_by_public_view_is_not_an_activity_change(monkeypatch):
    activity = meal(1, "14:00", kind="activity", title="경복궁",
                    place={"name": "경복궁", "latitude": 37.58, "longitude": 126.97, "place_id": "private-id"})
    svc, conn = setup(monkeypatch, links=[restaurant()], items=[meal(0), activity])
    def public_view(conn, **kw):
        review = deepcopy(conn.state["review"])
        for item in review["items"]:
            if item.get("place"):
                item["place"].pop("place_id", None)
        return {"revision": conn.state["revision"], "check": {"ready": True}, "review": review}
    monkeypatch.setattr(svc.pipeline, "view", public_view)
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert len(got["changes"]) == 1 and got["unplaced"] == []
    assert conn.state["review"]["items"][1]["place"]["place_id"] == "private-id"


def test_missing_revalidated_hours_cannot_be_saved_as_success(monkeypatch):
    def lose_rows(conn):
        conn.state["review"]["items"][0]["rows"] = []
    svc, conn = setup(monkeypatch, links=[restaurant()], items=[meal(0)], edit_effect=lose_rows)
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert got["changes"] == [] and got["unplaced"][0]["reason"] == "full_validation_failed"
    assert conn.state["revision"] == 3


def test_same_restaurant_links_preserve_all_provenance_without_duplicate_placement(monkeypatch):
    a, b = restaurant("a"), restaurant("b", restaurants=[{"name": "a"}])
    svc, conn = setup(monkeypatch, links=[a, b], items=[meal(0), meal(1, "18:00")])
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert len(got["changes"]) == 1
    primary = next(link for link in got["links"] if link["key"] == got["changes"][0]["key"])
    assert set(primary["source_urls"]) == set(a["source_urls"] + b["source_urls"])
    assert len(got["links"]) == 2 and got["links"][1]["duplicate_of"] == "a"


def test_reopened_intake_inherits_only_same_owner_confirmed_wishes_and_no_old_proposal():
    svc = importlib.import_module("app.domains.travel_ops.components.intake.social_dining")
    old = restaurant()
    old.update(placement_status="applied", placement_reason=None)
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, args):
            self.row = None
            if "JOIN trip_intakes previous" in sql:
                assert "current.customer_id=previous.customer_id" in sql
                assert "current.tenant_id=previous.tenant_id" in sql
                assert "previous.status='confirmed'" in sql
                assert args == ("tenant", "new-intake")
                self.row = ([old],)
        def fetchone(self): return self.row
    class Connection:
        def cursor(self): return Cursor()
    got = svc._load(Connection(), tenant_id="tenant", intake_id="new-intake")
    assert got["links"][0]["source_urls"] == old["source_urls"]
    assert got["links"][0]["placement_status"] == "waiting"
    assert got["proposal"] is None and got["applied"] == {}


@pytest.mark.parametrize("reserved", [{"booked": True}, {"booking_no": "SEOUL-RESTAURANT-42"}])
def test_existing_restaurant_booking_is_not_relabelled_as_the_sns_restaurant(monkeypatch, reserved):
    svc, conn = setup(monkeypatch, links=[restaurant()], items=[meal(0, **reserved)])
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert not got["changes"] and got["unplaced"][0]["reason"] == "no_future_meal_slots"


@pytest.mark.parametrize("facts,reason", [
    (None, "unknown_dietary"),
    ({"available": True, "linked": True, "source": "dining_ledger", "dietary": [],
      "dietary_absent": ["vegetarian"]}, "dietary_conflict"),
])
def test_required_diet_cannot_be_inferred_from_opening_hours(monkeypatch, facts, reason):
    svc, conn = setup(monkeypatch, links=[restaurant()], items=[meal(0)])
    monkeypatch.setattr(svc, "_dietary_requirements", lambda *a, **kw: ("vegetarian",))
    monkeypatch.setattr(svc.dining_ledger, "state", lambda *a, **kw: facts)
    monkeypatch.setattr(svc.dining_ledger, "find_by_name", lambda *a, **kw: None)
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert not got["changes"] and got["unplaced"][0]["reason"] == reason


def test_confirmed_dietary_fact_passes_but_is_rechecked_before_applying(monkeypatch):
    svc, conn = setup(monkeypatch, links=[restaurant()], items=[meal(0)])
    monkeypatch.setattr(svc, "_dietary_requirements", lambda *a, **kw: ("halal",))
    monkeypatch.setattr(svc.dining_ledger, "state", lambda *a, **kw: {
        "available": True, "linked": True, "source": "dining_ledger", "dietary": ["halal"], "dietary_absent": []})
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert len(got["changes"]) == 1
    monkeypatch.setattr(svc.dining_ledger, "state", lambda *a, **kw: None)
    monkeypatch.setattr(svc.dining_ledger, "find_by_name", lambda *a, **kw: None)
    with pytest.raises(svc.pipeline.IntakeConflict) as exc:
        svc.apply(conn, **OWNER, revision=3, proposal_id=got["proposal_id"])
    assert exc.value.code == "unknown_dietary" and conn.state["edits"] == 0


def test_original_diet_and_resolved_intake_food_conditions_are_both_retained(monkeypatch):
    svc = importlib.import_module("app.domains.travel_ops.components.intake.social_dining")
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, args):
            assert "customer_id" in sql and "tenant_id" in sql
        def fetchone(self):
            return ({"dietary": ["halal"], "allergies": ["peanut"], "survey": {
                "priority_details": {"food": ["taste"]}}}, 3)
    class Connection:
        def cursor(self): return Cursor()
    monkeypatch.setattr(svc.survey_answers, "stored", lambda *a, **kw: {"food": "vegetarian"})
    monkeypatch.setattr(svc.survey_answers, "stored_resolved", lambda *a, **kw: {})
    monkeypatch.setattr(svc.survey_answers, "to_survey", lambda *a, **kw: {"priority_details": {"food": ["vegetarian"]}})
    monkeypatch.setattr(svc.pipeline, "_claims", lambda *a: [])
    got = svc._dietary_requirements(Connection(), **OWNER)
    assert set(got) == {"halal", "vegetarian", "allergy:peanut"}


def test_preview_uses_model_order_only_for_verified_slots_and_exposes_planning_audit(monkeypatch):
    svc, conn = setup(monkeypatch, links=[restaurant()], items=[meal(0), meal(1, "18:00")])
    class Chat:
        def json(self, system, user):
            return {"rankings": [{"key": "a", "slot_ids": ["0-1", "0-0"]}]}
    got = svc.preview(conn, **OWNER, revision=3, now=NOW, chat=Chat())
    assert got["changes"][0]["item_id"] == "0-1"
    assert got["planning"]["mode"] == "model" and got["planning"]["prompt_hash"]
    assert conn.state["proposal"]["planning"] == got["planning"]


def test_estimated_or_unverified_connected_move_is_not_treated_as_a_verified_arrival(monkeypatch):
    def uncertain_move(conn):
        conn.state["review"]["moves"] = [{"from": "0-0", "to": "0-1", "status": "keep",
            "basis": "estimate", "rows": [
                {"row": "route", "result": "warn", "text": "직선거리 추정"},
                {"row": "arrival", "result": "ok", "text": "추정 도착"}]}]
    svc, conn = setup(monkeypatch, links=[restaurant()], items=[meal(0), meal(1, "14:00", kind="activity")],
                      edit_effect=uncertain_move)
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert got["changes"] == [] and got["unplaced"][0]["reason"] == "full_validation_failed"


def test_batch_tries_another_verified_meal_when_first_would_move_an_activity(monkeypatch):
    def first_slot_would_move_activity(conn):
        if conn.state["review"]["items"][0]["place"]:
            conn.state["review"]["items"][2]["starts_at"] = "14:20"
    svc, conn = setup(monkeypatch, links=[restaurant()], items=[meal(0), meal(1, "18:00"), meal(2, "14:00", kind="activity")],
                      edit_effect=first_slot_would_move_activity)
    got = svc.preview(conn, **OWNER, revision=3, now=NOW)
    assert len(got["changes"]) == 1 and got["changes"][0]["item_id"] == "0-1"
    assert got["unplaced"] == [] and conn.state["revision"] == 3

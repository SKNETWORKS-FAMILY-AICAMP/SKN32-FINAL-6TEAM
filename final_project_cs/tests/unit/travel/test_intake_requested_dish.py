import pytest

from app.domains.travel_ops.components.intake import candidates, autofix, prepared


def place(name):
    return {"name": name, "latitude":37.57, "longitude":126.98, "kind":"dining", "category":"음식점", "source":"places"}


def item(title="라멘"):
    return {"id":"m", "title":title, "kind":"dining", "place_state":"needs_choice", "place":None,
            "date":"2026-10-24", "starts_at":"18:00", "ends_at":"19:00", "parts":None}


@pytest.mark.parametrize("available,expected", [(True,["시험라멘"]),(False,[])])
def test_alternatives_keep_requested_ramen_even_after_a_pick(monkeypatch, available, expected):
    meal = {**item(), "place_state":"customer", "place":place("원래라멘")}
    monkeypatch.setattr(candidates, "reference", lambda *a:(37.57,126.98))
    monkeypatch.setattr(candidates, "_team_dining_places", lambda *a:[place("순대국"),place("들풀한상"),place("산띠")])
    monkeypatch.setattr(candidates, "_ledger_places", lambda *a, **k:[place("시험라멘")] if available else [])
    monkeypatch.setattr(candidates, "_kakao_places", lambda *a, **k:[])
    monkeypatch.setattr(candidates, "assess", lambda *a, **k:{"fits":True,"status":"ok","rows":[]})
    got = candidates.gather(None, tenant_id="t", review={"items":[meal]}, item=meal)
    assert [p["name"] for p, _ in got.pool] == expected
    if not available:
        assert "no_requested_dish" in got.notes


def test_route_fallback_does_not_reintroduce_another_menu(monkeypatch):
    monkeypatch.setattr(candidates, "_ledger_places", lambda *a, **k:[place("순대국"),place("시험라멘")])
    monkeypatch.setattr(candidates, "_kakao_places", lambda *a, **k:[])
    got = autofix._route_restaurants(None, "t", item(), [], {"place":place("박물관")}, None, None)
    assert [p["name"] for p in got] == ["시험라멘"]


def test_cached_pool_cannot_restore_an_unrelated_menu(monkeypatch):
    meal = item()
    monkeypatch.setattr(candidates, "reference", lambda *a:(37.57,126.98))
    monkeypatch.setattr(candidates, "assess", lambda *a, **k:{"fits":True,"status":"ok","rows":[]})
    got = candidates.regather(None, tenant_id="t", review={"items":[meal]}, item=meal,
                              places=[place("순대국")], notes=[])
    assert got.pool == []
    assert "no_requested_dish" in got.notes


def test_pre_fix_prepared_response_is_invalidated_for_a_menu_request():
    meal = item()
    review = {"items":[meal]}
    old = prepared._sha([prepared._place_sig(None), meal["date"], None, meal["starts_at"], meal["ends_at"],
                         "dining", "needs_choice", None, "라멘"])
    _, before, after = prepared.signatures(review, meal)
    assert prepared.usable({"item_sig":old,"before_sig":before,"after_sig":after}, review, meal)[0] == "none"


@pytest.mark.parametrize("title", ["점심", "토속촌삼계탕"])
def test_generic_meal_and_named_restaurant_do_not_invent_a_hard_menu(monkeypatch, title):
    monkeypatch.setattr(candidates, "_ledger_places", lambda *a, **k:[place("국밥")])
    monkeypatch.setattr(candidates, "_kakao_places", lambda *a, **k:[])
    assert autofix._route_restaurants(None, "t", item(title), [], {"place":place("박물관")}, None, None)


def test_pork_cutlet_spelling_is_preserved(monkeypatch):
    monkeypatch.setattr(candidates, "_ledger_places", lambda *a, **k:[place("시험돈카츠"),place("국밥")])
    monkeypatch.setattr(candidates, "_kakao_places", lambda *a, **k:[])
    assert [p["name"] for p in autofix._route_restaurants(None, "t", item("돈가스"), [], {"place":place("박물관")}, None, None)] == ["시험돈카츠"]

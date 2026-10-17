"""원문 예약 장소가 확인됐을 때만 모델의 이름 누락 질문을 생략한다."""
from app.domains.travel_ops.components.intake.prefill import model_gaps


def claim():
    return {"source_id": "plan", "field": "reading.agent", "value": {"used": True, "missing": ["booked_place_name"]}}


def booked(*, source="plan", place=None):
    return {"source_id": source, "booked": True, "place": place}


def test_resolved_booked_place_does_not_ask_for_its_name_again():
    assert model_gaps([claim()], [booked(place={"name": "N서울타워"})]) == []


def test_another_booked_item_without_a_place_keeps_the_question():
    questions = model_gaps([claim()], [booked(place={"name": "N서울타워"}), booked()])
    assert [q.kind for q in questions] == ["booked_place_name"]


def test_no_booked_item_keeps_the_question():
    assert [q.kind for q in model_gaps([claim()], [])] == ["booked_place_name"]


def test_resolved_booking_from_another_source_does_not_hide_the_question():
    questions = model_gaps([claim()], [booked(source="other", place={"name": "N서울타워"})])
    assert [q.kind for q in questions] == ["booked_place_name"]

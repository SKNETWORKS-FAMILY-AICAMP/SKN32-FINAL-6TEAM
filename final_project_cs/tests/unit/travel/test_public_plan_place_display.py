"""공유 계획서에는 원문 제목과 실제 선택 장소가 함께 보인다."""
from app.domains.travel_ops.entry.trip_api import _render_plan


def render(title="호텔", place="서울 시험호텔"):
    return _render_plan({"title":"서울 여행","version":1,"history":[],"items":[{
        "starts_at":"2026-10-24T09:00:00+09:00","ends_at":"2026-10-24T09:30:00+09:00",
        "title":title,"place":place,"changed":False,"other_options":[]}]})


def test_chosen_hotel_is_visible_without_changing_the_original_title():
    html = render()
    assert '<div class="title">호텔 ' in html
    assert '<div class="others">서울 시험호텔</div>' in html


def test_same_name_and_missing_place_do_not_add_a_duplicate():
    assert render("경복궁","경복궁").count("경복궁") == 1
    assert '<div class="others">' not in render("지하철 3호선",None)


def test_external_place_name_is_escaped():
    html = render(place='<script>alert("x")</script> & 호텔')
    assert "<script>" not in html
    assert "&lt;script&gt;" in html and "&amp; 호텔" in html

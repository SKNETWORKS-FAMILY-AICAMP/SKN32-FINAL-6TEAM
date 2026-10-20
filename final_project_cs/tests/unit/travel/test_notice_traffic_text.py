"""복수 위험 안내에서 도로통제 내용 누락과 중복 보완을 막는다."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.planning.pending import _cause_text, traffic_detail_notice, unresolved_notice
from app.infrastructure.notify.discord import render


def facts():
    return [{"category": "weather_warning", "kind": "강풍주의보"},
            {"category": "disaster_msg", "kind": "강풍"},
            {"category": "traffic_control", "kind": "전체 차로 통제", "incident_id": "public-event-1",
             "road": "문화로", "message": "문화로 동문~서문 양방향 전면통제", "ends_at": "2026-10-18T23:00:00+09:00"}]


def item():
    return Item(item_id=uuid4(), seq=1, kind="activity", title="문화축제", place_id=None,
                starts_at=datetime(2026, 10, 18, 4, tzinfo=timezone.utc), ends_at=None)


def test_mixed_alert_retains_road_section_and_end_in_channel_text():
    payload = unresolved_notice(item=item(), causes=facts())
    text = render(payload)
    assert "강풍주의보" in text and "문화로 동문~서문 양방향 전면통제" in text and "23:00" in text
    assert "일정은 그대로" in text


def test_all_known_causes_and_unique_labels_are_preserved():
    assert _cause_text([{"kind": "강풍"}, {"kind": "강풍"}, {"kind": "road_closed"}]) == "강풍; 도로가 통제돼요"


def test_unknown_codes_stay_out_of_customer_text():
    assert _cause_text([{"kind": "private_unknown"}]) == "일정에 문제가 생겼어요"


def legacy():
    return {"kind": "no_alternate", "text": "강풍주의보. 일정은 그대로 두었어요.", "causes": facts()}


def test_legacy_delivered_message_gets_only_missing_current_road_fact():
    key, payload = traffic_detail_notice(item=item(), causes=facts(), previous=legacy())
    assert key and len(payload["causes"]) == 1
    assert "문화로 동문~서문" in render(payload) and "23:00" in render(payload)
    assert "강풍주의보" not in payload["text"]


def test_changed_check_time_and_distance_keep_same_repair_identity():
    one = facts(); two = deepcopy(one); two[-1].update(distance_m=123, confirmed_at="later")
    assert traffic_detail_notice(item=item(), causes=one, previous=legacy())[0] == traffic_detail_notice(item=item(), causes=two, previous=legacy())[0]


def test_newly_complete_notice_needs_no_followup():
    previous = unresolved_notice(item=item(), causes=facts())
    assert traffic_detail_notice(item=item(), causes=facts(), previous=previous) is None


def test_different_or_cleared_incident_is_never_replayed():
    other = facts(); other[-1]["incident_id"] = "different-event"
    assert traffic_detail_notice(item=item(), causes=other, previous=legacy()) is None
    assert traffic_detail_notice(item=item(), causes=[], previous=legacy()) is None


def test_other_notice_kinds_are_not_repaired():
    previous = legacy(); previous["kind"] = "change_notice"
    assert traffic_detail_notice(item=item(), causes=facts(), previous=previous) is None

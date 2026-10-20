"""안내 알림의 일정 목록은 id 문자열일 수도, 일정 객체일 수도 있다 — 둘 다 id 목록으로 바꾼다.

★2026-10-19 x600 운영: 위험 확인 안내(`risk_detected`)가 일정 객체 목록을 실어 보내
  발송 확인 질의가 「cannot adapt type 'dict'」로 실패했다(3건 dead_letter).
"""
from __future__ import annotations

from app.domains.travel_ops.components.watch.notice_routing import guidance_item_ids


def test_plain_id_strings_pass_through():
    assert guidance_item_ids(["a", "b"]) == ["a", "b"]


def test_item_objects_become_their_ids():
    items = [{"item_id": "11111111-1111-1111-1111-111111111111", "title": "강동선사문화축제", "causes": []},
             {"item_id": "22222222-2222-2222-2222-222222222222", "title": "점심"}]
    assert guidance_item_ids(items) == ["11111111-1111-1111-1111-111111111111",
                                        "22222222-2222-2222-2222-222222222222"]


def test_missing_ids_are_skipped_and_empty_is_empty():
    assert guidance_item_ids([{"title": "id 없음"}, None, ""]) == []
    assert guidance_item_ids(None) == []

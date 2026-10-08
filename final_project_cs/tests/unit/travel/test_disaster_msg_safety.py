# -*- coding: utf-8 -*-
"""재난문자 판정이 **심각한 사건을 놓치지 않고 훈련 · 해제는 거르는지** + 해제 문자 조회. `[결정 2026-10-06 사용자 — 재난 시 일정 정지]`

★지키려는 것
 ①전쟁 · 화산 폭발이 재해구분 「모르는 값」(기타 · 새 이름)으로 와도 본문 낱말(공습경보 · 화산 …)이 있으면 이상으로 센다 — 전에는 「모르는 구분」으로 빠졌다
 ②민방위 · 화산 · 원전 · 방사능 재해구분은 이상이다
 ③훈련 · 해제 문자는 이상이 아니다(전에는 훈련을 거르지 않았다)
 ④실종자 문자(기타 + 일상 낱말)는 여전히 아무것도 안 바꾼다 — 서울 전역의 일정이 실종자 문자 한 통으로 바뀌면 안 된다
 ⑤해제 문자 조회 — 창 안 · 지역 안만, 재해구분은 안 가리고, 샘플 기간 밖은 「모름」(None)

재현:

    python -m pytest tests/unit/travel/test_disaster_msg_safety.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.domains.travel_ops.ports.data_sources import disaster_msg
from app.domains.travel_ops.ports.data_sources.disaster_msg import judge, judge_released

KST = ZoneInfo("Asia/Seoul")
AT = datetime(2026, 9, 23, 10, 30, tzinfo=KST)
START = AT - timedelta(hours=6)


def _row(kind, text, *, step="긴급재난", minutes_before=20, regions=("서울특별시 전체",)):
    return {"created_at": AT - timedelta(minutes=minutes_before), "kind": kind, "step": step, "text": text, "regions": list(regions), "serial": "1"}


def _judge(*rows):
    return judge(list(rows), region="서울", district=None, window_start=START, at=AT)


def test_a_war_alert_is_counted_even_when_its_kind_is_not_in_the_list():
    messages, unclassified = _judge(_row("기타", "서울특별시 전역에 공습경보가 발령되었습니다.", step="위급재난"),
                                    _row("새재해", "백두산 화산이 분화했습니다."))
    assert [m["kind"] for m in messages] == ["기타", "새재해"] and unclassified == []     # 둘 다 이상으로 세고, 「모르는 구분」으로 빠지지 않는다


def test_civil_defense_volcano_nuclear_kinds_are_counted():
    messages, _ = _judge(_row("민방위", "경계경보 발령"), _row("화산", "화산 활동"), _row("원전", "원전 사고"), _row("방사능", "방사능 누출"))
    assert len(messages) == 4


def test_drills_and_releases_are_not_counted():
    messages, unclassified = _judge(_row("민방위", "오늘 14시 민방위 훈련 공습경보 발령 — 실제 상황이 아닙니다.", step="위급재난"),
                                    _row("민방위", "공습경보가 해제되었습니다.", step="위급재난"),
                                    _row("호우", "호우 통제가 완전 해제되었음"))
    assert messages == [] and unclassified == []


def test_an_everyday_missing_person_message_still_changes_nothing():
    messages, unclassified = _judge(_row("기타", "[서울경찰청] 노원구에서 실종된 ○○○씨를 찾습니다", step="안전안내"))
    assert messages == [] and unclassified == []


def test_other_regions_and_old_messages_are_left_out():
    messages, _ = _judge(_row("민방위", "공습경보", regions=("부산광역시 전체",)), _row("민방위", "공습경보", minutes_before=60 * 7))
    assert messages == []


def test_release_messages_are_found_by_window_and_region_and_any_kind():
    rows = [_row("민방위", "공습경보가 해제되었습니다.", minutes_before=5), _row("호우", "호우 통제 해제", minutes_before=8),
            _row("민방위", "공습경보 발령", minutes_before=15),                          # 해제가 아니다
            _row("민방위", "공습경보가 해제되었습니다.", regions=("부산광역시 전체",)),      # 다른 지역
            _row("민방위", "공습경보가 해제되었습니다.", minutes_before=60 * 9)]            # 창 밖
    found = judge_released(rows, region="서울", district=None, window_start=START, at=AT)
    assert sorted(f["kind"] for f in found) == ["민방위", "호우"] and all("해제" in f["text"] for f in found)


def test_the_sample_source_answers_unknown_outside_its_period():
    source = disaster_msg.DisasterMsgCsv(disaster_msg.DEFAULT_SAMPLE_PATH)
    assert source.released(region="서울", since=START, at=AT) is None                      # 샘플은 2023-09 — 「해제 없음」이라고 답하지 않는다
    first, last = source.coverage
    inside = source.released(region="서울", since=first, at=last)
    assert isinstance(inside, list)

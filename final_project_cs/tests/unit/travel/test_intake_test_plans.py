"""시험 단축 입력의 경계·서울 일정 원문을 검증한다."""
from datetime import date
import re

import pytest

from app.domains.travel_ops.components.intake import test_plans as plans
from app.domains.travel_ops.components.intake.rules import read_plan


@pytest.mark.parametrize("number,count", enumerate((6, 3, 2, 2, 3, 3, 3, 3, 3, 3, 7, 4, 2, 2, 2, 3), start=1))
def test_every_prepared_code_has_dated_readable_stops(monkeypatch, number, count):
    monkeypatch.setattr(plans, "operator_setting", lambda *_: True)
    text, meta = plans.expand(f"  TeSt{number} \n", tenant_id="unit", has_files=False, today=date(2026, 10, 11))
    read = read_plan(text)
    assert len(read.items) == count
    assert read.party_size == 4
    assert all(item.date and item.date >= "2026-10-18" for item in read.items)
    assert meta["code"] == f"test{number}"
    assert meta["mode"] == "prepared_text"
    assert "text" not in meta
    if number == 4:
        assert date.fromisoformat(read.items[0].date).weekday() == 1


@pytest.mark.parametrize("text", ("", "서울 test1 방문", "test1 메모", "test01", "test0", "test 1", "test１"))
def test_ordinary_text_is_not_replaced_or_reads_settings(monkeypatch, text):
    def forbidden(*_):
        raise AssertionError("ordinary text should not read a test setting")
    monkeypatch.setattr(plans, "operator_setting", forbidden)
    assert plans.expand(text, tenant_id="unit", has_files=False) == (text, None)


@pytest.mark.parametrize("text,files,enabled,code", (
    ("test52", False, True, "unknown_test_scenario"),          # `[2026-10-19]` test51 은 장소 종류 · 이동 말 확인 예시
    ("test100", False, True, "unknown_test_scenario"),
    ("test999999999999999999999", False, True, "unknown_test_scenario"),
    ("test1", True, True, "test_scenario_with_files"),
    ("test1", False, False, "test_scenarios_disabled"),
    ("test1rt", False, True, "live_test_not_ready"),
))
def test_reserved_inputs_fail_explicitly(monkeypatch, text, files, enabled, code):
    monkeypatch.setattr(plans, "operator_setting", lambda *_: enabled)
    with pytest.raises(plans.TestPlanRejected) as error:
        plans.expand(text, tenant_id="unit", has_files=files)
    assert error.value.code == code


def test_disabled_catalog_is_empty_and_operator_override_wins(monkeypatch):
    monkeypatch.setattr(plans, "operator_setting", lambda *_: False)
    assert plans.catalog("unit")["scenarios"] == []
    assert plans.catalog("unit")["enabled"] is False
    monkeypatch.setattr(plans, "operator_setting", lambda *_: None)
    assert len(plans.catalog("unit")["scenarios"]) == plans.TOTAL == 51


def test_normal_plans_have_known_places_end_times_and_generous_gaps(monkeypatch):
    monkeypatch.setattr(plans, "operator_setting", lambda *_: True)
    entries = plans.catalog("unit", today=date(2026, 10, 11))["scenarios"]
    assert {entry["category"] for entry in entries[:16]} == {"normal", "time", "hours", "place", "mobility", "input", "general"}
    assert [entry["code"] for entry in entries if entry["category"] == "normal"] == ["test13", "test14", "test15"]
    for entry in entries[12:15]:
        read = read_plan(entry["text"])
        assert all(item.end and item.title and "호텔" not in item.title.text for item in read.items)
        for before, after in zip(read.items, read.items[1:]):
            if before.date == after.date:
                def minutes(value):
                    hour, minute = map(int, value.split(":"))
                    return hour * 60 + minute
                assert minutes(after.start) - minutes(before.end) >= 180
        assert "실제 조회" in entry["expected"]


def test_the_lodging_plan_has_a_named_hotel_the_catalog_knows(monkeypatch):
    """test16 — 이름 있는 호텔 체크인이 든 일정. 호텔 이름은 장소 목록(관광공사 숙박)에 있는 그대로여야 숙소 항목으로 이어진다."""
    monkeypatch.setattr(plans, "operator_setting", lambda *_: True)
    entry = next(e for e in plans.catalog("unit", today=date(2026, 10, 11))["scenarios"] if e["code"] == "test16")
    assert entry["category"] == "general" and "숙소" in entry["name"]
    read = read_plan(entry["text"])
    assert [item.title.text for item in read.items if "호텔" in item.title.text] == ["더 플라자 호텔 서울 체크인"]


FORM_CODES = [f"test{n}" for n in range(17, 52)]             # `[2026-10-19]` test51 더함(실제 사례 「real」 형식)


def test_form_plans_use_the_reading_test_shape_names_and_cover_every_shape(monkeypatch):
    """test17~ — 분류는 계획 이해 시험지(`eval/intake_diverse`)의 형식 이름 그대로이고, 형식마다 짧음 · 보통/김이 다 있다."""
    from eval.intake_diverse.report import SHAPES

    monkeypatch.setattr(plans, "operator_setting", lambda *_: True)
    entries = plans.catalog("unit", today=date(2026, 10, 16))["scenarios"][16:]
    assert [e["code"] for e in entries] == FORM_CODES
    assert list(plans.FORM_CATEGORIES) == SHAPES
    assert [c for c in dict.fromkeys(e["category"] for e in entries)] == SHAPES
    for shape in SHAPES:
        sizes = {e["name"].split(" · ")[0] for e in entries if e["category"] == shape}
        assert "짧음" in sizes and sizes & {"보통", "김"}, (shape, sizes)
    assert len({e["name"] for e in entries}) == len(entries)
    assert any(e["text"].count("\n") >= 20 for e in entries)          # 하루 꽉 찬 · 여러 날짜리 긴 예시가 있다


@pytest.mark.parametrize("code", FORM_CODES)
def test_form_plan_expands_to_dated_seoul_text_without_tokens(monkeypatch, code):
    monkeypatch.setattr(plans, "operator_setting", lambda *_: True)
    text, meta = plans.expand(code.upper(), tenant_id="unit", has_files=False, today=date(2026, 10, 16))
    assert meta["code"] == code and meta["mode"] == "prepared_text" and meta["catalog_version"] == "seoul-text-v3"
    # `[2026-10-19]` test51 은 「지금 구조」가 아니라 고친 뒤 기대 결과를 적는다(실서버 확인용)
    assert re.match(r"10/16 지금 구조: |10/19 고친 뒤 기대: ", meta["expected"]) and "실제 조회" in meta["expected"]
    assert "@" not in text and 0 < len(text) < 2_000
    for found in re.findall(r"20\d\d-\d\d-\d\d", text):            # 적힌 날짜는 7일 뒤부터 최대 7일 안
        assert "2026-10-23" <= found <= "2026-10-29"
    assert not re.search(r"(?<![\d.:])([5-9]|\d\d)\s*명", text)       # 4명 이하(「19:00 명동」의 00 은 인원이 아니다)


def test_form_plan_dates_follow_today(monkeypatch):
    monkeypatch.setattr(plans, "operator_setting", lambda *_: True)
    text, _ = plans.expand("test20", tenant_id="unit", has_files=False, today=date(2026, 12, 28))
    assert text.startswith("1/4(월)\n") and "1/10(일)\n" in text

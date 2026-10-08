"""인허가 자료 폐업 대조(`scripts/dining/license_closure.py`)의 판정 규칙. `[2026-10-05]`"""
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(_HERE))), "scripts", "dining", "license_closure.py")


def _load():
    spec = importlib.util.spec_from_file_location("license_closure", _PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rec(name, state, closed="", road="서울특별시 강남구 도산대로 10, 2층 201호 (청담동)"):
    return {"종류": "일반", "관리번호": f"m-{name}-{state}", "상호": name, "상태": state, "폐업일": closed,
            "도로명": road, "지번": "", "허가일": "2020-01-01", "업태": "한식"}


def test_same_address_same_name_closed_only_is_closed():
    lc = _load()
    kind, found, _ = lc.judge("청담식당", [rec("청담식당", "폐업", "2026-03-01")])
    assert kind == "폐업" and found["폐업일"] == "2026-03-01"


def test_an_active_record_with_the_same_name_means_open():
    lc = _load()
    kind, _, _ = lc.judge("청담식당", [rec("청담식당", "폐업", "2020-01-01"), rec("청담식당", "영업/정상")])
    assert kind == "영업"


def test_another_shop_in_the_same_building_is_not_a_successor_but_the_same_unit_is():
    lc = _load()
    other_unit = rec("다른집", "영업/정상", road="서울특별시 강남구 도산대로 10, 3층 301호 (청담동)")
    assert lc.judge("청담식당", [rec("청담식당", "폐업", "2026-03-01"), other_unit])[0] == "폐업"
    same_unit = rec("새이름", "영업/정상")
    assert lc.judge("청담식당", [rec("청담식당", "폐업", "2026-03-01"), same_unit])[0] == "모름"     # 상호 변경일 수 있다


def test_no_record_or_different_names_is_unknown_not_closed():
    lc = _load()
    assert lc.judge("청담식당", [])[0] == "후보없음"
    assert lc.judge("청담식당", [rec("전혀다른이름", "폐업", "2026-03-01")])[0] == "모름"


def test_address_keys_ignore_floors_and_parentheses():
    lc = _load()
    assert lc.road_key("서울특별시 강남구 도산대로45길 10-5, 2층 (신사동)") == "강남구 도산대로45길 10-5"
    assert lc.jibun_key("서울특별시 금천구 시흥동 992-47") == "금천구 시흥동 992-47"
    assert lc.same_name("청담 식당", "청담식당 본점")

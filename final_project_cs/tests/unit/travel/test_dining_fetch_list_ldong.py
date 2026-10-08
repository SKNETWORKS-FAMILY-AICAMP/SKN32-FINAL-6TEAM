"""법정동 재수집(`scripts/dining/fetch_list_ldong.py`)이 기존 목록을 건드리지 않고 새 가게만 뒤에 붙인다. `[2026-10-05]`"""
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(_HERE))), "scripts", "dining", "fetch_list_ldong.py")


def _load():
    spec = importlib.util.spec_from_file_location("fetch_list_ldong", _PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_old_rows_stay_as_they_are_and_only_unknown_ids_are_appended():
    mod = _load()
    old = [{"contentid": "1", "title": "옛 가게", "tel": "02-1"}, {"contentid": "2", "title": "빠진 가게"}]
    fresh = [{"contentid": "1", "title": "이름이 바뀐 가게", "tel": "02-9"}, {"contentid": "3", "title": "새 가게"}]
    merged, added = mod.merge(old, fresh)
    assert merged[:2] == old                           # 사람이 검수한 시트가 contentid 로 가리키는 행은 그대로
    assert [r["contentid"] for r in added] == ["3"] and merged[2]["title"] == "새 가게"
    assert [r["contentid"] for r in merged] == ["1", "2", "3"]       # 법정동 응답에 없는 옛 행(2)도 지우지 않는다


def test_pages_are_read_until_the_total_is_reached():
    mod = _load()
    pages = {1: [{"contentid": str(i)} for i in range(3)], 2: [{"contentid": "3"}]}
    mod.fetch_page = lambda key, page, get=None: (pages.get(page, []), 4)
    mod.fi.PAUSE = 0
    assert [r["contentid"] for r in mod.fetch_all("k")] == ["0", "1", "2", "3"]

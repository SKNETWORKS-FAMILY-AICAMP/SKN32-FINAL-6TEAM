"""인허가(사업자 등록) 식당 이름 찾기 — 적재 변환 · 이름 찾기 규칙 · 접수 어댑터 폴백. `[2026-10-05]`"""
import csv
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, *rel))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


loader = _load("load_license_mod", ("scripts", "dining", "load_license.py"))
ledger = _load("dining_ledger_license", ("app", "domains", "travel_ops", "instances", "dining", "ledger.py"))


class _Tx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeConn:
    def __init__(self, rows, fail=False):
        self.rows, self.fail = rows, fail

    def transaction(self):
        return _Tx()

    def cursor(self):
        conn = self

        class Cur(_Tx):
            def execute(self, sql, params=None):
                if conn.fail:
                    raise RuntimeError("표가 없다")

            def fetchall(self):
                return conn.rows
        return Cur()


def row(mgt, name, lat, lng, addr="서울특별시 성동구 성수일로3길 12 (성수동1가)", category="한식"):
    return (mgt, name, lat, lng, addr, category)


def test_one_active_shop_with_that_name_is_found_with_a_license_marker():
    found = ledger.find_license_shop_by_name(FakeConn([row("m1", "호집", 37.54, 127.05)]), "호집")
    assert found["license"] is True and found["content_id"] == "m1" and found["address"].startswith("서울")


def test_several_shops_with_the_same_name_need_a_clearly_nearest_one():
    rows = [row("a", "김밥천국", 37.5446, 127.0557), row("b", "김밥천국", 37.5600, 127.0700)]
    conn = FakeConn(rows)
    assert ledger.find_license_shop_by_name(conn, "김밥천국") is None                       # 단서 없이는 고르지 않는다
    near = ledger.find_license_shop_by_name(conn, "김밥천국", near=(37.5447, 127.0558))
    assert near["content_id"] == "a"
    close_pair = [row("a", "김밥천국", 37.5446, 127.0557), row("b", "김밥천국", 37.5450, 127.0560)]
    assert ledger.find_license_shop_by_name(FakeConn(close_pair), "김밥천국", near=(37.5448, 127.0558)) is None   # 비슷하게 가까우면 고르지 않는다
    far = [row("a", "김밥천국", 37.70, 127.15)]
    assert ledger.find_license_shop_by_name(FakeConn(far + [row("b", "김밥천국", 37.71, 127.16)]), "김밥천국", near=(37.50, 127.00)) is None


def test_a_missing_table_or_empty_name_is_not_found_not_an_error():
    assert ledger.find_license_shop_by_name(FakeConn([], fail=True), "호집") is None
    assert ledger.find_license_shop_by_name(FakeConn([]), "호집") is None
    assert ledger.find_license_shop_by_name(FakeConn([row("m", "x", 37.5, 127.0)]), "x") is None     # 한 글자는 찾지 않는다


def test_the_key_matches_the_ledger_rule_and_tm_coordinates_become_seoul_wgs84():
    assert loader.name_key("[백년가게] 호 집!") == "백년가게호집" and loader.name_key("Cafe  A.B") == "cafeab"
    import pyproj

    t = pyproj.Transformer.from_crs("EPSG:5174", "EPSG:4326", always_xy=True)
    lat, lng = loader.convert(t, "202000.5 ", "451000.1 ")
    assert 37.4 <= lat <= 37.72 and 126.7 <= lng <= 127.2
    assert loader.convert(t, "", "") == (None, None) and loader.convert(t, "1", "1") == (None, None)


def test_only_open_seoul_food_shops_are_loaded(tmp_path):
    head = ["MGTNO", "BPLCNM", "TRDSTATENM", "UPTAENM", "RDNWHLADDR", "SITEWHLADDR", "SITETEL", "X", "Y", "APVPERMYMD"]
    data = [["1", "열린집", "영업/정상", "한식", "서울특별시 성동구 성수일로3길 12", "", "02-1", "202000", "451000", "2020-01-01"],
            ["2", "닫힌집", "폐업", "한식", "서울특별시 성동구 성수일로3길 13", "", "", "202000", "451000", "2020-01-01"],
            ["3", "경기집", "영업/정상", "한식", "경기도 성남시 어딘가 1", "", "", "202000", "451000", "2020-01-01"],
            ["4", "편의점A", "영업/정상", "편의점", "서울특별시 성동구 성수일로3길 14", "", "", "202000", "451000", "2020-01-01"]]
    with open(tmp_path / "서울시 일반음식점 인허가 정보_20261005.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(head)
        w.writerows(data)
    got = list(loader.rows(str(tmp_path)))
    assert [r[0] for r in got] == ["1"] and got[0][2] == "열린집" and got[0][8] is not None


def test_the_intake_lookup_falls_back_to_the_license_table_when_the_ledger_misses(monkeypatch):
    from app.domains.travel_ops.instances.dining import place_lookup

    monkeypatch.setattr(place_lookup, "find_place_by_name", lambda conn, name: None)
    seen = {}

    def fake(conn, name, near=None):
        seen["near"] = near
        return {"content_id": "m1", "matched_title": name, "latitude": 37.5, "longitude": 127.0, "address": "서울 어딘가", "license": True}
    monkeypatch.setattr(place_lookup, "find_license_shop_by_name", fake)

    class Conn(_Tx):
        pass
    lookup = place_lookup.LedgerPlaceLookup(lambda: Conn(), near=lambda: (37.1, 127.1))
    found = lookup.find("호집")
    assert found["license"] is True and seen["near"] == (37.1, 127.1) and lookup.misses == {}

"""make_nopo_sql — 자치구 · 도로명 · 건물번호 · 상호가 모두 맞을 때만 잇는다. `[2026-10-07]`

데이터 파일을 읽지 않는다 — 주소 해석과 SQL 조각만 본다(데이터는 git 밖이라 CI 에 없다).
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(HERE, "..", "..", "..", "scripts", "dining", "make_nopo_sql.py")


@pytest.fixture(scope="module")
def mn():
    spec = importlib.util.spec_from_file_location("dining_make_nopo_sql", os.path.abspath(MODULE))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dining_make_nopo_sql"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("address, key", [
    ("서울 종로구 종로46길 1 1층 (창신동)", ("종로구", "종로46길", "1")),
    ("서울특별시 마포구 동교로 83 (망원동)", ("마포구", "동교로", "83")),
    ("서울특별시 중구 동호로 249, 신라호텔 23층", ("중구", "동호로", "249")),
    ("서울 영등포구 신길로 200-20 (신길동)", ("영등포구", "신길로", "200-20")),
])
def test_도로명_주소에서_자치구_도로명_건물번호만_꺼낸다(mn, address, key):
    assert mn.addr_key(address) == key


@pytest.mark.parametrize("address", ["서울특별시 동작구 노량진동 297-1", "서울특별시 종로구  자하문로1가길 (9)", ""])
def test_도로명_주소가_아니면_잇지_않는다(mn, address):
    assert mn.addr_key(address) is None


def test_건물번호는_뒤에_숫자가_붙은_번지에_걸리지_않는다(mn):
    sql = mn.match_sql("망원동즉석우동돈까스", ("마포구", "동교로", "83"))
    pattern = re.search(r"p\.road_address ~ '(.+?)'", sql).group(1)
    assert re.search(pattern, "서울특별시 마포구 동교로 83 (망원동)")
    assert re.search(pattern, "서울특별시 마포구 동교로 83, 1층")
    assert not re.search(pattern, "서울특별시 마포구 동교로 830")
    assert not re.search(pattern, "서울특별시 마포구 동교로 83-1")


def test_별칭이_있으면_원장_상호로_찾고_없으면_정규화한_상호로_찾는다(mn):
    assert "p.name_ko = '망원동즉석우동 본점'" in mn.match_sql("망원동즉석우동돈까스", ("마포구", "동교로", "83"))
    plain = mn.match_sql("공평동꼼장어 본점", ("종로구", "우정국로", "29"))
    assert "'공평동꼼장어본점'" in plain and "strpos" in plain
    assert "HAVING count(*) = 1" in plain       # 후보가 둘이면 잇지 않는다


def test_도로명_주소가_아닌_행은_SQL_을_만들지_않는다(mn):
    lines = mn.sql_lines([{"상호": "번지집", "주소": "서울특별시 동작구 노량진동 297-1", "자치구": "동작구"}])
    assert not any("dn_attribute (" in line for line in lines)


# ── 검수 시트 ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw, text", [("025167992", "02-516-7992"), ("02 2265 0151", "02-2265-0151"),
                                       ("0317654321", "031-765-4321"), ("", ""), (None, "")])
def test_전화는_엑셀이_앞자리_0을_지우지_않게_하이픈을_넣는다(mn, raw, text):
    assert mn.phone_text(raw) == text


@pytest.fixture(scope="module")
def mv():
    path = os.path.join(HERE, "..", "..", "..", "scripts", "dining", "make_vegan_sql.py")
    spec = importlib.util.spec_from_file_location("dining_make_vegan_sql_for_nopo", os.path.abspath(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_브레이크타임은_영업하는_요일의_구간에서_뺀다(mv):
    day = mv.parse_day("11:00-21:00")
    assert mv.apply_break(day, "16:00-17:00") == ("intervals", [(660, 960), (1020, 1260)])
    assert mv.apply_break(mv.parse_day("휴무"), "16:00-17:00") == ("closed", [])
    assert mv.apply_break(day, "없음") == day and mv.apply_break(day, None) == day   # 칸이 없는 옛 시트
    assert mv.apply_break(mv.parse_day("17:00-21:00"), "15:00-16:00") == ("intervals", [(1020, 1260)])


def test_브레이크타임을_읽지_못하면_멈춘다(mv):
    with pytest.raises(ValueError):
        mv.apply_break(mv.parse_day("11:00-21:00"), "15시~16시")


# ── 검수 시트 → 새 가게 ───────────────────────────────────────────────
@pytest.mark.parametrize("x, y, lat, lng", [
    (201016.330641653, 459391.044317921, 37.636879, 127.012302),      # 원장에 인허가 좌표로 들어간 가게 두 곳
    (205479.446439786, 454026.469298816, 37.5885297, 127.0628276),
])
def test_인허가_좌표를_원장과_같은_WGS84_로_바꾼다(x, y, lat, lng):
    sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "scripts", "dining")))
    from tm5174 import to_wgs84

    got = to_wgs84(x, y)
    assert abs(got[0] - lat) < 1e-5 and abs(got[1] - lng) < 1e-5      # 약 1m 안


def _sheet_row(label, **values):
    row = {"번호": "1", "상호(목록)": label, "표시명": label, "자치구": "강남구",
           "주소": "서울 강남구 논현로151길 26 1층 (신사동)", "확인일": "", "메모": "", "전화": "02-516-7992",
           "인허가 관리번호": "", **{d: "" for d in "월화수목금토일"}, "브레이크타임": "", "라스트오더": "", "정기휴무 외": ""}
    row.update(values)
    return row


def test_확인되고_관리번호가_있는_행만_가게로_만든다(mn, tmp_path):
    mn.OUT = str(tmp_path)
    licenses = {"N1": ("localdata_food", {"좌표정보(X)": "201016.33", "좌표정보(Y)": "459391.04", "사업장명": "가"}),
                "N2": ("localdata_food", {"좌표정보(X)": "", "좌표정보(Y)": "", "사업장명": "나"})}
    rows = [_sheet_row("예시줄", 번호="예시", 확인일="2026-10-07", **{"인허가 관리번호": "N1"}),
            _sheet_row("안 본 집", **{"인허가 관리번호": "N1"}),
            _sheet_row("문 닫은 집", 확인일="2026-10-07", 메모="폐업", **{"인허가 관리번호": "N1"}),
            _sheet_row("요일 빈 집", 확인일="2026-10-07", **{"인허가 관리번호": "N1"}),
            _sheet_row("번호 없는 집", 확인일="2026-10-07", 월="모름"),
            _sheet_row("좌표 없는 집", 확인일="2026-10-07", 월="모름", **{"인허가 관리번호": "N2"}),
            _sheet_row("만들 집", 확인일="2026-10-07", 월="11:00-21:00", 브레이크타임="16:00-17:00",
                       **{"인허가 관리번호": "N1"})]
    lines, counts = mn.new_place_lines(rows, licenses)
    assert counts["만든다"] == ["만들 집"] and counts["안 봄"] == 1
    assert counts["폐업"] == ["문 닫은 집"] and counts["관리번호 없음"] == ["번호 없는 집"]
    assert counts["좌표 없음"] == ["좌표 없는 집"]
    assert counts["요일 비어 있음"] == ["요일 빈 집"]       # 확인일만 있고 요일이 비면 아직 안 본 것이다
    sql = "\n".join(lines)
    assert sql.count("INSERT INTO dining.dn_place") == 1
    assert "'서울특별시 강남구 논현로151길 26 1층 (신사동)'" in sql
    assert "'nopo', 'yes'" in sql and "dn_hours_rule" in sql
    # 같은 관리번호의 가게가 이미 있으면(비건 · 할랄이 만든 곳) 그 가게에 붙는다
    assert "r.external_id = 'N1'" in sql and "IS NULL" in sql


def test_다시_돌릴_때_스스로_만든_가게에_기존_가게로_또_붙지_않는다(mn):
    sql = mn.match_sql("전주맛자랑", ("강남구", "논현로151길", "26"), ("9c50175a-d363-53d6-90cf-676e42d6579a",))
    assert "p.place_uid NOT IN ('9c50175a-d363-53d6-90cf-676e42d6579a')" in sql


def test_시트에_잘못_적은_행은_그_행만_빼고_알린다(mn, tmp_path):
    mn.OUT = str(tmp_path)
    licenses = {f"N{i}": ("localdata_food", {"좌표정보(X)": "201016.33", "좌표정보(Y)": "459391.04"}) for i in (1, 2)}
    rows = [_sheet_row("잘 적은 집", 확인일="2026-10-07", 월="11:00-21:00", **{"인허가 관리번호": "N1"}),
            _sheet_row("잘못 적은 집", 확인일="2026-10-07", 월="전화문의", **{"인허가 관리번호": "N2"})]
    lines, counts = mn.new_place_lines(rows, licenses)
    assert counts["만든다"] == ["잘 적은 집"]
    assert len(counts["시트 오류"]) == 1 and "잘못 적은 집" in counts["시트 오류"][0]
    assert "'잘못 적은 집'" not in "\n".join(lines)


@pytest.mark.parametrize("cell, text", [
    ("일요일 및 공휴일", "일요일 / 공휴일"),
    ("매월 1,3번째 일요일, 2,4번째 월요일", "매월 1,3번째 일요일 / 매월 2,4번째 월요일"),
    ("매월 2,4,5번째 일요일", "매월 2,4,5번째 일요일"),
    ("명절 전날, 명절 당일", "명절 전날 / 명절 당일"),
    ("연중무휴", "연중무휴"), ("", ""),
])
def test_정기휴무_외는_항목마다_나눠_적재기가_말없이_버리지_않게_한다(mn, cell, text):
    assert mn.closure_text(cell) == text


def test_24시간과_정기휴무를_고친_사본을_넘기고_원본은_그대로_둔다(mn):
    row = _sheet_row("영춘옥", 월="24시간", 화="11:00-21:00", **{"정기휴무 외": "일요일 및 공휴일"})
    got = mn.tidy(row)
    assert got["월"] == "00:00-24:00" and got["화"] == "11:00-21:00" and got["정기휴무 외"] == "일요일 / 공휴일"
    assert row["월"] == "24시간"


def test_메모에_노포가_아니라고_적은_행은_만들지_않는다(mn, tmp_path):
    mn.OUT = str(tmp_path)
    licenses = {"N1": ("localdata_food", {"좌표정보(X)": "201016.33", "좌표정보(Y)": "459391.04"})}
    rows = [_sheet_row("카페", 확인일="2026-10-07", 월="10:00-20:00", 메모="노포가 아니라 카페",
                       **{"인허가 관리번호": "N1"})]
    _, counts = mn.new_place_lines(rows, licenses)
    assert counts["노포 아님"] == ["카페"] and counts["만든다"] == []


def test_쉬는_구간이_둘이면_둘_다_뺀다(mv):
    assert mv.apply_break(mv.parse_day("00:00-24:00"), "03:00-04:00, 15:00-16:00") == (
        "intervals", [(0, 180), (240, 900), (960, 1440)])


def test_인허가_좌표가_없으면_브이월드_좌표로_만든다(mn, tmp_path):
    mn.OUT = str(tmp_path)
    row = _sheet_row("번호 없는 집", 확인일="2026-10-08", 월="11:00-21:00")
    lines, counts = mn.new_place_lines([row], {}, {("번호 없는 집", row["주소"]): (37.52, 127.02)})
    sql = "\n".join(lines)
    assert counts["만든다"] == ["번호 없는 집"] and counts["브이월드 좌표"] == ["번호 없는 집"]
    assert "'vworld_geocoder'" in sql and "37.5200000" in sql and "'nopo', 'yes'" in sql
    assert "dn_hours_rule" in sql                                  # 영업시간도 그 가게로 들어간다
    assert mn.new_place_lines([row], {}, {})[1]["관리번호 없음"] == ["번호 없는 집"]   # 좌표가 없으면 만들지 않는다


@pytest.mark.parametrize("rest, expected", [
    ("11:00-12:00", [(720, 1260)]),
    ("20:00-21:00", [(660, 1200)]),
    ("10:00-12:00", [(720, 1260)]),
    ("11:00-21:00", []),
])
def test_break_touching_open_or_close_is_removed(mv, rest, expected):
    assert mv.apply_break(mv.parse_day("11:00-21:00"), rest) == ("intervals", expected)


def test_duplicate_shop_labels_fail_before_generating_hours(mn):
    with pytest.raises(ValueError, match="같은 상호"):
        mn.new_place_lines([_sheet_row("같은집", 주소="서울 종로구 도로 1"),
                            _sheet_row("같은집", 주소="서울 종로구 도로 2")], {})


def test_sheet_upgrade_keeps_reviewed_rows_and_backs_up(mn, tmp_path, monkeypatch):
    import csv
    path = tmp_path / "sheet.csv"
    row = _sheet_row("검수한집", 월="11:00-21:00", 확인일="2026-10-08")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=mn.SHEET_COLUMNS)
        writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in mn.SHEET_COLUMNS})
    original = path.read_bytes()
    monkeypatch.setattr(mn, "SHEET", str(path))
    monkeypatch.setattr(mn, "MADE", str(tmp_path / "made.json"))
    monkeypatch.setattr(mn.sys, "argv", ["script", "--upgrade"])
    monkeypatch.setattr(mn, "_ledger_index", lambda: ([], {}, {}))
    monkeypatch.setattr(mn, "_localdata", lambda: {("sentinel",): []})
    monkeypatch.setattr(mn, "_match", lambda *args: ("확정", [{"place_uid": "mine"}]))
    monkeypatch.setattr(mn, "_licensed", lambda *args: ("없음", None))
    mn.sheet([{"상호": "검수한집", "주소": row["주소"], "자치구": "종로구"}])
    found = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    assert any(line.get("월") == "11:00-21:00" for line in found)
    assert any(backup.read_bytes() == original for backup in tmp_path.glob("_backup/*/sheet.csv"))


def test_license_reader_prefers_latest_dated_utf8_and_supports_legacy_cp949(mn, tmp_path, monkeypatch):
    import csv
    monkeypatch.setattr(mn, "RAW", str(tmp_path))
    base = "서울시 일반음식점 인허가 정보"
    for name, encoding, number in [(base + ".csv", "cp949", "legacy"),
                                    (base + "_20261001.csv", "utf-8-sig", "old"),
                                    (base + "_20261005.csv", "utf-8-sig", "new")]:
        with (tmp_path / name).open("w", encoding=encoding, newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["관리번호", "사업장명"])
            writer.writeheader()
            writer.writerow({"관리번호": number, "사업장명": "서울식당"})
    assert list(mn._licenses()) == ["new"]
    (tmp_path / (base + "_20261001.csv")).unlink()
    (tmp_path / (base + "_20261005.csv")).unlink()
    assert mn._licenses()["legacy"][1]["사업장명"] == "서울식당"


def test_license_reader_translates_seoul_api_columns(mn, tmp_path, monkeypatch):
    import csv
    monkeypatch.setattr(mn, "RAW", str(tmp_path))
    path = tmp_path / "서울시 일반음식점 인허가 정보_20261005.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["MGTNO", "BPLCNM", "RDNWHLADDR", "X", "Y"])
        writer.writeheader()
        writer.writerow({"MGTNO": "api1", "BPLCNM": "서울식당", "RDNWHLADDR": "서울 종로구 종로 1", "X": "1", "Y": "2"})
    row = mn._licenses()["api1"][1]
    assert row["사업장명"] == "서울식당" and row["좌표정보(X)"] == "1"
    assert mn._localdata()[('종로구', '종로', '1')][0][1]["관리번호"] == "api1"


@pytest.mark.parametrize("broken", [False, True])
def test_license_reader_detects_cp949_body_with_ascii_header(mn, tmp_path, monkeypatch, broken):
    monkeypatch.setattr(mn, "RAW", str(tmp_path))
    path = tmp_path / "서울시 일반음식점 인허가 정보_20261005.csv"
    payload = "MGTNO,BPLCNM\nlicense1,서울식당".encode("cp949")
    if broken:
        payload += b"\xff"
    path.write_bytes(payload + b"\n")
    row = mn._licenses()["license1"][1]
    assert row["사업장명"].startswith("서울식당")


def test_sheet_upgrade_without_license_data_keeps_original(mn, tmp_path, monkeypatch):
    path = tmp_path / "sheet.csv"
    path.write_text("번호,상호(목록),주소\n1,서울식당,서울 종로구 종로 1\n", encoding="utf-8-sig")
    original = path.read_bytes()
    monkeypatch.setattr(mn, "SHEET", str(path))
    monkeypatch.setattr(mn.sys, "argv", ["script", "--upgrade"])
    monkeypatch.setattr(mn, "_ledger_index", lambda: ([], {}, {}))
    monkeypatch.setattr(mn, "_localdata", lambda: {})
    with pytest.raises(ValueError, match="덮어쓰지"):
        mn.sheet([])
    assert path.read_bytes() == original


def test_geocode_without_license_data_stops_before_api_call(mn, monkeypatch):
    monkeypatch.setattr(mn, "_licenses", lambda: {})
    with pytest.raises(ValueError, match="좌표 수집을 중단"):
        mn.geocode([])


def test_main_missing_license_source_never_overwrites_sql(mn, tmp_path, monkeypatch):
    import csv
    monkeypatch.setattr(mn, "RAW", str(tmp_path / "missing"))
    monkeypatch.setattr(mn, "OUT", str(tmp_path))
    monkeypatch.setattr(mn.sys, "argv", ["script"])
    output = tmp_path / "nopo.sql"
    output.write_text("previous SQL", encoding="utf-8")
    listing = tmp_path / "list.csv"
    listing.write_text("상호,주소,자치구\n", encoding="utf-8-sig")
    sheet = tmp_path / "sheet.csv"
    sheet.write_text("번호,상호(목록),주소\n", encoding="utf-8-sig")
    monkeypatch.setattr(mn, "LIST", str(listing))
    monkeypatch.setattr(mn, "SHEET", str(sheet))
    with pytest.raises(ValueError, match="SQL 생성을 중단"):
        mn.main()
    assert output.read_text(encoding="utf-8") == "previous SQL"


def test_each_required_license_source_must_have_rows(mn, tmp_path, monkeypatch):
    monkeypatch.setattr(mn, "RAW", str(tmp_path))
    (tmp_path / "서울시 일반음식점 인허가 정보.csv").write_text("관리번호,사업장명\nN1,서울식당\n", encoding="utf-8-sig")
    (tmp_path / "서울시 휴게음식점 인허가 정보.csv").write_text("관리번호,사업장명\n", encoding="utf-8-sig")
    with pytest.raises(ValueError, match="데이터가 없어"):
        mn._licenses(require_all=True)

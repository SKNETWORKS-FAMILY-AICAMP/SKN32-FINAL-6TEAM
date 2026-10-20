# -*- coding: utf-8 -*-
"""활동 장소 별칭(`place_aliases` · 시드 `data_processing/place_aliases.csv` · DB 표 `activity.ac_place_alias`). `[2026-10-19]`

★별칭은 사람이 확인해 넣는다. 이 시험은 시드 파일의 **형식과 정식 제목**을 지킨다 — 정식 제목이 원장 CSV(`activity_total_data.csv`)와 다르면
  별칭이 엉뚱한 장소를 가리킨다. 대표 시나리오(2026-10-27 · 28 일정)의 장소는 전부 대표 이름으로 닿아야 한다.
  DB 에 실제로 들어 있는지는 적재 스크립트(`scripts/activity/load_place_aliases.py --dry-run`)가 본다.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import pytest

from app.domains.travel_ops.components.intake.places import normalize_full
from app.domains.travel_ops.instances.activity import place_aliases as pa
from app.domains.travel_ops.instances.activity import place_identity as pi
from app.domains.travel_ops.instances.activity.csv_places import _CSV_PATH

ROWS = pa.read_seed()
TABLE = pa.AliasTable((r["alias"], r["content_id"]) for r in ROWS)
LEDGER = {r["contentid"]: r["title"] for r in csv.DictReader(Path(_CSV_PATH).open(encoding="utf-8-sig", newline=""))}


def test_file_has_the_expected_columns_and_rows():
    assert ROWS and set(ROWS[0]) == {"content_id", "canonical_title", "alias", "source"}
    assert {r["source"] for r in ROWS} <= {"curated", "customer"}


def test_canonical_titles_match_the_ledger_data():
    wrong = [(r["content_id"], r["canonical_title"], LEDGER.get(r["content_id"])) for r in ROWS
             if LEDGER.get(r["content_id"]) != r["canonical_title"]]
    assert wrong == []


def test_no_blank_alias_and_no_alias_that_is_just_the_canonical_title():
    for r in ROWS:
        assert normalize_full(r["alias"]), r
        assert normalize_full(r["alias"]) != normalize_full(r["canonical_title"]), r   # 정규화가 이미 처리한다 — 별칭이 필요 없다


def test_no_alias_points_at_two_places():
    seen: dict[str, set[str]] = defaultdict(set)
    for r in ROWS:
        seen[normalize_full(r["alias"])].add(r["content_id"])
    assert {k: v for k, v in seen.items() if len(v) > 1} == {}


@pytest.mark.parametrize("name, content_id", [
    ("남산타워", "126535"), ("N서울타워", "126535"), ("엔서울타워", "126535"), ("N 서울 타워", "126535"), ("서울타워", "126535"),
    ("창덕궁", "127642"), ("창덕궁 후원", "127642"), ("비원", "127642"),
    ("국중박", "129703"), ("중앙박물관", "129703"),
    ("북촌", "126537"), ("북촌 한옥", "126537"),
    ("인사동거리", "264353"), ("인사동길", "264353"),
    ("남대문", "128162"), ("명동성당", "126804"), ("DDP", "2470006"), ("롯데타워 전망대", "2492348"),
])
def test_known_aliases_point_at_one_place(name, content_id):
    assert TABLE.content_id_for(name) == content_id


def test_ambiguous_or_unknown_names_are_not_aliases():
    assert TABLE.content_id_for("동대문") is None            # 흥인지문 · 지역 · 시장 — 일부러 넣지 않았다
    assert TABLE.content_id_for("없는 곳") is None
    assert TABLE.is_alias_of("남산타워", "999") is False
    two = pa.AliasTable([("공통 별칭", "1"), ("공통별칭", "2")])
    assert two.content_ids_for("공통 별칭") == {"1", "2"} and two.content_id_for("공통 별칭") is None   # 모호하면 쓰지 않는다
    assert two.is_alias_of("공통 별칭", "1") is False


def test_rows_from_the_pool_become_a_table_and_missing_rows_an_empty_one():
    table = pa.from_rows([{"alias": "N서울타워", "content_id": "126535"}, {"alias": "", "content_id": "1"}, "junk"])
    assert table.content_id_for("n 서울타워") == "126535" and len(table) == 1
    assert pa.from_rows(None) is pa.EMPTY and pa.from_rows([]) is pa.EMPTY


# ── 대표 시나리오 — 일정의 장소 이름이 원장 후보와 같은 곳으로 읽혀야 한다 ──

SCENARIO = [   # (일정에 들어간 이름 · 카카오 쪽 좌표라고 가정, 원장 후보)
    ("N서울타워", {"contentid": "126535", "title": "남산서울타워"}),
    ("창덕궁", {"contentid": "127642", "title": "창덕궁과 후원 [유네스코 세계유산]"}),
    ("북촌한옥마을", {"contentid": "126537", "title": "북촌한옥마을"}),
    ("인사동", {"contentid": "264353", "title": "인사동"}),
    ("청계천", {"contentid": "129507", "title": "청계천"}),
    ("국립중앙박물관", {"contentid": "129703", "title": "국립중앙박물관"}),
    ("광장시장", {"contentid": "132183", "title": "광장시장"}),
    ("경복궁", {"contentid": "126508", "title": "경복궁"}),
]


@pytest.mark.parametrize("plan_name, row", SCENARIO)
def test_representative_scenario_places_are_the_same_place_as_their_ledger_rows(plan_name, row):
    # 카카오 쪽 좌표는 관광공사와 수백 m 어긋난다고 가정한다(약 450m) — 별칭이 맞고 `ALIAS_MAX_M` 안이면 같은 곳이다
    spot = pi.Spot(plan_name, 37.504, 126.9, None, None)
    assert pi.verdict(spot, pi.spot_of({**row, "mapy": "37.5", "mapx": "126.9"}), TABLE) == "same"


def test_a_different_place_in_the_same_palace_is_not_the_same():
    spot = pi.Spot("창덕궁", 37.5794, 126.9910, None, None)
    nakseonjae = {"contentid": "1604941", "title": "창덕궁 낙선재", "mapy": "37.5796", "mapx": "126.9915"}
    assert pi.verdict(spot, pi.spot_of(nakseonjae), TABLE) != "same"


# ── 별칭 + 거리 ─────────────────────────────────────────────────

NAMSAN = {"contentid": "126535", "title": "남산서울타워", "mapy": "37.5510545", "mapx": "126.9878829"}


def test_alias_match_still_needs_the_places_to_be_near_when_coordinates_are_known():
    """★별칭은 이름만 증명한다 — 같은 이름의 다른 곳(다른 동네 · 다른 도시)이 카카오로 들어올 수 있다."""
    near = pi.Spot("N서울타워", 37.5512, 126.9885, None, None)                       # 약 60m
    far = pi.Spot("N서울타워", 35.1796, 129.0756, None, None)                        # 부산
    assert pi.verdict(near, pi.spot_of(NAMSAN), TABLE) == "same"
    assert pi.verdict(far, pi.spot_of(NAMSAN), TABLE) == "ambiguous"    # 같은 이름의 다른 곳일 수 있다 — 빼지 않고 경고로 센다


def test_alias_is_trusted_when_a_coordinate_is_missing():
    assert pi.verdict(pi.Spot("N서울타워", None, None, None, None), pi.spot_of(NAMSAN), TABLE) == "same"
    assert pi.verdict(pi.Spot("N서울타워", 37.5, 126.9, None, None), pi.spot_of({**NAMSAN, "mapy": None, "mapx": None}), TABLE) == "same"


def test_alias_distance_limit_tolerates_big_sites_whose_representative_points_differ():
    assert pi.ALIAS_MAX_M >= 2000                      # 공원 · 궁 · 산은 두 출처의 대표 좌표가 1km 넘게 어긋난다
    just_inside = pi.Spot("N서울타워", 37.5510545 + 0.02, 126.9878829, None, None)   # 약 2.2km
    assert pi.verdict(just_inside, pi.spot_of(NAMSAN), TABLE) == "same"


# ── 시드 파일 + DB 표 합치기 ────────────────────────────────────

def test_seed_file_alone_applies_without_any_database_rows():
    """★배포에 실린 시드 파일만으로 적용된다 — DB 적재를 안 했거나 표가 없어도."""
    assert pa.merged(None).content_id_for("남산타워") == "126535"
    assert pa.merged([]).content_id_for("엔서울타워") == "126535"


def test_database_rows_add_aliases_on_top_of_the_seed():
    table = pa.merged([{"alias": "서울 하늘전망대 타워", "content_id": "126535"}, {"alias": "새 별칭", "content_id": "129703"}])
    assert table.content_id_for("새 별칭") == "129703"
    assert table.content_id_for("남산타워") == "126535"          # 시드는 그대로


def test_database_row_that_contradicts_the_seed_makes_the_alias_ambiguous_and_unused():
    table = pa.merged([{"alias": "남산타워", "content_id": "999"}])
    assert table.content_ids_for("남산타워") == {"126535", "999"}
    assert table.content_id_for("남산타워") is None

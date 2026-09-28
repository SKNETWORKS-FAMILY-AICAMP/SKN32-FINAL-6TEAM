"""가게 링크(035)의 회귀 시험.

막는 것 — 확인하지 않은 링크가 사용자에게 나가지 않는가, 확인했다고 하려면 누가 언제를
남기는가, 단축 주소나 다른 kind 의 주소가 섞이지 않는가, 한 링크가 두 가게에 붙지 않는가,
map_links 를 이미 읽는 쪽이 깨지지 않는가.

도구(place_link.py)가 다듬은 주소를 DB 가 실제로 받는지도 본다. 모양 규칙은 DB 에만 있고
도구는 다듬기만 한다. 둘이 어긋나면 여기서 걸린다.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "..", "..", "..", "scripts", "dining", "place_link.py")

NAVER = "https://map.naver.com/p/entry/place/1390960244"
INSTA = "https://www.instagram.com/drvegan_official/"


def add_ref(conn, place_uid: str, kind: str, url: str, status: str = "candidate",
            verified: bool | None = None) -> str:
    verified = status != "candidate" if verified is None else verified
    return conn.execute(
        "INSERT INTO dining.dn_external_ref (place_uid, kind, url, status, entered_by, "
        "verified_by, verified_at) VALUES (%s, %s, %s, %s, 'test', %s, "
        "CASE WHEN %s THEN now() END) RETURNING ref_id",
        (place_uid, kind, url, status, "test" if verified else None, verified)).fetchone()[0]


def url_ok(conn, kind: str, url: str) -> bool:
    return conn.execute("SELECT dining.external_ref_url_ok(%s, %s)", (kind, url)).fetchone()[0]


def links(conn, place_uid: str) -> dict:
    return conn.execute("SELECT dining.map_links(%s)", (place_uid,)).fetchone()[0]


# ── 모양 ────────────────────────────────────────────────────────

@pytest.mark.parametrize("kind,url", [
    ("naver_place",  NAVER),
    ("google_place", "https://www.google.com/maps/place/Dr.Vegan/@37.52,127.04,17z"),
    ("google_place", "https://www.google.com/maps?cid=123456"),
    ("instagram",    INSTA),
    ("tripadvisor",  "https://www.tripadvisor.co.kr/Restaurant_Review-g294197-d1234567-Reviews-X-Seoul.html"),
    ("tripadvisor",  "https://www.tripadvisor.com/Restaurant_Review-g294197-d1234567-Reviews-X-Seoul.html"),
    ("homepage",     "https://drvegan.co.kr"),
    ("homepage",     "http://drvegan.co.kr/menu"),
])
def test_받는_주소(conn, kind, url):
    assert url_ok(conn, kind, url)


@pytest.mark.parametrize("kind,url", [
    # 단축 주소는 어느 자리로도 들어오지 못한다
    ("naver_place",  "https://naver.me/5abcXYZ"),
    ("google_place", "https://maps.app.goo.gl/abc"),
    ("homepage",     "https://naver.me/5abcXYZ"),
    ("homepage",     "https://maps.app.goo.gl/abc"),
    ("homepage",     "https://bit.ly/abc"),
    # 검색 주소는 가게가 아니다
    ("naver_place",  "https://map.naver.com/p/search/%EB%8B%A5"),
    ("google_place", "https://www.google.com/maps/search/?api=1&query=x"),
    # 다듬지 않은 모양
    ("naver_place",  NAVER + "?c=15"),
    ("instagram",    "https://instagram.com/drvegan_official"),
    ("instagram",    "https://www.instagram.com/DrVegan/"),
    # 게시물은 계정이 아니다
    ("instagram",    "https://www.instagram.com/p/"),
    # 다른 kind 의 자리
    ("homepage",     INSTA),
    ("homepage",     NAVER),
    ("naver_place",  INSTA),
    ("tripadvisor",  "https://www.tripadvisor.co.kr/Attraction_Review-g1-d2-Reviews-x.html"),
    ("blog",         "https://blog.naver.com/x"),
])
def test_받지_않는_주소(conn, kind, url):
    assert not url_ok(conn, kind, url)


def test_모양이_틀리면_표가_거부한다(conn, place):
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.CheckViolation):
        add_ref(conn, place(), "naver_place", "https://naver.me/5abcXYZ")


# ── 확인 ────────────────────────────────────────────────────────

def test_확인했다고_하려면_누가_언제를_남긴다(conn, place):
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.CheckViolation):
        add_ref(conn, place(), "instagram", INSTA, status="valid", verified=False)


def test_한_가게의_한_kind에_확인_링크는_하나다(conn, place):
    psycopg = pytest.importorskip("psycopg")
    uid = place()
    add_ref(conn, uid, "instagram", INSTA, status="valid")
    with pytest.raises(psycopg.errors.UniqueViolation):
        add_ref(conn, uid, "instagram", "https://www.instagram.com/other_account/", status="valid")


def test_한_링크는_두_가게에_붙지_않는다(conn, place):
    psycopg = pytest.importorskip("psycopg")
    add_ref(conn, place(), "naver_place", NAVER)
    with pytest.raises(psycopg.errors.UniqueViolation):
        add_ref(conn, place(), "naver_place", NAVER)


# ── map_links ───────────────────────────────────────────────────

def test_링크가_없으면_map_links는_전과_같다(conn, place):
    got = links(conn, place())
    assert got["kind"] == "search"
    assert got["naver"].startswith("https://map.naver.com/p/search/")
    assert "place_links" not in got


def test_확인하지_않은_링크는_나가지_않는다(conn, place):
    uid = place()
    add_ref(conn, uid, "instagram", INSTA, status="candidate")
    add_ref(conn, uid, "naver_place", NAVER, status="dead")
    assert "place_links" not in links(conn, uid)


def test_확인한_링크는_place_links로_나간다(conn, place):
    uid = place()
    add_ref(conn, uid, "instagram", INSTA, status="valid")
    add_ref(conn, uid, "naver_place", NAVER, status="valid")
    got = links(conn, uid)
    assert got["place_links"] == {"instagram": INSTA, "naver_place": NAVER}


def test_확인한_링크가_있어도_검색_주소는_그대로다(conn, place):
    # 026, 031 이 naver, google, kind 를 읽는다. kind=search 는 계속 검색 주소라는 뜻이어야 한다.
    uid = place()
    add_ref(conn, uid, "naver_place", NAVER, status="valid")
    got = links(conn, uid)
    assert got["kind"] == "search"
    assert got["naver"].startswith("https://map.naver.com/p/search/")


# ── 도구와 DB 가 어긋나지 않는다 ─────────────────────────────────

@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("dining_place_link", os.path.abspath(TOOL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("kind,pasted", [
    ("naver_place",  "https://map.naver.com/p/entry/place/1390960244?c=15.00,0,0,0,dh"),
    ("naver_place",  "https://m.place.naver.com/restaurant/1390960244/home"),
    ("google_place", "https://www.google.com/maps/place/Dr.Vegan/@37.52,127.04,17z/data=!3m1?entry=ttu"),
    ("google_place", "https://maps.google.com/?cid=123456&hl=ko"),
    ("instagram",    "https://instagram.com/DrVegan_Official?igsh=abc"),
    ("tripadvisor",  "https://m.tripadvisor.co.kr/Restaurant_Review-g294197-d1234567-Reviews-X-Seoul.html?m=1"),
    ("homepage",     "https://drvegan.co.kr/"),
])
def test_도구가_다듬은_주소를_DB가_받는다(conn, tool, kind, pasted):
    assert url_ok(conn, kind, tool.prepare(kind, pasted, fetch=lambda u: None))


def test_단축_주소를_펼치면_DB가_받는다(conn, tool):
    fetch = {"https://naver.me/5abc":
             "https://map.naver.com/p/entry/place/1390960244?c=15"}.get
    assert url_ok(conn, "naver_place", tool.prepare("naver_place", "https://naver.me/5abc", fetch))

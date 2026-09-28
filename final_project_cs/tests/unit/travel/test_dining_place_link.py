"""place_link 의 단축 주소 따라가기와 다듬기.

망에 닿지 않는다. 단축 주소 서버는 가짜로 세운다.
DB 가 이 주소를 받는지는 tests/integration/dining/test_dining_external_ref.py 가 본다.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(HERE, "..", "..", "..", "scripts", "dining", "place_link.py")


@pytest.fixture(scope="module")
def pl():
    spec = importlib.util.spec_from_file_location("dining_place_link", os.path.abspath(MODULE))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fake(routes: dict[str, str | None]):
    """정해 둔 곳으로만 넘기는 단축 주소 서버. 물어본 주소를 적어 둔다."""
    asked: list[str] = []

    def fetch(url: str):
        asked.append(url)
        return routes[url]

    fetch.asked = asked
    return fetch


# ── 따라가기 ────────────────────────────────────────────────────

def test_단축_주소는_긴_주소로_바뀐다(pl):
    fetch = fake({"https://naver.me/5abc": "https://map.naver.com/p/entry/place/1390960244?c=15"})
    assert pl.expand("https://naver.me/5abc", fetch) == \
        "https://map.naver.com/p/entry/place/1390960244?c=15"


def test_단축_주소가_아니면_묻지_않는다(pl):
    fetch = fake({})
    url = "https://www.instagram.com/drvegan/"
    assert pl.expand(url, fetch) == url
    assert fetch.asked == []


def test_목적지는_열지_않는다(pl):
    # 긴 주소가 나오면 거기서 멈춘다. 지도 페이지에는 묻지 않는다.
    fetch = fake({"https://maps.app.goo.gl/x": "https://www.google.com/maps/place/A/@37,127"})
    pl.expand("https://maps.app.goo.gl/x", fetch)
    assert fetch.asked == ["https://maps.app.goo.gl/x"]


def test_단축_주소가_단축_주소로_넘기면_이어서_따라간다(pl):
    fetch = fake({"https://bit.ly/a": "https://naver.me/b",
                  "https://naver.me/b": "https://map.naver.com/p/entry/place/7"})
    assert pl.expand("https://bit.ly/a", fetch) == "https://map.naver.com/p/entry/place/7"


def test_너무_여러_번_넘기면_멈춘다(pl):
    fetch = fake({"https://bit.ly/a": "https://bit.ly/b", "https://bit.ly/b": "https://bit.ly/c",
                  "https://bit.ly/c": "https://bit.ly/d", "https://bit.ly/d": "https://bit.ly/a"})
    with pytest.raises(pl.LinkError, match="너무 여러 번"):
        pl.expand("https://bit.ly/a", fetch)


def test_넘기지_않는_단축_주소는_넣지_않는다(pl):
    with pytest.raises(pl.LinkError, match="넘기지 않았다"):
        pl.expand("https://naver.me/dead", fake({"https://naver.me/dead": None}))


def test_웹_주소가_아닌_곳으로_넘기면_넣지_않는다(pl):
    fetch = fake({"https://naver.me/app": "nmap://place?id=1"})
    with pytest.raises(pl.LinkError, match="웹 주소가 아닌"):
        pl.expand("https://naver.me/app", fetch)


# ── 다듬기 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "https://map.naver.com/p/entry/place/1390960244",
    "https://map.naver.com/p/entry/place/1390960244?c=15.00,0,0,0,dh&placePath=%2Fhome",
    "https://map.naver.com/p/search/%EB%8B%A5%ED%84%B0%EB%B9%84%EA%B1%B4/place/1390960244?c=15",
    "https://map.naver.com/v5/entry/place/1390960244",
    "https://m.place.naver.com/restaurant/1390960244/home",
    "https://pcmap.place.naver.com/restaurant/1390960244/home",
])
def test_네이버는_어느_모양이든_플레이스_번호_하나로_모인다(pl, url):
    assert pl.normalize("naver_place", url) == "https://map.naver.com/p/entry/place/1390960244"


def test_네이버_검색_주소는_가게가_아니다(pl):
    with pytest.raises(pl.LinkError):
        pl.normalize("naver_place", "https://map.naver.com/p/search/%EB%8B%A5%ED%84%B0")


def test_구글은_추적용_꼬리를_뗀다(pl):
    url = "https://www.google.com/maps/place/Dr.Vegan/@37.52,127.04,17z/data=!3m1!4b1?entry=ttu&g_ep=abc"
    assert pl.normalize("google_place", url) == \
        "https://www.google.com/maps/place/Dr.Vegan/@37.52,127.04,17z/data=!3m1!4b1"


def test_구글_cid_주소는_cid만_남긴다(pl):
    assert pl.normalize("google_place", "https://maps.google.com/?cid=123456&hl=ko") == \
        "https://www.google.com/maps?cid=123456"


def test_구글_검색_주소는_가게가_아니다(pl):
    with pytest.raises(pl.LinkError):
        pl.normalize("google_place", "https://www.google.com/maps/search/?api=1&query=x")


@pytest.mark.parametrize("url", [
    "https://instagram.com/DrVegan_Official",
    "https://www.instagram.com/drvegan_official/?igsh=abc",
    "https://m.instagram.com/drvegan_official/",
])
def test_인스타는_계정_주소_하나로_모인다(pl, url):
    assert pl.normalize("instagram", url) == "https://www.instagram.com/drvegan_official/"


@pytest.mark.parametrize("url", [
    "https://www.instagram.com/p/Cx1abc/",          # 게시물 — 공지는 바뀐다
    "https://www.instagram.com/reel/Cx1abc/",
    "https://www.instagram.com/stories/drvegan/123/",
    "https://www.instagram.com/explore/",
])
def test_인스타_게시물은_계정이_아니다(pl, url):
    with pytest.raises(pl.LinkError, match="계정 주소가 아니다"):
        pl.normalize("instagram", url)


def test_트립어드바이저는_www로_모으고_꼬리를_뗀다(pl):
    url = "https://m.tripadvisor.co.kr/Restaurant_Review-g294197-d1234567-Reviews-Dr_Vegan-Seoul.html?m=1"
    assert pl.normalize("tripadvisor", url) == \
        "https://www.tripadvisor.co.kr/Restaurant_Review-g294197-d1234567-Reviews-Dr_Vegan-Seoul.html"


def test_트립어드바이저_명소_주소는_식당이_아니다(pl):
    with pytest.raises(pl.LinkError):
        pl.normalize("tripadvisor",
                     "https://www.tripadvisor.co.kr/Attraction_Review-g294197-d1-Reviews-x.html")


def test_모르는_kind는_받지_않는다(pl):
    with pytest.raises(pl.LinkError, match="kind"):
        pl.prepare("blog", "https://blog.naver.com/x", fake({}))


def test_붙여_넣은_단축_주소가_한_번에_넣을_주소가_된다(pl):
    fetch = fake({"https://naver.me/5abc":
                  "https://map.naver.com/p/entry/place/1390960244?c=15.00,0,0,0,dh"})
    assert pl.prepare("naver_place", " https://naver.me/5abc ".strip(), fetch) == \
        "https://map.naver.com/p/entry/place/1390960244"

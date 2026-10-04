"""google_link 의 판정. 딱 하나일 때만 붙이는가, 구글 내용을 남기지 않는가.

망에도 DB 에도 닿지 않는다. 구글 응답은 손으로 만든 후보 목록이다.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "..", "..", "scripts", "dining")


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, os.path.abspath(os.path.join(SCRIPTS, file)))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod          # dataclass 가 모듈을 찾는다
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gl():
    return _load("dining_google_link", "google_link.py")


@pytest.fixture(scope="module")
def normalize():
    return _load("dining_place_link_for_google", "place_link.py").normalize


OURS = dict(place_uid="00000000-0000-0000-0000-000000000001", name="닥터비건",
            address="서울특별시 성동구 연무장길 1", lat=37.5440, lng=127.0560)


def cand(pid: str, name: str, lat: float, lng: float, cid: str = "111") -> dict:
    return {"id": pid, "displayName": {"text": name}, "formattedAddress": "구글 주소",
            "location": {"latitude": lat, "longitude": lng},
            "googleMapsUri": f"https://maps.google.com/?cid={cid}"}


def test_이름과_거리가_맞는_하나면_붙인다(gl, normalize):
    v = gl.judge(gl.Place(**OURS), [cand("ChIJa", "닥터비건 성수점", 37.5441, 127.0561)], normalize)
    assert v.status == "matched"
    assert v.place_id == "ChIJa"
    assert v.url == "https://www.google.com/maps?cid=111"


def test_멀면_붙이지_않는다(gl, normalize):
    v = gl.judge(gl.Place(**OURS), [cand("ChIJa", "닥터비건", 37.5540, 127.0560)], normalize)
    assert v.status == "far"
    assert v.place_id is None


def test_이름이_다르면_붙이지_않는다(gl, normalize):
    v = gl.judge(gl.Place(**OURS), [cand("ChIJa", "옆집 카페", 37.5440, 127.0560)], normalize)
    assert v.status == "none"


def test_둘이_맞으면_고르지_않는다(gl, normalize):
    v = gl.judge(gl.Place(**OURS), [cand("ChIJa", "닥터비건", 37.5440, 127.0560, "1"),
                                    cand("ChIJb", "닥터비건 2호", 37.5441, 127.0560, "2")],
                 normalize)
    assert v.status == "ambiguous"


def test_후보가_없으면_none(gl, normalize):
    assert gl.judge(gl.Place(**OURS), [], normalize).status == "none"


def test_지도_주소가_아니면_붙이지_않는다(gl, normalize):
    c = cand("ChIJa", "닥터비건", 37.5440, 127.0560)
    c["googleMapsUri"] = "https://example.com/x"
    assert gl.judge(gl.Place(**OURS), [c], normalize).status == "none"


def test_판정_사유에_구글_내용이_없다(gl, normalize):
    """note 와 misses 파일에 들어가는 것은 reason 이다. 구글 이름, 주소가 섞이면 안 된다."""
    for c in ([cand("ChIJa", "닥터비건 성수점", 37.5441, 127.0561)],
              [cand("ChIJa", "닥터비건 성수점", 37.5540, 127.0561)]):
        reason = gl.judge(gl.Place(**OURS), c, normalize).reason
        assert "성수점" not in reason and "구글 주소" not in reason


def test_찾는_요청은_우리_좌표로_치우친다(gl):
    body = gl.search_body(gl.Place(**OURS))
    assert body["textQuery"] == "닥터비건 서울특별시 성동구 연무장길 1"
    assert body["locationBias"]["circle"]["center"] == {"latitude": 37.544, "longitude": 127.056}
    assert "regularOpeningHours" not in gl.FIELD_MASK       # 연결에는 영업시간을 받지 않는다


def test_못_붙인_가게_기록은_되읽힌다(gl, tmp_path):
    path = str(tmp_path / "misses.json")
    assert gl.load_misses(path) == {}
    gl.save_misses({"uid": {"name": "x", "status": "none", "reason": "r", "at": "2026-09-23"}}, path)
    assert json.load(open(path, encoding="utf-8"))["uid"]["status"] == "none"
    assert gl.load_misses(path)["uid"]["name"] == "x"


def test_회사_표기는_이름에서_뗀다(gl, normalize):
    ours = dict(OURS, name="(주)닥터비건")
    v = gl.judge(gl.Place(**ours), [cand("ChIJa", "닥터비건 성수점", 37.5441, 127.0561)], normalize)
    assert v.status == "matched"


def test_이름이_달라도_도로명_번지가_같고_가까우면_붙인다(gl, normalize):
    c = dict(cand("ChIJa", "Doctor Vegan", 37.5441, 127.0561), formattedAddress="서울특별시 성동구 연무장길 1")
    v = gl.judge(gl.Place(**OURS), [c], normalize)
    assert v.status == "matched"
    assert "Doctor" not in v.reason          # 구글 이름을 남기지 않는다


def test_같은_주소에_둘이면_고르지_않는다(gl, normalize):
    a = dict(cand("ChIJa", "1층 카페", 37.5441, 127.0561, "1"), formattedAddress="서울 성동구 연무장길 1")
    b = dict(cand("ChIJb", "2층 식당", 37.5441, 127.0561, "2"), formattedAddress="서울 성동구 연무장길 1")
    assert gl.judge(gl.Place(**OURS), [a, b], normalize).status == "ambiguous"


def test_주소가_같아도_멀면_붙이지_않는다(gl, normalize):
    c = dict(cand("ChIJa", "Doctor Vegan", 37.5540, 127.0560), formattedAddress="서울 성동구 연무장길 1")
    assert gl.judge(gl.Place(**OURS), [c], normalize).status == "none"

"""캐치테이블 다리가 모름을 모름으로 지키는지 본다.

여기서 지켜야 할 것은 하나다. 읽지 못한 것을 「아니다」로 바꾸지 않는 것.
빈자리가 없다고 적히면 일정이 바뀌고, 그게 틀렸다는 것은 영영 드러나지 않는다.

scripts/dining 은 꾸러미가 아니라 파일 모음이라 경로로 불러온다.
"""
from __future__ import annotations

import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

KST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
MODULE = os.path.join(ROOT, "final_project_cs", "scripts", "dining", "catchtable.py")
if not os.path.isfile(MODULE):
    MODULE = os.path.join(ROOT, "scripts", "dining", "catchtable.py")


def _load():
    spec = importlib.util.spec_from_file_location("dining_catchtable", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ct = _load()
UID = "11111111-2222-4333-8444-555555555555"


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setattr(ct, "_build_dir", lambda: str(tmp_path))
    return tmp_path


def write_answer(folder, **body):
    path = folder / f"{UID}.answer.json"
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return path


def now():
    return datetime(2026, 9, 25, 12, 10, tzinfo=KST)


# ── 답이 없을 때 ────────────────────────────────────────────

def test_답이_없으면_아니다가_아니라_막힘이다(folder):
    got = ct.read_answer(UID, "waiting", now=now())
    assert got["outcome"] == "blocked"
    assert got["value_state"] == "unknown"


def test_답_파일이_깨졌으면_오류로_적고_값은_모름이다(folder):
    (folder / f"{UID}.answer.json").write_text("{깨짐", encoding="utf-8")
    got = ct.read_answer(UID, "waiting", now=now())
    assert got["outcome"] == "error"
    assert got["value_state"] == "unknown"


# ── 본 시각 ────────────────────────────────────────────────

def test_본_시각이_없으면_지금_값으로_쓰지_않는다(folder):
    write_answer(folder, answers={"waiting": {"state": "yes", "num": 41}})
    got = ct.read_answer(UID, "waiting", now=now())
    assert got["outcome"] == "blocked"
    assert got["evidence"] == "catchtable:no_timestamp"


def test_웨이팅은_오분이_지나면_낡은_값이다(folder):
    write_answer(folder,
                 observed_at="2026-09-25T11:50:00+09:00",
                 answers={"waiting": {"state": "yes", "num": 41}})
    got = ct.read_answer(UID, "waiting", now=now())
    assert got["outcome"] == "blocked"
    assert got["evidence"] == "catchtable:stale"
    assert got["value_state"] == "unknown"


def test_영업시간은_같은_시각이어도_아직_쓴다(folder):
    # 주제마다 신선도가 다르다. 영업시간은 몇 분 만에 바뀌지 않는다.
    write_answer(folder,
                 observed_at="2026-09-25T11:50:00+09:00",
                 answers={"hours": {"state": "yes", "detail": "11:00-22:00"}})
    got = ct.read_answer(UID, "hours", now=now())
    assert got["outcome"] == "ok"
    assert got["value_state"] == "yes"


def test_본_시각_뒤에_사람이_덧붙여도_읽는다(folder):
    write_answer(folder,
                 observed_at="2026-09-25T12:05:00+09:00 (직접 봄)",
                 answers={"waiting": {"state": "yes", "num": 3}})
    assert ct.read_answer(UID, "waiting", now=now())["outcome"] == "ok"


# ── 값 ─────────────────────────────────────────────────────

def test_제대로_온_답은_숫자까지_받는다(folder):
    write_answer(folder,
                 observed_at="2026-09-25T12:05:00+09:00",
                 url="https://app.catchtable.co.kr/ct/shop/maple",
                 answers={"waiting": {"state": "yes", "num": 41,
                                      "detail": "현재 웨이팅 41팀"}})
    got = ct.read_answer(UID, "waiting", now=now())
    assert got["outcome"] == "ok"
    assert got["value_state"] == "yes"
    assert got["value_num"] == 41
    assert got["value_detail"] == "현재 웨이팅 41팀"
    assert got["evidence"].startswith("catchtable:https://")


def test_모르는_상태값은_모름으로_떨어진다(folder):
    write_answer(folder,
                 observed_at="2026-09-25T12:05:00+09:00",
                 answers={"waiting": {"state": "아마도"}})
    got = ct.read_answer(UID, "waiting", now=now())
    assert got["outcome"] == "ok"
    assert got["value_state"] == "unknown"


def test_숫자가_아닌_것은_숫자로_적지_않는다(folder):
    write_answer(folder,
                 observed_at="2026-09-25T12:05:00+09:00",
                 answers={"waiting": {"state": "yes", "num": "많음"}})
    assert ct.read_answer(UID, "waiting", now=now())["value_num"] is None


def test_참거짓은_숫자가_아니다(folder):
    # True 는 파이썬에서 int 다. 그대로 받으면 대기 1팀이 되어 버린다.
    write_answer(folder,
                 observed_at="2026-09-25T12:05:00+09:00",
                 answers={"waiting": {"state": "yes", "num": True}})
    assert ct.read_answer(UID, "waiting", now=now())["value_num"] is None


def test_물어본_적_없는_주제는_답이_없다고_적는다(folder):
    write_answer(folder,
                 observed_at="2026-09-25T12:05:00+09:00",
                 answers={"waiting": {"state": "yes"}})
    got = ct.read_answer(UID, "vacancy", now=now())
    assert got["outcome"] == "blocked"
    assert got["evidence"] == "catchtable:missing_topic"


def test_주소가_없으면_증거에_그렇게_남는다(folder):
    write_answer(folder,
                 observed_at="2026-09-25T12:05:00+09:00",
                 answers={"vacancy": {"state": "no"}})
    assert ct.read_answer(UID, "vacancy", now=now())["evidence"] == "catchtable:no_url"


# ── 의뢰 ───────────────────────────────────────────────────

def test_의뢰는_DB_가_만든_말을_그대로_싣는다(folder):
    prompt = {"place_uid": UID, "name": "메이플탑",
              "target_at": "2026-09-25T12:00:00+09:00",
              "sentence": "메이플탑 성수 09월 25일 12시 기준으로 현장 웨이팅 확인해줘."}
    path = ct.write_ask(UID, prompt, ["waiting"])
    got = json.loads(open(path, encoding="utf-8").read())
    assert got["sentence"] == prompt["sentence"]
    assert "메이플탑" in got["search_url"]
    assert got["topics"][0]["topic"] == "waiting"
    assert any("모름" in rule for rule in got["rules"])


def test_답이_놓이면_기다리는_목록에서_빠진다(folder):
    ct.write_ask(UID, {"place_uid": UID, "name": "메이플탑"}, ["waiting"])
    assert len(ct.pending()) == 1
    write_answer(folder, observed_at="2026-09-25T12:05:00+09:00", answers={})
    assert ct.pending() == []


# ── 답 놓기 ────────────────────────────────────────────────

def test_답을_놓으면_바로_읽힌다(folder):
    ct.write_answer(UID, "https://app.catchtable.co.kr/ct/shop/x",
                    {"waiting": {"state": "yes", "num": 41}})
    got = ct.read_answer(UID, "waiting")
    assert got["outcome"] == "ok"
    assert got["value_num"] == 41


def test_본_시각은_손으로_적지_않고_찍힌다(folder):
    # 사람이 적게 하면 화면을 본 시각이 아니라 파일을 쓴 시각이 들어간다.
    path = ct.write_answer(UID, "https://x", {"waiting": {"state": "yes"}})
    got = json.loads(open(path, encoding="utf-8").read())
    assert ct._parse_observed(got["observed_at"]) is not None


def test_육분_된_웨이팅도_낡았다(folder):
    # 예전에는 15분까지 받았다. DB 는 적은 시각부터 기한을 세므로
    # 10분 된 값이 5분 더 「지금」 행세를 했다. 여기서 5분으로 끊는다.
    write_answer(folder,
                 observed_at="2026-09-25T12:04:00+09:00",
                 answers={"waiting": {"state": "yes", "num": 41}})
    assert ct.read_answer(UID, "waiting", now=now())["evidence"] == "catchtable:stale"


# ── 화면 글자 읽기 (catchtable_auto) ─────────────────────────
#
# 2026-09-22 에 크롬으로 실제로 읽은 메이플탑 매장 페이지 글자다.
# 파서가 틀리면 값이 틀린다. 브라우저 없이 여기서 잡는다.

AUTO = os.path.join(os.path.dirname(MODULE), "catchtable_auto.py")


def _load_script(name, filename):
    import sys
    sys.path.insert(0, os.path.dirname(MODULE))
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(os.path.dirname(MODULE), filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


auto = _load_script("dining_catchtable_auto", "catchtable_auto.py")


def lines(*rows):
    return "\n".join(rows) + "\n"


MAPLETOP = lines(
    "예약", "웨이팅", "새로고침", "매장", "매장 식사", "웨이팅이 없어요",
    "요일별 평균 웨이팅 시간", "대체로 웨이팅이 없습니다",
    "2팀 이상부터 온라인 웨이팅 가능",
)


def test_실제_화면에서_웨이팅_없음을_읽는다():
    got = auto.parse_waiting(MAPLETOP)
    assert got == {"state": "no", "num": 0, "detail": "웨이팅이 없어요"}


def test_하단_버튼의_2팀을_웨이팅으로_읽지_않는다():
    # 예전 파서는 「웨이팅」과 「팀」이 같은 줄에 있으면 읽었다.
    text = lines("매장 식사", "확인 중", "2팀 이상부터 온라인 웨이팅 가능")
    assert auto.parse_waiting(text) is None


def test_포장이_없어요여도_매장_41팀은_41팀이다():
    # 예전 파서는 화면 어디든 「웨이팅이 없어요」가 있으면 없음으로 읽었다.
    text = lines("매장", "매장 식사", "41팀", "포장", "포장 주문", "웨이팅이 없어요")
    got = auto.parse_waiting(text)
    assert got["state"] == "yes"
    assert got["num"] == 41


def test_매장_식사가_없으면_읽지_않는다():
    # 로그인이 풀려 껍데기만 오면 이 줄이 없다. 없음이 아니라 모름이다.
    assert auto.parse_waiting(lines("캐치테이블", "즐거운 미식 생활의 시작")) is None


def test_실제_매장정보에서_요일별_영업시간을_모은다():
    text = lines("영업시간", "월·09:00 ~ 18:00", "월·17:30·라스트오더",
                 "토·09:00 ~ 19:00", "월·18:30·라스트오더", "홈페이지")
    got = auto.parse_hours(text)
    assert got["state"] == "unknown"
    assert "토·09:00 ~ 19:00" in got["detail"]


def test_꺼져_있으면_돌지_않는다(monkeypatch):
    class Args:
        i_know = True

    monkeypatch.delenv("DINING_CATCHTABLE_AUTO", raising=False)
    assert auto.guard(Args()) is not None

    monkeypatch.setenv("DINING_CATCHTABLE_AUTO", "1")
    Args.i_know = False
    assert auto.guard(Args()) is not None

    Args.i_know = True
    assert auto.guard(Args()) is None


def test_캐치테이블에서_본_영업시간은_캐치테이블_출처다():
    rc = _load_script("dining_run_check", "run_check.py")
    # 예전에는 auto_map_check 로 적혔다. 지도를 본 적이 없는데도.
    assert rc.default_source("catchtable", "hours") == "catchtable_trial"
    assert rc.default_source("catchtable", "closure") == "catchtable_trial"
    assert rc.default_source("manual", "hours") == "operator_check"

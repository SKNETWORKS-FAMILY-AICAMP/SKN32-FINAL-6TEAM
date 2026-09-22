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


def test_웨이팅은_십오분이_지나면_낡은_값이다(folder):
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

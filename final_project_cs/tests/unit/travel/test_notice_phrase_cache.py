# -*- coding: utf-8 -*-
"""알림 문구의 **언어별 생성 캐시** — wiki `architecture/notifications.md` 「언어」.

★이 시험이 지키는 것은 두 가지다.
  ① **모델을 언어·문구틀마다 한 번만 부른다**(같은 언어의 다음 안내는 0회).
  ② ★★**값은 절대 섞이지 않는다** — 캐시에 담기는 것은 틀뿐이고, 시각·장소·금액·예약번호는
     알림마다 그 알림의 값으로 채운다. 값이 다른 두 알림이 같은 캐시 항목을 써도
     10:50 출발 안내에 11:50 이 나가지 않는다.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.infrastructure.notify.discord import DiscordWebhook, phrase_of, render
from app.infrastructure.notify.phrase import Phrase, PhraseCache, PhraseSlotsLost, fill
from app.modules.travel_ops.itinerary import Item
from app.modules.travel_ops.trip_reminders import day_phrase, departure_phrase, notice_fields

KST = ZoneInfo("Asia/Seoul")


class _CountingTranslator:
    """틀을 「번역」한다 — 고정 접두를 붙이고 값 자리는 그대로 둔다. 부른 횟수를 센다."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def __call__(self, text: str, locale: str) -> str:
        self.calls.append((text, locale))
        return f"[{locale}] " + text.replace("출발", "出發").replace("다음 일정", "下一個行程")


def _hook(translator, *, phrases=None):
    sent: list[str] = []

    def transport(url, json):
        sent.append(json["content"])
        return httpx.Response(204, request=httpx.Request("POST", url))

    return DiscordWebhook("https://example.invalid/hook", transport=transport,
                          translator=translator, phrases=phrases), sent


def _item(hhmm: str, title: str, *, seq: int = 1, kind: str = "mobility", ends: str = "11:15") -> Item:
    at = lambda v: datetime.strptime(f"2026-09-22 {v}", "%Y-%m-%d %H:%M").replace(tzinfo=KST)  # noqa: E731
    return Item(item_id=uuid4(), seq=seq, kind=kind, title=title, place_id=None,
                starts_at=at(hhmm), ends_at=at(ends), detail={})


def _departure_notice(leave: str, title: str, *, locale="zh-TW", version=2, url=None):
    move = _item(leave, title, seq=3, ends="11:15")
    following = _item("11:15", "성수 카페거리", seq=4, kind="activity", ends="12:30")
    fields = notice_fields(departure_phrase(move, following, None))
    payload = {**fields, "locale": locale, "version": version}
    if url:
        payload["plan_url"] = url
    return {"topic": "trip.notice", "payload": payload}


# ── ① 모델을 언어·틀마다 한 번만 부른다 ───────────────────────────
def test_the_same_template_in_the_same_language_calls_the_model_once():
    """출발 안내 4건 → 번역 호출 1/4. 나머지 3건은 담아 둔 틀을 쓴다."""
    translator = _CountingTranslator()
    hook, sent = _hook(translator)
    for leave, title in [("10:50", "2호선 잠실→성수"), ("15:00", "버스 성수→종로"),
                         ("17:15", "도보 종로→광장시장"), ("19:20", "3호선 종로→잠실")]:
        hook(_departure_notice(leave, title))
    assert len(sent) == 4
    assert len(translator.calls) == 1, translator.calls      # 1/4 = 25% 만 모델을 탔다
    assert hook.phrases.stats() == {"entries": 1, "hits": 3, "misses": 1, "rejected": 0}


def test_another_language_is_generated_once_of_its_own():
    translator = _CountingTranslator()
    hook, sent = _hook(translator)
    for locale in ("zh-TW", "zh-TW", "en", "en", "ja"):
        hook(_departure_notice("10:50", "2호선 잠실→성수", locale=locale))
    assert [locale for _, locale in translator.calls] == ["zh-TW", "en", "ja"]   # 3/5
    assert hook.phrases.stats()["entries"] == 3


def test_korean_never_calls_the_model_and_never_fills_the_cache():
    translator = _CountingTranslator()
    hook, sent = _hook(translator)
    hook(_departure_notice("10:50", "2호선 잠실→성수", locale="ko"))
    assert translator.calls == [] and len(hook.phrases) == 0
    assert sent[0].startswith("10:50 출발")


# ── ② ★★값이 섞이지 않는다 ────────────────────────────────────────
def test_two_notices_that_share_a_cached_template_keep_their_own_time_and_place():
    """★이 시험이 이 작업의 핵심이다 — 캐시를 완성 문장으로 만들면 여기서 깨진다."""
    translator = _CountingTranslator()
    hook, sent = _hook(translator)
    hook(_departure_notice("10:50", "2호선 잠실→성수"))
    hook(_departure_notice("15:00", "버스 성수→종로"))
    assert len(translator.calls) == 1                  # 두 번째는 담아 둔 틀을 썼다
    assert "10:50 出發 — 2호선 잠실→성수 (10:50–11:15)." in sent[0]
    assert "15:00 出發 — 버스 성수→종로 (15:00–11:15)." in sent[1]
    assert "15:00" not in sent[0] and "10:50" not in sent[1]     # ★시각이 건너가지 않았다
    assert "버스 성수→종로" not in sent[0] and "2호선 잠실→성수" not in sent[1]


def test_the_cached_template_itself_carries_no_time_place_or_link():
    """담아 두는 것에 값이 들어 있지 않다 — 들어 있으면 위 시험이 언젠가 깨진다."""
    phrase = phrase_of(_departure_notice("10:50", "2호선 잠실→성수",
                                         url="https://plan.example/abc")["payload"])
    assert phrase.cacheable
    for value in ("10:50", "11:15", "2호선 잠실→성수", "성수 카페거리",
                  "https://plan.example/abc", "2"):
        assert value not in phrase.template, (value, phrase.template)
    assert phrase.render().endswith("https://plan.example/abc")


def test_version_and_link_and_other_options_stay_raw_values():
    translator = _CountingTranslator()
    hook, sent = _hook(translator)
    for version, url in [(2, "https://plan.example/aaa"), (7, "https://plan.example/bbb")]:
        hook(_departure_notice("10:50", "2호선 잠실→성수", version=version, url=url))
    assert len(translator.calls) == 1
    assert "(일정 버전 2)" in sent[0] and sent[0].endswith("https://plan.example/aaa")
    assert "(일정 버전 7)" in sent[1] and sent[1].endswith("https://plan.example/bbb")


def test_a_day_notice_keeps_its_own_stops():
    translator = _CountingTranslator()
    hook, sent = _hook(translator)
    day_one = [_item("09:00", "잠실 스카이타워", seq=1, kind="activity", ends="10:30")]
    day_two = [_item("09:30", "경복궁", seq=1, kind="activity", ends="11:00")]
    for items in (day_one, day_two):
        fields = notice_fields(day_phrase(items, items[0].starts_at.astimezone(KST).date()))
        hook({"topic": "trip.notice", "payload": {**fields, "locale": "zh-TW"}})
    assert len(translator.calls) == 1
    assert "09:00 잠실 스카이타워" in sent[0] and "잠실" not in sent[1]
    assert "09:30 경복궁" in sent[1]


# ── 번역이 값 자리를 잃으면 버린다 ─────────────────────────────────
def test_a_translation_that_drops_a_slot_is_rejected_and_not_cached():
    """★자리가 사라지면 시각이 통째로 빠진 문장이 나간다 — 버리고 한국어 원문으로 보낸다."""
    def losing(text, locale):
        return text.replace("{leave}", "").replace("{title}", "")

    hook, sent = _hook(losing)
    hook(_departure_notice("10:50", "2호선 잠실→성수"))
    assert sent[0].startswith("[번역 실패 — 한국어 원문]") and "10:50 출발" in sent[0]
    assert hook.translation_failures == 1 and len(hook.phrases) == 0
    assert hook.phrases.stats()["rejected"] == 1


def test_a_translation_that_duplicates_a_slot_is_rejected():
    with pytest.raises(PhraseSlotsLost):
        Phrase("{a} 출발", {"a": "10:50"}).with_translation("{a} 出發 {a}")


def test_a_failed_translator_still_sends_the_korean_original():
    def broken(text, locale):
        raise RuntimeError("model down")

    hook, sent = _hook(broken)
    hook(_departure_notice("10:50", "2호선 잠실→성수"))
    assert sent[0].startswith("[번역 실패 — 한국어 원문]") and hook.translation_failures == 1
    assert len(hook.phrases) == 0                 # 실패한 번역은 담기지 않는다


# ── 변경 통지(①)는 담지 않는다 ────────────────────────────────────
def test_a_generated_change_notice_is_not_cached_and_is_translated_each_time():
    """★값이 채워진 완성 문장은 캐시하지 않는다 — ①의 대안 설명은 매번 새 문장이다."""
    translator = _CountingTranslator()
    hook, sent = _hook(translator)
    for text in ["점심 도착이 14:10(으)로 늦어져 식당을 옮깁니다.",
                 "점심 도착이 15:40(으)로 늦어져 식당을 옮깁니다."]:
        hook({"topic": "trip.notice", "payload": {"text": text, "locale": "zh-TW", "version": 4}})
    assert len(translator.calls) == 2 and len(hook.phrases) == 0
    assert "14:10" in sent[0] and "15:40" in sent[1] and "14:10" not in sent[1]


# ── 채워 넣기 자체의 안전 ─────────────────────────────────────────
def test_a_value_that_looks_like_a_slot_is_not_substituted_again():
    """★값을 한 번만 훑는다 — 값 안의 `{b}` 가 다시 값으로 읽히면 엉뚱한 글이 들어간다."""
    assert fill("{a}-{b}", {"a": "{b}", "b": "성수"}) == "{b}-성수"


def test_an_empty_notice_is_still_refused():
    with pytest.raises(ValueError):
        render({"template": "{stops}", "values": {"stops": "   "}})


# ── 프로세스를 넘겨 쓴다 ──────────────────────────────────────────
def test_the_cache_survives_a_restart_through_its_file(tmp_path):
    """★배달 루프는 `--once` 로도 돈다 — 파일이 없으면 프로세스마다 다시 부른다."""
    path = tmp_path / "phrasebook.json"
    translator = _CountingTranslator()
    first = PhraseCache(path=path)
    hook, _ = _hook(translator, phrases=first)
    hook(_departure_notice("10:50", "2호선 잠실→성수"))
    first.save()

    second = PhraseCache(path=path)
    assert second.load() == 1
    hook2, sent = _hook(translator, phrases=second)
    hook2(_departure_notice("15:00", "버스 성수→종로"))
    assert len(translator.calls) == 1 and second.stats()["hits"] == 1
    assert "15:00 出發 — 버스 성수→종로" in sent[0]


def test_the_cache_does_not_grow_without_a_bound():
    cache = PhraseCache(max_entries=2)
    for n in range(5):
        cache.localize(Phrase(f"틀 {n} {{v}}", {"v": "값"}), "en", lambda text, locale: text)
    assert len(cache) == 2 and cache.stats()["misses"] == 5

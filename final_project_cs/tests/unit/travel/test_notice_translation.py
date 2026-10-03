# -*- coding: utf-8 -*-
"""통지를 보낼 때 고객 언어로 — 결정 14. ★숫자(시각·금액·버전)가 빠진 번역은 쓰지 않는다."""
from __future__ import annotations

import httpx
import pytest

from app.infrastructure.notify import DiscordWebhook
from app.infrastructure.notify.translate import TranslationRejected, is_korean, make_translator

TEXT = "점심 도착이 14:10(으)로 늦어져 식당을 옮깁니다. (일정 버전 4)"


class _Chat:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def text(self, system, user):
        self.calls.append(user)
        return self.answer


def test_a_translation_that_keeps_every_number_is_used():
    chat = _Chat("午餐抵達延後至 14:10，改換餐廳。（行程版本 4）")
    assert make_translator(chat)(TEXT, "zh-TW").startswith("午餐")
    assert "zh-TW" in chat.calls[0]


def test_a_translation_that_loses_a_time_is_rejected():
    with pytest.raises(TranslationRejected):
        make_translator(_Chat("午餐延後，改換餐廳。（行程版本 4）"))(TEXT, "zh-TW")


# 결함 인계 #4(2026-10-02): 집합 포함만 봐서 「5 5」→「5 999」가 통과했다
@pytest.mark.parametrize("original,translated", [
    ("5 5", "5 999"),                                            # 출현 횟수가 빠지고(5 하나) 새 숫자(999)가 생겼다
    ("5 5", "5"),                                                # 횟수만 빠졌다
    ("출발 14:10 도착 15:30", "14:10 出發 14:10 抵達"),             # 한 숫자를 되풀이해 다른 숫자(15:30)를 지웠다
    ("버전 4", "版本 4 · 7"),                                      # 새 숫자 7 이 더해졌다
])
def test_a_translation_with_a_wrong_number_count_or_a_new_number_is_rejected(original, translated):
    with pytest.raises(TranslationRejected):
        make_translator(_Chat(translated))(original, "zh-TW")


def test_repeating_a_number_that_is_already_in_the_notice_is_allowed():
    """이미 있는 값을 괄호로 되풀이하는 것(원문 병기)은 새 사실이 아니다."""
    assert make_translator(_Chat("版本 4 (버전 4)"))("버전 4", "zh-TW").startswith("版本")


@pytest.mark.parametrize("locale,expected", [("ko", True), ("ko-KR", True), (None, True),
                                             ("zh-TW", False), ("en", False)])
def test_korean_is_not_translated(locale, expected):
    assert is_korean(locale) is expected


def _webhook(translator):
    sent = []

    def transport(url, json):
        sent.append(json["content"])
        return httpx.Response(204, request=httpx.Request("POST", url))
    return DiscordWebhook("https://example.invalid/hook", transport=transport,
                          translator=translator), sent


def _message(locale):
    return {"topic": "trip.notice", "payload": {"text": TEXT, "version": 4, "locale": locale}}


def test_the_notice_goes_out_in_the_trip_language():
    hook, sent = _webhook(make_translator(_Chat("午餐抵達延後至 14:10。（行程版本 4）\n(일정 버전 4)")))
    hook(_message("zh-TW"))
    assert sent[0].startswith("午餐")


def test_a_failed_translation_still_sends_the_korean_original_and_is_counted():
    """★번역이 실패해도 알림은 간다 — 안 보내는 것보다 낫다. 대신 표시하고 센다."""
    def broken(text, locale):
        raise RuntimeError("model down")
    hook, sent = _webhook(broken)
    hook(_message("zh-TW"))
    assert sent[0].startswith("[번역 실패 — 한국어 원문]") and hook.translation_failures == 1


def test_a_korean_trip_is_sent_as_is():
    hook, sent = _webhook(lambda text, locale: pytest.fail("한국어는 옮기지 않는다"))
    hook(_message("ko"))
    assert sent[0].startswith("점심 도착")

# -*- coding: utf-8 -*-
"""알림 문구의 **틀**과 **언어별 생성 캐시** — wiki `architecture/notifications.md` 「언어」 절.

★한 줄로: **틀만 옮기고 값은 원값 그대로 채운다.** 그래서 같은 언어의 다음 안내는 모델을
  안 부른다("문구틀·언어마다 처음 한 번 생성하고 재사용한다").

★★**값이 채워진 완성 문장은 캐시하지 않는다.** 캐시 열쇠는 `(틀, 언어)` 이고, 틀에는
  시각·날짜·금액·장소 이름·예약번호가 들어 있지 않다(`{leave}` 같은 **자리**만 있다).
  값은 알림마다 그 알림의 것으로 채우므로 **값이 다른 두 알림이 같은 캐시 항목을 써도
  시각이 섞이지 않는다.** 완성 문장을 캐시했다면 10:50 출발 안내가 11:50 출발에 나갈 수
  있었다 — 그것을 구조로 막는다.

★**자리가 번역에서 사라지면 그 번역을 버린다.** 모델이 `{leave}` 를 옮겨 버리거나 하나로
  합치면 시각이 통째로 빠진 문장이 나간다. 이름별 **개수까지** 대조해 다르면 예외를 올리고
  (`PhraseSlotsLost`) 캐시에 넣지 않는다 — 부르는 쪽이 「번역 실패」로 세고 한국어 원문을
  보낸다(조용한 스킵 금지).

★**틀이 없는 통지(① 변경 통지의 대안 설명)는 캐시하지 않는다**(`cacheable=False`).
  그건 매번 새로 생성되는 문장이라 재사용할 것이 없고, 완성 문장을 열쇠로 삼는 캐시는
  위 규칙이 금지한다.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

#: 값이 들어갈 자리. `{leave}` · `{_version}` 처럼 이름을 쓴다.
SLOT = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

#: 캐시에 담아 둘 `(틀, 언어)` 최대 개수. 넘으면 오래된 것부터 버린다.
#: ★틀 수는 문구 종류(하루 시작·전날·출발 변형) × 언어 수라 작다 — 상한은 폭주 방지다.
MAX_ENTRIES = 512


class PhraseSlotsLost(RuntimeError):
    """번역이 값 자리를 잃거나 개수를 바꿨다 — 쓰지 않는다(시각이 빠진 문장이 나간다)."""


def fill(template: str, values: Mapping[str, Any]) -> str:
    """틀의 자리에 값을 **한 번만** 훑어 채운다.

    ★한 번만 훑는 것이 중요하다 — 값 안에 `{...}` 가 들어 있어도 그것을 다시 값으로 보지
      않는다. `str.replace` 를 값마다 돌리면 앞 값이 넣은 글자가 뒤 값의 자리로 읽힌다.
    """
    return SLOT.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0),
                    template)


def slot_counts(template: str) -> Counter:
    return Counter(SLOT.findall(template))


def check_slots(source: str, translated: str) -> None:
    """번역이 틀의 자리를 **이름별 개수까지** 그대로 들고 있는지 본다."""
    want, got = slot_counts(source), slot_counts(translated)
    if want != got:
        lost = sorted((want - got).keys()) or sorted((got - want).keys())
        raise PhraseSlotsLost(f"번역이 값 자리를 바꿨다: {lost[:5]}")


@dataclass(frozen=True)
class Phrase:
    """옮길 **틀**과 옮기지 않을 **원값**.

    `cacheable=False` 면 틀 자체가 그때그때 생성된 문장이라는 뜻이다 — 옮기되 담아 두지 않는다.
    """

    template: str
    values: Mapping[str, Any] = field(default_factory=dict)
    cacheable: bool = True

    def render(self) -> str:
        """한국어 원문 — 값을 채운 완성 문장."""
        return fill(self.template, self.values)

    def with_translation(self, translated_template: str) -> str:
        """옮겨진 틀에 **이 알림의 원값**을 채운다. 값은 어느 언어에서도 원값 그대로다."""
        check_slots(self.template, translated_template)
        return fill(translated_template, self.values)


class PhraseCache:
    """`(틀, 언어) → 옮겨진 틀`. 같은 틀·같은 언어의 다음 알림은 모델을 안 부른다.

    ★세는 값 — `hits`(모델을 안 부른 횟수) · `misses`(모델을 부른 횟수) ·
      `rejected`(자리를 잃어 버린 번역 수). 재사용률을 말할 때 분모는 `hits + misses` 다.
    """

    def __init__(self, *, path: str | Path | None = None, max_entries: int = MAX_ENTRIES) -> None:
        self._entries: dict[tuple[str, str], str] = {}
        self._max = max_entries
        self.path = Path(path) if path else None
        self.hits = self.misses = self.rejected = 0

    # ── 쓰는 자리 ──────────────────────────────────────────────
    def localize(self, phrase: Phrase, locale: str,
                 translate: Callable[[str, str], str]) -> str:
        """이 언어로 된 완성 문장. 틀이 이미 있으면 모델을 부르지 않는다."""
        key = (phrase.template, locale)
        cached = self._entries.get(key) if phrase.cacheable else None
        if cached is not None:
            self.hits += 1
            # ★담아 둔 것은 **틀**이다 — 값은 지금 이 알림의 것으로 채운다.
            return fill(cached, phrase.values)
        self.misses += 1
        translated = translate(phrase.template, locale)
        try:
            filled = phrase.with_translation(translated)
        except PhraseSlotsLost:
            self.rejected += 1
            raise
        if phrase.cacheable:
            self._put(key, translated)
        return filled

    def _put(self, key: tuple[str, str], translated: str) -> None:
        self._entries[key] = translated
        while len(self._entries) > self._max:        # 오래된 것부터 버린다(들어온 순서)
            self._entries.pop(next(iter(self._entries)))

    def __len__(self) -> int:
        return len(self._entries)

    def stats(self) -> dict[str, int]:
        return {"entries": len(self._entries), "hits": self.hits, "misses": self.misses,
                "rejected": self.rejected}

    # ── 프로세스를 넘겨 쓰는 자리 ──────────────────────────────
    # ★배달 루프는 `--once` 로도 돌아서(프로세스가 매번 죽는다) 메모리 캐시만으로는
    #   재사용이 안 된다. 파일로 남겨 다음 실행이 이어 쓴다. 파일은 `var/` 라 커밋되지 않는다.
    def load(self) -> int:
        """담아 둔 틀을 읽는다. 파일이 없으면 0. ★깨진 파일은 조용히 넘기지 않고 올린다."""
        if self.path is None or not self.path.is_file():
            return 0
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"문구 캐시 파일 형식이 아니다: {self.path}")
        for row in data:
            self._put((str(row["template"]), str(row["locale"])), str(row["translated"]))
        return len(self._entries)

    def save(self) -> None:
        """★같은 이름에 바로 쓰지 않는다 — 임시 파일에 쓰고 바꿔 끼운다(중간에 죽어도 안 깨진다)."""
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rows = [{"template": template, "locale": locale, "translated": translated}
                for (template, locale), translated in self._entries.items()]
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)


__all__ = ["MAX_ENTRIES", "Phrase", "PhraseCache", "PhraseSlotsLost", "SLOT", "check_slots",
           "fill", "slot_counts"]

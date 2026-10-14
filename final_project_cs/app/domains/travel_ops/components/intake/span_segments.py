"""장소별 원문 구간 — 추출과 조립이 같은 경계를 사용한다.

장소 사이의 연결어 뒤와 다음 일정의 수식어 앞에서 나눈다. 장소 이름만
경계로 쓰면 다음 장소의 「점심은」「저녁 무렵」이 앞 장소에도 남는다.
"""
from __future__ import annotations

import re

from .rules import TIME

_JOIN = re.compile(r"[,;]|그리고|그\s*다음|이어서|(?:[가-힣]+(?:다가|고|나서))(?=\s|$)|"
                   r"(?:[가-힣]+(?:한|은)\s*(?:뒤|후))(?=\s|$)")
_PREFIX = re.compile(
    r"(?:오전|오후)(?=\s|\d|엔|에는)|"
    r"(?:아침|조식|점심|중식|저녁|석식)(?=$|[^가-힣]|은|는|엔|에|무렵|쯤|즈음|께|때)|"
    r"(?:오늘|내일|모레|글피|지금|현재|당장)(?=$|[^가-힣]|은|는|엔|에)|"
    r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}\s*월\s*\d{1,2}\s*일")
_POSTFIX = re.compile(r"\s*(?:에서|은|는|에)(?=\s|$)")


def split_segments(text: str, places: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """원문 순서의 장소 범위마다 겹치지 않는 (시작, 끝)을 돌려준다."""
    if not places:
        return []
    boundaries = [0]
    for (_, previous_end), (next_start, _) in zip(places, places[1:]):
        gap = text[previous_end:next_start]
        joins = list(_JOIN.finditer(gap))
        offset = joins[-1].end() if joins else 0
        tail = gap[offset:]
        cues = [match for match in (_PREFIX.search(tail), TIME.search(tail)) if match is not None]
        cue = min(cues, key=lambda match: match.start()) if cues else None
        if cue is not None and (joins or not _POSTFIX.match(gap)):
            boundary = previous_end + offset + cue.start()
        elif joins:
            boundary = previous_end + offset
        else:
            boundary = next_start
        while boundary < next_start and text[boundary].isspace():
            boundary += 1
        boundaries.append(boundary)
    boundaries.append(len(text))
    return list(zip(boundaries, boundaries[1:]))


__all__ = ["split_segments"]

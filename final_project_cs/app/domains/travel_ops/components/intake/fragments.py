# -*- coding: utf-8 -*-
"""입구 하나 — 계획서 · 채팅 수정 요청을 **원래 위치가 붙은 조각**으로 펼치고, 긴 글은 **길이로** 나눈다. `[2026-10-16 D-025]`

    explode(texts)        글 여럿(원본 · 메시지) → 줄 조각 목록. 조각마다 원래 위치(원본 n 의 몇째 줄 · 메시지 n 의 몇째 줄 · 시트/행)
    chunk(fragments)      모델 한 번에 보낼 묶음. ★날짜가 아니라 **글자 수**로 자르고, 앞 묶음 끝 줄을 겹쳐 붙인다
    ReadState             앞 묶음에서 읽은 상태(지금 몇째 날 · 앞에 나온 장소) — 다음 묶음 지시문에 붙인다

★입력 모양(표냐 글이냐, 계획서냐 채팅이냐)으로 **미리 갈라 뜻을 정하지 않는다** — 어느 입력이든 같은 조각이 되고, 뜻은 읽기 에이전트가 정한다.
★줄 번호(`n`)는 펼친 전체에서 1부터 — 모델은 이 번호로 가리키고, 코드는 그 번호의 원문으로 인용을 확인한다(`agent_read.ground`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

#: 한 묶음의 글자 수 상한(우리가 고른 값) — 가르친 E4B 문맥 8,192 토큰 안에 지시문 · 답(최대 3,072 토큰)이 함께 들어가게.
#: 한국어 1글자 ≈ 1토큰 안팎 `[추정]`. 시험지 69건 중 이보다 긴 원문은 없다(가장 긴 것 약 1,100자 `[실측 2026-10-16]`).
CHUNK_CHARS = 1800
#: 앞 묶음의 끝 줄을 다음 묶음 앞에 몇 줄 겹쳐 붙이나(우리가 고른 값) — 묶음 경계에서 「일차 머리줄 · 시각 줄」이 갈라지지 않게
OVERLAP_LINES = 2


@dataclass(frozen=True)
class Fragment:
    """줄 조각 하나. `n` = 펼친 전체에서의 줄 번호(1부터), `origin` = 원래 위치."""

    n: int
    text: str
    origin: dict[str, Any]

    def where(self) -> str:
        """사람이 읽는 위치 — 확인 화면 · 기록용."""
        o = self.origin
        if "message" in o:
            return f"메시지 {o['message']} · {o['line']}째 줄"
        if "sheet" in o:
            return f"{o['sheet']} 시트 {o.get('row', '?')}행"
        return f"원본 {o.get('source', 0) + 1} · {o.get('line')}째 줄"


@dataclass
class Chunk:
    """모델 한 번에 보낼 묶음. `fragments` 앞쪽 `overlap` 개는 앞 묶음과 겹친 줄(읽기만 하고 새 항목으로 세지 않는다)."""

    fragments: list[Fragment]
    overlap: int = 0

    @property
    def lines(self) -> list[str]:
        return [f.text for f in self.fragments]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def new_numbers(self) -> set[int]:
        return {f.n for f in self.fragments[self.overlap:]}


@dataclass
class ReadState:
    """앞 묶음에서 읽은 상태 — 다음 묶음이 「지금 몇째 날인지 · 앞에서 무엇이 나왔는지」 알게."""

    day: int | None = None
    date: str | None = None
    places: list[str] = field(default_factory=list)

    def note(self) -> str:
        if self.day is None and self.date is None and not self.places:
            return ""
        bits = []
        if self.day is not None or self.date:
            bits.append(f"day {self.day}" + (f" ({self.date})" if self.date else ""))
        if self.places:
            bits.append("earlier stops: " + ", ".join(self.places[-6:]))
        return "This message continues an earlier part. State so far: " + "; ".join(bits) + "."


def explode(texts: Iterable[tuple[str, dict[str, Any]]]) -> list[Fragment]:
    """(글, 원래 위치의 뿌리) 여럿 → 줄 조각. 뿌리 예: `{"source": 0}` · `{"message": 3}` · `{"source": 1, "sheet": "1일차"}`.

    빈 줄은 줄 번호를 지키려고 그대로 둔다(규칙 읽기 · 받아쓰기 누락 검사가 쓰는 줄 번호와 맞춘다)."""
    out: list[Fragment] = []
    for text, root in texts:
        rows = root.get("rows")                        # 표 원본이면 줄마다 행 번호(같은 길이) — 없으면 줄 번호만
        base = {k: v for k, v in root.items() if k != "rows"}
        for k, line in enumerate((text or "").splitlines(), start=1):
            origin = {**base, "line": k}
            if rows and k - 1 < len(rows):
                origin["row"] = rows[k - 1]
            out.append(Fragment(len(out) + 1, line, origin))
    return out


def chunk(fragments: list[Fragment], *, limit: int = CHUNK_CHARS, overlap: int = OVERLAP_LINES) -> list[Chunk]:
    """길이로 나눈다. 한 줄이 상한보다 길면 그 줄 하나가 한 묶음이다(줄을 쪼개지 않는다 — 인용이 줄 안에서 확인돼야 한다)."""
    if not fragments:
        return []
    chunks: list[Chunk] = []
    current: list[Fragment] = []
    carried = size = 0
    for frag in fragments:
        length = len(frag.text) + 1
        if len(current) > carried and size + length > limit:
            chunks.append(Chunk(current, overlap=carried))
            tail = current[-overlap:] if overlap else []
            current, carried, size = list(tail), len(tail), sum(len(f.text) + 1 for f in tail)
        current.append(frag)
        size += length
    chunks.append(Chunk(current, overlap=carried))
    return chunks


__all__ = ["CHUNK_CHARS", "Chunk", "Fragment", "OVERLAP_LINES", "ReadState", "chunk", "explode"]

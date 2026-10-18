"""Copying a schedule can put a clock range and its place on separate lines."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .rules import Claim, DAY_HEADING, RANGE_SEP, Span, TIME, read_plan

_STATUS = re.compile(r"\s+변경됨\s*$")
_TRANSPORT = re.compile(r"^(?:도보|걸음|걷기|지하철|버스|택시|자동차|차량|자전거|대중교통|이동)(?=\s|\d|$)")
_DIRECTIVE = re.compile(r"말고|아니라|빼(?:고|줘|주세요|자|기)|제외|취소|삭제|대신\s|바꾸|바꿔|바꿀|변경해|변경할|옮겨")
_NON_STOP = re.compile(r"(?:[?？]|→|->|⇒|(?:오|내리|불|있|없)면|경우|주의보|경보|알림|확인해|추천해|알려|문의)")
_SENTENCE = re.compile(r"(?:요|니다|할게|할래|주세요|해줘|[.!])\s*$")


@dataclass
class Card:
    index: int
    title: Span
    start: Claim
    end: Claim
    status_label: bool


def cards(read: Any) -> list[Card]:
    """Only an otherwise empty, full clock-range line may own the next place line."""
    by_field = {claim.field: claim for claim in read.claims}
    out = []
    for index, item in enumerate(read.items):
        if item.title is not None or not item.start or not item.end:
            continue
        start = by_field.get(f"items[{index}].starts_at")
        end = by_field.get(f"items[{index}].ends_at")
        if start is None or end is None or start.span.line != end.span.line:
            continue
        number = start.span.line
        line = read.lines[number - 1]
        clocks = list(TIME.finditer(line))
        if len(clocks) != 2 or line[:clocks[0].start()].strip() or line[clocks[1].end():].strip():
            continue
        separator = line[clocks[0].end():clocks[1].start()]
        if not RANGE_SEP.fullmatch(separator):
            continue
        following = next((n for n in range(number + 1, len(read.lines) + 1) if read.lines[n - 1].strip()), None)
        if following is None:
            continue
        if following in read.read_lines:
            continue
        title_line = read.lines[following - 1]
        status = _STATUS.search(title_line)
        right = status.start() if status else len(title_line)
        left = len(title_line) - len(title_line.lstrip())
        text = title_line[left:right].rstrip()
        right = left + len(text)
        if not 2 <= len(text) <= 100 or not re.search(r"[가-힣A-Za-z]", text):
            continue
        if text in {"활동", "식사", "숙소", "항공", "이동", "일정", "변경됨"}:
            continue
        if TIME.search(text) or DAY_HEADING.match(text) or _TRANSPORT.match(text):
            continue
        if _DIRECTIVE.search(text) or _NON_STOP.search(text) or _SENTENCE.search(text):
            continue
        out.append(Card(index, Span(following, left, right, text), start, end, status is not None))
    return out


def restore(read: Any, found: list[Card]) -> None:
    """Attach original place spans to the existing timed rule items, without new values."""
    for card in found:
        read.items[card.index].title = card.title
        read.claims.append(Claim(f"items[{card.index}].title", card.title.text, card.title,
                                 note="앞 시각범위 줄에 이어지는 장소를 원문 그대로 읽었어요"))
        read.read_lines.add(card.title.line)


def may_restore(card: Card, requests: list[str], pieces: list[dict[str, Any]]) -> bool:
    if "correction" not in requests:
        return True
    # A copied status badge is not a request to replace or remove this stop.
    corrections = [p.get("quote") or "" for p in pieces if p.get("kind") == "correction"]
    return card.status_label and bool(corrections) and not any(_DIRECTIVE.search(quote) for quote in corrections)


def edited_title_evidence(evidence: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    """Keep the original row association when a customer changes its displayed title."""
    prior = previous.get("evidence") or {}
    number = prior.get("source_item_line", prior.get("line"))
    return {**evidence, "source_item_line": number} if isinstance(number, int) else evidence


def omissions(sources: list[dict[str, Any]], claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """An explicit card without a corresponding title claim cannot silently be ready."""
    out = []
    for source in sources:
        found = cards(read_plan(source.get("transcript") or ""))
        mine = [c for c in claims if c["source_id"] == source["source_id"]]
        represented = {(c.get("evidence") or {}).get("source_item_line", (c.get("evidence") or {}).get("line"))
                       for c in mine if c["field"].endswith(".title")}
        clock_lines = {(c.get("evidence") or {}).get("line") for c in mine
                       if c["field"].endswith((".starts_at", ".ends_at"))}
        reports = [c.get("value") or {} for c in mine if c["field"] == "reading.agent"]
        pieces = [p for value in reports for p in value.get("pieces") or [] if p.get("kind") == "correction"]
        for card in found:
            if card.title.line in represented or card.start.span.line in clock_lines:
                continue
            if any(card.title.text in (p.get("quote") or "") and _DIRECTIVE.search(p.get("quote") or "") for p in pieces):
                continue
            out.append({"source_id": source["source_id"], "line": card.title.line, "title": card.title.text,
                        "starts_at": card.start.value, "ends_at": card.end.value})
    return out

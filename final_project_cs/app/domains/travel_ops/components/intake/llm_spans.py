# -*- coding: utf-8 -*-
"""남은 줄 — 모델이 **어디가 무엇인지만** 가리키고, 값은 서버가 원문에서 잘라 낸다. `[2026-09-27]` 설계서 §3-4

★규칙이 못 읽은 줄(「점심은 토속촌에서 먹을래」 「저녁엔 광장시장 가 보고 싶어」)만 모델에 보낸다.
★모델이 내는 것: `{"spans": [{"line": 줄 번호, "quote": 원문 조각, "role": 역할}]}`.
  ☆설계서 §3-4 는 (시작, 끝) **글자 위치**를 받으라 했다. 언어 모델은 글자 수 세기가 약해서, 여기서는 **원문 조각을
    그대로 인용**하게 하고 서버가 그 조각을 원문에서 찾는다. ★원문에 **글자 그대로 없는** 인용은 버린다 — 실측
    (triPilot : RAG, 2026-09-26)에서 모델이 「토속촌」을 「토속툰」으로 바꿔 적었다. 그런 값은 원문에 없으니 들어오지 못한다.
★시각·날짜는 인용 조각을 **규칙으로 다시 읽어** 값을 만든다 — 모델이 정규화한 값을 쓰지 않는다.
★`[2026-10-16]` 남은 줄이 많으면 **줄 묶음으로 나눠** 부른다(`label_lines` · 가드레일 `travel.intake_reading`) — 묶음마다 넘김 장치를 따로 거친다.
★모델 호출: 설정의 기본 모델(`ollama_model` — 2026-10-14 부터 가르친 E4B `tripilot-pointer:e4b-ft`, 설계 당시에는 `gemma4:12b`) · think=false · 온도 0 · JSON(설계서 §3-4). 실패하면 이 단계만 건너뛰고 그 줄은 남은 줄로 둔다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import time
from typing import Any, Callable

from .rules import _EAT, _EAT_BEFORE, TIME, Claim, Span, _date_in, _hhmm, _narrow, eat_mention, meal_mention
from .span_segments import split_segments

ROLES = ("place", "time", "date", "meal", "eat", "booking_no", "party", "plan_request", "ignore")

SYSTEM = (
    "You label parts of a traveller's itinerary lines (usually Korean). You get numbered lines. "
    "For each useful part, return the line number, the EXACT substring copied character-for-character from that line "
    "(never fix typos, never translate, never add words), and its role.\n"
    "Roles: place (a place/shop/sight the traveller will visit), time (a clock time or time of day), "
    "date (a date or relative day such as 내일), time also includes relative-now expressions such as 지금/당장/현재, "
    "meal (breakfast/lunch/dinner word), "
    "eat (words saying the traveller will eat or drink AT that place, e.g. 먹고, 맛집, 한잔, 브런치, 카페, 커피 — not a meal word "
    "that only tells the time such as 저녁 무렵 or 점심쯤, and not eating before leaving for the place such as 아침 먹고 나와서), "
    "booking_no (reservation number), "
    "party (number of people), plan_request (they ask us to make a plan, e.g. '일정 짜 줘'), ignore.\n"
    'Return JSON only: {"spans": [{"line": 1, "quote": "...", "role": "place"}]}. '
    "If nothing is useful, return {\"spans\": []}.")



@dataclass
class SpanItem:
    """남은 줄의 장소 하나에서 모은 항목 — 규칙 항목과 같은 모양으로 합친다. ★한 줄에 장소가 여럿이면 항목도 여럿이다."""

    line: int
    title: Span | None
    start: str | None
    meal: str | None
    date: str | None
    time_claim: Claim | None = None
    segment: Span | None = None


def split_chunks(unread: list[int], size: int) -> list[list[int]]:
    """못 읽은 줄 번호를 **고른 크기**의 묶음으로 나눈다. `size` 가 0 이하이거나 줄이 그보다 적으면 한 묶음.
    ★끝 묶음만 작게 남기지 않는다 — 46줄을 8줄씩이면 8 · 8 · 8 · 8 · 7 · 7(묶음 수는 같고 크기만 고르게)."""
    numbers = list(unread)
    if size <= 0 or len(numbers) <= size:
        return [numbers] if numbers else []
    count = -(-len(numbers) // size)
    base, extra = divmod(len(numbers), count)
    out, at = [], 0
    for index in range(count):
        width = base + (1 if index < extra else 0)
        out.append(numbers[at:at + width])
        at += width
    return out


def _call_path() -> dict[str, Any] | None:
    """직전 모델 호출이 어느 경로(로컬 · 유료)로 답했나 — 넘김 장치가 꺼져 있으면 None."""
    try:
        from app.infrastructure import llm_failover

        return llm_failover.current_path()
    except Exception:                                    # noqa: BLE001 — 기록용이다. 못 읽어도 읽기를 막지 않는다
        return None


def _clear_path() -> None:
    try:
        from app.infrastructure import llm_failover

        llm_failover.clear_path()
    except Exception:                                    # noqa: BLE001
        pass


def label_lines(lines: list[str], unread: list[int], chat: Any, *, now: datetime | None = None,
                chunk_lines: int = 0, total_seconds: float = 0.0,
                on_chunk: Callable[[dict[str, Any]], None] | None = None,
                clock: Callable[[], float] = time.monotonic) -> tuple[list[Claim], list[SpanItem], dict[str, Any]]:
    """(claims, 항목, 보고). ★모델이 가리킨 조각 중 원문에 그대로 있는 것만 받는다.

    ★`[2026-10-14]` 한 줄을 장소마다 나눈다 — 줄마다 항목 하나로 묶었더니 「서촌 … 저녁 무렵 남산타워」에서 남산타워가 빠지고
      「저녁」이 서촌에 붙었다(테스트 서버 접수 87858b77). 시각 · 날짜 · 끼니는 같은 원문 구간의 장소에 붙인다.
    ★끼니는 모델이 가리키지 않아도 **그 장소 몫의 원문**에서 규칙으로 다시 본다(`rules.meal_mention`) — 같은 접수에서 모델이
      「점심은 통인시장 근처에서」의 「점심」을 가리키지 않아 식사가 활동이 됐다.

    ★`[2026-10-16]` **줄 묶음으로 나눠 부른다**(`chunk_lines` 줄씩, 0 이면 전처럼 한 번). 근거: 실측 보고서
      `wiki/records/reports/2026-10-16_계획읽기_묶음나누기.md`. 묶음마다 넘김 장치(`llm_failover`)를 그대로 거치므로 **실패한 묶음만** 유료로 간다.
      - 묶음 안에서는 줄 번호를 **1부터** 다시 매겨 보내고, 답의 번호를 원래 줄 번호로 되돌린다. 묶음 밖 번호는 버린다.
        ☆가르친 E4B 는 받은 번호(16 · 17 · 18 · 20)를 무시하고 목록 안 순서(1 · 2 · 3 · 4)로 답했다 — 원래 번호로 보냈더니
          4줄 묶음에서 가리킨 조각 54개 중 45개가 버려졌다(실측 보고서 「줄 번호」). 유료(gpt-6-luna)는 어느 쪽으로 보내도 맞게 답했다.
      - 한 묶음이 실패하면(로컬 · 유료 다 안 됨) 그 묶음의 줄만 남은 줄로 두고 다음 묶음으로 간다(`report.chunks[].error`).
      - `total_seconds`(0 이면 없음) — **묶음을 보내기 전마다** 이 단계에 쓴 시간을 보고, 넘었으면 남은 묶음은 보내지 않고 남은 줄로 둔다
        (`report.chunks[].skipped`). ☆넘김 장치의 전체 15초는 로컬 · 유료 첫 시도 쌍(9 + 8초)을 막지 않으므로 여기서 따로 센다.
        한 묶음은 시작하면 끝까지 기다리므로 실제 시간은 상한 + 묶음 하나의 최대 시간까지 갈 수 있다.
      - `on_chunk(진행)` — 처음 한 번(`done` 0)과 묶음 하나가 끝날 때마다 `{done, total, failed, skipped}` 를 알린다.
        `done` = 답을 받았거나 실패해 **끝난** 묶음 수, `total` = 보낼 묶음 전체, `skipped` = 상한 때문에 안 보낸 묶음(마지막 알림에서 정해진다).
        분모는 묶음 수이지 읽어 낸 비율이 아니다. 알림 쪽 오류는 읽기를 막지 않는다."""
    report: dict[str, Any] = {"asked_lines": len(unread), "spans": 0, "accepted": 0, "rejected": [], "plan_request": False}
    if not unread or chat is None:
        return [], [], report
    batches = split_chunks(unread, chunk_lines)
    report["chunk_lines"] = int(chunk_lines)
    report["chunks"] = []
    started = clock()
    tally = {"done": 0, "total": len(batches), "failed": 0, "skipped": 0}

    def tell() -> None:
        if on_chunk is None:
            return
        try:
            on_chunk(dict(tally))
        except Exception:                                # noqa: BLE001 — 진행 알림은 부가 기능이다
            pass

    tell()
    spans: list[tuple[list[int], Any]] = []
    for index, batch in enumerate(batches):
        spent = clock() - started
        if total_seconds > 0 and spent >= total_seconds:
            left = [n for rest in batches[index:] for n in rest]
            tally["skipped"] = len(batches) - index
            report["chunks"] += [{"lines": rest, "skipped": "total_seconds"} for rest in batches[index:]]
            report["left_lines"] = report.get("left_lines", []) + left
            report["deadline"] = {"total_seconds": total_seconds, "spent": round(spent, 2), "skipped_chunks": tally["skipped"]}
            break
        user = "\n".join(f"{at}: {lines[n - 1]}" for at, n in enumerate(batch, start=1))
        entry: dict[str, Any] = {"lines": batch}
        _clear_path()
        at = clock()
        try:
            raw = chat.json(SYSTEM, user)
        except Exception as exc:                         # noqa: BLE001 — 모델 장애는 그 묶음만 남은 줄로 둔다(기록하고 넘어간다)
            entry["error"] = f"{type(exc).__name__}: {exc}"[:200]
            report["left_lines"] = report.get("left_lines", []) + batch
            tally["failed"] += 1
            raw = None
        entry["seconds"] = round(clock() - at, 2)
        path = _call_path()
        if path:
            entry["path"] = path.get("path")
            if path.get("reasons"):
                entry["reasons"] = [list(r) for r in path["reasons"]]
        report["chunks"].append(entry)
        tally["done"] += 1
        if raw is not None:
            spans.append((batch, raw.get("spans") if isinstance(raw, dict) else None))
        tell()
    if tally["skipped"]:
        tell()
    errors = [c["error"] for c in report["chunks"] if c.get("error")]
    if errors:
        # 화면이 읽는 한 줄(`reading.error`) — 전처럼 첫 오류를 싣고, 몇 묶음이 실패했는지 붙인다
        report["error"] = errors[0] if len(batches) == 1 else f"{len(errors)}/{len(batches)} 묶음 실패 — {errors[0]}"[:240]
    accepted: dict[int, list[tuple[int, int, str, str]]] = {}
    cursors: dict[tuple[int, str, str], int] = {}
    for batch_lines, batch_spans in spans:
        _accept(lines, batch_lines, batch_spans, report, accepted, cursors)
    return _collect(lines, accepted, now, report)


def _accept(lines: list[str], batch: list[int], spans: Any, report: dict[str, Any],
            accepted: dict[int, list[tuple[int, int, str, str]]], cursors: dict[tuple[int, str, str], int]) -> None:
    """한 묶음의 답 → 받은 조각. 답의 줄 번호(묶음 안 순서, 1부터)를 원래 줄 번호로 되돌린다.
    ★그 순서의 줄에 인용이 글자 그대로 없고, 답의 번호가 **그 묶음의 원래 줄 번호**이며 그 줄에 인용이 있으면 원래 번호로 본다 —
      원래 번호로 답하는 모델(2026-10-16 전 계약 · 그 계약으로 쓴 시험)도 같은 결과가 나오게. 어느 쪽이든 인용이 그 줄에 있어야 받는다.
    ★원문에 글자 그대로 없는 인용 · 그 묶음 밖 번호 · 모르는 역할은 버린다."""
    for entry in spans or []:
        report["spans"] += 1
        try:
            asked, quote, role = int(entry["line"]), str(entry["quote"]), str(entry["role"])
        except (KeyError, TypeError, ValueError):
            report["rejected"].append({"why": "모양이 다르다", "entry": str(entry)[:80]})
            continue
        candidates = [batch[asked - 1]] if 1 <= asked <= len(batch) else []
        if asked in batch and asked not in candidates:
            candidates.append(asked)
        if not candidates or role not in ROLES or not quote.strip():
            report["rejected"].append({"why": "남은 줄이 아니거나 모르는 역할", "line": asked, "role": role})
            continue
        number, at = candidates[0], -1
        for number in candidates:
            at = lines[number - 1].find(quote, cursors.get((number, role, quote), 0))
            if at >= 0:
                break
        number = number if at >= 0 else candidates[0]
        key = number, role, quote
        if at < 0:
            # ★원문에 글자 그대로 없다 — 모델이 바꿔 적었다. 받지 않는다
            report["rejected"].append({"why": "원문에 없는 인용", "line": number, "quote": quote})
            continue
        cursors[key] = at + len(quote)
        if role == "plan_request":
            report["plan_request"] = True
        accepted.setdefault(number, []).append((at, at + len(quote), quote, role))
        report["accepted"] += 1


def _collect(lines: list[str], accepted: dict[int, list[tuple[int, int, str, str]]], now: datetime | None,
             report: dict[str, Any]) -> tuple[list[Claim], list[SpanItem], dict[str, Any]]:
    claims: list[Claim] = []
    items: list[SpanItem] = []
    for number in sorted(accepted):
        text = lines[number - 1]
        mine = _line_items(number, text, accepted[number])
        for start, end, quote, role in sorted(accepted[number]):
            if role in ("place", "plan_request", "ignore", "booking_no", "party") or not mine:
                continue
            item = _owner(mine, start)
            if role == "time" and item.time_claim is None:
                claim = _time_claim(number, start, quote, now, item)
                if claim is not None:
                    item.time_claim = claim
                    claims.append(claim)
            elif role == "date":
                value, match = _date_in(quote)
                if match:
                    item.date = value
            # 끼니는 _line_items가 항목의 전체 구간과 장소 위치로 판정한다.
            # 모델이 따로 낸 meal 조각으로 다른 항목의 판정을 덮지 않는다.
        items += mine
    return claims, items, report


def _line_items(number: int, text: str, spans: list[tuple[int, int, str, str]]) -> list[SpanItem]:
    """줄의 장소 조각마다 항목 하나 — 겹치지 않는 원문 구간을 보존한다."""
    places: list[tuple[int, int]] = []
    eaten: set[tuple[int, int]] = set()
    for start, end, _, role in sorted(spans):
        if role != "place":
            continue
        s, e = _narrow(text, start, end)
        # ★`[2026-10-15]` 모델이 「성수동 맛집」 · 「연남동 카페」처럼 「먹는다」 말까지 장소로 가리키면 그 앞까지가 이름이고 식사다(규칙 읽기와 같다)
        inner = _EAT.search(text, s + 1, e) if e > s else None
        if inner is not None and not _EAT_BEFORE.match(text, inner.end()):
            s, e = _narrow(text, s, inner.start())
            eaten.add((s, e))
        if e > s and not any(s < pe and ps < e for ps, pe in places):    # 겹치는 조각은 앞 것만
            places.append((s, e))
    # 모델이 끼니 말을 **시각**(숫자 없는 때)으로 짚었으면 그 판단을 따른다 — 「저녁엔 광장시장 가 보고 싶어」는 저녁에 가는 것이다.
    # 짚지 않았거나 끼니로 짚었으면 규칙이 정한다(「점심은 통인시장 근처에서」 — 모델이 아무것도 안 짚었다).
    as_time = [(start, end) for start, end, quote, role in spans if role == "time" and not TIME.search(quote)]
    eats = [(start, end) for start, end, _, role in spans if role == "eat"]
    items: list[SpanItem] = []
    for (s, e), (left, right) in zip(places, split_segments(text, places)):
        mention = meal_mention(text[left:right], place_start=s - left)
        meal = mention[1] if mention and mention[2] else None
        if meal and any(left <= start < right and mention[0] in text[start:end] for start, end in as_time):
            meal = None
        if meal is None and ((s, e) in eaten or eat_mention(text[left:right], place_end=e - left)):
            meal = "meal"                 # ★`[2026-10-15]` 끼니 말 없이 「먹고」 · 「맛집」 · 「한잔」 — 끼니는 모르고 식사인 것만 안다
        if meal is None and any(s <= start < right and not _EAT_BEFORE.match(text, end) for start, end in eats):
            # ★`[2026-10-15]` 모델이 그 장소 **이름 뒤** 구간의 「먹는다」 조각을 원문 그대로 가리켰다 — 규칙 낱말 목록 밖의 말(「요기」 · 「칼국수」 …).
            #   ☆이름 앞 조각은 받지 않는다 — 「밥 먹고 나서 창덕궁」의 「밥 먹고」를 모델이 eat 로 짚었다(실제 접수 모양 측정)
            meal = "meal"
        items.append(SpanItem(number, Span(number, s, e, text[s:e]), None, meal, None,
                              segment=Span(number, left, right, text[left:right])))
    return items


def _owner(items: list[SpanItem], at: int) -> SpanItem:
    """조각이 포함된 원문 구간의 장소. 장소 뒤의 「지금」도 그 장소에 붙는다."""
    return next((item for item in items if item.segment.start <= at < item.segment.end), items[-1])


def _time_claim(number: int, at: int, quote: str, now: datetime | None, item: SpanItem) -> Claim | None:
    match = TIME.search(quote)
    if match:
        value, review, note = _hhmm(match)
        if value:
            item.start = value
            return Claim("", value, Span(number, at + match.start(), at + match.end(), match.group(0)),
                         needs_review=review, note=note, method="llm_span")
    elif now is not None and any(word in quote for word in ("지금", "현재", "당장")):
        from zoneinfo import ZoneInfo
        instant = now.astimezone(ZoneInfo("Asia/Seoul"))
        value = instant.strftime("%H:%M")
        item.start = value
        item.date = instant.date().isoformat()
        return Claim("", value, Span(number, at, at + len(quote), quote), note="접수 시각 기준 현재 시각",
                     method="llm_span")
    return None


def make_labeler(chat: Any) -> Callable[[list[str], list[int]], tuple[list[Claim], list[SpanItem], dict[str, Any]]]:
    return lambda lines, unread: label_lines(lines, unread, chat)


__all__ = ["ROLES", "SYSTEM", "SpanItem", "label_lines", "make_labeler", "split_chunks"]

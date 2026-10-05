# -*- coding: utf-8 -*-
"""접수 읽기 실시간 진행의 **내용 이벤트** — 읽은 줄 · 찾은 일정 · 검사 줄 · 이동. `[2026-10-02 사용자 지시 — 계획 확인 시나리오 목업]`

단계 이벤트(`accepted` · `stage` · `beat` · `result` · `error`)는 `op_stream.watch` 가 낸다. 이 모듈은 그 사이에 흘릴 **내용**을 만든다:

    line   {source_id, no, text, read, found?}      원문 한 줄이 **읽혔다**(규칙이 읽었거나 모델이 가리킨 줄). found = 그 줄에서 찾은 일정
    item   {id, source_id, index, title, kind, day, date, starts_at, ends_at, place, place_state, status?, locked, …}
                                                    찾은 일정 한 건 — 값이 채워질 때마다(시각 → 장소) 같은 id 로 다시 온다. status 는 검사가 끝난 뒤
    check  {item, row, result, text}                일정의 검사 줄 한 줄(row = place · time · hours · closed)
    move   {from, to, status, mode, minutes, …, rows}   앞뒤 일정 사이 이동 한 구간
    done   {stage, revision, needs, ready}          검사가 끝났다 — 곧바로 `result` 가 온다

★**이벤트는 상태의 복사본이다**(순서가 있는 명령이 아니다). 같은 키(`line:원본:번호` · `item:id` · `check:id:row` · `move:from:to`)의 이벤트가 두 번 와도 나중 것으로 **덮으면** 된다.
  그래서 연결이 끊겼다 다시 붙으면 지금까지의 모든 상태가 처음부터 다시 오고(웹은 같은 키를 덮는다), 그 뒤 새 것만 온다. 서버는 누가 어디까지 받았는지 기억하지 않는다
  (변경 초인종과 같은 방식). 정본은 늘 `GET /v1/web/trip-intakes/{id}` 다 — 이벤트는 그 값이 만들어지는 과정을 보여 주는 것이다.
★**서버는 순서만 맞춘다**: 줄 → 일정 → (장소가 찾아질 때마다 일정을 다시) → 검사 줄 → 이동 → done. 웹이 받은 이벤트를 차례 줄에 쌓아 최소 표시 시간을 두고 하나씩 그린다
  (한꺼번에 와도 차례로 보인다) — 서버는 시간 간격을 맞추려고 일부러 늦추지 않는다(지어낸 진행이 아니다).
★읽은 값을 싣는다 — 사용자 키 · 원본 파일 · 내부 근거(evidence)는 싣지 않는다.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from .assemble import collect, effective
from . import progress as progress_module
from . import review as review_module


def _same(a: Any, b: Any) -> bool:
    return json.dumps(a, sort_keys=True, default=str, ensure_ascii=False) == json.dumps(b, sort_keys=True, default=str,
                                                                                         ensure_ascii=False)


class Feed:
    """한 연결의 내용 이벤트 만들기 — 연결마다 하나. `poll(conn, state)` 은 **새로 생기거나 달라진 것만** `(이벤트 이름, 몸통)` 으로 돌려준다."""

    def __init__(self, tenant_id: str, customer_id: UUID, intake_id: UUID) -> None:
        self.tenant_id, self.customer_id, self.intake_id = tenant_id, customer_id, intake_id
        self.sent: dict[str, Any] = {}
        self.done_sent = False
        #: 진행 보관소(`progress.py`)에서 어디까지 가져왔나 — 연결마다 따로(서버는 누가 어디까지 받았는지 모른다)
        self.cursor = 0
        #: 보관소가 검사 줄까지 정해 준 일정 — DB 의 검사가 저장되기 전에 DB 값(status 없음)이 이것을 **덮어 퇴보시키지 않게** 건너뛴다
        self.rich: set[str] = set()

    def _emit(self, out: list[tuple[str, dict[str, Any]]], key: str, name: str, body: dict[str, Any]) -> None:
        if key in self.sent and _same(self.sent[key], body):
            return
        self.sent[key] = body
        out.append((name, body))

    def poll(self, conn, state: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        from .pipeline import _claims, _sources

        out: list[tuple[str, dict[str, Any]]] = []
        # 검사가 계산되는 **동안** 쌓인 진행(장소 n/m · 일정 · 검사 줄 · 이동) — 검사는 끝나 커밋돼야 DB 에 보이므로 여기서 먼저 내보낸다(`progress.py`).
        # 같은 키로 끝에 DB 의 최종 값이 와서 덮는다
        fresh, self.cursor = progress_module.drain(str(self.intake_id), self.cursor)
        for name, body in fresh:
            if name == "item":
                self.rich.add(body["id"])
            self._emit(out, progress_module.key_of(name, body), name, body)
        sources = _sources(conn, self.tenant_id, self.intake_id)
        raw_claims = _claims(conn, self.tenant_id, self.intake_id, int(state["revision"]))
        claims = effective(raw_claims)
        positions = {str(s["source_id"]): int(s["position"]) for s in sources}
        reading = state["status"] == "reading"
        got = collect(sources=sources, claims=claims)
        for r in got.rows:
            r["source_id"] = str(r["source_id"])

        # 줄 — 읽힌 줄만(안 읽힌 줄은 확인 화면의 「남은 줄」이다). 그 줄에서 찾은 일정이 있으면 함께
        item_of_line: dict[tuple[str, int], str] = {}
        for r in got.rows:
            lines = [c["evidence"].get("line") for c in r["claims"].values() if c["evidence"].get("line")]
            if lines:
                item_of_line.setdefault((r["source_id"], min(lines)), f"{positions.get(r['source_id'], 0)}-{r['index']}")
        read_by_source: dict[str, set[int]] = {}
        for c in raw_claims:                       # 덮이기 전의 값에서 센다 — 같은 칸 이름의 날짜 줄이 여럿이면 앞 줄이 지워진다
            line = (c["evidence"] or {}).get("line")
            if line and c["source_id"] is not None:
                read_by_source.setdefault(str(c["source_id"]), set()).add(int(line))
        rows_by_id = {f"{positions.get(r['source_id'], 0)}-{r['index']}": r for r in got.rows}
        for source in sources:
            sid = str(source["source_id"])
            text_lines = (source["transcript"] or "").splitlines()
            for no in sorted(read_by_source.get(sid, ())):
                if not 0 < no <= len(text_lines):
                    continue
                item_id = item_of_line.get((sid, no))
                found = None
                if item_id:
                    row = rows_by_id[item_id]
                    found = {"id": item_id, "index": row["index"], "day": row["day"], "date": row["date"],
                             "starts_at": row["start"], "title": row["title"]}
                self._emit(out, f"line:{sid}:{no}", "line",
                           {"source_id": sid, "no": no, "text": text_lines[no - 1], "read": True, "found": found})

        # 일정 — 값이 채워질 때마다 같은 id 로 다시. 검사가 있으면 status 까지
        finished = state["status"] in ("review", "confirmed")
        review = None
        if finished:
            from .pipeline import _review_of

            review, _ = _review_of(conn, self.tenant_id, self.intake_id, int(state["revision"]), sources,
                                   claims)
            review = review_module.public(review)
        by_item = {it["id"]: it for it in (review or {}).get("items", [])}
        for item_id, row in rows_by_id.items():
            if item_id in self.rich and item_id not in by_item:
                continue                                                  # 보관소가 이미 검사 줄까지 낸 일정 — DB 의 덜 채운 값으로 되돌리지 않는다
            if item_id in by_item:
                it = by_item[item_id]
                body = {k: it[k] for k in ("id", "source_id", "index", "title", "kind", "day", "date", "starts_at", "ends_at",
                                            "locked", "status", "can_lock", "place_state", "place", "candidates_hint", "booked",
                                            "parts")}
            else:
                claim = (row["claims"] or {}).get("place")
                state_name, value = review_module.place_state(row)
                if claim is None and reading:
                    state_name = "searching"
                body = {"id": item_id, "source_id": row["source_id"], "index": row["index"], "title": row["title"],
                        "kind": row["kind"], "day": row["day"], "date": row["date"], "starts_at": row["start"],
                        "ends_at": row["end"], "locked": bool(row["locked"]), "status": None, "can_lock": False,
                        "place_state": state_name,
                        "place": ({"name": value["name"], "latitude": value.get("latitude"),
                                   "longitude": value.get("longitude"), "source": value.get("source"),
                                   "kind": value.get("kind")} if value else None),
                        "candidates_hint": None, "booked": review_module.booked_of(row, state_name),
                        "parts": review_module.nameless_parts(row, state_name)}
            self._emit(out, f"item:{item_id}", "item", body)

        # 검사 줄 · 이동 · 끝 — 검사가 만들어진 뒤에만
        if review is not None:
            for it in review["items"]:
                for line in it["rows"]:
                    self._emit(out, f"check:{it['id']}:{line['row']}", "check", {"item": it["id"], **line})
            for move in review["moves"]:
                body = {k: v for k, v in move.items() if k != "sig"}
                self._emit(out, f"move:{move['from']}:{move['to']}", "move", body)
            # 검사할 것이 없는 접수(빈 접수)는 `done` 없이 곧바로 `result` 로 끝난다(전에 문서화된 모양 그대로)
            if not self.done_sent and (review["items"] or review["moves"]):
                self.done_sent = True
                out.append(("done", {"stage": state["stage"], "revision": review["revision"], "needs": review["needs"],
                                     "ready": review["ready"]}))
        return out


def sse_chunks(events: list[tuple[str, dict[str, Any]]]) -> list[str]:
    """진행 이벤트를 화면이 읽는 모양으로 바꾼다.

    ★`[2026-10-06]` 전에는 실시간 진행 기능(`modules/live_progress`)을 직접 불렀다 — 그 기능을
      끄면 접수 읽기가 같이 멈추는 길이었다(D-CS-013). 지금은 **포장하는 쪽이 조립 때 꽂는다.**
      아무도 안 꽂으면 그냥 빈 목록이다 — 실시간 화면이 없을 뿐, 접수 읽기는 그대로 돈다.
    """
    from app.domains.travel_ops.components.progress_hook import render

    return render(events)


__all__ = ["Feed", "sse_chunks"]

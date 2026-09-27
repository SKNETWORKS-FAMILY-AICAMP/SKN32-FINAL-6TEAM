# -*- coding: utf-8 -*-
"""계획 읽기 한 건 — 접수 · 글자로 · 규칙 읽기 · 읽은 값 저장. `[2026-09-27]` 설계서 §3·§6

    open_intake   접수 행 + 원본 행(글자 판별·sha256). ★여기서는 읽지 않는다 — 요청이 45초를 기다리지 않게
    process       뒤에서: 원본마다 글자로(받아쓰기 포함) → 규칙 읽기 → `intake_claims` (revision 1) → review
    view          화면이 읽는 모양: 진행 단계 · 원본별 줄 번호 글 · 읽은 항목 · 확인 필요 · 남은 줄

★실패를 숨기지 않는다 — 형식을 못 읽으면 `fatal`(코드·사유), 받아쓰기 모델이 죽으면 `fatal` + 다시 시도 가능.
  「읽은 항목 0개」는 실패가 아니다 — 확인 화면이 남은 줄을 보여 주고 고객이 고친다(2주차부터 LLM 이 남은 줄을 돕는다).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable
from uuid import UUID

from .rules import read_plan
from .sources import UnsupportedSource, sniff, to_text

#: 받는 크기 · 개수 — 우리가 고른 값(설계서 §9 「악성 파일·압축 폭탄」). 넘으면 접수하지 않는다
MAX_FILES = 5
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 20_000

STAGES = {"received": "받았어요", "transcribing": "글자로 옮기는 중", "reading": "규칙으로 읽는 중",
          "review": "확인해 주세요", "fatal": "읽지 못했어요"}


class IntakeRejected(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


def open_intake(conn, *, tenant_id: str, customer_id: UUID, text: str | None,
                files: list[tuple[str, bytes]]) -> UUID:
    """접수 한 건. `files` = [(파일 이름, 바이트)]. ★종류는 첫 바이트로 — 모르는 형식은 여기서 거절한다."""
    text = (text or "").strip()
    if not text and not files:
        raise IntakeRejected("empty_intake", "글이나 파일을 하나 이상 보내 주세요")
    if len(text) > MAX_TEXT_CHARS:
        raise IntakeRejected("text_too_long", f"글은 {MAX_TEXT_CHARS:,}자까지 받아요")
    if len(files) > MAX_FILES:
        raise IntakeRejected("too_many_files", f"파일은 {MAX_FILES}개까지 받아요")
    kinds = []
    for name, data in files:
        if len(data) > MAX_FILE_BYTES:
            raise IntakeRejected("file_too_large", f"{name}: 파일 하나는 {MAX_FILE_BYTES // 1024 // 1024}MB 까지 받아요")
        try:
            kinds.append(sniff(data, filename=name))
        except UnsupportedSource as exc:
            raise IntakeRejected("unsupported_format", f"{name}: {exc}") from None
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO trip_intakes (tenant_id, customer_id, stage) VALUES (%s,%s,'received') "
                    "RETURNING intake_id", (tenant_id, customer_id))
        intake_id = cur.fetchone()[0]
        position = 0
        if text:
            raw = text.encode("utf-8")
            cur.execute("INSERT INTO intake_sources (intake_id, tenant_id, position, kind, sha256, size_bytes, "
                        "transcript) VALUES (%s,%s,%s,'chat',%s,%s,%s)",
                        (intake_id, tenant_id, position, hashlib.sha256(raw).hexdigest(), len(raw), text))
            position += 1
        for (name, data), kind in zip(files, kinds):
            # ★원본은 DB 에 두지 않는다 — 뒤에서 읽을 동안만 메모리/임시 저장소(`blobs`)에 둔다
            cur.execute("INSERT INTO intake_sources (intake_id, tenant_id, position, kind, filename, sha256, "
                        "size_bytes) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (intake_id, tenant_id, position, kind, name[:200], hashlib.sha256(data).hexdigest(),
                         len(data)))
            position += 1
    return intake_id


def process(connect: Callable[[], Any], *, tenant_id: str, intake_id: UUID, blobs: dict[int, bytes],
            see: Callable[[str, bytes], str] | None) -> str:
    """뒤에서 한 건을 읽는다. 돌려주는 값은 마지막 상태(review · fatal). `blobs` = {position: 바이트}."""
    try:
        with connect() as conn:
            sources = _sources(conn, tenant_id, intake_id)
        for source in sources:
            if source["transcript"] is None:
                _stage(connect, tenant_id, intake_id, "transcribing")
                data = blobs.get(source["position"])
                if data is None:
                    raise IntakeRejected("source_missing", f"{source['filename']}: 원본을 찾지 못했다")
                result = to_text(data, filename=source["filename"] or "", see=see)
                with connect() as conn, conn.transaction(), conn.cursor() as cur:
                    cur.execute("UPDATE intake_sources SET transcript=%s, transcribed=%s, missing_json=%s, "
                                "seconds=%s WHERE source_id=%s AND tenant_id=%s",
                                (result.text, bool(result.transcribed_pages) or result.kind == "image",
                                 json.dumps(result.missing, ensure_ascii=False), result.seconds,
                                 source["source_id"], tenant_id))
                source["transcript"] = result.text
        _stage(connect, tenant_id, intake_id, "reading")
        with connect() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM intake_claims WHERE tenant_id=%s AND intake_id=%s AND revision=1 "
                        "AND method='rule'", (tenant_id, intake_id))
            for source in sources:
                read = read_plan(source["transcript"] or "")
                for claim in read.claims:
                    row = claim.as_dict()
                    cur.execute("INSERT INTO intake_claims (intake_id, tenant_id, revision, source_id, field, "
                                "value_json, method, evidence, needs_review, note) "
                                "VALUES (%s,%s,1,%s,%s,%s,%s,%s,%s,%s)",
                                (intake_id, tenant_id, source["source_id"], row["field"],
                                 json.dumps(row["value"], ensure_ascii=False), row["method"],
                                 json.dumps({**row["evidence"], "source_id": str(source["source_id"])},
                                            ensure_ascii=False), row["needs_review"], row["note"]))
            cur.execute("UPDATE trip_intakes SET status='review', stage='review', updated_at=now() "
                        "WHERE tenant_id=%s AND intake_id=%s", (tenant_id, intake_id))
        return "review"
    except (IntakeRejected, UnsupportedSource) as exc:
        code = getattr(exc, "code", "unsupported_format")
        _fatal(connect, tenant_id, intake_id, code, str(exc))
        return "fatal"
    except Exception as exc:                         # ★받아쓰기 모델 장애 등 — 숨기지 않고 남긴다
        _fatal(connect, tenant_id, intake_id, "reading_failed", f"{type(exc).__name__}: {exc}"[:300])
        return "fatal"


def view(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID) -> dict[str, Any] | None:
    """확인 화면이 읽는 모양. ★남의 접수는 없는 것과 같다(None)."""
    with conn.cursor() as cur:
        cur.execute("SELECT status, stage, revision, fatal_code, fatal_detail, trip_id, received_at "
                    "FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s AND customer_id=%s",
                    (tenant_id, intake_id, customer_id))
        row = cur.fetchone()
        if row is None:
            return None
        status, stage, revision, fatal_code, fatal_detail, trip_id, received_at = row
        sources = _sources(conn, tenant_id, intake_id)
        cur.execute("SELECT source_id, field, value_json, method, evidence, needs_review, note FROM intake_claims "
                    "WHERE tenant_id=%s AND intake_id=%s AND revision=%s ORDER BY created_at, claim_id",
                    (tenant_id, intake_id, revision))
        claims = [dict(zip(("source_id", "field", "value", "method", "evidence", "needs_review", "note"), r))
                  for r in cur.fetchall()]
    out_sources = []
    for source in sources:
        mine = [c for c in claims if c["source_id"] == source["source_id"]]
        lines = (source["transcript"] or "").splitlines()
        read_lines = {c["evidence"].get("line") for c in mine}
        out_sources.append({
            "source_id": str(source["source_id"]), "kind": source["kind"], "filename": source["filename"],
            "transcribed": source["transcribed"], "missing": source["missing_json"], "seconds": source["seconds"],
            "lines": [{"no": n, "text": text, "read": n in read_lines} for n, text in enumerate(lines, start=1)],
            "items": _items(mine), "trip": _trip_fields(mine)})
    return {"intake_id": str(intake_id), "status": status, "stage": stage, "stage_label": STAGES.get(stage, stage),
            "revision": revision, "fatal": {"code": fatal_code, "detail": fatal_detail} if fatal_code else None,
            "trip_id": str(trip_id) if trip_id else None, "received_at": received_at.isoformat(),
            "sources": out_sources,
            "needs_review": [{"field": c["field"], "value": c["value"], "note": c["note"],
                              "evidence": c["evidence"]} for c in claims if c["needs_review"]]}


# ── 부품 ─────────────────────────────────────────────────────────
def _items(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`items[n].필드` 줄들을 항목으로 묶는다. 각 값은 근거를 같이 들고 간다."""
    items: dict[int, dict[str, Any]] = {}
    for claim in claims:
        field = claim["field"]
        if not field.startswith("items["):
            continue
        index = int(field[6:field.index("]")])
        name = field[field.index("]") + 2:]
        entry = items.setdefault(index, {"index": index, "fields": {}})
        entry["fields"][name] = {"value": claim["value"], "method": claim["method"],
                                 "evidence": claim["evidence"], "needs_review": claim["needs_review"],
                                 "note": claim["note"]}
    days = _day_dates(claims)
    for entry in items.values():
        line = min((f["evidence"].get("line", 0) for f in entry["fields"].values()), default=0)
        entry["line"] = line
        entry["day"], entry["date"] = _day_for(line, days)
    return [items[k] for k in sorted(items)]


def _day_dates(claims: list[dict[str, Any]]) -> list[tuple[int, int | None, str | None]]:
    """(줄, 몇째 날, 날짜) — 일차 머리줄·날짜 줄의 위치."""
    marks: dict[int, list] = {}
    for claim in claims:
        field, line = claim["field"], claim["evidence"].get("line", 0)
        if field.startswith("days[") and field.endswith(".heading"):
            marks.setdefault(line, [None, None])[0] = claim["value"]
        elif field.startswith("days[") and field.endswith(".date"):
            marks.setdefault(line, [None, None])[1] = claim["value"]
    return [(line, day, date) for line, (day, date) in sorted(marks.items())]


def _day_for(line: int, marks: list[tuple[int, int | None, str | None]]) -> tuple[int | None, str | None]:
    day = date = None
    for mark_line, mark_day, mark_date in marks:
        if mark_line > line:
            break
        if mark_day is not None:
            day, date = mark_day, mark_date
        elif mark_date is not None:
            date = mark_date
    return day, date


def _trip_fields(claims: list[dict[str, Any]]) -> dict[str, Any]:
    return {c["field"][5:]: {"value": c["value"], "evidence": c["evidence"]}
            for c in claims if c["field"].startswith("trip.")}


def _sources(conn, tenant_id: str, intake_id: UUID) -> list[dict[str, Any]]:
    columns = ("source_id", "position", "kind", "filename", "transcript", "transcribed", "missing_json", "seconds")
    with conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(columns)} FROM intake_sources WHERE tenant_id=%s AND intake_id=%s "
                    "ORDER BY position", (tenant_id, intake_id))
        return [dict(zip(columns, r)) for r in cur.fetchall()]


def _stage(connect, tenant_id: str, intake_id: UUID, stage: str) -> None:
    with connect() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET stage=%s, updated_at=now() WHERE tenant_id=%s AND intake_id=%s",
                    (stage, tenant_id, intake_id))


def _fatal(connect, tenant_id: str, intake_id: UUID, code: str, detail: str) -> None:
    with connect() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET status='fatal', stage='fatal', fatal_code=%s, fatal_detail=%s, "
                    "updated_at=now() WHERE tenant_id=%s AND intake_id=%s", (code, detail, tenant_id, intake_id))


__all__ = ["IntakeRejected", "MAX_FILES", "MAX_FILE_BYTES", "MAX_TEXT_CHARS", "STAGES", "open_intake", "process",
           "view"]

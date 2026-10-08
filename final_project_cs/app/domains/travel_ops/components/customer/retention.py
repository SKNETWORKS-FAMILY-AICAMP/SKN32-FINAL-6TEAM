# -*- coding: utf-8 -*-
"""약관의 보관 기간 — 값 · 약관 문장 · 운영자가 바꾼 기록 · 약관 버전. `[2026-10-07 사용자 결정 — uiux 전달]` 마이그레이션 056

계약 `wiki/external/rest-endpoints.md` 「약관 보관 기간」 · HTTP `modules/web_account/retention_api.py` · 정리 작업 `modules/web_account/member_cleanup.py`.

★약관 화면의 다섯 칸(`CELLS`) — 회원 자료 · 처리 기록 · 동의 기록 · 위치 점 · 위치 확인자료. 숫자 넷은 운영자가 관리 화면에서 고칠 수 있고(범위는 `retention.bounds`),
  처리 기록은 「여행 · 게스트 자료가 지워질 때 함께 파기」로 **고정 문장**이다(`retention.case_follows_trip` 스위치는 코드 설정이지 약관 칸이 아니다).
★기본값은 `config/guardrails.yaml` 이 정본이다(동의 기록 일수는 `consent.evidence_retention_days`). 운영자가 바꾼 값만 `legal_retention.overrides` 에 둔다 —
  **기본값과 같아지는 값은 저장하지 않는다**(「바꿨다」가 아니다).
★값이 **실제로 바뀌면** 약관 글이 바뀌므로 `revision` 이 +1 되고 약관 버전이 `기본 버전+ret{revision}` 이 된다(`version_for`) — 같은 버전 이름으로 다른 글에 동의했다는 기록이 생기지 않게.
  바뀐 칸이 없으면 revision 도 이력도 늘지 않는다. 이력(`legal_retention_history`)은 덧붙이기만 하고 누가(`actor` · `key_id`) · 언제 · 왜를 남긴다.
★약관 문장(한 · 영)은 **값에서 만든다** — 값과 문장이 따로 놀지 않게. 웹은 이 문장을 읽어 약관에 끼운다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg.types.json import Json

from app.core.settings import get_guardrails


class RetentionError(Exception):
    def __init__(self, status: int, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra


@dataclass(frozen=True)
class Cell:
    key: str
    label_ko: str
    label_en: str
    unit: str | None          # "days" · "months" · None(고정 문장)
    editable: bool


CELLS: tuple[Cell, ...] = (
    Cell("member_idle_days", "회원 여행 · 대화 기록", "Member trips and chat history", "days", True),
    Cell("case_follows_trip", "처리 기록", "Processing records", None, False),
    Cell("consent_days", "동의 기록", "Consent records", "days", True),
    Cell("location_points_days", "위치 점", "Location points", "days", True),
    Cell("location_proof_months", "위치 확인자료", "Location verification data", "months", True),
)
EDITABLE = tuple(cell.key for cell in CELLS if cell.editable)


# ── 기본값 · 범위 ───────────────────────────────────────────────
def defaults() -> dict[str, int]:
    guard = get_guardrails()
    return {"member_idle_days": int(guard.get("retention.member_idle_days")),
            "consent_days": int(guard.get("consent.evidence_retention_days")),
            "location_points_days": int(guard.get("retention.location_points_days_after_trip")),
            "location_proof_months": int(guard.get("retention.location_proof_months"))}


def bounds(key: str) -> tuple[int, int]:
    guard_key = {"location_points_days": "location_points_days_after_trip"}.get(key, key)
    spec = get_guardrails().get(f"retention.bounds.{guard_key}")
    return int(spec["min"]), int(spec["max"])


def check(key: str, value: Any) -> str | None:
    """값이 받을 수 있는 것이면 None, 아니면 이유(`unknown_cell` · `wrong_type` · `out_of_range`)."""
    if key not in EDITABLE:
        return "unknown_cell"
    if isinstance(value, bool) or not isinstance(value, int):
        return "wrong_type"
    low, high = bounds(key)
    return None if low <= value <= high else "out_of_range"


# ── 저장된 값 ───────────────────────────────────────────────────
def read(conn, tenant_id: str, *, lock: bool = False) -> tuple[int, dict[str, int]]:
    """(revision, 운영자가 바꾼 값) — 행이 없으면 (0, {}). 범위를 벗어난 저장값은 읽을 때 버린다(가드레일 범위가 나중에 좁아져도 그 값으로 돌지 않는다)."""
    with conn.cursor() as cur:
        cur.execute("SELECT revision, overrides FROM legal_retention WHERE tenant_id=%s" + (" FOR UPDATE" if lock else ""), (tenant_id,))
        row = cur.fetchone()
    if row is None:
        return 0, {}
    return int(row[0]), {k: v for k, v in (row[1] or {}).items() if check(k, v) is None}


def effective(conn, tenant_id: str) -> dict[str, int]:
    """지금 적용되는 값 — 운영자가 바꾼 것이 있으면 그것, 없으면 기본값."""
    revision, stored = read(conn, tenant_id)
    del revision
    return {**defaults(), **stored}


def revision(conn, tenant_id: str) -> int:
    return read(conn, tenant_id)[0]


def version_for(base: str, rev: int) -> str:
    """약관 버전 — 보관 기간을 한 번도 안 바꿨으면 기본 버전 그대로, 바꿨으면 `+ret{revision}`."""
    return f"{base}+ret{rev}" if rev > 0 else base


# ── 약관 문장 ───────────────────────────────────────────────────
def span_ko(value: int, unit: str) -> str:
    if unit == "months":
        return f"{value // 12}년" if value % 12 == 0 else f"{value}개월"
    if value % 365 == 0:
        return f"{value // 365}년"
    return f"{value // 30}개월" if value % 30 == 0 else f"{value}일"


def span_en(value: int, unit: str) -> str:
    def plural(n: int, word: str) -> str:
        return f"{n} {word}" + ("" if n == 1 else "s")

    if unit == "months":
        return plural(value // 12, "year") if value % 12 == 0 else plural(value, "month")
    if value % 365 == 0:
        return plural(value // 365, "year")
    return plural(value // 30, "month") if value % 30 == 0 else plural(value, "day")


_TEXT = {
    "member_idle_days": ("회원이 지우거나 탈퇴를 요청할 때까지, 마지막 이용 후 {s}이 지나면 파기",
                         "Kept until you delete it or ask to withdraw, and destroyed once {s} have passed since your last use"),
    "case_follows_trip": ("여행 · 게스트 자료가 지워질 때 함께 파기", "Destroyed together when the trip or guest data is deleted"),
    "consent_days": ("기록한 때부터 {s}", "{s} from the time it was recorded"),
    "location_points_days": ("여행 종료 후 {s}", "{s} after the trip ends"),
    "location_proof_months": ("기록한 때부터 {s}", "{s} from the time it was recorded"),
}


def _cells(values: dict[str, int], defaulted: dict[str, int]) -> list[dict[str, Any]]:
    out = []
    for cell in CELLS:
        ko, en = _TEXT[cell.key]
        value = values.get(cell.key)
        if cell.unit and value is not None:
            ko, en = ko.format(s=span_ko(value, cell.unit)), en.format(s=span_en(value, cell.unit))
        out.append({"key": cell.key, "label_ko": cell.label_ko, "label_en": cell.label_en, "value": value, "unit": cell.unit,
                    "default": defaulted.get(cell.key), "editable": cell.editable, "text_ko": ko, "text_en": en,
                    **({"min": bounds(cell.key)[0], "max": bounds(cell.key)[1]} if cell.editable else {})})
    return out


def public_view(conn, tenant_id: str) -> dict[str, Any]:
    """`GET /v1/web/legal/retention` 의 모양 — 칸마다 값 · 한 · 영 문장, 지금 약관 버전과 revision. 개인 정보 없음."""
    rev, stored = read(conn, tenant_id)
    base = defaults()
    values = {**base, **stored}
    return {"revision": rev, "terms_version": version_for(str(get_guardrails().get("consent.terms_version")), rev),
            "cells": _cells(values, base)}


# ── 바꾸기 ──────────────────────────────────────────────────────
def update(conn, tenant_id: str, *, expected_revision: int, changes: dict[str, Any], actor: str, key_id: str, reason: str) -> dict[str, Any]:
    """운영자가 칸 값을 바꾼다 — `changes = {칸: 숫자 | None}`(None 은 기본값으로 되돌림). 바뀐 칸이 하나도 없으면 아무것도 쓰지 않는다.

    오류: 운영자 · 이유가 비면 422 · 모르는 칸 · 숫자가 아니거나 범위 밖이면 422(어느 칸인지 싣는다) · `expected_revision` 이 지금과 다르면 409 `stale_revision`."""
    if not actor.strip():
        raise RetentionError(422, "actor_required", "누가 바꾸는지(actor)를 적어 주세요")
    if not reason.strip():
        raise RetentionError(422, "reason_required", "왜 바꾸는지(reason)를 적어 주세요")
    for key, value in changes.items():
        if value is not None and (problem := check(key, value)) is not None:
            raise RetentionError(422, problem, "이 칸의 값을 받을 수 없어요", cell=key)
        if value is None and key not in EDITABLE:
            raise RetentionError(422, "unknown_cell", "바꿀 수 없는 칸이에요", cell=key)
    base = defaults()
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("INSERT INTO legal_retention (tenant_id) VALUES (%s) ON CONFLICT DO NOTHING", (tenant_id,))
        rev, stored = read(conn, tenant_id, lock=True)
        if rev != expected_revision:
            raise RetentionError(409, "stale_revision", "다른 운영자가 먼저 바꿨어요 — 다시 불러와 주세요", revision=rev)
        new_overrides = dict(stored)
        for key, value in changes.items():
            if value is None or value == base[key]:
                new_overrides.pop(key, None)              # 기본값과 같으면 「바꾼 값」으로 두지 않는다
            else:
                new_overrides[key] = value
        before, after = {**base, **stored}, {**base, **new_overrides}
        diff = {key: [before[key], after[key]] for key in EDITABLE if before[key] != after[key]}
        if not diff:
            return {"revision": rev, "changed": {}}
        with conn.cursor() as cur:
            cur.execute("UPDATE legal_retention SET revision=%s, overrides=%s, updated_at=now(), updated_by=%s WHERE tenant_id=%s",
                        (rev + 1, Json(new_overrides), actor.strip(), tenant_id))
            cur.execute("INSERT INTO legal_retention_history (tenant_id, revision, old_values, new_values, changed, actor, key_id, reason) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (tenant_id, rev + 1, Json(before), Json(after), Json(diff), actor.strip(), key_id, reason.strip()))
    return {"revision": rev + 1, "changed": diff}


def history(conn, tenant_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT revision, changed, actor, key_id, reason, at FROM legal_retention_history WHERE tenant_id=%s ORDER BY seq DESC LIMIT %s",
                    (tenant_id, limit))
        return [{"revision": r[0], "changed": r[1], "actor": r[2], "key_id": r[3], "reason": r[4], "at": r[5].isoformat()} for r in cur.fetchall()]


__all__ = ["CELLS", "EDITABLE", "RetentionError", "bounds", "check", "defaults", "effective", "history", "public_view", "read", "revision",
           "span_en", "span_ko", "update", "version_for"]

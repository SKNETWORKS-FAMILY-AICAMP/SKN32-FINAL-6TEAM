"""진행 상태. 파일 하나에 담고, 웹 지도는 이 파일만 읽는다.

점수와 배지는 두지 않는다. 남기는 것은 무엇을 해봤고 무엇을 설명할 수 있는지다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import progress_path

SCHEMA_VERSION = "acop-progress/1.0"

EMPTY: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "stages": {},
    "abilities": {},
    "defects": {},
    "visits": [],
    "discovered": [],
}


def load() -> dict[str, Any]:
    path = progress_path()
    if not path.exists():
        return json.loads(json.dumps(EMPTY))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(EMPTY))
    for key, value in EMPTY.items():
        data.setdefault(key, json.loads(json.dumps(value)))
    return data


def save(data: dict[str, Any]) -> Path:
    path = progress_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8", newline="\n",
    )
    return path


def record_stage(stage: str, *, status: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    data = load()
    entry = data["stages"].setdefault(stage, {"attempts": 0})
    entry["attempts"] += 1
    entry["status"] = status
    if detail:
        entry.update(detail)
    save(data)
    return data


def discover(symbols: list[str]) -> dict[str, Any]:
    """트레이스에서 실제로 지나간 것만 발견 처리한다. 읽었다고 발견이 아니다."""
    data = load()
    known = set(data["discovered"])
    known.update(symbols)
    data["discovered"] = sorted(known)
    save(data)
    return data


def claim_ability(name: str, *, evidence: str, confirmed: bool) -> dict[str, Any]:
    """능력은 실행 증거가 있을 때만 준다. confirmed=False 는 잠정이다."""
    data = load()
    data["abilities"][name] = {
        "evidence": evidence,
        "state": "confirmed" if confirmed else "provisional",
    }
    save(data)
    return data

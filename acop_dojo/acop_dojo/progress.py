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
    _park_commerce(data)
    return data


#: 도메인 전환으로 등록에서 빠진 커머스 Team 코드
_COMMERCE_CODE = "app/modules/customer_ops/"


def _park_commerce(data: dict[str, Any]) -> None:
    """2026-09-14 커머스 중지. 중지한 결함·지워진 코드로 얻은 기록을 `archived` 로 옮긴다.

    지우지 않는다 — 한 일은 한 일이다. 다만 그대로 두면 옛 커머스 보스를 깬 기록이
    베이스먼트 보스전 통과처럼, 지워진 Team 함수가 '본 적 있음' 으로 지도에 남는다
    (codex-alt 지적). 몇 번 불러도 결과가 같다.
    """
    from .defects import PARKED

    parked = {d.defect_id for d in PARKED}
    archived = data.setdefault("archived", {})
    stage4 = data["stages"].get("4")
    if stage4 and stage4.get("defect") in parked:
        archived.setdefault("stages", {})["4"] = data["stages"].pop("4")
    for name, ability in list(data["abilities"].items()):
        if any(defect_id in str(ability.get("evidence", "")) for defect_id in parked):
            archived.setdefault("abilities", {})[name] = data["abilities"].pop(name)
    gone = [s for s in data["discovered"] if _COMMERCE_CODE in s]
    if gone:
        archived["discovered"] = sorted(set(archived.get("discovered", [])) | set(gone))
        data["discovered"] = [s for s in data["discovered"] if _COMMERCE_CODE not in s]
    for concept, entry in list(data.get("reviews", {}).items()):
        if entry.get("source") in parked:
            archived.setdefault("reviews", {})[concept] = data["reviews"].pop(concept)


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

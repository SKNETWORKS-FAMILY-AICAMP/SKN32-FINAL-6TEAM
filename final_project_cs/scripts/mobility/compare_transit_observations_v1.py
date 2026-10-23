"""대중교통의 같은 이동 사건을 정렬한 뒤 초 단위 오차를 계산한다.

실제 탑승, 공표 시간표, 승강장 표시, 개발 재생은 서로 다른 분모다.
허용오차를 입력하지 않거나 식별자·시간이 맞지 않으면 평가하지 않는다.
이 도구는 파일만 읽으며 개발자 API나 운영 서비스를 호출하지 않는다.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import json
import math
from pathlib import Path
import shutil
from uuid import uuid4

SCOPES = frozenset({"actual_transport_event", "official_timetable", "platform_display", "development_replay"})
EVENTS = frozenset({"board", "alight", "transfer"})
IDENTITIES = ("journey_id", "leg_index", "line_id", "direction", "station_id", "service", "event_kind")


def _clock(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value)
        return result if result.utcoffset() is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def _identity_valid(key, value):
    if key == "leg_index":
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0
    return isinstance(value, str) and bool(value.strip()) and value.strip().casefold() not in {"unknown", "미확인", "모름"}


def compare_row(row):
    """명시적 허용오차·동일 식별자·사전 예측을 갖춘 한 사건만 비교한다."""
    row = row if isinstance(row, dict) else {}
    prediction, reference = row.get("prediction"), row.get("reference")
    scope = reference.get("kind") if isinstance(reference, dict) else None
    if not isinstance(scope, str):
        scope = None
    result = {"id": row.get("id") if isinstance(row.get("id"), str) else None,
              "status": "unaligned", "scope": scope if scope in SCOPES else "unknown",
              "reason": None, "absolute_error_seconds": None, "within_tolerance": None}

    def reject(reason):
        return {**result, "reason": reason}

    if not result["id"] or not isinstance(prediction, dict) or not isinstance(reference, dict):
        return reject("record_shape_invalid")
    if scope not in SCOPES:
        return reject("reference_kind_missing_or_unknown")
    if not isinstance(reference.get("evidence_ref"), str) or not reference["evidence_ref"].strip():
        return reject("reference_evidence_missing")
    tolerance = row.get("tolerance_seconds")
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
        return reject("tolerance_missing_or_invalid")
    try:
        if not math.isfinite(tolerance) or tolerance < 0:
            return reject("tolerance_missing_or_invalid")
    except OverflowError:
        return reject("tolerance_missing_or_invalid")
    for key in IDENTITIES:
        if not _identity_valid(key, prediction.get(key)) or not _identity_valid(key, reference.get(key)):
            return reject(f"identity_missing_or_invalid:{key}")
        if prediction[key] != reference[key]:
            return reject(f"identity_mismatch:{key}")
    if "vehicle_id" in prediction or "vehicle_id" in reference:
        if not all(_identity_valid("vehicle_id", item.get("vehicle_id")) for item in (prediction, reference)):
            return reject("identity_missing_or_invalid:vehicle_id")
        if prediction["vehicle_id"] != reference["vehicle_id"]:
            return reject("identity_mismatch:vehicle_id")
    if prediction["event_kind"] not in EVENTS:
        return reject("event_kind_unknown")
    predicted, actual, issued = (_clock(prediction.get("event_at")),
                                 _clock(reference.get("event_at")), _clock(prediction.get("as_of")))
    if predicted is None or actual is None or issued is None:
        return reject("timezone_clock_missing_or_invalid")
    if issued > actual or issued > predicted:
        return reject("prediction_issued_after_event")
    error = (predicted - actual).total_seconds()
    return {**result, "status": "compared", "reason": None,
            "signed_error_seconds": error, "absolute_error_seconds": abs(error),
            "tolerance_seconds": tolerance, "within_tolerance": abs(error) <= tolerance}


def summarize(rows):
    """미평가 행을 전체 분모에 남기고 참조 자료 종류별로 따로 집계한다."""
    if not isinstance(rows, list):
        raise ValueError("입력 rows는 배열이어야 합니다")
    results = [compare_row(row) for row in rows]
    ids = [result["id"] for result in results if result["id"]]
    duplicates = {value for value, count in Counter(ids).items() if count > 1}
    for result in results:
        if result["id"] in duplicates:
            result.update(status="unaligned", reason="duplicate_record_id", within_tolerance=None,
                          absolute_error_seconds=None)
            result.pop("signed_error_seconds", None)
            result.pop("tolerance_seconds", None)
    groups = {}
    for scope in sorted(SCOPES | {"unknown"}):
        selected = [r for r in results if r["scope"] == scope]
        if selected:
            compared = [r for r in selected if r["status"] == "compared"]
            groups[scope] = {"total": len(selected), "compared": len(compared),
                             "unaligned": len(selected) - len(compared),
                             "passed": sum(r["within_tolerance"] is True for r in compared),
                             "failed": sum(r["within_tolerance"] is False for r in compared)}
    return {"schema_version": 1, "rows": results, "total": len(results),
            "compared": sum(r["status"] == "compared" for r in results), "by_reference_kind": groups,
            "claim": "자료 종류별 정렬 비교; 공표·표시·재생은 실제 탑승 정확도가 아님",
            "developer_api_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = json.loads(args.input.read_text(encoding="utf8"))
    report = summarize(document.get("rows") if isinstance(document, dict) else document)
    output = args.output.resolve()
    if output == args.input.resolve():
        raise ValueError("입력 기록과 출력 보고서를 같은 파일로 지정할 수 없습니다")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        backup = output.parent / "_backup" / (datetime.now(UTC).strftime("%Y-%m-%d_%H%M%S") + "_transit_compare_" + uuid4().hex[:8])
        backup.mkdir(parents=True)
        shutil.copy2(output, backup / output.name)
        report["previous_output_backup"] = str(backup / output.name)
    temporary = output.with_name(output.name + "." + uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    temporary.replace(output)
    print(json.dumps({"total": report["total"], "compared": report["compared"],
                      "by_reference_kind": report["by_reference_kind"]}, ensure_ascii=False))
    return 0 if report["total"] > 0 and all(r["within_tolerance"] is True for r in report["rows"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())

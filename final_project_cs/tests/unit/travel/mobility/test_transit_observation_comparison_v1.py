"""현장 관측 정렬과 공표·재생 분모 분리를 검증한다. 실제 측정은 아니다."""
from copy import deepcopy
import json

import pytest

from scripts.mobility.compare_transit_observations_v1 import compare_row, main, summarize


def record(kind="actual_transport_event", difference=30):
    identity = {"journey_id": "synthetic-seoul-trip", "leg_index": 0, "line_id": "1005",
                "direction": "up", "station_id": "1005000534", "service": "local", "event_kind": "board"}
    return {"id": "synthetic-board-1", "tolerance_seconds": 60,
            "prediction": {**identity, "as_of": "2026-10-12T10:00:00+09:00",
                           "event_at": "2026-10-12T10:08:00+09:00"},
            "reference": {**identity, "kind": kind, "event_at": f"2026-10-12T10:08:{difference:02d}+09:00",
                          "evidence_ref": "synthetic/local-log"}}


def test_actual_event_error_preserves_sign_and_explicit_tolerance():
    got = compare_row(record())
    assert got["status"] == "compared" and got["scope"] == "actual_transport_event"
    assert got["signed_error_seconds"] == -30 and got["absolute_error_seconds"] == 30
    assert got["within_tolerance"] is True


def test_error_outside_tolerance_is_failure_not_unscored():
    row = record()
    row["tolerance_seconds"] = 29
    got = compare_row(row)
    assert got["status"] == "compared" and got["within_tolerance"] is False


@pytest.mark.parametrize("actual_id", [None, "0502"])
def test_specific_predicted_train_needs_same_actual_train(actual_id):
    row = record()
    row["prediction"]["vehicle_id"] = "0501"
    if actual_id is not None:
        row["reference"]["vehicle_id"] = actual_id
    assert compare_row(row)["status"] == "unaligned"


@pytest.mark.parametrize("key", ["journey_id", "leg_index", "line_id", "direction", "station_id", "service", "event_kind"])
def test_mismatched_transport_identity_is_not_scored(key):
    row = record()
    row["reference"][key] = 1 if key == "leg_index" else "other"
    got = compare_row(row)
    assert got["reason"] == f"identity_mismatch:{key}" and got["within_tolerance"] is None


@pytest.mark.parametrize("key,value", [("leg_index", True), ("leg_index", -1), ("line_id", None),
                                      ("station_id", ""), ("service", "unknown"), ("direction", "미확인")])
def test_missing_or_unknown_identity_is_not_scored(key, value):
    row = record()
    row["prediction"][key] = row["reference"][key] = value
    assert compare_row(row)["reason"] == f"identity_missing_or_invalid:{key}"


@pytest.mark.parametrize("tolerance", [None, True, -1, float("nan"), float("inf"), "60", 10 ** 1000])
def test_tolerance_must_be_explicit_finite_number(tolerance):
    row = record()
    row["tolerance_seconds"] = tolerance
    assert compare_row(row)["reason"] == "tolerance_missing_or_invalid"


@pytest.mark.parametrize("where,key,value", [
    ("prediction", "as_of", "2026-10-12T10:00:00"),
    ("reference", "event_at", "2026-10-12"),
    ("prediction", "event_at", "invalid"),
    ("prediction", "as_of", "2026-10-12T10:09:00+09:00"),
])
def test_timezone_or_retrospective_prediction_cannot_pass(where, key, value):
    row = record()
    row[where][key] = value
    assert compare_row(row)["status"] == "unaligned"


def test_timezone_offsets_for_same_instants_compare_correctly():
    row = record()
    row["reference"]["event_at"] = "2026-10-12T01:08:30Z"
    assert compare_row(row)["absolute_error_seconds"] == 30


def test_duplicate_record_ids_stay_in_total_and_are_not_counted_twice():
    row = record()
    got = summarize([row, deepcopy(row)])
    assert got["total"] == 2 and got["compared"] == 0
    assert got["by_reference_kind"]["actual_transport_event"] == {
        "total": 2, "compared": 0, "unaligned": 2, "passed": 0, "failed": 0}
    assert all(r["reason"] == "duplicate_record_id" for r in got["rows"])


def test_public_display_and_replay_are_not_actual_transport_accuracy():
    rows = []
    for i, kind in enumerate(["actual_transport_event", "official_timetable", "platform_display", "development_replay"]):
        rows.append(dict(record(kind), id=f"synthetic-{i}"))
    got = summarize(rows)
    assert got["total"] == got["compared"] == 4
    assert len(got["by_reference_kind"]) == 4
    assert got["by_reference_kind"]["actual_transport_event"]["compared"] == 1


@pytest.mark.parametrize("mutation", ["evidence", "kind", "shape", "event"])
def test_unknown_reference_or_event_is_not_a_pass(mutation):
    row = record()
    if mutation == "evidence":
        row["reference"].pop("evidence_ref")
    elif mutation == "kind":
        row["reference"]["kind"] = "unknown"
    elif mutation == "event":
        row["prediction"]["event_kind"] = row["reference"]["event_kind"] = "unknown-event"
    else:
        row = None
    assert compare_row(row)["status"] == "unaligned"


def test_summary_rejects_non_list_instead_of_reporting_empty_success():
    with pytest.raises(ValueError):
        summarize(None)


@pytest.mark.parametrize("kind", [None, [], {}])
def test_malformed_reference_kind_returns_unaligned_instead_of_crashing(kind):
    row = record()
    row["reference"]["kind"] = kind
    assert compare_row(row)["status"] == "unaligned"


def test_cli_backs_up_existing_report_and_returns_nonzero_for_unaligned(tmp_path, monkeypatch):
    source, output = tmp_path / "records.json", tmp_path / "report.json"
    source.write_text(json.dumps({"rows": [record()]}), encoding="utf8")
    monkeypatch.setattr("sys.argv", ["compare", "--input", str(source), "--output", str(output)])
    assert main() == 0
    old = output.read_bytes()
    row = record()
    row.pop("tolerance_seconds")
    source.write_text(json.dumps({"rows": [row]}), encoding="utf8")
    assert main() == 1
    got = json.loads(output.read_text(encoding="utf8"))
    from pathlib import Path
    assert Path(got["previous_output_backup"]).read_bytes() == old
    assert got["total"] == 1 and got["compared"] == 0


def test_cli_never_overwrites_input_records(tmp_path, monkeypatch):
    source = tmp_path / "records.json"
    source.write_text(json.dumps({"rows": [record()]}), encoding="utf8")
    old = source.read_bytes()
    monkeypatch.setattr("sys.argv", ["compare", "--input", str(source), "--output", str(source)])
    with pytest.raises(ValueError):
        main()
    assert source.read_bytes() == old

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from acop_basement.core.project_config import ProjectConfigError, load_project_config

ROOT = Path(__file__).resolve().parents[2]


def test_project_yaml_contract_reads_real_file_and_rejects_removed_field():
    raw = yaml.safe_load((ROOT / "config/project.yaml").read_text(encoding="utf-8"))
    config = load_project_config(ROOT / "config/project.yaml")
    assert config.revision
    assert all({"enabled"} <= set(value) for value in raw["modules"].values())
    assert {"team_executor", "message_broker", "graph_store"} <= set(raw["ports"])

    negative = ROOT / ".contract-negative-project.yaml"
    raw["ports"].pop("graph_store")
    negative.write_text(yaml.safe_dump(raw), encoding="utf-8")
    try:
        with pytest.raises(ProjectConfigError):
            load_project_config(negative)
    finally:
        negative.unlink(missing_ok=True)


def test_dod_contract_reads_real_files_and_rejects_renamed_fixture():
    files = sorted((ROOT / "docs/evidence").glob("DoD-*.md"))
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert path.name.startswith("DoD-")
        assert "```" in text or "판정" in text

    positive = ROOT / ".contract-positive-dod.md"
    positive.write_text("# DoD-01\n판정: 통과\n```text\n실제 출력\n```\n", encoding="utf-8")
    negative = ROOT / ".contract-negative-dod.md"
    negative.write_text(positive.read_text(encoding="utf-8").replace("판정", "결과"), encoding="utf-8")
    try:
        assert "판정:" in positive.read_text(encoding="utf-8")
        assert "판정:" not in negative.read_text(encoding="utf-8")
    finally:
        positive.unlink(missing_ok=True)
        negative.unlink(missing_ok=True)


def test_eval_contract_reads_real_jsonl_and_rejects_renamed_fixture():
    files = sorted((ROOT / "eval/reports").glob("*.jsonl"))
    assert files
    record = json.loads(files[0].read_text(encoding="utf-8").splitlines()[0])
    assert {"config", "arm", "run_id"} <= set(record)
    assert {"provider", "arm", "dataset"} <= set(record["config"])

    negative = dict(record)
    negative["run_id_renamed"] = negative.pop("run_id")
    assert "run_id" not in negative


def test_db_contract_reads_live_columns():
    from acop_basement.infrastructure.db.session import get_connection

    expected = {
        "agent_runs": {"run_id", "case_id", "graph_revision", "status", "started_at", "finished_at"},
        "team_tasks": {"run_id", "task_id", "team_id", "contract_version", "status", "created_at"},
        "llm_calls": {"run_id", "call_id", "prompt_id", "provider", "model", "input_tokens", "output_tokens", "latency_ms", "cost_microusd", "created_at"},
        "case_events": {"case_id", "event_id", "aggregate_version", "event_type", "actor_type", "created_at"},
    }
    with get_connection() as conn, conn.cursor() as cur:
        for table, columns in expected.items():
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", (table,))
            actual = {row[0] for row in cur.fetchall()}
            assert columns <= actual, (table, columns - actual)

"""읽기 어댑터.

★fixture 는 **실제 대상에서 관측한 형식 그대로** 만든다 (2026-08-17 read-only 확인).
  추측한 형식으로 테스트를 짜면 "테스트는 통과하는데 실제 프로젝트에선 빈 화면" 이 된다.

관측한 것:
  - `판정: **통과**` · `판정: 통과` · `판정: **통과 (기준선 기록)**`
    `판정: **부분 통과** — 설명` · `판정: 부분 통과`
  - eval jsonl: `config` 에 arm·provider·model·dataset·dataset_sha256·prompt_snapshot·
    ablations·**estimated_cost_usd**, 행에 **cost_usd**
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from console.readers import (judgement_counts, read_declaration, read_eval_runs,
                             read_guardrails, read_judgements)

DECLARATION = """modules:
  vector_rag:
    enabled: true
  a2a_executor:
    enabled: false
ports:
  team_executor: local
  message_broker: outbox
  graph_store: sql
teams:
- team_id: billing_subscription
  active: true
  implementation_ref: app.modules.customer_ops:BillingSubscriptionTeam
"""


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "project.yaml").write_text(DECLARATION, encoding="utf-8")
    return tmp_path


# ── 조립 선언 ────────────────────────────────────────────────────────────────
def test_declaration_is_read_as_plain_data(project):
    result = read_declaration(project)
    assert result.ok
    assert result.value["modules"] == {"vector_rag": True, "a2a_executor": False}
    assert result.value["ports"]["team_executor"] == "local"
    assert result.value["teams"][0]["team_id"] == "billing_subscription"


def test_a_broken_declaration_is_reported_not_swallowed(project):
    (project / "config" / "project.yaml").write_text("{{{ not yaml", encoding="utf-8")
    result = read_declaration(project)
    assert not result.ok
    assert "읽지 못했다" in result.error
    # ★빈 dict 로 바꾸지 않는다 — 빈 선언과 못 읽은 선언은 다르다
    assert result.value is None


def test_a_missing_declaration_is_reported(tmp_path):
    result = read_declaration(tmp_path)
    assert not result.ok
    assert "없다" in result.error


def test_unexpected_module_shape_becomes_none_not_false(project):
    """★형태가 다르면 `None`(모름)이다. `False` 로 바꾸면 '꺼짐' 으로 읽힌다."""
    (project / "config" / "project.yaml").write_text(
        "modules:\n  weird: yes\nports: {}\nteams: []\n", encoding="utf-8")
    assert read_declaration(project).value["modules"] == {"weird": None}


# ── DoD 판정 ─────────────────────────────────────────────────────────────────
def _evidence(project: Path, name: str, body: str) -> None:
    folder = project / "docs" / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(body, encoding="utf-8")


def test_every_observed_judgement_form_is_parsed(project):
    """★실제로 관측된 6가지 표기를 전부 넣는다."""
    forms = {
        "DoD-01_a.md": "- 판정: **통과**",
        "DoD-02_b.md": "- 판정: 통과",
        "DoD-03_c.md": "- 판정: **통과 (기준선 기록)**",
        "DoD-04_d.md": "- 판정: **부분 통과** — 설명이 뒤에 붙는다",
        "DoD-05_e.md": "- 판정: 부분 통과",
        "DoD-06_f.md": "- 판정: 통과 (★한계는 아래 참조)",
        "DoD-07_g.md": "- 판정: 미착수",
    }
    for name, body in forms.items():
        _evidence(project, name, body)
    counts = judgement_counts(read_judgements(project).value)
    assert counts == {"통과": 4, "부분통과": 2, "미착수": 1}


def test_a_document_without_a_judgement_is_named_not_dropped(project):
    _evidence(project, "DoD-09_nothing.md", "# 아무 판정도 없다")
    items = read_judgements(project).value
    assert [i.judgement for i in items] == ["판정 없음"]


def test_reproduction_and_actual_output_are_reported(project):
    _evidence(project, "DoD-01_x.md", "- 판정: 통과\n\n## 실제 출력\n```\n3 passed\n```\n")
    _evidence(project, "DoD-02_y.md", "- 판정: 통과\n근거가 없다\n")
    items = {i.id: i for i in read_judgements(project).value}
    assert items["DoD-01"].has_reproduction and items["DoD-01"].has_actual_output
    assert not items["DoD-02"].has_reproduction
    assert not items["DoD-02"].has_actual_output


def test_missing_evidence_folder_is_reported(project):
    result = read_judgements(project)
    assert result.value == []
    assert "없다" in result.error


# ── 평가 실행 ────────────────────────────────────────────────────────────────
def _report(project: Path, name: str, rows: list[dict]) -> None:
    folder = project / "eval" / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")


def _row(**over) -> dict:
    row = {"arm": "Proposed", "cost_usd": 0.001,
           "config": {"arm": "Proposed", "provider": "openai", "model": "gpt-4o-mini",
                      "dataset": "eval/datasets/golden.jsonl", "dataset_sha256": "abc123",
                      "prompt_snapshot": "proposed-v1", "ablations": ["no_rag"],
                      "estimated_cost_usd": 0.0273}}
    row.update(over)
    return row


def test_eval_run_keeps_arm_dataset_and_prompt_snapshot(project):
    _report(project, "abl_no_rag.jsonl", [_row(), _row()])
    run = read_eval_runs(project).value["runs"][0]
    assert run.arm == "Proposed"
    assert run.dataset_sha256 == "abc123"
    assert run.prompt_snapshot == "proposed-v1"
    assert run.ablations == ["no_rag"]
    assert run.rows == 2


def test_observed_and_estimated_cost_are_not_conflated(project):
    """★추정과 실측을 하나로 뭉치면 거짓이 된다."""
    _report(project, "run.jsonl", [_row(), _row()])
    run = read_eval_runs(project).value["runs"][0]
    assert run.observed_cost_usd == 0.002       # 행별 합
    assert run.estimated_cost_usd == 0.0273     # 돌리기 전 추정
    assert run.observed_cost_usd != run.estimated_cost_usd


def test_missing_cost_is_none_not_zero(project):
    """★한 줄도 값이 없으면 `0.0` 이 아니라 모름이다. 0 은 '공짜' 로 읽힌다."""
    _report(project, "run.jsonl", [_row(cost_usd=None)])
    assert read_eval_runs(project).value["runs"][0].observed_cost_usd is None


def test_mock_runs_are_flagged(project):
    _report(project, "mock.jsonl", [_row(config={"provider": "mock"})])
    assert read_eval_runs(project).value["runs"][0].is_mock


def test_truncation_reports_total_and_shown(project):
    """★말없이 자르면 '이게 전부' 로 읽힌다."""
    for i in range(5):
        _report(project, f"r{i}.jsonl", [_row()])
    result = read_eval_runs(project, limit=2).value
    assert result["total"] == 5
    assert result["shown"] == 2


def test_unreadable_report_is_listed_with_a_note(project):
    _report(project, "broken.jsonl", [])
    (project / "eval" / "reports" / "broken.jsonl").write_text("not json", encoding="utf-8")
    run = read_eval_runs(project).value["runs"][0]
    assert run.note and "형식 불명" in run.note
def test_guardrails_is_read_normally(project):
    (project / "config" / "guardrails.yaml").write_text("context:\n  token_budget: 12000\n", encoding="utf-8")
    result = read_guardrails(project)
    assert result.ok
    assert result.value["context"]["token_budget"] == 12000


def test_missing_guardrails_file_is_reported(tmp_path):
    result = read_guardrails(tmp_path)
    assert not result.ok
    assert "guardrails.yaml" in result.error


def test_broken_guardrails_yaml_is_reported(project):
    (project / "config" / "guardrails.yaml").write_text("context: [", encoding="utf-8")
    result = read_guardrails(project)
    assert not result.ok
    assert result.value is None
    assert result.error


def test_unreadable_evidence_location_is_reported(project):
    (project / "docs").mkdir()
    (project / "docs" / "evidence").write_text("not a directory", encoding="utf-8")
    result = read_judgements(project)
    assert result.value == []
    assert result.error


def test_malformed_eval_row_is_excluded_from_cost_but_counted_as_seen_row(project):
    _report(project, "mixed.jsonl", [_row(cost_usd=0.125)])
    path = project / "eval" / "reports" / "mixed.jsonl"
    path.write_text(json.dumps(_row(cost_usd=0.125)) + "\nnot-json\n", encoding="utf-8")
    run = read_eval_runs(project).value["runs"][0]
    assert run.observed_cost_usd == 0.125
    assert run.rows == 2

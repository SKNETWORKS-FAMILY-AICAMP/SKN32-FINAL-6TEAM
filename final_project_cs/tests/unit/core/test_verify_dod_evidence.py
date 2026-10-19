"""DoD가 실제 pytest의 정리 오류와 비정상 종료를 숨기지 않는지 검사한다."""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET

import pytest

from scripts import verify_dod_v11 as dod


def _scenario(tmp_path, monkeypatch, source):
    (tmp_path / "test_probe.py").write_text(source, encoding="utf-8")
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setattr(dod, "ROOT", tmp_path)
    monkeypatch.setattr(dod, "ITEMS", (
        dod.Item(1, "여행 실행 검증", "자동", ("test_probe.py::test_body",)),
    ))
    evidence = tmp_path / "evidence"
    monkeypatch.setattr(sys, "argv", ["verify_dod_v11", "--evidence-dir", str(evidence)])
    return evidence


def test_a_teardown_error_keeps_the_full_cause_and_fails_the_gate(tmp_path, monkeypatch, capsys):
    cause = "정리 단계 연결 오류 근거: " + "X" * 3000
    evidence = _scenario(tmp_path, monkeypatch, f"""
import pytest
@pytest.fixture
def world():
    yield
    raise RuntimeError({cause!r})
def test_body(world):
    assert True
""")

    assert dod.main() == 1
    assert cause in capsys.readouterr().out
    assert cause in (evidence / "pytest.stdout.log").read_text(encoding="utf-8")
    summary = json.loads((evidence / "summary.json").read_text(encoding="utf-8"))
    assert summary["passed"] == 0 and summary["failed"] == 1
    assert summary["test_results"]["test_probe.py::test_body"] == "ERROR"
    assert any(case.find("error") is not None for case in ET.parse(evidence / "pytest.xml").iter("testcase"))


def test_a_child_failure_after_passed_tests_still_fails_the_gate(tmp_path, monkeypatch, capsys):
    evidence = _scenario(tmp_path, monkeypatch, "def test_body():\n    assert True\n")
    (tmp_path / "conftest.py").write_text("""
def pytest_sessionfinish(session, exitstatus):
    if not session.config.option.collectonly:
        session.exitstatus = 7
""", encoding="utf-8")

    assert dod.main() == 1
    assert "하위 시험 명령 종료 코드: 7" in capsys.readouterr().out
    summary = json.loads((evidence / "summary.json").read_text(encoding="utf-8"))
    assert summary["subprocess_exit_code"] == 7


def test_a_successful_run_preserves_every_parameter_and_the_exact_selection(tmp_path, monkeypatch):
    evidence = _scenario(tmp_path, monkeypatch, """
import pytest
@pytest.mark.parametrize('value', [1, 2])
def test_body(value):
    assert value > 0
""")

    assert dod.main() == 0
    summary = json.loads((evidence / "summary.json").read_text(encoding="utf-8"))
    execution = json.loads((evidence / "execution.json").read_text(encoding="utf-8"))
    assert summary["passed"] == summary["total"] == 1
    assert len(summary["test_results"]) == 2
    assert set(summary["test_results"].values()) == {"PASSED"}
    assert execution["requested_nodes"] == execution["runnable_nodes"] == ["test_probe.py::test_body"]
    assert execution["pytest_exit_code"] == execution["collection_exit_code"] == 0


def test_an_existing_evidence_directory_is_not_overwritten(tmp_path, monkeypatch):
    evidence = _scenario(tmp_path, monkeypatch, "def test_body():\n    assert True\n")
    evidence.mkdir()
    marker = evidence / "previous.log"
    marker.write_text("이전 실행 원문", encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        dod.main()
    assert error.value.code == 2
    assert marker.read_text(encoding="utf-8") == "이전 실행 원문"


def test_a_database_error_preserves_the_cause_without_printing_credentials(tmp_path, monkeypatch, capsys):
    credential = "probe-" + __import__("uuid").uuid4().hex
    message = (f"connection closed unexpectedly; password='{credential}'; "
               f"postgresql://tester:{credential}@localhost/test")
    evidence = _scenario(tmp_path, monkeypatch, f"def test_body():\n    raise RuntimeError({message!r})\n")

    assert dod.main() == 1
    output = capsys.readouterr().out
    saved = (evidence / "pytest.stdout.log").read_text(encoding="utf-8")
    for text in (output, saved):
        assert "connection closed unexpectedly" in text
        assert "[REDACTED]" in text
        assert credential not in text

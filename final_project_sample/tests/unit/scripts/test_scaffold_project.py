from __future__ import annotations

import sys

import pytest

from acop_basement.core.project_config import load_project_config
from examples.catalog import CATALOG
from scripts import scaffold_project


def test_list_prints_exactly_two_catalog_entries(capsys):
    assert scaffold_project.main(["list"]) == 0
    output = capsys.readouterr().out
    lines = output.splitlines()
    assert len(lines) == 4
    assert lines[0].split() == ["example_id", "case_type", "summary"]
    for entry in CATALOG:
        assert entry.example_id in output
        assert entry.case_type in output
        assert entry.summary in output


def test_show_unknown_example_fails(capsys):
    assert scaffold_project.main(["show", "does_not_exist"]) != 0
    assert "unknown example_id" in capsys.readouterr().err


def test_new_writes_module_and_loader_valid_project(tmp_path, monkeypatch, capsys):
    target = tmp_path / "new-project"
    assert scaffold_project.main(["new", "billing_subscription", "--target", str(target)]) == 0

    copied = target / "app" / "modules" / "customer_ops" / "billing.py"
    project_yaml = target / "config" / "project.yaml"
    assert copied.read_bytes() == (scaffold_project.REPO_ROOT / CATALOG[0].module_path).read_bytes()

    monkeypatch.syspath_prepend(str(target))
    # The test process already imported this repository's ``app`` package;
    # emulate loading the generated project as the process's app package.
    original_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            del sys.modules[module_name]
    try:
        config = load_project_config(project_yaml)
    finally:
        for module_name in list(sys.modules):
            if module_name == "app" or module_name.startswith("app."):
                del sys.modules[module_name]
        sys.modules.update(original_app_modules)
    assert config.teams[0].team_id == "billing_subscription"
    assert config.teams[0].implementation_ref == CATALOG[0].implementation_ref
    assert set(config.modules) == set(CATALOG[0].required_modules)
    assert config.ports.model_dump() == CATALOG[0].required_ports
    assert "Next steps" in capsys.readouterr().out


def test_new_refuses_to_overwrite_existing_project_yaml(tmp_path, capsys):
    target = tmp_path / "existing-project"
    project_yaml = target / "config" / "project.yaml"
    project_yaml.parent.mkdir(parents=True)
    original = "do not overwrite\n"
    project_yaml.write_text(original, encoding="utf-8")

    assert scaffold_project.main(["new", "technical_entitlement", "--target", str(target)]) != 0
    assert project_yaml.read_text(encoding="utf-8") == original
    assert not (target / "app").exists()
    assert "refusing to overwrite" in capsys.readouterr().err

"""composer_service.apply_candidate() 가 실패 경로에서 임시 파일을 안 남기는지 검사한다.

★버그사냥 2026-08-17 (라운드 07) — os.replace() 가 실패하면 staged 파일이
정리되지 않고 남았다. 반복되는 디스크 오류·권한 문제에서 임시 파일이 쌓인다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from acop_basement.core import config_store
from acop_composer import service as composer_service
from acop_composer.service import apply_candidate


@pytest.fixture()
def declaration(tmp_path: Path) -> Path:
    source = Path("config/project.yaml")
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    path = tmp_path / "project.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def test_staged_file_is_removed_when_os_replace_fails(declaration, monkeypatch):
    raw = yaml.safe_load(declaration.read_text(encoding="utf-8"))
    current = composer_service.read_current(declaration)

    def _boom(*_args, **_kwargs):
        raise OSError("simulated disk failure")

    # ★2026-08-29 — 원자적 교체가 `acop_basement.core.config_store.FileConfigStore`
    #   로 옮겨갔다(중앙 설정 저장소 도입). 검사하는 **성질**은 그대로다:
    #   교체가 실패해도 임시 파일이 안 남고 원본이 안 바뀐다.
    monkeypatch.setattr(config_store.os, "replace", _boom)

    with pytest.raises(OSError, match="simulated disk failure"):
        apply_candidate(raw, base_revision=current.revision, path=declaration)

    leftovers = list(declaration.parent.glob(f".{declaration.stem}.*"))
    assert leftovers == [], f"임시 파일이 정리되지 않고 남았다: {leftovers}"
    # ★원본은 손대지 않았어야 한다 - os.replace() 가 실패했으니 revision 이 그대로다.
    assert composer_service.read_current(declaration).revision == current.revision

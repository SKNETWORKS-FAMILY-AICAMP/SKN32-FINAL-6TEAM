"""config/project.yaml 에 같은 칸이 두 번 적히지 않았는지 — ST4F-714(LB-16).

YAML 은 같은 칸이 두 번 나오면 말없이 뒤의 값을 쓴다. 요식(dining) 팀 블록에
required · capabilities · hooks 가 두 번 적혀 있어 어느 값이 쓰이는지 읽는 사람이 헷갈렸다.
두 값이 지금은 같아도, 한쪽만 고치면 고친 값이 무시될 수 있다.
"""

from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_YAML = Path(__file__).resolve().parents[3] / "config" / "project.yaml"


class _NoDuplicateLoader(yaml.SafeLoader):
    pass


def _mapping_without_duplicates(loader, node, deep=False):
    seen: dict = {}
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise AssertionError(f"project.yaml {key_node.start_mark.line + 1}행: 「{key}」 칸이 같은 블록에 이미 "
                                 f"{seen[key]}행에 있다")
        seen[key] = key_node.start_mark.line + 1
    return loader.construct_mapping(node, deep=deep)


_NoDuplicateLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping_without_duplicates)


def test_project_yaml_has_no_duplicate_keys_in_any_block() -> None:
    yaml.load(PROJECT_YAML.read_text(encoding="utf-8"), Loader=_NoDuplicateLoader)

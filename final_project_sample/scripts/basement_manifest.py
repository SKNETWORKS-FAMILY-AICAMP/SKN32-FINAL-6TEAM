"""Declarative definition of the files that make up the basement export."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

# Keep this list explicit: changing the basement boundary is a deliberate
# versioning decision, not an accidental consequence of directory crawling.
BASEMENT_COMPONENTS: tuple[str, ...] = (
    "acop_basement/core",
    "acop_basement/domain",
    "acop_basement/application",
    "acop_basement/infrastructure",
    "acop_basement/presentation",
    "acop_basement/tools",
    "acop_basement/introspection",
)
EXCLUDED_PATTERNS: tuple[str, ...] = ("__pycache__", "*.pyc")

# ★버그사냥 2026-08-19 — 도메인 마이그레이션(002_domain_customer_ops.sql)이
#   한때 acop_basement/infrastructure/db/migrations/ 안에 물리적으로 있었다
#   (basement 순수성 위반 — domain 무관해야 할 패키지 안에 도메인 SQL이
#   실렸다). config/migrations/(product 쪽)로 옮겨서 애초에 이 경로에
#   존재하지 않게 됐다. 패턴 제외 목록으로 가리는 것보다 원천적으로 위치를
#   옮기는 게 맞다 — export 뿐 아니라 실제 pip 배포물에도 안 실린다.
EXCLUDED_FILES: tuple[str, ...] = ()

BASEMENT_VERSION = "0.3.0"
CONTRACT_VERSION = "1.0"
EXPORT_TOOL_VERSION = "1"


def _matches_exclusion(relative_path: str, path: Path) -> bool:
    """Return whether a repository-relative path is outside the export."""

    if any(part in EXCLUDED_PATTERNS for part in path.parts):
        return True
    if any(fnmatch(relative_path, pattern) for pattern in EXCLUDED_FILES):
        return True
    return path.suffix == ".pyc"


def basement_files(root: Path | str) -> list[Path]:
    """Return existing basement files in stable, repository-relative order."""

    root = Path(root).resolve()
    files: list[Path] = []
    for component in BASEMENT_COMPONENTS:
        component_root = root / component
        if not component_root.exists():
            continue
        for path in component_root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if not _matches_exclusion(relative, path):
                files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def excluded_entries() -> list[str]:
    """Return the declared exclusions for inclusion in the artifact."""

    return [*EXCLUDED_PATTERNS, *EXCLUDED_FILES]

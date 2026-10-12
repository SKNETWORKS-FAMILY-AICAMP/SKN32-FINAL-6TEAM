"""Export the reusable basement sources and a content-addressed manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from .basement_manifest import (
    BASEMENT_COMPONENTS,
    BASEMENT_VERSION,
    CONTRACT_VERSION,
    EXPORT_TOOL_VERSION,
    basement_files,
    excluded_entries,
)

ROOT = Path(__file__).resolve().parents[1]


def _git_value(*args: str, root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=root, stderr=subprocess.DEVNULL, text=True
        ).strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path | str = ROOT, *, generated_at: datetime | None = None) -> dict:
    """Build a deterministic manifest except for the supplied timestamp."""

    root = Path(root).resolve()
    timestamp = generated_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    files = basement_files(root)
    return {
        "basement_version": BASEMENT_VERSION,
        "source_commit": _git_value("rev-parse", "HEAD", root=root),
        "source_tag": _git_value("describe", "--tags", root=root),
        "generated_at": timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "components": list(BASEMENT_COMPONENTS),
        "excluded": excluded_entries(),
        "files": [
            {"path": path.relative_to(root).as_posix(), "sha256": _sha256(path)}
            for path in files
        ],
        "contract_version": CONTRACT_VERSION,
        "export_tool_version": EXPORT_TOOL_VERSION,
    }


def export_basement(
    root: Path | str = ROOT,
    output_dir: Path | str | None = None,
    *,
    generated_at: datetime | None = None,
) -> tuple[Path, dict]:
    """Write ``manifest.json`` and the declared sources below ``output_dir``."""

    root = Path(root).resolve()
    destination = Path(output_dir) if output_dir is not None else root / "dist" / "basement"
    destination = destination.resolve()
    manifest = build_manifest(root, generated_at=generated_at)
    files_root = destination / "files"

    # The destination is a generated artifact.  Removing only this exact
    # output directory prevents stale files from surviving a later export.
    if destination.exists():
        shutil.rmtree(destination)
    files_root.mkdir(parents=True)
    for source in basement_files(root):
        relative = source.relative_to(root)
        target = files_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    manifest_path = destination / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest_path, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="override dist/basement")
    args = parser.parse_args()
    manifest_path, manifest = export_basement(output_dir=args.output_dir)
    print(f"exported {len(manifest['files'])} files to {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

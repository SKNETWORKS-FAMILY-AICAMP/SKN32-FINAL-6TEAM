"""Compare a CS checkout against the sample basement manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("cs_root", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    root = args.cs_root.resolve()

    matches: list[str] = []
    drifts: list[dict[str, str]] = []
    missing: list[str] = []
    for entry in manifest["files"]:
        relative = Path(*entry["path"].split("/"))
        path = root / relative
        if not path.is_file():
            missing.append(entry["path"])
        elif sha256(path) == entry["sha256"]:
            matches.append(entry["path"])
        else:
            drifts.append(
                {"path": entry["path"], "expected": entry["sha256"], "actual": sha256(path)}
            )

    components = [Path(*component.split("/")) for component in manifest["components"]]
    declared = {entry["path"] for entry in manifest["files"]}
    unique: list[str] = []
    for component in components:
        base = root / component
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                relative = path.relative_to(root).as_posix()
                if relative not in declared:
                    unique.append(relative)

    result = {
        "manifest_files": len(manifest["files"]),
        "match": matches,
        "drift": drifts,
        "missing": missing,
        "cs_unique": unique,
        "counts": {
            "match": len(matches),
            "drift": len(drifts),
            "missing": len(missing),
            "cs_unique": len(unique),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

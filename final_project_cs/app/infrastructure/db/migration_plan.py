"""Resolve current SQL inputs and preserve explicitly retired SQL as history."""
import json
from pathlib import Path

def migration_files(directory: Path) -> tuple[list[Path], list[Path]]:
    plan = json.loads((directory / "migration-plan.json").read_text(encoding="utf-8"))
    if plan.get("version") != 1:
        raise ValueError("Unsupported migration plan version")
    names = plan["historical_files"]
    if not isinstance(names, list) or any(not isinstance(n, str) for n in names):
        raise ValueError("Historical SQL names must be a list of strings")
    if len(names) != len(set(names)):
        raise ValueError("Duplicate historical SQL name")
    for name in names:
        if Path(name).name != name or "/" in name or "\\" in name or not name.endswith(".sql"):
            raise ValueError("Historical SQL must be a local SQL filename")
        if not (directory / name).is_file():
            raise ValueError(f"Missing historical SQL: {name}")
    historical = [directory / n for n in sorted(names)]
    return [p for p in sorted(directory.glob("*.sql")) if p.name not in names], historical

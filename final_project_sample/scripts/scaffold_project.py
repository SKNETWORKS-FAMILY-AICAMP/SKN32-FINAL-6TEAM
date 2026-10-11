"""Scaffold a project from one of the explicitly cataloged examples."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sys

from examples.catalog import CATALOG, ExampleEntry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _entry(example_id: str) -> ExampleEntry:
    for entry in CATALOG:
        if entry.example_id == example_id:
            return entry
    raise ValueError(f"unknown example_id: {example_id}")


def _print_list() -> None:
    rows = [("example_id", "case_type", "summary")]
    rows.extend((item.example_id, item.case_type, item.summary) for item in CATALOG)
    widths = [max(len(row[index]) for row in rows) for index in range(3)]
    for number, row in enumerate(rows):
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
        if number == 0:
            print("  ".join("-" * width for width in widths))


def _project_yaml(entry: ExampleEntry, team_id: str) -> str:
    module_lines = "\n".join(
        f"  {module_id}:\n    enabled: true" for module_id in entry.required_modules
    )
    port_lines = "\n".join(f"  {name}: {value}" for name, value in entry.required_ports.items())
    return (
        "modules:\n"
        f"{module_lines}\n"
        "ports:\n"
        f"{port_lines}\n"
        "teams:\n"
        f"- team_id: {team_id}\n"
        "  active: true\n"
        f"  implementation_ref: {entry.implementation_ref}\n"
    )


def _new(entry: ExampleEntry, target: Path, team_id: str) -> None:
    project_yaml = target / "config" / "project.yaml"
    if project_yaml.exists():
        raise FileExistsError(f"refusing to overwrite existing file: {project_yaml}")

    source = REPO_ROOT / entry.module_path
    if not source.is_file():
        raise FileNotFoundError(f"catalog source does not exist: {source}")

    destination = target / "app" / "modules" / "customer_ops" / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Make the copied module importable by the loader in a standalone target.
    for package_dir in (target / "app", target / "app" / "modules", destination.parent):
        init_file = package_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8")
    shutil.copyfile(source, destination)
    project_yaml.parent.mkdir(parents=True, exist_ok=True)
    project_yaml.write_text(_project_yaml(entry, team_id), encoding="utf-8")

    print(f"Created project scaffold in {target}")
    print(f"Copied example module: {destination}")
    print(f"Created project declaration: {project_yaml}")
    print("Next steps (run manually):")
    print("  pip install -e <acop_basement path>")
    print("  Apply the project's database migrations.")
    print("  python -m pytest tests/architecture -q")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="list catalog entries")
    show = subparsers.add_parser("show", help="show one catalog entry")
    show.add_argument("example_id")
    new = subparsers.add_parser("new", help="create a project scaffold")
    new.add_argument("example_id")
    new.add_argument("--target", required=True, type=Path)
    new.add_argument("--team-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "list":
            _print_list()
        elif args.command == "show":
            print(json.dumps(asdict(_entry(args.example_id)), ensure_ascii=False, indent=2))
        else:
            item = _entry(args.example_id)
            _new(item, args.target, args.team_id or item.example_id)
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

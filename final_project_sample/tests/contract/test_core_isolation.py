from pathlib import Path
import ast


_FORBIDDEN_PREFIXES = (
    "app.modules",
    "acop_basement.presentation",
    "acop_basement.infrastructure",
    "acop_basement.application",
    "app.composition",
)


def test_core_does_not_import_modules():
    root = Path("acop_basement/core")
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if any(name == prefix or name.startswith(prefix + ".") for prefix in _FORBIDDEN_PREFIXES):
                    assert False, f"Core isolation violation: {path} imports {name}"

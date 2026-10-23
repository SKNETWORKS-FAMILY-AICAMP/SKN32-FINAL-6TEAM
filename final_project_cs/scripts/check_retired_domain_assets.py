"""Reject retired runtime surfaces and business fixtures; historical and defense material stay separate."""
from pathlib import Path
import ast
import os

ROOT = Path(__file__).resolve().parents[1]
RETIRED_LITERALS = frozenset({
    "billing", "post_cancel_charge", "payment_failed", "billing.investigate",
    "fake_order", "order.investigate", "return.diagnose", "read.order",
    "read.shipment", "read.catalog", "read.order_items", "read.return",
    "order:read", "return:read",
})

def check_tree(root: Path) -> list[str]:
    problems = []
    for area in ("app", "tests"):
        for folder, dirs, files in os.walk(root / area):
            dirs[:] = [d for d in dirs if d not in {"_backup", "legacy", "__pycache__"}]
            for name in files:
                p = Path(folder) / name
                if p.suffix != ".py":
                    continue
                tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
                for n in ast.walk(tree):
                    if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in RETIRED_LITERALS:
                        problems.append(f"{p.relative_to(root)}:{n.lineno}: retired business fixture {n.value}")
                    if isinstance(n, ast.ImportFrom) and n.module == "app.presentation.api.mcp":
                        problems.append(f"{p.relative_to(root)}:{n.lineno}: retired MCP import")
    if (root / "app/presentation/api/mcp.py").exists():
        problems.append("Retired MCP surface exists in active app")
    dockerfile = root / "deploy/Dockerfile.api"
    if dockerfile.exists():
        ignore = root / ".dockerignore"
        patterns = ignore.read_text(encoding="utf-8").splitlines() if ignore.exists() else []
        if "**/_backup/" not in patterns:
            problems.append("Docker build context must exclude historical _backup directories")
    return problems

def main() -> int:
    problems = check_tree(ROOT)
    for problem in problems:
        print(problem)
    print(f"retired domain guard: {len(problems)} violation(s)")
    return int(bool(problems))

if __name__ == "__main__":
    raise SystemExit(main())

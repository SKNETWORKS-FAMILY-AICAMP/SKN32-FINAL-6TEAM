"""문서를 가리키는 참조가 실재하는지 본다.

문서 체재가 바뀌면 마크다운 링크는 이전 작업에서 같이 고쳐지는데
**코드 주석 안의 경로는 안 따라간다.** 실제로 `docs/` 가 `wiki/records/` 로
옮겨간 뒤 파이썬 주석 92곳이 없어진 경로를 가리키고 있었다.

주석이 틀리면 그 주석을 믿고 근거를 찾으러 간 사람이 빈손으로 돌아온다.
근거를 대는 문화를 유지하려면 근거 경로가 살아 있어야 한다.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

#: 저장소 안 문서를 가리키는 모양. 확장자가 있거나 알려진 문서 폴더로 시작한다.
REFERENCE = re.compile(
    r"(?<![\w/])(?:docs|wiki)/[A-Za-z0-9_./\-가-힣]*\.(?:md|py|ya?ml|json|jsonl)"
)

SKIP_PARTS = (".pytest", "__pycache__", "/legacy/", "/.git/", "/node_modules/")
SCAN_SUFFIXES = (".py", ".md")


def _skip(path: Path) -> bool:
    text = str(path).replace("\\", "/")
    return any(part in text for part in SKIP_PARTS)


def scan(target: Path) -> dict[str, Any]:
    """없어진 경로를 가리키는 참조를 모은다. 어디로 옮겨갔는지도 같이 찾는다."""
    broken: list[tuple[str, int, str, str]] = []
    checked = 0
    for path in target.rglob("*"):
        if path.suffix not in SCAN_SUFFIXES or not path.is_file() or _skip(path):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        where = str(path.relative_to(target)).replace("\\", "/")
        for number, line in enumerate(lines, start=1):
            for match in REFERENCE.finditer(line):
                reference = match.group(0)
                checked += 1
                if (target / reference).exists():
                    continue
                broken.append((where, number, reference, _moved_to(target, reference)))
    return {"checked": checked, "broken": broken}


def _moved_to(target: Path, reference: str) -> str:
    """옮겨간 자리를 찾아본다. 못 찾으면 빈 문자열이다 — 지어내지 않는다."""
    if reference.startswith("docs/"):
        candidate = "wiki/records/" + reference[len("docs/"):]
        if (target / candidate).exists():
            return candidate
    name = Path(reference).name
    matches = [p for p in (target / "wiki").rglob(name)] if (target / "wiki").is_dir() else []
    if len(matches) == 1:
        return str(matches[0].relative_to(target)).replace("\\", "/")
    return ""


def report(outcome: dict[str, Any], *, separator: str, limit: int = 12) -> int:
    broken = outcome["broken"]
    checked = outcome["checked"]
    found = checked - len(broken)
    ratio = f"{found}/{checked}" if checked else "0/0"
    percent = f" = {found * 100 // checked}%" if checked else ""
    print(f"문서를 가리키는 참조 {checked}건 · 실재하는 것 {ratio}{percent}")
    print(separator)
    if not broken:
        print("없어진 경로를 가리키는 참조가 없다.")
        return 0

    fixable = [row for row in broken if row[3]]
    print(f"  없어진 경로를 가리킨다        {len(broken)}건")
    print(f"    옮겨간 자리를 찾은 것       {len(fixable)}건 — 경로만 바꾸면 된다")
    print(f"    못 찾은 것                 {len(broken) - len(fixable)}건 — 사람이 봐야 한다")
    print("")
    for where, number, reference, moved in broken[:limit]:
        arrow = f"  ->  {moved}" if moved else "  (옮겨간 자리를 못 찾았다)"
        print(f"  {where}:{number}")
        print(f"    {reference}{arrow}")
    if len(broken) > limit:
        print(f"  … 외 {len(broken) - limit}건")
    return 1


def fix(target: Path, outcome: dict[str, Any]) -> dict[str, Any]:
    """옮겨간 자리를 찾은 참조만 고친다. 못 찾은 것은 건드리지 않는다.

    바꾸는 것은 **주석과 문서 안의 경로 문자열뿐**이다. 동작은 바뀌지 않는다.
    그래도 고친 뒤에는 테스트를 돌려 확인한다 — 경로가 코드로 쓰이는 곳이
    있을 수 있고, 그 경우 문자열 치환이 동작을 바꾼다.
    """
    plans: dict[str, list[tuple[str, str]]] = {}
    for where, _number, reference, moved in outcome["broken"]:
        if moved:
            plans.setdefault(where, []).append((reference, moved))

    changed, replaced = 0, 0
    for where, pairs in sorted(plans.items()):
        path = target / where
        with path.open(encoding="utf-8", newline="") as handle:
            text = handle.read()
        original = text
        for reference, moved in pairs:
            count = text.count(reference)
            if count:
                text = text.replace(reference, moved)
                replaced += count
        if text != original:
            with path.open("w", encoding="utf-8", newline="") as handle:
                handle.write(text)
            changed += 1
    return {"files": changed, "references": replaced,
            "left": [row for row in outcome["broken"] if not row[3]]}

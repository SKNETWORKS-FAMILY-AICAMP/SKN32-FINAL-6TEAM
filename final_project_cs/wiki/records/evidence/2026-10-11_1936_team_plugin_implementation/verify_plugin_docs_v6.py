"""현재 계약과 이번 검증 기록의 로컬 파일 링크·문서 해시를 확인한다."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit


def main() -> None:
    evidence = Path(__file__).resolve().parent
    root = evidence.parents[3]
    previous = json.loads((evidence / "wiki-link-check-v3.json").read_text(encoding="utf-8"))
    documents = {root / name for name in previous["document_sha256"]}
    reports = root / "wiki/records/reports"
    for path in reports.glob("2026-10-1[12]_*.md"):
        if any(word in path.stem for word in ("plugin", "resume", "worker", "conversation", "initial", "operating")):
            documents.add(path)
    documents.add(root / "wiki/records/plans/2026-10-11_2325_conversation_isolation.md")
    broken: list[dict[str, str]] = []
    checked = 0
    hashes: dict[str, str] = {}
    for path in sorted(documents):
        if not path.is_file():
            broken.append({"document": str(path.relative_to(root)), "target": "document missing"})
            continue
        raw = path.read_bytes()
        hashes[path.relative_to(root).as_posix()] = hashlib.sha256(raw).hexdigest()
        source = re.sub(r"```.*?```", "", raw.decode("utf-8-sig"), flags=re.S)
        for match in re.finditer(r"\]\((<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)", source):
            target = match.group(1).strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            local = unquote(parsed.path)
            local = re.sub(r":\d+$", "", local)
            resolved = Path(local) if Path(local).is_absolute() else path.parent / local
            checked += 1
            if not resolved.exists():
                broken.append({"document": path.relative_to(root).as_posix(), "target": target})
    output = {
        "created_at": datetime.now().astimezone().isoformat(),
        "scope": "local file targets only; remote URLs, anchor existence and browser rendering not checked",
        "documents": len(documents), "checked": checked, "broken": broken, "document_sha256": hashes,
    }
    destination = evidence / "wiki-link-check-v6.json"
    if destination.exists():
        raise FileExistsError("preserve the previous result; use a new version for a new run")
    destination.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: output[key] for key in ("documents", "checked", "broken")}, ensure_ascii=True))
    if broken:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

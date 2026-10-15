"""준비 산출물의 링크·원문 일치·비밀값과 기존 자료 제외 규칙을 검사한다."""
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse
import hashlib
import ipaddress
import json
import re
import shutil
import subprocess
import sys
import markdown

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[4]
NOW = datetime.now(timezone(timedelta(hours=9)))
BACKUP = BASE / "_backup" / (NOW.strftime("%Y-%m-%d_%H%M%S") + "_preparation_audit")


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.source_hash = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.append(values["id"])
        if tag == "a" and "href" in values:
            self.links.append(values["href"])
        if tag == "meta" and values.get("name") == "source-sha256":
            self.source_hash = values.get("content")


def save(name, value):
    path = BASE / name
    if path.exists():
        BACKUP.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, BACKUP / name)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    pages = ["v12-outline", "baseline-outline", "review-checklist", "integration-table"]
    checks, links, files = [], [], []
    for stem in pages:
        md = BASE / (stem + ".md")
        page = BASE / (stem + ".html")
        source = md.read_text(encoding="utf-8")
        raw = page.read_text(encoding="utf-8")
        parser = Page()
        parser.feed(raw)
        digest = hashlib.sha256(md.read_bytes()).hexdigest()
        checks.append({"name": stem + " 원문 해시", "passed": parser.source_hash == digest})
        body = source.split("---\n", 2)[2] if source.startswith("---\n") else source
        expected = markdown.markdown(body, extensions=["tables", "fenced_code"])
        checks.append({"name": stem + " Markdown·HTML 본문 일치", "passed": expected in raw})
        checks.append({"name": stem + " HTML ID 중복", "passed": len(parser.ids) == len(set(parser.ids))})
        for link in parser.links:
            parsed = urlparse(link)
            if parsed.scheme or not parsed.path:
                continue
            target = (page.parent / unquote(parsed.path)).resolve()
            links.append({"source": page.name, "target": link, "exists": target.exists()})
        files.extend([md, page])
    checks.append({"name": "로컬 링크 목적지", "passed": all(link["exists"] for link in links), "checked": len(links), "failed": [link for link in links if not link["exists"]]})
    exposed, allowed_local_addresses = [], []
    files += list(BASE.glob("*.py")) + [BASE / "finalization-flow.html"]
    pattern = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])|https?://[^\s<>\"]*/webhooks/[^\s<>\"]+|sk-proj-[A-Za-z0-9_-]+")
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in pattern.finditer(line):
                token = match.group(0)
                try:
                    address = ipaddress.ip_address(token)
                except ValueError:
                    address = None
                # 사용자 규칙의 사설·루프백 예외만 적용한다. 파일 전체를 면제하지 않는다.
                local_ranges = ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
                if address and any(address in ipaddress.ip_network(net) for net in local_ranges):
                    allowed_local_addresses.append({"file": path.name, "line": number})
                    continue
                exposed.append({"file": path.name, "line": number})
    checks.append({"name": "산출물 접속값 패턴 검사", "passed": not exposed, "scope": [path.name for path in files], "findings_without_values": exposed, "allowed_private_loopback_occurrences": len(allowed_local_addresses), "limit": "IPv4·웹훅 경로·OpenAI 프로젝트 키 패턴 검사. 사용자 규칙의 RFC1918 사설·루프백은 허용. 모든 종류의 비밀값 탐지를 보장하지 않음"})
    script = Path("C:/Users/playdata2/.agents/skills/diagram-design/scripts/self_check.py")
    result = subprocess.run([sys.executable, "-B", str(script), str(BASE / "finalization-flow.html")], capture_output=True, text=True, encoding="utf-8")
    checks.append({"name": "그림 접근성·단일 파일 검사", "passed": result.returncode == 0, "command": "python -B <diagram-design>/scripts/self_check.py <integration>/finalization-flow.html", "stdout": result.stdout.strip(), "stderr": result.stderr.strip()})

    paths = ["datasets/README.md", "datasets/mobility/scripts/reduce_75.py", "datasets/dining/README.md", "datasets/activity/README.md"]
    ignored = []
    for name in paths:
        proc = subprocess.run(["git", "check-ignore", "--quiet", "--no-index", name], cwd=ROOT)
        ignored.append({"path": name, "ignored_by_current_rules": proc.returncode == 0, "exit_code": proc.returncode})
    tracked = subprocess.run(["git", "ls-files", "datasets"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    entries = tracked.stdout.splitlines()
    gitignore = ROOT / ".gitignore"
    conflict = {
        "id": "INT-W19-001", "w_id": "W19", "captured_at_kst": NOW.isoformat(),
        "contract": "W19: datasets 폴더 전체 Git 제외, 주변 스크립트·문서도 별도 검토 없이 공개하지 않음",
        "source": "datasets/wiki/index.md", "gitignore_sha256": hashlib.sha256(gitignore.read_bytes()).hexdigest(),
        "probes": ignored, "tracked_count": len(entries), "tracked_query_exit_code": tracked.returncode,
        "tracked_by_team": {key: sum(name.startswith("datasets/" + key + "/") for name in entries) for key in ["activity", "dining", "mobility"]},
        "tracked_paths": entries,
        "status": "requires_reconciliation" if not all(row["ignored_by_current_rules"] for row in ignored) or entries else "consistent",
        "changes_performed": "없음. 원본 자료·제외 규칙·Git 추적 상태 유지",
        "next_action": "최종 통합에서 현재 W19의 전체 제외 계약과 기존 팀 폴더 예외를 정합화. 이미 추적된 파일은 ignore 규칙만으로 빠지지 않으므로 기존 공유 작업과 충돌 없이 추적 상태를 별도 정리할 필요가 있음. 원본 데이터 삭제·Git 이력 재작성·커밋·푸시는 수행하지 않음",
    }
    save("w19-reconciliation.json", conflict)
    summary = {"captured_at_kst": NOW.isoformat(), "scope": "통합 준비 산출물만. 제품 기능·실환경 인수 시험 아님", "checks": checks, "passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks), "total": len(checks), "known_requirement_conflict": "INT-W19-001", "backup": BACKUP.relative_to(ROOT).as_posix() if BACKUP.exists() else "신규 생성"}
    save("preparation-checks.json", summary)
    print(json.dumps({"passed": summary["passed"], "failed": summary["failed"], "total": summary["total"], "local_links": len(links), "w19": {key: conflict[key] for key in ["status", "probes", "tracked_count", "tracked_by_team"]}}, ensure_ascii=False))
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())

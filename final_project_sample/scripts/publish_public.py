"""공개 저장소 배포 — 내부 문서·AI 협업 흔적을 걷어낸 `public` 브랜치를 만든다.

내부 `main` 은 RULE.md·CLAUDE.md·docs/ 를 그대로 갖는다.
공개 저장소에는 제품 코드와 README 만 올린다.

    python -m scripts.publish_public --dry-run     # 무엇이 올라갈지만 본다
    python -m scripts.publish_public               # public 브랜치 갱신
    python -m scripts.publish_public --push        # 갱신 후 origin/main 에 푸시

★이 스크립트가 있는 이유: 배포 때마다 손으로 걷어내면 언젠가 빠뜨린다.
  2026-08-12 최초 배포에서 `.gitignore` 에 파일명을 적었다가 그 자체가
  내부 파일 존재를 노출하는 것을 발견해 일반 패턴으로 바꿨다.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PUBLIC_BRANCH = "public"

#: 공개하지 않는 경로 (디렉터리 통째)
EXCLUDE_DIRS = ("docs", "legacy", ".agents", ".pytest_cache", ".claude")

#: 최상위 마크다운은 README 만 공개한다.
#: ★파일명을 나열하지 않는다 — 나열 자체가 내부 파일의 존재를 알린다.
ROOT_MD_ALLOW = {"README.md"}

#: 내부 도구라 공개하지 않는 개별 파일. ★이 스크립트 자신이 포함된다 —
#: 스크럽 패턴 문자열 때문에 자기 자신이 흔적 검사에 걸린다.
EXCLUDE_FILES = {"scripts/publish_public.py"}

#: 소스 주석의 내부 문서 참조를 중립 표현으로 바꾼다.
SCRUB = [
    (re.compile(r"CLAUDE\.md\s*(§[\d.\-]+)"), r"설계 원칙 \1"),
    (re.compile(r"CLAUDE\.md"), "설계 원칙"),
    (re.compile(r"RULE\.md\s*(§[\d.\-]+)"), r"작업 규칙 \1"),
    (re.compile(r"RULE\.md"), "작업 규칙"),
    (re.compile(r"docs/handoff/[^\s`)]+"), "설계 계약 문서"),
    (re.compile(r"docs/reports/debugs/[^\s`)]+"), "결함 리포트"),
    (re.compile(r"docs/reports/[^\s`)]+"), "작업 리포트"),
    (re.compile(r"docs/evidence/[^\s`)]+"), "검증 기록"),
    (re.compile(r"docs/plans/[^\s`)]+"), "실행계획서"),
    (re.compile(r"(?i)\bcodex\b"), "구현 담당"),
    (re.compile(r"(?i)\bclaude\b"), "검수 담당"),
    (re.compile(r"(?i)\banthropic\b"), ""),
]

SCRUB_SUFFIXES = {".py", ".yaml", ".yml", ".json", ".md", ".sql", ".txt"}


def run(*args: str, check: bool = True) -> str:
    # ★core.quotepath=false — 이게 없으면 한글 경로가 "docs/..." 처럼 따옴표로 감싸여
    #   경로 비교가 전부 어긋난다(2026-08-12: docs/ 51개가 제외되지 않고 통과했다).
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} 실패:\n{result.stderr}")
    return result.stdout


def publishable() -> list[str]:
    """공개 대상 파일 목록. 내부 문서와 무시 대상은 뺀다."""
    tracked = [p.strip('"') for p in run("ls-files").splitlines() if p]
    out = []
    for path in tracked:
        if path in EXCLUDE_FILES:
            continue
        head = path.split("/")[0]
        if head in EXCLUDE_DIRS:
            continue
        if "/" not in path and path.endswith(".md") and path not in ROOT_MD_ALLOW:
            continue
        out.append(path)
    return out


def scrub_text(text: str) -> str:
    for pattern, replacement in SCRUB:
        text = pattern.sub(replacement, text)
    return text


def audit(paths: list[str]) -> list[str]:
    """공개 직전 최종 검사 — 남아 있으면 안 되는 것."""
    problems = []
    secret = re.compile(r"sk-[A-Za-z0-9_\-]{20,}|AIza[A-Za-z0-9_\-]{30,}")
    trace = re.compile(r"(?i)claude|codex|anthropic")
    for path in paths:
        full = REPO / path
        if not full.is_file() or full.suffix not in SCRUB_SUFFIXES:
            continue
        text = full.read_text(encoding="utf-8", errors="ignore")
        if secret.search(text):
            problems.append(f"{path}: API 키로 보이는 문자열")
        if trace.search(scrub_text(text)):
            problems.append(f"{path}: 스크럽 후에도 AI 협업 흔적이 남는다")
    if ".env" in paths:
        problems.append(".env 가 공개 목록에 있다")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", action="store_true", help="origin/main 으로 푸시")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--message", default="A-COP: AI 연동형 고객운영 플랫폼")
    args = parser.parse_args()

    if run("status", "--porcelain").strip():
        print("작업 트리가 깨끗하지 않다. 커밋하거나 stash 한 뒤 다시 실행한다.")
        return 1

    source_branch = run("rev-parse", "--abbrev-ref", "HEAD").strip()
    paths = publishable()
    problems = audit(paths)

    print(f"소스 브랜치 : {source_branch}")
    print(f"공개 대상   : {len(paths)}개 파일")
    counts: dict[str, int] = {}
    for path in paths:
        head = path.split("/")[0] if "/" in path else path
        counts[head] = counts.get(head, 0) + 1
    for head, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {head:<20} {n}")
    print(f"제외        : {', '.join(EXCLUDE_DIRS)} + 최상위 md(README 제외)")

    if problems:
        print("\n★검사 실패 — 배포하지 않는다")
        for p in problems:
            print(f"  {p}")
        return 1
    print("\n검사 통과 — 키·AI 흔적 없음")

    if args.dry_run:
        return 0

    if not args.push:
        print("\n검사만 했다. 실제 배포는 --push 를 붙인다.")
        return 0

    return build_public(source_branch, paths, message=args.message)


def build_public(source_branch: str, paths: list[str], *, message: str) -> int:
    """공개 브랜치를 다시 만들어 origin/main 으로 보낸다.

    ★워킹 트리에 스크럽을 적용했다가 되돌린다. 중간에 죽으면 스크럽된 파일이 남으므로
      finally 에서 반드시 `checkout -f` 로 복구한다. 복구를 확인하고 끝낸다.
    """
    temp_branch = "_publish_tmp"
    run("branch", "-D", temp_branch, check=False)
    restored = False
    try:
        run("checkout", "--orphan", temp_branch)
        run("rm", "-r", "--cached", ".", "-q", check=False)

        scrubbed = 0
        for path in paths:
            full = REPO / path
            if not full.is_file():
                continue
            if full.suffix in SCRUB_SUFFIXES:
                text = full.read_text(encoding="utf-8", errors="ignore")
                cleaned = scrub_text(text)
                if cleaned != text:
                    full.write_text(cleaned, encoding="utf-8")
                    scrubbed += 1
            run("add", "-f", "--", path)

        print(f"\n스크럽 적용   : {scrubbed}개 파일")

        # ★커밋 identity 는 사용자 것을 쓴다. 협업 흔적을 남기지 않는다.
        run("commit", "-q", "-m", message)
        head = run("rev-parse", "--short", "HEAD").strip()
        print(f"공개 커밋     : {head}")

        run("push", "--force", "origin", f"{temp_branch}:main")
        print("푸시 완료     : origin/main")

        run("checkout", "-f", source_branch)
        restored = True
        run("branch", "-D", "public", check=False)
        run("branch", "-m", temp_branch, "public", check=False)
        run("branch", "-f", "public", head, check=False)
        return 0
    finally:
        if not restored:
            run("checkout", "-f", source_branch, check=False)
        dirty = run("status", "--porcelain", check=False).strip()
        if dirty:
            print("\n★워킹 트리가 깨끗하지 않다 — 스크럽이 남았을 수 있다:")
            print(dirty[:800])
        else:
            print(f"워킹 트리     : {source_branch} 복구 확인")


if __name__ == "__main__":
    sys.exit(main())

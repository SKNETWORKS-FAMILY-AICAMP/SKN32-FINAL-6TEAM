"""docs/ 통합 실행기 — 각 저장소의 `docs/` 를 `wiki/records/` 로 합친다 (2026-09-08).

    python program/scripts/merge_docs_apply.py              # dry-run
    python program/scripts/merge_docs_apply.py --apply      # zip 백업 → 링크 재계산 → 이동

★왜: 사용자 결정(2026-09-08). "기록"과 "현재 지식"의 구분은 필요하지만 폴더를
  둘로 나눌 이유는 없다. 한 트리 안에 `records/` 를 두면 진입점 하나·검사기
  하나가 되고, 압축·삭제도 된다.
  - 기록(evidence·reports 등)은 `wiki/records/<원래 하위폴더>/` 로 그대로 옮긴다.
    파일명(날짜 접두)은 그대로. 고치지 않는 것이 기록의 성질이다.
  - `check_wiki.py` 는 `records/` 를 기록 구역으로 다룬다 — front matter·크기·
    index 규칙을 적용하지 않고, 링크 깨짐은 위반이 아니라 집계로만 낸다.

무엇을 하나
  1. zip 백업 — `program/research/_backup/<날짜>_docs_통합전.zip` (git 무시 폴더).
     git 쪽 백업은 태그 `docs-pre-merge-<날짜>`.
  2. 링크 재계산 — 저장소 안 모든 .md 의 상대 링크·`resource:` 를 절대 경로로 풀어
     새 위치 기준으로 다시 계산 (`cutover_apply.rewrite_links` 재사용).
  3. 경로 문자열 치환 —
     `final_project_cs/docs/` → `final_project_cs/wiki/records/` (저장소 전체),
     cs·sample 안의 `docs/<하위>` → `wiki/records/<하위>`,
     파이썬 경로 상수 `"docs" / "…"` → `"wiki" / "records" / "…"`.
  4. 이동 — cs 는 루트 저장소에서 `git mv`, sample 은 자기 저장소에서 `git mv`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cutover_apply as base  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = base.ROOT
SOURCES = {
    "final_project_cs/docs": "final_project_cs/wiki/records",
    "final_project_sample/docs": "final_project_sample/wiki/records",
}
#: 자기 저장소에서 git mv 할 트리
OWN_REPO = {"final_project_sample/docs": "final_project_sample"}

SUBS = "evidence|reports|handoff|history|plans|vision|manuals|submission|TODO|labeling|screenshots|release_checklist"
BARE = re.compile(r"(?<![\w/.\-])docs/(" + SUBS + r")(?=[/`\s)\"'.,:]|$)")
PYPATH = re.compile(r'"docs"\s*/\s*"')
PYPREFIX = re.compile(r'\(\s*"docs/"')
SKIP_DIRS = base.SKIP_DIRS | {"legacy", "dist", "versions", ".tmp", "_codex_out"}
#: 코드는 **실제 경로 상수가 있는 파일만** 고친다. 주석의 docs/ 언급은 그대로 둔다 —
#: 100여 개 코드 파일의 주석을 건드리면 다른 세션과 충돌하고 얻는 게 없다.
PY_ALLOW = {
    "final_project_cs/scripts/verify_dod.py", "final_project_sample/scripts/verify_dod.py",
    "final_project_cs/scripts/check_release_gate.py", "final_project_cs/scripts/map_commits_to_phase.py",
    "final_project_cs/tests/unit/core/test_debug_report_status.py",
}
TEXT_EXT = base.TEXT_EXT | {".tsv"}


def walk_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            yield os.path.join(dirpath, f)


def build_map() -> dict[str, str]:
    m: dict[str, str] = {}
    for src, dst in SOURCES.items():
        s_abs = os.path.join(ROOT, src)
        if not os.path.isdir(s_abs):
            raise SystemExit(f"원본 트리가 없다: {src}")
        for f in walk_files(s_abs):
            inner = os.path.relpath(f, s_abs)
            m[os.path.normpath(f)] = os.path.normpath(os.path.join(ROOT, dst, inner))
    return m


def new_location(abs_path: str, mapping: dict[str, str]) -> str:
    n = os.path.normpath(abs_path)
    if n in mapping:
        return mapping[n]
    for src, dst in SOURCES.items():
        s_abs = os.path.normpath(os.path.join(ROOT, src))
        if n == s_abs:
            return os.path.normpath(os.path.join(ROOT, dst))
        if n.startswith(s_abs + os.sep):
            return os.path.normpath(os.path.join(ROOT, dst, os.path.relpath(n, s_abs)))
    return n


def rewrite_text(path: str, text: str) -> tuple[str, int]:
    rel = base.rel(path)
    n = 0
    for src, dst in SOURCES.items():
        text, k = re.subn(r"(?<![\w/.\-])" + re.escape(src) + r"/", dst + "/", text)
        n += k
    in_repo = rel.startswith(("final_project_cs/", "final_project_sample/"))
    if in_repo and (path.endswith(".md") or rel in PY_ALLOW):
        text, k = BARE.subn(r"wiki/records/\1", text); n += k
    if rel in PY_ALLOW:
        text, k = PYPATH.subn('"wiki" / "records" / "', text); n += k
        text, k = PYPREFIX.subn('("wiki/records/"', text); n += k
    return text, n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    os.chdir(ROOT)

    dirty = subprocess.run(["git", "status", "--porcelain", "--", "final_project_cs/docs"],
                           capture_output=True, text=True).stdout.strip()
    dirty_s = subprocess.run(["git", "-C", "final_project_sample", "status", "--porcelain", "--", "docs"],
                             capture_output=True, text=True).stdout.strip()
    if dirty or dirty_s:
        print("★docs/ 에 커밋 안 된 변경이 있다(다른 세션 작업 중). --apply 는 거부한다:\n" + dirty + "\n" + dirty_s)
        if args.apply:
            return 2
    for dst in SOURCES.values():
        if os.path.exists(os.path.join(ROOT, dst)):
            print(f"★목적지가 이미 있다: {dst}")
            return 2

    mapping = build_map()
    print(f"옮길 파일 {len(mapping)}개")

    # 링크·경로 재작성 대상: 저장소 안 텍스트 파일 전부
    base.new_location = new_location  # rewrite_links 가 이 매핑 규칙을 쓰게 한다
    self_paths = {os.path.normpath(os.path.abspath(__file__))}
    edits: dict[str, str] = {}
    touched: list[str] = []
    n_links = n_text = 0
    # 다른 세션이 수정 중인 파일은 건드리지 않는다
    dirty_files: set[str] = set()
    for repo in (".", "final_project_sample"):
        out = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            pth = line[3:].strip().strip('"')
            dirty_files.add(os.path.normpath(os.path.join(ROOT, repo, pth)))
    skipped_dirty: list[str] = []
    for f in walk_files(ROOT):
        if os.path.splitext(f)[1] not in TEXT_EXT or os.path.normpath(f) in self_paths:
            continue
        if os.path.normpath(f) in dirty_files:
            skipped_dirty.append(base.rel(f)); continue
        if f.endswith(".py") and base.rel(f) not in PY_ALLOW:
            continue
        if os.path.getsize(f) > 5_000_000:   # 거대 텍스트(로그·덤프)는 경로 언급 대상이 아니다
            continue
        try:
            raw = open(f, encoding="utf-8", newline="").read()
        except (UnicodeDecodeError, OSError):
            continue
        crlf = "\r\n" in raw
        text = raw.replace("\r\n", "\n")
        a = b = 0
        if f.endswith(".md"):
            text, a = base.rewrite_links(f, text, mapping)
        text, b = rewrite_text(f, text)
        if a or b:
            n_links += a; n_text += b
            touched.append(base.rel(f))
            edits[f] = text.replace("\n", "\r\n") if crlf else text
    outside = [t for t in touched if not any(t.startswith(s + "/") for s in SOURCES)]
    print(f"링크 재계산 {n_links}곳 · 경로 문자열 {n_text}곳 · 파일 {len(touched)}개 (docs 밖 {len(outside)}개)")
    for t in outside:
        if not t.endswith(".md") or t.startswith(("wiki/", "final_project_cs/wiki", "final_project_sample/wiki", "program/")):
            pass
    py = [t for t in outside if t.endswith(".py")]
    print("  파이썬 경로 상수:", ", ".join(py))
    if skipped_dirty:
        print("  건너뜀(남의 미커밋 파일):", ", ".join(skipped_dirty))

    if not args.apply:
        print("\n★dry-run 이다. 아무것도 안 바꿨다.")
        return 0

    stamp = dt.date.today().isoformat()
    bdir = os.path.join(ROOT, "program", "research", "_backup")
    os.makedirs(bdir, exist_ok=True)
    zpath = os.path.join(bdir, f"{stamp}_docs_통합전.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for src in SOURCES:
            for f in walk_files(os.path.join(ROOT, src)):
                z.write(f, base.rel(f))
    print(f"zip 백업: {base.rel(zpath)} ({os.path.getsize(zpath)//1024} KB)")

    for f, text in edits.items():
        open(f, "w", encoding="utf-8", newline="").write(text)
    print(f"재작성 {len(edits)}개 파일")

    for src, dst in SOURCES.items():
        os.makedirs(os.path.dirname(os.path.join(ROOT, dst)), exist_ok=True)
        if src in OWN_REPO:
            repo = OWN_REPO[src]
            subprocess.run(["git", "-C", repo, "mv", os.path.relpath(src, repo).replace("\\", "/"),
                            os.path.relpath(dst, repo).replace("\\", "/")], check=True)
            print(f"git mv (in {repo}): {src} → {dst}")
        else:
            subprocess.run(["git", "mv", src, dst], check=True)
            print(f"git mv: {src} → {dst}")
    open(os.path.join(bdir, "merge_docs_touched.txt"), "w", encoding="utf-8").write("\n".join(touched) + "\n")
    print("\n끝. 다음: check_wiki.py 규칙 갱신 → 검사 → 커밋(루트·sample)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

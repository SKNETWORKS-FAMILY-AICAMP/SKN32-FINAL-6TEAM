"""wiki 전환 실행기 — program/ 아래 시험 구축 wiki 를 각 저장소 안으로 옮긴다.

    python program/scripts/cutover_apply.py              # dry-run: 무엇이 바뀌는지만 센다
    python program/scripts/cutover_apply.py --apply      # 백업 → 링크 재계산 → 이동

★D-012 (2026-09-06): 놓을 자리는 `<저장소>/wiki/`. 전환은 사용자가 부를 때 한 번에.
★`cutover_rewrite.py` 는 계획만 냈다(2026-09-07 확인). 이 파일이 실행부다.

무엇을 하나
  1. 백업 — 다섯 트리를 `program/research/_backup/<날짜>_wiki_전환전/` 에 복사한다
     (그 폴더는 .gitignore 대상이다. git 쪽 백업은 태그로 남긴다).
  2. 링크 재계산 — 저장소 안의 모든 .md 에서 상대 링크(`](…)`)와 front matter 의
     `resource:` 를 **절대 경로로 풀어 새 위치 기준으로 다시 계산**한다. 옮겨지는
     문서를 가리키든, 옮겨지는 문서가 코드·원본을 가리키든 같은 규칙이다.
  3. 루트 기준 경로 문자열 치환 — `program/wiki/…` 처럼 적힌 텍스트(문서·스크립트·
     코드 주석)를 새 경로로 바꾼다. 긴 접두어부터.
  4. 이동 — 루트 저장소가 추적하는 넷은 `git mv`. sample wiki 는 sample 이 자체
     저장소라 루트 추적을 끊고(`git rm --cached`) 파일만 옮긴다. sample 커밋은 따로.

안 하는 것 — 커밋·태그·검사 실행. 스크립트가 끝난 뒤 사람이 검사기를 돌리고 커밋한다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

#: 지금 위치 → 전환 후 위치 (D-012 배치안 `wiki`)
SOURCES = {
    "program/wiki": "wiki",
    "program/final_project_cs/wiki": "final_project_cs/wiki",
    "program/final_project_sample/wiki": "final_project_sample/wiki",
    "program/datasets/wiki": "datasets/wiki",
    "program/acop_dojo/wiki": "acop_dojo/wiki",
}
#: 루트 저장소가 아니라 자기 저장소로 가는 트리
SEPARATE_REPO = {"program/final_project_sample/wiki"}

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pytest-tmp", ".pytest-basetemp",
             ".pytest-basetemp-final", ".pytest-tmp-all", ".pytest-tmp-run", ".pytest_cache",
             "_backup", "build", ".venv", "venv", ".acop_dojo"}
TEXT_EXT = {".md", ".py", ".json", ".yaml", ".yml", ".js", ".ts", ".txt", ".html", ".toml"}

LINK = re.compile(r"\]\(([^)\s]+)\)")
RESOURCE = re.compile(r"^(\s*resource:\s*)(\S+)\s*$", re.M)
EXTERNAL = ("http://", "https://", "mailto:", "#", "/", "\\")


def rel(p: str) -> str:
    return os.path.relpath(p, ROOT).replace("\\", "/")


def walk_files(base: str):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            yield os.path.join(dirpath, f)


def build_file_map() -> dict[str, str]:
    """옮겨지는 파일마다 old_abs → new_abs."""
    mapping: dict[str, str] = {}
    for src, dst in SOURCES.items():
        s_abs = os.path.join(ROOT, src)
        if not os.path.isdir(s_abs):
            raise SystemExit(f"원본 트리가 없다: {src}")
        for f in walk_files(s_abs):
            inner = os.path.relpath(f, s_abs)
            mapping[os.path.normpath(f)] = os.path.normpath(os.path.join(ROOT, dst, inner))
    return mapping


def new_location(abs_path: str, mapping: dict[str, str]) -> str:
    n = os.path.normpath(abs_path)
    if n in mapping:
        return mapping[n]
    # 디렉터리(또는 아직 없는 파일)라면 트리 접두어로 판정한다
    for src, dst in SOURCES.items():
        s_abs = os.path.normpath(os.path.join(ROOT, src))
        if n == s_abs or n.startswith(s_abs + os.sep):
            return os.path.normpath(os.path.join(ROOT, dst, os.path.relpath(n, s_abs))) if n != s_abs \
                else os.path.normpath(os.path.join(ROOT, dst))
    return n


def rewrite_links(path: str, text: str, mapping: dict[str, str]) -> tuple[str, int]:
    """상대 링크와 resource: 를 새 위치 기준으로 다시 계산한다."""
    old_dir = os.path.dirname(os.path.normpath(path))
    new_dir = os.path.dirname(new_location(path, mapping))
    changed = 0

    def fix(target: str) -> str:
        nonlocal changed
        if target.startswith(EXTERNAL) or re.match(r"^[a-zA-Z]:", target):
            return target
        body, sep, anchor = target.partition("#")
        if not body:
            return target
        abs_old = os.path.normpath(os.path.join(old_dir, body))
        # 존재하지 않는 대상(미작성 문서)도 트리 접두어로 옮겨 준다
        abs_new = new_location(abs_old, mapping)
        new_rel = os.path.relpath(abs_new, new_dir).replace("\\", "/")
        if body.endswith("/") and not new_rel.endswith("/"):
            new_rel += "/"
        if new_rel == body:
            return target
        changed += 1
        return new_rel + sep + anchor

    text = LINK.sub(lambda m: "](" + fix(m.group(1)) + ")", text)
    text = RESOURCE.sub(lambda m: m.group(1) + fix(m.group(2)), text)
    return text, changed


#: 루트 기준 경로 문자열. 긴 것부터 바꿔야 `program/wiki` 가 먼저 먹지 않는다.
PREFIXES = sorted(SOURCES.items(), key=lambda kv: -len(kv[0]))


def rewrite_prefixes(text: str) -> tuple[str, int]:
    n = 0
    for old, new in PREFIXES:
        # 앞에 경로 문자가 더 붙어 있으면(예: ../program/wiki) 상대 링크라 위에서 처리됐다.
        pat = re.compile(r"(?<![\w/.\-])" + re.escape(old) + r"(?=/|`|\s|\)|\"|'|$|:|,|\.)")
        text, k = pat.subn(new, text)
        n += k
    return text, n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제로 바꾼다. 없으면 dry-run")
    args = ap.parse_args()
    os.chdir(ROOT)

    # 전제 — 원본 트리가 깨끗해야 한다(남의 편집 중 작업을 덮지 않는다)
    dirty = subprocess.run(["git", "status", "--porcelain", "--", *SOURCES],
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        print("★원본 트리에 커밋 안 된 변경이 있다. 먼저 정리한다:\n" + dirty)
        return 2
    for dst in SOURCES.values():
        if os.path.exists(os.path.join(ROOT, dst)):
            print(f"★목적지가 이미 있다: {dst}")
            return 2

    mapping = build_file_map()
    print(f"옮길 파일 {len(mapping)}개")

    # 대상 파일 — 저장소 안의 텍스트 파일 전부(백업·캐시 제외)
    self_path = os.path.normpath(os.path.abspath(__file__))
    targets = [f for f in walk_files(ROOT)
               if os.path.splitext(f)[1] in TEXT_EXT and os.path.normpath(f) != self_path]

    link_total = prefix_total = 0
    touched: list[str] = []
    edits: dict[str, str] = {}
    for f in targets:
        try:
            raw = open(f, encoding="utf-8", newline="").read()
        except (UnicodeDecodeError, OSError):
            continue
        crlf = "\r\n" in raw
        text = raw.replace("\r\n", "\n")
        n_links = 0
        if f.endswith(".md"):
            text, n_links = rewrite_links(f, text, mapping)
        text, n_pref = rewrite_prefixes(text)
        if n_links or n_pref:
            link_total += n_links
            prefix_total += n_pref
            touched.append(rel(f))
            edits[f] = text.replace("\n", "\r\n") if crlf else text

    print(f"링크 재계산 {link_total}곳 · 경로 문자열 치환 {prefix_total}곳 · 파일 {len(touched)}개")
    outside = [t for t in touched if not any(t.startswith(s + "/") for s in SOURCES)]
    print(f"  그중 wiki 트리 밖 파일 {len(outside)}개:")
    for t in outside:
        print("    " + t)

    if not args.apply:
        print("\n★dry-run 이다. 아무것도 안 바꿨다. --apply 로 실행한다.")
        return 0

    # 1. 백업
    stamp = dt.date.today().isoformat()
    bdir = os.path.join(ROOT, "program", "research", "_backup", f"{stamp}_wiki_전환전")
    os.makedirs(bdir, exist_ok=True)
    for src in SOURCES:
        shutil.copytree(os.path.join(ROOT, src), os.path.join(bdir, src.replace("/", "__")),
                        dirs_exist_ok=True)
    print(f"백업: {rel(bdir)}")

    # 2·3. 내용 재작성 (아직 옛 위치에서)
    for f, text in edits.items():
        open(f, "w", encoding="utf-8", newline="").write(text)
    print(f"재작성 {len(edits)}개 파일")

    # 4. 이동
    for src, dst in SOURCES.items():
        os.makedirs(os.path.dirname(os.path.join(ROOT, dst)) or ROOT, exist_ok=True)
        if src in SEPARATE_REPO:
            subprocess.run(["git", "rm", "-r", "--cached", "--quiet", src], check=True)
            shutil.move(os.path.join(ROOT, src), os.path.join(ROOT, dst))
            print(f"이동(루트 추적 해제): {src} → {dst}")
        else:
            subprocess.run(["git", "mv", src, dst], check=True)
            print(f"git mv: {src} → {dst}")
    # 비어 남은 program/<repo>/ 폴더 정리
    for src in SOURCES:
        parent = os.path.dirname(os.path.join(ROOT, src))
        if os.path.isdir(parent) and rel(parent) != "program" and not os.listdir(parent):
            os.rmdir(parent)

    open(os.path.join(ROOT, "program", "research", "_backup", "cutover_touched.txt"), "w",
         encoding="utf-8").write("\n".join(touched) + "\n")
    print("\n끝. 다음: python program/scripts/check_wiki.py → 커밋(루트) → sample 저장소 커밋")
    return 0


if __name__ == "__main__":
    sys.exit(main())

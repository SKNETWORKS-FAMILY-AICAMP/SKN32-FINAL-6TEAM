"""문서 드리프트 검사기.

기준선 문서의 개정이 **일부 절에만 반영되어 다른 절이 옛말을 유지하는** 상태를
찾는다. 2026-09-01 VOC 사고가 그 모양이었다 — v7.1 결정이 §7-A 에는 갔는데
§3-A 에는 안 갔고, 하필 `CLAUDE.md` 가 인용한 쪽이 §3-A 였다. 경위는
`program/research/2026-09-01_VOC가_팀모듈로_흘러간_경위.md`.

    python program/scripts/check_drift.py            # 전체
    python program/scripts/check_drift.py --only 1   # 한 검사만

종료 코드 0 = 확인할 것 없음, 1 = 사람이 볼 것 있음.

★이 도구는 **모순 후보를 찾아 줄 뿐 어느 쪽이 맞는지 판정하지 않는다.**
  v6/v7/v7.1 개정 기록을 읽고 "v7 이 뒤집은 근거가 없다" 를 찾는 일은 사람 몫이다.

★아직 안 보는 것: `v8 ↔ program/wiki/` 대조. wiki 이관이 진행 중이라
  (`program/wiki/governance/migration-scope.md`, 747건 중 202건 이관 대상)
  대상이 확정된 뒤에 검사 4로 붙인다. 이관이 끝나면 v8 과 wiki 페이지가 같은
  내용을 두 벌 갖게 되므로, 이번과 똑같은 드리프트 면이 새로 생긴다.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASELINE = "program/plan/A-COP_구현계획서_v9.md"

#: 기준선을 인용하는 규칙 문서. ★여기 실린 문장은 매 세션 컨텍스트에 자동으로
#:  실리므로 기준선 본문보다 강하게 작용한다. 기준선을 고칠 때 이 파일들이 그
#:  부분을 인용하고 있는지 반드시 확인해야 한다 — 2026-09-01 사고의 교훈이다.
CLAUDE_MDS = [
    "CLAUDE.md",
    "final_project_cs/CLAUDE.md",
    "final_project_sample/CLAUDE.md",
    "acop_dojo/CLAUDE.md",
]

#: 코드로 확인해야 하는 주장. ★문자열 검색은 주석과 docstring 에 낚인다 —
#:  2026-09-01 에 `require_module("voc")` 가 남아 있는 줄 알았으나 주석이었다.
#:  그래서 AST 로 실제 호출만 센다.
CODE_CLAIMS = [
    {
        "root": "final_project_cs/app",
        "call": "require_module",
        "arg0": "voc",
        "expect": 0,
        "why": "인라인 분류와 집계 배치는 코어 1 소유이며 voc 플래그에 묶이지 않는다 (v9 §3-A·§7-A)",
    },
    {
        "root": "final_project_cs/app",
        "call": "run_case",
        "arg0": None,
        "expect": None,
        "why": "2026-09-03 에 접수 응답 뒤로 분리됐다(v9 §3-A). 지금 기대되는 호출처는 셋 — "
               "controller 내부 resume, 접수 라우트(응답 뒤 detached), routing_sweeper(되잡기). "
               "sweeper 가 사라지면 routing 잔류 Case 를 아무도 안 집는다",
    },
]

MARK_RE = re.compile(r"\[(v\d+(?:\.\d+)?)\]")
HEAD_RE = re.compile(r"^#{2,3}\s*(.+)$")


# ── 공통 ──────────────────────────────────────────────────────────────
def read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def sections(text: str) -> list[tuple[int, str]]:
    """(줄번호, 절 제목) 목록. 줄번호로 어느 절인지 되짚는 데 쓴다."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        m = HEAD_RE.match(line)
        if m:
            out.append((i, m.group(1).strip()))
    return out


def section_of(secs: list[tuple[int, str]], lineno: int) -> str:
    cur = "(머리말)"
    for ln, title in secs:
        if ln > lineno:
            break
        cur = title
    return cur


# ── 검사 1. 개정 표 반대진술 스윕 ──────────────────────────────────────
#: §0 안에서도 개정 표만 본다. 문서 전체 표를 긁으면 상태표의 "완료"·"취소"
#:  같은 흔한 낱말이 항목으로 잡혀 결과가 못 쓰게 된다.
REVISION_HEADER = "항목"


def parse_revision_items(text: str) -> list[dict]:
    """§0 의 개정 표에서 항목과 검색어를 뽑는다.

    표 모양: | 항목 | 이전 | 이후 | 이유 |
    검색어는 '이후' 칸의 굵은 글씨·백틱·따옴표 안 어구를 쓴다. 그게 그 개정이
    실제로 바꾼 말이기 때문이다.

    §0 은 문서 처음부터 `## 0-1` 또는 `## 1.` 직전까지다. 개정 기록이 거기
    모여 있고, 뒤쪽 표는 개정이 아니라 명세라 대상이 아니다.
    """
    lines = text.splitlines()
    end = len(lines)
    for i, line in enumerate(lines):
        if re.match(r"^##\s*(0-1|1)\.", line):
            end = i
            break

    items, in_revision_table = [], False
    for line in lines[:end]:
        if not line.startswith("|"):
            in_revision_table = False
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == REVISION_HEADER:
            in_revision_table = True
            continue
        if not in_revision_table:
            continue
        if len(cells) < 3 or set("".join(cells)) <= {"-", ":", " "}:
            continue
        items.append({"name": cells[0], "terms": key_terms(cells[2])})
    return [it for it in items if it["terms"]]


#: 너무 흔해서 검색어로 못 쓰는 것. 경로·일반 낱말은 문서 곳곳에 나와
#:  결과를 잡음으로 채운다.
TOO_COMMON = re.compile(r"^(app/|program/|final_project|Core|Team|Registry|Case)\b", re.I)


def key_terms(cell: str) -> list[str]:
    """개정 표 '이후' 칸에서 검색어를 뽑는다.

    ★굵은 글씨·백틱·따옴표를 먼저 쓴다. 그게 그 개정이 실제로 바꾼 말이다.
      다만 v7→v7.1 표처럼 표시 없이 평문으로만 쓴 표가 있어서, 없으면
      구두점으로 끊어 긴 조각을 쓴다. 이 폴백이 없으면 정작 중요한 개정이
      통째로 안 잡힌다 — 2026-09-01 VOC 건이 그 표에 있었다.
    """
    marked = re.findall(r"\*\*(.+?)\*\*|`(.+?)`|\"(.+?)\"", cell)
    flat = [t.strip() for g in marked for t in g if t and len(t.strip()) >= 4]
    if not flat:
        plain = re.sub(r"[*`\"]", "", cell)
        chunks = [c.strip(" .·,") for c in re.split(r"[.·,、]|\s—\s", plain)]
        flat = sorted((c for c in chunks if 6 <= len(c) <= 40), key=len, reverse=True)
    return [t for t in flat if not TOO_COMMON.match(t)][:3]


#: 도표 선. ASCII 상자 안의 글자는 주장이 아니다.
BOXCHARS = set("│┌└├─┐┘┬┴┼╭╮╰╯▲▼◄►")


def noise_lines(lines: list[str]) -> set[int]:
    """검사에서 뺄 줄. ★2026-09-06 실측 — 이걸 안 빼면 오탐이 5건 나온다.

    셋 다 "주장" 이 아니라서 대조 대상이 아니다.
      1. 코드 펜스 안        — 예시·출력이지 서술이 아니다
      2. ASCII 도표 선       — `│ Agent Card → Task │` 가 §7-B 에서 잡혔다
      3. 개정 기록 표의 행    — 표가 자기 자신을 모순으로 잡는다(§7 309행)
    """
    skip: set[int] = set()
    in_fence = False
    header_is_revision = False
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            skip.add(i)
            continue
        if in_fence:
            skip.add(i)
            continue
        if any(ch in BOXCHARS for ch in line):
            skip.add(i)
            continue
        if s.startswith("|"):
            # ★머리글 첫 칸이 '항목'이면 개정 기록 표다 — `parse_revision_items` 가
            #   항목을 뽑는 바로 그 표이므로, 그 표의 행을 다시 모순으로 세면 안 된다.
            #   머리글에 판올림 표기(v8 등)가 없는 표도 있어서 그것만으로는 못 거른다.
            if "---" not in s:
                cells = [c.strip() for c in s.strip("|").split("|")]
                if cells and cells[0] == REVISION_HEADER:
                    header_is_revision = True
            if header_is_revision:
                skip.add(i)
        else:
            header_is_revision = False
    return skip


def check_revisions(text: str) -> int:
    secs = sections(text)
    items = parse_revision_items(text)
    lines = text.splitlines()
    noise = noise_lines(lines)
    print(f"[1] 개정 표 반대진술 스윕 — 항목 {len(items)}건")
    if not items:
        print("    표를 못 찾았다. 기준선의 §0 표 모양이 바뀌었는지 확인한다.")
        return 1

    flagged = 0
    for it in items:
        # ★한 검색어가 너무 많은 줄에 걸리면 그 말은 이 문서의 일상어라
        #   드리프트 신호가 못 된다. 세어 보고 버린다.
        usable = []
        for t in it["terms"]:
            if sum(1 for line in lines if t in line) <= 12:
                usable.append(t)
        if not usable:
            print(f"    {it['name'][:22]:<24} 검색어가 전부 흔한 말이라 건너뛴다")
            continue

        marked, unmarked = [], []
        for i, line in enumerate(lines, 1):
            if i in noise:
                continue
            if line.startswith("|") and it["name"] in line:
                continue  # 개정 표 자기 자신
            if not any(t in line for t in usable):
                continue
            (marked if MARK_RE.search(line) else unmarked).append(i)
        status = "OK"
        if unmarked:
            status = "★확인"
            flagged += 1
        name = it["name"][:22]
        print(f"    {name:<24} 표시있음 {len(marked):>2}곳   표시없음 {len(unmarked):>2}곳   {status}")
        for ln in unmarked[:3]:
            print(f"        {ln:>5}행  {section_of(secs, ln)[:44]}")
        if len(unmarked) > 3:
            print(f"        … 외 {len(unmarked) - 3}곳")
    print()
    print("    ★'표시없음'은 곧 모순이 아니다. 개정 표시가 안 붙은 채 같은 말을")
    print("      하는 자리이며, 그중 옛말을 유지한 절이 있는지는 사람이 읽어 판정한다.")
    return flagged


# ── 검사 2. CLAUDE.md 인용 추적 ────────────────────────────────────────
#: 경로·명령어·식별자는 두 문서에 같이 나와도 인용이 아니다. 찾는 것은
#:  **주장을 담은 문장**이다 — 그런 문장이 기준선에서 정정되면 CLAUDE.md 도
#:  같이 고쳐야 하는데, 경로가 같은 것은 고칠 일이 아니다.
def is_claim(frag: str) -> bool:
    if not re.search(r"[가-힣]", frag):
        return False
    if re.search(r"[/\\]|--|::|\bpython\b|\.py\b|\.md\b|\.jsonl\b", frag):
        return False
    return True


def check_claude_quotes(text: str) -> int:
    secs = sections(text)
    lines = text.splitlines()
    print("[2] CLAUDE.md 인용 대조")
    hits = 0
    for path in CLAUDE_MDS:
        if not os.path.exists(path):
            continue
        for i, line in enumerate(read(path).splitlines(), 1):
            for frag in re.split(r"[.。]\s*", line.strip()):
                frag = frag.strip(" -*`|")
                if len(frag) < 14 or not is_claim(frag):
                    continue
                for j, bl in enumerate(lines, 1):
                    if frag in bl:
                        print(f"    {path}:{i}")
                        print(f"        \"{frag[:56]}\"")
                        print(f"        → 기준선 {j}행 · {section_of(secs, j)[:44]}")
                        hits += 1
                        break
    if not hits:
        print("    기준선 문장을 그대로 인용한 곳이 없다.")
    else:
        print()
        print("    ★기준선의 해당 절을 고치면 위 CLAUDE.md 도 같이 고친다.")
        print("      매 세션 자동으로 실리는 문서라 기준선보다 강하게 작용한다.")
    return 0


# ── 검사 3. 코드 대조 (AST) ────────────────────────────────────────────
def find_calls(root: str, name: str, arg0: str | None) -> list[tuple[str, int]]:
    found = []
    for dirpath, _dirs, files in os.walk(root):
        if "__pycache__" in dirpath:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                tree = ast.parse(read(p))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fname = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if fname != name:
                    continue
                if arg0 is not None:
                    if not node.args:
                        continue
                    a = node.args[0]
                    if not (isinstance(a, ast.Constant) and a.value == arg0):
                        continue
                found.append((p.replace("\\", "/"), node.lineno))
    return sorted(found)


def check_code(_text: str) -> int:
    print("[3] 코드 대조 (AST — 주석·docstring 은 세지 않는다)")
    bad = 0
    for c in CODE_CLAIMS:
        if not os.path.isdir(c["root"]):
            print(f"    {c['root']} 없음. 건너뛴다.")
            continue
        calls = find_calls(c["root"], c["call"], c["arg0"])
        label = f"{c['call']}({c['arg0']!r})" if c["arg0"] else f"{c['call']}()"
        if c["expect"] is None:
            print(f"    {label:<32} 호출 {len(calls)}곳")
        else:
            ok = len(calls) == c["expect"]
            print(f"    {label:<32} 호출 {len(calls)}곳 (기대 {c['expect']})  {'OK' if ok else '★불일치'}")
            if not ok:
                bad += 1
        for p, ln in calls[:4]:
            print(f"        {p}:{ln}")
        if len(calls) > 4:
            print(f"        … 외 {len(calls) - 4}곳")
        print(f"        └ {c['why']}")
    return bad


# ── 실행 ──────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int, choices=[1, 2, 3], help="한 검사만 돌린다")
    args = ap.parse_args()

    if not os.path.exists(BASELINE):
        print(f"기준선이 없다: {BASELINE}")
        print("저장소 루트에서 실행한다.")
        return 1

    text = read(BASELINE)
    print(f"기준선: {BASELINE}")
    print()

    checks = {1: check_revisions, 2: check_claude_quotes, 3: check_code}
    todo = [args.only] if args.only else [1, 2, 3]
    total = 0
    for n in todo:
        total += checks[n](text)
        print()

    print("─" * 62)
    if total:
        print(f"사람이 볼 것 {total}건. 위 ★표시를 확인한다.")
        print("판정 절차는 program/research/index.md 문서 정합성 점검 캘린더 항목 4.")
    else:
        print("확인할 것 없음.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())

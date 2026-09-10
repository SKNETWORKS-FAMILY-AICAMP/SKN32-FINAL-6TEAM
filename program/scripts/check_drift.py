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

★검사 5 를 왜 넣었나 (2026-09-07). 검사 1~4 는 **개정이 안 퍼진 자리**를 찾는다.
  그런데 2026-09-07 에 실제로 낡아 있던 둘은 그 종류가 아니었다:

      §8-D "cs에는 옛 v2를 복사한 자체 구현이 남아 있어 제거 대상이다"
      §0   "결함 2가 절반만 고쳐졌다" · "중간발표(9/15) 이후로 미룬다"

  **일이 끝나면 저절로 낡는 서술**이고, 검사 1~4 는 하나도 못 잡았다. 개정 표에
  대응 항목이 없고 CLAUDE.md 가 인용하지도 않기 때문이다. 계획서는 범위·결정·
  일정을 적는 문서라 이런 문장이 구조적으로 많이 생긴다.

  검사 5 는 그 문장들을 모아 보여 준다. **낡았다고 판정하지 않는다** — 코드에
  대고 확인하는 것은 사람 몫이다. 검사 1 과 같은 성격이다.

★아직 안 보는 것: `v8 ↔ wiki/` 대조. wiki 이관이 진행 중이라
  (`wiki/governance/migration-scope.md`, 747건 중 202건 이관 대상)
  대상이 확정된 뒤에 검사 4로 붙인다. 이관이 끝나면 v8 과 wiki 페이지가 같은
  내용을 두 벌 갖게 되므로, 이번과 똑같은 드리프트 면이 새로 생긴다.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: ★2026-09-10 판올림으로 **v11 이 기준선이다.** 검사기가 옛 판을 읽고 있으면
#:  낡은 문서를 지키게 된다 — 있는 것보다 나쁘다.
#:  v9·v10 은 아직 `program/plan/` 에 남아 있지만 기준선이 아니다.
#:  (2026-09-08 에는 v10 이었다. 도메인 교체 판이었고, v11 은 그 위에 여행 전환
#:   결정을 올린 판이다.)
BASELINE = "program/plan/A-COP_구현계획서_v11.md"

#: 판정 원장. 검사 1·5 는 **후보**를 모을 뿐이라 매번 같은 줄이 다시 올라온다.
#:  2026-09-07 에 13건을 코드에 대고 판정했는데, 그 13건이 다음 세션에 그대로
#:  또 올라오면 사람은 두 번째부터 안 읽는다 — 경보가 많으면 경보가 아니다.
#:  판정한 것은 여기 적어 두고 요약만 보여 준다.
#:
#:  ★지문에 **줄 번호를 넣지 않는다.** 위에 문단이 하나 끼면 줄이 다 밀리는데
#:    그때마다 전부 다시 판정하게 된다. 대신 절 제목과 문장 자체로 만든다 —
#:    **문장이 바뀌면 지문도 바뀌어 다시 올라온다.** 그게 맞는 동작이다.
#:    낡은 문장을 살짝 고쳐 놓고 "판정했다" 로 덮는 것을 막는다.
LEDGER = "program/research/_드리프트_판정.jsonl"


def _today() -> str:
    import datetime
    return datetime.date.today().isoformat()


def fingerprint(check: int, section: str, fragment: str) -> str:
    """검사 번호 · 절 제목 · 문장으로 만든 지문. 줄 번호는 일부러 뺀다."""
    norm = re.sub(r"\s+", " ", fragment).strip()
    return hashlib.sha1(f"{check} | {section.strip()} | {norm}".encode("utf-8")).hexdigest()[:12]


def load_ledger() -> dict[str, dict]:
    if not os.path.exists(LEDGER):
        return {}
    rows = {}
    for line in Path(LEDGER).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["지문"]] = row
    return rows


def append_ledger(rows: list[dict]) -> None:
    with open(LEDGER, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + NEWLINE)


NEWLINE = chr(10)

#: 검사 1·5 가 이번 실행에서 모은 후보. main 이 원장과 대조해 요약한다.
CANDIDATES: list[dict] = []


def note(check: int, section: str, lineno: int, fragment: str) -> bool:
    """후보를 기록하고 **아직 판정 안 된 것인지** 돌려준다."""
    fp = fingerprint(check, section, fragment)
    CANDIDATES.append({"지문": fp, "검사": check, "절": section, "행": lineno, "본문": fragment})
    return fp not in LEDGER_ROWS


LEDGER_ROWS: dict[str, dict] = {}

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
#:
#: ★★AST 로도 못 잡는 것이 있다 (2026-09-07 실측). "LLM 호출이 트랜잭션 안에
#:  있나" 는 정적으로 판정할 수 없다 — `await` 가 `with connection_factory()`
#:  안에 있어도 그 순간 트랜잭션이 열려 있다는 뜻은 아니다. **커넥션을 쥔 것과
#:  트랜잭션을 쥔 것은 다르다.** 실제로 `Controller.run_case()` 는 단계마다
#:  명시적으로 커밋해 Team 실행을 트랜잭션 밖에 둔다. 실행 중에 프로브로
#:  `conn.info.transaction_status`(IDLE) 와 `pg_locks`(0) 를 읽어야 판정된다.
#:  **이 검사기는 호출처를 세어 줄 뿐 실행 시점의 상태를 재지 않는다.**
#:  그런 주장은 여기 넣지 말고 런타임 프로브로 재고 리포트에 남긴다.
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

    넷 다 "주장" 이 아니라서 대조 대상이 아니다.
      1. 코드 펜스 안        — 예시·출력이지 서술이 아니다
      2. ASCII 도표 선       — `│ Agent Card → Task │` 가 §7-B 에서 잡혔다
      3. 개정 기록 표의 행    — 표가 자기 자신을 모순으로 잡는다(§7 309행)
      4. §0 전체            — 아래

    ★**§0 은 통째로 뺀다** (2026-09-07 추가). `parse_revision_items` 가 항목을
      뽑는 곳이 바로 §0 이라, 거기 적힌 글은 **개정 기록 자신**이지 본문의
      반대 진술이 아니다. 표만 빼는 것으로는 모자랐다 — 2026-09-07 에 §0 의
      「남은 것 둘」 문단을 「해소됨」 으로 고쳐 쓰자 확인 대상이 7 → 15건으로
      뛰었다. 정정문을 길게 쓸수록 자기 항목에 더 걸리는 구조였다.
      찾으려는 것은 **본문이 옛말을 유지하는 자리**다.
    """
    skip: set[int] = set()

    # §0 = 문서 처음부터 `## 0-1` 또는 `## 1.` 직전까지
    for i, line in enumerate(lines, 1):
        if re.match(r"^##\s*(0-1|1)\.", line):
            skip.update(range(1, i))
            break
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
        # ★원장에 판정이 있는 줄은 세지 않는다. 같은 줄이 매번 다시 올라오면
        #   사람은 두 번째부터 안 읽는다.
        fresh = [ln for ln in unmarked
                 if note(1, section_of(secs, ln), ln, lines[ln - 1].strip()[:120])]
        settled = len(unmarked) - len(fresh)
        status = "OK"
        if fresh:
            status = "★확인"
            flagged += len(fresh)
        elif settled:
            status = f"판정됨 {settled}"
        name = it["name"][:22]
        print(f"    {name:<24} 표시있음 {len(marked):>2}곳   표시없음 {len(unmarked):>2}곳   {status}")
        for ln in fresh[:3]:
            print(f"        {ln:>5}행  {section_of(secs, ln)[:44]}")
        if len(fresh) > 3:
            print(f"        … 외 {len(fresh) - 3}곳")
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


#: 「현재 기준 사실」 표를 두는 두 곳. 루트 `CLAUDE.md` 가 "이 표가 오래됐으면
#:  research/index.md 가 정본" 이라 가리키므로 **둘은 같이 갱신해야 한다.**
#:  ★2026-09-06 실측 — 실제로 어긋나 있었다. Composer 행 하나가 루트에만 있었고
#:    DoD 행의 "evidence 9건 낡음" 이 research 에만 빠져 있었다. 규칙을 글로만
#:    적어 두면 이렇게 된다.
FACT_TABLES = ("CLAUDE.md", "program/research/index.md")

#: 같은 파일을 다른 깊이에서 가리키는 것은 차이가 아니다.
PATH_ALIASES = ((r"\.\./plan/", "program/plan/"), (r"\.\./wiki/", "wiki/"))


def _fact_rows(path: str) -> dict[str, str]:
    lines = read(path).splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip().startswith("| 사실")), None)
    if start is None:
        return {}
    out: dict[str, str] = {}
    for line in lines[start:]:
        if not line.startswith("|"):
            if out:
                break
            continue
        if "---" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] == "사실":
            continue
        key = re.sub(r"[*`]", "", cells[0])
        val = re.sub(r"[*`]", "", cells[1])
        for pat, rep in PATH_ALIASES:
            val = re.sub(pat, rep, val)
        out[key] = val
    return out


def check_fact_tables(_text: str) -> int:
    print("[4] 「현재 기준 사실」 표 대조 — 루트 CLAUDE.md ↔ research/index.md")
    tables = {p: _fact_rows(p) for p in FACT_TABLES}
    for p, rows in tables.items():
        if not rows:
            print(f"    {p} 에서 표를 못 찾았다 (머리글 '| 사실' 확인)")
            return 1
    a, b = (tables[p] for p in FACT_TABLES)
    print(f"    {FACT_TABLES[0]} {len(a)}행 · {FACT_TABLES[1]} {len(b)}행")

    bad = 0
    for key in a.keys() - b.keys():
        print(f"    ★{FACT_TABLES[1]} 에 없다: {key}")
        bad += 1
    for key in b.keys() - a.keys():
        print(f"    ★{FACT_TABLES[0]} 에 없다: {key}")
        bad += 1
    for key in sorted(a.keys() & b.keys()):
        if a[key] != b[key]:
            print(f"    ★값이 다르다: {key}")
            print(f"        루트     {a[key][:96]}")
            print(f"        research {b[key][:96]}")
            bad += 1
    if not bad:
        print("    일치. 행·값 모두 같다")
    return bad


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


# ── 검사 5. 진행상태 서술 ─────────────────────────────────────────────

#: "이 일은 아직 안 끝났다" 고 말하는 표현. ★일이 끝나면 이 문장이 낡는다.
#:  넓게 잡지 않는다 — 후보가 수십 건이면 아무도 안 읽는다.
PROGRESS_CLAIMS = (
    "제거 대상", "남아 있어", "남아 있다", "미룬다", "미뤘다",
    "아직 없다", "아직 안", "미착수", "절반만", "몫이다", "몫으로",
    "예정이다", "착수 전", "하지 않았다", "구현이 없다",
)


def check_progress_claims(text: str) -> int:
    """기준선이 "아직 안 끝났다" 고 말하는 자리를 모은다.

    ★판정하지 않는다. 코드에 대고 확인하는 것은 사람 몫이다 — 이 도구는
      **어디를 볼지**를 좁혀 줄 뿐이다(검사 1 과 같다).
    """
    print("[5] 진행상태 서술 스윕 — 일이 끝나면 낡는 문장")
    lines = text.splitlines()
    secs = sections(text)
    noise = noise_lines(lines)

    hits: list[tuple[int, str, str]] = []
    for i, line in enumerate(lines, start=1):
        if i in noise or not line.strip():
            continue
        for claim in PROGRESS_CLAIMS:
            if claim in line:
                # 문장 하나만 보여 준다 — 표 한 줄이 통째로 나오면 못 읽는다
                frag = next((s for s in re.split(r"(?<=[.다])\s+", line) if claim in s), line)
                hits.append((i, section_of(secs, i), frag.strip()[:120]))
                break

    settled = sum(1 for lineno, sec, frag in hits if not note(5, sec, lineno, frag))
    hits = [h for h in hits if fingerprint(5, h[1], h[2]) not in LEDGER_ROWS]

    if not hits:
        print(f"    새로 볼 것 없음." + (f" (판정됨 {settled}줄)" if settled else ""))
        return 0

    by_section: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for lineno, sec, frag in hits:
        by_section[sec].append((lineno, frag))
    for sec in sorted(by_section, key=lambda s: by_section[s][0][0]):
        print(f"    ★{sec}")
        for lineno, frag in by_section[sec][:3]:
            print(f"        {lineno:>5}행  {frag}")
        if len(by_section[sec]) > 3:
            print(f"              … 외 {len(by_section[sec]) - 3}줄")
    print()
    print(f"    ★{len(hits)}줄" + (f" (판정됨 {settled}줄은 감췄다)" if settled else "")
          + ". **낡았다는 뜻이 아니다** — 아직 그런지 코드에 대고 확인한다.")
    print("      2026-09-07 에 이 방식으로 §8-D·§0 의 낡은 서술 셋을 찾았다")
    print("      (final_project_cs/wiki/records/reports/2026-09-07_v9_8D_문구_정정_제안.md).")
    return len(hits)



# ── 검사 6. DB 제약 대조 ───────────────────────────────────────────────

#: wiki 가 DDL 을 스니펫으로 베껴 싣는다. 스키마가 바뀌면 그 스니펫이 낡는데
#:  링크도 tag 도 안 깨져서 **아무 검사도 안 운다.**
#:
#:  2026-09-07 에 실제로 걸렸다 — `003_outbox_tenant_scoped_dedupe.sql` 이
#:  `outbox` 제약에 `tenant_id` 를 넣은 뒤에도 wiki 세 곳이 옛 제약을 실었고,
#:  그중 하나는 **스니펫 주석이 003 을 가리키면서 003 이전 값**을 싣고 있었다.
#:  `tenant_id` 누락은 테넌트끼리 dedupe 충돌을 내는 보안급이다.
WIKI_ROOTS = ("wiki", "final_project_cs/wiki", "final_project_sample/wiki",
              "datasets/wiki", "acop_dojo/wiki")
UNIQUE_RE = re.compile(r"UNIQUE\s*\(([^)]*)\)", re.I)
MIGRATIONS = "final_project_cs/app/infrastructure/db/migrations"


#: cs 의 `.env` 에서 접속 문자열만 꺼낸다. ★앱을 import 하지 않는다 —
#:  `app.infrastructure.db.session` 을 부르면 cs 패키지 전체가 딸려 와서
#:  그것만으로 느리고, 접속 시간 제한도 우리가 못 건다.
CS_ENV = "final_project_cs/.env"
DB_TIMEOUT_SECONDS = 5


def _dsn() -> str | None:
    if not os.path.exists(CS_ENV):
        return None
    for line in Path(CS_ENV).read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("ACOP_DATABASE_URL="):
            url = line.split("=", 1)[1].strip().strip('"').strip("'")
            # SQLAlchemy 표기(`postgresql+psycopg://`)를 libpq 가 아는 형태로
            return url.replace("postgresql+psycopg://", "postgresql://", 1)
    return None


def _real_constraints() -> tuple[set[frozenset], str]:
    """살아 있는 DB 를 먼저 본다. 못 붙으면 마이그레이션 SQL 로 떨어진다.

    ★DB 가 정본이다. 마이그레이션은 "돌렸다면 이렇게 됐을 것" 이라서
      실제로 안 돌린 환경에서는 거짓 안심을 준다. 어느 쪽을 봤는지 찍는다.

    ★**시간 제한을 건다.** DB 가 응답을 안 하면 예외가 아니라 멈춤이라
      `except` 로는 안 잡힌다. 2026-09-09 에 실제로 이것 때문에 검사기가
      90초를 넘겨 죽었다. 붙는 데 몇 초 넘게 걸리면 없는 것으로 본다.
    """
    dsn = _dsn()
    if dsn:
        try:
            import psycopg
            out = set()
            # ★`SET LOCAL statement_timeout = %s` 는 **SyntaxError 다** —
            #   `SET` 은 자리표시자를 안 받는다(2026-09-09 실측). 접속 옵션으로 건다.
            with psycopg.connect(dsn, connect_timeout=DB_TIMEOUT_SECONDS,
                                 options=f"-c statement_timeout={DB_TIMEOUT_SECONDS * 1000}") as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_get_constraintdef(oid) "
                                "FROM pg_constraint WHERE contype = 'u'")
                    for (definition,) in cur.fetchall():
                        m = UNIQUE_RE.search(definition or "")
                        if m:
                            out.add(frozenset(c.strip().strip('"')
                                              for c in m.group(1).split(",")))
            if out:
                return out, "살아 있는 DB (pg_constraint)"
        except Exception as exc:
            print(f"    DB 에 못 붙었다({type(exc).__name__}) — 마이그레이션으로 떨어진다")

    out = set()
    if os.path.isdir(MIGRATIONS):
        for name in sorted(os.listdir(MIGRATIONS)):
            if not name.endswith(".sql"):
                continue
            sql = Path(MIGRATIONS, name).read_text(encoding="utf-8", errors="replace")
            for m in UNIQUE_RE.finditer(sql):
                out.add(frozenset(c.strip().strip('"') for c in m.group(1).split(",")))
    return out, f"마이그레이션 SQL ({MIGRATIONS}) — ★DB 를 못 봤다"


def check_db_constraints(_text: str) -> int:
    print("[6] DB 제약 대조 — wiki 의 UNIQUE 스니펫이 실제와 맞나")
    real, source = _real_constraints()
    if not real:
        print("    제약을 한 건도 못 읽었다. DB 도 마이그레이션도 안 보인다 — 건너뛴다.")
        return 0
    print(f"    기준: {source} · 유니크 제약 {len(real)}종 · 대상은 wiki 본문(records/ 제외)")

    flagged = 0
    for root in WIKI_ROOTS:
        if not os.path.isdir(root):
            continue
        for dirpath, _, names in os.walk(root):
            for name in sorted(names):
                if not name.endswith(".md"):
                    continue
                path = os.path.join(dirpath, name).replace("\\", "/")
                # ★`wiki/records/` 는 건너뛴다 (2026-09-08 `docs/` 통합).
                #   날짜가 박힌 작업 기록이라 **고치지 않는 것이 성질**이다
                #   (루트 `CLAUDE.md`, `check_wiki.py` 도 같은 이유로 면제한다).
                #   통합 직후 여기서 27곳이 올라왔는데 전부 옛 기록의 옛 제약이었다 —
                #   고칠 수 없는 것을 매번 보여 주면 경보가 경보가 아니게 된다.
                # ★읽기 **전에** 거른다. 읽고 나서 걸렀더니 799개를 다 열어
                #   검사 6 하나가 90초를 넘겼다(2026-09-09 실측). 못 돌리는
                #   검사기는 아무도 안 돌린다.
                if "/records/" in path:
                    continue
                lines = read(path).splitlines()
                for i, line in enumerate(lines, 1):
                    for m in UNIQUE_RE.finditer(line):
                        cols = frozenset(c.strip().strip("`\"' ")
                                         for c in m.group(1).split(","))
                        if not cols or "..." in cols or "" in cols:
                            continue
                        if cols in real:
                            continue
                        frag = line.strip()[:110]
                        if note(6, path, i, frag):
                            flagged += 1
                            print(f"    ★{path}:{i}")
                            print(f"        {frag}")
    if not flagged:
        print("    새로 볼 것 없음.")
        return 0
    print()
    print(f"    ★{flagged}곳. **틀렸다는 뜻이 아니다** — 옛 제약을 **역사로** 적은 자리도")
    print("      이렇게 걸린다(\"원래는 tenant_id 가 없었다\"). 지금 값으로 적은 것인지")
    print("      그때는 그랬다고 적은 것인지는 사람이 읽어 가른다. 판정하면 원장에 남는다.")
    return flagged

# ── 실행 ──────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int, choices=[1, 2, 3, 4, 5, 6], help="한 검사만 돌린다")
    ap.add_argument("--판정", nargs="+", metavar="지문=정상|정정함",
                    help="후보를 판정해 원장에 적는다. 지문은 --지문 으로 본다")
    ap.add_argument("--메모", default="", help="--판정 과 같이 쓴다. 왜 그렇게 봤는지")
    ap.add_argument("--지문", action="store_true", help="후보를 지문과 함께 나열한다")
    args = ap.parse_args()

    global LEDGER_ROWS
    LEDGER_ROWS = load_ledger()

    if not os.path.exists(BASELINE):
        print(f"기준선이 없다: {BASELINE}")
        print("저장소 루트에서 실행한다.")
        return 1

    text = read(BASELINE)
    print(f"기준선: {BASELINE}")
    print()

    checks = {1: check_revisions, 2: check_claude_quotes, 3: check_code,
              4: check_fact_tables, 5: check_progress_claims,
              6: check_db_constraints}
    todo = [args.only] if args.only else [1, 2, 3, 4, 5, 6]
    total = 0
    for n in todo:
        total += checks[n](text)
        print()

    if args.지문:
        print("─" * 62)
        print("후보 지문 — --판정 <지문>=정상 으로 원장에 적는다")
        for c in CANDIDATES:
            mark = "  " if c["지문"] in LEDGER_ROWS else "★"
            print(f"  {mark}{c['지문']}  검사{c['검사']}  {c['행']:>5}행  {c['본문'][:64]}")
        print()

    if args.판정:
        index = {c["지문"]: c for c in CANDIDATES}
        rows, unknown = [], []
        for item in args.판정:
            fp, _, verdict = item.partition("=")
            if fp not in index:
                unknown.append(fp)
                continue
            if verdict not in ("정상", "정정함"):
                print(f"판정은 정상 또는 정정함 이어야 한다: {item}")
                return 1
            c = index[fp]
            rows.append({**c, "판정": verdict, "날짜": _today(), "메모": args.메모})
        if unknown:
            # ★없는 지문을 조용히 넘기면 원장이 실제와 어긋난 채 커진다.
            print(f"이번 실행의 후보에 없는 지문이다: {', '.join(unknown)}")
            return 1
        append_ledger(rows)
        print("─" * 62)
        print(f"원장에 {len(rows)}건 적었다 → {LEDGER}")
        return 0

    print("─" * 62)
    settled_total = sum(1 for c in CANDIDATES if c["지문"] in LEDGER_ROWS)
    if total:
        print(f"사람이 볼 것 {total}건" + (f" (판정됨 {settled_total}건은 감췄다)" if settled_total else "") + ". 위 ★표시를 확인한다.")
        print("판정 절차는 program/research/index.md 문서 정합성 점검 캘린더 항목 4·5.")
        print("판정을 남기려면 --지문 으로 지문을 보고 --판정 <지문>=정상 --메모 \"...\" 를 쓴다.")
    else:
        print("확인할 것 없음." + (f" 판정된 후보 {settled_total}건은 원장에 있다." if settled_total else ""))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())

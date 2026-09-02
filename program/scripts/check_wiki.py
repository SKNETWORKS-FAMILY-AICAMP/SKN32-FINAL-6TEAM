"""wiki 표준 검사기.

program/wiki/governance/ 의 규칙을 실제로 검사한다.
문서에만 적힌 규칙은 지켜지지 않으므로 실행으로 판정한다.

    python program/scripts/check_wiki.py

종료 코드 0 = 통과, 1 = 위반 있음.
"""
from __future__ import annotations

import glob
import os
import re
import sys
from collections import Counter, defaultdict

# Windows 콘솔이 cp949 라 한글 외 기호에서 깨진다. 출력만 utf-8 로 고정한다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: 시험 구축 중이라 저장소별 wiki 도 전부 program/ 아래에 둔다.
#: 실제 저장소에는 아직 wiki 를 넣지 않는다.
ROOTS = [
    "program/wiki",
    "program/final_project_cs/wiki",
    "program/final_project_sample/wiki",
    "program/datasets/wiki",
    "program/acop_dojo/wiki",
]

#: governance/front-matter.md — type 11개.
#: evidence·runbook 은 표본 A 검증에서, reference 는 표본 B blind 대조에서 추가됐다.
#: 셋 다 두 판정자가 같은 자리에서 막혀 드러난 빈 자리다. (type-verification.md)
TYPES = {
    "concept", "decision", "plan", "contract", "guide",
    "report", "research", "policy", "dataset",
    "evidence", "runbook", "reference",
}

#: governance/front-matter.md — tags 통제 목록
TAGS = {
    "agent", "api", "architecture", "contract", "cost", "customer-operations",
    "data", "evaluation", "gpu", "release", "security", "state", "testing", "ui",
    "documentation", "governance",
}

#: governance/document-standard.md — 문서가 커질 때
SOFT_LINES = 300
HARD_LINES = 500

#: 예약 파일
RESERVED = {"index.md", "log.md", "quickstart.md"}

#: 불변식 ID 접두사 → 저장소. governance/structure-guide.md
INV_REPO = {
    "CS": "final_project_cs",
    "SAMPLE": "final_project_sample",
    "HUB": "program",
    "DOJO": "acop_dojo",
    "DATA": "datasets",
    "GPU": None,          # 별도 워크스페이스. 검사 대상 아님
}

#: ★구현 편향 검사.
#:
#:   요구: cs 가 릴리스로 나간 뒤에도 sample 은 혼자 정확히 돌아야 한다.
#:   따라서 hub(program/wiki)는 **어느 한 구현에만 매여선 안 된다.**
#:   hub 의 계약 문서가 cs 상세로만 내려가면, cs 가 나가는 순간
#:   계약을 읽으러 온 사람이 전부 남의 저장소로 떨어진다.
#:
#:   규칙: hub 문서가 한 구현을 가리키면 다른 구현도 가리키거나,
#:         왜 한쪽만 있는지를 front matter 에 적는다.
IMPL_REPOS = ("final_project_cs", "final_project_sample")
IMPL_REF = re.compile(r"(final_project_cs|final_project_sample)/")

#: 편향이 정당한 문서. 이유를 함께 적는다.
IMPL_BIAS_OK = {
    # cs 만 다루는 게 맞는 것 — 도메인·릴리스 고유
    "product/", "business/", "delivery/",
    # 이관 작업 자체의 기록. 대상이 cs 라서 한쪽만 나온다
    "governance/migration", "governance/type-verification/",
    "log.md",
    # ★_migration/ 은 이관 전 스테이징이다. 원문을 형식만 바꿔 담아 둔 곳이라
    #   hub 의 계약 문서가 아니다. 적용할 때 이 규칙을 다시 건다.
    "_migration/",
}

FENCE = re.compile(r"(?ms)^```.*?^```+\s*$")
LINK = re.compile(r"\]\(([^)#]*\.md)\)")
INV_DOC = re.compile(r"`(INV-[A-Z]+-[A-Z]+-\d{3})`")
INV_CODE = re.compile(r"#\s*invariant:\s*(INV-[A-Z]+-[A-Z]+-\d{3})")


def front_matter(text: str) -> dict[str, str] | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fm: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.startswith((" ", "-", "\t")):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def main() -> int:
    docs: list[str] = []
    for r in ROOTS:
        docs += sorted(glob.glob(r + "/**/*.md", recursive=True))

    problems: dict[str, list[str]] = defaultdict(list)
    pending: list[str] = []               # 아직 안 쓴 문서로 가는 링크. 위반 아님
    inv_in_docs: Counter[str] = Counter()
    inv_tests: list[tuple[str, str, str]] = []   # (doc, id, test path)

    for f in docs:
        raw = open(f, encoding="utf-8").read()
        body = FENCE.sub("", raw)
        rel = f.replace("\\", "/")
        n_lines = raw.count("\n") + 1

        # --- front matter
        fm = front_matter(raw)
        if fm is None:
            problems["front matter 없음"].append(rel)
            fm = {}
        else:
            t = fm.get("type", "")
            if not t:
                problems["type 없음"].append(rel)
            elif t not in TYPES:
                problems["알 수 없는 type"].append(f"{rel}  (type: {t})")

            if fm.get("status") == "stable":
                for req in ("title", "description", "owners"):
                    if not fm.get(req):
                        problems["stable 인데 필수 필드 없음"].append(f"{rel}  ({req})")

            tags = fm.get("tags", "")
            for tag in re.findall(r"[a-z][a-z0-9-]*", tags):
                if tag not in TAGS:
                    problems["통제 목록에 없는 tag"].append(f"{rel}  ({tag})")

        # --- 크기
        #   ★ front matter 만 본다. 본문 예시의 size_exempt 를 세면 안 된다.
        exempt = fm.get("size_exempt", "").lower() == "true"
        if exempt and not fm.get("size_exempt_reason"):
            problems["size_exempt 인데 이유 없음"].append(rel)
        if not exempt:
            if n_lines > HARD_LINES:
                problems["500줄 초과 (분할 필요)"].append(f"{rel}  ({n_lines}줄)")
            elif n_lines > SOFT_LINES:
                problems["300줄 초과 (분할 검토)"].append(f"{rel}  ({n_lines}줄)")

        # --- 링크
        #   폴더가 있으면 "아직 안 쓴 문서", 폴더도 없으면 "경로 오타"로 나눈다.
        d = os.path.dirname(f)
        for p in LINK.findall(body):
            target = os.path.normpath(os.path.join(d, p))
            if os.path.exists(target):
                continue
            if os.path.isdir(os.path.dirname(target)):
                pending.append(f"{rel} -> {p}")
            else:
                problems["경로 오타 (폴더도 없음)"].append(f"{rel} -> {p}")

        # --- 불변식
        for inv in INV_DOC.findall(body):
            inv_in_docs[inv] += 1
        for m in re.finditer(
            r"`(INV-[A-Z]+-[A-Z]+-\d{3})`[^|]*\|[^|]*\|\s*automated\s*\|\s*`?([^`|]+)`?", body
        ):
            inv_tests.append((rel, m.group(1), m.group(2).strip()))

    # --- 폴더마다 index.md
    #   ★ `_` 로 시작하는 폴더는 스테이징이다. 탐색 계층이 아니므로 면제한다.
    #     루트에는 index.md 를 둬서 무엇을 하는 곳인지 밝힌다.
    for r in ROOTS:
        for dirpath, _, files in os.walk(r):
            d = dirpath.replace("\\", "/")
            if any(part.startswith("_") for part in d.split("/")[2:]):
                continue
            if any(f.endswith(".md") for f in files) and "index.md" not in files:
                problems["index.md 없는 폴더"].append(d)

    # --- 불변식 테스트 경로 실재 여부
    #   ★ 저장소는 문서 위치가 아니라 불변식 ID 접두사로 정한다.
    #     중앙 허브 문서가 cs 테스트를 인용하는 경우가 많다.
    last_test_file: dict[str, str] = {}   # 문서별 직전 테스트 파일 (`::test_x` 축약용)
    for doc, inv, path in inv_tests:
        repo = INV_REPO.get(inv.split("-")[1])
        if repo is None:
            problems["알 수 없는 불변식 저장소 접두사"].append(f"{inv}  ({doc})")
            continue
        fpath, _, fname = path.partition("::")
        fpath, fname = fpath.strip(), fname.strip()

        # `::test_x` 만 적힌 경우 같은 문서의 직전 파일 경로를 이어받는다
        if not fpath and last_test_file.get(doc):
            fpath = last_test_file[doc]
        if not fpath.startswith("tests/"):
            continue                       # 경로가 아니라 설명이면 건너뛴다
        last_test_file[doc] = fpath

        full = os.path.join(repo, fpath)
        if not os.path.exists(full):
            problems["불변식이 가리키는 테스트 파일 없음"].append(f"{inv}  {repo}/{fpath}")
            continue
        if fname:
            src = open(full, encoding="utf-8", errors="replace").read()
            if not re.search(rf"^\s*def {re.escape(fname)}\s*\(", src, re.M):
                problems["불변식이 가리키는 테스트 함수 없음"].append(
                    f"{inv}  {repo}/{fpath}::{fname}"
                )

    # --- 코드 쪽 역방향 표식
    code_ids: set[str] = set()
    for py in glob.glob("final_project_cs/tests/**/*.py", recursive=True):   # 코드는 원래 자리
        code_ids |= set(INV_CODE.findall(open(py, encoding="utf-8", errors="replace").read()))
    doc_ids = set(inv_in_docs)
    for cid in sorted(code_ids - doc_ids):
        problems["코드에만 있는 불변식 ID"].append(cid)

    # --- 구현 편향: hub 가 한쪽 구현만 가리키는가
    for f in docs:
        rel = f.replace("\\", "/")
        if not rel.startswith("program/wiki/"):
            continue
        sub = rel[len("program/wiki/"):]
        if any(sub.startswith(k) or k in sub for k in IMPL_BIAS_OK):
            continue
        raw_h = open(f, encoding="utf-8").read()
        fm_h = front_matter(raw_h) or {}
        # 한쪽만 다루는 게 맞는 문서는 이유와 함께 선언한다.
        #   impl_scope: cs — 왜 sample 에는 해당하지 않는지
        scope = fm_h.get("impl_scope", "")
        if scope:
            if len(scope.split("—")) < 2 and len(scope.split("-")) < 2:
                problems["impl_scope 인데 이유 없음"].append(rel)
            continue
        body = FENCE.sub("", raw_h)
        hit = {m.group(1) for m in IMPL_REF.finditer(body)}
        if len(hit) == 1:
            only = hit.pop()
            other = [r for r in IMPL_REPOS if r != only][0]
            n = len(IMPL_REF.findall(body))
            problems["hub 가 한 구현만 가리킨다"].append(
                f"{sub}  ({only} {n}회 · {other} 0회)")

    # --- 출력
    print(f"문서 {len(docs)}개 검사")
    print(f"불변식 {len(doc_ids)}개 (automated 연결 {len(inv_tests)}개)")
    print(f"코드 역방향 표식 {len(code_ids)}개")
    print()

    if pending:
        targets = sorted({p.split(' -> ')[1] for p in pending})
        print(f"미작성 문서로 가는 링크 {len(pending)}건 (고유 {len(targets)}개) — 위반 아님")
        for t in targets[:8]:
            print(f"    {t}")
        if len(targets) > 8:
            print(f"    ... 외 {len(targets) - 8}개")
        print()

    total = sum(len(v) for v in problems.values())
    if not total:
        print("통과. 위반 없음.")
        return 0

    for kind in sorted(problems, key=lambda k: -len(problems[k])):
        items = problems[kind]
        print(f"[{len(items)}] {kind}")
        for it in items[:12]:
            print(f"    {it}")
        if len(items) > 12:
            print(f"    ... 외 {len(items) - 12}건")
        print()

    print(f"위반 {total}건")
    return 1


if __name__ == "__main__":
    sys.exit(main())

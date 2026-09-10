"""wiki 표준 검사기.

wiki/governance/ 의 규칙을 실제로 검사한다.
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

#: 2026-09-07 전환 완료 — 각 저장소의 `wiki/` 가 정본이다 (D-012).
#: 전환 전에는 다섯 트리가 전부 `program/` 아래에 있었다.
ROOTS = [
    "wiki",
    "final_project_cs/wiki",
    "final_project_sample/wiki",
    "datasets/wiki",
    "acop_dojo/wiki",
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

#: ★도메인 축 (2026-09-09 신설). governance/domain-axis.md
#:
#:   2026-09-08 에 도메인이 커머스 → 여행으로 통째로 바뀌었다. 그런데 **어느 문서가
#:   그 교체에 걸리는지 알 방법이 없어** grep 으로 훑어야 했고, grep 은 "쇼핑몰"
#:   이라는 낱말이 안 든 문서를 놓쳤다 — `wiki/architecture/pack-model.md` 의
#:   Pack 표가 그렇게 하루 넘게 커머스로 남아 있었다.
#:
#:   그래서 문서마다 front matter 에 **이 문서가 도메인에 묶여 있는가**를 적는다.
#:   다음 교체 때 대상 목록이 grep 이 아니라 목록으로 나온다:
#:
#:       python program/scripts/check_wiki.py --domain travel
CURRENT_DOMAIN = "travel"
PAST_DOMAINS = ("commerce",)
DOMAINS = {"neutral", CURRENT_DOMAIN, *PAST_DOMAINS}

#: `domain: neutral` 을 주장하는 문서에 이 낱말이 여러 번 나오면 주장이 거짓이다.
#:   ★도메인 **이름**("커머스"·"여행")은 넣지 않는다. 판올림 자체를 설명하는 문장에
#:     정당하게 나오기 때문이다. 여기 넣는 것은 **업무 어휘**뿐이다.
DOMAIN_VOCAB = {
    "commerce": ("주문", "배송", "반품", "환불", "장바구니", "결제 수단",
                 "order_id", "shipment", "sku", "cart", "refund"),
    "travel": ("일정", "액티비티", "숙박", "항공", "여행자", "티타임",
               "trip", "itinerary", "booking", "reservation", "activity"),
}

#: 두 번까지는 예시로 본다. 세 번부터 "이 문서는 그 도메인 얘기를 하고 있다"로 본다.
#:   면제하려면 front matter 에 `domain_note:` 로 왜인지 적는다.
DOMAIN_VOCAB_LIMIT = 2

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
#:   따라서 hub(wiki)는 **어느 한 구현에만 매여선 안 된다.**
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

#: ★문서가 인용한 코드 경로가 실재하는지 (2026-09-10 신설).
#:
#:   2026-09-10 에 커머스 모듈이 삭제되자 **비-기록 문서 36곳이 없는 파일을
#:   인용하는 상태**가 됐다. 링크 검사는 `.md` 만 보므로 이걸 못 잡았다.
#:   문서가 `app/core/x.py` 를 근거로 적고 그 파일이 사라지면 **근거가 없는
#:   문장이 남는다** — 그게 이 프로젝트가 가장 막으려는 것이다.
#:
#:   찾는 방법의 한계: 본문에 적힌 경로 문자열만 본다. 동적으로 조립되는
#:   경로나 이름이 바뀐 같은 파일은 못 잡는다.
CODE_PATH = re.compile(r"`((?:app|tests|eval|scripts|config)/[A-Za-z0-9_\-./]+\.(?:py|ya?ml|jsonl?|txt|md))`")

#: 코드 경로를 찾을 저장소. 문서가 어느 저장소를 말하는지 경로만으로는 모르므로
#: 전부에서 찾고 **어디에도 없을 때만** 센다.
#:   ★`datasets/wiki/` 문서의 `scripts/x.py` 는 **그 데이터셋 폴더 기준**이다
#:     (`datasets/<도메인>/<이름>/scripts/x.py`). 처음 이 검사를 넣었을 때
#:     12건이 거짓양성으로 나왔고 전부 그 경우였다.
CODE_ROOTS = ("final_project_cs", "final_project_sample", "acop_dojo", ".")
CODE_ROOTS_GLOB = ("datasets/*/*",)

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
    record_broken: list[str] = []         # records/ 안의 깨진 링크. 집계만 한다
    inv_in_docs: Counter[str] = Counter()
    inv_tests: list[tuple[str, str, str]] = []   # (doc, id, test path)
    unmarked: list[str] = []                     # domain 미표시. 위반 아니고 집계다
    dead_code: list[str] = []                    # 없는 코드 파일을 인용하는 문서
    by_domain: dict[str, list[str]] = defaultdict(list)
    stale_todo: list[str] = []       # 옛 도메인인데 이유가 없다 = 다시 써야 한다
    stale_recorded: list[str] = []   # 옛 도메인이지만 이유가 있다 = 그대로 둔다

    for f in docs:
        raw = open(f, encoding="utf-8").read()
        body = FENCE.sub("", raw)
        rel = f.replace("\\", "/")
        n_lines = raw.count("\n") + 1

        # --- 기록 구역 (2026-09-08 docs/ 통합)
        #   `wiki/records/` 는 날짜가 박힌 작업 기록(evidence·리포트·옛 handoff 등)이다.
        #   고치지 않는 것이 기록의 성질이므로 front matter·크기·index 규칙을 적용하지
        #   않고, 깨진 링크는 위반이 아니라 집계로만 낸다 — 옛 기록의 링크가 낡는 건
        #   정상이고, 그걸 고치면 기록이 아니게 된다.
        if "/records/" in rel:
            d = os.path.dirname(f)
            for p in LINK.findall(FENCE.sub("", raw)):
                if not os.path.exists(os.path.normpath(os.path.join(d, p))):
                    record_broken.append(f"{rel} -> {p}")
            continue

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

            # --- 도메인 축
            dom = fm.get("domain", "")
            if not dom:
                unmarked.append(rel)
            elif dom not in DOMAINS:
                problems["알 수 없는 domain"].append(f"{rel}  (domain: {dom})")
            else:
                by_domain[dom].append(rel)
                if dom not in ("neutral", CURRENT_DOMAIN):
                    # 지금 도메인이 아닌 값 = 옛 도메인으로 쓰인 문서.
                    #   두 부류가 섞이므로 이유(domain_note)로 가른다.
                    #     이유 있음 → 그때의 기록이거나 그 도메인이 맞는 문서. 그대로 둔다
                    #     이유 없음 → 판올림을 못 따라간 것. 다시 써야 한다
                    (stale_recorded if fm.get("domain_note") else stale_todo).append(rel)
                if dom == "neutral" and not fm.get("domain_note"):
                    b = FENCE.sub("", raw)
                    for dname, words in DOMAIN_VOCAB.items():
                        n = sum(b.count(w) for w in words)
                        if n > DOMAIN_VOCAB_LIMIT:
                            problems["neutral 인데 도메인 어휘가 있다"].append(
                                f"{rel}  ({dname} 어휘 {n}회 — 고치거나 domain_note 로 이유를 적는다)")

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

        # --- 인용한 코드 경로가 실재하나
        #   ★`records/` 는 위에서 continue 했으므로 여기 오지 않는다 — 옛 기록이
        #     없어진 파일을 인용하는 것은 정상이다.
        for cp in set(CODE_PATH.findall(body)):
            if any(os.path.exists(os.path.join(r, cp)) for r in CODE_ROOTS):
                continue
            if any(glob.glob(os.path.join(g, cp)) for g in CODE_ROOTS_GLOB):
                continue
            dead_code.append(f"{rel} -> {cp}")

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
            inner = d[len(r):].strip("/")
            if any(part.startswith("_") for part in inner.split("/") if part):
                continue
            if inner == "records" or inner.startswith("records/"):
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
        if not rel.startswith("wiki/"):
            continue
        sub = rel[len("wiki/"):]
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
    n_records = sum(1 for f in docs if "/records/" in f.replace("\\", "/"))
    if n_records:
        print(f"기록(records/) {n_records}개 — 규칙 면제. 깨진 링크 {len(record_broken)}곳은 집계만 한다")

    # --- 도메인 축 집계
    n_axis = sum(len(v) for v in by_domain.values())
    n_all = n_axis + len(unmarked)
    if n_all:
        pct = round(100 * n_axis / n_all)
        parts = " · ".join(f"{k} {len(v)}" for k, v in sorted(by_domain.items()))
        print(f"도메인 축 표시 {n_axis}/{n_all} = {pct}%" + (f"  ({parts})" if parts else ""))
        if unmarked:
            print(f"    미표시 {len(unmarked)}개 — 위반 아님. 다음 교체 때 대상인지 알 수 없다")
        if stale_todo:
            print(f"    ★옛 도메인인데 이유가 없다 {len(stale_todo)}개 — 판올림을 못 따라간 문서다")
            for x in stale_todo[:10]:
                print(f"        {x}")
            if len(stale_todo) > 10:
                print(f"        ... 외 {len(stale_todo) - 10}개")
        if stale_recorded:
            print(f"    옛 도메인이나 이유가 붙어 있다 {len(stale_recorded)}개 — 그대로 둔다")
    print()

    if dead_code:
        print(f"[{len(dead_code)}] 문서가 인용한 코드 파일이 없다 — 위반 아니고 집계다")
        print("    ★둘을 가려야 한다 — 「삭제를 기록한 결정 문서」는 맞고,")
        print("      「근거로 인용했는데 사라진 것」은 근거 없는 문장이 남은 것이다")
        for it in sorted(dead_code)[:12]:
            print(f"    {it}")
        if len(dead_code) > 12:
            print(f"    ... 외 {len(dead_code) - 12}건")
        print()

    if pending:
        targets = sorted({p.split(' -> ')[1] for p in pending})
        print(f"미작성 문서로 가는 링크 {len(pending)}건 (고유 {len(targets)}개) — 위반 아님")
        for t in targets[:8]:
            print(f"    {t}")
        if len(targets) > 8:
            print(f"    ... 외 {len(targets) - 8}개")
        print()

    # --- `--domain <이름>` : 그 도메인에 묶인 문서 목록 (교체 대상 작업 목록)
    if "--domain" in sys.argv:
        i = sys.argv.index("--domain")
        want = sys.argv[i + 1] if len(sys.argv) > i + 1 else CURRENT_DOMAIN
        hits = sorted(by_domain.get(want, []))
        print(f"domain: {want} 인 문서 {len(hits)}개 — 도메인을 바꾸면 이것들을 다시 쓴다")
        for h in hits:
            print(f"    {h}")
        if unmarked:
            print("")
            print(f"  ★미표시 {len(unmarked)}개는 이 목록에 안 들어 있다. 목록이 아직 완전하지 않다")
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

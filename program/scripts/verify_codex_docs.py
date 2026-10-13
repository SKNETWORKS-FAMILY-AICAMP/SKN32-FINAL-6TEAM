"""codex 가 낸 문서의 근거 인용을 기계로 대조한다.

    python program/scripts/verify_codex_docs.py program/scripts/_codex_out/teams_raw.md

무엇을 보나:
  1. `파일:줄` 인용이 실재하고 범위 안인가
  2. 금지 대상(final_project_cs·wiki)을 읽었나
     ★"cs 에는 없다" 류 부정 서술은 위반으로 세지 않는다
  3. 빈 패키지를 문서화했나
  4. 근거 등급이 붙어 있나

★이 검사는 "인용이 가리키는 줄이 존재한다"까지만 본다.
  그 줄이 주장하는 내용인지는 사람이 봐야 한다. 자동으로 못 한다.
"""
from __future__ import annotations

import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SAMPLE = "final_project_sample/"
PREFIX = {
    "core/": "acop_basement/core/",
    "application/": "acop_basement/application/",
    "teams/": "acop_basement/teams/",
    "acop_composer/": "acop_composer/",
    "tests/": "tests/",
}
CITE = re.compile(
    r"`((?:core|application|teams|acop_composer|tests)/[A-Za-z0-9_/.]+\.py):(\d+)(?:-(\d+))?`")
BANNED = ("final_project_cs", "wiki")


def resolve(rel: str) -> str | None:
    for k, v in PREFIX.items():
        if rel.startswith(k):
            return SAMPLE + v + rel[len(k):]
    return None


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = sys.argv[1]
    text = open(path, encoding="utf-8", errors="replace").read()

    bad: list[str] = []
    ok = 0
    files: set[str] = set()

    for m in CITE.finditer(text):
        rel, a, b = m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))
        p = resolve(rel)
        if p is None or not os.path.exists(p):
            bad.append(f"파일 없음   {rel}:{a}")
            continue
        n = sum(1 for _ in open(p, encoding="utf-8", errors="replace"))
        if b > n:
            bad.append(f"줄 초과     {rel}:{a}-{b}  (실제 {n}줄)")
        else:
            ok += 1
            files.add(p)

    print(f"{os.path.basename(path)}")
    print(f"  인용 {ok + len(bad)}건 · 유효 {ok} · 문제 {len(bad)}")
    for b in bad[:15]:
        print(f"    {b}")

    # ★"cs 에는 없다" 같은 부정 서술은 위반이 아니다. 8차 검증에서 오탐이 났다.
    NEGATED = ("없다", "않는다", "아니다", "안 한다", "제외")
    banned_hits = 0
    for word in BANNED:
        lines = [ln for ln in text.splitlines() if word in ln]
        real = [ln for ln in lines if not any(g in ln for g in NEGATED)]
        banned_hits += len(real)
        note = ""
        if len(lines) != len(real):
            note = f"  (부정 서술 {len(lines) - len(real)}건은 뺐다)"
        print(f"  금지어 '{word}'  {len(real)}회" + ("  ★위반" if real else "") + note)

    # 빈 패키지를 문서에 등장시켰나
    empties = []
    for root, dirs, fs in os.walk(SAMPLE + "acop_basement"):
        if "__pycache__" in root:
            continue
        if not any(f.endswith(".py") and f != "__init__.py" for f in fs):
            name = root.replace(os.sep, "/").replace(SAMPLE, "")
            if name.count("/") >= 2 and name in text:
                empties.append(name)
    print(f"  빈 패키지 언급 {len(empties)}건" + ("  ★위반" if empties else ""))
    for e in empties:
        print(f"    {e}")

    print(f"  [실측] {text.count('[실측]')}회 · [미확보] {text.count('[미확보]')}회")
    print(f"  인용된 파일 {len(files)}개")
    print()
    print("  ★내용이 맞는지는 사람이 본다. 이 검사는 인용의 실재만 확인한다.")
    return 1 if (bad or empties or banned_hits) else 0


if __name__ == "__main__":
    sys.exit(main())

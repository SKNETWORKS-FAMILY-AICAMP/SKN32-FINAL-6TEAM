"""원본 문서의 절이 wiki 에 반영됐는지 기계로 후보를 뽑는다.

    python program/scripts/audit_coverage.py <원본경로>

★이 도구는 판정하지 않는다. **어디를 봐야 하는지**만 좁힌다.
  절 제목과 본문의 특징 문자열(숫자·파일명·따옴표 인용)이 wiki 에
  있는지 세고, 없으면 사람이 그 절을 직접 읽는다.

  "비슷한 주제가 있다" 를 반영으로 세면 안 된다 — 그래서 자동 판정을 안 한다.
"""
from __future__ import annotations

import glob
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WIKI_GLOBS = ["wiki/**/*.md", "final_project_cs/wiki/**/*.md",
              "final_project_sample/wiki/**/*.md",
              "datasets/wiki/**/*.md", "acop_dojo/wiki/**/*.md"]

#: 절 안에서 "이게 있으면 옮겨진 것" 을 판별할 만한 특징 문자열
SIGNALS = [
    re.compile(r"`([A-Za-z_][A-Za-z0-9_./]{4,})`"),      # 코드·파일명
    re.compile(r"(\d[\d,]{2,}(?:\.\d+)?%?)"),             # 숫자
    re.compile(r"\*\*([^*\n]{6,40})\*\*"),                # 강조 문구
]


def load_wiki() -> str:
    out = []
    for g in WIKI_GLOBS:
        for f in glob.glob(g, recursive=True):
            out.append(open(f, encoding="utf-8", errors="replace").read())
    return "\n".join(out)


def sections(text: str) -> list[tuple[str, str]]:
    parts = re.split(r"^(#{2,3} .+)$", text, flags=re.M)
    out = []
    for i in range(1, len(parts), 2):
        out.append((parts[i].lstrip("# ").strip(), parts[i + 1]))
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = sys.argv[1]
    wiki = load_wiki()
    text = open(src, encoding="utf-8", errors="replace").read()
    secs = sections(text)

    print(f"{os.path.basename(src)}  —  절 {len(secs)}개\n")
    print(f"{'절':44} {'신호':>5} {'적중':>5}  판정후보")
    print("-" * 78)
    need = []
    for title, body in secs:
        sigs = []
        for pat in SIGNALS:
            sigs += pat.findall(body)
        sigs = [s for s in dict.fromkeys(sigs) if len(s) >= 4][:14]
        hit = sum(1 for s in sigs if s in wiki)
        if not sigs:
            verdict = "신호없음 — 직접 읽어라"
            need.append(title)
        elif hit == 0:
            verdict = "★누락 후보"
            need.append(title)
        elif hit < len(sigs) * 0.5:
            verdict = "일부 후보"
            need.append(title)
        else:
            verdict = "반영 후보"
        print(f"{title[:44]:44} {len(sigs):5} {hit:5}  {verdict}")

    print(f"\n사람이 읽어야 할 절 {len(need)}/{len(secs)}")
    for t in need:
        print(f"  - {t}")
    print("\n★이건 후보다. 판정은 사람이 한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

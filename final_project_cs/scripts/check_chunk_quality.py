"""청크 문장 품질 선별 — 게이트가 못 보는 것을 본다.

★`check_corpus.py` 는 **글자 수와 중복**을 잰다. 의미는 읽지 않는다.
  그래서 길이를 채우려고 붙인 어색한 꼬리 문장이 그대로 통과한다. 실제로 이런 게 나왔다:

      "이번 단계는 예정일을 갱신한다 확인 사건 5건은 해당 로그에 보관한다."

  두 문장이 마침표 없이 붙었고 뒷부분은 앞과 연결되지 않는다.

★`_unified_mall_3`(보험 약관) 의 방식을 옮겨 왔다. 그 프로젝트는 PDF 에서 뽑은 조항에
  `parse_status`(ok / suspect / no_clause_heads)를 붙이고 **`ok` 만 판정에 쓴다.**
  나머지는 `abstained=true` 로 기권한다 — 근거를 정확히 대기 어렵기 때문이다.

  우리는 문서를 **직접 쓰므로** 파싱 실패는 없지만, **빈약한 문장**이라는 다른 실패가 있다.
  그래서 같은 자리에 다른 검사를 놓는다.

★이 스크립트는 **후보를 뽑을 뿐 판정하지 않는다.** 사람이 읽고 정한다.
  기계가 문장의 의미를 안다고 가정하지 않는다.

    python -m scripts.check_chunk_quality
    python -m scripts.check_chunk_quality --show 20    # 상위 20건 본문까지
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

DOCUMENTS = Path(__file__).resolve().parents[1] / "knowledge" / "documents"

#: 문장 종결로 인정하는 어미. 정책 문서는 평서형 종결로 끝난다.
SENTENCE_END = re.compile(r"(다|음|함)\.")

#: ★의심 신호. 각각 "확실한 결함" 이 아니라 **읽어 볼 이유**다.
SIGNALS: dict[str, str] = {
    "run_on": "종결어미 뒤 마침표 없이 다음 문장이 붙었다",
    "short_tail": "마지막 문장이 지나치게 짧다 (길이 채우기 의심)",
    "no_object": "목적어 없이 서술어만 있는 문장이 있다",
    "repeated_verb": "같은 서술어가 한 청크에서 3번 이상 반복된다",
    "orphan_number": "숫자가 나오는데 단위나 대상이 붙지 않았다",
    "filler_pair": "끝에 짧은 문장이 2개 이상 연달아 붙었다",
}


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[다음함])\.\s*", text)
    return [p.strip() for p in parts if p.strip()]


def inspect(chunk: str) -> list[str]:
    """의심 신호 목록을 돌려준다. 빈 목록이면 특이사항 없음."""
    hits: list[str] = []
    sents = sentences(chunk)

    # 1) 종결어미 뒤에 마침표 없이 이어붙은 자리
    #    "…갱신한다 확인 사건…" 처럼 공백 하나로 두 문장이 붙은 경우
    if re.search(r"(다|음|함)\s+[가-힣]{2,}(은|는|이|가|을|를)\s", chunk):
        hits.append("run_on")

    if sents:
        tail = sents[-1]
        if len(re.sub(r"\s", "", tail)) < 12:
            hits.append("short_tail")
        short_tails = [s for s in sents[-3:] if len(re.sub(r"\s", "", s)) < 16]
        if len(short_tails) >= 2:
            hits.append("filler_pair")

    # 2) 목적어 없이 서술어만 (예: "확인한다." 만 있는 문장)
    for s in sents:
        stripped = re.sub(r"\s", "", s)
        if len(stripped) < 14 and re.search(r"(한다|된다|않는다)$", stripped):
            if not re.search(r"(을|를|이|가|은|는)", stripped):
                hits.append("no_object")
                break

    # 3) 같은 서술어 반복
    verbs = re.findall(r"([가-힣]{2,4})(?:한다|된다|않는다)", chunk)
    if verbs and Counter(verbs).most_common(1)[0][1] >= 3:
        hits.append("repeated_verb")

    # 4) 단위 없는 숫자
    for m in re.finditer(r"\d+", chunk):
        after = chunk[m.end():m.end() + 4]
        if not re.match(r"\s*(일|영업일|시간|분|초|%|퍼센트|원|건|회|개월|년|개|번|차|조|항)", after):
            hits.append("orphan_number")
            break

    return sorted(set(hits))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", type=int, default=0, help="상위 N건의 본문을 함께 출력")
    args = parser.parse_args()

    flagged: list[tuple[str, str, list[str], str]] = []
    total = 0
    for path in sorted(DOCUMENTS.glob("*.md")):
        body = path.read_text(encoding="utf-8").split("---", 2)[2]
        for section in re.split(r"^## ", body, flags=re.M)[1:]:
            title, _, text = section.partition("\n")
            text = text.strip()
            if not text:
                continue
            total += 1
            hits = inspect(text)
            if hits:
                flagged.append((path.name, title.strip(), hits, text))

    print("=" * 74)
    print("청크 문장 품질 선별  (게이트가 보지 않는 축)")
    print("=" * 74)
    print(f"  전체 청크 {total} · 신호 있음 {len(flagged)} ({len(flagged)/total:.1%})")
    counts = Counter(h for _, _, hits, _ in flagged for h in hits)
    for name, reason in SIGNALS.items():
        print(f"    {name:<14} {counts.get(name, 0):>4}  {reason}")

    print("-" * 74)
    for name, title, hits, text in flagged[: args.show or 0]:
        print(f"\n[{','.join(hits)}] {name} :: {title}")
        print(f"  {text[:200]}")

    print("-" * 74)
    # ★실패로 끝내지 않는다. 이것은 **읽어 볼 목록**이지 판정이 아니다.
    print("이 목록은 판정이 아니라 후보다. 사람이 읽고 고칠지 정한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

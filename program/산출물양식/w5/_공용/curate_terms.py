"""코덱스 용어 점검 결과(audit_<문서>.json)를 검토해 용어정비/<문서>.json 으로 만든다 (2026-10-06).

자동 검사(통과 못 하면 버리고 목록에 남긴다):
- 원문 조각이 실제 문서 글에 있나
- 원문의 숫자가 고친 글에 모두 남아 있나(숫자를 바꾸지 않는다)
- 금지 표현: 「Jev」 단독 · 목 서버 · 가짜 서버 · 줄표(—) · 말줄임표 · 국적 무관류 · 인원 제한(4인)
자동 손질:
- 코덱스가 검토 메모로 넣은 문장(「별도 명시가 필요」 · 「추가 설명 필요」 등)은 문서에 들어가면 안 되므로 지운다
- Claude 검토로 고친 글(OVERRIDE)은 코덱스 글보다 우선한다
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "용어정비"
OUT.mkdir(exist_ok=True)

META_S = (r"별도\s*(명시|설명|확인)|추가\s*(명시|설명|확인)|명시해야|명시가\s*필요|설명이\s*필요(하다|합니다)|설명\s*필요(\.|$)|확인이\s*필요(하다|합니다)|확인\s*필요(\.|$)|"
          r"확인해\s*명시|구체화해야|이 문서만으로|원문에 없어|원문이 ‘|설명해야\s*한다|명시\s*필요")
META = re.compile(META_S)
BAD = [re.compile(r"(?<![A-Za-z가-힣])Jev(?!\s*계열|\s*API|Bench|K5|-Omni|ify|bench)"), re.compile("목 서버|가짜 서버|모방 서버|스텁 서버"),
       re.compile("—|…"), re.compile("국적"), re.compile(r"4\s*인|네 명까지|최대 4명")]
NUM = re.compile(r"\d[\d,.]*\d|\d")


def strip_clause(t: str) -> str:
    """용어 풀이처럼 한 문장짜리 글에서 메모 구절만 뗀다."""
    t = re.sub(r"(,|이며|며|이고)?\s*[^,.]*(" + META_S + r")[^,.]*", "", t).strip()
    return re.sub(r"\s*(,|이며|며|이고)\s*\.?$", ".", t)


def strip_meta(t: str) -> str:
    # 문장(마침표) 또는 표 칸 조각 단위로 메모 문장을 지운다
    parts = re.split(r"(?<=[.다요])\s+", t)
    keep = [p for p in parts if not META.search(p)]
    out = " ".join(keep).strip()
    out = re.sub(r"\s*[,·]\s*$", "", out)
    return out


def curate(key: str, src_text: str, audit: dict, override: dict | None = None, drop: set | None = None):
    override, drop = override or {}, drop or set()
    ok, rejected = [], []
    for i, r in enumerate(audit.get("rewrites", [])):
        old, new = r["old"], override.get(i, r["new"])
        if i in drop:
            rejected.append((i, "Claude 검토로 뺌", old[:60]))
            continue
        if old not in src_text:
            rejected.append((i, "원문 없음", old[:60]))
            continue
        if old.strip().startswith("|"):
            cells = [strip_meta(c.strip()) for c in new.strip().strip("|").split("|")]
            new = "| " + " | ".join(cells) + " |"
        else:
            new = strip_meta(new)
        old_nums = re.sub(r"(정본\s*)?§\s*[\d\-·~, §]+", " ", old)
        lost = [n for n in NUM.findall(old_nums) if n not in new]
        if lost:
            rejected.append((i, f"숫자 빠짐 {lost[:4]}", old[:60]))
            continue
        bad = [b.pattern for b in BAD if b.search(new) and not b.search(old)]
        if bad:
            rejected.append((i, f"금지 표현 {bad}", old[:60]))
            continue
        ok.append({"old": old, "new": new})
    gl = [list(x) for x in audit.get("glossary_rows", []) if list(x)[:1] != ["용어"]]
    gl = [[a, strip_clause(b)] for a, b in gl if not any(bb.search(b) for bb in BAD)]
    (OUT / f"{key}.json").write_text(json.dumps({"rewrites": ok, "glossary": gl}, ensure_ascii=False, indent=1), encoding="utf-8")
    return ok, rejected, gl


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

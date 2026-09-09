"""RAG 코퍼스 인수 검사 — 건수만 세지 않고 **내용의 변별력**을 잰다.

★이 스크립트가 생긴 이유:
  1차 산출물이 "25문서 300섹션"을 만족했는데도 쓸 수 없었다. 모든 섹션이
  공통 보일러플레이트 + 문서별 꼬리문장 2개였고, 정확 해시 중복 검사는 이것을
  0% 중복으로 셌다. → wiki/records/reports/debugs/2026-08-12_1600_RAG코퍼스_섹션이_보일러플레이트로_채워짐.md

  검증되지 않는 요구는 지켜지지 않는다. 그래서 근사 중복을 여기서 잰다.

    python -m scripts.check_corpus
"""

from __future__ import annotations

import itertools
import json
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

KNOWLEDGE = REPO_ROOT / "knowledge"
DOCUMENTS = KNOWLEDGE / "documents"
MANIFEST = KNOWLEDGE / "manifest.json"

# ── 인수 기준 ────────────────────────────────────────────────────────
# 건수는 config/guardrails.yaml (rag.*) 이 정한다. 내용 기준은 여기서 정한다.
MAX_INTRA_DOC_SENTENCE_REPEAT = 1  # 한 문서 안에서 같은 문장이 두 번 나오면 실패
MAX_CROSS_DOC_JACCARD = 0.25  # 같은 제목 섹션의 문서 간 6-gram Jaccard 평균 상한
MAX_GLOBAL_MEDIAN_JACCARD = 0.25  # ★제목과 무관하게 전체 청크 쌍의 중앙 유사도 상한
MAX_SHARED_GRAM_TYPES = 20  # 청크 절반 이상이 공유하는 6-gram 종류 수 상한 (정형 문구 탐지)
MAX_SHARED_TITLE_RATIO = 0.5  # 한 섹션 제목이 전체 문서의 절반을 넘게 쓰이면 템플릿이다
MIN_CHUNK_CHARS = 200  # 청크 본문 길이 하한 (공백 제외). ★짧게 써서 유사도를 낮추는 것을 막는다
MAX_CHUNK_CHARS = 600  # 상한 — 길면 토큰 예산을 먹고 lost-in-the-middle 이 온다
MAX_UNDERLENGTH_RATIO = 0.05  # 하한 미달 청크 허용 비율
MIN_DOCS_WITH_NUMBERS = 0.9  # 구체 수치(일/시간/금액/%)를 가진 문서 비율 하한
MIN_SECTIONS_WITH_NUMBERS = 0.4  # 구체 수치를 가진 섹션 비율 하한

# ── ★슬롯 템플릿 탐지 (2026-08-17 추가) ──────────────────────────────
# 기존 검사가 **원리적으로 통과시킨** 유형이 있었다:
#
#   "...에서 [A]와 [B] 기준값은 X과 Y이며 Z 여부 및 W를 기록한다. 이번 단계는..."
#
# 슬롯만 바꿔 끼운 기계 템플릿이다. 실측: `기준값은` 288/301(95.7%),
# `여부 및` 288/301, `를 기록한다` 289/301.
#
# 왜 안 걸렸나 —
#   · 6-gram 중앙 유사도: 슬롯 값이 달라 **쌍별로는 낮다** (0.032)
#   · MAX_SHARED_GRAM_TYPES: "절반 이상" 기준인데 6-gram 이 슬롯에 끊긴다
#   · 문서 내 문장 반복: 슬롯이 달라 **완전 일치가 아니다**
#
# 그래서 **더 긴 조각을 더 낮은 임계로** 본다. 통과율을 낮추는 방향이다.
TEMPLATE_GRAM = 8  # 정형 문구 탐지용 n-gram 길이 (6 보다 길게 — 슬롯 사이를 넘어간다)
MAX_TEMPLATE_CHUNK_RATIO = 0.30  # 한 조각이 이 비율을 넘는 청크에 나오면 템플릿이다
MAX_TEMPLATE_TYPES = 0  # ★허용하지 않는다. 하나라도 나오면 실패

# ── ★조사 검사 (2026-08-17 추가) ─────────────────────────────────────
# 슬롯에 명사를 꽂으면서 **받침 유무를 보지 않으면** 조사가 깨진다.
# 실측 132건: `17시과`(→시와) `알림를`(→알림을) `기한를`(→기한을) `요청를`(→요청을).
# 고객 응대 자료로 쓸 수 없는 품질인데 기존 게이트에는 검사 항목 자체가 없었다.
MAX_PARTICLE_ERRORS = 0

#: 앞 글자의 받침 유무로 갈리는 조사 쌍 — (받침 있을 때, 받침 없을 때)
#
# ★`은/는`·`이/가`·`으로/로` 는 **뺐다.** 한국어 어미와 충돌해 오탐이 쏟아진다 —
#   `있는`→`있은`, `없는`→`없은`, `사실로`→`사실으로` 처럼 관형형·부사형을
#   조사로 잘못 읽는다(첫 구현에서 458건 중 대부분이 이것이었다).
#   ★게이트는 **틀린 것을 잡아야지 맞는 것을 틀렸다고 하면 안 된다.**
#   실제로 깨져 있던 `과/와`·`을/를` 만 검사한다.
PARTICLE_PAIRS = (("과", "와"), ("을", "를"))

# ★받침 유무만으로는 "명사 어미"와 "조사"를 구분할 수 없다 — 2026-08-17 발견.
#   `초과`(『초』+명사 어미 『과』, 받침 없음)를 『초』+조사 『과』로 오인해
#   `초와`로 고치라고 잘못 지적했다. 코퍼스에 실제로 나오는, 받침 없는 글자
#   뒤에 『과』/『을』이 붙는 한자어 명사를 예외로 둔다. 조사 검사는
#   "틀린 것을 잡아야지 맞는 것을 틀렸다고 하면 안 된다"는 원칙을 그대로 지킨다.
PARTICLE_WORD_EXCEPTIONS = {
    "초과", "결과", "효과", "성과", "경과", "부과", "교과", "여과",
    "사과", "분과", "백과", "통과", "인과", "학과", "가을",
}

# ★쇼핑몰 CS 도메인. sample(구독·결제)에서 갈아 끼운 부분이다
#   (`wiki/records/handoff/10_도메인_교체_가이드.md` §1-4).
#   합이 guardrails 의 rag.document_count(25) 와 같아야 한다.
SCOPE_PLAN = {
    "order": 5,        # 주문 확인·변경·취소·상태·결제수단
    "shipping": 5,     # 배송 기간·지연·분실·주소 변경·부재
    "return": 4,       # 반품 기한·비용·불가 품목·절차
    "exchange": 3,     # 교환 기한·절차·불가
    "refund": 4,       # 환불 기한·수단·부분 환불·지연
    "support": 2,      # 접수·에스컬레이션
    "incident": 2,     # 시스템 장애·대량 배송 지연
}

# 시나리오가 근거로 삼아야 할 표현.
# ★이것이 없으면 코퍼스가 "그럴듯하지만 우리 시나리오에 답하지 못하는" 글이 된다.
SCENARIO_PROBES = {
    # 시나리오1 — 배송완료로 찍혔는데 고객은 받지 못했다
    "시나리오1 배송완료 표시와 미수령": r"(배송\s*완료|수령\s*완료).{0,40}(받지|미수령|분실)",
    "시나리오1 조사 기한(숫자)": r"\d+\s*(일|영업일)\s*(이내|이후|안)",
    # 시나리오2 — 주문 수량보다 많은 반품 요청
    "시나리오2 수량 상한": r"(반품|교환).{0,40}수량.{0,40}(초과|넘|이내|이하)",
    "시나리오2 진단 순서": r"(진단|확인)\s*(순서|절차|단계)",
    # 공통 — 쓰기는 승인을 거친다
    "승인 없이 실행 금지": r"승인\s*(없이|전에는).{0,40}(실행|처리)",
}

NUMBER_PATTERN = re.compile(r"\d+\s*(일|영업일|시간|분|초|%|퍼센트|원|건|회|개월|년)")

failures: list[str] = []
notes: list[str] = []


def fail(message: str) -> None:
    failures.append(message)


def note(message: str) -> None:
    notes.append(message)


def char_grams(text: str, n: int = 6) -> set[str]:
    stripped = re.sub(r"\s+", "", text)
    return {stripped[i : i + n] for i in range(max(0, len(stripped) - n + 1))}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def split_sections(text: str) -> list[tuple[str, str]]:
    parts = re.split(r"^## ", text, flags=re.M)[1:]
    out = []
    for part in parts:
        lines = part.split("\n")
        out.append((lines[0].strip(), "\n".join(lines[1:]).strip()))
    return out


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?]\s|\n", text) if len(s.strip()) > 15]


def main() -> int:
    from app.core.settings import get_guardrails

    guardrails = get_guardrails()
    want_docs = guardrails.get("rag.document_count")
    chunk_min = guardrails.get("rag.chunk_total_min")
    chunk_max = guardrails.get("rag.chunk_total_max")
    per_min = guardrails.get("rag.chunks_per_document_min")
    per_max = guardrails.get("rag.chunks_per_document_max")

    if not DOCUMENTS.is_dir():
        print(f"[FAIL] 코퍼스 디렉터리 없음: {DOCUMENTS}")
        return 1

    files = sorted(DOCUMENTS.glob("*.md"))
    docs: dict[str, list[tuple[str, str]]] = {}
    scopes: Counter[str] = Counter()

    for path in files:
        text = path.read_text(encoding="utf-8")
        docs[path.name] = split_sections(text)
        match = re.search(r"^scope:\s*(\S+)", text, flags=re.M)
        if match:
            scopes[match.group(1)] += 1
        else:
            fail(f"{path.name}: frontmatter 에 scope 가 없다")

    # ── 1. 건수 (계약: guardrails rag.*) ─────────────────────────────
    if len(files) != want_docs:
        fail(f"문서 수 {len(files)} != {want_docs}")
    total_sections = sum(len(v) for v in docs.values())
    if not (chunk_min <= total_sections <= chunk_max):
        fail(f"총 섹션 {total_sections} 이 {chunk_min}~{chunk_max} 밖")
    for name, secs in docs.items():
        if not (per_min <= len(secs) <= per_max):
            fail(f"{name}: 섹션 {len(secs)} 이 {per_min}~{per_max} 밖")
    note(f"문서 {len(files)} / 총 섹션 {total_sections}")

    # ── 2. scope 배분 ────────────────────────────────────────────────
    if dict(scopes) != SCOPE_PLAN:
        fail(f"scope 배분 불일치: 실측 {dict(sorted(scopes.items()))} != 계약 {SCOPE_PLAN}")
    else:
        note(f"scope 배분 일치: {dict(sorted(scopes.items()))}")

    # ── 3. ★문서 내 문장 반복 ────────────────────────────────────────
    worst_repeat = 0
    for name, secs in docs.items():
        counter: Counter[str] = Counter()
        for _title, body in secs:
            counter.update(set(sentences(body)))
        if counter:
            sentence, count = counter.most_common(1)[0]
            worst_repeat = max(worst_repeat, count)
            if count > MAX_INTRA_DOC_SENTENCE_REPEAT:
                fail(
                    f"{name}: 같은 문장이 {count}개 섹션에 반복된다 "
                    f'— "{sentence[:45]}..."'
                )
    note(f"문서 내 최대 문장 반복: {worst_repeat} (상한 {MAX_INTRA_DOC_SENTENCE_REPEAT})")

    # ── 4. ★섹션 제목 템플릿화 ───────────────────────────────────────
    title_counts: Counter[str] = Counter()
    for secs in docs.values():
        title_counts.update({t for t, _ in secs})
    if files:
        for title, count in title_counts.most_common(3):
            ratio = count / len(files)
            if ratio > MAX_SHARED_TITLE_RATIO:
                fail(
                    f"섹션 제목 '{title}' 이 {count}/{len(files)} 문서에 쓰인다 "
                    f"({ratio:.0%} > {MAX_SHARED_TITLE_RATIO:.0%}) — 템플릿 채우기다"
                )
        top = title_counts.most_common(1)[0]
        note(f"최다 공유 섹션 제목: '{top[0]}' {top[1]}/{len(files)}문서")

    # ── 5. ★같은 제목 섹션의 문서 간 근사 중복 ───────────────────────
    by_title: dict[str, list[str]] = defaultdict(list)
    for secs in docs.values():
        for title, body in secs:
            by_title[title].append(body)
    cross_sims: list[float] = []
    for title, bodies in by_title.items():
        if len(bodies) < 3:
            continue
        grams = [char_grams(b) for b in bodies]
        sims = [
            jaccard(a, b) for a, b in itertools.islice(itertools.combinations(grams, 2), 80)
        ]
        if not sims:
            continue
        mean = statistics.mean(sims)
        cross_sims.append(mean)
        if mean > MAX_CROSS_DOC_JACCARD:
            fail(
                f"섹션 '{title}' 의 문서 간 유사도 평균 {mean:.2f} > {MAX_CROSS_DOC_JACCARD} "
                "— 내용이 사실상 같다"
            )
    if cross_sims:
        note(f"문서 간 섹션 유사도 평균의 평균: {statistics.mean(cross_sims):.2f}")

    # ── 5b. ★전체 청크 쌍 유사도 ────────────────────────────────────
    # 5번 검사는 "같은 제목이 3개 문서 이상"일 때만 돈다. 제목을 전부 다르게 지으면
    # 그 검사가 통째로 건너뛰어진다 — 2026-08-12 v2 에서 실제로 그렇게 됐다.
    # 그래서 제목과 무관하게 **모든 청크 쌍**을 표본으로 재는 검사를 따로 둔다.
    all_bodies = [re.sub(r"\s+", "", b) for secs in docs.values() for _t, b in secs]
    if len(all_bodies) >= 20:
        rng = random.Random(7)
        indexes = list(itertools.combinations(range(len(all_bodies)), 2))
        sample = rng.sample(indexes, min(3000, len(indexes)))
        grams = [char_grams(b) for b in all_bodies]
        sims = [jaccard(grams[i], grams[j]) for i, j in sample]
        mean_sim = statistics.mean(sims)
        median_sim = statistics.median(sims)
        note(f"전체 청크 쌍 유사도: 평균 {mean_sim:.3f} / 중앙 {median_sim:.3f}")
        if median_sim > MAX_GLOBAL_MEDIAN_JACCARD:
            fail(
                f"전체 청크 쌍 유사도 중앙값 {median_sim:.3f} > {MAX_GLOBAL_MEDIAN_JACCARD} "
                "— 모든 청크가 서로 비슷하면 top-k 검색이 변별력을 잃는다"
            )
        # 공통 꼬리·머리 템플릿 탐지: 절반 이상의 청크에 공통인 6-gram 종류 수
        counter: Counter[str] = Counter()
        for gram_set in grams:
            counter.update(gram_set)
        half = len(all_bodies) // 2
        shared = [g for g, c in counter.items() if c >= half]
        note(f"청크 절반 이상에 공통인 6-gram 종류: {len(shared)}")
        if len(shared) > MAX_SHARED_GRAM_TYPES:
            fail(
                f"청크 절반 이상이 공유하는 6-gram 이 {len(shared)}종 "
                f"> {MAX_SHARED_GRAM_TYPES} — 정형 문구가 본문에 박혀 있다"
            )

    # ── 5a. ★청크 길이 ──────────────────────────────────────────────
    # 유사도 검사만 두면 "짧게 쓰기"로 통과할 수 있다 — 2026-08-12 v4 에서 실제로 그랬다
    # (평균 56자, 300/300 이 하한 미달인데 유사도는 0.000 이었다).
    # 근거로 인용되려면 그 자체로 말이 되는 길이여야 한다.
    lengths = [len(re.sub(r"\s+", "", b)) for secs in docs.values() for _t, b in secs]
    if lengths:
        under = [n for n in lengths if n < MIN_CHUNK_CHARS]
        over = [n for n in lengths if n > MAX_CHUNK_CHARS]
        note(
            f"청크 길이(공백 제외): 평균 {statistics.mean(lengths):.0f} "
            f"최소 {min(lengths)} 최대 {max(lengths)}"
        )
        ratio = len(under) / len(lengths)
        if ratio > MAX_UNDERLENGTH_RATIO:
            fail(
                f"{MIN_CHUNK_CHARS}자 미만 청크가 {len(under)}/{len(lengths)} ({ratio:.0%}) "
                f"> {MAX_UNDERLENGTH_RATIO:.0%} — 짧은 청크는 그 자체로 근거가 되지 못한다"
            )
        if over:
            fail(f"{MAX_CHUNK_CHARS}자 초과 청크 {len(over)}건 — 토큰 예산을 먹는다")

    # ── 5c. ★지표 우회(gaming) 탐지 ─────────────────────────────────
    # 2026-08-12 v3 에서 실제로 일어난 일: 유사도 검사를 통과하려고 문장마다
    # (s1-625) · (case-6024) · [제목 / ref-6024] 같은 무작위 토큰을 주입했다.
    # n-gram 유사도는 떨어졌지만 내용은 오히려 나빠졌다.
    # ★지표를 낮추는 것과 글을 좋게 만드는 것은 다르다. 그래서 우회 자체를 검사한다.
    gaming_patterns = {
        "무작위 참조 토큰 (s1-625) 형태": re.compile(r"\([a-z]{1,6}[-_]\d{2,6}\)"),
        "대괄호 제목+참조 [.. / ref-1234]": re.compile(r"\[[^\]]{4,60}/\s*[a-z]{2,6}[-_]\d{2,6}\]"),
        "발명된 자리표시 용어 '기준 토큰'": re.compile(r"기준\s*토큰"),
        "본문 속 rule_/ref- 식별자": re.compile(r"\b(rule|ref)[-_]\d{1,6}\b"),
    }
    for label, pattern in gaming_patterns.items():
        hits = sum(1 for b in all_bodies if pattern.search(b)) if all_bodies else 0
        if hits:
            fail(
                f"지표 우회 의심 — {label} 가 {hits}/{len(all_bodies)} 청크에 있다. "
                "유사도를 낮추려고 넣은 토큰은 근거가 아니다"
            )

    # 길이가 긴 공통 문구 탐지 (6-gram 임계를 아슬아슬하게 피하는 꼬리 잡기)
    if all_bodies:
        phrase_counter: Counter[str] = Counter()
        for body in all_bodies:
            phrase_counter.update({body[i : i + 14] for i in range(max(0, len(body) - 13))})
        threshold = int(len(all_bodies) * 0.3)
        common_phrases = [p for p, c in phrase_counter.items() if c > threshold]
        if common_phrases:
            worst = max(common_phrases, key=lambda p: phrase_counter[p])
            fail(
                f"청크의 30% 초과가 공유하는 14자 문구가 {len(common_phrases)}종 있다 "
                f'— 예: "{worst}" ({phrase_counter[worst]}/{len(all_bodies)})'
            )

    # ── 6. ★구체 수치 ───────────────────────────────────────────────
    docs_with_numbers = 0
    sections_with_numbers = 0
    for _name, secs in docs.items():
        hits = sum(1 for _t, b in secs if NUMBER_PATTERN.search(b))
        sections_with_numbers += hits
        if hits:
            docs_with_numbers += 1
    if files:
        doc_ratio = docs_with_numbers / len(files)
        sec_ratio = sections_with_numbers / max(1, total_sections)
        note(f"구체 수치 포함: 문서 {doc_ratio:.0%} / 섹션 {sec_ratio:.0%}")
        if doc_ratio < MIN_DOCS_WITH_NUMBERS:
            fail(f"구체 수치를 가진 문서가 {doc_ratio:.0%} < {MIN_DOCS_WITH_NUMBERS:.0%}")
        if sec_ratio < MIN_SECTIONS_WITH_NUMBERS:
            fail(f"구체 수치를 가진 섹션이 {sec_ratio:.0%} < {MIN_SECTIONS_WITH_NUMBERS:.0%}")

    # ── 6-A. ★슬롯 템플릿 ───────────────────────────────────────────
    # 6-gram 유사도가 낮아도 **더 긴 조각이 많은 청크에 공통**이면 틀을 돌려쓴 것이다.
    chunk_texts = [b for secs in docs.values() for _t, b in secs]
    chunk_owner = [name for name, secs in docs.items() for _s in secs]
    if chunk_texts:
        appearance: Counter[str] = Counter()
        for text in chunk_texts:
            stripped = re.sub(r"\s", "", text)
            appearance.update({stripped[i:i + TEMPLATE_GRAM]
                               for i in range(max(0, len(stripped) - TEMPLATE_GRAM + 1))})
        limit = MAX_TEMPLATE_CHUNK_RATIO * len(chunk_texts)
        templates = sorted(((g, c) for g, c in appearance.items() if c > limit),
                           key=lambda x: -x[1])
        note(f"청크 {MAX_TEMPLATE_CHUNK_RATIO:.0%} 초과에 공통인 {TEMPLATE_GRAM}-gram: "
             f"{len(templates)}종 (상한 {MAX_TEMPLATE_TYPES})")
        if len(templates) > MAX_TEMPLATE_TYPES:
            worst = ", ".join(f"'{g}'({c}/{len(chunk_texts)})" for g, c in templates[:4])
            fail(f"슬롯 템플릿으로 보이는 공통 문구 {len(templates)}종 — 예: {worst}")

    # ── 6-B. ★조사 ─────────────────────────────────────────────────
    # 앞 글자의 받침 유무로 조사가 갈린다. 슬롯에 명사를 꽂으며 이것을 놓치면 깨진다.
    def _has_final(ch: str) -> bool | None:
        if not ("가" <= ch <= "힣"):
            return None
        return (ord(ch) - 0xAC00) % 28 != 0

    particle_errors: list[str] = []
    for name, text in zip(chunk_owner, chunk_texts):
        for after_final, after_open in PARTICLE_PAIRS:
            for particle, expects_final in ((after_final, True), (after_open, False)):
                for m in re.finditer(rf"([가-힣]){re.escape(particle)}(?![가-힣])", text):
                    if m.group(0) in PARTICLE_WORD_EXCEPTIONS:
                        continue
                    final = _has_final(m.group(1))
                    if final is None or final == expects_final:
                        continue
                    correct = after_open if final is False else after_final
                    particle_errors.append(f"{name}: '{m.group(1)}{particle}' → '{m.group(1)}{correct}'")
    note(f"조사 오류: {len(particle_errors)}건 (상한 {MAX_PARTICLE_ERRORS})")
    if len(particle_errors) > MAX_PARTICLE_ERRORS:
        fail(f"조사 오류 {len(particle_errors)}건 — 예: {'; '.join(particle_errors[:4])}")

    # ── 7. 시나리오 근거 ────────────────────────────────────────────
    corpus_text = "\n".join(p.read_text(encoding="utf-8") for p in files)
    for label, pattern in SCENARIO_PROBES.items():
        if not re.search(pattern, corpus_text):
            fail(f"시나리오 근거 없음: {label}")

    # ── 8. manifest 대조 ────────────────────────────────────────────
    if not MANIFEST.is_file():
        fail(f"manifest 없음: {MANIFEST}")
    else:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        entries = data.get("documents", [])
        if len(entries) != len(files):
            fail(f"manifest 문서 수 {len(entries)} != 파일 수 {len(files)}")
        ids = [e.get("document_id") for e in entries]
        if len(ids) != len(set(ids)):
            fail("manifest 에 document_id 중복이 있다")
        for entry in entries:
            target = KNOWLEDGE / entry.get("file", "")
            if not target.is_file():
                fail(f"manifest 가 없는 파일을 가리킨다: {entry.get('file')}")
                continue
            actual = len(split_sections(target.read_text(encoding="utf-8")))
            if entry.get("section_count") != actual:
                fail(
                    f"{entry.get('document_id')}: section_count 선언 "
                    f"{entry.get('section_count')} != 실측 {actual}"
                )

    # ── 출력 ────────────────────────────────────────────────────────
    print("=" * 78)
    print("RAG 코퍼스 인수 검사")
    print("=" * 78)
    for line in notes:
        print(f"  · {line}")
    print("-" * 78)
    if failures:
        for line in failures:
            print(f"  [FAIL] {line}")
        print("-" * 78)
        print(f"실패 {len(failures)}건 — 인수 불가")
        return 1
    print("  전 항목 통과 — 인수 가능")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

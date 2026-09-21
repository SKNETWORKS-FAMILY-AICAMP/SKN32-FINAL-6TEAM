"""Verify the v5 Definition of Done against evidence and the test suite.

This checker is intentionally read-only with respect to ``wiki/records/evidence``.
It reports the state of every DoD item and returns non-zero until all items
have an explicit passing judgement and the test suite has no failures.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "wiki" / "records" / "evidence"

ITEMS = (
    ("원본 v4 hash 불변", "DoD-01"),
    ("상태전이 규약", "DoD-02"),
    ("동시성·append-only·replay", "DoD-03"),
    ("checkpoint 분리", "DoD-04"),
    ("ContextPack ≤ 12,000 token", "DoD-05"),
    ("정책/FAQ 25건·300~400 chunk", "DoD-06"),
    ("tenant/customer scope·PII redaction", "DoD-07"),
    ("TeamModule·manifest 호환", "DoD-08"),
    ("인라인 분류", "DoD-09"),
    ("일일 배치 report", "DoD-10"),
    ("action·approval·idempotency·unknown", "DoD-11"),
    ("outbox 원자성·worker replay", "DoD-12"),
    ("MVP REST + MCP 3 contract", "DoD-13"),
    ("API key scope", "DoD-14"),
    ("A/B/Proposed·holdout 보존", "DoD-15"),
    ("bootstrap CI·McNemar·한계", "DoD-16"),
    ("마일스톤 gate·기능 동결", "DoD-17"),
    ("Case UI·trace·approval·VOC", "DoD-18"),
    # ── v7 §27 신규 (19~28) ──────────────────────────────────────────────
    # ★기준선이 v6 → v7 로 바뀌며 DoD 가 18 → 28 로 늘었다.
    #   ★없는 것은 없다고 적는다. evidence 가 없으면 여기서 미작성으로 잡힌다.
    ("LOCAL/A2A 동일 TeamResult 정규화", "DoD-19"),
    ("TeamExecutorPort 교체 시 Controller 불변", "DoD-20"),
    ("SqlGraphAdapter 관계 질의 3종", "DoD-21"),
    ("Team 직접 Tool 호출 금지", "DoD-22"),
    ("consumer at-least-once idempotency", "DoD-23"),
    ("ActionProposal 근거 대조·실행 차단", "DoD-24"),
    ("degraded Context 자동 실행 금지", "DoD-25"),
    ("A2A Catalog Verification 왕복", "DoD-26"),
    ("A2A 실패·타임아웃·취소·인증", "DoD-27"),
    ("파인튜닝 경로와 방어 지표", "DoD-28"),
    # ── v8 §27 신규 (29) ─────────────────────────────────────────────────
    ("Response Generation & Review GEN→REV·재시도·PII 검증", "DoD-29"),
)


@dataclass(frozen=True)
class EvidenceResult:
    path: Path | None
    judgement: str | None
    has_reproduction: bool
    has_actual_output: bool


def _judgement(text: str) -> str | None:
    # ★"미착수" 를 판정으로 인정한다. 착수하지 않은 것과 문서가 덜 된 것은 다르다 —
    #   전에는 미착수 문서가 INCOMPLETE 로 나와 "문서를 잘못 썼다" 처럼 읽혔다.
    match = re.search(r"판정\s*:\s*(?:\*\*)?\s*(통과|부분\s*통과|미통과|미착수)\s*(?:\*\*)?", text)
    if not match:
        return None
    return re.sub(r"\s+", "", match.group(1))


def _evidence(prefix: str) -> EvidenceResult:
    matches = sorted(EVIDENCE_DIR.glob(f"{prefix}_*.md"))
    if not matches:
        return EvidenceResult(None, None, False, False)
    path = matches[0]
    text = path.read_text(encoding="utf-8")
    fenced_blocks = re.findall(r"```(?:[^\n]*)\n(.*?)```", text, flags=re.DOTALL)
    has_reproduction = bool(fenced_blocks)
    output_pattern = re.compile(
        r"실제\s*출력|실측\s*(?:결과|출력)|실제\s*결과|actual\s*output",
        re.IGNORECASE,
    )
    has_actual_output = any(output_pattern.search(block) for block in fenced_blocks)
    # A heading immediately preceding a fenced output block is also accepted;
    # the measured block itself remains mandatory.
    if not has_actual_output:
        has_actual_output = bool(
            re.search(
                r"(?:실제\s*출력|실측\s*(?:결과|출력)|실제\s*결과)[^`\n]*\n\s*```",
                text,
                flags=re.IGNORECASE,
            )
        )
    return EvidenceResult(path, _judgement(text), has_reproduction, has_actual_output)


def _run_tests() -> tuple[str, int, int, int, int, int]:
    # ★경로를 주지 않는다. `pytest tests` 로 부르면 **`eval/tests/` 14건이
    #   조용히 빠진다**(2026-09-02 실측: 542 vs 556). 빠지던 것 중에
    #   `eval/tests/test_holdout_labeling.py` — DoD-15, 즉 RC 를 막고 있는 바로
    #   그 항목의 라벨링 도구 테스트가 있었다. **DoD 를 검증하는 스크립트가
    #   차단 항목의 테스트를 한 번도 안 돌리고 "통과"를 세고 있었다.**
    #   같은 결함이 `check_release_gate.py` 에도 있었고 같은 날 함께 고쳤다.
    #   `CLAUDE.md` §6 이 정한 정본 전체 실행 명령도 경로 없는 `python -m pytest -q` 다.
    command = [sys.executable, "-m", "pytest", "-q"]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    def count(name: str) -> int:
        match = re.search(rf"(\d+)\s+{name}", output)
        return int(match.group(1)) if match else 0
    passed = count("passed")
    skipped = count("skipped")
    failed = count("failed")
    errors = count("errors?")
    return output, passed, skipped, failed, errors, completed.returncode


def main() -> int:
    print("=" * 64)
    print(f"A-COP DoD 검증  (v8 §27 · {len(ITEMS)}항목, 1~28은 v7 번호 보존)")
    print("=" * 64)
    print(f"{' #':>3}  {'항목':<36} {'evidence':<8} {'판정':<8} 결과")

    results: list[tuple[str, str, EvidenceResult, str]] = []
    for number, (label, prefix) in enumerate(ITEMS, 1):
        evidence = _evidence(prefix)
        if evidence.path is None:
            evidence_state, judgement, result = "없음", "-", "MISSING"
        elif evidence.judgement == "미착수":
            # ★착수하지 않았다고 **적은** 것은 정직한 상태다. 실측을 요구하지 않는다 —
            #   없는 실행의 출력을 만들어 내라는 요구가 되기 때문이다.
            evidence_state, judgement, result = "있음", "미착수", "NOT STARTED"
        elif not (evidence.has_reproduction and evidence.has_actual_output):
            evidence_state, judgement, result = "있음", evidence.judgement or "-", "INCOMPLETE"
        else:
            evidence_state = "있음"
            judgement = evidence.judgement or "-"
            result = "OK" if judgement == "통과" else "NOT PASS"
        print(f"{number:>2}  {label:<36} {evidence_state:<8} {judgement:<8} {result}")
        results.append((prefix, label, evidence, result))

    output, passed, skipped, failed, errors, returncode = _run_tests()
    print("-" * 64)
    evidence_count = sum(e.path is not None for _, _, e, _ in results)
    pass_count = sum(e.judgement == "통과" and e.has_reproduction and e.has_actual_output for _, _, e, _ in results)
    partial_count = sum(e.judgement == "부분통과" for _, _, e, _ in results)
    notstarted_count = sum(e.judgement == "미착수" for _, _, e, _ in results)
    missing = [prefix for prefix, _, e, _ in results if e.path is None]
    print(f"evidence 있음 {evidence_count}/{len(ITEMS)} · 통과 {pass_count} · "
          f"부분통과 {partial_count} · 미착수 {notstarted_count} · 미작성 {len(missing)}")
    print(f"테스트: {passed} passed, {skipped} skipped, {failed + errors} failed")
    print("-" * 64)
    if missing:
        print(f"★미작성 {len(missing)}항목: {', '.join(missing)}")
    if skipped:
        print("★skipped가 있어 경고: skip은 통과로 세지 않습니다")
    if output and not re.search(r"\d+\s+passed", output):
        print("★pytest 출력:")
        print(output)

    all_pass = all(
        e.path is not None and e.has_reproduction and e.has_actual_output and e.judgement == "통과"
        for _, _, e, _ in results
    )
    return 0 if all_pass and failed == 0 and errors == 0 and skipped == 0 and returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

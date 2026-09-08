"""커밋을 실행계획서의 Phase(P0~P10)에 자동으로 대응시킨다.

★이 스크립트가 채우는 구멍: `wiki/records/release_checklist.md` §5-3 의
  "커밋 ↔ Phase 자동 매핑 없음 (사람이 읽어 대조)". DoD-17 이 요구하는
  "각 커밋이 어느 Phase 의 일인지"를 사람이 커밋 메시지를 읽어 판단하던 것을,
  **커밋이 실제로 건드린 경로**로 판정한다. 메시지는 사람이 쓴 주장이고
  경로는 실제로 일어난 일이라, 경로가 더 믿을 만한 근거다.

근거 문서 둘:

    wiki/records/handoff/05_분업_규칙.md         스트림별 소유 디렉터리 (경로 → 스트림)
    wiki/records/plans/2026-08-12_1507_...md    P0~P10 절 제목 (스트림 → Phase)

★**소유 표를 파싱하지 않고 여기에 적는다.** 05 번 문서의 S-TEAM 행은
  `order_shipping.py`·`return_exchange.py` 를 가리키는데 두 파일은 이 저장소에
  없다(2026-08-18 도메인 교체로 사라졌고 `CLAUDE.md` 가 그 경위를 적고 있다).
  낡은 표를 파싱하면 낡은 결과가 조용히 나온다. 대신 여기 적고 출처를 밝히며,
  **매핑되지 않는 경로를 조용히 넘기지 않고 세어 보고한다**(`CLAUDE.md` §3).

    python -m scripts.map_commits_to_phase                 # 최근 20개 커밋
    python -m scripts.map_commits_to_phase --range HEAD~50..HEAD
    python -m scripts.map_commits_to_phase --strict        # 미매핑이 있으면 exit 1
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 경로 접두어 → (스트림, Phase). **더 긴 접두어가 이긴다** — `app/modules/`
#: 전체는 S-TEAM(P4)이지만 그 안의 `feedback.py` 하나는 S-VOC(P7)다.
#: 출처: `wiki/records/handoff/05_분업_규칙.md` 소유 표 + 실행계획서 §P0~P10 절 제목.
PATH_OWNERS: tuple[tuple[str, str, str], ...] = (
    # 가장 구체적인 것부터 적을 필요는 없다 — 아래에서 길이순으로 정렬한다.
    ("app/core/", "Claude-Core", "P1"),
    ("app/domain/", "Claude-Core", "P1"),
    ("app/core/context.py", "S-RAG+Claude", "P3"),
    ("app/infrastructure/rag/", "S-RAG", "P3"),
    ("knowledge/", "S-RAG", "P3"),
    ("app/infrastructure/db/", "S-DB", "P2"),
    ("scripts/seed.py", "S-DB", "P2"),
    ("app/modules/", "S-TEAM", "P4"),
    ("app/tools/", "S-TEAM", "P4"),
    ("app/modules/customer_ops/feedback.py", "S-VOC", "P7"),
    ("app/application/feedback_job.py", "S-VOC", "P7"),
    ("scripts/run_daily_feedback.py", "S-VOC", "P7"),
    ("app/application/", "Claude-Core", "P5"),
    ("app/infrastructure/messaging/", "Claude-Core", "P5"),
    ("app/presentation/api/", "S-API", "P6"),
    ("app/presentation/security.py", "S-API", "P6"),
    ("app/presentation/a2a/", "S-API", "P6"),
    ("app/presentation/ui/", "S-UI", "P8"),
    ("eval/", "S-EVAL", "P9"),
    ("prompts/judge/", "S-EVAL", "P9"),
    ("scripts/", "Claude-Core", "P10"),
    ("wiki/records/", "Claude-Core", "P10"),
    ("config/", "Claude-Core", "P10"),
    ("prompts/", "Claude-Core", "P10"),
    # ★조립 지점과 루트 문서. 05 번 문서 소유 표에 `app/composition.py` 가 없다 —
    #   그 표가 쓰인 뒤에 생긴 파일이다. 조립은 P10(통합)의 일이므로 여기 둔다.
    ("app/composition.py", "Claude-Core", "P10"),
    ("app/introspection/", "Claude-Core", "P10"),
    ("CLAUDE.md", "Claude-Core", "P10"),
    ("RULE.md", "Claude-Core", "P10"),
    ("requirements.txt", "Claude-Core", "P10"),
    # 테스트는 대상 코드의 Phase 를 따른다.
    ("tests/unit/core/", "Claude-Core", "P1"),
    ("tests/contract/", "Claude-Core", "P1"),
    ("tests/integration/db/", "S-DB", "P2"),
    ("tests/integration/rag/", "S-RAG", "P3"),
    ("tests/unit/teams/", "S-TEAM", "P4"),
    ("tests/unit/voc/", "S-VOC", "P7"),
    ("tests/integration/controller/", "Claude-Core", "P5"),
    ("tests/integration/messaging/", "Claude-Core", "P5"),
    ("tests/security/", "S-API", "P6"),
    ("tests/integration/api/", "S-API", "P6"),
    ("tests/e2e/", "S-UI", "P8"),
    ("tests/architecture/", "Claude-Core", "P1"),
    ("tests/", "Claude-Core", "P10"),
)

#: 접두어가 긴 것부터 본다.
_OWNERS_BY_SPECIFICITY = tuple(sorted(PATH_OWNERS, key=lambda row: len(row[0]), reverse=True))

#: 저장소 안이지만 어느 Phase 의 산출물도 아닌 것 — 세되 미매핑으로 치지 않는다.
IGNORED_PREFIXES = ("legacy/", ".claude/", ".gitignore", "README.md")


def _git(args: list[str]) -> str:
    # ★`core.quotePath=false` 가 없으면 한글 경로가 `"\355\217\264..."` 로 이스케이프돼
    #   돌아와 접두어 매칭이 통째로 빗나간다. 이 저장소에서 전에도 같은 함정을 밟았다
    #   (`fix(publish) 한글 경로 quotepath 처리`). 이 프로젝트는 문서·리포트 파일명이
    #   대부분 한글이라 이 한 줄이 없으면 결과가 조용히 절반만 맞는다.
    completed = subprocess.run(
        ["git", "-c", "safe.directory=*", "-c", "core.quotePath=false", *args],
        cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True,
    )
    if completed.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} 실패 (exit {completed.returncode}): {completed.stderr.strip()}")
    return completed.stdout


def phase_for_path(path: str) -> tuple[str, str] | None:
    """경로 하나를 (스트림, Phase) 로 판정한다. 모르면 None — 지어내지 않는다."""
    for prefix, stream, phase in _OWNERS_BY_SPECIFICITY:
        if path.startswith(prefix):
            return stream, phase
    return None


def _repo_relative(path: str) -> str | None:
    """workspace 루트 기준 경로를 저장소 기준으로 줄인다. 저장소 밖이면 None."""
    marker = "final_project_cs/"
    if path.startswith(marker):
        return path[len(marker):]
    return None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="커밋을 Phase(P0~P10)에 자동 대응시킨다")
    parser.add_argument("--range", dest="commit_range", default=None,
                        help="git rev 범위 (예: HEAD~50..HEAD). 없으면 --count 개")
    parser.add_argument("--count", type=int, default=20, help="--range 가 없을 때 볼 커밋 수")
    parser.add_argument("--strict", action="store_true",
                        help="Phase 를 못 정한 커밋이 하나라도 있으면 exit 1")
    args = parser.parse_args()

    log_args = ["log", "--format=%h\t%s", "--no-merges"]
    log_args += [args.commit_range] if args.commit_range else [f"-{args.count}"]
    commits = [line.split("\t", 1) for line in _git(log_args).splitlines() if "\t" in line]

    rows: list[tuple[str, str, str, list[str]]] = []
    unmapped_paths: Counter[str] = Counter()
    phase_totals: Counter[str] = Counter()

    for sha, subject in commits:
        names = _git(["show", "--name-only", "--format=", sha]).splitlines()
        phases: Counter[str] = Counter()
        outside = 0
        for raw in names:
            name = raw.strip()
            if not name:
                continue
            relative = _repo_relative(name)
            if relative is None:
                outside += 1
                continue
            if relative.startswith(IGNORED_PREFIXES):
                continue
            found = phase_for_path(relative)
            if found is None:
                unmapped_paths[relative] += 1
                continue
            phases[found[1]] += 1

        if phases:
            ordered = [phase for phase, _ in phases.most_common()]
            verdict = ordered[0] if len(ordered) == 1 else f"{ordered[0]}(+{len(ordered)-1})"
            for phase in ordered:
                phase_totals[phase] += 1
        elif outside:
            verdict = "저장소 밖"
        else:
            verdict = "미정"
        rows.append((sha, verdict, subject, sorted(phases)))

    print(f"커밋 {len(rows)}개 · Phase 자동 매핑 (경로 기준, 커밋 메시지 아님)")
    print()
    for sha, verdict, subject, phases in rows:
        detail = ",".join(phases) if len(phases) > 1 else ""
        suffix = f"  [{detail}]" if detail else ""
        print(f"  {sha}  {verdict:<10} {subject[:64]}{suffix}")

    print()
    print("Phase 별 커밋 수: " + (", ".join(f"{p}={n}" for p, n in sorted(phase_totals.items())) or "없음"))

    undecided = [sha for sha, verdict, _, _ in rows if verdict == "미정"]
    if unmapped_paths:
        print()
        print(f"★어느 Phase 에도 매핑되지 않은 경로 {sum(unmapped_paths.values())}건 "
              f"(고유 {len(unmapped_paths)}개) — 조용히 넘기지 않고 센다:")
        for path, count in unmapped_paths.most_common(15):
            print(f"    {count:>3}x  {path}")
        print("    → PATH_OWNERS 에 넣거나, 산출물이 아니면 IGNORED_PREFIXES 에 넣는다.")
    if undecided:
        print()
        print(f"★Phase 를 정하지 못한 커밋 {len(undecided)}개: " + ", ".join(undecided))

    if args.strict and (undecided or unmapped_paths):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""커밋↔Phase 자동 매핑의 경로 판정 규칙을 고정한다.

★`docs/release_checklist.md` §5-3 이 "커밋 ↔ Phase 자동 매핑 없음(사람이 읽어
  대조)"으로 남겨 뒀던 항목을 `scripts/map_commits_to_phase.py` 가 채운다.
  여기서는 git 이력에 의존하지 않는 **순수 판정 규칙**만 검사한다 — 커밋 이력은
  세션마다 달라져서 테스트가 흔들린다.
"""
from __future__ import annotations

import pytest

from scripts.map_commits_to_phase import IGNORED_PREFIXES, PATH_OWNERS, phase_for_path


@pytest.mark.parametrize(
    "path,expected_phase",
    [
        ("app/core/registry.py", "P1"),
        ("app/infrastructure/db/repository.py", "P2"),
        ("app/infrastructure/rag/retriever.py", "P3"),
        ("app/modules/customer_ops/return_refund.py", "P4"),
        ("app/application/controller.py", "P5"),
        ("app/presentation/api/cases.py", "P6"),
        ("app/presentation/ui/theme.py", "P8"),
        ("eval/runners/proposed.py", "P9"),
        ("docs/release_checklist.md", "P10"),
        ("app/composition.py", "P10"),
    ],
)
def test_known_paths_map_to_their_owning_phase(path, expected_phase):
    found = phase_for_path(path)
    assert found is not None, f"{path} 가 어느 Phase 에도 매핑되지 않는다"
    assert found[1] == expected_phase


# invariant 성격의 검사 — 더 구체적인 경로가 덜 구체적인 것을 이겨야 한다.
def test_more_specific_prefix_wins_over_the_broader_one():
    """`app/modules/` 전체는 S-TEAM(P4)이지만 그 안 `feedback.py` 하나는 S-VOC(P7)다."""
    assert phase_for_path("app/modules/customer_ops/return_refund.py")[1] == "P4"
    assert phase_for_path("app/modules/customer_ops/feedback.py")[1] == "P7"
    assert phase_for_path("app/application/controller.py")[1] == "P5"
    assert phase_for_path("app/application/feedback_job.py")[1] == "P7"


def test_unknown_path_returns_none_instead_of_guessing():
    """★모르면 None 이다. 아무 Phase 로나 떨어뜨리면 미매핑이 조용히 사라진다."""
    assert phase_for_path("some/brand/new/directory/thing.py") is None


def test_every_declared_prefix_is_reachable():
    """더 긴 접두어에 완전히 가려져 절대 선택될 수 없는 규칙이 없어야 한다.

    ★같은 접두어를 두 번 적거나, 짧은 규칙을 긴 규칙 뒤에 잘못 두면 그 규칙은
      죽은 규칙이 된다 — 죽은 채로 남으면 나중에 소유를 바꿔도 반영되지 않는다.
    """
    prefixes = [row[0] for row in PATH_OWNERS]
    assert len(prefixes) == len(set(prefixes)), "PATH_OWNERS 에 중복 접두어가 있다"
    for prefix, _, phase in PATH_OWNERS:
        probe = prefix if not prefix.endswith("/") else prefix + "probe.py"
        found = phase_for_path(probe)
        assert found is not None and found[1] == phase, (
            f"{prefix} 규칙이 더 긴 다른 규칙에 가려 도달하지 않는다 (실제: {found})")


def test_ignored_prefixes_are_not_silently_phase_mapped():
    """무시 목록은 '매핑됨'이 아니라 '산출물이 아님'이다 — 둘을 섞지 않는다."""
    for prefix in IGNORED_PREFIXES:
        assert not any(prefix.startswith(owned) for owned, _, _ in PATH_OWNERS), (
            f"{prefix} 가 무시 목록과 소유 목록에 동시에 있다")

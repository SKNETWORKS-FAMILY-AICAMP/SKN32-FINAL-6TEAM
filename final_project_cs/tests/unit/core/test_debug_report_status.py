"""결함 리포트가 열렸는지 닫혔는지를 **읽어서 알 수 있게** 유지한다.

★2026-09-03 실측: `docs/reports/debugs/` 26건 중 상태를 기계로 셀 수 있는
  것이 없었다. `RULE.md` §4.1 이 "고쳤는지와 무관하게 먼저 기록한다" 고 해서
  발견 기록은 잘 남는데, **고친 뒤 되돌아와 닫는 단계가 없었다.** 그래서 각
  문서의 `- 상태:` 줄이 작성 시점("미수정 → 수정 발주함")에 멈춰 있었고,
  `CLAUDE.md` 상태표가 **해결로 인용하는 문서 3건**까지 "미해결" 로 보였다.
  경위: `docs/reports/2026-09-03_결함리포트_상태를_읽을_수_없다.md`

  17건을 하나씩 코드로 확인해 닫고 표기를 통일했다. 이 검사는 **다시
  흐트러지지 않게** 한다 — 표기가 없으면 여기서 실패한다.

★**옛 `- 상태:` 줄을 지우라고 요구하지 않는다.** 그건 발견 시점의 사실이고
  그 자체가 기록이다. 요구하는 것은 그 위에 **지금 상태를 한 줄로 얹는 것**뿐이다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

DEBUG_DIR = Path(__file__).resolve().parents[3] / "docs" / "reports" / "debugs"

#: 문서 어디든 이 형태가 한 번 나오면 상태가 표기된 것으로 본다.
#:  "## 해결됨", "## 해결됨 (2026-09-03)", "## 해결됨 (2026-09-01, 부분) — …" 등.
STATUS_RESOLVED = re.compile(r"^##\s*해결됨", re.MULTILINE)
STATUS_OPEN = re.compile(r"^##\s*미해결", re.MULTILINE)

REPORTS = sorted(DEBUG_DIR.glob("*.md"))


def test_the_debug_report_directory_is_not_empty():
    """★검사 대상이 0건이면 아래 테스트는 언제나 통과한다 — 빈 검사 방지."""
    assert len(REPORTS) >= 20, f"결함 리포트를 {len(REPORTS)}건밖에 못 찾았다 — 경로가 바뀌었는지 확인한다"


# invariant 성격 — 새 리포트가 생기면 자동으로 포함된다.
@pytest.mark.parametrize("path", REPORTS, ids=lambda p: p.stem[:40])
def test_every_debug_report_declares_whether_it_is_open_or_closed(path: Path):
    text = path.read_text(encoding="utf-8")
    resolved = bool(STATUS_RESOLVED.search(text))
    still_open = bool(STATUS_OPEN.search(text))

    assert resolved or still_open, (
        f"{path.name} 에 상태 표기가 없다.\n"
        "  문서 첫 줄 다음에 `## 해결됨 (YYYY-MM-DD)` 또는 `## 미해결` 을 둔다.\n"
        "  ★옛 `- 상태:` 줄은 지우지 않는다 — 발견 시점의 기록이다. 위에 얹기만 한다.\n"
        "  근거: docs/reports/2026-09-03_결함리포트_상태를_읽을_수_없다.md")

    assert not (resolved and still_open), (
        f"{path.name} 에 '해결됨' 과 '미해결' 이 둘 다 있다. 지금 상태 하나만 남긴다.\n"
        "  부분 해결이면 `## 해결됨 (날짜, 부분) — 무엇이 닫혔는지` 로 적고,\n"
        "  열려 있는 부분을 그 아래 본문에 분명히 남긴다.")


def test_a_resolved_report_says_what_closed_it():
    """★"해결됨" 만 적고 근거가 없으면 다음 사람이 다시 확인해야 한다.

    표기 줄 뒤에 최소한의 설명이 붙어 있는지 본다 — 날짜만 있고 본문이
    비어 있으면 "고쳤다고 하는데 무엇으로 확인했는지" 를 알 수 없다.
    """
    thin = []
    for path in REPORTS:
        text = path.read_text(encoding="utf-8")
        match = STATUS_RESOLVED.search(text)
        if not match:
            continue
        # 표기 줄 다음부터 그 다음 제목 전까지가 근거 본문이다.
        body = text[match.end():]
        body = re.split(r"^##\s", body, maxsplit=1, flags=re.MULTILINE)[0]
        if len(body.strip()) < 40:
            thin.append(f"{path.name} (근거 {len(body.strip())}자)")

    assert not thin, (
        "해결됨 표기 뒤에 근거가 거의 없다. 무엇으로 닫았는지 한 줄이라도 적는다:\n  "
        + "\n  ".join(thin))

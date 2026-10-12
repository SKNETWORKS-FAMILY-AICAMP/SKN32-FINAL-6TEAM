"""결함 리포트가 열렸는지 닫혔는지를 **읽어서 알 수 있게** 유지한다.

★2026-09-03 실측: `wiki/records/reports/debugs/` 26건 중 상태를 기계로 셀 수 있는
  것이 없었다. `RULE.md` §4.1 이 "고쳤는지와 무관하게 먼저 기록한다" 고 해서
  발견 기록은 잘 남는데, **고친 뒤 되돌아와 닫는 단계가 없었다.** 그래서 각
  문서의 `- 상태:` 줄이 작성 시점("미수정 → 수정 발주함")에 멈춰 있었고,
  `CLAUDE.md` 상태표가 **해결로 인용하는 문서 3건**까지 "미해결" 로 보였다.
  경위: `wiki/records/reports/2026-09-03_결함리포트_상태를_읽을_수_없다.md`

  17건을 하나씩 코드로 확인해 닫고 표기를 통일했다. 이 검사는 **다시
  흐트러지지 않게** 한다 — 표기가 없으면 여기서 실패한다.

★**옛 `- 상태:` 줄을 지우라고 요구하지 않는다.** 그건 발견 시점의 사실이고
  그 자체가 기록이다. 요구하는 것은 그 위에 **지금 상태를 한 줄로 얹는 것**뿐이다.

2026-10-12: 과거 원문은 현재 규격에 맞추어 다시 쓰지 않는다. 상충 표기·표기 누락은
  별도 현황 주석에 원문 해시와 미확인 범위를 기록한다. unverified는 해결이 아니며
  새 보고서의 누락·상충이나 근거 없는 해결 승격은 계속 실패한다.
"""
from __future__ import annotations

import re
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

DEBUG_DIR = Path(__file__).resolve().parents[3] / "wiki" / "records" / "reports" / "debugs"
STATUS_INDEX = DEBUG_DIR.parents[2] / "quality" / "debug-report-current-status.json"

#: 문서 어디든 이 형태가 한 번 나오면 상태가 표기된 것으로 본다.
#:  "## 해결됨", "## 해결됨 (2026-09-03)", "## 해결됨 (2026-09-01, 부분) — …" 등.
STATUS_RESOLVED = re.compile(r"^##\s*해결됨", re.MULTILINE)
STATUS_OPEN = re.compile(r"^##\s*미해결", re.MULTILINE)

REPORTS = sorted(DEBUG_DIR.glob("*.md"))


def current_status(text: str, entry: dict | None = None) -> tuple[str, str]:
    """과거 본문을 보존하고 명시적 현황 주석과 원문 해시를 검증한다."""
    if entry is not None:
        assert entry["source_text_sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest(), "현황 주석의 원문이 바뀌어 재확인이 필요하다"
        status = entry["state"]
        assert status in {"open", "resolved", "unverified"}, "알 수 없는 현황 상태"
        assert datetime.fromisoformat(entry["checked_at_kst"]).utcoffset() is not None
        reason = entry["reason"].strip()
        assert len(reason) >= 40, "현황 주석에는 근거와 미확인 범위가 필요하다"
        if status == "resolved":
            assert entry.get("closure_evidence"), "해결로 승격하려면 검증 근거가 필요하다"
        if status == "unverified":
            assert entry.get("required_verification"), "미확인을 닫지 말고 필요한 확인을 남긴다"
        return status, reason
    resolved = STATUS_RESOLVED.search(text)
    still_open = STATUS_OPEN.search(text)
    assert bool(resolved) != bool(still_open), "현재 상태가 명확하지 않다. 원문을 보존하고 현황 주석에 근거·해시를 추가한다"
    match = resolved or still_open
    body = re.split(r"^##\s", text[match.end():], maxsplit=1, flags=re.MULTILINE)[0]
    return ("resolved" if resolved else "open"), body


def status_entries():
    data = json.loads(STATUS_INDEX.read_text(encoding="utf-8"))
    entries = data["reports"]
    assert len(entries) == len({entry["report"] for entry in entries}), "현황 주석의 보고서가 중복된다"
    return {entry["report"]: entry for entry in entries}


def test_the_debug_report_directory_is_not_empty():
    """★검사 대상이 0건이면 아래 테스트는 언제나 통과한다 — 빈 검사 방지."""
    assert len(REPORTS) >= 20, f"결함 리포트를 {len(REPORTS)}건밖에 못 찾았다 — 경로가 바뀌었는지 확인한다"


# invariant 성격 — 새 리포트가 생기면 자동으로 포함된다.
@pytest.mark.parametrize("path", REPORTS, ids=lambda p: p.stem[:40])
def test_every_debug_report_declares_whether_it_is_open_or_closed(path: Path):
    text = path.read_text(encoding="utf-8")
    current_status(text, status_entries().get(path.name))


def test_a_resolved_report_says_what_closed_it():
    """★"해결됨" 만 적고 근거가 없으면 다음 사람이 다시 확인해야 한다.

    표기 줄 뒤에 최소한의 설명이 붙어 있는지 본다 — 날짜만 있고 본문이
    비어 있으면 "고쳤다고 하는데 무엇으로 확인했는지" 를 알 수 없다.
    """
    thin = []
    for path in REPORTS:
        text = path.read_text(encoding="utf-8")
        status, body = current_status(text, status_entries().get(path.name))
        if status != "resolved":
            continue
        # 표기 줄 다음부터 그 다음 제목 전까지가 근거 본문이다.
        if len(body.strip()) < 40:
            thin.append(f"{path.name} (근거 {len(body.strip())}자)")

    assert not thin, (
        "해결됨 표기 뒤에 근거가 거의 없다. 무엇으로 닫았는지 한 줄이라도 적는다:\n  "
        + "\n  ".join(thin))


def test_current_annotations_reference_existing_reports():
    assert set(status_entries()) <= {p.name for p in REPORTS}
    for name, entry in status_entries().items():
        assert entry["source_sha256"] == hashlib.sha256((DEBUG_DIR / name).read_bytes()).hexdigest()


def test_unannotated_ambiguous_history_still_fails():
    with pytest.raises(AssertionError):
        current_status("## 미해결\n발견 당시\n## 해결됨\n후속 확인\n")


@pytest.mark.parametrize("text", ["# 상태 없는 신규 보고서", "## 부분 해결\n연결 미확인"])
def test_new_report_without_current_status_is_not_silently_accepted(text):
    with pytest.raises(AssertionError):
        current_status(text)


def test_annotation_cannot_hide_changed_source_or_close_without_evidence():
    text = "# 과거 기록\n"
    entry = {"source_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
             "state": "unverified", "checked_at_kst": "2026-10-12T04:00:00+09:00",
             "reason": "원본의 작성 시점 표기만 확인했으며 현재 코드와 운영 환경의 해결 여부는 재검증하지 않았습니다.",
             "required_verification": "관련 코드와 실행 증거 대조"}
    assert current_status(text, entry)[0] == "unverified"
    with pytest.raises(AssertionError):
        current_status(text + "새 변경", entry)
    with pytest.raises(AssertionError):
        current_status(text, {**entry, "state": "resolved"})

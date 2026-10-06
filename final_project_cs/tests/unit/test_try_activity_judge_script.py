"""`scripts/try_activity_judge.py` — 규칙 모드는 LLM·DB 없이 끝까지 돈다(입력 해석과 출력 모양만 본다)."""
from __future__ import annotations

from datetime import datetime

import pytest

from scripts import try_activity_judge as script


def test_rule_mode_runs_without_network(capsys):
    assert script.main(["--place", "경복궁", "--at", "2026-10-13 14:00",
                        "--restdate", "매주 화요일 휴무", "--usetime", "09:00~18:00", "--mode", "rule"]) == 0
    printed = capsys.readouterr().out
    assert "CSV 126508" in printed                     # 장소는 CSV 목록에서 찾는다
    assert "성립: False" in printed and "closed_weekday" in printed


def test_unknown_place_still_runs(capsys):
    assert script.main(["--place", "없는장소이름XYZ", "--at", "2026-10-13 14:00", "--mode", "rule"]) == 0
    assert "CSV 에서 못 찾음" in capsys.readouterr().out


def test_parse_at_assumes_korea_time():
    assert script.parse_at("2026-10-13 14:00").utcoffset().total_seconds() == 9 * 3600
    assert script.parse_at("2026-10-13T05:00:00+00:00") == datetime.fromisoformat("2026-10-13T14:00:00+09:00")


def test_parse_disaster():
    msg = script.parse_disaster("위급재난|호우|해운대 침수|부산광역시, 해운대구", "t")
    assert msg == {"step": "위급재난", "kind": "호우", "text": "해운대 침수",
                   "regions": ["부산광역시", "해운대구"], "created_at": "t"}
    with pytest.raises(SystemExit):
        script.parse_disaster("본문만", "t")

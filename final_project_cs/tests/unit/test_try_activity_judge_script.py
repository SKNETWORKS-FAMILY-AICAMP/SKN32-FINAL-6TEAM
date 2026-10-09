"""`scripts/try_activity_judge.py` — 규칙 모드는 LLM 없이 develop 판 팀으로 끝까지 돈다(입력 해석과 출력 모양만 본다).

★`[2026-10-09]` develop 판 팀(`team.py`)으로 옮겼다(D-CS-015) — 전에는 보존본 `team_a.py` 를 돌렸다.
★대체 후보 풀만 실제 DB 를 읽는다 — DB 가 없으면 「못 읽었다」를 보이고 모름으로 돈다(이 시험은 그 경우에도 통과한다).
"""
from __future__ import annotations

from datetime import datetime

import pytest

from scripts import try_activity_judge as script

AT = "2026-11-10 14:00"     # 화요일


def test_rule_mode_blocks_a_closed_day(capsys):
    assert script.main(["--place", "경복궁", "--at", AT, "--restdate", "매주 화요일 휴무", "--usetime", "09:00~18:00",
                        "--weather-sensitive", "indoor", "--mode", "rule"]) == 0
    printed = capsys.readouterr().out
    assert "CSV 126508" in printed                     # 장소는 CSV 목록에서 찾는다
    assert "성립: False" in printed and "closed_weekday" in printed


def test_rule_mode_runs_the_real_shared_check(capsys):
    """교통통제(장소형 유형) 문자는 실제 공유 점검(`DisruptionCheck`)이 막는다."""
    assert script.main(["--place", "경복궁", "--at", AT, "--weather-sensitive", "indoor", "--mode", "rule",
                        "--disaster", "안전안내|교통통제|[종로구] 율곡로 통제|서울특별시 종로구"]) == 0
    assert "disrupted" in capsys.readouterr().out


def test_another_district_does_not_reach_the_place(capsys):
    assert script.main(["--place", "경복궁", "--at", AT, "--weather-sensitive", "indoor", "--mode", "rule",
                        "--disaster", "안전안내|교통통제|[부산시] 해운대 통제|부산광역시 해운대구"]) == 0
    assert "성립: True" in capsys.readouterr().out


def test_outdoor_without_a_forecast_is_warned(capsys):
    assert script.main(["--place", "경복궁", "--at", AT, "--weather-sensitive", "outdoor", "--mode", "rule"]) == 0
    printed = capsys.readouterr().out
    assert "--forecast 가 없다" in printed and "escalated" in printed


def test_unknown_place_still_runs(capsys):
    assert script.main(["--place", "없는장소이름XYZ", "--at", AT, "--weather-sensitive", "indoor",
                        "--mode", "rule"]) == 0
    assert "CSV 에서 못 찾음" in capsys.readouterr().out


def test_llm_mode_is_not_offered():
    """develop 판은 `llm` 모드를 받지 않는다(D-CS-015)."""
    with pytest.raises(SystemExit):
        script.main(["--place", "경복궁", "--at", AT, "--mode", "llm"])


def test_parse_at_assumes_korea_time():
    assert script.parse_at("2026-10-13 14:00").utcoffset().total_seconds() == 9 * 3600
    assert script.parse_at("2026-10-13T05:00:00+00:00") == datetime.fromisoformat("2026-10-13T14:00:00+09:00")


def test_parse_disaster():
    msg = script.parse_disaster("위급재난|호우|해운대 침수|부산광역시, 해운대구", "t")
    assert msg == {"step": "위급재난", "kind": "호우", "text": "해운대 침수",
                   "regions": ["부산광역시", "해운대구"], "created_at": "t", "serial": None}
    assert script.parse_disaster("위급재난|호우|본문", "t")["regions"] == ["서울특별시 전체"]
    with pytest.raises(SystemExit):
        script.parse_disaster("본문만", "t")

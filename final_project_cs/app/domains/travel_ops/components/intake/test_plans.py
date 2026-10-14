"""사용자가 명시적으로 고른 시험 코드만 준비된 서울 일정 원문으로 바꾼다.

검사 결과·영업 정보·경보를 만들지 않는다. 확장한 원문은 일반 접수와 같은 검증을 거친다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import re
from zoneinfo import ZoneInfo

from app.core.settings import get_guardrails
from app.domains.travel_ops.components.settings_hook import operator_setting

CATALOG_VERSION = "seoul-text-v2"
CODE = re.compile(r"test([1-9][0-9]*)(rt)?", re.IGNORECASE | re.ASCII)

# (이름, 확인할 내용, 날짜별 원문). 고정된 것은 입력뿐이며 결과는 실제 조회에 따른다.
PLANS = (
    ("서울 2일 기본 일정", "궁궐·시장·박물관과 다음 날 일정을 확인합니다.", (
        "09:00~10:30 경복궁 관람\n12:30~13:30 광장시장 점심\n15:00~16:30 국립중앙박물관 관람",
        "10:00~11:00 북촌한옥마을 산책\n12:00~13:00 인사동 점심\n14:00~15:30 창덕궁 관람")),
    ("겹치는 일정", "서로 겹치는 방문 시간을 확인합니다.", (
        "09:00~11:00 경복궁 관람\n10:30~12:00 국립중앙박물관 관람\n12:30~13:30 광장시장 점심",)),
    ("늦은 궁궐 방문", "야간 방문이 실제 운영시간에 맞는지 확인합니다.", (
        "12:00~13:00 광장시장 점심\n21:00~22:00 경복궁 관람",)),
    ("화요일 궁궐 방문", "화요일의 휴무·운영 정보를 조회합니다.", (
        "10:00~11:30 경복궁 관람\n12:30~13:30 광장시장 점심",)),
    ("정해지지 않은 숙소", "호텔 이름을 정하지 않은 일정의 장소 확인을 살펴봅니다.", (
        "09:00~09:30 호텔 조식\n10:30~12:00 경복궁 관람\n12:30~13:30 광장시장 점심",)),
    ("짧은 이동 간격", "멀리 떨어진 방문지 사이의 짧은 이동 간격을 확인합니다.", (
        "10:00~11:00 국립중앙박물관 관람\n11:05~12:00 경복궁 관람\n12:30~13:30 광장시장 점심",)),
    ("종료 시각 생략", "종료 시각이 없는 일정의 확인·수정을 살펴봅니다.", (
        "09:00 경복궁 관람\n12:30 광장시장 점심\n15:00 국립중앙박물관 관람",)),
    ("같은 장소 재방문", "같은 날 같은 장소를 두 번 방문하는 일정을 확인합니다.", (
        "09:00~10:00 인사동 산책\n12:00~13:00 광장시장 점심\n16:00~17:00 인사동 산책",)),
    ("예약이 있는 방문", "예약 표시가 있는 일정의 보존·수정을 확인합니다.", (
        "10:00~11:30 경복궁 관람\n12:30~13:30 광장시장 점심\n19:00~20:00 N서울타워 관람 · 예약 있음",)),
    ("원문 순서가 다른 일정", "입력 순서와 방문 시각이 다른 일정을 확인합니다.", (
        "15:00~16:30 국립중앙박물관 관람\n09:00~10:30 경복궁 관람\n12:30~13:30 광장시장 점심",)),
    ("서울 7일 일정", "최대 7일 일정의 날짜 전환·목록을 확인합니다.", (
        "10:00~11:30 경복궁 관람", "10:00~11:30 국립중앙박물관 관람",
        "10:00~11:30 북촌한옥마을 산책", "12:00~13:00 광장시장 점심",
        "10:00~11:30 창덕궁 관람", "10:00~11:00 청계천 산책",
        "19:00~20:00 N서울타워 관람")),
    ("활동과 식사", "서울의 활동·식사·이동을 함께 확인합니다.", (
        "10:00~11:30 북촌한옥마을 산책\n12:00~13:00 광장시장 점심\n15:00~16:30 국립중앙박물관 관람\n19:00~20:00 N서울타워 관람",)),
    ("여유 있는 도심 산책", "시간 겹침·장소 미정 없이 여유를 둔 기본안입니다.", (
        "10:00~11:00 청계천 산책\n14:00~15:00 인사동 산책",)),
    ("여유 있는 박물관 방문", "장소와 종료 시각을 정하고 이동 여유를 둔 기본안입니다.", (
        "10:00~12:00 국립중앙박물관 관람\n16:00~17:00 N서울타워 관람",)),
    ("하루 한 곳씩 서울 2일", "하루에 한 곳씩 방문해 날짜 전환을 확인하는 기본안입니다.", (
        "10:00~11:00 청계천 산책", "10:00~12:00 국립중앙박물관 관람")),
    ("숙소가 있는 서울 2일", "이름이 있는 호텔 체크인이 든 일정으로 숙소 후보와 바꾸기를 확인합니다.", (
        "10:00~11:30 경복궁 관람\n15:00 더 플라자 호텔 서울 체크인", "11:00~12:30 N서울타워 관람")),
)

# 시험 목적 분류이며 실제 검증 결과의 문제 분류를 대신하지 않는다.
CATEGORIES = ("general", "time", "hours", "hours", "place", "mobility", "input",
              "general", "general", "input", "general", "general", "normal", "normal", "normal", "general")


class TestPlanRejected(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def enabled(tenant_id: str) -> bool:
    value = operator_setting(tenant_id, "testing.intake_presets_enabled")
    return bool(get_guardrails().get("testing.intake_presets_enabled") if value is None else value)


def prepared(number: int, today: date | None = None) -> dict:
    name, description, days = PLANS[number - 1]
    first = (today or datetime.now(ZoneInfo("Asia/Seoul")).date()) + timedelta(days=7)
    if number == 4:
        first += timedelta(days=(1 - first.weekday()) % 7)
    text = f"서울 {len(days)}일 여행 · 4명\n\n" + "\n\n".join(
        f"{i + 1}일차 · {(first + timedelta(days=i)).isoformat()}\n{body}" for i, body in enumerate(days))
    return {"code": f"test{number}", "mode": "prepared_text", "catalog_version": CATALOG_VERSION,
            "name": name, "description": description, "category": CATEGORIES[number - 1],
            "expected": "입력은 시험용이며 검증 결과는 실제 조회에 따라 달라집니다.", "text": text}


def catalog(tenant_id: str, today: date | None = None) -> dict:
    active = enabled(tenant_id)
    return {"enabled": active, "realtime_enabled": False, "catalog_version": CATALOG_VERSION,
            "scenarios": [prepared(n, today) for n in range(1, len(PLANS) + 1)] if active else []}


def expand(text: str, *, tenant_id: str, has_files: bool, today: date | None = None) -> tuple[str, dict | None]:
    match = CODE.fullmatch(text.strip())
    if not match:
        return text, None
    available_codes = f"test1부터 test{len(PLANS)}까지"
    if len(match[1]) > len(str(len(PLANS))):
        raise TestPlanRejected("unknown_test_scenario", f"준비된 시험 코드는 {available_codes}예요.")
    number = int(match[1])
    if number > len(PLANS):
        raise TestPlanRejected("unknown_test_scenario", f"준비된 시험 코드는 {available_codes}예요.")
    if has_files:
        raise TestPlanRejected("test_scenario_with_files", "시험 코드와 파일은 함께 보낼 수 없어요. 하나만 선택해 주세요.")
    if not enabled(tenant_id):
        raise TestPlanRejected("test_scenarios_disabled", "시험 일정 입력이 꺼져 있어요. 준비된 일정 원문이나 직접 작성한 계획을 입력해 주세요.")
    if match[2]:
        raise TestPlanRejected("live_test_not_ready", f"실시간 경보 시험은 아직 연결되지 않았어요. {available_codes} 준비된 계획을 사용할 수 있어요.")
    entry = prepared(number, today)
    return entry["text"], {k: v for k, v in entry.items() if k != "text"}

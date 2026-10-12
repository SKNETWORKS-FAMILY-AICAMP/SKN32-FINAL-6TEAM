"""요약 버튼이 보낸 명시적 날짜를 검증한다. 자유 문장 분류나 모델 실패의 대체 경로가 아니다."""
from datetime import date
from zoneinfo import ZoneInfo

from .decision_unit import Decision


def decide_summary(day: date, *, message: str, items: list) -> Decision:
    if type(day) is not date:
        raise ValueError("요약할 날짜가 올바르지 않습니다")
    iso = day.isoformat()
    if message not in (f"{iso} 하루 일정을 요약해 주세요.", f"Summarize the itinerary for {iso}."):
        raise ValueError("요약 날짜와 요청 문장이 일치하지 않습니다")
    days = sorted({item.starts_at.astimezone(ZoneInfo("Asia/Seoul")).date()
                   for item in items if item.kind != "mobility"})
    if day not in days:
        raise ValueError("이 여행에 해당 날짜의 일정이 없습니다")
    query = {"day": f"d{(day-days[0]).days+1}", "period": "all", "kind": "all", "position": "all"}
    read = {"fact": "day", "target_item": "none", "reference": "none", "origin_item": "none", "query": query, "text": ""}
    return Decision("answer_fact", None, None, "schedule", None, "", query=query,
                    raw={"source": "explicit_summary_button", "model_called": False, "summary_day": iso})

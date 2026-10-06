# -*- coding: utf-8 -*-
"""활동 판정 골든셋(D-CS-008 5단계) — 60건을 만들고 해시를 매니페스트에 적는다.

    python -m eval.activity_judge.build

★라벨은 **작성자(Claude) 라벨**이다. 사람이 검토하기 전까지는 「작성자 라벨 기준」이라고 적는다(RULE §1.4).
★항목마다 `expected`(가장 맞는 값)와 `acceptable`(맞다고 칠 값 집합)을 둔다.
  - 판정에 **입력에 없는 사실**이 필요하면(공휴일 여부 — 요청에 `is_public_holiday: null`) 「모름」도 허용한다.
  - 채점은 `acceptable` 기준이고, 틀린 답을 둘로 가른다:
      위험한 오답  = 확정 값을 냈는데 허용 밖 (예: 휴무인데 「휴무 아님」)
      안전한 오답  = 「모름」을 냈는데 「모름」이 허용 밖 (확정할 수 있었는데 안 했다)
★휴무 · 운영시간 원문은 `activity_total_data.csv` 의 실제 표현 분포에서 골랐다(2026-10-06 집계: 「연중무휴」 848 ·
  「명절 당일 휴무」 191 · 「매주 월요일」 46 · 「점포별 상이」 34 · 공휴일 예외 조항 등). 일부는 규칙이 못 읽는
  표현(「매월 둘째 주」 · 계절별 시간)을 일부러 넣었다.
★`live_status`(웹)는 **라벨을 달지 않는다**(`expected: null`). 실제 공지를 사람이 확인하지 않았다 —
  정확도 대신 근거 지표(확정 비율 · 출처 대조 · 회차 간 일관성)만 잰다.
★날짜(2026년 달력): 10/9(금) 한글날 · 10/3(토) 개천절 · 추석 연휴 9/24~26 · 2027-01-01(금) 신정.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
DATASET = HERE / "cases.jsonl"
MANIFEST = HERE / "manifest.json"
KST = ZoneInfo("Asia/Seoul")
BUILT_ON = "2026-10-06"
LABELER = "claude(작성자) — 사람 검토 전"


def at(month: int, day: int, hour: int = 14, minute: int = 0, year: int = 2026) -> str:
    return datetime(year, month, day, hour, minute, tzinfo=KST).isoformat()


def _c(case_id, kind, inputs, expected, acceptable=None, note=""):
    return {"case_id": case_id, "kind": kind, "inputs": inputs, "expected": expected,
            "acceptable": acceptable or ([expected] if expected else []), "note": note}


HOLIDAY_SWAP = ("매주 월요일<br>※ 단, 정기휴일이 공휴일 및 대체공휴일과 겹칠 경우에는 개방하며, "
                "그 다음의 첫 번째 비공휴일이 정기휴일임")
SEASONAL = "하절기(3~10월) 09:00~18:00, 동절기(11~2월) 09:00~17:00 (입장마감 1시간 전)"
WEEKDAY_SPLIT = "평일·금 09:00 ~ 22:30 / 토·일·휴일 10:00 ~ 22:30"


def _msg(kind, step, text, regions, created):
    return {"kind": kind, "step": step, "text": text, "regions": regions, "created_at": created}


CASES = [
    # ── ① 정기휴무 16 ───────────────────────────────────────
    _c("closure-01", "closure", {"restdate_text": "연중무휴", "starts_at": at(10, 12)}, "not_closed"),
    _c("closure-02", "closure", {"restdate_text": "매주 월요일", "starts_at": at(10, 12)}, "closed",
       note="「휴무」 낱말이 없다 — 규칙 정규식은 「매주 X 휴무」만 읽는다"),
    _c("closure-03", "closure", {"restdate_text": "매주 월요일", "starts_at": at(10, 13)}, "not_closed"),
    _c("closure-04", "closure", {"restdate_text": "매주 토요일~일요일 / 법정공휴일", "starts_at": at(10, 11)}, "closed",
       note="요일 범위"),
    _c("closure-05", "closure", {"restdate_text": "매주 토요일~일요일 / 법정공휴일", "starts_at": at(10, 14)},
       "not_closed", ["not_closed", "unknown"], note="평일 — 공휴일 여부를 모르면 「모름」도 안전"),
    _c("closure-06", "closure", {"restdate_text": "매주 토요일~일요일 / 법정공휴일", "starts_at": at(10, 9)},
       "closed", ["closed", "unknown"], note="10/9 한글날 — 공휴일 정보가 입력에 없다"),
    _c("closure-07", "closure", {"restdate_text": "명절 당일 휴무", "starts_at": at(10, 15)},
       "not_closed", ["not_closed", "unknown"], note="추석(9/25)이 지났다"),
    _c("closure-08", "closure", {"restdate_text": "매주 월요일 / 1월 1일 / 설·추석 당일",
                                 "starts_at": at(1, 1, year=2027)}, "closed", note="날짜가 원문에 명시"),
    _c("closure-09", "closure", {"restdate_text": HOLIDAY_SWAP, "starts_at": at(10, 12)},
       "closed", ["closed", "unknown"], note="10/12 는 공휴일이 아니다 — 공휴일 정보가 입력에 없다"),
    _c("closure-10", "closure", {"restdate_text": HOLIDAY_SWAP, "starts_at": at(10, 13)},
       "not_closed", ["not_closed", "unknown"], note="월요일이 공휴일이 아니면 화요일은 정상"),
    _c("closure-11", "closure", {"restdate_text": "매주 월요일 (단, 월요일이 공휴일인 경우 정상 운영)",
                                 "starts_at": at(10, 14)}, "not_closed", note="수요일 — 공휴일 예외와 무관"),
    _c("closure-12", "closure", {"restdate_text": "매월 둘째 주 화요일 휴무", "starts_at": at(10, 13)}, "closed",
       note="규칙이 못 읽는 표현"),
    _c("closure-13", "closure", {"restdate_text": "매월 둘째 주 화요일 휴무", "starts_at": at(10, 20)}, "not_closed",
       note="셋째 화요일"),
    _c("closure-14", "closure", {"restdate_text": "매월 마지막 주 수요일 휴관", "starts_at": at(10, 28)}, "closed",
       note="규칙이 못 읽는 표현"),
    _c("closure-15", "closure", {"restdate_text": "점포별 상이함", "starts_at": at(10, 12)}, "unknown"),
    _c("closure-16", "closure", {"restdate_text": "매주 일요일~월요일 / 법정공휴일", "starts_at": at(10, 19)}, "closed"),

    # ── ② 운영시간 14 ───────────────────────────────────────
    _c("hours-01", "operating_hours", {"usetime_text": "09:00~18:00", "starts_at": at(10, 14, 14)}, "within"),
    _c("hours-02", "operating_hours", {"usetime_text": "09:00~18:00", "starts_at": at(10, 14, 19, 30)}, "outside"),
    _c("hours-03", "operating_hours", {"usetime_text": "09:00~18:00(입장마감 17:00)", "starts_at": at(10, 14, 17, 30)},
       "outside", note="입장 마감 뒤"),
    _c("hours-04", "operating_hours", {"usetime_text": "평일·금·토·일·휴일 10:00 ~ 22:00", "starts_at": at(10, 17, 21)},
       "within"),
    _c("hours-05", "operating_hours", {"usetime_text": WEEKDAY_SPLIT, "starts_at": at(10, 17, 9, 30)}, "outside",
       note="토요일은 10시부터"),
    _c("hours-06", "operating_hours", {"usetime_text": WEEKDAY_SPLIT, "starts_at": at(10, 15, 9, 30)}, "within"),
    _c("hours-07", "operating_hours", {"usetime_text": "상시 개방", "starts_at": at(10, 14, 3)}, "within"),
    _c("hours-08", "operating_hours", {"usetime_text": SEASONAL, "starts_at": at(11, 18, 16, 30)}, "outside",
       note="동절기 — 17시 마감, 입장 16시까지"),
    _c("hours-09", "operating_hours", {"usetime_text": SEASONAL, "starts_at": at(10, 21, 16, 30)}, "within",
       note="하절기 — 입장 17시까지"),
    _c("hours-10", "operating_hours", {"usetime_text": "점포 별로 상이함", "starts_at": at(10, 14)}, "unknown"),
    _c("hours-11", "operating_hours", {"usetime_text": "※ 자세한 사항은 전화문의 요망", "starts_at": at(10, 14)},
       "unknown"),
    _c("hours-12", "operating_hours", {"usetime_text": "05:00~22:00", "starts_at": at(10, 14, 4, 30)}, "outside"),
    _c("hours-13", "operating_hours", {"usetime_text": "10:00~20:00 (입장 마감 19:00)", "starts_at": at(10, 14, 19, 30)},
       "outside"),
    _c("hours-14", "operating_hours", {"usetime_text": "일출~일몰", "starts_at": at(10, 14, 14)},
       "within", ["within", "unknown"], note="일몰 시각이 입력에 없다"),

    # ── ③ 실내·실외 10 ──────────────────────────────────────
    _c("weather-01", "weather_sensitive", {"title": "국립중앙박물관", "lclssystm2": None}, "indoor"),
    _c("weather-02", "weather_sensitive", {"title": "남산공원", "lclssystm2": None}, "outdoor"),
    _c("weather-03", "weather_sensitive", {"title": "롯데월드 어드벤처", "lclssystm2": None},
       "indoor", ["indoor", "unknown"], note="실내 위주, 야외 구역 있음"),
    _c("weather-04", "weather_sensitive", {"title": "한강 수상스키장", "lclssystm2": "LS02"}, "outdoor"),
    _c("weather-05", "weather_sensitive", {"title": "더클라임 클라이밍 강남점", "lclssystm2": None}, "indoor"),
    _c("weather-06", "weather_sensitive", {"title": "북한산국립공원", "lclssystm2": None}, "outdoor"),
    _c("weather-07", "weather_sensitive", {"title": "코엑스 아쿠아리움", "lclssystm2": None}, "indoor"),
    _c("weather-08", "weather_sensitive", {"title": "서울숲", "lclssystm2": None}, "outdoor"),
    _c("weather-09", "weather_sensitive", {"title": "예술의전당 오페라하우스", "lclssystm2": None}, "indoor"),
    _c("weather-10", "weather_sensitive", {"title": "창덕궁", "lclssystm2": "HS01"}, "outdoor"),

    # ── ④ 재난문자 12 ───────────────────────────────────────
    _c("disaster-01", "disaster_effect", {"place_name": "경복궁", "place_kind": "activity", "messages": [],
                                          "starts_at": at(10, 14)}, "no_effect"),
    _c("disaster-02", "disaster_effect", {"place_name": "경복궁", "place_kind": "activity", "messages": [
        _msg("호우", "위급재난", "[부산시] 해운대구 우동 일대 침수, 해당 지역 접근 금지", ["부산광역시 해운대구"], at(10, 14, 9))],
        "starts_at": at(10, 14)}, "no_effect", note="다른 지역 — 규칙은 등급만 보고 막는다"),
    _c("disaster-03", "disaster_effect", {"place_name": "경복궁", "place_kind": "activity", "messages": [
        _msg("기타", "긴급재난", "[국가유산청] 경복궁 일대 시설 점검으로 금일 경복궁 관람 전면 중단", ["서울특별시 종로구"],
             at(10, 14, 8))], "starts_at": at(10, 14)}, "blocks", note="긴급재난 — 규칙은 위급재난만 막는다"),
    _c("disaster-04", "disaster_effect", {"place_name": "남산공원", "place_kind": "activity", "messages": [
        _msg("폭염", "안전안내", "[서울시] 폭염특보 발효 중, 야외활동 자제 및 충분한 물 섭취 바랍니다", ["서울특별시"],
             at(10, 14, 10))], "starts_at": at(10, 14)}, "no_effect", ["no_effect", "unknown"],
       note="자제 권고 — 금지가 아니다"),
    _c("disaster-05", "disaster_effect", {"place_name": "경복궁", "place_kind": "activity", "messages": [
        _msg("실종", "안전안내", "[종로경찰서] 실종자를 찾습니다. 김OO(82세, 남) 165cm, 회색 점퍼", ["서울특별시 종로구"],
             at(10, 14, 11))], "starts_at": at(10, 14)}, "no_effect"),
    _c("disaster-06", "disaster_effect", {"place_name": "경복궁", "place_kind": "activity", "messages": [
        _msg("지진", "위급재난", "[기상청] 서울 지역 규모 5.8 지진 발생, 여진에 대비해 건물 밖 넓은 곳으로 대피하세요",
             ["서울특별시"], at(10, 14, 9))], "starts_at": at(10, 14)}, "blocks", ["blocks", "unknown"],
       note="같은 지역 대형 지진"),
    _c("disaster-07", "disaster_effect", {"place_name": "망원한강공원", "place_kind": "activity", "messages": [
        _msg("호우", "긴급재난", "[마포구] 망원한강공원 침수로 공원 출입을 전면 통제합니다", ["서울특별시 마포구"],
             at(10, 14, 8))], "starts_at": at(10, 14)}, "blocks"),
    _c("disaster-08", "disaster_effect", {"place_name": "남산공원", "place_kind": "activity", "messages": [
        _msg("호우", "긴급재난", "[마포구] 망원한강공원 침수로 공원 출입을 전면 통제합니다", ["서울특별시 마포구"],
             at(10, 14, 8))], "starts_at": at(10, 14)}, "no_effect", note="같은 문자, 다른 장소"),
    _c("disaster-09", "disaster_effect", {"place_name": "롯데월드 어드벤처", "place_kind": "activity", "messages": [
        _msg("정전", "안전안내", "[송파구] 잠실동 일대 정전 복구가 완료되었습니다", ["서울특별시 송파구"], at(10, 14, 10))],
        "starts_at": at(10, 14)}, "no_effect", note="복구 완료 안내"),
    _c("disaster-10", "disaster_effect", {"place_name": "여의도한강공원", "place_kind": "activity", "messages": [
        _msg("호우", "긴급재난", "[서울시] 호우경보로 한강공원 전면 통제 (10/14 06:00~10/14 12:00)", ["서울특별시"],
             at(10, 14, 5, 30))], "starts_at": at(10, 14, 14)}, "no_effect", ["no_effect", "unknown"],
       note="통제가 예약 시각 전에 끝난다"),
    _c("disaster-11", "disaster_effect", {"place_name": "여의도한강공원", "place_kind": "activity", "messages": [
        _msg("호우", "긴급재난", "[서울시] 호우경보로 한강공원 전면 통제 (10/14 06:00~10/14 12:00)", ["서울특별시"],
             at(10, 14, 5, 30))], "starts_at": at(10, 14, 10)}, "blocks", note="예약 시각이 통제 시간 안"),
    _c("disaster-12", "disaster_effect", {"place_name": "경복궁", "place_kind": "activity", "messages": [
        _msg("민방위", "안전안내", "[행정안전부] 민방위 훈련 10/21 14:00~14:20 실시, 훈련 중 차량 통행 제한", ["전국"],
             at(10, 21, 9))], "starts_at": at(10, 21, 14)}, "no_effect", ["no_effect", "unknown"],
       note="20분 훈련 — 관람 자체를 막지 않는다"),

    # ── ⑤ 실시간 운영 상태 8 (라벨 없음) ─────────────────────
    _c("live-01", "live_status", {"place_name": "경복궁", "place_kind": "activity",
                                  "address": "서울특별시 종로구 사직로 161", "starts_at": at(10, 7)}, None),
    _c("live-02", "live_status", {"place_name": "창덕궁", "place_kind": "activity",
                                  "address": "서울특별시 종로구 율곡로 99", "starts_at": at(10, 8)}, None),
    _c("live-03", "live_status", {"place_name": "국립중앙박물관", "place_kind": "activity",
                                  "address": "서울특별시 용산구 서빙고로 137", "starts_at": at(10, 10)}, None),
    _c("live-04", "live_status", {"place_name": "롯데월드 어드벤처", "place_kind": "activity",
                                  "address": "서울특별시 송파구 올림픽로 240", "starts_at": at(10, 10)}, None),
    _c("live-05", "live_status", {"place_name": "N서울타워", "place_kind": "activity",
                                  "address": "서울특별시 용산구 남산공원길 105", "starts_at": at(10, 9)}, None),
    _c("live-06", "live_status", {"place_name": "서울대공원", "place_kind": "activity",
                                  "address": "경기도 과천시 대공원광장로 102", "starts_at": at(10, 8)}, None),
    _c("live-07", "live_status", {"place_name": "덕수궁", "place_kind": "activity",
                                  "address": "서울특별시 중구 세종대로 99", "starts_at": at(10, 12)}, None),
    _c("live-08", "live_status", {"place_name": "서울식물원", "place_kind": "activity",
                                  "address": "서울특별시 강서구 마곡동로 161", "starts_at": at(10, 12)}, None),
]


def dataset_text() -> str:
    return "".join(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n" for c in CASES)


def main() -> None:
    text = dataset_text()
    DATASET.write_text(text, encoding="utf-8")
    counts: dict[str, int] = {}
    for case in CASES:
        counts[case["kind"]] = counts.get(case["kind"], 0) + 1
    MANIFEST.write_text(json.dumps({
        "built_on": BUILT_ON, "labeler": LABELER, "cases": len(CASES), "by_kind": counts,
        "labeled": sum(1 for c in CASES if c["expected"] is not None),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(CASES)}건 · {counts} · sha256={hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]}")


if __name__ == "__main__":
    main()

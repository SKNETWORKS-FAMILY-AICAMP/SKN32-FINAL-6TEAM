# -*- coding: utf-8 -*-
"""다양한 입력 계획 읽기 시험지 — 정답 정의. `[2026-10-16]` 계획 읽기 재설계의 비교 기준선

★출제 · 정답: Claude(이 시험지를 만든 세션). 시스템 출력을 보기 **전에** 정답을 달았다 — 학습 자료와 출제자를 나누는 규칙.
  가르친 E4B(`tripilot-pointer:e4b-ft`)의 학습 자료는 Codex · Claude 하위 작업이 만들었고 이 시험지와 겹치는 문장은 없다(새로 썼다).
★두 갈래:
  - `synthetic` — 이 세션이 쓴 합성 입력 49건(모양 10가지).
  - `real` — x600 서버의 cs 프로젝트 DB `intake_sources` 에 쌓인 실제 접수 원문 중 20건(2026-10-06~10-15, 시험 장면 코드 접수 제외,
    같은 원문 반복은 하나만). 작성자가 사람인지 다른 세션인지는 DB 로 가릴 수 없다. 이름 · 연락처 · 주소 같은 개인정보는 없음을 눈으로 확인했다
    (가게 · 관광지 · 호텔 이름만 있다).

정답 칸(`gold`):
  items        일정 항목 — day(며칠째, 모르면 None) · date(YYYY-MM-DD, 원문 · 상대 날짜로 정해지면) · start/end(HH:MM, 원문에 시각이 있을 때만)
               · place(★원문 표기 그대로 — 원문의 부분 문자열이어야 한다) · canon(찾은 장소로 인정할 공식 이름들) · kind(activity · dining · lodging)
               · optional(True 면 읽든 안 읽든 점수에 넣지 않는다 — 「→ 지하철로 동대문」의 동대문처럼 항목인지 갈리는 것)
  moves        이동 수단 — scope(segment · day · all) · mode(taxi · subway · bus · transit · walk · car · bike · cablecar) · from/to(원문 표기)
  conditions   조건 — code(if_rain_indoor · if_rain_skip · finish_by:HH:MM · …) · target(걸리는 항목 원문, 없으면 None)
  preferences  성향 — code(prefer_taxi · avoid_walking · prefer_walking · kid_friendly · …)
  requests     요청 종류 — register(일정 등록) · plan_ask(짜 주기 · 채워 주기 · 추천) · question(질문) · correction(중간 정정)
  requests_optional  있어도 없어도 점수에 넣지 않는 요청 종류(해석이 갈리는 것)
  missing      고객만 아는 빠진 값 — first_day_date(날짜) · lodging_name(숙소 이름) · booked_place_name(예약한 가게 이름)
  missing_optional  있어도 없어도 점수에 넣지 않는 빠진 값
  trip         party_size · days · nights (원문에 있을 때만)
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

AUTHOR = "Claude (2026-10-16 계획 읽기 기준선 세션)"
TODAY = "2026-10-16"          # 금요일. 합성 입력의 「내일」 「토요일」은 이 날 기준


def it(day, dt, start, place, kind="activity", *, end=None, canon=None, optional=False):
    return {"day": day, "date": dt, "start": start, "end": end, "place": place, "kind": kind,
            "canon": list(canon or []), "optional": optional}


def mv(mode, *, scope="segment", frm=None, to=None, day=None):
    return {"scope": scope, "mode": mode, "from": frm, "to": to, "day": day}


def cond(code, target=None):
    return {"code": code, "target": target}


def G(items, *, moves=(), conditions=(), preferences=(), requests=("register",), requests_optional=(),
      missing=(), missing_optional=(), trip=None, note=""):
    return {"note": note, "items": list(items), "moves": list(moves), "conditions": list(conditions), "preferences": list(preferences),
            "requests": list(requests), "requests_optional": list(requests_optional), "missing": list(missing),
            "missing_optional": list(missing_optional), "trip": dict(trip or {})}


def text(t: str) -> list[dict[str, Any]]:
    return [{"kind": "text", "text": t}]


def messages(*ms: str) -> list[dict[str, Any]]:
    return [{"kind": "message", "text": m} for m in ms]


def xlsx(rows, merges=()) -> list[dict[str, Any]]:
    return [{"kind": "xlsx", "rows": rows, "merges": list(merges)}]


D = lambda m, d: f"2026-{m:02d}-{d:02d}"          # noqa: E731
GBG = ["경복궁"]
NST = ["N서울타워", "남산서울타워", "YTN서울타워"]

SYNTHETIC: list[dict[str, Any]] = []


def S(case_id, shape, inputs, gold, *, today=TODAY, note=""):
    SYNTHETIC.append({"case_id": case_id, "shape": shape, "origin": "synthetic", "author": AUTHOR, "today": today,
                      "inputs": inputs, "gold": gold, "note": note})


# ── A. 정형 목록 + 자유 문장 ─────────────────────────────────────────
d = D(10, 22)
S("A01", "mixed_list", text("1일차 10/22(목)\n10:00 경복궁\n택시로 이동할 거야\n12:30 광장시장 빈대떡\n15:00 국립중앙박물관\n저녁은 숙소 근처에서 대충"),
  G([it(1, d, "10:00", "경복궁", canon=GBG), it(1, d, "12:30", "광장시장", "dining", canon=["광장시장"]),
     it(1, d, "15:00", "국립중앙박물관", canon=["국립중앙박물관"]), it(1, d, None, "숙소 근처", "dining")],
    moves=[mv("taxi", frm="경복궁", to="광장시장")], missing=["lodging_name"]))
d = D(10, 24)
S("A02", "mixed_list", text("10월 24일 토요일\n09:30 창덕궁 후원 (예약함)\n점심은 익선동에서 먹고 싶어\n14:00 서울공예박물관\n지하철 타고 이동\n17:00 DDP"),
  G([it(1, d, "09:30", "창덕궁 후원", canon=["창덕궁", "창덕궁 후원"]), it(1, d, None, "익선동", "dining"),
     it(1, d, "14:00", "서울공예박물관", canon=["서울공예박물관"]), it(1, d, "17:00", "DDP", canon=["동대문디자인플라자", "DDP"])],
    moves=[mv("subway", frm="서울공예박물관", to="DDP")]))
d = D(11, 3)
S("A03", "mixed_list", text("첫날\n- 11시 북촌한옥마을\n- 걸어서 삼청동 카페 거리\n- 13시 삼청동 수제비\n- 버스 타고 남산\n- 18시 N서울타워 전망대\n날짜는 11월 3일부터"),
  G([it(1, d, "11:00", "북촌한옥마을", canon=["북촌한옥마을"]), it(1, d, None, "삼청동 카페 거리", "dining"),
     it(1, d, "13:00", "삼청동 수제비", "dining", canon=["삼청동수제비"]), it(1, d, None, "남산", optional=True),
     it(1, d, "18:00", "N서울타워", canon=NST)],
    moves=[mv("walk", frm="북촌한옥마을", to="삼청동 카페 거리"), mv("bus", frm="삼청동 수제비", to="N서울타워")]))
S("A04", "mixed_list", text("Day 1 (10/30)\ncheck-in 롯데호텔 서울 3시\n6시 명동교자 칼국수\n밤에 청계천 산책 — 비 오면 패스\nDay 2\n아침 늦게 시작, 11시 경복궁\n점심 토속촌\n이후 서촌 걷기"),
  G([it(1, D(10, 30), "15:00", "롯데호텔 서울", "lodging", canon=["롯데호텔 서울"]),
     it(1, D(10, 30), "18:00", "명동교자", "dining", canon=["명동교자 본점", "명동교자"]),
     it(1, D(10, 30), None, "청계천", canon=["청계천"]), it(2, D(10, 31), "11:00", "경복궁", canon=GBG),
     it(2, D(10, 31), None, "토속촌", "dining", canon=["토속촌삼계탕", "토속촌"]), it(2, D(10, 31), None, "서촌", canon=["서촌"])],
    conditions=[cond("if_rain_skip", "청계천")], preferences=["late_start"]))
d = D(10, 27)
S("A05", "mixed_list", text("10/27 화\n10:00 국립중앙박물관\n(애들 데리고 가니까 너무 많이 걷는 건 빼줘)\n12:00 이촌동 점심\n14:00 용산가족공원\n16:00 전쟁기념관"),
  G([it(1, d, "10:00", "국립중앙박물관", canon=["국립중앙박물관"]), it(1, d, "12:00", "이촌동", "dining"),
     it(1, d, "14:00", "용산가족공원", canon=["용산가족공원"]), it(1, d, "16:00", "전쟁기념관", canon=["전쟁기념관"])],
    preferences=["kid_friendly", "avoid_walking"]))
d = D(11, 7)
S("A06", "mixed_list", text("11.7(토)\n아침 7시 광장시장 마약김밥\n→ 지하철로 동대문\n9시 동대문디자인플라자\n11시 흥인지문\n점심은 진옥화할매원조닭한마리\n오후는 자유시간"),
  G([it(1, d, "07:00", "광장시장", "dining", canon=["광장시장"]), it(1, d, None, "동대문", optional=True),
     it(1, d, "09:00", "동대문디자인플라자", canon=["동대문디자인플라자", "DDP"]), it(1, d, "11:00", "흥인지문", canon=["흥인지문"]),
     it(1, d, None, "진옥화할매원조닭한마리", "dining", canon=["진옥화할매원조닭한마리"])],
    moves=[mv("subway", frm="광장시장", to="동대문디자인플라자")]))
d = D(11, 14)
S("A07", "mixed_list", text("1일차 11/14\n10:00 국립현대미술관 서울\n12:30 삼청동 수제비\n15:00 경복궁\n경복궁 야간개장 하는 날인가요?\n19:00 광화문 광장"),
  G([it(1, d, "10:00", "국립현대미술관 서울", canon=["국립현대미술관 서울관", "국립현대미술관 서울"]),
     it(1, d, "12:30", "삼청동 수제비", "dining", canon=["삼청동수제비"]), it(1, d, "15:00", "경복궁", canon=GBG),
     it(1, d, "19:00", "광화문 광장", canon=["광화문광장"])],
    requests=["register", "question"]))

# ── B. 말투 · 오타 · 띄어쓰기 깨진 한 줄 계획 ─────────────────────────
d = D(10, 17)
S("B01", "typo_line", text("낼 10시 국립 중앙박 물 관 갔다가 1시쯤 이촌동에서 점심 먹고 4시 n서울타워 ㄱㄱ"),
  G([it(1, d, "10:00", "국립 중앙박 물 관", canon=["국립중앙박물관"]), it(1, d, "13:00", "이촌동", "dining"),
     it(1, d, "16:00", "n서울타워", canon=NST)]))
d = D(10, 19)
S("B02", "typo_line", text("그ㅐㄹ서 담주 월욜에 경복궁이랑 북촌 한옥 마을 보고 저녁엔 광장 시장 갈래요"),
  G([it(1, d, None, "경복궁", canon=GBG), it(1, d, None, "북촌 한옥 마을", canon=["북촌한옥마을"]),
     it(1, d, None, "광장 시장", "dining", canon=["광장시장"])]))
d = D(10, 17)
S("B03", "typo_line", text("토욜 오전 창경궁 오후 대학로 연극 저녁 혜화 닭갈비집~ 4명이서"),
  G([it(1, d, None, "창경궁", canon=["창경궁"]), it(1, d, None, "대학로", canon=["대학로"]), it(1, d, None, "혜화 닭갈비집", "dining")],
    trip={"party_size": 4}))
d = D(10, 20)
S("B04", "typo_line", text("10/20 9시반 덕수궁 돌담길 11시 시청앞 서울도서관 12시반 정동 점심 2시 서울역사박물관"),
  G([it(1, d, "09:30", "덕수궁 돌담길", canon=["덕수궁", "덕수궁 돌담길", "덕수궁돌담길"]),
     it(1, d, "11:00", "서울도서관", canon=["서울도서관"]), it(1, d, "12:30", "정동", "dining"),
     it(1, d, "14:00", "서울역사박물관", canon=["서울역사박물관"])]))
d = D(10, 21)
S("B05", "typo_line", text("ㅇㅇ 그럼 21일날 잠실 롯데월드 갓다가 석촌호수 산책하구 저녘은 송리단길에서 먹을께여"),
  G([it(1, d, None, "롯데월드", canon=["롯데월드", "롯데월드 어드벤처"]), it(1, d, None, "석촌호수", canon=["석촌호수"]),
     it(1, d, None, "송리단길", "dining")]))
d = D(10, 18)
S("B06", "typo_line", text("몰라 그냥 내일모레 홍대 가서 놀고 연남동 경의선숲길 걸을래 택시는 싫고 걸어다닐거"),
  G([it(1, d, None, "홍대", canon=["홍대", "홍익대학교", "홍대거리"]), it(1, d, None, "경의선숲길", canon=["경의선숲길", "경의선 숲길"])],
    moves=[mv("walk", scope="all")], preferences=["prefer_walking"]))
d = D(10, 23)
S("B07", "typo_line", text("10월23일 오후2시 성수동카페거리 오후5시 서울숲 저녁7시 뚝섬한강공원 치맥"),
  G([it(1, d, "14:00", "성수동카페거리", "dining"), it(1, d, "17:00", "서울숲", canon=["서울숲"]),
     it(1, d, "19:00", "뚝섬한강공원", "dining", canon=["뚝섬한강공원"])]))
d = D(11, 2)
S("B08", "typo_line", text("11/2 아침9시에 호텔에서 나와서 창덕궁 보고 점심 먹고 3시 반에 인사동 쌈지길"),
  G([it(1, d, None, "창덕궁", canon=["창덕궁"]), it(1, d, "15:30", "인사동 쌈지길", canon=["쌈지길", "인사동쌈지길"])],
    missing=["lodging_name"]))

# ── C. 문단 자유문(기간 · 인원 · 조건 · 성향 · 일부 짜기) ─────────────────
S("C01", "paragraph", text("다음 달 5일부터 2박 3일로 서울 가요. 어른 둘이고 걷는 걸 별로 안 좋아해서 웬만하면 택시 탈게요. "
                          "첫날은 도착하면 오후라 경복궁이랑 북촌만 보고, 둘째 날은 알아서 짜 주세요. "
                          "마지막 날은 오전에 남대문시장 들렀다가 공항 가요. 비 오면 실내 위주로 바꿔 주세요."),
  G([it(1, D(11, 5), None, "경복궁", canon=GBG), it(1, D(11, 5), None, "북촌", canon=["북촌한옥마을"]),
     it(3, D(11, 7), None, "남대문시장", canon=["남대문시장"]), it(3, D(11, 7), None, "공항", optional=True)],
    moves=[mv("taxi", scope="all")], conditions=[cond("if_rain_indoor")], preferences=["avoid_walking", "prefer_taxi"],
    requests=["register", "plan_ask"], trip={"party_size": 2, "days": 3, "nights": 2}))
S("C02", "paragraph", text("서울 처음이에요. 4명(초등학생 아이 2명 포함)이고 3일 있을 거예요. 날짜는 아직 미정이에요. "
                          "아이들이 좋아할 만한 곳 위주로 일정 좀 짜 주세요. 롯데월드는 꼭 넣어 주세요."),
  G([it(None, None, None, "롯데월드", canon=["롯데월드", "롯데월드 어드벤처"])],
    preferences=["kid_friendly"], requests=["plan_ask"], requests_optional=["register"], missing=["first_day_date"],
    trip={"party_size": 4, "days": 3}))
d = D(10, 17)
S("C03", "paragraph", text("내일 하루 종일 비 온다던데 실내에서 놀 만한 데로 일정 바꿔 줄 수 있어요? 원래는 한강공원 자전거 타고 서울숲 가려고 했어요."),
  G([it(1, d, None, "한강공원", canon=["뚝섬한강공원", "여의도한강공원", "한강공원"]), it(1, d, None, "서울숲", canon=["서울숲"])],
    moves=[mv("bike", frm="한강공원", to="서울숲")], conditions=[cond("if_rain_indoor")],
    requests=["plan_ask"], requests_optional=["register", "question"]))
S("C04", "paragraph", text("10월 말에 엄마랑 둘이 1박 2일로 가는데요, 엄마가 무릎이 안 좋으셔서 계단 많은 곳은 피하고 싶어요. "
                          "첫날 점심은 명동에서 먹고 오후에 남산 케이블카 타고 싶고, 저녁엔 숭례문 근처에서 한식 먹을래요. "
                          "둘째 날은 고궁 하나 정도만 가볍게."),
  G([it(1, None, None, "명동", "dining"), it(1, None, None, "남산 케이블카", canon=["남산케이블카", "남산 케이블카"]),
     it(1, None, None, "숭례문 근처", "dining")],
    preferences=["avoid_stairs", "slow_pace"], requests=["register", "plan_ask"], missing=["first_day_date"],
    trip={"party_size": 2, "days": 2, "nights": 1}))
d = D(10, 17)
S("C05", "paragraph", text("토요일에 친구들이랑 5명이서 성수 놀러 가요 점심 12시에 성수동 대림창고 근처에서 먹고 1시 반부터 소품샵 구경하다가 "
                          "4시쯤 서울숲 산책하고 저녁은 7시 뚝섬역 쪽 고깃집 예약해놨어요"),
  G([it(1, d, "12:00", "대림창고", "dining"), it(1, d, "13:30", "소품샵"), it(1, d, "16:00", "서울숲", canon=["서울숲"]),
     it(1, d, "19:00", "뚝섬역 쪽 고깃집", "dining")],
    missing=["booked_place_name"], trip={"party_size": 5}))
S("C06", "paragraph", text("Arriving Oct 29 evening, staying at a hotel in Myeongdong. Day 2 want 경복궁 in the morning and 광장시장 for lunch, "
                          "then maybe COEX in the afternoon. Day 3 free day — please plan. Flight out Nov 1 at 2pm."),
  G([it(2, D(10, 30), None, "경복궁", canon=GBG), it(2, D(10, 30), None, "광장시장", "dining", canon=["광장시장"]),
     it(2, D(10, 30), None, "COEX", canon=["코엑스", "COEX", "스타필드 코엑스몰"])],
    requests=["register", "plan_ask"], missing=["lodging_name"], trip={"days": 4}))
S("C07", "paragraph", text("주말에 혼자 서울 당일치기 해요. 아침 10시 서울역 도착, 남산타워까지 걸어 올라가 보고 싶고요, 점심은 남대문시장에서 갈치조림, "
                          "오후엔 덕수궁, 저녁 기차가 7시라 6시 반까지는 서울역으로 돌아와야 해요."),
  G([it(1, None, "10:00", "서울역", canon=["서울역"]), it(1, None, None, "남산타워", canon=NST),
     it(1, None, None, "남대문시장", "dining", canon=["남대문시장"]), it(1, None, None, "덕수궁", canon=["덕수궁"])],
    moves=[mv("walk", frm="서울역", to="남산타워")], conditions=[cond("finish_by:18:30")],
    missing=["first_day_date"], trip={"party_size": 1, "days": 1}))
S("C08", "paragraph", text("부모님 모시고 3박 4일 갑니다 11월 12일 도착. 숙소는 신라호텔. 매일 저녁 6시 전에는 숙소로 돌아갔으면 좋겠고, "
                          "맛집 위주로 짜 주시되 첫날 저녁은 호텔 안 라연에서 먹기로 했어요."),
  G([it(1, D(11, 12), None, "신라호텔", "lodging", canon=["서울신라호텔", "신라호텔"]),
     it(1, D(11, 12), None, "라연", "dining", canon=["라연"])],
    conditions=[cond("finish_by:18:00")], preferences=["food_focus", "elderly_friendly"],
    requests=["register", "plan_ask"], trip={"days": 4, "nights": 3}))

# ── D. CSV · JSON(채팅에 붙여 넣은 글) ───────────────────────────────
S("D01", "csv", text("날짜,시간,장소,메모\n2026-10-25,09:00,경복궁,한복 대여\n2026-10-25,12:00,토속촌삼계탕,\n2026-10-25,14:00,국립고궁박물관,\n"
                     "2026-10-25,,광화문,택시로 이동\n2026-10-26,10:00,롯데월드타워,서울스카이 예약"),
  G([it(1, D(10, 25), "09:00", "경복궁", canon=GBG), it(1, D(10, 25), "12:00", "토속촌삼계탕", "dining", canon=["토속촌삼계탕"]),
     it(1, D(10, 25), "14:00", "국립고궁박물관", canon=["국립고궁박물관"]), it(1, D(10, 25), None, "광화문", canon=["광화문"]),
     it(2, D(10, 26), "10:00", "롯데월드타워", canon=["롯데월드타워", "서울스카이"])],
    moves=[mv("taxi", frm="국립고궁박물관", to="광화문")]))
S("D02", "csv", text("일차,시간,할 일\n1,오전 10시,창덕궁 후원 투어\n1,점심,익선동 한옥 카페 거리\n1,오후 3시,종묘\n2,오전 11시,여의도 더현대 서울\n2,저녁,여의도 한강공원 치킨"),
  G([it(1, None, "10:00", "창덕궁 후원", canon=["창덕궁", "창덕궁 후원"]), it(1, None, None, "익선동", "dining"),
     it(1, None, "15:00", "종묘", canon=["종묘"]), it(2, None, "11:00", "더현대 서울", canon=["더현대 서울"]),
     it(2, None, None, "여의도 한강공원", "dining", canon=["여의도한강공원"])],
    missing=["first_day_date"]))
S("D03", "csv", text("Day\tTime\tPlace\tTransport\n1\t10:00\tGyeongbokgung Palace\tsubway\n1\t13:00\t명동교자\twalk\n"
                     "1\t16:00\tN Seoul Tower\ttaxi\n2\t09:30\tStarfield COEX Mall\tsubway"),
  G([it(1, None, "10:00", "Gyeongbokgung Palace", canon=GBG), it(1, None, "13:00", "명동교자", "dining", canon=["명동교자 본점", "명동교자"]),
     it(1, None, "16:00", "N Seoul Tower", canon=NST), it(2, None, "09:30", "Starfield COEX Mall", canon=["스타필드 코엑스몰", "코엑스"])],
    moves=[mv("subway", to="Gyeongbokgung Palace"), mv("walk", frm="Gyeongbokgung Palace", to="명동교자"),
           mv("taxi", frm="명동교자", to="N Seoul Tower"), mv("subway", to="Starfield COEX Mall")],
    missing=["first_day_date"]))
S("J01", "json", text('{"trip":{"start":"2026-11-10","days":2,"people":3},"plan":[{"day":1,"time":"10:00","place":"국립중앙박물관"},'
                      '{"day":1,"time":"13:00","place":"이태원 점심"},{"day":1,"time":"16:00","place":"한남동 리움미술관"},'
                      '{"day":2,"time":"11:00","place":"성수동 서울숲","note":"비 오면 대신 실내 전시"}]}'),
  G([it(1, D(11, 10), "10:00", "국립중앙박물관", canon=["국립중앙박물관"]), it(1, D(11, 10), "13:00", "이태원", "dining"),
     it(1, D(11, 10), "16:00", "리움미술관", canon=["리움미술관"]), it(2, D(11, 11), "11:00", "서울숲", canon=["서울숲"])],
    conditions=[cond("if_rain_indoor", "서울숲")], trip={"party_size": 3, "days": 2}))
S("J02", "json", text('[\n  {"title": "창경궁 산책", "start": "2026-10-28T09:30", "end": "2026-10-28T11:00"},\n'
                      '  {"title": "대학로 마로니에공원", "start": "2026-10-28T11:30"},\n'
                      '  {"title": "혜화 학림다방", "start": "2026-10-28T13:00", "type": "cafe"},\n'
                      '  {"title": "낙산공원 야경", "start": "2026-10-28T19:00", "transport": "taxi"}\n]'),
  G([it(1, D(10, 28), "09:30", "창경궁", end="11:00", canon=["창경궁"]),
     it(1, D(10, 28), "11:30", "마로니에공원", canon=["마로니에공원"]),
     it(1, D(10, 28), "13:00", "학림다방", "dining", canon=["학림다방"]), it(1, D(10, 28), "19:00", "낙산공원", canon=["낙산공원"])],
    moves=[mv("taxi", frm="학림다방", to="낙산공원")]))
d = D(11, 21)
S("J03", "json", text('{"날짜": "11/21", "일정": ["10시 경복궁", "12시 통인시장 도시락카페", "3시 서촌 골목 산책", "6시 광화문 교보문고"], '
                      '"요청": "저녁 맛집 하나 추천해 주세요"}'),
  G([it(1, d, "10:00", "경복궁", canon=GBG), it(1, d, "12:00", "통인시장 도시락카페", "dining", canon=["통인시장"]),
     it(1, d, "15:00", "서촌", canon=["서촌"]), it(1, d, "18:00", "광화문 교보문고", canon=["교보문고 광화문점"])],
    requests=["register", "plan_ask"]))

# ── X. 메모처럼 쓴 엑셀(한 칸에 하루 통째 · 병합 칸 · 비고 칸) ───────────
S("X01", "excel_memo", xlsx([["날짜", "일정", "비고"],
                             [date(2026, 10, 30), "10시 창덕궁 → 12시 광장시장 점심 → 3시 청계천 걷기 → 7시 을지로 노가리 골목", "택시 위주"],
                             [date(2026, 10, 31), "오전 롯데월드 / 오후 석촌호수 / 저녁 잠실 새마을시장", "비 오면 롯데월드몰만"]]),
  G([it(1, D(10, 30), "10:00", "창덕궁", canon=["창덕궁"]), it(1, D(10, 30), "12:00", "광장시장", "dining", canon=["광장시장"]),
     it(1, D(10, 30), "15:00", "청계천", canon=["청계천"]), it(1, D(10, 30), "19:00", "을지로 노가리 골목", "dining"),
     it(2, D(10, 31), None, "롯데월드", canon=["롯데월드", "롯데월드 어드벤처"]), it(2, D(10, 31), None, "석촌호수", canon=["석촌호수"]),
     it(2, D(10, 31), None, "잠실 새마을시장", "dining", canon=["새마을전통시장", "잠실새마을시장"])],
    moves=[mv("taxi", scope="day", day=1)], conditions=[cond("if_rain_indoor", "롯데월드")], preferences=["prefer_taxi"]))
S("X02", "excel_memo", xlsx([["일자", "시간", "장소", "교통"],
                             [date(2026, 11, 5), time(9, 0), "경복궁", "지하철"],
                             [None, time(11, 30), "삼청동 수제비", "도보"],
                             [None, time(14, 0), "국립현대미술관 서울", "도보"],
                             [date(2026, 11, 6), time(10, 0), "남산골한옥마을", "택시"],
                             [None, time(13, 0), "명동 교자", "도보"]], merges=["A2:A4", "A5:A6"]),
  G([it(1, D(11, 5), "09:00", "경복궁", canon=GBG), it(1, D(11, 5), "11:30", "삼청동 수제비", "dining", canon=["삼청동수제비"]),
     it(1, D(11, 5), "14:00", "국립현대미술관 서울", canon=["국립현대미술관 서울관", "국립현대미술관 서울"]),
     it(2, D(11, 6), "10:00", "남산골한옥마을", canon=["남산골한옥마을"]),
     it(2, D(11, 6), "13:00", "명동 교자", "dining", canon=["명동교자 본점", "명동교자"])],
    moves=[mv("subway", to="경복궁"), mv("walk", frm="경복궁", to="삼청동 수제비"), mv("walk", frm="삼청동 수제비", to="국립현대미술관 서울"),
           mv("taxi", to="남산골한옥마을"), mv("walk", frm="남산골한옥마을", to="명동 교자")]))
S("X03", "excel_memo", xlsx([["서울 여행 계획표 (3명)"], [],
                             ["Day", "오전", "점심", "오후", "저녁", "비고"],
                             ["1일 (11/14)", "경복궁", "토속촌", "북촌 한옥마을", "광장시장", "첫날은 천천히"],
                             ["2일 (11/15)", "롯데월드", "", "석촌호수", "잠실 방이먹자골목", "아이 키 제한 확인 필요"]]),
  G([it(1, D(11, 14), None, "경복궁", canon=GBG), it(1, D(11, 14), None, "토속촌", "dining", canon=["토속촌삼계탕", "토속촌"]),
     it(1, D(11, 14), None, "북촌 한옥마을", canon=["북촌한옥마을"]), it(1, D(11, 14), None, "광장시장", "dining", canon=["광장시장"]),
     it(2, D(11, 15), None, "롯데월드", canon=["롯데월드", "롯데월드 어드벤처"]), it(2, D(11, 15), None, "석촌호수", canon=["석촌호수"]),
     it(2, D(11, 15), None, "방이먹자골목", "dining", canon=["방이먹자골목"])],
    preferences=["slow_pace", "kid_friendly"], requests=["register", "question"], trip={"party_size": 3}))
S("X04", "excel_memo", xlsx([["Date", "Time", "Spot", "Move"],
                             [datetime(2026, 10, 23), "10:00~12:00", "국립중앙박물관", ""],
                             [None, "12:30~13:30", "용산 해방촌 점심", "버스 20분"],
                             [None, "14:30~16:00", "N서울타워", "케이블카"],
                             [None, "18:00~", "명동 쇼핑", "도보"]], merges=["A2:A5"]),
  G([it(1, D(10, 23), "10:00", "국립중앙박물관", end="12:00", canon=["국립중앙박물관"]),
     it(1, D(10, 23), "12:30", "해방촌", "dining", end="13:30"),
     it(1, D(10, 23), "14:30", "N서울타워", end="16:00", canon=NST), it(1, D(10, 23), "18:00", "명동", canon=["명동"])],
    moves=[mv("bus", frm="국립중앙박물관", to="해방촌"), mv("cablecar", frm="해방촌", to="N서울타워"), mv("walk", frm="N서울타워", to="명동")]))

# ── T. 채팅에 붙여 넣은 표 ─────────────────────────────────────────
d = D(10, 29)
S("T01", "pasted_table", text("| 시간 | 장소 | 메모 |\n|---|---|---|\n| 09:00 | 경복궁 | 수문장 교대식 10시 |\n| 11:30 | 국립민속박물관 | |\n"
                              "| 13:00 | 삼청동 | 점심 |\n| 15:00 | 창덕궁 | 후원 예약 15:30 |\n날짜는 10월 29일이에요"),
  G([it(1, d, "09:00", "경복궁", canon=GBG), it(1, d, "11:30", "국립민속박물관", canon=["국립민속박물관"]),
     it(1, d, "13:00", "삼청동", "dining"), it(1, d, "15:00", "창덕궁", canon=["창덕궁"])]))
d = D(11, 9)
S("T02", "pasted_table", text("월요일(11/9)\t\t\n오전\t경복궁 + 한복\t\n점심\t광화문 미진 메밀\t\n오후\t청와대 관람\t예약 완료\n저녁\t서촌 계단집\t"),
  G([it(1, d, None, "경복궁", canon=GBG), it(1, d, None, "광화문 미진", "dining", canon=["미진 광화문점", "광화문미진"]),
     it(1, d, None, "청와대", canon=["청와대"]), it(1, d, None, "서촌 계단집", "dining", canon=["계단집"])]))
S("T03", "pasted_table", text("📍 1일차 (토)\n⏰ 10:00 ▶ 홍대입구역 집합\n⏰ 11:00 ▶ 연남동 카페 투어 ☕\n⏰ 13:00 ▶ 망원시장 먹방 🍢\n"
                              "⏰ 16:00 ▶ 망원한강공원 🚲\n📍 2일차 (일)\n⏰ 12:00 ▶ 합정 메세나폴리스"),
  G([it(1, D(10, 17), "10:00", "홍대입구역", canon=["홍대입구역"]), it(1, D(10, 17), "11:00", "연남동 카페", "dining"),
     it(1, D(10, 17), "13:00", "망원시장", "dining", canon=["망원시장"]), it(1, D(10, 17), "16:00", "망원한강공원", canon=["망원한강공원"]),
     it(2, D(10, 18), "12:00", "메세나폴리스", canon=["메세나폴리스"])]))

# ── E. 여러 번 나눠 보낸 메시지 ─────────────────────────────────────
d = D(10, 22)
S("E01", "multi_message", messages("서울 여행 일정 보낼게요", "10/22 목요일", "10시 경복궁", "12시 반 토속촌", "아 그리고 3시에 국립현대미술관", "저녁은 아직 못 정했어요"),
  G([it(1, d, "10:00", "경복궁", canon=GBG), it(1, d, "12:30", "토속촌", "dining", canon=["토속촌삼계탕", "토속촌"]),
     it(1, d, "15:00", "국립현대미술관", canon=["국립현대미술관 서울관"])], requests_optional=["plan_ask"]))
d = D(10, 17)
S("E02", "multi_message", messages("내일 일정이요", "오전엔 창덕궁", "점심 먹고 종묘", "저녁 7시에 을지로3가 만선호프", "이동은 다 지하철로 할게요"),
  G([it(1, d, None, "창덕궁", canon=["창덕궁"]), it(1, d, None, "종묘", canon=["종묘"]),
     it(1, d, "19:00", "만선호프", "dining", canon=["만선호프"])],
    moves=[mv("subway", scope="all")]))
S("E03", "multi_message", messages("11월 1일", "09:00 서울숲", "11:00 성수 어니언", "13:00 언더스탠드에비뉴", "11월 2일", "10:00 코엑스 별마당도서관", "12:00 봉은사"),
  G([it(1, D(11, 1), "09:00", "서울숲", canon=["서울숲"]), it(1, D(11, 1), "11:00", "어니언", "dining", canon=["어니언 성수", "어니언"]),
     it(1, D(11, 1), "13:00", "언더스탠드에비뉴", canon=["언더스탠드에비뉴"]),
     it(2, D(11, 2), "10:00", "별마당도서관", canon=["별마당도서관", "코엑스"]), it(2, D(11, 2), "12:00", "봉은사", canon=["봉은사"])]))
d = D(10, 21)
S("E04", "multi_message", messages("안녕하세요 다음주 수요일에 가요", "남산골한옥마을 → 명동성당 → 명동교자에서 저녁", "몇 시에 출발하면 좋을까요?"),
  G([it(1, d, None, "남산골한옥마을", canon=["남산골한옥마을"]), it(1, d, None, "명동성당", canon=["명동성당", "명동대성당"]),
     it(1, d, None, "명동교자", "dining", canon=["명동교자 본점", "명동교자"])],
    requests=["register", "question"]))

# ── F. 계획 + 질문 + 짜기 요청이 섞인 메시지 ────────────────────────────
d = D(11, 8)
S("F01", "mixed_request", text("11월 8일 일요일에 가요. 10시 경복궁, 12시 반 통인시장 점심까지는 정했고 오후는 알아서 채워 주세요. 그리고 경복궁 일요일에 문 여나요?"),
  G([it(1, d, "10:00", "경복궁", canon=GBG), it(1, d, "12:30", "통인시장", "dining", canon=["통인시장"])],
    requests=["register", "plan_ask", "question"]))
S("F02", "mixed_request", text("일정 짜줘. 10월 30일~31일, 커플이고 야경 좋은 곳이랑 분위기 좋은 레스토랑 위주로. 31일 저녁엔 이미 롯데월드타워 서울스카이 예약해 뒀어 (8시)"),
  G([it(2, D(10, 31), "20:00", "롯데월드타워 서울스카이", canon=["서울스카이", "롯데월드타워"])],
    preferences=["night_view", "nice_restaurants"], requests=["register", "plan_ask"], trip={"party_size": 2, "days": 2}))
d = D(11, 3)
S("F03", "mixed_request", text("1일차 2026-11-03: 10:00 국립중앙박물관 / 13:00 이태원 / 17:00 반포한강공원 달빛무지개분수. "
                               "2일차는 비워둘게요, 추천 부탁. 참고로 둘째 날 비 소식 있던데 우산 필요할까요?"),
  G([it(1, d, "10:00", "국립중앙박물관", canon=["국립중앙박물관"]), it(1, d, "13:00", "이태원", canon=["이태원"]),
     it(1, d, "17:00", "반포한강공원 달빛무지개분수", canon=["달빛무지개분수", "반포한강공원"])],
    requests=["register", "plan_ask", "question"]))
d = D(10, 24)
S("F04", "mixed_request", text("택시 타면 경복궁에서 동대문까지 얼마나 걸려요? 일정은 10/24 10시 경복궁 1시 동대문 DDP 5시 남산"),
  G([it(1, d, "10:00", "경복궁", canon=GBG), it(1, d, "13:00", "DDP", canon=["동대문디자인플라자", "DDP"]),
     it(1, d, "17:00", "남산", canon=["남산", "남산공원", "N서울타워"])],
    requests=["register", "question"], note="첫 문장의 「경복궁」「동대문」은 질문 속 말이라 항목이 아니다 — 읽으면 중복 항목(정밀도 손해)"))
d = D(11, 20)
S("F05", "mixed_request", text("엄마 생신 기념 여행인데요 11/20 금요일 저녁 6시 반에 한남동 '모수' 예약이 있어요. 그 전에 오후 일정 2~3개 정도 근처로 짜 주시고, 혹시 모수 드레스코드 있나요?"),
  G([it(1, d, "18:30", "모수", "dining", canon=["모수", "모수 서울"])],
    requests=["register", "plan_ask", "question"]))

# ── G. 중간 정정 ────────────────────────────────────────────────
d = D(10, 27)
S("G01", "correction", text("1일차 10/27\n10:00 경복궁\n12:00 광장시장\n15:00 창덕궁\n아 첫날 순서 바꿀래 창덕궁 먼저 가고 경복궁은 오후에"),
  G([it(1, d, "10:00", "창덕궁", canon=["창덕궁"]), it(1, d, "12:00", "광장시장", "dining", canon=["광장시장"]),
     it(1, d, "15:00", "경복궁", canon=GBG)],
    requests=["register", "correction"], note="정정 반영 정답: 창덕궁·경복궁의 시각 자리를 맞바꾼다"))
d = D(10, 22)
S("G02", "correction", messages("10/22 10시 남산타워 12시 명동 점심 3시 덕수궁", "아 잠깐 남산타워 말고 롯데타워로 바꿀게요"),
  G([it(1, d, "10:00", "롯데타워", canon=["롯데월드타워", "서울스카이"]), it(1, d, "12:00", "명동", "dining"),
     it(1, d, "15:00", "덕수궁", canon=["덕수궁"])],
    requests=["register", "correction"], note="남산타워를 항목으로 남기면 틀림(정밀도)"))
d = D(11, 12)
S("G03", "correction", text("11/12 9시 창경궁 11시 대학로 2시 낙산공원 → 아니다 낙산공원은 빼고 그 시간에 이화벽화마을"),
  G([it(1, d, "09:00", "창경궁", canon=["창경궁"]), it(1, d, "11:00", "대학로", canon=["대학로"]),
     it(1, d, "14:00", "이화벽화마을", canon=["이화벽화마을", "이화마을"])],
    requests=["register", "correction"], note="낙산공원을 항목으로 남기면 틀림"))
d = D(10, 25)
S("G04", "correction", messages("다음주 토요일에 홍대 갈 거예요", "12시 연남동 점심, 3시 홍대 걷고싶은거리", "아 날짜 틀렸다 일요일이에요"),
  G([it(1, d, None, "홍대", optional=True), it(1, d, "12:00", "연남동", "dining"),
     it(1, d, "15:00", "홍대 걷고싶은거리", canon=["걷고싶은거리", "홍대 걷고싶은거리"])],
    requests=["register", "correction"], note="다음주 토요일 10-24 → 정정 뒤 일요일 10-25"))


# ── R. 실제 접수 원문(x600 서버 cs 프로젝트 DB, 2026-10-06~10-15) ────────
REAL: list[dict[str, Any]] = []
TEMPLATE_DAY1 = "09:00 호텔 조식\n10:00 경복궁 · 한복 체험, 12:00 종료\n12:30 광장시장 · 점심\n15:00 국립중앙박물관 · 전시 관람\n19:00 N서울타워 · 예약 있음"
TEMPLATE_DAY2 = "09:00 호텔 조식\n10:00 북촌한옥마을 · 산책\n12:00 인사동 · 점심\n14:00 창덕궁 · 후원 관람\n17:00 청계천 · 산책"


def R(case_id, received, inputs, gold, *, note="", crlf=True):
    # ★웹 입력칸으로 들어온 원문은 줄 끝이 CRLF 다(DB 원문 그대로) — 서버가 받는 글과 같게 되돌린다
    if crlf:   # 한 건(R14)은 LF 로 들어왔다 — API 로 넣은 글로 보인다
        inputs = [{**one, "text": one["text"].replace(chr(10), chr(13) + chr(10))} for one in inputs]
    REAL.append({"case_id": case_id, "shape": "real", "origin": "real", "author": "정답: " + AUTHOR,
                 "provenance": {"source": "x600 서버 cs 프로젝트 DB intake_sources.transcript", "first_received_kst": received,
                                "transcript_md5": None},          # build.py 가 원문으로 채운다
                 "today": received[:10], "inputs": inputs, "gold": gold, "note": note})


def template_items(d1, d2, *, day1=None, day2=None):
    a = [it(1, d1, "09:00", "호텔", "dining"), it(1, d1, "10:00", "경복궁", end="12:00", canon=GBG),
         it(1, d1, "12:30", "광장시장", "dining", canon=["광장시장"]), it(1, d1, "15:00", "국립중앙박물관", canon=["국립중앙박물관"]),
         it(1, d1, "19:00", "N서울타워", canon=NST)]
    b = [it(2, d2, "09:00", "호텔", "dining"), it(2, d2, "10:00", "북촌한옥마을", canon=["북촌한옥마을"]),
         it(2, d2, "12:00", "인사동", "dining", canon=["인사동"]), it(2, d2, "14:00", "창덕궁", canon=["창덕궁"]),
         it(2, d2, "17:00", "청계천", canon=["청계천"])]
    return (day1 or a) + (day2 or b)


R("R01", "2026-10-06T00:05",
  text(f"1일차 · 2026-10-13\n{TEMPLATE_DAY1}\n\n2일차 · 2026-10-14\n{TEMPLATE_DAY2}"),
  G(template_items(D(10, 13), D(10, 14)), missing=["lodging_name"]), note="웹 화면의 예시 원문 — 실제 접수의 절반 이상이 이 모양")
R("R02", "2026-10-07T10:24",
  text("1일차 · 2026-10-14\n\n10:00 경복궁 · 한복 체험, 12:00 종료\n12:30 광장시장 삼겹살집\n15:00 국립중앙박물관 · 전시 관람\n19:00 N서울타워 · 예약 있음\n\n"
       "2일차 · 2026-10-15\n\n10:00 북촌한옥마을 · 산책\n12:00 인사동 삼계탕\n14:00 창덕궁 · 후원 관람\n17:00 청계천 · 산책"),
  G([it(1, D(10, 14), "10:00", "경복궁", end="12:00", canon=GBG), it(1, D(10, 14), "12:30", "광장시장 삼겹살집", "dining"),
     it(1, D(10, 14), "15:00", "국립중앙박물관", canon=["국립중앙박물관"]), it(1, D(10, 14), "19:00", "N서울타워", canon=NST),
     it(2, D(10, 15), "10:00", "북촌한옥마을", canon=["북촌한옥마을"]), it(2, D(10, 15), "12:00", "인사동 삼계탕", "dining"),
     it(2, D(10, 15), "14:00", "창덕궁", canon=["창덕궁"]), it(2, D(10, 15), "17:00", "청계천", canon=["청계천"])]))
R("R03", "2026-10-08T16:30", text("10:00 박물관 관람"),
  G([it(None, None, "10:00", "박물관")], missing=["first_day_date"]))
R("R04", "2026-10-12T09:46", text("연동 시험용 서울 3박 4일 여행입니다. 성인 2명, 대중교통 중심으로 이동하고 관광과 식사를 적당히 배치해 주세요. 숙소·항공·업체 예약이나 결제는 하지 않습니다."),
  G([], moves=[mv("transit", scope="all")], preferences=["prefer_transit"], requests=["plan_ask"], missing=["first_day_date"],
    trip={"party_size": 2, "days": 4, "nights": 3}), note="「연동 시험용」 — 다른 세션이 쓴 글일 수 있다")
R("R05", "2026-10-12T09:48", text("연동 시험용 서울 3박 4일입니다. 성인 2명, 대중교통 중심으로 관광과 식사를 적당히 배치해 주세요. 매일 모든 방문과 이동을 20:00 이전에 마치고, 마지막 날은 18:00에 일정을 종료해 주세요. 숙소·항공·업체 예약이나 결제는 하지 않습니다."),
  G([], moves=[mv("transit", scope="all")], conditions=[cond("finish_by:20:00"), cond("finish_by:18:00")], preferences=["prefer_transit"],
    requests=["plan_ask"], missing=["first_day_date"], trip={"party_size": 2, "days": 4, "nights": 3}), note="「연동 시험용」 — 다른 세션이 쓴 글일 수 있다")
R("R06", "2026-10-12T13:52", text("오늘 지금 당장 남부터미널 갓다가 바로 올거야"),
  G([it(1, D(10, 12), None, "남부터미널", canon=["남부터미널", "서울남부터미널"])]), note="시각은 「지금」 — 정답 시각은 두지 않는다")
R("R07", "2026-10-12T15:41", text("지금 당장 남부터미널 갈거야 일정 잡아주ㅏ"),
  G([it(1, D(10, 12), None, "남부터미널", canon=["남부터미널", "서울남부터미널"])], requests_optional=["plan_ask"]),
  note="「일정 잡아줘」 — 이 일정을 넣어 달라는 뜻으로 보지만 짜기 요청으로 읽어도 틀리지 않게 했다")
R("R08", "2026-10-13T06:16",
  text("1일차 · 2026-10-13\n09:00 서울역 도착\n10:30 경복궁 관람\n12:30 토속촌 삼계탕 점심\n14:30 국립현대미술관 서울\n17:00 북촌한옥마을 산책\n19:00 광장시장 저녁\n\n"
       "2일차 · 2026-10-14\n10:00 남산서울타워\n12:30 명동교자 점심\n15:00 롯데월드타워 서울스카이\n18:30 성수동 저녁 식사"),
  G([it(1, D(10, 13), "09:00", "서울역", canon=["서울역"]), it(1, D(10, 13), "10:30", "경복궁", canon=GBG),
     it(1, D(10, 13), "12:30", "토속촌", "dining", canon=["토속촌삼계탕", "토속촌"]),
     it(1, D(10, 13), "14:30", "국립현대미술관 서울", canon=["국립현대미술관 서울관", "국립현대미술관 서울"]),
     it(1, D(10, 13), "17:00", "북촌한옥마을", canon=["북촌한옥마을"]), it(1, D(10, 13), "19:00", "광장시장", "dining", canon=["광장시장"]),
     it(2, D(10, 14), "10:00", "남산서울타워", canon=NST), it(2, D(10, 14), "12:30", "명동교자", "dining", canon=["명동교자 본점", "명동교자"]),
     it(2, D(10, 14), "15:00", "롯데월드타워 서울스카이", canon=["서울스카이", "롯데월드타워"]), it(2, D(10, 14), "18:30", "성수동", "dining")]))
R("R09", "2026-10-13T12:49",
  text("1일차 · 2026-10-20\n09:00 호텔 조식\n10:00 경복궁 · 한복 체험, 12:00 종료\n12:30 광장시장 · 점심\n15:00 스카이타워 \n19:00 N서울타워 · 예약 있음\n\n"
       f"2일차 · 2026-10-21\n{TEMPLATE_DAY2}"),
  G(template_items(D(10, 20), D(10, 21), day1=[
      it(1, D(10, 20), "09:00", "호텔", "dining"), it(1, D(10, 20), "10:00", "경복궁", end="12:00", canon=GBG),
      it(1, D(10, 20), "12:30", "광장시장", "dining", canon=["광장시장"]), it(1, D(10, 20), "15:00", "스카이타워"),
      it(1, D(10, 20), "19:00", "N서울타워", canon=NST)]), missing=["lodging_name"]),
  note="「스카이타워」 — 서울스카이인지 다른 곳인지 원문만으로 못 정한다(찾은 장소 정답 없음)")
R("R10", "2026-10-13T18:10", text("18:20 여의도 더현대\n19:00 당산 허브족발"),
  G([it(1, None, "18:20", "여의도 더현대", canon=["더현대 서울"]), it(1, None, "19:00", "당산 허브족발", "dining", canon=["허브족발"])],
    missing_optional=["first_day_date"]), note="날짜 없음 — 접수 10분 뒤 시각이라 오늘로 볼 수도 있어 날짜 정답 · 날짜 묻기 모두 점수에서 뺐다")
R("R11", "2026-10-13T18:22", text("2026-10-13\n\n18:30 더현대 서울\n19:00 또순이네\n20:00 카페 진정성"),
  G([it(1, D(10, 13), "18:30", "더현대 서울", canon=["더현대 서울"]), it(1, D(10, 13), "19:00", "또순이네", "dining", canon=["또순이네"]),
     it(1, D(10, 13), "20:00", "카페 진정성", "dining", canon=["카페 진정성", "진정성"])]))
R("R12", "2026-10-14T16:53", text("1일차 · 2026-11-06\n10:00 경복궁 관람\n15:00 롯데호텔 서울 체크인\n\n2일차 · 2026-11-07\n11:00 남산서울타워"),
  G([it(1, D(11, 6), "10:00", "경복궁", canon=GBG), it(1, D(11, 6), "15:00", "롯데호텔 서울", "lodging", canon=["롯데호텔 서울"]),
     it(2, D(11, 7), "11:00", "남산서울타워", canon=NST)]))
R("R13", "2026-10-14T22:04", text("서울 2일 여행 · 4명\n\n1일차 · 2026-10-21\n10:00~11:30 경복궁 관람\n15:00 호텔 체크인\n\n2일차 · 2026-10-22\n11:00~12:30 N서울타워 관람"),
  G([it(1, D(10, 21), "10:00", "경복궁", end="11:30", canon=GBG), it(1, D(10, 21), "15:00", "호텔", "lodging"),
     it(2, D(10, 22), "11:00", "N서울타워", end="12:30", canon=NST)],
    missing=["lodging_name"], trip={"party_size": 4, "days": 2}))
R("R14", "2026-10-15T12:30", text("2026-11-20\n10:00~11:30 경복궁 관람\n15:00 더 플라자 호텔 서울 체크인\n2026-11-21\n11:00~12:30 N서울타워 관람\n11:00 체크아웃"),
  G([it(1, D(11, 20), "10:00", "경복궁", end="11:30", canon=GBG),
     it(1, D(11, 20), "15:00", "더 플라자 호텔 서울", "lodging", canon=["더 플라자 호텔", "더플라자호텔"]),
     it(2, D(11, 21), "11:00", "N서울타워", end="12:30", canon=NST), it(2, D(11, 21), "11:00", "체크아웃", "lodging", optional=True)]), crlf=False)
R("R15", "2026-10-15T12:44", text("10월 17일에 아침에 한강가서 구경 좀 하다가 점심으로 여의도 또순이네 갔다가 홍대 ak플라자에 갈거야"),
  G([it(1, D(10, 17), None, "한강"), it(1, D(10, 17), None, "또순이네", "dining", canon=["또순이네"]),
     it(1, D(10, 17), None, "홍대 ak플라자", canon=["AK플라자 홍대", "AK& 홍대"])]))
R("R16", "2026-10-15T12:46", text("1일차 2026.10.17\n10시 여의도 한강공원 구경\n12시 또순이네 점심식사\n14시 홍대 ak 플라자"),
  G([it(1, D(10, 17), "10:00", "여의도 한강공원", canon=["여의도한강공원"]), it(1, D(10, 17), "12:00", "또순이네", "dining", canon=["또순이네"]),
     it(1, D(10, 17), "14:00", "홍대 ak 플라자", canon=["AK플라자 홍대", "AK& 홍대"])]))
R("R17", "2026-10-15T16:15",
  text("1일차 · 2026-10-20\n12:00 연신내에서 점심\n18:30 망원동에서 저녁\n2일차 · 2026-10-21\n12:00 해방촌에서 점심\n18:30 익선동에서 저녁\n"
       "3일차 · 2026-10-22\n12:00 서촌에서 점심\n18:30 은평구에서 저녁"),
  G([it(1, D(10, 20), "12:00", "연신내", "dining"), it(1, D(10, 20), "18:30", "망원동", "dining"),
     it(2, D(10, 21), "12:00", "해방촌", "dining"), it(2, D(10, 21), "18:30", "익선동", "dining"),
     it(3, D(10, 22), "12:00", "서촌", "dining"), it(3, D(10, 22), "18:30", "은평구", "dining")]),
  note="지역 + 끼니만 — 가게는 우리가 골라도 되는 값(고객만 아는 값이 아니다)")
R("R18", "2026-10-15T19:11",
  text("1일차 · 2026-10-22\n8:00 경복궁 · 한복 체험, 9:00 종료\n09:30 홍대 조식\n10:00 북촌한옥마을 · 산책\n12:00 인사동 · 점심\n14:00 창덕궁 · 후원 관람\n17:00 청계천 · 산책"),
  G([it(1, D(10, 22), "08:00", "경복궁", end="09:00", canon=GBG), it(1, D(10, 22), "09:30", "홍대", "dining"),
     it(1, D(10, 22), "10:00", "북촌한옥마을", canon=["북촌한옥마을"]), it(1, D(10, 22), "12:00", "인사동", "dining", canon=["인사동"]),
     it(1, D(10, 22), "14:00", "창덕궁", canon=["창덕궁"]), it(1, D(10, 22), "17:00", "청계천", canon=["청계천"])]))
R("R19", "2026-10-15T20:11",
  text(f"1일차 · 2026-10-22\n09:00 호텔 조식\n10:00 경복궁 · 한복 체험, 12:00 종료\n12:30 광장시장 · 점심\n15:00 국립중앙박물관 · 전시 관람\n택시로 이동\n"
       f"19:00 N서울타워 · 예약 있음\n\n2일차 · 2026-10-23\n{TEMPLATE_DAY2}"),
  G(template_items(D(10, 22), D(10, 23)), moves=[mv("taxi", frm="국립중앙박물관", to="N서울타워")], missing=["lodging_name"]),
  note="견본 사이에 「택시로 이동」 한 줄 — 이번 재설계의 출발점이 된 접수")
R("R20", "2026-10-15T20:41", text("1일차 · 2026-10-15\n20:00 서초동 대게나라 저녁\n21:00 고속터미널 · 신세계백화점\n22:00 여의도 · 산책"),
  G([it(1, D(10, 15), "20:00", "대게나라", "dining", canon=["대게나라"]),
     it(1, D(10, 15), "21:00", "신세계백화점", canon=["신세계백화점 강남점"]), it(1, D(10, 15), "22:00", "여의도", canon=["여의도한강공원", "여의도"])]))

ALL = SYNTHETIC + REAL

__all__ = ["ALL", "AUTHOR", "REAL", "SYNTHETIC", "TODAY"]

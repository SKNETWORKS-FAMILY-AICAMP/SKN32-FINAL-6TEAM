"""등록할 일정 이름 — `assemble._item_title`. `[2026-10-25 사용자 결정]`

☆왜: 처음 등록은 적힌 이름만 써서, 휴무인 창덕궁을 확인 화면에서 「쌈지길로 바꾸기」로 고르거나 「전체 자동 추천」이 바꾼 뒤 여행 화면이
「창덕궁」 + 아래 「쌈지길」이었다(수정 모드 완료 `reopen.py` 와 확인 화면 카드는 고른 곳의 이름을 일정 이름으로 보인다).
계약 `wiki/external/rest-endpoints/web-intakes.md` 의 `/confirm` 줄.

★지키려는 것: ①장소가 바뀐 일정(후보 · 검색 · 「맞아요」 · 전체 자동 추천)은 그 장소 이름 ②지역만 적어 서버가 채운 일정(처음 읽은 장소가 `nameless`
+ `via: autofix`)은 적힌 이름(여행 화면이 장소를 아래 줄에) ③계획서에서 찾은 곳 · 숙소 · 「식사」 같은 빈 이름은 지금 규칙 그대로
④고객이 제목을 직접 고쳤으면 그 제목.
"""
from app.domains.travel_ops.components.intake.assemble import _item_title, assemble


def row(title, place, *, method="customer", via=None, kind="activity", title_method="llm_agent"):
    evidence = {"via": via} if via else {}
    return {"title": title, "kind": kind,
            "place": {"name": place, "latitude": 37.58, "longitude": 126.99} if place else None,
            "claims": {"title": {"value": title, "method": title_method, "evidence": {}},
                       "place": {"value": {"name": place} if place else None, "method": method, "evidence": evidence}}}


def test_a_place_that_was_changed_names_the_stop():
    assert _item_title(row("창덕궁", "쌈지길")) == "쌈지길"                          # 휴무 대안 「쌈지길로 바꾸기」
    assert _item_title(row("남산서울타워", "N서울타워")) == "N서울타워"                # 「「N서울타워」 맞아요」
    assert _item_title(row("명동교자", "백제삼계탕", kind="dining")) == "백제삼계탕"     # 식사도 바꾸기로 고르면 그 이름
    assert _item_title(row("창덕궁", "쌈지길", via="autofix")) == "쌈지길"              # 「전체 자동 추천」이 휴무 곳을 바꿨다


def test_a_line_with_only_an_area_that_the_server_filled_keeps_the_written_name():
    assert _item_title(row("인사동", "양반댁", via="autofix", kind="dining"), filled=True) == "인사동"
    assert _item_title(row("성수 식당", "소문난성수감자탕", kind="dining"), filled=True) == "소문난성수감자탕"   # 고객이 직접 고르면 바꾼 것


def test_a_title_the_customer_wrote_on_the_check_screen_comes_first():
    assert _item_title(row("엄마랑 남산", "N서울타워", title_method="customer")) == "엄마랑 남산"


def test_a_place_read_from_the_plan_and_the_other_rules_stay_as_they_were():
    assert _item_title(row("경복궁 관람", "경복궁", method="lookup")) == "경복궁 관람"
    assert _item_title(row("롯데호텔 체크인", "롯데호텔 서울", kind="lodging")) == "롯데호텔 체크인"
    assert _item_title(row("식사", "양반댁", kind="dining")) == "양반댁 식사"
    assert _item_title(row("쌈지길", "쌈지길")) == "쌈지길"
    assert _item_title(row("", None)) == "(제목 없음)"


def _claim(index, field, value, method, evidence=None):
    return {"source_id": "s", "field": f"items[{index}].{field}", "value": value, "method": method,
            "evidence": {"line": index + 1, **(evidence or {})}, "needs_review": False, "note": None}


def test_the_registration_body_tells_a_filled_area_line_from_a_changed_place_by_the_first_reading():
    """등록 몸통이 그 판의 값 줄 전부에서 처음 읽은 장소 값(`nameless` 냐 찾은 곳이냐)을 보고 가른다 — 둘 다 마지막 값은 `customer` + `via: autofix`."""
    sources = [{"source_id": "s", "position": 0, "kind": "text", "filename": None,
                "transcript": "12:00 인사동 · 점심\n14:00 창덕궁 · 후원 관람"}]
    meal = {"name": "양반댁", "latitude": 37.5740, "longitude": 126.9850, "source": "customer_pick"}
    palace = {"name": "창덕궁", "latitude": 37.5794, "longitude": 126.9910, "source": "places"}
    swap = {"name": "쌈지길", "latitude": 37.5743, "longitude": 126.9852, "source": "customer_pick"}
    claims = []
    for index, (title, start, kind) in enumerate((("인사동", "12:00", "dining"), ("창덕궁", "14:00", "activity"))):
        claims += [_claim(index, "title", title, "llm_agent"), _claim(index, "date", "2030-11-06", "llm_agent"),
                   _claim(index, "starts_at", start, "llm_agent"), _claim(index, "kind", kind, "llm_agent")]
    claims += [_claim(0, "place", None, "lookup", {"method": "nameless"}), _claim(1, "place", palace, "lookup", {"method": "places"}),
               _claim(0, "place", meal, "customer", {"via": "autofix"}), _claim(1, "place", swap, "customer", {"via": "autofix"})]
    body = assemble(intake_id="i", revision=2, sources=sources, claims=claims).body
    assert [item["title"] for item in body["items"]] == ["인사동", "쌈지길"]

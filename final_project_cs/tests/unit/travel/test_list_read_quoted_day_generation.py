"""목록·하루 조회의 생성 범위 — 문장에 적힌 달력 날짜와 「대상 없음」을 **생성 단계에서** 묶는다(답을 고치지 않는다).

`[2026-10-26 수용 C02]` 「1월 2일 일정을 전부 보여줘」(여행 1일차 = 01-02, 지금 = 01-01)에 실제 E4B 가
`reads=[{fact: schedule, target_item: i2, reference: previous, query.day: today}]` + 같은 후보(`i2`)를 냈다.
서버는 계약대로(목록 조회는 빈 대상만, 다른 대상이 섞인 후보는 거부) 해석 실패로 끝냈다 — 날짜(오늘 ≠ 1월 2일)도 틀렸다.
고치는 곳은 생성 문법이다: ①목록 읽기(schedule·changeability·day)는 대상·변경 대상 none 과 범위(query)를 반드시 갖고
②목록 사실 후보는 같은 읽기 행동·빈 대상만 ③문장에 적힌 달력 날짜(일정의 월-일)가 있으면 범위의 날은 그 날(과 문장에 적힌 오늘·내일)만.
모델 답을 서버가 바꿔 쓰지 않는다 — 기존 `day_quotes`(시각 범위 옮기기)와 같은 「문장 근거로 생성만 제한」이다.
"""
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator

from app.domains.travel_ops.components.conversation import decision_unit as du

KST = ZoneInfo("Asia/Seoul")
LIST_FACTS = ("schedule", "changeability", "day")


def _item(seq, title, day, hour):
    return SimpleNamespace(item_id=uuid4(), kind="activity", title=title, place={"name": title}, seq=seq,
                           starts_at=datetime(2030, 1, day, hour, 0, tzinfo=KST),
                           ends_at=datetime(2030, 1, day, hour + 1, 0, tzinfo=KST), detail={}, locked=False, booking_id=None)


ITEMS = [_item(1, "북촌한옥마을", 2, 10), _item(2, "인사동", 2, 12), _item(3, "N서울타워", 2, 15), _item(4, "국립중앙박물관", 3, 10)]
STOPS = du.stops_of(ITEMS)
MESSAGE = "1월 2일 일정을 전부 보여줘"
NOW = datetime(2030, 1, 1, 9, 0, tzinfo=KST)

#: 실제 E4B 가 수용 C02 에서 낸 구조(합성 여행 · 합성 문장, 기록 진단용 맥락 칸만 뺐다)
OBSERVED_C02 = {
    "action": "answer_fact",
    "time_edit": {"boundary": "none", "scope": "item", "time": "", "duration_minutes": 0, "cascade": False,
                  "continue_previous": False, "evidence": ""},
    "place_search": {"relation": "none", "anchor_item": "none", "place_text": "", "evidence": ""},
    "place_setting": {"want": "any", "evidence": ""},  # v9: QA place_setting is a required generation field; neutral value per edit_intent.SYSTEM
    "target_item": "i2", "target_change": "none", "fact": "schedule", "destination_text": "", "condition_text": "",
    "anchor_kind": "none", "anchor_item": "none", "anchor_time": "", "at_day": "today", "relation": "after", "steps": 1,
    "minutes": 0,
    "reads": [{"fact": "schedule", "target_item": "i2", "origin_item": "none", "origin_text": "", "transport_mode": "any",
               "reference": "previous", "query": {"day": "today", "period": "all", "kind": "all", "position": "all"},
               "text": MESSAGE, "advice": "", "anchor_kind": "none", "anchor_item": "none", "anchor_time": "",
               "at_day": "today", "relation": "after", "steps": 1}],
    "social": "", "general_requests": [],
    "choices": [{"action": "answer_fact", "target_item": "i2", "target_change": "none", "fact": "schedule"}],
}


def _within_grammar(answer):
    """같은 문장 기준 생성 문법(모델에게 주는 형식) 안의 답인가."""
    return Draft202012Validator(du._schema(STOPS, [], message=MESSAGE)).is_valid(answer)


def _grounded(observed):
    """같은 모델 답을 새 문법이 허용하는 값으로만 옮긴 것 — 서버가 만든 값이 아니라 문법이 남긴 유일한 선택지다."""
    import copy
    answer = copy.deepcopy(observed)
    answer["reads"][0].update(target_item="none", query={"day": "d1", "period": "all", "kind": "all", "position": "all"})
    # `[2026-10-27 G]` 기준 없음(anchor_kind=none)의 앞뒤 칸은 at 하나만 남는다(`decision_unit._anchor_branches`) — 관측 답의 after 는 쓸모없는 칸을 채운 값이다
    answer["reads"][0].update(relation="at")
    answer["choices"] = []
    return answer


def _decide(answer, message=MESSAGE):
    class Chat:
        def structured(self, system, user, schema, *, num_predict=160):
            self.schema = schema
            return answer
    return du.decide(Chat(), stops=STOPS, changes=[], history=[], selected_item_id=None, message=message, now=NOW)


def test_observed_c02_answer_is_outside_the_generation_grammar():
    """RED 근거: 지금 문법은 1월 2일을 말한 목록 조회에 「오늘」 범위와 엉뚱한 대상 힌트를 허용한다."""
    assert not _within_grammar(OBSERVED_C02)


def test_grammar_admitted_c02_answer_lists_exactly_the_quoted_day():
    answer = _grounded(OBSERVED_C02)
    assert _within_grammar(answer)
    decision = _decide(answer)
    assert decision.action == "answer_fact" and decision.fact == "schedule" and decision.item is None
    assert decision.query == {"day": "d1", "period": "all", "kind": "all", "position": "all"}
    from app.domains.travel_ops.components.conversation import schedule_query
    text, _ = schedule_query.reply(decision.fact, decision.query, items=ITEMS, now=NOW)
    assert all(name in text for name in ("북촌한옥마을", "인사동", "N서울타워")) and "국립중앙박물관" not in text


def _alternatives(node):
    return node.get("anyOf", [node])


def _read_alternatives(schema, *, branches=None):
    for branch in branches or schema["anyOf"]:
        reads = branch["properties"].get("reads")
        if reads is None:
            continue
        yield from _alternatives(reads["items"])


def _admits_list_read(branch):
    reads = branch["properties"].get("reads") or {"items": {"properties": {"fact": {"enum": []}}}}
    return any(set(read["properties"]["fact"]["enum"]) & set(LIST_FACTS) for read in _alternatives(reads["items"]))


def _reading_branches(schema):
    """바꾸지 않는 할 일의 갈래(조회 범위가 읽기 범위인 갈래)."""
    editing = {"change_time", "apply_change", "add_item"}
    return [b for b in schema["anyOf"] if not set(b["properties"]["action"]["enum"]) & editing]


def test_every_list_read_alternative_requires_no_target_and_a_scope():
    schema = du._schema(STOPS, [], message=MESSAGE)
    seen = 0
    for read in _read_alternatives(schema):
        props = read["properties"]
        if not set(props["fact"]["enum"]) & set(LIST_FACTS):
            continue
        seen += 1
        assert set(props["fact"]["enum"]) <= set(LIST_FACTS)          # 목록 읽기와 한 일정 읽기를 섞지 않는다
        assert props["target_item"]["enum"] == ["none"] and props["target_change"]["enum"] == ["none"]
        assert props["query"].get("type") == "object" and "anyOf" not in props["query"]   # null 범위 없음
        assert props["query"]["properties"]["day"]["enum"] == ["d1"]                      # 문장에 적힌 1월 2일
    assert seen >= 1


def test_a_branch_that_admits_a_list_read_is_an_answer_without_candidates():
    """목록 사실 후보는 같은 읽기의 반복뿐이고 다른 대상이 섞이면 서버가 거부한다(계약) — 그 갈래는 후보를 내지 않는다."""
    schema = du._schema(STOPS, [], message=MESSAGE)
    listed = [b for b in schema["anyOf"] if _admits_list_read(b)]
    assert listed
    for branch in listed:
        assert branch["properties"]["action"]["enum"] == ["answer_fact"]
        assert branch["properties"]["choices"]["maxItems"] == 0
        assert branch["properties"]["reads"].get("minItems") == 1


def test_quoted_calendar_day_bounds_every_read_scope_but_unquoted_days_stay_open():
    quoted = du._schema(STOPS, [], message=MESSAGE)
    reading = _reading_branches(quoted)
    assert reading and all(b["properties"]["query"]["properties"]["day"]["enum"] == ["d1"] for b in reading)
    for read in _read_alternatives(quoted):
        scopes = [s for s in _alternatives(read["properties"]["query"]) if s.get("type") == "object"]
        assert scopes and all(s["properties"]["day"]["enum"] == ["d1"] for s in scopes)
    open_schema = du._schema(STOPS, [], message="둘째 날 일정 보여줘")
    days = [read["properties"]["query"]["properties"]["day"]["enum"] for read in _read_alternatives(open_schema)
            if set(read["properties"]["fact"]["enum"]) & set(LIST_FACTS)]
    assert days and all(d == ["all", "today", "tomorrow", "d1", "d2"] for d in days)


def test_quoted_calendar_labels_need_digit_boundaries_and_keep_spoken_relative_days():
    assert du.quoted_calendar_days(STOPS, "1월 2일 일정") == ["d1"]
    assert du.quoted_calendar_days(STOPS, "1월3일이랑 2030-01-02") == ["d1", "d2"]
    assert du.quoted_calendar_days(STOPS, "11월 2일 일정") == []        # 「11월 2일」은 「1월 2일」이 아니다
    assert du.quoted_calendar_days(STOPS, "1월 22일 일정") == []
    both = du._schema(STOPS, [], message="오늘 말고 1월 3일 일정 보여줘")
    days = {tuple(read["properties"]["query"]["properties"]["day"]["enum"]) for read in _read_alternatives(both)
            if set(read["properties"]["fact"]["enum"]) & set(LIST_FACTS)}
    assert days == {("d2", "today")}


def test_single_item_reads_and_choices_keep_their_targets():
    """한 일정 사실(시각 · 운영시간 …)과 그 후보는 지금처럼 대상을 고른다 — 묶는 것은 목록 사실뿐이다."""
    decision = _decide({**_grounded(OBSERVED_C02), "fact": "time", "target_item": "i2",
                        "reads": [{**OBSERVED_C02["reads"][0], "fact": "time", "target_item": "i2", "reference": "explicit",
                                   "query": None, "at_day": "none", "relation": "at", "text": "인사동 몇 시야"}],
                        "choices": [{"action": "answer_fact", "target_item": "i2", "target_change": "none", "fact": "hours"}]},
                       message="인사동 몇 시야")
    assert decision.fact == "time" and decision.item is ITEMS[1]
    schema = du._schema(STOPS, [], message="인사동 몇 시야")
    single = [read for read in _read_alternatives(schema) if "time" in read["properties"]["fact"]["enum"]]
    assert single and all("i2" in read["properties"]["target_item"]["enum"] for read in single)

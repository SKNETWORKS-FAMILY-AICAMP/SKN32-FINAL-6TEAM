# -*- coding: utf-8 -*-
"""계획 읽기 · 채팅에서 서울 밖 장소를 「못 찾음 — 정확한 이름을 알려 주세요」가 아니라 「서울 밖(부산 …)」으로 알린다.

`[2026-10-28 라우팅 전수검사 E D3 후속]` 장소 검색(웹)은 10-27 에 `outside_service_area:<시·도>` 로 알리게 됐지만(D2),
계획 읽기의 장소 찾기(`places.resolve`)와 채팅 「바꿔 줘」 · 「넣어 줘」는 여전히 「지도에서 찾지 못했어요 — 정확한 이름을 알려 주세요」였다
(시연: 해운대해수욕장 · 감천문화마을 — 이름은 맞는데 고객에게 이름을 고치라고 했다).

★규칙은 D2 와 같다(Codex Q1): 서울에서 못 찾았고 · 카카오 서울 검색이 **막히지 않았을 때만** 카카오를 **한 번** 서울 사각 없이 부른다.
  정규화 이름이 같고 주소가 서울 밖인 곳만 근거다. 호출 실패 · 이름이 다른 곳은 근거가 아니다(지금처럼 못 찾음).
★서비스 범위(서울)는 넓히지 않는다 — 결과는 여전히 「못 찾음」(unresolved)이고 빈칸 종류 · 고르기 카드도 그대로다. 바뀌는 것은 고객 문장뿐이다.
"""
from __future__ import annotations

from app.domains.travel_ops.components.conversation.chat_edit import _refusal
from app.domains.travel_ops.components.intake import prefill
from app.domains.travel_ops.components.intake.gaps import Proposal
from app.domains.travel_ops.components.intake.places import resolve
from app.domains.travel_ops.components.intake import review as review_module


class Tour:
    def find(self, name, area_code=None):
        return None


class Kakao:
    def __init__(self, outside=None, *, seoul=None, down=False):
        self.outside, self.seoul, self.down = outside, seoul or {}, down
        self.outside_asked, self.misses = [], {}

    def search(self, query, size=5, near=None, **kw):
        if self.down:
            self.misses = {"budget_exhausted": 1}
            return None
        return self.seoul.get(query, [])

    def outside_seoul(self, query, *, size=5):
        self.outside_asked.append(query)
        return self.outside if not callable(self.outside) else self.outside(query)


def _busan(name="해운대해수욕장"):
    return [{"id": "1", "name": name, "category": "", "category_group": "AT4", "address": "부산 해운대구 우동",
             "latitude": 35.15, "longitude": 129.15, "region": "부산"}]


def test_a_same_named_place_outside_seoul_is_marked_with_its_region():
    kakao = Kakao(_busan())
    found = resolve("해운대해수욕장", our_places=[], tour=Tour(), kakao=kakao)
    assert found.status == "unresolved"                       # 범위는 넓히지 않는다
    assert found.outside_region == "부산"
    assert found.evidence()["outside_service_area"] == "부산"
    assert "부산" in (found.note or "") and "서울" in found.note
    assert kakao.outside_asked == ["해운대해수욕장"]


def test_a_place_found_in_seoul_never_asks_outside():
    kakao = Kakao(_busan("경복궁"))
    ours = [{"place_id": "p1", "name": "경복궁", "kind": "activity", "latitude": 37.5796, "longitude": 126.977}]
    found = resolve("경복궁", our_places=ours, tour=Tour(), kakao=kakao)
    assert found.status == "resolved" and found.outside_region is None and kakao.outside_asked == []


def test_a_differently_named_place_outside_seoul_is_not_evidence():
    found = resolve("해운대해수욕장", our_places=[], tour=Tour(), kakao=Kakao(_busan("해운대해수욕장 주차장")))
    assert found.outside_region is None and "outside_service_area" not in found.evidence()


def test_a_failed_outside_call_is_not_evidence_and_not_a_blocked_lookup():
    found = resolve("해운대해수욕장", our_places=[], tour=Tour(), kakao=Kakao(None))
    assert found.outside_region is None and found.blocked == []


def test_a_blocked_seoul_lookup_does_not_ask_outside():
    kakao = Kakao(_busan(), down=True)
    found = resolve("해운대해수욕장", our_places=[], tour=Tour(), kakao=kakao)
    assert found.outside_region is None and kakao.outside_asked == []


def test_a_kakao_without_the_outside_call_behaves_as_before():
    class Old:
        def search(self, query, size=5, near=None, **kw):
            return []

    found = resolve("해운대해수욕장", our_places=[], tour=Tour(), kakao=Old())
    assert found.status == "unresolved" and found.outside_region is None


def _item(**extra):
    return {"id": "i1", "title": "해운대해수욕장", "place_state": "unresolved", "kind": "activity", **extra}


def test_the_intake_question_says_outside_seoul_instead_of_fix_the_name():
    gaps = prefill.check_gaps({"items": [_item(_outside_area="부산")]})
    gap = next(g for g in gaps if g.where.get("item") == "i1")
    assert gap.kind == "place_not_found"                      # 같은 빈칸 · 같은 카드(후보 · 직접 고르기 · 장소 없이)
    assert "부산" in gap.reason and "서울" in gap.reason and "정확한" not in gap.reason
    question = prefill._question(Proposal(gap=gap, owner="ask_customer", candidates=[{"question": gap.reason}]), {"i1": _item(_outside_area="부산")}, set())  # noqa: SLF001
    assert "부산" in question["question"] and question["actions"] == list(prefill.PLACE_NOT_FOUND_ACTIONS)


def test_an_unresolved_place_without_region_keeps_the_old_question():
    gap = next(g for g in prefill.check_gaps({"items": [_item()]}) if g.where.get("item") == "i1")
    assert gap.reason == prefill.PLACE_NOT_FOUND_QUESTION.format(title="해운대해수욕장")


def test_the_review_line_and_public_payload():
    row = {"title": "해운대해수욕장", "claims": {"place": {"method": "model", "value": None,
                                                    "evidence": {"outside_service_area": "부산", "blocked": []}}}}
    line = review_module._place_line(row, "unresolved", None)        # noqa: SLF001
    assert line["result"] == "bad" and "부산" in line["text"] and "이름을 고치" not in line["text"]
    shown = review_module.public({"items": [{**_item(_outside_area="부산"), "place": None, "rows": []}], "moves": []})
    assert "_outside_area" not in shown["items"][0]


def test_the_chat_refusal_says_outside_seoul():
    found = resolve("해운대해수욕장", our_places=[], tour=Tour(), kakao=Kakao(_busan()))
    text = _refusal("place_not_found", f"「해운대해수욕장」: {found.note}")
    assert "부산" in text and "바꾸지 않았어요" in text and "정확히" not in text

# -*- coding: utf-8 -*-
"""계획 읽기 평가셋 — 실제 고객 입력 모양 8건(`edge-*`). 조사 `wiki/records/reports/2026-10-16_여행계획_사용자입력_케이스_조사.md` §3 C1~C8

    python -m eval.intake.edge             # eval/intake/cases/edge-*/gold.json 을 쓰고 manifest.json 을 다시 센다
    python -m eval.intake.run --only edge  # 이 8건만 채점(기본 실행은 원래 60건만 — 이전 실행과 견줄 수 있게)

★합성 60건(`build.py`)은 정해진 줄 모양 세 가지뿐이라, 고객이 실제로 붙여 넣을 만한 모양(카톡 대화 · AI 답변 마크다운 ·
  영어 · 자정 넘김 · 범위 밖 일수)이 없다. 이 8건은 2026-10-16 규칙 읽기 층에서 **틀린 값 · 조용한 누락**이 나온 모양이다.
★정답은 **사람이 읽었을 때의 값**이다 — 지금 시스템 출력이 아니다. 지금은 틀리는 것이 정상이다(기준선).
★`expect_problems` 는 조립 결과에 나와야 할 문제 코드다. `days_out_of_range` 는 **아직 코드에 없는 이름**이다(인원 쪽
  `party_size_out_of_range` 에 맞춰 지었다) — 고칠 때 이 이름을 쓰거나 여기를 함께 바꾼다.
★생성 규칙이 없는 손글 케이스라 시드를 쓰지 않는다. 오늘 = `build.TODAY`(해 없는 날짜는 다가오는 날).
"""
from __future__ import annotations

import hashlib
import json

from .build import CASES, HERE, SEED, TODAY

FORMAT = "edge"


def _item(date: str, start: str | None, title: str, place: str | None, kind: str = "activity") -> dict:
    return {"date": date, "start": start, "title": title, "place": place, "kind": kind, "booking_no": None}


D20, D21, D27 = "2026-10-20", "2026-10-21", "2026-10-27"

#: (case_id, defect, 원문, 정답 항목, 나와야 할 문제 코드, 왜)
EDGE = [
    ("edge-01", "c1_name_prefix",
     "서울 1일 여행 (2명)\n1일차 · 10월 20일\n09:30 도산공원 산책\n12:30 은평한옥마을\n15:00 도봉산 등산",
     [_item(D20, "09:30", "도산공원 산책", "도산공원"), _item(D20, "12:30", "은평한옥마을", "은평한옥마을"),
      _item(D20, "15:00", "도봉산 등산", "도봉산")],
     [], "이름 첫 글자가 「에·는·은·도」 — 조사 떼기가 첫 글자를 먹는다(도산공원 → 산공원)"),
    ("edge-02", "c2_heading_arrow",
     "서울 1일 여행 (2명)\n1일차 · 10월 20일: 경복궁 → 북촌한옥마을 → 인사동",
     [_item(D20, None, "경복궁", "경복궁"), _item(D20, None, "북촌한옥마을", "북촌한옥마을"),
      _item(D20, None, "인사동", "인사동")],
     [], "머리줄과 화살표 나열이 한 줄 — 항목이 통째로 사라지고 줄은 「읽음」이 된다"),
    ("edge-03", "c3_kakao_export",
     "[민지] [오후 3:12] 우리 10월 20일에 경복궁 10시 어때\n[준호] [오후 3:13] 좋아 점심은 광장시장\n"
     "[민지] [오후 3:14] 저녁 7시엔 N서울타워 가자",
     [_item(D20, "10:00", "경복궁", "경복궁"), _item(D20, None, "광장시장", "광장시장", "dining"),
      _item(D20, "19:00", "N서울타워", "N서울타워")],
     [], "카톡 대화 내보내기 — 메시지 보낸 시각(오후 3:12)을 일정 시각으로 읽는다"),
    ("edge-04", "c4_markdown",
     "## Day 1 (10/20)\n- **오전 9:30** 경복궁 🏯\n- **12:30** 토속촌삼계탕 🍲\n- **15:00** 북촌한옥마을",
     [_item(D20, "09:30", "경복궁", "경복궁"), _item(D20, "12:30", "토속촌삼계탕", "토속촌삼계탕", "dining"),
      _item(D20, "15:00", "북촌한옥마을", "북촌한옥마을")],
     [], "AI 답변 마크다운 — 굵게 기호(**)와 이모지가 제목에 남는다"),
    ("edge-05", "c5_bare_hour",
     "10월 20일\n11시 국립중앙박물관\n2시쯤 토속촌삼계탕 점심\n5시 반 N서울타워",
     [_item(D20, "11:00", "국립중앙박물관", "국립중앙박물관"),
      _item(D20, "14:00", "토속촌삼계탕", "토속촌삼계탕", "dining"),
      _item(D20, "17:30", "N서울타워", "N서울타워")],
     [], "오전·오후 없는 「2시쯤」 · 「5시 반」 — 낮 일정인데 새벽(02:00 · 05:30)으로 읽고 「쯤」이 제목에 붙는다"),
    ("edge-06", "c6_past_midnight",
     "10월 20일\n21:00 광장시장\n23:30 동대문디자인플라자\n01:00 숙소 복귀",
     [_item(D20, "21:00", "광장시장", "광장시장", "dining"),
      _item(D20, "23:30", "동대문디자인플라자", "동대문디자인플라자"),
      _item(D21, "01:00", "숙소 복귀", None, "lodging")],
     [], "자정 넘김 — 23:30 다음 01:00 은 다음 날이다"),
    ("edge-07", "c7_english_date",
     "Seoul trip (2 people)\nDay 1 Oct 20\n9:30 Gyeongbokgung Palace\n12:30 Tosokchon Samgyetang\n"
     "15:00 Bukchon Hanok Village\nDay 2 Oct 21\n10:00 National Museum of Korea",
     [_item(D20, "09:30", "Gyeongbokgung Palace", "경복궁"), _item(D20, "12:30", "Tosokchon Samgyetang", "토속촌삼계탕", "dining"),
      _item(D20, "15:00", "Bukchon Hanok Village", "북촌한옥마을"),
      _item(D21, "10:00", "National Museum of Korea", "국립중앙박물관")],
     [], "영어 월 이름 날짜(Oct 20) — 일차만 읽고 날짜를 버리며 줄은 「읽음」이라 모델에게도 안 간다"),
    ("edge-08", "c8_days_out_of_range",
     "서울 7박8일 여행 (2명)\n1일차 · 10월 20일\n10:00 경복궁\n12:30 명동교자\n8일차 · 10월 27일\n10:00 국립중앙박물관",
     [_item(D20, "10:00", "경복궁", "경복궁"), _item(D20, "12:30", "명동교자", "명동교자", "dining"),
      _item(D27, "10:00", "국립중앙박물관", "국립중앙박물관")],
     ["days_out_of_range"], "최대 7일을 넘는 일정 — 일수를 조용히 버린다(인원은 범위 밖 문제를 낸다)"),
]


def build_edge() -> list[dict]:
    out = []
    for case_id, defect, text, items, problems, why in EDGE:
        lines = text.split("\n")
        for it in items:
            assert it["title"] in text, f"{case_id}: 정답 제목 「{it['title']}」 이 원문에 글자 그대로 없다"
        gold = {"case_id": case_id, "format": FORMAT, "defect": defect, "party": None,
                "inputs": [{"kind": "text", "text": text}], "lines": lines, "items": items,
                "expect_problems": problems, "why": why}
        folder = CASES / case_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "gold.json").write_text(json.dumps(gold, ensure_ascii=False, indent=1), encoding="utf-8")
        out.append(gold)
    _refresh_manifest(len(out))
    return out


def _refresh_manifest(edge_count: int) -> None:
    """manifest 를 디스크 그대로 다시 센다 — 기존 60건 파일은 건드리지 않으므로 그 해시는 그대로다."""
    path = HERE / "manifest.json"
    old = json.loads(path.read_text(encoding="utf-8"))
    files = {str(p.relative_to(CASES)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(CASES.rglob("*")) if p.is_file()}
    changed = [k for k, v in old["files"].items() if files.get(k) != v]
    assert not changed, f"기존 평가 파일이 바뀌었다: {changed[:5]}"
    manifest = {"seed": SEED, "today": TODAY.isoformat(), "cases": old["cases"], "edge_cases": edge_count,
                "synthetic": True, "files": files}
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    built = build_edge()
    print(f"edge cases={len(built)} items={sum(len(c['items']) for c in built)} -> {CASES}")

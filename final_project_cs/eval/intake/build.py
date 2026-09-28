# -*- coding: utf-8 -*-
"""계획 읽기 평가셋 60건 생성기. 설계서 `program/plan/A-COP_고객계획_읽기_설계_2026-09-26.md` §7

    python -m eval.intake.build            # eval/intake/cases/ 에 60건 + manifest.json

★**정답이 먼저다.** 정답(항목마다 날짜·시각·원문 제목·정답 장소·예약번호)을 시드로 정하고, 그 정답에서 입력을 만든다 —
  정답을 우리 시스템 출력에서 뽑지 않는다. ★**합성 평가셋이다 — 사람이 단 라벨이 아니다.** 실제 고객 사진·손글씨·저해상도는
  이 셋이 대표하지 않는다(설계서 §9 첫 줄 `[미확보]` 그대로).
★형식 6가지 × 10건: paste(붙여넣기) · text_pdf · photo · scan_pdf · xlsx · mixed(채팅 글 + 표/사진).
  형식마다 3건은 결함을 넣는다 — 상대 날짜(「내일」) · 시각 없음 · 오타(자모 한 글자). 예약 문서 충돌은 **넣지 않았다**
  (예약 문서 읽기가 아직 없다 — 넣으면 재는 것이 아니라 틀린다는 것을 확인할 뿐이다).
★오늘 = `TODAY`(실행기도 같은 값을 쓴다). 해 없는 날짜는 오늘 기준 다가오는 날이 정답이다.
★장소 정답은 **공식 이름**으로 적는다(정규화 비교: 괄호·지점 표시·공백 무시). 이 목록은 조회로 미리 걸러 고르지 않았다 —
  고르면 장소 정확도가 부풀려진다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
import hashlib
import io
import json
from pathlib import Path
import random

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases"
SEED = 20260928
TODAY = date(2026, 10, 1)
FONT = r"C:\Windows\Fonts\malgun.ttf"

#: (원문에 쓰는 제목, 정답 장소, 종류). ★원문 제목은 사람이 흔히 쓰는 모양 — 활동 말이 붙거나(「경복궁 관람」) 가게 이름만
ACTIVITIES = [
    ("경복궁 관람", "경복궁"), ("창덕궁 후원", "창덕궁"), ("덕수궁 돌담길 산책", "덕수궁"), ("창경궁", "창경궁"),
    ("북촌한옥마을 산책", "북촌한옥마을"), ("인사동 구경", "인사동"), ("남산골한옥마을", "남산골한옥마을"),
    ("N서울타워", "N서울타워"), ("국립중앙박물관 관람", "국립중앙박물관"), ("국립민속박물관", "국립민속박물관"),
    ("청계천 산책", "청계천"), ("동대문디자인플라자", "동대문디자인플라자"), ("롯데월드", "롯데월드"),
    ("서울숲 산책", "서울숲"), ("전쟁기념관", "전쟁기념관"), ("익선동 한옥거리", "익선동"),
    ("명동난타극장", "명동난타극장"), ("여의도한강공원", "여의도한강공원"),
]
DINING = [("토속촌삼계탕", "토속촌삼계탕"), ("광장시장 빈대떡", "광장시장"), ("명동교자", "명동교자"),
          ("진옥화할매원조닭한마리", "진옥화할매원조닭한마리"), ("망원시장 칼국수", "망원시장")]
TYPO = {"경복궁 관람": "경복굼 관람", "창덕궁 후원": "창덕굼 후원", "북촌한옥마을 산책": "북촌한옥마울 산책",
        "국립중앙박물관 관람": "국립중앙박물곤 관람"}
FORMATS = ["paste", "text_pdf", "photo", "scan_pdf", "xlsx", "mixed"]
DEFECTS = ["relative_date", "no_time", "typo"]


@dataclass
class GoldItem:
    date: str
    start: str | None          # None = 원문에 시각이 없다(시각 정확도 분모에서 빠진다)
    title: str                 # 원문에 적힌 제목(글자 그대로 — 변조 검사 기준)
    place: str | None
    kind: str
    booking_no: str | None = None


@dataclass
class Case:
    case_id: str
    format: str
    defect: str | None
    party: int
    inputs: list[dict] = field(default_factory=list)      # [{"kind": "text"|"file", "name", "text"?}]
    lines: list[str] = field(default_factory=list)        # 원문 전체(사람이 쓴 글 — 변조 검사 기준)
    items: list[GoldItem] = field(default_factory=list)


def _plan(rng: random.Random, defect: str | None) -> tuple[list[tuple[int, date, list[GoldItem]]], dict]:
    start = TODAY + timedelta(days=rng.randint(7, 40))
    ndays = rng.randint(1, 3)
    days = []
    used: set[str] = set()
    for d in range(ndays):
        when = start + timedelta(days=d)
        acts = rng.sample([a for a in ACTIVITIES if a[0] not in used], 2)
        meal = rng.choice([m for m in DINING if m[0] not in used])
        used |= {acts[0][0], acts[1][0], meal[0]}
        slots = [("09:30", acts[0], "activity"), ("12:30", meal, "dining"), ("15:00", acts[1], "activity")]
        items = [GoldItem(when.isoformat(), t, title, place, kind) for t, (title, place), kind in slots]
        days.append((d + 1, when, items))
    if rng.random() < 0.4:                                       # 예약번호 한 건
        target = rng.choice([it for _, _, its in days for it in its])
        target.booking_no = f"KY-{rng.randint(10000, 99999)}"
    meta = {"defect_line": None}
    if defect == "relative_date":
        # 첫날을 「내일」로 — 정답 날짜는 오늘 + 1(나머지 날은 이어서)
        base = TODAY + timedelta(days=1)
        for number, (_, _, its) in enumerate(days):
            for it in its:
                it.date = (base + timedelta(days=number)).isoformat()
        days = [(n, base + timedelta(days=n - 1), its) for n, _, its in days]
    elif defect == "no_time":
        victim = days[0][2][1]                                   # 첫날 점심 — 시각을 지운다
        victim.start = None
        meta["defect_line"] = victim.title
    elif defect == "typo":
        for _, _, its in days:
            for it in its:
                if it.title in TYPO:
                    it.title = TYPO[it.title]                   # 원문은 오타, 정답 장소는 그대로
                    meta["defect_line"] = it.title
                    break
            if meta["defect_line"]:
                break
        if not meta["defect_line"]:                              # 오타 낼 항목이 없으면 첫 활동을 바꿔 넣는다
            first = days[0][2][0]
            first.title, first.place = "경복굼 관람", "경복궁"
            meta["defect_line"] = first.title
    return days, meta


def _lines(days, party: int, defect: str | None, style: int) -> list[str]:
    head = [f"서울 {len(days)}일 여행 ({party}명)"]
    out = list(head)
    for number, when, items in days:
        if defect == "relative_date" and number == 1:
            out.append("1일차 · 내일")
        elif style == 0:
            out.append(f"{number}일차 · {when.month}월 {when.day}일")
        elif style == 1:
            out.append(f"DAY {number} {when.isoformat()}")
        else:
            out.append(f"{number}일차 {when.isoformat()}")
        for it in items:
            tail = f" · 예약번호 {it.booking_no}" if it.booking_no else ""
            meal = " 점심" if it.kind == "dining" and it.title in ("토속촌삼계탕", "명동교자", "진옥화할매원조닭한마리") else ""
            out.append(f"{it.start + ' ' if it.start else ''}{it.title}{meal}{tail}")
        out.append("")
    return out[:-1]


# ── 형식별 파일 ───────────────────────────────────────────────────
def _image(lines: list[str], rng: random.Random, scale: float = 1.0) -> bytes:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    font = ImageFont.truetype(FONT, int(30 * scale))
    width, height = int(900 * scale), int((80 + 44 * len(lines)) * scale)
    img = Image.new("RGB", (width, height), (250, 248, 242))
    draw = ImageDraw.Draw(img)
    for n, line in enumerate(lines):
        draw.text((int(40 * scale), int((40 + 44 * n) * scale)), line, fill=(30, 30, 30), font=font)
    img = img.rotate(rng.uniform(-2.5, 2.5), expand=True, fillcolor=(235, 233, 226))
    noise = Image.effect_noise(img.size, 18).convert("RGB")
    img = Image.blend(img, noise, 0.06).filter(ImageFilter.GaussianBlur(0.4))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=82)
    return out.getvalue()


def _text_pdf(lines: list[str]) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((60, 70), "\n".join(lines), fontname="korea", fontsize=12)
    return doc.tobytes()


def _scan_pdf(lines: list[str], rng: random.Random) -> bytes:
    import fitz

    image = _image(lines, rng, scale=1.2)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(page.rect, stream=image, keep_proportion=True)
    return doc.tobytes()


def _xlsx(days) -> tuple[bytes, list[str]]:
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.append(["일차", "날짜", "시각", "일정", "메모"])
    lines = ["일차 | 날짜 | 시각 | 일정 | 메모"]
    for number, when, items in days:
        for it in items:
            memo = f"예약번호 {it.booking_no}" if it.booking_no else ""
            row = [f"{number}일차", when.isoformat(), it.start or "", it.title, memo]
            sheet.append(row)
            lines.append(" | ".join(str(c) for c in row))
    out = io.BytesIO()
    book.save(out)
    return out.getvalue(), lines


def build() -> list[Case]:
    rng = random.Random(SEED)
    cases = []
    for fmt in FORMATS:
        for n in range(10):
            defect = DEFECTS[n] if n < 3 else None
            party = rng.randint(1, 4)
            days, _ = _plan(rng, defect)
            case = Case(f"{fmt}-{n + 1:02d}", fmt, defect, party,
                        items=[it for _, _, its in days for it in its])
            lines = _lines(days, party, defect, style=n % 3)
            folder = CASES / case.case_id
            folder.mkdir(parents=True, exist_ok=True)
            if fmt == "paste":
                case.inputs.append({"kind": "text", "text": "\n".join(lines)})
            elif fmt == "text_pdf":
                (folder / "plan.pdf").write_bytes(_text_pdf(lines))
                case.inputs.append({"kind": "file", "name": "plan.pdf"})
            elif fmt == "photo":
                (folder / "plan.jpg").write_bytes(_image(lines, rng))
                case.inputs.append({"kind": "file", "name": "plan.jpg"})
            elif fmt == "scan_pdf":
                (folder / "scan.pdf").write_bytes(_scan_pdf(lines, rng))
                case.inputs.append({"kind": "file", "name": "scan.pdf"})
            elif fmt == "xlsx":
                data, lines = _xlsx(days)
                if defect == "relative_date":                    # 표에는 상대 날짜 칸이 없다 — 첫날 날짜 칸을 「내일」로
                    lines = [line.replace((TODAY + timedelta(days=1)).isoformat(), "내일") for line in lines]
                    data = _xlsx_relative(days)
                (folder / "plan.xlsx").write_bytes(data)
                case.inputs.append({"kind": "file", "name": "plan.xlsx"})
            else:                                                # mixed — 첫날은 채팅 글, 나머지는 표(또는 사진)
                chat = [f"안녕하세요 {party}명이서 서울 가요"] + lines[1:1 + 1 + len(days[0][2])]
                rest = [lines[0]] + lines[1 + 1 + len(days[0][2]):]
                case.inputs.append({"kind": "text", "text": "\n".join(chat)})
                if len(days) > 1:
                    (folder / "rest.jpg").write_bytes(_image([l for l in rest if l], rng))
                    case.inputs.append({"kind": "file", "name": "rest.jpg"})
                lines = chat + rest
            case.lines = lines
            (folder / "gold.json").write_text(json.dumps(asdict(case), ensure_ascii=False, indent=1), encoding="utf-8")
            cases.append(case)
    manifest = {"seed": SEED, "today": TODAY.isoformat(), "cases": len(cases), "synthetic": True,
                "files": {str(p.relative_to(CASES)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(CASES.rglob("*")) if p.is_file()}}
    (HERE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return cases


def _xlsx_relative(days) -> bytes:
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.append(["일차", "날짜", "시각", "일정", "메모"])
    for number, when, items in days:
        for it in items:
            memo = f"예약번호 {it.booking_no}" if it.booking_no else ""
            sheet.append([f"{number}일차", "내일" if number == 1 else when.isoformat(), it.start or "", it.title, memo])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


if __name__ == "__main__":
    built = build()
    print(f"cases={len(built)} items={sum(len(c.items) for c in built)} -> {CASES}")

# -*- coding: utf-8 -*-
"""4차 v4 자동 검사 — 코덱스 명세의 검사표를 프로그램으로 셀 수 있는 것만 구현했다.

    python qa_docx.py <docx> [<docx> ...]        (모든 문서를 함께 주면 문서 사이 중복도 본다)
    종료 코드 0 = 필수 검사 통과, 1 = 필수 위반 있음. 「검토」는 위반이 아니라 사람이 눈으로 볼 항목이다.

DOCX 구조(XML): 금지 문자, 표 폭 9,345 dxa(표·격자·셀), 표 열·행 수, 5열 표 셀 길이는 빌드가 추정으로 경고, 글자 크기 집합, 본문 줄 간격,
                그림 폭 155~165mm · 300dpi, 절 머리(1·2단계) 뒤 결론 문장.
Word PDF(PyMuPDF): 문단 줄 수 <= 4, 제목 고립, 그림·캡션 같은 쪽, 쪽당 그림 <= 2, 본문 영역 이탈 <= 1pt, 쪽 아래 빈 공간 > 35%(검토), 쪽 안 큰 빈 구간 > 20%(검토),
                문서 사이 같은 문장(25자 이상) 중복.
못 재는 것(코덱스 명세 중 대체·제외, 근거는 변경요약): 쪽마다 결론 1~2줄 → 절 머리 결론 문장으로 대체, 쪽별 블록 수 2~4 → 흐름 배치라 보장 불가(눈 검사), 강조색 쪽당 3영역.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

THRESH = dict(max_para_lines=4, blank_review=0.35, gap_review=0.20, max_figs_per_page=2, dup_min_chars=25,
              table_w=9345, fig_mm=(155, 165), fig_dpi=300, out_pt=1.0)
BANNED = "—–→⇒★☆✓✔✕✗▸…⇄"
RENDER_PS1 = Path(__file__).resolve().parent / "render_word.ps1"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ALLOWED_SZ = {18, 19, 20, 21, 22, 23, 26, 34}          # 캡션·표·카드·본문·제목·값(반 포인트). 양식(표지·머리)의 크기는 제외하고 본문 요소만 본다.


def render_pdf(docx: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / "in.docx"
    tmp.write_bytes(docx.read_bytes())
    pdf = out_dir / "out.pdf"
    subprocess.run(["powershell", "-NoProfile", "-File", str(RENDER_PS1), "-Docx", str(tmp), "-Pdf", str(pdf)], check=True, capture_output=True)
    return pdf


# ── DOCX 구조 ────────────────────────────────────────────────────
def check_docx(docx: Path, template_text: str = ""):
    from docx import Document
    from lxml import etree
    bad, review = [], []
    d = Document(str(docx))
    body = d.element.body
    text = "\n".join(t.text or "" for t in body.iter(W + "t"))
    circled = {ch for ch in text if 0x2460 <= ord(ch) <= 0x24FF}
    banned = sorted({ch for ch in text if (ch in BANNED or ch in circled) and ch not in template_text})
    if banned:
        bad.append(f"금지 문자 {banned}")
    # 표
    n_tbl = 0
    for tbl in body.iter(W + "tbl"):
        cap = tbl.find(f"{W}tblPr/{W}tblCaption")
        kind = (cap.get(W + "val") if cap is not None else "").split(":")[0]
        if kind not in ("body", "detail", "card", "callout", "form"):
            continue                                   # 양식의 표지·머리 표는 건드리지 않는다
        wtag = tbl.find(f"{W}tblPr/{W}tblW")
        grid = [int(g.get(W + "w")) for g in tbl.findall(f"{W}tblGrid/{W}gridCol")]
        if kind in ("body", "detail", "card", "callout", "form"):
            n_tbl += 1
            if wtag is None or int(wtag.get(W + "w")) != THRESH["table_w"] or sum(grid) != THRESH["table_w"]:
                bad.append(f"표 폭 불일치: {kind} {sum(grid)}")
            for tr in tbl.findall(W + "tr"):
                if sum(int(tc.find(f"{W}tcPr/{W}tcW").get(W + "w")) for tc in tr.findall(W + "tc")) != sum(grid):
                    bad.append(f"표 셀 폭 합 불일치({kind})")
                    break
        if kind in ("body", "detail", "form"):
            rows = tbl.findall(W + "tr")
            n_hdr = sum(1 for tr in rows if tr.find(f"{W}trPr/{W}tblHeader") is not None)
            data = len(rows) - n_hdr
            limit = 8 if kind == "body" else 12
            if len(grid) > 6:
                bad.append(f"표 열 {len(grid)}개(>5): {cap.get(W + 'val')}")
            if data > limit:
                bad.append(f"표 데이터 행 {data}개(>{limit}): {cap.get(W + 'val')}")
            if data < 2:
                bad.append(f"표 데이터 행 2개 미만: {cap.get(W + 'val')}")
            if n_hdr < 1:
                bad.append(f"표 머리행 반복 없음: {cap.get(W + 'val')}")
            if any(tr.find(f"{W}trPr/{W}cantSplit") is None for tr in rows):
                bad.append(f"행 쪼갬 허용: {cap.get(W + 'val')}")
    # 글자 크기·줄 간격(본문 표지 이후)
    sizes = Counter(int(sz.get(W + "val")) for sz in body.iter(W + "sz"))
    odd = {s: n for s, n in sizes.items() if s not in ALLOWED_SZ}
    if odd:
        review.append(f"양식 밖 글자 크기(반 포인트: 개수) {odd} — 표지·머리 표의 양식 값이면 정상")
    exact = Counter()
    for p in body.iter(W + "p"):
        sp = p.find(f"{W}pPr/{W}spacing")
        if sp is not None and sp.get(W + "lineRule") == "exact":
            exact[int(sp.get(W + "line"))] += 1
    for line in exact:
        if line not in (320, 280, 260, 400, 80, 100, 120):
            review.append(f"고정 줄 간격 {line} 사용({exact[line]}곳)")
    # 그림
    z = zipfile.ZipFile(docx)
    from PIL import Image
    import io
    rels = {}
    rel_xml = etree.fromstring(z.read("word/_rels/document.xml.rels"))
    for r in rel_xml:
        rels[r.get("Id")] = r.get("Target")
    figs = 0
    for dr in body.iter("{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline"):
        figs += 1
        cx = int(dr.find("{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent").get("cx"))
        mm = cx / 914400 * 25.4
        blip = dr.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip")
        target = rels[blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")]
        px = Image.open(io.BytesIO(z.read("word/" + target))).size[0]
        dpi = px / (cx / 914400)
        if not THRESH["fig_mm"][0] <= mm <= THRESH["fig_mm"][1]:
            bad.append(f"그림 폭 {mm:.0f}mm(155~165 밖)")
        if dpi < THRESH["fig_dpi"] - 1:
            bad.append(f"그림 해상도 {dpi:.0f}dpi(<300)")
    # 절 머리(1·2단계) 뒤 결론 문장
    prev_kind = None
    return bad, review, dict(tables=n_tbl, figures=figs)


# ── Word PDF ─────────────────────────────────────────────────────
def analyse(pdf: Path):
    import fitz
    doc = fitz.open(str(pdf))
    m = dict(pages=doc.page_count, max_para_lines=0, max_para_page=0, orphan=[], blank=[], gap=[], figs_per_page=[], out=[], cap_no_fig=[], sentences=[])
    W_, H_ = doc[0].rect.width, doc[0].rect.height
    left, right, top, bot = 49.6, W_ - 49.6, 63.8, H_ - 78.0
    for pno, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]
        text_blocks = [b for b in blocks if b["type"] == 0 and b["bbox"][3] <= H_ - 40 and b["bbox"][1] >= 30]
        imgs = [b for b in blocks if b["type"] == 1]
        if len(imgs) > THRESH["max_figs_per_page"]:
            m["figs_per_page"].append((pno, len(imgs)))
        spans_all = []
        boxes = []
        body_lines = []
        for b in text_blocks:
            sizes = [s["size"] for l in b["lines"] for s in l["spans"] if s["text"].strip()]
            if not sizes:
                continue
            x0, y0, x1, y1 = b["bbox"]
            if top - 20 <= y0 and y1 <= bot + 20 and pno > 1 or pno == 1:
                if x0 < left - THRESH["out_pt"] and y0 > top and y1 < bot and pno > 1 or x1 > right + THRESH["out_pt"] + 20 and pno > 1:
                    m["out"].append((pno, round(x0), round(x1)))
            txt = " ".join(s["text"] for l in b["lines"] for s in l["spans"]).strip()
            for ln in b["lines"]:
                sp = [s for s in ln["spans"] if s["text"].strip()]
                if sp and 10.2 <= max(s["size"] for s in sp) <= 10.8 and not (sp[0]["flags"] & 16):
                    body_lines.append((ln["bbox"][1], ln["bbox"][0], "".join(s["text"] for s in sp)))
            spans_all.append((y0, y1, sizes, txt, b))
            boxes.append((y0, y1))
        body_lines.sort()
        run = []
        for y, x, t in body_lines + [(9999, 0, "")]:
            if run and 14.0 <= y - run[-1][0] <= 18.0:
                run.append((y, x, t))
                continue
            if len(run) > m["max_para_lines"]:
                m["max_para_lines"], m["max_para_page"] = len(run), pno
            if len(run) > THRESH["max_para_lines"]:
                m.setdefault("long_paras", []).append((pno, len(run), run[0][2][:30]))
            run = [(y, x, t)]
        for b in imgs:
            boxes.append((b["bbox"][1], b["bbox"][3]))
        try:
            for dr in page.get_drawings():
                r = dr["rect"]
                if r.height > 3 and r.y0 >= top - 5 and r.y1 <= bot + 5:
                    boxes.append((r.y0, r.y1))
        except Exception:
            pass
        boxes = [(a, b_) for a, b_ in boxes if top - 5 <= a and b_ <= bot + 30]
        if not boxes:
            continue
        boxes.sort()
        merged = [list(boxes[0])]
        for a, b_ in boxes[1:]:
            if a - merged[-1][1] <= 2:
                merged[-1][1] = max(merged[-1][1], b_)
            else:
                merged.append([a, b_])
        span = bot - top
        last_y = merged[-1][1]
        if pno > 1 and pno < doc.page_count:
            blank = (bot - last_y) / span
            if blank > THRESH["blank_review"]:
                m["blank"].append((pno, round(blank, 2)))
            for i in range(len(merged) - 1):
                g = (merged[i + 1][0] - merged[i][1]) / span
                if g > THRESH["gap_review"]:
                    m["gap"].append((pno, round(g, 2)))
        # 제목 고립: 마지막 텍스트 블록이 제목(굵고 큰 글자)
        if spans_all and 1 < pno < doc.page_count:
            y0, y1, sizes, txt, b = max(spans_all, key=lambda x: x[1])
            bold = any(s["flags"] & 16 for l in b["lines"] for s in l["spans"])
            if re.fullmatch(r'\d+', txt.strip()):
                pass
            elif bold and max(sizes) >= 10.8 and len(txt) < 45 and y1 > bot - 60:
                m["orphan"].append((pno, txt[:20]))
            elif bold and max(sizes) >= 10.4 and len(txt) < 45 and y1 > bot - 40 and not re.match(r"표 \d|그림 \d", txt):
                m["orphan"].append((pno, txt[:20]))
        # 그림 캡션이 그림과 같은 쪽에 있는가
        caps = [t for _, _, _, t, _ in spans_all if re.match(r"그림 \d+\.", t)]
        if len(caps) > len(imgs):
            m["cap_no_fig"].append((pno, caps[0][:12]))
    return m


def sentences_of(docx: Path):
    from docx import Document
    d = Document(str(docx))
    out = []
    body = d.element.body
    for tbl in body.iter(W + "tbl"):
        pass
    parts = []
    for el in body.iterchildren():
        if el.tag == W + "tbl":
            first = " ".join("".join(t.text or "" for t in tr.iter(W + "t")) for tr in el.findall(W + "tr")[:2])
            if "변경일" in first:
                continue
            for tc in [tc for tr in el.findall(W + "tr")[1:] for tc in tr.findall(W + "tc")]:
                parts.append("".join(t.text or "" for t in tc.iter(W + "t")))
        elif el.tag == W + "p":
            parts.append("".join(t.text or "" for t in el.iter(W + "t")))
    for part in parts:
        for s in re.split(r"(?<=[.다요])\s+|\n", part):
            s = re.sub(r"\s+", " ", s).strip()
            if len(s) >= THRESH["dup_min_chars"] and s.rstrip('.').endswith('다'):   # 문장만(표의 이름·값은 되풀이돼도 정상)
                out.append(s)
    return out


def check(docs: list[Path]):
    template_text = ""
    from docx import Document
    tmpl_dir = Path(__file__).resolve().parents[2]
    for t in tmpl_dir.glob("[[]데이터 전처리[]]*.docx"):
        template_text += "".join(x.text or "" for x in Document(str(t)).element.body.iter(W + "t"))
    results, all_sent = {}, defaultdict(list)
    for docx in docs:
        bad, review, info = check_docx(docx, template_text)
        with tempfile.TemporaryDirectory(dir=r"C:\Users\playdata2\Documents") as tmp:
            m = analyse(render_pdf(docx, Path(tmp)))
        if m["max_para_lines"] > THRESH["max_para_lines"]:
            for pno, n, t in m.get("long_paras", []):
                bad.append(f"본문 문단 {n}줄(쪽 {pno}) > {THRESH['max_para_lines']}: {t}")
        if m["orphan"]:
            bad.append(f"제목 고립 {m['orphan']}")
        if m["figs_per_page"]:
            bad.append(f"쪽당 그림 > 2: {m['figs_per_page']}")
        if m["cap_no_fig"]:
            bad.append(f"그림·캡션 쪽 분리: {m['cap_no_fig']}")
        if m["out"]:
            bad.append(f"본문 영역 이탈: {m['out'][:5]}")
        if m["blank"]:
            review.append(f"쪽 아래 빈 공간 > 35%(쪽, 비율): {m['blank']}")
        if m["gap"]:
            review.append(f"쪽 안 큰 빈 구간 > 20%(쪽, 비율): {m['gap']}")
        for s in sentences_of(docx):
            all_sent[s].append(docx.name)
        results[docx.name] = (m, bad, review, info)
    exempt = re.compile(r'^(https?://|김지혜|개정 기준|팀 A-COPilot이 만드는)')
    dups = {s: names for s, names in all_sent.items() if len(names) > 1 and not exempt.match(s) and ' ' in s.replace('. ', '') and not re.fullmatch(r'[0-9a-f]{40,}', s)}
    return results, dups


if __name__ == "__main__":
    args = [Path(a) for a in sys.argv[1:]]
    results, dups = check(args)
    rc = 0
    for name, (m, bad, review, info) in results.items():
        print(f"== {name}: {m['pages']}쪽(PDF 쪽, 표지가 1쪽 · 인쇄 번호 = PDF 쪽 - 1), 표 {info['tables']}·그림 {info['figures']}, 최대 본문 문단 {m['max_para_lines']}줄, 필수 위반 {len(bad)}, 검토 {len(review)}")
        for b in bad:
            print("  [위반] " + b)
        for r in review:
            print("  [검토] " + r)
        rc |= bool(bad)
    if dups:
        print(f"== 같은 문장 중복(25자 이상) {len(dups)}종")
        for s, names in list(dups.items())[:40]:
            print(f"  [{len(names)}] {s[:60]}")
        rc |= 1
    sys.exit(rc)

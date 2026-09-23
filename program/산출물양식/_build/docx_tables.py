# -*- coding: utf-8 -*-
"""저장된 .docx 에 진짜 Word 표를 끼워 넣는다.

★왜 따로 있나 (2026-09-10). `docxfill.py` 는 원시 XML 을 다루며 **문단·굵게·불릿·
  그림만** 만든다(`Doc.build()` 의 item 종류). 표가 없다. 그런데 기획서 템플릿은
  「시장조사 및 BM 분석」 절에만 표 여덟 개를 요구한다.

  docxfill 을 고치는 대신 **저장한 뒤 python-docx 로 표를 끼워 넣는다.** 표지의 깃허브
  칸을 채울 때 쓴 방식과 같다. docxfill 의 XML 조작과 섞이지 않아 서로를 깨뜨리지 않는다.

쓰는 법 —

    from docx_tables import insert_tables
    insert_tables(OUT, [
        ("시장 규모표", ["구분", "대상", "산식", "규모", "출처"], [
            ["TAM", "...", "...", "...", "[외부]"],
        ]),
    ])

`앵커` 는 **문단의 전체 텍스트**와 비교한다. 같은 문단이 여럿이면 첫째 뒤에 넣는다.
표 바로 위에 굵은 캡션 문단을 하나 둔다 — 캡션이 곧 앵커가 되어 다음 표를 이어 붙일 수 있다.
"""
import time

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

FONT = "맑은 고딕"
HEAD_FILL = "DDE7F0"   # WBS·요구사항 머리행과 같은 색


def _shade(cell, hex_fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def _borders(tbl, sz="4", color="808080"):
    """표 전체에 얇은 실선 테두리를 직접 넣는다."""
    tbl_pr = tbl._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement("w:" + edge)
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), sz)
        e.set(qn("w:space"), "0")
        e.set(qn("w:color"), color)
        b.append(e)
    tbl_pr.append(b)


def _write(cell, text, bold=False, size=9):
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run("" if text is None else str(text))
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = FONT
    # 한글 글꼴은 eastAsia 로 따로 지정해야 먹는다
    r_pr = run._r.get_or_add_rPr()
    fonts = r_pr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        r_pr.append(fonts)
    fonts.set(qn("w:eastAsia"), FONT)


def _find_para(doc, anchor):
    for p in doc.paragraphs:
        if p.text.strip() == anchor.strip():
            return p
    # 전체 일치가 없으면 앞부분 일치로 한 번 더 — 제목 뒤에 번호가 붙는 경우
    for p in doc.paragraphs:
        if p.text.strip().startswith(anchor.strip()):
            return p
    return None


def _caption_after(par, text):
    """par 바로 뒤에 굵은 캡션 문단을 만들고 그 문단을 돌려준다."""
    new_p = OxmlElement("w:p")
    par._p.addnext(new_p)
    from docx.text.paragraph import Paragraph
    cap = Paragraph(new_p, par._parent)
    run = cap.add_run(text)
    run.bold = True
    run.font.size = Pt(10)
    run.font.name = FONT
    return cap


def insert_table_after(doc, anchor, caption, header, rows, widths=None):
    """anchor 문단 뒤에 [캡션 문단 + 표] 를 넣는다. 넣은 캡션 문단을 돌려준다."""
    par = _find_para(doc, anchor)
    if par is None:
        raise KeyError("앵커 문단을 못 찾았다: %r" % anchor)
    cap = _caption_after(par, caption)

    ncol = len(header)
    for i, r in enumerate(rows):
        if len(r) != ncol:
            raise ValueError("%s 의 %d번째 행 칸 수가 %d 이다 (머리행은 %d)"
                             % (caption, i + 1, len(r), ncol))

    # ★doc.add_table 은 구역 여백으로 표 너비를 잰다. 이 양식은 여백이 소수점
    #   (`pgMar left="992.12..."`)이라 python-docx 가 int 로 못 읽고 죽는다.
    #   너비를 직접 주고 본문 컨테이너에 바로 만든다.
    tbl = doc._body.add_table(1 + len(rows), ncol, Inches(6.3))
    # ★이 양식에는 "Table Grid" 스타일이 없다(KeyError). 있으면 쓰고, 없으면 테두리를
    #   표 속성에 직접 그린다 — 스타일 유무와 무관하게 선이 보이게.
    try:
        tbl.style = "Table Grid"
    except KeyError:
        _borders(tbl)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, h in enumerate(header):
        c = tbl.rows[0].cells[j]
        _write(c, h, bold=True)
        _shade(c, HEAD_FILL)
    for i, r in enumerate(rows, start=1):
        for j, v in enumerate(r):
            _write(tbl.rows[i].cells[j], v)
    if widths:
        for row in tbl.rows:
            for j, w in enumerate(widths):
                row.cells[j].width = w

    # add_table 은 문서 끝에 붙인다 — 캡션 뒤로 옮긴다
    cap._p.addnext(tbl._tbl)
    return cap


def insert_tables(path, specs, out=None):
    """specs: [(앵커, 캡션, 머리행, 행들), ...] — 순서대로 넣는다.

    ★앵커를 None 으로 주면 **직전에 넣은 표의 캡션 뒤**가 아니라 **직전 표 뒤**에 잇는다.
      같은 절에 표를 여럿 연달아 둘 때 쓴다.
    """
    doc = Document(path)
    last_tbl = None
    n = 0
    for spec in specs:
        anchor, caption, header, rows = spec[:4]
        widths = spec[4] if len(spec) > 4 else None
        if anchor is None:
            if last_tbl is None:
                raise ValueError("첫 표의 앵커는 None 일 수 없다")
            # 직전 표 뒤에 빈 문단을 하나 두고 그것을 앵커로 쓴다
            gap = OxmlElement("w:p")
            last_tbl.addnext(gap)
            from docx.text.paragraph import Paragraph
            tmp = Paragraph(gap, doc.paragraphs[0]._parent)
            marker = "__표이음_%d__" % n
            tmp.add_run(marker)
            cap = insert_table_after(doc, marker, caption, header, rows, widths)
            tmp._p.getparent().remove(tmp._p)
        else:
            cap = insert_table_after(doc, anchor, caption, header, rows, widths)
        last_tbl = cap._p.getnext()
        n += 1
    target = out or path
    for _ in range(5):
        try:
            doc.save(target)
            return target, n
        except PermissionError:
            time.sleep(0.4)
    base, ext = target.rsplit(".", 1)
    target = base + "_새버전." + ext
    doc.save(target)
    return target, n

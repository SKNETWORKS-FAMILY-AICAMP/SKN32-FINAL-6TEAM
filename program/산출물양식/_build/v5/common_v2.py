# -*- coding: utf-8 -*-
"""4차 v2 공통 — 경로·상수·검사·저장 도구. (문서별 본문은 docs_*_v2.py)"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
FORMS = Path(os.environ.get("ACOP_FORMS_DIR") or HERE.parent.parent)
WORKSPACE = FORMS.parents[1]
ML = Path(os.environ.get("ACOP_ML_DIR") or WORKSPACE / "datasets" / "ml")
OUT_DIR = Path(os.environ.get("ACOP_DOC_OUT") or FORMS / "w4" / "데이터전처리_여행_4차v5")
FIG_DIR = OUT_DIR / "그림"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))          # docxfill
os.environ["MPLCONFIGDIR"] = str(OUT_DIR / "_tmp" / "matplotlib")
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)

import charts_v4 as CH  # noqa: E402
import content_core_v2 as K  # noqa: E402
import content_teams_v2 as T  # noqa: E402
from docx_compose import Composer  # noqa: E402

COVER = "SK 네트웍스 Family AI 32기: 6팀"
SUBMIT_DATE = "2026. 9. 28."
REPO_URL = "https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM"
AUTHORS = "김지혜, 서유현, 송채영, 정세환, 최상욱, 최연우"
DRIVE_URL = "https://drive.google.com/drive/folders/1nMDeAqeSsLqeNoJg_N_8xf5s8wyC06ly"
VERSION_TAG = "4차v5"

#: 공개 문서에 들어가면 안 되는 식별자 — 원문 문자열로 적지 않는다.
PRIVATE_MARKERS = ("C:\\", "C:/", "E:/", "F:/", "localhost", "127.0.0.1", "playdata", "F:\\", "E:\\", "_work", "ssh ", "사실표")
TEMPLATE_LEFTOVERS = ("BERT-base-ko", "XGBoost", "8,000건", "2026.04.11", "2026.04.13", "MLflow", "xgb_classifier", "sbert_embed",
                      "random_state=42", "_____팀", "27기", "00기", "kiwipiepy", "사내 업무 문서", "T4 1건", "Back-translation")


def template(name: str) -> Path:
    found = [FORMS / n for n in os.listdir(FORMS) if unicodedata.normalize("NFC", n) == name]
    if len(found) != 1:
        raise SystemExit(f"[멈춤] 양식을 하나로 못 찾았다: {name} ({len(found)}개)")
    return found[0]


def pct(n, d, digits=1):
    return f"{n / d * 100:.{digits}f}%"


def frac(n, d, digits=1):
    return f"{n:,}/{d:,} = {pct(n, d, digits)}"


def need(path: Path):
    if not path.exists():
        raise SystemExit(f"[멈춤] 근거 파일이 없다: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def verify(c: Composer, name: str):
    text = c.all_text()
    left = [t for t in TEMPLATE_LEFTOVERS if t in text]
    private = [i for i, t in enumerate(PRIVATE_MARKERS) if t.lower() in text.lower()]
    ip = re.findall(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)", text)
    if left or private or ip:
        raise SystemExit(f"[멈춤] {name}: 양식 예시 {left} · 비공개 식별자 {len(private)}종 · IP {ip}")


def dump_markdown(docx_path: Path, md_path: Path):
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    d = Document(str(docx_path))
    lines = [f"# {docx_path.stem}", ""]
    for el in d.element.body.iterchildren():
        tag = el.tag.split("}")[1]
        if tag == "p":
            p = Paragraph(el, d)
            if p.text.strip():
                lines.append(p.text.strip())
            elif el.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing"):
                lines.append("[그림]")
        elif tag == "tbl":
            tb = Table(el, d)
            lines.append("")
            for i, row in enumerate(tb.rows):
                cells = []
                for cell in row.cells:
                    x = cell.text.strip().replace("\n", " / ")
                    if not cells or cells[-1] != x:
                        cells.append(x)
                lines.append("| " + " | ".join(cells) + " |")
                if i == 0 and len(tb.rows) > 1:
                    lines.append("|" + "---|" * len(cells))
            lines.append("")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def finish(c: Composer, name: str) -> Path:
    verify(c, name)
    out = c.save(OUT_DIR / name)
    review = OUT_DIR / "검수본문"
    review.mkdir(exist_ok=True)
    dump_markdown(out, review / (out.stem + ".md"))
    print("저장:", out.name)
    return out



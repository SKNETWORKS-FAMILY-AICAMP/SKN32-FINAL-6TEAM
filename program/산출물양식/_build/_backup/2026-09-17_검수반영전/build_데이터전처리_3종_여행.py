# -*- coding: utf-8 -*-
"""데이터 전처리 단계 산출물 3종 — **여행판**(전처리 결과서 · ML/DL 학습 결과서 · 학습한 ML/DL 모델).

    python build_데이터전처리_3종_여행.py                 # 표지 빈칸(팀장 지시 기본값)
    python build_데이터전처리_3종_여행.py --fill-cover    # 표지·변경자 채움(제출 직전)

★`w3/데이터전처리/` 의 커머스판(`build_데이터전처리_3종.py`)과 **따로** 만든다. 그 안내
  문서 「남은 일」의 「여행 데이터로 재작성」이 이 판이다. 커머스판 파일은 건드리지 않는다.
★**숫자는 손으로 적지 않는다.** 전부 학습 산출물 JSON(`datasets/ml/`)에서 읽는다.
  근거 JSON 이 없으면 멈춘다 — 빈칸이나 추정치로 문서를 내지 않는다.
★**점수의 이름을 지킨다.** 감정 정확도는 별점 라벨 기준, 요청 종류·문제 코드는
  「교사(Gemma) 일치도」다. 사람 정답과의 일치도로 쓰지 않는다.
★**접속 정보를 쓰지 않는다.** 서버 별칭·계정·내부 경로는 넣지 않고 장치는 사양으로만
  적는다. 저장 직전에 문서 전체 글을 검사해서 걸리면 멈춘다.
★**양식 예시값이 남지 않게** 예시 행은 지우고, 예시 문구가 남았는지 검사한다.
★검수(코덱스)는 `검수본문/*.md` 를 읽는다. 고칠 것은 **이 스크립트를 고쳐 다시 빌드**한다
  — docx 를 직접 고치면 다음 빌드에서 사라진다.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.text.paragraph import Paragraph

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
FORMS = HERE.parent
WORKSPACE = FORMS.parents[1]
ML = Path(os.environ.get("ACOP_ML_DIR") or WORKSPACE / "datasets" / "ml")          # 시험 실행용으로 바꿀 수 있다
OUT_DIR = Path(os.environ.get("ACOP_DOC_OUT") or FORMS / "w3" / "데이터전처리_여행")
FIG_DIR = OUT_DIR / "그림"
sys.path.insert(0, str(HERE))
from docxfill import check  # noqa: E402  금지 문자 검사(줄표·화살표·별표 등)

COVER = "SK 네트웍스 Family AI 32기: 6팀"
SUBMIT_DATE = "2026. 9. 17."
REPO_URL = "https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM"
AUTHORS = "김지혜, 서유현, 송채영, 정세환, 최상욱, 최연우"
CHANGER = "전체"
DRIVE_URL = "https://drive.google.com/drive/folders/1nMDeAqeSsLqeNoJg_N_8xf5s8wyC06ly"
GPU = "NVIDIA RTX 5090 32GB 공유 GPU 서버(학습 프로세스당 GPU 메모리 7GB 상한)"
GPU_PREV = "NVIDIA RTX 4070 SUPER 12GB"
SENT_MODELS = (("skt/A.X-Encoder-base", "A.X-Encoder-base", "한국어 전용 최신 인코더, 공개 비교표(KoBEST·KLUE)에서 최고"),
               ("jhu-clsp/mmBERT-base", "mmBERT-base", "최신 다국어 ModernBERT, XLM-R 대비 추론 2~4배"),
               ("kakaobank/kf-deberta-base", "kf-deberta-base", "한국어 DeBERTa, A.X 공개 비교표의 차순위"))
CPU = "Intel Core i5-1135G7 노트북(torch 4스레드)"

#: 양식 예시가 남으면 안 되는 문구(커머스판 검사 목록에서 **우리 실제 내용과 겹치지 않는 것만**).
TEMPLATE_LEFTOVERS = ("BERT-base-ko", "XGBoost", "8,000건", "2026.04.11", "2026.04.13", "MLflow",
                      "xgb_classifier", "sbert_embed", "random_state=42", "_____팀", "27기", "00기",
                      "kiwipiepy", "LangChain", "사내 업무 문서", "T4 1건", "Back-translation")
#: 공개 문서에 들어가면 안 되는 식별자 — 원문 문자열로 적지 않는다.
PRIVATE_MARKERS = ("".join(map(chr, (120, 54, 48, 48))), "".join(map(chr, (89, 101, 111, 110))),
                   "playdata", "F:\\", "E:\\", "C:\\Users", "_work", "ssh ")


# ════════════════════════════════════════════════════════════════
# 근거 읽기
# ════════════════════════════════════════════════════════════════
def need(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"[멈춤] 근거 파일이 없다: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def pct(n, d, digits=1):
    return f"{n / d * 100:.{digits}f}%"


def f4(x):
    return f"{x:.4f}"


def ci(pair):
    return f"[{pair[0]:.4f}, {pair[1]:.4f}]"


def optional(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load() -> dict:
    sota = ML / "sentiment_ko" / "sota"
    s = {"sent_prep": need(ML / "sentiment_ko" / "data" / "preprocess_stats.json"),
         "sent_base": need(ML / "sentiment_ko" / "baseline" / "metrics.json"),
         # ★먼저 다른 GPU 에서 같은 설정(배치만 64)으로 학습한 A.X — 재현성 확인용
         "sent_prev": optional(ML / "sentiment_ko" / "skt__A.X-Encoder-base" / "metrics.json"),
         "pool": need(ML / "intent_ko" / "data" / "pool_real_stats.json"),
         "label": need(ML / "intent_ko" / "data" / "labeling_stats.json"),
         "pii": need(ML / "pii_audit.json")}
    # ★비교 모델은 실패해도 목록에 남긴다 — 실패는 실패로 적는다(분모를 줄이지 않는다).
    comparison = {row["model"]: row for row in (optional(sota / "comparison.json") or {}).get("models", [])}
    s["sent_all"] = {}
    for model_id, short, why in SENT_MODELS:
        metrics = optional(sota / model_id.replace("/", "__") / "metrics.json")
        s["sent_all"][model_id] = {"short": short, "why": why, "metrics": metrics,
                                   "failed": (comparison.get(model_id) or {}).get("failed")}
    qwen = optional(ML / "sentiment_ko" / "qwen3" / "Qwen__Qwen3-Embedding-0.6B" / "metrics.json")
    qwen_cmp = {r["model"]: r for r in (optional(ML / "sentiment_ko" / "qwen3" / "comparison.json") or {}).get("models", [])}
    if qwen or qwen_cmp:
        s["sent_all"]["Qwen/Qwen3-Embedding-0.6B"] = {
            "short": "Qwen3-Embedding-0.6B", "why": "다국어 임베딩 상위 계열, 큰 백본의 정확도 이득 확인", "metrics": qwen,
            "failed": (qwen_cmp.get("Qwen/Qwen3-Embedding-0.6B") or {}).get("failed")}
    run = ML / "intent_ko" / "p1_real_only"
    s["int_ax"] = need(run / "intent__skt__A.X-Encoder-base" / "metrics.json")     # 분할 건수(전처리 결과서)
    s["intent_runs"] = []
    for key, label, required in (("p1_real_only", "실제 글", True), ("p3_full", "실제+합성", False),
                                 ("p4_qwen3", "실제+합성", False)):
        folder = ML / "intent_ko" / key
        if not folder.exists():
            if required:
                raise SystemExit(f"[멈춤] 근거 폴더가 없다: {folder}")
            continue
        data = {sub.name: json.loads((sub / "metrics.json").read_text(encoding="utf-8"))
                for sub in folder.iterdir() if (sub / "metrics.json").exists()}
        data["failed"] = {(r.get("field"), r.get("model")): r["failed"]
                          for r in (optional(folder / "comparison.json") or []) if r.get("failed")}
        s["intent_runs"].append((key, label, data))
    return s


def load_picked_extras(s):
    """선정된 감정 모델의 CPU 평가와 가중치 크기 — 선정 뒤에 읽는다."""
    folder = ML / "sentiment_ko" / ("sota" if "Qwen" not in s["picked"]["sentiment"]["model"] else "qwen3")         / s["picked"]["sentiment"]["model"].replace("/", "__")
    s["sent_cpu"] = need(folder / "cpu_eval.json")
    weights = folder / "model.safetensors"
    s["size_mb"] = round(weights.stat().st_size / 1024 / 1024) if weights.exists() else None


def sent_speed(metrics) -> str:
    speed = (metrics or {}).get("inference") or {}
    return f"{speed['sentences_per_second']:,.0f}문장/s" if speed.get("sentences_per_second") else "[미확보]"


def split_sizes(metrics):
    lc = metrics["label_counts"]
    return (sum(lc["train_real"].values()), sum(lc["valid"].values()), sum(lc["test"].values()))


def best_travel(metrics):
    return max(metrics["travel_eval"]["by_threshold"], key=lambda r: r["macro_f1_3class"])


# ════════════════════════════════════════════════════════════════
# 그림 — 맑은 고딕, 상자와 선만
# ════════════════════════════════════════════════════════════════
def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for name in ("Malgun Gothic", "맑은 고딕"):
        if any(f.name == name for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def flow(path: Path, title: str, lanes: list[tuple[str, list[str]]]):
    """세로 흐름 — 줄(lane)마다 한 열, 단계는 위에서 아래로.

    ★가로 흐름을 A4 본문 폭(15cm)에 맞추면 상자 글자가 5pt 아래로 작아졌다(2026-09-17
      첫 렌더링). 세로로 쌓아 글자를 키운다.
    """
    plt = _plt()
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    cols, rows = len(lanes), max(len(steps) for _, steps in lanes)
    box_w, box_h, gap_x, gap_y = 3.4, 1.05, 0.7, 0.55
    width = cols * box_w + (cols - 1) * gap_x
    height = rows * box_h + (rows - 1) * gap_y + 1.1
    fig, ax = plt.subplots(figsize=(width * 0.62, height * 0.62), dpi=250)
    ax.set_xlim(-0.1, width + 0.1)
    ax.set_ylim(-0.1, height + 0.1)
    ax.axis("off")
    palette = ("#E8F1FB", "#EEF7EC", "#FDF3E6", "#F3EDFA")
    for c, (lane, steps) in enumerate(lanes):
        x = c * (box_w + gap_x)
        ax.text(x + box_w / 2, height - 0.35, lane.replace("\n", " "), fontsize=10.5, fontweight="bold",
                ha="center", va="center", color="#1F2933")
        for r, text in enumerate(steps):
            y = height - 1.0 - box_h - r * (box_h + gap_y)
            ax.add_patch(FancyBboxPatch((x, y), box_w, box_h, boxstyle="round,pad=0.02,rounding_size=0.1",
                                        linewidth=1.0, edgecolor="#5B6B7C", facecolor=palette[c % 4]))
            ax.text(x + box_w / 2, y + box_h / 2, text, fontsize=9.5, ha="center", va="center",
                    color="#1F2933", linespacing=1.3)
            if r < len(steps) - 1:
                ax.add_patch(FancyArrowPatch((x + box_w / 2, y - 0.03), (x + box_w / 2, y - gap_y + 0.03),
                                             arrowstyle="-|>", mutation_scale=11, color="#5B6B7C", lw=1.0))
    fig.tight_layout(pad=0.2)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def flow_horizontal(path: Path, title: str, lanes: list[tuple[str, list[str]]]):  # 첫 판(보관용)
    plt = _plt()
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    rows, cols = len(lanes), max(len(steps) for _, steps in lanes)
    fig, ax = plt.subplots(figsize=(1.6 + cols * 2.25, 1.35 * rows + 0.7), dpi=220)
    ax.set_xlim(0, 1.7 + cols * 3.0)
    ax.set_ylim(0, rows * 1.55 + 0.55)
    ax.axis("off")
    ax.text(0.05, rows * 1.55 + 0.28, title, fontsize=11, fontweight="bold", va="center", color="#1F2933")
    palette = ("#E8F1FB", "#EEF7EC", "#FDF3E6", "#F3EDFA")
    for r, (lane, steps) in enumerate(lanes):
        y = (rows - 1 - r) * 1.55 + 0.35
        ax.text(0.05, y + 0.55, lane, fontsize=9, fontweight="bold", va="center", color="#333333")
        for c, text in enumerate(steps):
            x = 1.7 + c * 3.0
            ax.add_patch(FancyBboxPatch((x, y), 2.55, 1.1, boxstyle="round,pad=0.02,rounding_size=0.08",
                                        linewidth=0.9, edgecolor="#5B6B7C", facecolor=palette[r % 4]))
            ax.text(x + 1.275, y + 0.55, text, fontsize=7.8, ha="center", va="center",
                    color="#1F2933", linespacing=1.3)
            if c < len(steps) - 1:
                ax.add_patch(FancyArrowPatch((x + 2.58, y + 0.55), (x + 2.97, y + 0.55),
                                             arrowstyle="-|>", mutation_scale=9, color="#5B6B7C", lw=0.9))
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


# ════════════════════════════════════════════════════════════════
# docx 도구
# ════════════════════════════════════════════════════════════════
def template(name: str) -> Path:
    found = [FORMS / n for n in os.listdir(FORMS) if unicodedata.normalize("NFC", n) == name]
    if len(found) != 1:
        raise SystemExit(f"[멈춤] 양식을 하나로 못 찾았다: {name} ({len(found)}개)")
    return found[0]


BLACK = RGBColor(0, 0, 0)


def plain(run, size=None, bold=False):
    """★양식 예시 글은 파란색(0000ff)이고 기본 스타일은 굵게다 — 채운 글은 검정·보통으로 못박는다."""
    run.bold = bold
    run.font.color.rgb = BLACK
    run.font.name = "맑은 고딕"
    if size:
        run.font.size = Pt(size)


def setc(cell, text, bold=False, size=9):
    check(text, "표")
    p = cell.paragraphs[0]
    for extra in list(cell.paragraphs)[1:]:
        extra._element.getparent().remove(extra._element)
    for r in list(p.runs)[1:]:
        r._element.getparent().remove(r._element)
    if not p.runs:
        p.add_run("")
    r = p.runs[0]
    r.text = text
    plain(r, size, bold)


def fill(tbl, rows, start=1):
    while len(tbl.rows) - 1 < start - 1 + len(rows):
        tbl._tbl.append(copy.deepcopy(tbl.rows[-1]._tr))
    while len(tbl.rows) > start + len(rows):          # 양식 예시 행을 남기지 않는다
        tr = tbl.rows[-1]._tr
        tr.getparent().remove(tr)
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            if j < len(tbl.columns):
                setc(tbl.rows[start + i].cells[j], value)
    keep_table_tidy(tbl)


def keep_table_tidy(tbl):
    """★표 제목 행이 쪽 끝에 홀로 남았다(2026-09-17 렌더링) — 제목 행은 다음 행과 붙이고,
    쪽을 넘기면 제목 행을 반복하며, 한 행은 쪽 경계에서 쪼개지 않는다."""
    for index, row in enumerate(tbl.rows):
        trpr = row._tr.get_or_add_trPr()
        if trpr.find(qn("w:cantSplit")) is None:
            trpr.append(OxmlElement("w:cantSplit"))
        if index == 0:
            if trpr.find(qn("w:tblHeader")) is None:
                trpr.append(OxmlElement("w:tblHeader"))
            for cell in row.cells:
                for para in cell.paragraphs:
                    para.paragraph_format.keep_with_next = True


def header(doc, fill_cover: bool):
    first = doc.tables[0].rows[0].cells[0].paragraphs[0]
    for r in list(first.runs)[1:]:
        r._element.getparent().remove(r._element)
    first.runs[0].text = COVER
    meta = doc.tables[1]
    setc(meta.rows[0].cells[1], "데이터 전처리")
    setc(meta.rows[1].cells[1], SUBMIT_DATE if fill_cover else "")
    setc(meta.rows[2].cells[1], REPO_URL if fill_cover else "")
    setc(meta.rows[3].cells[1], AUTHORS if fill_cover else "")


def para_by_text(doc, starts: str) -> Paragraph:
    hits = [p for p in doc.paragraphs if p.text.strip().startswith(starts)]
    if len(hits) != 1:
        raise SystemExit(f"[멈춤] 양식 문단을 하나로 못 찾았다: {starts} ({len(hits)}개)")
    return hits[0]


def set_line(doc, label: str, value: str):
    """「라벨 : 값」 줄의 값만 바꾼다."""
    check(value, label)
    p = para_by_text(doc, label)
    full = "".join(r.text for r in p.runs)
    head = full.split(":", 1)[0].rstrip() + " : "
    for r in p.runs[1:]:
        r._element.getparent().remove(r._element)
    p.runs[0].text = head + value
    plain(p.runs[0])
    black_bullet(p)


def black_bullet(para: Paragraph):
    """글머리표(●) 색은 문단 기호 서식을 따른다 — 양식은 거기에 파란색을 박아 두었다."""
    ppr = para._p.pPr
    rpr = ppr.find(qn("w:rPr")) if ppr is not None else None
    if rpr is not None:
        # ★굵기 끔(b=0)은 지우지 않는다 — 지우면 기본 스타일의 굵게가 되살아난다. 색만 바꾼다.
        for color in rpr.findall(qn("w:color")):
            rpr.remove(color)
        black = OxmlElement("w:color")
        black.set(qn("w:val"), "000000")
        rpr.append(black)


def _drop_numbering(para: Paragraph):
    """그림·캡션 문단에는 글머리표(●)를 달지 않는다."""
    ppr = para._p.pPr
    if ppr is not None:
        for num in ppr.findall(qn("w:numPr")):
            ppr.remove(num)
        ind = ppr.find(qn("w:ind"))
        if ind is not None:
            ppr.remove(ind)


def insert_after(doc, anchor, items: list):
    """절 제목(문단 머리글 str) 또는 요소(표 등) 뒤에 설명 문단·그림을 넣는다.

    items: str(글머리표 문단) | ("img", 경로, 캡션, 너비cm)
    """
    anchor_el = para_by_text(doc, anchor)._element if isinstance(anchor, str) else anchor
    source = set_line_source(doc)
    cursor = anchor_el

    def new_para():
        nonlocal cursor
        el = copy.deepcopy(source._element)
        cursor.addnext(el)
        cursor = el
        para = Paragraph(el, source._parent)
        for r in list(para.runs):
            r._element.getparent().remove(r._element)
        return para

    for item in items:
        if isinstance(item, tuple):
            pic = new_para()
            _drop_numbering(pic)
            pic.alignment = 1
            pic.add_run().add_picture(str(item[1]), width=Cm(item[3] if len(item) > 3 else 15.0))
            check(item[2], "캡션")
            cap = new_para()
            _drop_numbering(cap)
            cap.alignment = 1
            plain(cap.add_run(item[2]), 8.5)
        else:
            check(item, str(anchor)[:20])
            para = new_para()
            black_bullet(para)
            plain(para.add_run(item), 10)
    return cursor


def move_after(anchor_el, table):
    """표를 제목·문단 뒤로 옮긴다 — ★양식은 표가 **한 절씩 앞 제목** 밑에 붙어 있다
    (「2.1 출처」 밑에 품질 이슈 표). 제목과 내용이 맞도록 옮긴다."""
    anchor_el.addnext(table._tbl)
    return table._tbl


def set_line_source(doc) -> Paragraph:
    """본문 설명 문단 서식의 원본 — 양식의 첫 「라벨 : 값」 줄."""
    for p in doc.paragraphs:
        if " : " in p.text:
            return p
    raise SystemExit("[멈춤] 서식 원본 문단이 없다")


def all_text(doc) -> str:
    parts = [p.text for p in doc.paragraphs]
    for tb in doc.tables:
        for row in tb.rows:
            parts += [c.text for c in row.cells]
    return "\n".join(parts)


def verify(doc, name: str):
    text = all_text(doc)
    left = [t for t in TEMPLATE_LEFTOVERS if t in text]
    private = [i for i, t in enumerate(PRIVATE_MARKERS) if t.lower() in text.lower()]
    ip = re.findall(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)", text)
    if left or private or ip:
        raise SystemExit(f"[멈춤] {name}: 양식 예시 {left} · 비공개 식별자 {len(private)}종 · IP {ip}")


def dump_markdown(doc, path: Path, title: str):
    from docx.table import Table
    lines = [f"# {title}", ""]
    for el in doc.element.body.iterchildren():
        tag = el.tag.split("}")[1]
        if tag == "p":
            p = Paragraph(el, doc)
            if p.text.strip():
                lines.append(p.text.strip())
            elif el.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing"):
                lines.append("[그림]")
        elif tag == "tbl":
            tb = Table(el, doc)
            lines.append("")
            for i, row in enumerate(tb.rows):
                cells = []
                for c in row.cells:
                    x = c.text.strip().replace("\n", " / ")
                    if not cells or cells[-1] != x:
                        cells.append(x)
                lines.append("| " + " | ".join(cells) + " |")
                if i == 0 and len(tb.rows) > 1:
                    lines.append("|" + "---|" * len(cells))
            lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def flow_pages(doc):
    """본문의 수동 쪽 나눔을 없앤다 — 표지 뒤(절 머리 표 앞)는 남긴다.

    ★양식은 예시 내용이 길 때를 기준으로 「2.3」 앞 등에 쪽 나눔을 박아 두었다. 우리 내용은
      짧아서 그 앞 쪽이 거의 비었다(2026-09-17 렌더링, 모델 문서 2쪽).
    """
    body = doc.element.body
    section_head = doc.tables[2]._tbl
    passed = False
    removed = 0
    for el in list(body.iterchildren()):
        if el is section_head:
            passed = True
            continue
        if not passed or el.tag != qn("w:p"):
            continue
        for br in el.findall(".//" + qn("w:br")):
            if br.get(qn("w:type")) == "page":
                br.getparent().remove(br)
                removed += 1
    return removed


def save(doc, name: str):
    flow_pages(doc)
    verify(doc, name)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / name
    doc.save(out)
    review = OUT_DIR / "검수본문"
    review.mkdir(exist_ok=True)
    dump_markdown(doc, review / (Path(name).stem + ".md"), Path(name).stem)
    print("저장:", out.name)
    return out


# ════════════════════════════════════════════════════════════════
# 1. 데이터 전처리 결과서
# ════════════════════════════════════════════════════════════════
def build_preprocess(s, fill_cover):
    sp, pool, lab, pii = s["sent_prep"], s["pool"], s["label"], s["pii"]
    cnt = pool["counts"]
    tr_n, va_n, te_n = split_sizes(s["int_ax"])
    rejected = lab["invalid_label"] + lab["missing_in_answer"] + lab["batch_failed"]
    fig = flow(FIG_DIR / "그림1_전처리흐름.png", "전처리 흐름", [
        ("감정", [f"네이버쇼핑 리뷰\n{sp['read']:,}건",
                  "유니코드 정규화\n반복 글자 축약\n개인정보 마스킹",
                  f"정규화 후 중복 제거\n{sp['dropped']['duplicate']}건",
                  f"층화 분할 8:1:1\n{sp['split_sizes']['train']:,} / {sp['split_sizes']['valid']:,} / {sp['split_sizes']['test']:,}"]),
        ("요청 종류\n문제 코드", [f"소비자상담 원천\n{cnt['rows_read']:,}행",
                               f"여행 서비스 16개 품목\n{cnt['travel_rows']:,}행",
                               f"중복·길이 이상 제거\n고유 {pool['unique_travel_cases_after_filters']:,}건",
                               f"품목별 최대 400건\n{pool['pool_size']:,}건",
                               f"교사 라벨 확정\n{lab['labeled']:,}건"]),
    ])
    d = Document(template("[데이터 전처리] 데이터 전처리 결과서.docx"))
    header(d, fill_cover)
    set_line(d, "전처리 목적", "Case 인라인 분류(감정·요청 종류·문제 코드)를 외부 LLM 호출 없이 로컬 모델로 수행하기 위한 "
                              "학습·평가 데이터를 만든다")
    set_line(d, "전처리 범위", "공개 쇼핑 리뷰 말뭉치(감정), 공정위 소비자상담 사건제목 중 여행 서비스 품목(요청 종류·문제 코드), "
                              "여행 시나리오 문장(평가 전용)")
    set_line(d, "사용 도구", "Python 3.12(csv, json, re, unicodedata, hashlib), scikit-learn, 제품 개인정보 마스킹 모듈, "
                            "Ollama Gemma 4 12B(교사 라벨)")
    insert_after(d, "2.1 데이터 출처 및 현황", [
        f"감정 데이터는 네이버쇼핑 리뷰 공개 말뭉치(Public Domain) {sp['read']:,}건이다. 별점 1·2점은 부정, 4·5점은 긍정으로 "
        f"라벨이 붙어 있고 원 말뭉치에 3점(중립)은 없다. 수집 단계에서 원문 중복 92건을 뺀 판을 입력으로 썼다.",
        f"요청 종류·문제 코드 데이터는 공정거래위원회 소비자상담 공개 데이터 2종(온라인 상거래, 지역별) {cnt['rows_read']:,}행에서 "
        f"항공·해외여행·숙박·공연·외식·철도·버스 등 여행 서비스 16개 품목만 허용 목록으로 골랐다. 제품 라벨 어휘(요청 종류 5종, "
        f"문제 코드 17종)가 붙은 공개 데이터가 없어 교사 모델(Gemma 4 12B)로 라벨을 붙였다.",
        "평가 전용 데이터는 팀 확정 시나리오와 같은 성격의 여행 문장이다(감정 41건, 요청 종류·문제 코드 51건). 학습에는 쓰지 않았고, "
        "라벨은 작업자 1인이 붙였다(이중 검수 [미확보]).",
    ])
    fill(d.tables[3], [
        ("형식 불일치", "사건제목 원천", "CP949 인코딩, 칸 이름이 「품목명(ITEM_NAME)」 형태",
         "인코딩 지정, 칸 이름 포함 검사로 열 선택", "칸을 못 찾으면 파일 단위 실패로 기록(0건)"),
        ("형식 불일치", "text", "NFKC 정규화 전후 차이, 같은 글자 3회 이상 반복, 공백 중복",
         "정규화 후 재저장(반복 글자는 2회로 축약)", f"리뷰 {sp['normalisation_changed_text']:,}건 변경"),
        ("민감정보", "text", "전화·휴대폰·주민번호·계좌·이메일·카드번호 형식",
         "제품과 같은 마스킹 모듈로 치환", f"리뷰 {pii['sentiment_reviews']['replacements_total']}건, "
                                        f"사건제목 {pii['travel_complaint_titles']['replacements_total']}건"),
        ("중복치", "사건번호", "두 원천 파일에 같은 사건번호", "한 건만 유지", f"{cnt['dropped_same_case_other_file']:,}건"),
        ("중복치", "text", "정규화 후 SHA1 동일", "대표 한 건만 유지",
         f"리뷰 {sp['dropped']['duplicate']}건, 사건제목 {cnt['dropped_duplicate_text']:,}건"),
        ("이상치", "사건제목 길이", "8자 미만 또는 150자 초과", "행 제거", f"{cnt['dropped_length']:,}건"),
    ])
    fill(d.tables[4], [
        ("형식 정합성", "리뷰 JSONL, 상담 CSV(CP949)", "UTF-8 JSONL", "인코딩·칸 이름 통일"),
        ("대상 선별", f"상담 {cnt['rows_read']:,}행", f"여행 서비스 {cnt['travel_rows']:,}행", "품목 허용 목록으로 도메인 한정"),
        ("정규화·마스킹", "선별 텍스트", "표준화·마스킹 텍스트", "학습과 운영이 같은 형태의 글을 입력받게 함"),
        ("중복·이상치 제거", "표준화 텍스트", f"고유 사건제목 {pool['unique_travel_cases_after_filters']:,}건",
         "학습 편향·시험 누수 방지"),
        ("라벨링·분할", f"표본 {pool['pool_size']:,}건", f"교사 라벨 {lab['labeled']:,}건, 학습·검증·시험 조각",
         "제품 어휘로 라벨 부여, 라벨 기준 층화 분할"),
    ])
    set_line(d, "분할 기준", "라벨 기준 층화 추출(seed=7). 요청 종류·문제 코드는 라벨별 8:1:1, 3건 미만 라벨은 학습에만 둔다")
    insert_after(d, "분할 기준", [
        f"감정은 학습 {sp['split_sizes']['train']:,}건, 검증 {sp['split_sizes']['valid']:,}건, 시험 {sp['split_sizes']['test']:,}건이고 "
        f"세 조각의 부정·긍정 비율이 모두 0.50이다. 요청 종류는 학습 {tr_n:,}건, 검증 {va_n:,}건, 시험 {te_n:,}건이며 "
        f"시험 조각은 실제 사건제목으로만 구성한다(합성 문장 제외).",
    ])
    fill(d.tables[5], [
        ("text(리뷰)", "TEXT", "빈 문자열 행 제거(0건)", "정규화 후 SHA1", "2~300자 밖 제거(0건)", "감정 모델 입력"),
        ("label(감정)", "CATEGORY", "어휘 밖 행 제거(0건)", "해당 없음", "원 말뭉치에 3점 없음", "positive, negative"),
        ("text(사건제목)", "TEXT", "칸 부족 행 제거", "사건번호, 문장 해시", "8~150자 밖 제거", "요청 종류·문제 코드 입력"),
        ("intent", "CATEGORY", f"교사 답 누락 {lab['missing_in_answer']}건 제외", "해당 없음",
         f"어휘 밖 답 {lab['invalid_label']}건 제외", "5종, 교사 라벨"),
        ("issue_code", "CATEGORY", "intent 와 같은 행 기준", "해당 없음", "가까운 코드로 고쳐 넣지 않음", "17종, 접두가 담당 팀"),
    ])
    fill(d.tables[6], [
        ("분할", "감정 학습", f"80% ({sp['split_sizes']['train']:,}건)", "층화 추출(seed=7), 라벨 비율 0.50"),
        ("분할", "감정 검증", f"10% ({sp['split_sizes']['valid']:,}건)", "에폭별 검증 정확도 기록"),
        ("분할", "감정 시험", f"10% ({sp['split_sizes']['test']:,}건)", "최종 평가 전용, 학습과 격리"),
        ("분할", "요청 종류·문제 코드", f"학습 {tr_n:,} / 검증 {va_n:,} / 시험 {te_n:,}건",
         "요청 종류 기준 층화, 문제 코드는 같은 방식으로 따로 분할"),
        ("품질", "교사 라벨 확정", f"{lab['labeled']:,}건 / {lab['input']:,}건({pct(lab['labeled'], lab['input'])})",
         f"Gemma 4 12B, 온도 0, 라벨 안내 {lab['guide']}"),
        ("품질", "교사 답 제외", f"{rejected}건(어휘 밖 {lab['invalid_label']}, 누락 {lab['missing_in_answer']})",
         "추정으로 채우지 않고 제외, 한 건씩 재질의해 다음 판에 반영"),
        ("품질", "민감정보 마스킹", f"리뷰 {pii['sentiment_reviews']['replacements_total']}건, "
                               f"사건제목 {pii['travel_complaint_titles']['replacements_total']}건 치환",
         "제품 마스킹 규칙에 주민번호·휴대폰·계좌 형식 추가, 적용 순서대로 집계"),
        ("품질", "산술 검사", "읽은 건수 = 제거 합계 + 남은 건수", "두 데이터 모두 일치, 불일치 시 실행 실패"),
        ("후속 활용", "ML/DL 학습", "JSONL(text, label)", "TF-IDF 기준선과 인코더 파인튜닝의 공통 입력"),
        ("후속 활용", "평가 전용 조각", "여행 문장 41건, 51건", "학습 미사용, 도메인 차이 확인"),
        ("후속 활용 / 재현성", "재현 명령과 기록", "python -m ml.preprocess, python -m ml.build_intent_pool",
         "seed, 입력 경로, 단계별 제거 건수를 통계 JSON으로 함께 저장"),
    ])
    fill(d.tables[7], [("2026.09.17", CHANGER if fill_cover else "", "초안: 여행 분류 모델 학습 데이터 전처리", "전체", "v1.0")])
    # ── 제목과 표를 맞춘다: 2.2 에 품질 이슈·필드 처리 표, 2.3 에 처리 단계 표와 흐름도
    t_issue, t_steps, t_fields = d.tables[3], d.tables[4], d.tables[5]
    after = move_after(para_by_text(d, "2.2 품질 이슈 진단")._element, t_issue)
    after = insert_after(d, after, ["위 이슈를 필드별 처리 기준으로 정리하면 다음과 같다. 교사 라벨의 누락·어휘 밖 답은 "
                                    "가장 가까운 코드로 고쳐 넣지 않고 제외했다."])
    move_after(after, t_fields)
    after = move_after(para_by_text(d, "2.3 전처리 파이프라인 흐름도")._element, t_steps)
    insert_after(d, after, [("img", fig, "그림 1. 두 학습 데이터의 전처리 흐름(건수는 실행 통계 기준)", 14.0)])
    return save(d, "[데이터 전처리] 데이터 전처리 결과서_3차_여행.docx")



def _cand_sentiment(s):
    """감정 후보 — 기준선 + 인코더(실패도 줄로 남긴다)."""
    sb = s["sent_base"]
    rows = [{"model": "TF-IDF + 로지스틱 회귀", "short": "TF-IDF", "kind": "Baseline", "metrics": sb,
             "acc": sb["test"]["accuracy"], "ci": sb["test"]["accuracy_ci95"], "f1": sb["test"]["macro_f1"],
             "speed": None, "params": None, "failed": None, "why": "해석 가능한 기준선, 낱말·글자 n-gram"}]
    for model_id, info in s["sent_all"].items():
        m = info["metrics"]
        rows.append({"model": model_id, "short": info["short"], "kind": "DL", "metrics": m, "why": info["why"],
                     "acc": m["review_test"]["accuracy"] if m else None,
                     "ci": m["review_test"]["accuracy_ci95"] if m else None,
                     "f1": m["review_test"]["macro_f1"] if m else None,
                     "speed": ((m or {}).get("inference") or {}).get("sentences_per_second"),
                     "params": (m or {}).get("params_million"),
                     "failed": None if m else (info["failed"] or "결과 없음")})
    return rows


def _cand_labels(s, field):
    """요청 종류·문제 코드 후보 — 실제 글만(우선판)과 실제+합성(전체판)을 모두 줄로 둔다."""
    rows = []
    for key, label, data in s["intent_runs"]:
        for model_id, short in (("tfidf", "TF-IDF"), ("skt/A.X-Encoder-base", "A.X-Encoder-base"),
                                ("jhu-clsp/mmBERT-base", "mmBERT-base"), ("kakaobank/kf-deberta-base", "kf-deberta-base"),
                                ("Qwen/Qwen3-Embedding-0.6B", "Qwen3-Embedding-0.6B")):
            m = data.get(f"{field}__{model_id.replace('/', '__')}")
            failed = data.get("failed", {}).get((field, model_id))
            if m is None and failed is None:
                continue
            speed = next((h["inference"] for h in (m or {}).get("history") or [] if "inference" in h), {})
            t = (m or {}).get("teacher_agreement_test") or {}
            rows.append({"model": model_id, "short": short, "run": label, "kind": "Baseline" if model_id == "tfidf" else "DL",
                         "metrics": m, "acc": t.get("accuracy"), "ci": t.get("accuracy_ci95"), "f1": t.get("macro_f1"),
                         "gold": ((m or {}).get("gold_author_labels") or {}).get("accuracy"),
                         "speed": speed.get("sentences_per_second"), "failed": failed,
                         "train": f"{m['train_real']:,}+{m['train_synthetic']:,}" if m else None})
    return rows


def travel_note(rows, picked) -> str:
    """★선정은 리뷰 시험 정확도로 했다. 여행 문장(41건)에서 다른 모델이 더 나았으면 숨기지 않고 적는다."""
    scored = [(best_travel(r["metrics"])["macro_f1_3class"], r) for r in rows
              if r["kind"] == "DL" and (r.get("metrics") or {}).get("travel_eval")]
    if not scored:
        return "여행 문장 조각 평가 결과가 없다 [미확보]."
    top_f1, top = max(scored, key=lambda x: x[0])
    mine = best_travel(picked["metrics"])["macro_f1_3class"]
    if top is picked:
        return f"여행 문장 41건의 3분류 F1도 선정 모델({picked['short']}, {mine:.3f})이 가장 높았다. 다만 41건이라 방향만 확인한 값이다."
    return (f"선정 감정 모델({picked['short']})은 리뷰 시험에서 가장 정확했지만, 여행 문장 41건의 3분류 F1은 {mine:.3f}로 "
            f"{top['short']}({top_f1:.3f})보다 낮았다. 41건은 소표본이라 선정을 바꾸지 않았고, 여행 문장 라벨을 늘려 다시 비교하는 것을 "
            f"다음 과제로 둔다.")


def choose(rows):
    """★선정 규칙 — 기준선을 포함한 모든 후보 중 시험 정확도가 가장 높은 것. 그와 95% 신뢰구간이 겹치는
    인코더가 있으면 GPU 추론이 가장 빠른 것을 고른다(정확도 차이를 구분할 수 없으면 빠른 쪽이 운영에 낫다).

    ☆2026-09-17 초안: 인코더끼리만 비교했더니 문제 코드에서 기준선(0.713)보다 훨씬 낮은 A.X(0.327)가 뽑혔다.
      기준선보다 나쁜 모델을 선정하지 않도록 기준선을 후보에 넣는다."""
    ok = [r for r in rows if r["acc"] is not None]
    if not ok:
        raise SystemExit("[멈춤] 선정할 결과가 없다")
    best = max(ok, key=lambda r: r["acc"])
    lo = best["ci"][0] if best["ci"] else best["acc"]
    tied = [r for r in ok if r["ci"] and r["ci"][1] >= lo] or [best]
    baseline = next((r for r in tied if r["kind"] == "Baseline"), None)
    if baseline is not None:
        # ★기준선과 구분되지 않으면 더 단순·가벼운 기준선을 택한다(속도를 잰 적 없는 기준선을 「느리다」로 읽지 않는다).
        pick = baseline
        reason = "정확도 최고" if pick is best else             f"정확도 최고({best['short']} {f4(best['acc'])})와 95% 신뢰구간이 겹쳐 더 단순한 기준선"
    else:
        pick = max(tied, key=lambda r: (r["speed"] or 0, r["acc"]))
        reason = "정확도 최고" if pick is best else             f"정확도 최고({best['short']} {f4(best['acc'])})와 95% 신뢰구간이 겹쳐 GPU 추론이 빠른 쪽"
    pick["reason"] = reason
    return pick


def result_text(r, score="Acc"):
    if r["failed"]:
        return f"실패: {str(r['failed'])[:70]}"
    speed = f", 추론 {r['speed']:,.0f}문장/s" if r.get("speed") else ""
    travel = ""
    if (r.get("metrics") or {}).get("travel_eval"):
        bt = best_travel(r["metrics"])
        travel = f", 여행 3분류 F1 {bt['macro_f1_3class']:.3f}"
    return f"{score} {f4(r['acc'])} {ci(r['ci']) if r['ci'] else ''}, F1 {f4(r['f1'])}{speed}{travel}".replace("  ", " ")


# ════════════════════════════════════════════════════════════════
# 2. 머신러닝 / 딥러닝 학습 결과서
# ════════════════════════════════════════════════════════════════
def build_training(s, fill_cover):
    sent, intent, issue = _cand_sentiment(s), _cand_labels(s, "intent"), _cand_labels(s, "issue_code")
    ps, pi, pj = choose(sent), choose(intent), choose(issue)
    s["picked"] = {"sentiment": ps, "intent": pi, "issue_code": pj}
    load_picked_extras(s)
    sm = ps["metrics"]
    bt = best_travel(sm)
    label_n = s["label"]
    fig = flow(FIG_DIR / "그림2_실험흐름.png", "학습과 평가 흐름", [
        ("학습", ["전처리 조각\n학습·검증·시험", "기준선\nTF-IDF + 로지스틱 회귀",
                 "인코더 파인튜닝 4종\nGPU, bfloat16", "에폭별 검증\n정확도 기록"]),
        ("평가", ["시험 조각\n정확도·macro F1", "부트스트랩 2,000회\n95% 신뢰구간",
                 "여행 문장 조각\n도메인 차이 확인", "선정 모델을 제품\n어댑터로 CPU 측정"]),
    ])
    d = Document(template("[데이터 전처리] 머신러닝_딥러닝 학습 결과서.docx"))
    header(d, fill_cover)
    set_line(d, "목표", "Case 인라인 분류를 로컬 모델로 수행해 외부 LLM 호출과 지연을 줄이고, 확신이 낮으면 LLM에 넘기는 기준을 만든다")
    set_line(d, "문제 정의", "여행 고객 메시지 한 건으로 감정(긍정·부정, 확신이 낮으면 중립), 요청 종류 5종, 문제 코드 17종을 예측한다")
    set_line(d, "사용 프레임워크", "scikit-learn, PyTorch, Hugging Face Transformers, Ollama(교사 라벨)")

    picked_by = {}
    for task, r in (("감정", ps), ("요청 종류", pi), ("문제 코드", pj)):
        picked_by.setdefault(r["model"], []).append(task)
    t3 = [("Baseline", "TF-IDF + 로지스틱 회귀", "해석 가능한 기준선, 낱말·글자 n-gram",
           f"리뷰 {s['sent_base']['train_size']:,}건, 사건제목 학습 조각", "CPU 학습")]
    for model_id, short, why in SENT_MODELS + (("Qwen/Qwen3-Embedding-0.6B", "Qwen3-Embedding-0.6B",
                                                  "다국어 임베딩 상위 계열, 큰 백본의 정확도 이득 확인"),):
        tasks = picked_by.get(model_id)
        t3.append(("DL(선정)" if tasks else "DL(비교)", model_id, why, "감정·요청 종류·문제 코드 같은 조각",
                   f"선정: {', '.join(tasks)}" if tasks else "비교"))
    t3.append(("교사", "Gemma 4 12B(Ollama)", "여행 라벨 부여(증류의 교사), 학습 대상 아님",
               f"사건제목 {label_n['input']:,}건", "온도 0, 어휘 밖 답 제외"))
    fill(d.tables[3], t3)
    fill(d.tables[4], [
        ("Accuracy", "시험 조각 정답률", "기준선 초과, 95% 신뢰구간 비교", "부트스트랩 2,000회"),
        ("F1(macro)", "라벨별 F1 평균", "소수 라벨 누락 확인", "문제 코드 17종은 불균형이 큼"),
        ("교사 일치도", "Gemma 라벨과 예측의 일치율", "사람 정답이 아님을 표기", "요청 종류·문제 코드"),
        ("추론 속도", "GPU 시험 조각 처리량, CPU 한 문장 지연", "신뢰구간이 겹치면 빠른 모델 선정", "선정 모델만 CPU 측정"),
        ("여행 3분류 F1", "여행 문장 41건(중립 포함)", "도메인 차이 방향 확인", "소표본, 일반화 근거 아님"),
    ])
    insert_after(d, "2.3 실험 파이프라인", [
        f"모든 모델은 같은 조각, 같은 지표, 같은 seed(7)로 평가했다. 인코더는 {GPU}에서 bfloat16 자동 혼합정밀도로 학습했고, "
        f"선정 모델의 CPU 지연은 {CPU}에서 제품 어댑터로 불러 측정했다.",
        "선정 규칙: 인코더 중 시험 정확도가 가장 높은 모델을 고르되, 그 모델과 95% 신뢰구간이 겹치는 후보가 있으면 "
        "정확도 차이를 구분할 수 없다고 보고 GPU 추론이 가장 빠른 모델을 고른다. 단, GPU 처리량은 교사 라벨링용 LLM과 GPU를 "
        "나눠 쓰는 상태에서 잰 참고값이다(같은 모델도 부하에 따라 차이가 있었다). 제품 기준 지연은 선정 모델을 CPU에서 따로 쟀다.",
        ("img", fig, "그림 2. 학습과 평가 흐름", 12.0),
    ])
    set_line(d, "최종 선정 모델", f"감정 {ps['short']}, 요청 종류 {pi['short']}({pi['run']}), 문제 코드 {pj['short']}({pj['run']})")
    fill(d.tables[5], [
        ("learning_rate", "2e-5(감정), 3e-5(요청·문제)", "고정(탐색 안 함)", "인코더 파인튜닝 통상값", "인코더 4종", "OneCycle, warmup 10%"),
        ("batch_size", "32(Qwen3는 16)", "고정(탐색 안 함)", "공유 GPU 메모리 상한 안에서 가능한 값", "인코더 4종", ""),
        ("epochs", "2(감정), 4(요청·문제)", "고정(탐색 안 함)",
         f"선정 감정 모델 검증 정확도 {sm['history'][0]['valid_accuracy']:.4f}, {sm['history'][-1]['valid_accuracy']:.4f}", "인코더 4종", ""),
        ("max_len", "96 토큰", "고정(탐색 안 함)", f"리뷰 길이 p95 {s['sent_prep']['char_length']['p95']}자", "인코더 4종", ""),
        ("class_weight", "라벨 빈도 반비례(상한 20)", "고정(탐색 안 함)", "문제 코드 불균형 보정", "요청·문제 코드", "TF-IDF는 balanced"),
    ])
    t6, n = [], 0
    for task, rows, score in (("감정", sent, "Acc"), ("요청 종류", intent, "일치도"), ("문제 코드", issue, "일치도")):
        for r in rows:
            n += 1
            setting = f"{task} {r['short']}" + (f"({r['run']})" if r.get("run") else "")
            mark = " (선정)" if r is {"감정": ps, "요청 종류": pi, "문제 코드": pj}[task] else ""
            t6.append((r["kind"], f"EXP-{n:02d}", setting, result_text(r, score) + mark))
    prev = s.get("sent_prev")
    if prev:
        now_ax = s["sent_all"]["skt/A.X-Encoder-base"]["metrics"]
        p_ci = prev["review_test"]["accuracy_ci95"]
        if now_ax:
            n_ci = now_ax["review_test"]["accuracy_ci95"]
            same = p_ci[0] <= n_ci[1] and n_ci[0] <= p_ci[1]
            verdict = "이번 학습과 95% 신뢰구간이 겹침(구분되지 않음)" if same else "이번 학습과 95% 신뢰구간이 겹치지 않음"
        else:
            verdict = "이번 학습 결과 없음(비교 불가)"
        t6.append(("재현성", "확인", f"감정 A.X, {GPU_PREV}(배치 64)",
                   f"Acc {f4(prev['review_test']['accuracy'])} {ci(p_ci)}, {verdict}"))
    t6.append(("추론", "CPU", f"감정 {ps['short']}, 제품 어댑터",
               f"한 문장 p50 {s['sent_cpu']['latency_single_ms']['p50']} ms, p95 {s['sent_cpu']['latency_single_ms']['p95']} ms"))
    t6.append(("도메인", "여행 문장", f"감정 {ps['short']}, 3분류(중립 물러섬)",
               f"임계값 {bt['threshold']}에서 F1 {f4(bt['macro_f1_3class'])}, 중립 {pct(bt['abstain_rate'], 1)}(41건)"))
    fill(d.tables[6], t6)
    fill(d.tables[7], [("2026.09.17", CHANGER if fill_cover else "", "초안: 기준선·인코더 4종 학습 결과와 선정 근거", "전체", "v1.0")])
    t_params, t_results = d.tables[5], d.tables[6]
    move_after(para_by_text(d, "그림 2.")._element, t_params)
    move_after(para_by_text(d, "최종 선정 모델")._element, t_results)
    insert_after(d, "3.2 과적합", [
        f"과적합은 에폭마다 검증 조각 정확도를 기록해 관리했다. 선정 감정 모델은 학습 손실이 {sm['history'][0]['train_loss']}에서 "
        f"{sm['history'][-1]['train_loss']}로 내려가는 동안 검증 정확도가 {sm['history'][0]['valid_accuracy']:.4f}, "
        f"{sm['history'][-1]['valid_accuracy']:.4f}로 유지돼 과적합 징후가 없었다. weight decay 0.01과 기울기 절단 1.0을 적용했다.",
        "요청 종류·문제 코드는 학습 조각이 수천 건 규모라 4 epoch 동안 검증 정확도를 함께 기록했고, 소수 라벨은 손실 가중으로 보정했다. "
        "합성 문장은 학습에만 넣고 시험 조각은 실제 사건제목으로만 구성해 점수가 부풀지 않게 했다.",
        travel_note(sent, ps),
        "과소적합보다 큰 위험은 도메인 차이와 교사 라벨 오류다. 감정 모델은 쇼핑 리뷰로 학습해 여행 문장의 중립을 직접 내지 못하므로 "
        "확신이 낮으면 중립으로 물러서게 했고, 요청 종류·문제 코드는 사람 검수 표본으로 교사 정확도를 재는 것이 다음 과제다.",
    ])
    return save(d, "[데이터 전처리] 머신러닝_딥러닝 학습 결과서_3차_여행.docx")


# ════════════════════════════════════════════════════════════════
# 3. 학습한 ML / DL 모델
# ════════════════════════════════════════════════════════════════
def learner_name(r) -> str:
    return "TF-IDF + 로지스틱 회귀" if r["kind"] != "DL" else f"{r['short']}(FT)"


def learner_dep(r) -> str:
    return "scikit-learn" if r["kind"] != "DL" else "transformers"


def build_model(s, fill_cover):
    ps, pi, pj = s["picked"]["sentiment"], s["picked"]["intent"], s["picked"]["issue_code"]
    sm, cpu = ps["metrics"], s["sent_cpu"]
    bt = best_travel(sm)
    names = {ps["short"], pi["short"], pj["short"]}
    fig = flow(FIG_DIR / "그림3_추론구조.png", "제품 안에서의 추론 구조(로컬 우선, 확신이 낮으면 LLM)", [
        ("입력", ["고객 메시지", "개인정보 마스킹\n(제품 모듈)", "토크나이저\n최대 96토큰"]),
        ("모델", [f"감정 모델\n{ps['short']}", f"요청 종류 모델\n{pi['short']}", f"문제 코드 모델\n{pj['short']}"]),
        ("후처리", ["확신도 검사\n임계값 0.7", "낮으면 LLM에 위임\n충분하면 로컬 라벨", "분류 계약 검사\nCase 분류 이벤트"]),
    ])
    d = Document(template("[데이터 전처리] 학습한 ML_DL 모델.docx"))
    header(d, fill_cover)
    enc = [r for r in (ps, pi, pj) if r["kind"] == "DL"]
    lin = [r for r in (ps, pi, pj) if r["kind"] != "DL"]
    kinds = []
    if enc:
        kinds.append(f"파인튜닝한 인코더 분류기 {len(enc)}종({', '.join(sorted({r['short'] for r in enc}))})")
    if lin:
        kinds.append(f"TF-IDF 로지스틱 회귀 분류기 {len(lin)}종")
    set_line(d, "모델 유형", ", ".join(kinds) + " (과제별로 시험 조각에서 선정)")
    set_line(d, "담당 태스크", "Case 인라인 분류: 감정(긍정·부정·중립), 요청 종류 5종, 문제 코드 17종")
    set_line(d, "프레임워크 / 버전", "학습 PyTorch 2.13(CUDA 13.0), Transformers 5.16, scikit-learn 1.9 / "
                                 "추론 검증 PyTorch 2.12(CPU), Transformers 5.13, scikit-learn 1.5")
    fill(d.tables[3], [
        ("전처리", "정규화·마스킹", "NFKC, 반복 글자 축약, 개인정보 치환", "제품 마스킹 모듈", "학습·추론 공용"),
        *([("특징", "모델별 토크나이저", "하위 단어 분할, 최대 96토큰", "transformers", "모델 폴더에 함께 저장")] if enc else []),
        *([("특징", "TF-IDF 벡터라이저", "낱말 1~2 · 글자 2~4 n-gram", "scikit-learn", "Pipeline 에 함께 저장")] if lin else []),
        *[(f"학습기 {i}", learner_name(r), task, learner_dep(r), note)
          for i, (r, task, note) in enumerate(((ps, "감정 2분류, 확률 출력", f"리뷰 {sm['train_size']:,}건"),
                                                (pi, "요청 종류 5분류", f"사건제목 {pi.get('run') or ''} 학습 조각"),
                                                (pj, "문제 코드 17분류", f"사건제목 {pj.get('run') or ''} 학습 조각")), start=1)],
        ("후처리", "캐스케이드 제공자", "확신이 낮으면 LLM 위임, 감정은 중립 물러섬", "제품 분류 계약", "계약 검사 통과 시험 4건"),
    ])
    fill(d.tables[4], [
        ("text", "str", "메시지 1건", "마스킹된 고객 입력"),
        *([("input_ids", "int64", "[1, 최대 96]", "인코더 토크나이저 출력")] if enc else []),
        *([("features", "sparse float", "[1, 어휘 수]", "TF-IDF 희소 벡터")] if lin else []),
        ("logits", "float32", "[1, 라벨 수]", "감정 2, 요청 종류 5, 문제 코드 17"),
        ("label", "str", "1개", "제품 어휘 라벨(어휘 밖이면 분류 실패로 처리)"),
        ("confidence", "float", "0~1", "최대 확률, 위임·물러섬 판단에 사용"),
    ])
    insert_after(d, "2.3 학습 데이터", [
        f"CPU 측정 장치는 {CPU}이고, 모델은 제품 어댑터(app/infrastructure/ml)로 불러 측정했다.",
        ("img", fig, "그림 3. 학습한 모델이 제품 분류 흐름에 들어가는 구조", 12.5),
    ])
    set_line(d, "모델 파일", "sentiment, intent, issue_code 폴더(인코더는 model.safetensors·config.json·토크나이저, "
                            "TF-IDF는 model.joblib, 공통 metrics.json), 감정 기준선 tfidf_baseline(model.joblib). "
                            f"제출 위치: 팀 공유 드라이브 {DRIVE_URL}")
    lat, batch = cpu["latency_single_ms"], cpu["batch32_throughput"]
    fill(d.tables[5], [
        (f"크기({ps['short']})", str(s["size_mb"]) if s["size_mb"] else "[미확보]", "MB", "model.safetensors", "해당 없음",
         "토크나이저 별도"),
        ("적재 시간", f"{cpu['load_seconds']}", "s", "CPU 첫 호출 1회", "[미확보]", "이후 호출은 적재된 모델 재사용"),
        ("추론 지연 p50", f"{lat['p50']}", "ms", f"CPU 한 문장 {lat['n']}회", "[미확보]", "제품 어댑터 경유"),
        ("추론 지연 p95", f"{lat['p95']}", "ms", f"CPU 한 문장 {lat['n']}회", "[미확보]", "제품 어댑터 경유"),
        ("GPU 처리량", sent_speed(sm).replace("문장/s", ""), "문장/s", "시험 조각 19,988건, bfloat16", "해당 없음", "공유 GPU 부하 속 참고값"),
    ])
    pi_t, pj_t = pi["metrics"]["teacher_agreement_test"], pj["metrics"]["teacher_agreement_test"]
    fill(d.tables[6], [
        ("성능", "감정 정확도", f"{f4(ps['acc'])}, 95% 신뢰구간 {ci(ps['ci'])}",
         f"리뷰 시험 {sm['test_size']:,}건, 기준선 {f4(s['sent_base']['test']['accuracy'])}, 선정 사유: {ps['reason']}"),
        ("성능", "요청 종류 교사 일치도", f"{f4(pi['acc'])}, macro F1 {f4(pi['f1'])}",
         f"사건제목 시험 {pi_t['n']:,}건, Gemma 라벨 기준, 선정 사유: {pi['reason']}"),
        ("성능", "문제 코드 교사 일치도", f"{f4(pj['acc'])}, macro F1 {f4(pj['f1'])}",
         f"사건제목 시험 {pj_t['n']:,}건, Gemma 라벨 기준, 선정 사유: {pj['reason']}"),
        ("저장", "형식과 버저닝", "SafeTensors, config, 토크나이저, 모델 폴더별 metrics.json",
         "pickle 없이 로딩, seed·에폭·학습 건수·지표를 가중치와 함께 보관"),
        ("로딩", "호출 코드", "LocalLabelModel(model_dir).predict(text)",
         f"감정은 LocalSentiment(model_dir, threshold={bt['threshold']}), 여행 문장 조각에서 가장 나은 임계값"),
        ("추론", "캐스케이드", "확신도 0.7 미만은 LLM에 위임", "모르면 지어내지 않고 위임 여부를 기록, 분류 계약 검사 통과"),
        ("한계", "도메인 이동", f"리뷰 학습 감정의 여행 3분류 F1 {f4(bt['macro_f1_3class'])}(41건)", "여행 문장 라벨 확충 후 재학습"),
        ("한계", "교사 라벨 의존", "요청 종류·문제 코드 점수는 Gemma 일치도", "사람 검수 표본으로 교사 정확도 측정 [미확보]"),
        ("한계", "심각도 미지원", "severity 라벨 학습 데이터 없음", "LLM 값 사용, 규칙으로 채울지 [결정 필요]"),
        ("연계", "Team 라우팅", "문제 코드 접두가 case_type, 요청 종류가 intent", "두 축으로 Activity·Dining·Mobility 선택"),
    ])
    fill(d.tables[7], [("2026.09.17", CHANGER if fill_cover else "", "초안: 선정 인코더 3종과 기준선의 구조·저장·추론", "전체", "v1.0")])
    return save(d, "[데이터 전처리] 학습한 ML_DL 모델_3차_여행.docx")



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fill-cover", action="store_true", help="표지·변경자 채움(팀장 확인 후)")
    parser.add_argument("--pick-only", action="store_true", help="선정 모델만 계산해 출력")
    args = parser.parse_args()
    s = load()
    if args.pick_only:
        picks = {"sentiment": choose(_cand_sentiment(s)), "intent": choose(_cand_labels(s, "intent")),
                 "issue_code": choose(_cand_labels(s, "issue_code"))}
        print(json.dumps({k: {"model": v["model"], "run": v.get("run"), "acc": v["acc"], "reason": v["reason"]}
                          for k, v in picks.items()}, ensure_ascii=False, indent=2))
        return
    outs = [build_preprocess(s, args.fill_cover), build_training(s, args.fill_cover), build_model(s, args.fill_cover)]
    print("\n생성 완료:", *[o.name for o in outs], sep="\n  ")


if __name__ == "__main__":
    main()

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
    s["env"] = need(ML / "environment.json")
    s["sent_first_run"] = {r["model"]: r for r in (optional(sota / "comparison.json") or {}).get("models", [])}
    synth = ML / "intent_ko" / "data" / "synth_labeled.jsonl"
    if synth.exists():
        rows = [json.loads(l) for l in synth.read_text(encoding="utf-8").splitlines() if l.strip()]
        s["synth_kept"] = sum(1 for r in rows if r.get("intent") == r.get("intended_intent")
                              and r.get("issue_code") == r.get("intended_issue_code"))
        s["synth_total"] = len(rows)
    run = ML / "intent_ko" / "p1_real_only"
    s["int_ax"] = need(run / "intent__skt__A.X-Encoder-base" / "metrics.json")     # 분할 건수(전처리 결과서)
    s["iss_ax"] = need(run / "issue_code__skt__A.X-Encoder-base" / "metrics.json")
    s["intent_runs"] = []
    for key, label, required in (("p1_real_only", "실제 글", True), ("p1b_real_tuned", "실제 글·가중 조정", False),
                                 ("p3_full", "실제+합성·가중 조정", False), ("p4_qwen3", "실제+합성·가중 조정", False)):
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
    s["size_mib"] = round(weights.stat().st_size / 1024 / 1024) if weights.exists() else None
    if weights.exists():   # ★크기 근거를 파일로 남긴다(코덱스 검수 중요 9)
        (folder / "model_files.json").write_text(json.dumps(
            {"model.safetensors_bytes": weights.stat().st_size, "mib": s["size_mib"]}, indent=2), encoding="utf-8")


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
    jr_n, jv_n, jt_n = split_sizes(s["iss_ax"])
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
        f"감정 데이터는 네이버쇼핑 리뷰 공개 말뭉치(Public Domain, 수집 보고서에서 라이선스 확인) {sp['read']:,}건이다. 별점 1·2점은 부정, 4·5점은 긍정으로 "
        f"라벨이 붙어 있고 원 말뭉치에 3점(중립)은 없다. 수집 단계에서 원문 중복 92건을 뺀 판을 입력으로 썼다.",
        f"요청 종류·문제 코드 데이터는 공정거래위원회 소비자상담 공개 데이터 2종(온라인 상거래, 지역별) {cnt['rows_read']:,}행에서 "
        f"항공·해외여행·숙박·공연·외식·철도·버스 등 여행 서비스 {len(pool['travel_items_allowlist'])}개 품목을 허용 목록으로 적용했고, "
        f"실제로 데이터가 있던 품목은 {len(pool['per_item'])}개였다. 제품 라벨 어휘(요청 종류 5종, "
        f"문제 코드 17종)가 붙은 공개 데이터가 없어 교사 모델(Gemma 4 12B)로 라벨을 붙였다.",
        "평가 전용 데이터는 팀 확정 시나리오와 같은 성격의 여행 문장이다(감정 41건, 요청 종류·문제 코드 51건). 학습에는 쓰지 않았고, "
        "라벨은 작업 세션에서 부여했으며 사람 검수는 하지 않았다. 따라서 방향 확인용으로만 쓴다.",
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
        ("분할", "요청 종류", f"학습 {tr_n:,} / 검증 {va_n:,} / 시험 {te_n:,}건", "요청 종류 라벨 기준 층화(seed=7)"),
        ("분할", "문제 코드", f"학습 {jr_n:,} / 검증 {jv_n:,} / 시험 {jt_n:,}건", "문제 코드 라벨 기준 층화(seed=7), 요청 종류와 따로 분할"),
        ("품질", "교사 라벨 확정", f"{lab['labeled']:,}건 / {lab['input']:,}건({pct(lab['labeled'], lab['input'])})",
         f"Gemma 4 12B, 온도 0, 라벨 안내 {lab['guide']}"),
        ("품질", "교사 답 제외", f"{rejected}건(어휘 밖 {lab['invalid_label']}, 누락 {lab['missing_in_answer']})",
         f"추정으로 채우지 않고 제외, 한 건씩 다시 물어 {lab.get('recovered_by_single_pass', 0)}건 회수"),
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



#: ★감정 임계값 — 여행 문장 41건에서 고르지 않고 이 값으로 고정해 보고한다. 첫 모델 실험 뒤 정한 값이고
#:  같은 41건을 봤으므로 독립 평가가 아니라는 점을 문서에 적는다(코덱스 검수 2026-09-17 치명 1).
SENT_THRESHOLD = 0.9


def travel_at(metrics, threshold=SENT_THRESHOLD):
    rows = (metrics or {}).get("travel_eval", {}).get("by_threshold") or []
    return next((r for r in rows if abs(r["threshold"] - threshold) < 1e-9), None)


def _valid_acc_sentiment(m, baseline=False):
    if baseline:
        return (m.get("valid") or {}).get("accuracy")
    hist = [h for h in (m or {}).get("history") or [] if "valid_accuracy" in h]
    return hist[-1]["valid_accuracy"] if hist else None


def _valid_acc_labels(m):
    if (m or {}).get("teacher_agreement_valid"):
        return m["teacher_agreement_valid"]["accuracy"]
    hist = [h for h in (m or {}).get("history") or [] if "valid_accuracy" in h]
    return hist[-1]["valid_accuracy"] if hist else None


def _cand_sentiment(s):
    """감정 후보 — 기준선 + 인코더(실패도 줄로 남긴다). 선정은 검증 조각, 시험은 보고용."""
    sb = s["sent_base"]
    rows = [{"model": "TF-IDF + 로지스틱 회귀", "short": "TF-IDF", "kind": "Baseline", "metrics": sb,
             "valid": _valid_acc_sentiment(sb, baseline=True),
             "acc": sb["test"]["accuracy"], "ci": sb["test"]["accuracy_ci95"], "f1": sb["test"]["macro_f1"],
             "speed": None, "failed": None, "why": "해석 가능한 기준선, 낱말·글자 n-gram", "run": None}]
    for model_id, info in s["sent_all"].items():
        m = info["metrics"]
        rows.append({"model": model_id, "short": info["short"], "kind": "DL", "metrics": m, "why": info["why"], "run": None,
                     "valid": _valid_acc_sentiment(m) if m else None,
                     "acc": m["review_test"]["accuracy"] if m else None,
                     "ci": m["review_test"]["accuracy_ci95"] if m else None,
                     "f1": m["review_test"]["macro_f1"] if m else None,
                     "speed": ((m or {}).get("inference") or {}).get("sentences_per_second"),
                     "failed": None if m else (info["failed"] or "결과 없음")})
    return rows


LABEL_MODELS = (("tfidf", "TF-IDF"), ("skt/A.X-Encoder-base", "A.X-Encoder-base"),
                ("jhu-clsp/mmBERT-base", "mmBERT-base"), ("kakaobank/kf-deberta-base", "kf-deberta-base"),
                ("Qwen/Qwen3-Embedding-0.6B", "Qwen3-Embedding-0.6B"))


def _cand_labels(s, field):
    """요청 종류·문제 코드 후보 — 실행(실제 글 / 가중 조정 / 실제+합성)마다 줄로 둔다."""
    rows = []
    for key, label, data in s["intent_runs"]:
        for model_id, short in LABEL_MODELS:
            m = data.get(f"{field}__{model_id.replace('/', '__')}")
            failed = data.get("failed", {}).get((field, model_id))
            if m is None and failed is None:
                continue
            speed = next((h["inference"] for h in (m or {}).get("history") or [] if "inference" in h), {})
            t = (m or {}).get("teacher_agreement_test") or {}
            rows.append({"model": model_id, "short": short, "run": label, "run_key": key,
                         "kind": "Baseline" if model_id == "tfidf" else "DL", "metrics": m,
                         "valid": _valid_acc_labels(m), "acc": t.get("accuracy"), "ci": t.get("accuracy_ci95"),
                         "f1": t.get("macro_f1"), "speed": speed.get("sentences_per_second"), "failed": failed,
                         "train": (m or {}).get("train_real"), "synthetic": (m or {}).get("train_synthetic")})
    return rows


def choose(rows, score_name):
    """★선정 규칙 — 기준선을 포함한 모든 후보 중 **검증 조각** 점수가 가장 높은 것. 시험 조각은 선정에 쓰지 않는다.
    점수가 같으면 더 단순한 기준선, 인코더끼리 같으면 GPU 추론이 빠른 쪽.

    ☆2026-09-17 초안은 시험 조각으로 골랐다(평가 누수, 코덱스 검수 치명 1). 그 전에는 인코더끼리만 비교해
      기준선보다 낮은 A.X(문제 코드 0.327)가 뽑히기도 했다."""
    ok = [r for r in rows if r["valid"] is not None and not r["failed"]]
    if not ok:
        raise SystemExit("[멈춤] 검증 점수가 있는 후보가 없다")
    top = max(r["valid"] for r in ok)
    tied = [r for r in ok if abs(r["valid"] - top) < 1e-12]
    pick = next((r for r in tied if r["kind"] == "Baseline"), None) or max(tied, key=lambda r: r["speed"] or 0)
    pick["reason"] = f"검증 조각 {score_name} 최고({f4(pick['valid'])})"
    return pick


def result_text(r, score="정확도"):
    if r["failed"]:
        return f"실패: {str(r['failed'])[:80]}"
    parts = [f"검증 {f4(r['valid'])}" if r["valid"] is not None else "검증 기록 없음",
             f"시험 {score} {f4(r['acc'])} {ci(r['ci']) if r['ci'] else ''}".rstrip(), f"F1 {f4(r['f1'])}"]
    if r.get("speed"):
        parts.append(f"GPU 추론 {r['speed']:,.0f}문장/s")
    at = travel_at(r.get("metrics"))
    if at:
        parts.append(f"여행 3분류 F1 {at['macro_f1_3class']:.3f}(임계값 {SENT_THRESHOLD})")
    return ", ".join(parts)


def travel_note(rows, picked) -> str:
    scored = [(travel_at(r["metrics"])["macro_f1_3class"], r) for r in rows
              if r["kind"] == "DL" and travel_at(r.get("metrics"))]
    mine = travel_at(picked.get("metrics"))
    if not scored or not mine:
        return "여행 문장 조각의 3분류 결과가 없어 도메인 차이를 확인하지 못했다."
    top_f1, top = max(scored, key=lambda x: x[0])
    head = (f"임계값 {SENT_THRESHOLD}에서 여행 문장 3분류 macro F1은 선정 감정 모델({picked['short']})이 "
            f"{mine['macro_f1_3class']:.3f}였다(평가 표본 n=41). ")
    if top is picked:
        return head + "비교한 인코더 가운데 가장 높았으나 표본이 작아 방향 확인에 그친다."
    return head + (f"{top['short']}({top_f1:.3f})가 더 높아 리뷰 검증 결과와 방향이 달랐다. 41건은 소표본이라 선정 기준으로 쓰지 "
                   f"않았고, 여행 문장 라벨을 늘려 다시 비교하는 것을 다음 과제로 둔다.")


def env_line(s) -> str:
    t, c = s["env"]["train"], s["env"]["cpu_eval"]
    return (f"학습 PyTorch {t['torch']}(CUDA {t['cuda']}), Transformers {t['transformers']}, scikit-learn {t['scikit_learn']} / "
            f"추론 검증 PyTorch {c['torch']}, Transformers {c['transformers']}, scikit-learn {c['scikit_learn']}")


# ════════════════════════════════════════════════════════════════
# 2. 머신러닝 / 딥러닝 학습 결과서
# ════════════════════════════════════════════════════════════════
def build_training(s, fill_cover):
    sent, intent, issue = _cand_sentiment(s), _cand_labels(s, "intent"), _cand_labels(s, "issue_code")
    ps, pi, pj = choose(sent, "정확도"), choose(intent, "교사 일치도"), choose(issue, "교사 일치도")
    s["picked"] = {"sentiment": ps, "intent": pi, "issue_code": pj}
    load_picked_extras(s)
    sm = ps["metrics"]
    encoders = sorted({r["model"] for r in sent + intent + issue if r["kind"] == "DL" and not r["failed"]})
    fig = flow(FIG_DIR / "그림2_실험흐름.png", "학습과 평가 흐름", [
        ("학습", ["전처리 조각\n학습·검증·시험", "기준선\nTF-IDF + 로지스틱 회귀",
                 f"인코더 파인튜닝 {len(encoders)}종\nGPU, bfloat16", "에폭별 검증\n정확도 기록"]),
        ("선정·보고", ["검증 조각 점수로\n모델 선정", "시험 조각은 선정 뒤\n1회 보고", "부트스트랩 2,000회\n95% 신뢰구간",
                     "선정 모델을 제품\n어댑터로 CPU 측정"]),
    ])
    d = Document(template("[데이터 전처리] 머신러닝_딥러닝 학습 결과서.docx"))
    header(d, fill_cover)
    set_line(d, "목표", "Case 인라인 분류를 로컬 모델로 수행해 외부 LLM 호출과 지연을 줄이고, 확신이 낮으면 LLM에 넘기는 기준을 만든다")
    set_line(d, "문제 정의", "여행 고객 메시지 한 건으로 감정(긍정·부정, 확신이 낮으면 중립), 요청 종류 5종, 문제 코드 17종을 예측한다")
    set_line(d, "사용 프레임워크", "scikit-learn, PyTorch, Hugging Face Transformers, Ollama(교사 라벨)")

    picked_by = {}
    for task, r in (("감정", ps), ("요청 종류", pi), ("문제 코드", pj)):
        picked_by.setdefault(r["model"] if r["kind"] == "DL" else "tfidf", []).append(task)
    t3 = [("Baseline", "TF-IDF + 로지스틱 회귀", "해석 가능한 기준선, 낱말·글자 n-gram",
           f"리뷰 {s['sent_base']['train_size']:,}건, 사건제목 학습 조각",
           f"선정: {', '.join(picked_by['tfidf'])}" if picked_by.get("tfidf") else "CPU 학습")]
    for model_id, short, why in SENT_MODELS + (("Qwen/Qwen3-Embedding-0.6B", "Qwen3-Embedding-0.6B",
                                                  "다국어 임베딩 상위 계열, 큰 백본의 정확도 이득 확인"),):
        if model_id not in encoders:
            continue
        tasks = picked_by.get(model_id)
        t3.append(("DL(선정)" if tasks else "DL(비교)", model_id, why, "감정·요청 종류·문제 코드 같은 조각",
                   f"선정: {', '.join(tasks)}" if tasks else "비교"))
    t3.append(("교사", "Gemma 4 12B(Ollama)", "여행 라벨 부여(증류의 교사), 학습 대상 아님",
               f"사건제목 {s['label']['input']:,}건", "온도 0, 어휘 밖 답 제외"))
    fill(d.tables[3], t3)
    fill(d.tables[4], [
        ("Accuracy", "검증 조각 정답률(선정), 시험 조각 정답률(보고)", "기준선 이상", "시험은 부트스트랩 2,000회 95% 신뢰구간"),
        ("F1(macro)", "라벨별 F1 평균", "소수 라벨 누락 확인", "문제 코드 17종은 불균형이 큼"),
        ("교사 일치도", "Gemma 라벨과 예측의 일치율", "사람 정답 기준 정확도가 아님", "요청 종류·문제 코드"),
        ("추론 속도", "GPU 시험 조각 처리량, CPU 한 문장 지연", "점수가 같을 때만 참고", "선정 감정 모델만 CPU 측정"),
        ("여행 3분류 F1", f"여행 문장 41건(중립 포함), 임계값 {SENT_THRESHOLD}", "도메인 차이 방향 확인", "소표본, 선정에 쓰지 않음"),
    ])
    insert_after(d, "2.3 실험 파이프라인", [
        f"모든 모델은 같은 분할과 같은 seed(7)로 학습했다. 인코더는 {GPU}에서 bfloat16 자동 혼합정밀도로 학습했고, "
        f"선정 감정 모델의 CPU 지연은 {CPU}에서 제품 어댑터로 불러 측정했다.",
        "선정 규칙: 기준선을 포함한 후보 가운데 검증 조각 점수(감정은 정확도, 요청 종류·문제 코드는 교사 일치도)가 가장 높은 "
        "모델을 고른다. 시험 조각은 선정이 끝난 뒤 성능 보고에만 쓴다. GPU 처리량은 교사 라벨링용 LLM과 GPU를 나눠 쓰는 "
        "상태에서 잰 참고값이다.",
        f"감정 임계값 {SENT_THRESHOLD}는 첫 인코더 실험 뒤 정한 고정값이다. 같은 여행 문장 41건을 이미 확인한 뒤 정했으므로 "
        "여행 3분류 결과는 독립 평가가 아니라 방향 확인용이다.",
        ("img", fig, "그림 2. 학습과 평가 흐름", 12.0),
    ])
    def picked_name(r):
        return ("TF-IDF" if r["kind"] != "DL" else r["short"]) + (f"({r['run']})" if r.get("run") else "")
    set_line(d, "최종 선정 모델", f"감정 {picked_name(ps)}, 요청 종류 {picked_name(pi)}, 문제 코드 {picked_name(pj)}")
    overrides = next((m.get("overrides") for _, _, data in s["intent_runs"] for k, m in data.items()
                      if k != "failed" and isinstance(m, dict) and m.get("overrides")), None)
    fill(d.tables[5], [
        ("learning_rate", "2e-5(감정), 3e-5(요청·문제)", "고정", "인코더 파인튜닝에 흔히 쓰는 값", "인코더 전체", "OneCycle, warmup 10%"),
        ("batch_size", "감정 32, 요청·문제 32(첫 판)·16(조정판)", "고정", "공유 GPU 메모리 상한 7GB 안에서 가능한 값",
         "인코더 전체", "mmBERT 감정은 16"),
        ("epochs", "감정 2, 요청·문제 4(첫 판)·8(조정판)", "고정",
         f"선정 감정 모델 검증 정확도 {sm['history'][0]['valid_accuracy']:.4f}, {sm['history'][-1]['valid_accuracy']:.4f}",
         "인코더 전체", ""),
        ("max_len", "96 토큰", "고정", f"리뷰 길이 p95 {s['sent_prep']['char_length']['p95']}자", "인코더 전체", ""),
        ("class_weight", "빈도 역수 상한 20(첫 판), 제곱근 상한 5(조정판)", "2가지 비교",
         "첫 판에서 문제 코드 인코더가 다수 라벨을 놓침", "요청·문제 코드", "TF-IDF는 balanced"),
    ])
    t6, n = [], 0
    for task, rows, score in (("감정", sent, "정확도"), ("요청 종류", intent, "교사 일치도"), ("문제 코드", issue, "교사 일치도")):
        chosen = {"감정": ps, "요청 종류": pi, "문제 코드": pj}[task]
        for r in rows:
            n += 1
            setting = f"{task} {r['short']}" + (f"({r['run']})" if r.get("run") else "")
            t6.append((r["kind"], f"EXP-{n:02d}", setting, result_text(r, score) + (" (선정)" if r is chosen else "")))
    first = s.get("sent_first_run") or {}
    if (first.get("jhu-clsp/mmBERT-base") or {}).get("failed"):
        t6.append(("재실행", "mmBERT", "감정 mmBERT-base 배치 32", "GPU 메모리 상한 7GB 초과로 실패, 배치 16으로 다시 학습(위 결과)"))
    kf_first = first.get("kakaobank/kf-deberta-base") or {}
    if kf_first.get("review_accuracy"):
        t6.append(("재실행", "kf-deberta", "감정 kf-deberta-base 첫 실행(가중치 미저장)",
                   f"시험 정확도 {f4(kf_first['review_accuracy'])} {ci(kf_first['review_accuracy_ci95'])}, "
                   f"선정 후 가중치 저장을 위해 같은 설정으로 다시 학습(위 결과)"))
    prev = s.get("sent_prev")
    if prev:
        t6.append(("환경 비교", "A.X", f"감정 A.X, {GPU_PREV}(배치 64)",
                   f"시험 정확도 {f4(prev['review_test']['accuracy'])} {ci(prev['review_test']['accuracy_ci95'])}. "
                   "환경·배치가 달라 재현성 검증으로 보지 않는다"))
    t6.append(("추론", "CPU", f"감정 {ps['short']}, 제품 어댑터",
               f"한 문장 p50 {s['sent_cpu']['latency_single_ms']['p50']} ms, p95 {s['sent_cpu']['latency_single_ms']['p95']} ms"))
    fill(d.tables[6], t6)
    fill(d.tables[7], [("2026.09.17", CHANGER if fill_cover else "",
                        f"초안: 기준선·인코더 {len(encoders)}종 학습 결과와 검증 조각 기준 선정", "전체", "v1.0")])
    t_params, t_results = d.tables[5], d.tables[6]
    move_after(para_by_text(d, "그림 2.")._element, t_params)
    move_after(para_by_text(d, "최종 선정 모델")._element, t_results)
    vhist = [h for h in sm["history"] if "valid_accuracy" in h]
    tuning = []
    for field, name in (("issue_code", "문제 코드"), ("intent", "요청 종류")):
        first_ax = next((r for r in (intent if field == "intent" else issue)
                         if r["run_key"] == "p1_real_only" and r["model"] == "skt/A.X-Encoder-base" and r["valid"] is not None), None)
        tuned_ax = next((r for r in (intent if field == "intent" else issue)
                         if r["run_key"] == "p1b_real_tuned" and r["model"] == "skt/A.X-Encoder-base" and r["valid"] is not None), None)
        if first_ax and tuned_ax:
            tuning.append(f"{name} A.X 검증 {first_ax['valid']:.4f}에서 {tuned_ax['valid']:.4f}")
    insert_after(d, "3.2 과적합", [
        f"선정 감정 모델은 {len(vhist)}에폭 동안 검증 정확도가 하락하지 않았다({vhist[0]['valid_accuracy']:.4f}, "
        f"{vhist[-1]['valid_accuracy']:.4f}). "
        "다만 관측 구간이 짧아 과적합이 없다고 단정하지 않는다. 학습 스크립트(ml/train_gpu.py)는 weight decay 0.01과 기울기 절단 1.0을 쓴다.",
        "요청 종류·문제 코드의 첫 판(빈도 역수 가중 상한 20, 4에폭)에서 문제 코드 인코더가 다수 라벨을 거의 예측하지 않고 "
        "검증 점수가 기준선보다 크게 낮았다. 학습 손실이 계속 내려가던 점을 근거로 과소적합과 과한 가중을 원인으로 보고, "
        "제곱근 가중(상한 5)·8에폭·배치 16으로 조정했다" + (f"({', '.join(tuning)})." if tuning else "."),
        travel_note(sent, ps),
        "요청 종류·문제 코드는 교사 라벨의 오류가 그대로 학습되므로, 사람 검수 표본으로 교사 라벨의 정확도를 재는 것이 다음 과제다.",
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
    env_t = s["env"]["train"]
    enc = [r for r in (ps, pi, pj) if r["kind"] == "DL"]
    lin = [r for r in (ps, pi, pj) if r["kind"] != "DL"]
    fig_deps = flow(FIG_DIR / "그림3_학습데이터와의존라이브러리.png", "학습 데이터와 의존 라이브러리", [
        ("학습 데이터", [f"리뷰 {sm['train_size']:,}건\n(감정)", f"사건제목 교사 라벨\n{s['label']['labeled']:,}건",
                      f"합성 문장\n{s.get('synth_kept', 0):,}건(거름 통과)"]),
        ("학습 라이브러리", [f"PyTorch {env_t['torch'].split('+')[0]}\nTransformers {env_t['transformers']}",
                         f"scikit-learn {env_t['scikit_learn']}\nNumPy {env_t['numpy']}",
                         f"Ollama {env_t['ollama']}\n교사 {env_t['teacher_model']}"]),
        ("모델 파일", ["SafeTensors\n(인코더 가중치)", "joblib\n(TF-IDF 파이프라인)", "metrics.json\n(학습 설정·지표)"]),
    ])
    fig_infer = flow(FIG_DIR / "그림4_추론구조.png", "제품 안에서의 추론 구조(로컬 우선, 확신이 낮으면 LLM)", [
        ("입력", ["고객 메시지", "개인정보 마스킹\n(제품 모듈)", "토크나이저 또는\nTF-IDF 벡터화"]),
        ("모델", [f"감정\n{learner_name(ps)}", f"요청 종류\n{learner_name(pi)}", f"문제 코드\n{learner_name(pj)}"]),
        ("후처리", ["확신도 검사\n임계값 0.7", "낮으면 LLM에 위임\n충분하면 로컬 라벨", "분류 계약 검사\nCase 분류 이벤트"]),
    ])
    d = Document(template("[데이터 전처리] 학습한 ML_DL 모델.docx"))
    header(d, fill_cover)
    kinds = []
    if enc:
        kinds.append(f"파인튜닝한 인코더 분류기 {len(enc)}종({', '.join(sorted({r['short'] for r in enc}))})")
    if lin:
        kinds.append(f"TF-IDF 로지스틱 회귀 분류기 {len(lin)}종")
    set_line(d, "모델 유형", ", ".join(kinds) + " (과제별로 검증 조각에서 선정)")
    set_line(d, "담당 태스크", "Case 인라인 분류: 감정(긍정·부정·중립), 요청 종류 5종, 문제 코드 17종")
    set_line(d, "프레임워크 / 버전", env_line(s))
    fill(d.tables[3], [
        ("전처리", "정규화·마스킹", "NFKC, 반복 글자 축약, 개인정보 치환", "제품 마스킹 모듈", "학습·추론 공용"),
        *([("특징", "모델별 토크나이저", "하위 단어 분할, 최대 96토큰", "transformers", "모델 폴더에 함께 저장")] if enc else []),
        *([("특징", "TF-IDF 벡터라이저", "낱말 1~2·글자 2~4 n-gram", "scikit-learn", "Pipeline에 함께 저장")] if lin else []),
        *[(f"학습기 {i}", learner_name(r), task, learner_dep(r), note) for i, (r, task, note) in enumerate((
            (ps, "감정 2분류, 확률 출력", f"리뷰 {sm['train_size']:,}건"),
            (pi, "요청 종류 5분류", f"사건제목 학습 {pi['train']:,}건" + (f", 합성 {pi['synthetic']:,}건" if pi.get('synthetic') else "")),
            (pj, "문제 코드 17분류", f"사건제목 학습 {pj['train']:,}건" + (f", 합성 {pj['synthetic']:,}건" if pj.get('synthetic') else ""))),
            start=1)],
        ("후처리", "캐스케이드 제공자", "확신이 낮으면 LLM 위임, 감정은 중립 물러섬", "제품 분류 계약", "계약 검사 시험 4건 통과"),
    ])
    fill(d.tables[4], [
        ("text", "str", "메시지 1건", "마스킹된 고객 입력"),
        *([("input_ids", "int64", "[1, 최대 96]", "인코더 토크나이저 출력")] if enc else []),
        *([("features", "sparse float", "[1, 어휘 수]", "TF-IDF 희소 벡터")] if lin else []),
        ("score / probability", "float32", "[1, 라벨 수]", "인코더 logits 또는 TF-IDF 분류 확률(감정 2, 요청 종류 5, 문제 코드 17)"),
        ("label, confidence", "str, float", "1개, 0~1", "제품 어휘 라벨과 최대 확률(어휘 밖이면 분류 실패로 처리)"),
    ])
    insert_after(d, "2.3 학습 데이터", [
        "감정은 쇼핑 리뷰로, 요청 종류·문제 코드는 교사 라벨을 붙인 사건제목(조정판·전체판은 거름을 통과한 합성 문장 포함)으로 "
        "학습했다. 학습과 추론 검증에 쓴 라이브러리 버전은 실행 환경에서 직접 기록했다.",
        ("img", fig_deps, "그림 3. 학습 데이터와 의존 라이브러리", 12.5),
    ])
    set_line(d, "모델 파일", "sentiment, intent, issue_code 폴더(인코더는 model.safetensors·config.json·토크나이저, "
                            "TF-IDF는 model.joblib, 공통 metrics.json), 감정 기준선 tfidf_baseline(model.joblib). "
                            f"제출 위치: 팀 공유 드라이브 {DRIVE_URL}")
    after = insert_after(d, "모델 파일", [
        f"CPU 측정 장치는 {CPU}이고, 모델은 제품 어댑터(app/infrastructure/ml)로 불러 측정했다.",
        ("img", fig_infer, "그림 4. 학습한 모델이 제품 분류 흐름에 들어가는 구조", 12.5),
    ])
    move_after(after, d.tables[5])
    lat, batch = cpu["latency_single_ms"], cpu["batch32_throughput"]
    fill(d.tables[5], [
        (f"크기({ps['short']})", str(s["size_mib"]) if s["size_mib"] else "기록 없음", "MiB", "model.safetensors", "목표 미설정",
         "토크나이저 파일 별도"),
        ("적재 시간", f"{cpu['load_seconds']}", "s", "CPU 첫 호출 1회", "목표 미설정", "이후 호출은 적재된 모델 재사용"),
        ("추론 지연 p50", f"{lat['p50']}", "ms", f"CPU 한 문장 {lat['n']}회", "목표 미설정", "제품 어댑터 경유"),
        ("추론 지연 p95", f"{lat['p95']}", "ms", f"CPU 한 문장 {lat['n']}회", "목표 미설정", "제품 어댑터 경유"),
        ("CPU 배치 처리량", f"{batch['sentences_per_second']}", "문장/s", f"배치 32, {batch['sentences']:,}문장", "목표 미설정", ""),
    ])
    def perf(r, task):
        if r["kind"] != "DL" and task == "감정":
            return f"{f4(r['acc'])}, 95% 신뢰구간 {ci(r['ci'])}"
        return f"{f4(r['acc'])}" + (f", 95% 신뢰구간 {ci(r['ci'])}" if r.get("ci") else "") + f", macro F1 {f4(r['f1'])}"
    fill(d.tables[6], [
        ("성능", "감정 시험 정확도", perf(ps, "감정"),
         f"리뷰 시험 {sm['test_size']:,}건, 선정 사유: {ps['reason']}"),
        ("성능", "요청 종류 시험 교사 일치도", perf(pi, "요청"),
         f"사건제목 시험 {pi['metrics']['teacher_agreement_test']['n']:,}건, Gemma 라벨 기준, 선정 사유: {pi['reason']}"),
        ("성능", "문제 코드 시험 교사 일치도", perf(pj, "문제"),
         f"사건제목 시험 {pj['metrics']['teacher_agreement_test']['n']:,}건, Gemma 라벨 기준, 선정 사유: {pj['reason']}"),
        ("저장", "형식과 버저닝", "인코더 SafeTensors, TF-IDF joblib, 모델 폴더별 metrics.json",
         "인코더 가중치는 SafeTensors로, TF-IDF 파이프라인은 joblib으로 로딩한다"),
        ("로딩", "호출 코드", "LocalLabelModel(model_dir).predict(text)",
         f"감정은 LocalSentiment(model_dir, threshold={SENT_THRESHOLD})"),
        ("추론", "캐스케이드", "확신도 0.7 미만은 LLM에 위임", "모르면 지어내지 않고 위임 여부를 기록, 분류 계약 검사 통과"),
        ("한계", "도메인 이동",
         (f"여행 3분류 F1 {travel_at(sm)['macro_f1_3class']:.3f}(임계값 {SENT_THRESHOLD}, n=41)" if travel_at(sm) else "여행 3분류 결과 없음"),
         "리뷰로 학습해 여행 문장의 중립을 직접 내지 못함, 여행 문장 라벨 확충 후 재학습"),
        ("한계", "교사 라벨 의존", "요청 종류·문제 코드 점수는 Gemma 라벨과의 일치도",
         "사람 검수 표본이 없어 교사 라벨의 정확도를 측정하지 못함"),
        ("한계", "심각도 미지원", "severity 라벨 학습 데이터 없음", "현재 LLM 값을 사용하며, 규칙으로 채울지는 후속 정책 확정이 필요함"),
        ("연계", "Team 라우팅", "문제 코드 접두가 case_type, 요청 종류가 intent", "두 축으로 Activity·Dining·Mobility 선택"),
    ])
    desc = []
    if enc:
        desc.append(f"인코더 {len(enc)}종")
    if lin:
        desc.append(f"TF-IDF 분류기 {len(lin)}종")
    fill(d.tables[7], [("2026.09.17", CHANGER if fill_cover else "",
                        f"초안: 선정 모델 3종({', '.join(desc)})의 구조·저장·추론", "전체", "v1.0")])
    return save(d, "[데이터 전처리] 학습한 ML_DL 모델_3차_여행.docx")



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fill-cover", action="store_true", help="표지·변경자 채움(팀장 확인 후)")
    parser.add_argument("--pick-only", action="store_true", help="선정 모델만 계산해 출력")
    args = parser.parse_args()
    s = load()
    if args.pick_only:
        picks = {"sentiment": choose(_cand_sentiment(s), "정확도"), "intent": choose(_cand_labels(s, "intent"), "교사 일치도"),
                 "issue_code": choose(_cand_labels(s, "issue_code"), "교사 일치도")}
        print(json.dumps({k: {"model": v["model"], "run": v.get("run"), "valid": v["valid"], "test": v["acc"], "reason": v["reason"]}
                          for k, v in picks.items()}, ensure_ascii=False, indent=2))
        return
    outs = [build_preprocess(s, args.fill_cover), build_training(s, args.fill_cover), build_model(s, args.fill_cover)]
    print("\n생성 완료:", *[o.name for o in outs], sep="\n  ")


if __name__ == "__main__":
    main()

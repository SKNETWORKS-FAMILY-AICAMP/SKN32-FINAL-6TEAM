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

sys.dont_write_bytecode = True
_temp_root = Path(os.environ.get("ACOP_DOC_OUT") or Path(__file__).resolve().parent.parent / "w4" / "데이터전처리_여행").parent / "_tmp"
_temp_root.mkdir(parents=True, exist_ok=True)
os.environ["TEMP"] = os.environ["TMP"] = str(_temp_root)
os.environ["MPLCONFIGDIR"] = str(_temp_root / "matplotlib")
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.text.paragraph import Paragraph

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
FORMS = Path(os.environ.get("ACOP_FORMS_DIR") or HERE.parent)
WORKSPACE = FORMS.parents[1]
ML = Path(os.environ.get("ACOP_ML_DIR") or WORKSPACE / "datasets" / "ml")          # 시험 실행용으로 바꿀 수 있다
OUT_DIR = Path(os.environ.get("ACOP_DOC_OUT") or FORMS / "w4" / "데이터전처리_여행")
FIG_DIR = OUT_DIR / "그림"
sys.path.insert(0, str(FORMS / "_build"))
from docxfill import check  # noqa: E402  금지 문자 검사(줄표·화살표·별표 등)

COVER = "SK 네트웍스 Family AI 32기: 6팀"
SUBMIT_DATE = "2026. 9. 28."
REPO_URL = "https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM"
AUTHORS = "김지혜, 서유현, 송채영, 정세환, 최상욱, 최연우"
CHANGER = "전체"
DRIVE_URL = "https://drive.google.com/drive/folders/1nMDeAqeSsLqeNoJg_N_8xf5s8wyC06ly"
GPU = "NVIDIA RTX 5090 32GB 공유 GPU 서버(학습 프로세스당 GPU 메모리 7GB 상한)"
GPU_PREV = "NVIDIA RTX 4070 SUPER 12GB"
SENT_MODELS = (("skt/A.X-Encoder-base", "A.X-Encoder-base", "한국어 전용 ModernBERT 계열 인코더 후보"),
               ("jhu-clsp/mmBERT-base", "mmBERT-base", "다국어 ModernBERT 계열 인코더 후보"),
               ("kakaobank/kf-deberta-base", "kf-deberta-base", "한국어 DeBERTa 계열 인코더 후보"))
CPU = "Intel Core i5-1135G7 노트북(torch 4스레드)"

#: 양식 예시가 남으면 안 되는 문구(커머스판 검사 목록에서 **우리 실제 내용과 겹치지 않는 것만**).
TEMPLATE_LEFTOVERS = ("BERT-base-ko", "XGBoost", "8,000건", "2026.04.11", "2026.04.13", "MLflow",
                      "xgb_classifier", "sbert_embed", "random_state=42", "_____팀", "27기", "00기",
                      "kiwipiepy", "LangChain", "사내 업무 문서", "T4 1건", "Back-translation")
#: 공개 문서에 들어가면 안 되는 식별자 — 원문 문자열로 적지 않는다.
PRIVATE_MARKERS = ("C:\\", "C:/", "E:/", "F:/", "localhost", "127.0.0.1", "".join(map(chr, (120, 54, 48, 48))), "".join(map(chr, (89, 101, 111, 110))),
                   "사실표", "playdata", "F:\\", "E:\\", "C:\\Users", "_work", "ssh ")


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
            "short": "Qwen3-Embedding-0.6B", "why": "다국어 임베딩 모델(0.6B), 큰 백본 비교 후보", "metrics": qwen,
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
    # ★선정된 kf-deberta(요청 종류·문제 코드)는 가중치를 저장하려고 같은 설정으로 다시 학습했다. 문서의 수치는 저장한 모델과
    #   맞아야 하므로 전체판의 kf-deberta 줄을 저장판 결과로 바꾸고, 첫 실행 결과는 재실행 기록으로 남긴다.
    saved = ML / "intent_ko" / "p3_kf_saved"
    s["kf_label_first_run"] = {}
    for key, label, data in s["intent_runs"]:
        if key != "p3_full":
            continue
        for field in ("intent", "issue_code"):
            name = f"{field}__kakaobank__kf-deberta-base"
            m = optional(saved / name / "metrics.json")
            if m and name in data:
                s["kf_label_first_run"][field] = data[name]
                data[name] = m
    return s


def load_picked_extras(s):
    """선정된 감정 모델의 CPU 평가와 가중치 크기 — 선정 뒤에 읽는다."""
    folder = ML / "sentiment_ko" / ("sota" if "Qwen" not in s["picked"]["sentiment"]["model"] else "qwen3")         / s["picked"]["sentiment"]["model"].replace("/", "__")
    s["sent_cpu"] = need(folder / "cpu_eval.json")
    weights = folder / "model.safetensors"
    s["size_mib"] = round(weights.stat().st_size / 1024 / 1024) if weights.exists() else None
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if weights.exists():   # ★크기 근거를 파일로 남긴다(코덱스 검수 중요 9)
        (OUT_DIR / "model_files.json").write_text(json.dumps(
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
        cant = trpr.find(qn("w:cantSplit"))
        if cant is None:
            trpr.append(OxmlElement("w:cantSplit"))
        elif cant.get(qn("w:val")) in ("0", "false"):     # 양식이 끈 값을 남겨 두면 행이 쪼개진다
            cant.attrib.pop(qn("w:val"))
        if index == 0:
            if trpr.find(qn("w:tblHeader")) is None:
                trpr.append(OxmlElement("w:tblHeader"))
            for cell in row.cells:
                for para in cell.paragraphs:
                    para.paragraph_format.keep_with_next = True


def add_strategy(doc, tbl, text: str):
    """변경 이력 표 뒤에 적용 전략 문단을 붙인다. ★문단만 다음 쪽에 홀로 넘어갔다(2026-09-17 렌더링) —
    표의 모든 행을 다음 요소와 붙여 제목·표·문단이 한 덩어리로 움직이게 한다."""
    for row in tbl.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                para.paragraph_format.keep_with_next = True
    prev = tbl._tbl.getprevious()
    if prev is not None and prev.tag == qn("w:p"):          # 절 제목도 표와 붙인다
        Paragraph(prev, tbl._parent).paragraph_format.keep_with_next = True
    insert_after(doc, tbl._tbl, [text])


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


def josa_eun(word: str) -> str:
    """받침이 있으면 「은」, 없으면 「는」을 붙인다."""
    last = word[-1]
    has_final = "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 != 0
    return word + ("은" if has_final else "는")


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
    revise_v4(doc, name)
    flow_pages(doc)
    verify(doc, name)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / name
    check(all_text(doc), name)
    doc.save(out)
    reopened = Document(out)
    check(all_text(reopened), name)
    verify(reopened, name)
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
    ratios = sp['split_label_ratio']
    label_ratio = f"{ratios['train']['negative']:.2f}"
    if not all(f"{v:.2f}" == label_ratio for part in ratios.values() for v in part.values()):
        raise SystemExit('감정 분할의 라벨 비율을 다시 확인해야 한다')
    total = sum(sp['split_sizes'].values())
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
                            "Ollama Gemma 4 12B(교사 라벨), python-docx(docx), openpyxl(xlsx), PyMuPDF(fitz, PDF), "
                            "Pillow(사진), Ollama gemma4:12b(사진 받아쓰기·남은 줄 원문 인용, 온도 0·생각 끔), 관광공사·카카오 장소 조회 API")
    insert_after(d, "2.1 데이터 출처 및 현황", [
        f"감정 데이터는 네이버쇼핑 리뷰 공개 말뭉치(Public Domain, 수집 보고서에서 라이선스 확인) {sp['read']:,}건이다. 별점 1·2점은 부정, 4·5점은 긍정으로 "
        f"라벨이 붙어 있고 원 말뭉치에 3점(중립)은 없다. 수집 단계에서 원문 중복 92건을 뺀 판을 입력으로 썼다.",
        f"요청 종류·문제 코드 데이터는 공정거래위원회 소비자상담 공개 데이터 2종(온라인 상거래, 지역별) {cnt['rows_read']:,}행에서 "
        f"항공·해외여행·숙박·공연·외식·철도·버스 등 여행 서비스 {len(pool['travel_items_allowlist'])}개 품목을 허용 목록으로 적용했고, "
        f"실제로 데이터가 있던 품목은 {len(pool['per_item'])}개였다"
        f"({josa_eun(', '.join(sorted(set(pool['travel_items_allowlist']) - set(pool['per_item']))))} 해당 데이터 0건). 사용한 공정위 "
        f"공개 데이터에는 제품 라벨 어휘(요청 종류 5종, 문제 코드 17종)가 없어 교사 모델(Gemma 4 12B)로 라벨을 붙였다.",
        "평가 전용 데이터는 팀 확정 시나리오와 같은 성격의 여행 문장이다(감정 41건, 요청 종류·문제 코드 51건). 학습에는 쓰지 않았고, "
        "라벨은 작업 세션에서 부여했으며 사람 검수는 하지 않았다. 따라서 방향 확인용으로만 쓴다.",
    ])
    fill(d.tables[3], [
        ("형식 불일치", "사건제목 원천", "CP949 인코딩, 칸 이름이 「품목명(ITEM_NAME)」 형태",
         "인코딩 지정, 칸 이름 포함 검사로 열 선택", "칸을 못 찾으면 파일 단위 실패로 기록(실패 파일 0개)"),
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
        f"세 조각의 부정·긍정 비율이 모두 {label_ratio}이다(소수 둘째 자리 반올림). 요청 종류는 학습 {tr_n:,}건, 검증 {va_n:,}건, 시험 {te_n:,}건이며 "
        f"시험 조각은 실제 사건제목으로만 구성한다(합성 문장 제외).",
    ])
    fill(d.tables[5], [
        ("text(리뷰)", "TEXT", "빈 문자열 행 제거(0건)", "정규화 후 SHA1", "2~300자 밖 제거(0건)", "감정 모델 입력"),
        ("label(감정)", "CATEGORY", "어휘 밖 행 제거(0건)", "해당 없음", "원 말뭉치에 3점 없음", "positive, negative"),
        ("text(사건제목)", "TEXT", "칸 부족 행 제거", "사건번호, 문장 해시", "8~150자 밖 제거", "요청 종류·문제 코드 입력"),
        ("intent", "CATEGORY", f"교사 답 누락 {lab['missing_in_answer']}건 제외", "해당 없음",
         f"어휘 밖 답 {lab['invalid_label']}건 제외", "5종, 교사 라벨"),
        ("issue_code", "CATEGORY", "intent 와 같은 행 기준", "해당 없음", "가까운 코드로 고쳐 넣지 않음", "17종, 후속 라우팅 입력"),
    ])
    fill(d.tables[6], [
        ("분할", "감정 학습", f"{pct(sp['split_sizes']['train'], total)} ({sp['split_sizes']['train']:,} / {total:,}건)", f"층화 추출(seed=7), 라벨 비율 {label_ratio}"),
        ("분할", "감정 검증", f"{pct(sp['split_sizes']['valid'], total)} ({sp['split_sizes']['valid']:,} / {total:,}건)", "에폭별 검증 정확도 기록"),
        ("분할", "감정 시험", f"{pct(sp['split_sizes']['test'], total)} ({sp['split_sizes']['test']:,} / {total:,}건)", "최종 평가 전용, 학습과 격리"),
        ("분할", "요청 종류", f"학습 {tr_n:,} / 검증 {va_n:,} / 시험 {te_n:,}건", "요청 종류 라벨 기준 층화(seed=7)"),
        ("분할", "문제 코드", f"학습 {jr_n:,} / 검증 {jv_n:,} / 시험 {jt_n:,}건", "문제 코드 라벨 기준 층화(seed=7), 요청 종류와 따로 분할"),
        ("품질", "교사 라벨 확정", f"{lab['labeled']:,}건 / {lab['input']:,}건({pct(lab['labeled'], lab['input'])})",
         f"Gemma 4 12B, 온도 0, 라벨 안내 {lab['guide']}"),
        ("품질", "교사 답 제외", f"{rejected}건(어휘 밖 {lab['invalid_label']}, 누락 {lab['missing_in_answer']})",
         f"추정으로 채우지 않고 제외, 단건 재요청으로 {lab.get('recovered_by_single_pass', 0)}건 회수"),
        ("품질", "민감정보 마스킹", f"리뷰 {pii['sentiment_reviews']['replacements_total']}건, "
                               f"사건제목 {pii['travel_complaint_titles']['replacements_total']}건 치환",
         "제품 마스킹 규칙에 주민번호·휴대폰·계좌 형식 추가, 적용 순서대로 집계"),
        ("품질", "산술 검사", "읽은 건수 = 제거 합계 + 남은 건수", "두 데이터 모두 일치, 불일치 시 실행 실패"),
        ("후속 활용", "ML/DL 학습", "JSONL(text, label)", "TF-IDF 기준선과 인코더 파인튜닝의 공통 입력"),
        ("후속 활용", "평가 전용 조각", "여행 문장 41건, 51건", "학습 미사용, 도메인 차이 확인"),
        ("후속 활용 / 재현성", "재현 명령과 기록", "python -m ml.preprocess, python -m ml.build_intent_pool",
         "seed, 입력 경로, 단계별 제거 건수를 통계 JSON으로 함께 저장"),
    ])
    fill(d.tables[7], [("2026.09.17", CHANGER if fill_cover else "", "여행 분류 모델 학습 데이터 전처리 작성", "전체", "v1.0")])
    add_strategy(d, d.tables[7], "적용 전략: 전처리 규칙이나 원천 데이터가 바뀌면 판 번호를 올리고 같은 명령과 seed(7)로 "
                                        "분할을 다시 만든 뒤, 통계 JSON을 이전 판과 비교하고 모델을 다시 학습한다.")
    # ── 제목과 표를 맞춘다: 2.2 에 품질 이슈·필드 처리 표, 2.3 에 처리 단계 표와 흐름도
    t_issue, t_steps, t_fields = d.tables[3], d.tables[4], d.tables[5]
    after = move_after(para_by_text(d, "2.2 품질 이슈 진단")._element, t_issue)
    after = insert_after(d, after, ["위 이슈를 필드별 처리 기준으로 정리하면 다음과 같다. 교사 라벨의 누락·어휘 밖 답은 "
                                    "가장 가까운 코드로 고쳐 넣지 않고 제외했다."])
    move_after(after, t_fields)
    after = move_after(para_by_text(d, "2.3 전처리 파이프라인 흐름도")._element, t_steps)
    insert_after(d, after, [("img", fig, "그림 1. 두 학습 데이터의 전처리 흐름(건수는 실행 통계 기준)", 14.0)])
    return save(d, "[데이터 전처리] 데이터 전처리 결과서_4차_여행.docx")



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
            if model_id == "tfidf" and m and rows[-1]["valid"] is None:
                # ★회수 스크립트가 원격 지표로 덮으면 재계산한 검증 점수가 사라진다(2026-09-17 실제로 그랬다).
                raise SystemExit(f"[멈춤] {key}/{field} TF-IDF 검증 점수가 없다 — python -m ml.rescore_tfidf_valid 를 먼저 돌린다")
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
                     "선정 모델을 시험\n어댑터로 CPU 측정"]),
    ])
    d = Document(template("[데이터 전처리] 머신러닝_딥러닝 학습 결과서.docx"))
    header(d, fill_cover)
    set_line(d, "목표", "Case 인라인 분류를 로컬 모델로 수행해 외부 LLM 호출과 지연을 줄이고, 확신이 낮으면 LLM에 넘기는 기준을 만든다")
    set_line(d, "문제 정의", f"여행 고객 메시지 한 건에 대해 감정은 긍정·부정 2분류 확률을 예측하고 최대 확률이 {SENT_THRESHOLD} 미만이면 "
                              "후처리에서 중립으로 처리한다. 요청 종류는 5종, 문제 코드는 17종을 예측한다")
    set_line(d, "사용 프레임워크", "scikit-learn, PyTorch, Hugging Face Transformers, Ollama(교사 라벨)")

    picked_by = {}
    for task, r in (("감정", ps), ("요청 종류", pi), ("문제 코드", pj)):
        picked_by.setdefault(r["model"] if r["kind"] == "DL" else "tfidf", []).append(task)
    t3 = [("Baseline", "TF-IDF + 로지스틱 회귀", "해석 가능한 기준선, 낱말·글자 n-gram",
           f"리뷰 {s['sent_base']['train_size']:,}건, 사건제목 학습 조각",
           f"선정: {', '.join(picked_by['tfidf'])}" if picked_by.get("tfidf") else "CPU 학습")]
    for model_id, short, why in SENT_MODELS + (("Qwen/Qwen3-Embedding-0.6B", "Qwen3-Embedding-0.6B",
                                                  "다국어 임베딩 모델(0.6B), 큰 백본 비교 후보"),):
        if model_id not in encoders:
            continue
        tasks = picked_by.get(model_id)
        t3.append(("DL(선정)" if tasks else "DL(비교)", model_id, why, ("요청 종류·문제 코드의 실제+합성 학습 조각" if model_id.startswith("Qwen/") and not (s["sent_all"].get(model_id) or {}).get("metrics")
                    else "감정·요청 종류·문제 코드 같은 조각"),
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
        "같은 과제·같은 실험판의 후보 모델은 동일한 검증·시험 조각과 seed(7)를 사용했다. 전체판은 실제 글 학습 조각에 "
        f"합성 문장을 더했다. 인코더는 {GPU}에서 bfloat16 자동 혼합정밀도로 학습했고(ml/train_gpu.py, ml/train_labels_gpu.py), "
        f"선정 감정 모델의 CPU 지연은 {CPU}에서 로컬 시험 어댑터로 불러 측정했다.",
        "선정 규칙: 기준선을 포함한 후보 가운데 검증 조각 점수(감정은 정확도, 요청 종류·문제 코드는 교사 일치도)가 가장 높은 "
        "모델을 고른다. 인코더의 검증 점수는 저장한 모델인 마지막 에폭 기준이며, 에폭 중간의 최고점 체크포인트는 저장하지 않았다. "
        "점수가 같으면 더 단순한 기준선을 택한다. 시험 조각은 선정이 끝난 뒤 성능 보고에만 쓴다. GPU 처리량은 실행 결과 JSON에 "
        "기록된 참고값이며, 같은 GPU를 쓰던 다른 프로세스의 동시 실행 조건은 통제하지 않았다.",
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
        ("learning_rate", "2e-5(감정), 3e-5(요청·문제)", "고정", "결과 JSON의 lr 기록", "인코더 전체",
         "OneCycle(warmup 10%), ml/train_gpu.py·ml/train_labels_gpu.py 고정값"),
        ("batch_size", "감정 32, 요청·문제 32(첫 판)·16(조정판)", "고정", "공유 GPU 메모리 상한 7GB 안에서 가능한 값",
         "인코더 전체", "mmBERT 감정은 16"),
        ("epochs", "감정 2, 요청·문제 4(첫 판)·8(조정판)", "고정",
         f"선정 감정 모델 검증 정확도 {sm['history'][0]['valid_accuracy']:.4f}, {sm['history'][-1]['valid_accuracy']:.4f}",
         "인코더 전체", ""),
        ("max_len", "96 토큰", "고정", "결과 JSON의 max_len 기록", "인코더 전체", ""),
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
    for field, name in (("intent", "요청 종류"), ("issue_code", "문제 코드")):
        f0 = s.get("kf_label_first_run", {}).get(field)
        if f0:
            t0 = f0["teacher_agreement_test"]
            t6.append(("재실행", "kf-deberta", f"{name} kf-deberta-base 첫 실행(가중치 미저장)",
                       f"검증 {f4(_valid_acc_labels(f0))}, 시험 교사 일치도 {f4(t0['accuracy'])}, "
                       "선정 후 가중치 저장을 위해 같은 설정으로 다시 학습(위 결과)"))
    prev = s.get("sent_prev")
    if prev:
        t6.append(("환경 비교", "A.X", f"감정 A.X, {GPU_PREV}(배치 64)",
                   f"시험 정확도 {f4(prev['review_test']['accuracy'])} {ci(prev['review_test']['accuracy_ci95'])}. "
                   "환경·배치가 달라 재현성 검증으로 보지 않는다"))
    t6.append(("추론", "CPU", f"감정 {ps['short']}, 로컬 시험 어댑터",
               f"한 문장 p50 {s['sent_cpu']['latency_single_ms']['p50']} ms, p95 {s['sent_cpu']['latency_single_ms']['p95']} ms"))
    fill(d.tables[6], t6)
    fill(d.tables[7], [("2026.09.17", CHANGER if fill_cover else "",
                        f"기준선·인코더 {len(encoders)}종 학습 결과와 검증 조각 기준 선정 작성", "전체", "v1.0")])
    add_strategy(d, d.tables[7], "적용 전략: 새 후보 모델은 같은 검증 조각과 같은 선정 규칙으로 비교하고, 선정 모델이 "
                                        "바뀔 때만 판 번호를 올린다. 시험 조각 점수는 선정에 쓰지 않는다.")
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
        "다만 관측 구간이 짧아 과적합이 없다고 단정하지 않는다. weight decay 0.01과 기울기 절단 1.0은 학습 스크립트(ml/train_gpu.py, "
        "ml/train_labels_gpu.py)의 고정값이다.",
        "요청 종류·문제 코드의 첫 판(빈도 역수 가중 상한 20, 4에폭)에서 문제 코드 인코더가 다수 라벨을 거의 예측하지 않고 "
        "검증 점수가 기준선보다 크게 낮았다. 학습 손실이 계속 내려가던 점을 근거로 과소적합과 과한 가중을 원인으로 보고, "
        "제곱근 가중(상한 5)·8에폭·배치 16으로 조정했다" + (f"({', '.join(tuning)})." if tuning else "."),
        travel_note(sent, ps),
        "요청 종류·문제 코드는 교사 라벨의 오류가 그대로 학습되므로, 사람 검수 표본으로 교사 라벨의 정확도를 재는 것이 다음 과제다.",
    ])
    return save(d, "[데이터 전처리] 머신러닝_딥러닝 학습 결과서_4차_여행.docx")


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
    fig_infer = flow(FIG_DIR / "그림4_추론구조.png", "제품 경로와 로컬 모델 시험 경로", [
        ("제품 분류", ["고객 메시지", "Gemma 4 12B\n없으면 OpenAI", "제품 분류·후속 라우팅"]),
        ("로컬 모델 시험", ["제출 kf-deberta-base\n감정·요청 종류·문제 코드", "로컬 어댑터\n계약 시험·CPU 측정", "제품 분류 조립에\n연결되지 않음"]),
    ])
    d = Document(template("[데이터 전처리] 학습한 ML_DL 모델.docx"))
    header(d, fill_cover)
    kinds = []
    if enc:
        kinds.append(f"파인튜닝한 인코더 분류기 {len(enc)}종({', '.join(sorted({r['short'] for r in enc}))})")
    if lin:
        kinds.append(f"TF-IDF 로지스틱 회귀 분류기 {len(lin)}종")
    set_line(d, "모델 유형", ", ".join(kinds) + " (과제별로 검증 조각에서 선정)")
    set_line(d, "담당 태스크", f"로컬 분류 시험: 감정 긍정·부정 2분류(최대 확률 {SENT_THRESHOLD} 미만은 후처리로 중립), "
                               "요청 종류 5종, 문제 코드 17종")
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
        ("시험 어댑터", "로컬 분류 어댑터", "로컬 모델 호출과 계약 시험까지 구현했다", "tests/unit/ml", "제품 분류 조립에는 연결되지 않았다"),
    ])
    fill(d.tables[4], [
        ("text", "str", "메시지 1건", "마스킹된 고객 입력"),
        *([("input_ids", "int64", "[1, 최대 96]", "인코더 토크나이저 출력")] if enc else []),
        *([("features", "sparse float", "[1, 어휘 수]", "TF-IDF 희소 벡터")] if lin else []),
        ("score / probability", "float32", "[1, 라벨 수]", "인코더 logits 또는 TF-IDF 분류 확률(감정 2, 요청 종류 5, 문제 코드 17)"),
        ("label, confidence", "str, float", "1개, 0~1", "제품 어휘 라벨과 최대 확률(어휘 밖이면 분류 실패로 처리)"),
    ])
    insert_after(d, "2.3 학습 데이터", [
        "감정은 쇼핑 리뷰로, 요청 종류·문제 코드는 교사 라벨을 붙인 사건제목(조정판·전체판은 일관성 필터를 통과한 합성 문장 포함)으로 "
        "학습했다. 학습과 추론 검증에 쓴 라이브러리 버전은 실행 환경에서 직접 기록했다.",
        ("img", fig_deps, "그림 3. 학습 데이터와 의존 라이브러리", 12.5),
    ])
    set_line(d, "모델 파일", "sentiment, intent, issue_code 폴더(인코더는 model.safetensors·config.json·토크나이저, "
                            "TF-IDF는 model.joblib, 공통 metrics.json), 감정 기준선 tfidf_baseline(model.joblib). "
                            f"제출 위치: 팀 공유 드라이브 {DRIVE_URL}")
    after = insert_after(d, "모델 파일", [
        f"CPU 측정 장치는 {CPU}이고, 모델은 로컬 시험 어댑터(app/infrastructure/ml)로 불러 측정했다.",
        ("img", fig_infer, "그림 4. 제품 LLM 분류와 미연결 로컬 모델의 시험 경로", 10.5),
    ])
    move_after(after, d.tables[5])
    lat, batch = cpu["latency_single_ms"], cpu["batch32_throughput"]
    fill(d.tables[5], [
        (f"크기({ps['short']})", str(s["size_mib"]) if s["size_mib"] else "기록 없음", "MiB", "model.safetensors", "목표 미설정",
         "토크나이저 파일 별도"),
        ("적재 시간", f"{cpu['load_seconds']}", "s", "CPU 첫 호출 1회", "목표 미설정", "이후 호출은 적재된 모델 재사용"),
        ("추론 지연 p50", f"{lat['p50']}", "ms", f"CPU 한 문장 {lat['n']}회", "목표 미설정", "로컬 시험 어댑터 경유"),
        ("추론 지연 p95", f"{lat['p95']}", "ms", f"CPU 한 문장 {lat['n']}회", "목표 미설정", "로컬 시험 어댑터 경유"),
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
        ("제품 추론", "LLM 분류", "Gemma 4 12B(Ollama), 없으면 OpenAI", "app/composition.py의 build_classifier는 로컬 모델을 연결하지 않는다"),
        ("한계", "도메인 이동",
         (f"여행 3분류 F1 {travel_at(sm)['macro_f1_3class']:.3f}(임계값 {SENT_THRESHOLD}, n=41)" if travel_at(sm) else "여행 3분류 결과 없음"),
         "리뷰로 학습해 여행 문장의 중립을 직접 내지 못함, 여행 문장 라벨 확충 후 재학습"),
        ("한계", "교사 라벨 의존", "요청 종류·문제 코드 점수는 Gemma 라벨과의 일치도",
         "사람 검수 표본이 없어 교사 라벨의 정확도를 측정하지 못함"),
        ("한계", "심각도 미지원", "severity 라벨 학습 데이터 없음", "현재 LLM 값을 사용하며, 규칙으로 채울지는 후속 정책 확정이 필요함"),
        ("연계", "팀 라우팅", "제품 LLM의 문제 코드와 요청 종류를 후속 라우팅 입력으로 사용", "문제 코드 접두별 case_type·담당 팀 매핑은 제품 라우팅 규칙에 별도로 둔다"),
    ])
    desc = []
    if enc:
        desc.append(f"인코더 {len(enc)}종")
    if lin:
        desc.append(f"TF-IDF 분류기 {len(lin)}종")
    fill(d.tables[7], [("2026.09.17", CHANGER if fill_cover else "",
                        f"선정 모델 3종({', '.join(desc)})의 구조·저장·추론 작성", "전체", "v1.0")])
    add_strategy(d, d.tables[7], "적용 전략: 제출 모델 폴더는 판마다 새로 만들고 기존 폴더를 덮어쓰지 않는다(ml/package_models.py는 "
                                        "출력 폴더가 있으면 멈춘다). 받는 쪽은 SHA256SUMS.txt로 파일을 확인한 뒤 교체한다.")
    return save(d, "[데이터 전처리] 학습한 ML_DL 모델_4차_여행.docx")



# 4차 추가 상수의 유일한 수치 출처: w4/데이터전처리_여행/_사실표_클로드.md.
# A: 2026-09-28 확인, B: 설계서 2026-09-26 및 구현 실측 09-27~28,
# C: 0639e54e·094e5019·473ada20 및 migrations.md 029,
# D: team/role-mobility의 2026-09-16 전처리 v2·ML학습 v1 보고.
SERVICE_NOTE = '팀 A-COPilot이 만드는 여행 운영 서비스 guguroute의 데이터 전처리와 분류 모델을 다룬다.'
LABEL_NOTE = ('라벨 지침은 2026-09-17.v2에서 2026-09-22.v3으로 바뀌었다. '
              'booking_revert_request가 추가되어 제품 문제 코드는 18종이지만, 학습 데이터와 제출 모델은 '
              'v2의 17종 그대로다. 2026-09-17 이후 재학습은 없다. 취소와 되돌림을 구분하려면 '
              'v3 지침으로 다시 라벨을 붙이고 학습해야 한다(ml/label_with_gemma.py, 커밋 36cc1b99).')
LOCAL_NOTE = ('3차의 제품 캐스케이드 연결 서술을 정정한다. 로컬 모델은 어댑터와 계약 시험까지 구현했으며 '
              '제품 분류에는 연결되지 않았다. guguroute의 인라인 분류는 Gemma 4 12B(Ollama)가 맡고, '
              '없으면 OpenAI를 사용한다. 근거는 app/composition.py의 build_classifier와 '
              'app/infrastructure/ml, tests/unit/ml 및 추가 커밋 e8f9c458이다(2026-09-28 기준).')
MOB_SOURCE = ('이동 팀 보고(2026-09-16) 기준이다. 팀 브랜치 team/role-mobility의 '
              'docs/mobility/2026-09-16_Mobility_데이터전처리결과서_v2.md 및 '
              '2026-09-16_Mobility_ML학습결과서_v1.md를 인용하며 이번 문서 작성에서 재실행하지 않았다.')
PLAN_SOURCE = ('계획 읽기 비교는 새 모델 학습이 아니라 쓰는 모델의 선정·평가다. '
               '출처는 고객 계획 읽기 설계서(2026-09-26) 실측 절이다. '
               'Gemma 4 12B, 온도 0, 생각 모드 끔을 기본으로 쟀다. '
               '합성 사진 1장, 시각 항목 분모 6, 방식마다 1회 측정이며 생각 모드를 켠 비교는 따로 표시했다.')
# 사실표 B1: 평가 분모가 다른 장소 실험은 각각 분모를 명시한다.
PLAN_ROWS = [
    ('방식 선정', '계획 JSON', '사진을 한 번에 일정 JSON으로 변환', '3/6 = 50%, 95.2초. 일차 누락·없는 칸 추가가 있었다'),
    ('방식 선정', '받아쓰기', '사진을 한 줄씩 그대로 받아 적기', '6/6 = 100%, 44.7초'),
    ('방식 선정', 'LLM 구조화', '받아쓴 글에 format: json 적용', '1/6 = 17%, 48.7초. 예약번호를 다른 항목에 붙였다'),
    ('방식 선정', '스키마', '줄 번호·JSON 스키마, 생각 모드 끔', '6/6을 찾았으나 머리줄 3개를 포함해 9개 반환, 이름 변조, 40.0초'),
    ('방식 선정', '생각 모드', '같은 스키마에 생각 모드 켬', '1/6, 35.8초'),
    ('방식 선정', '규칙 파서', '받아쓴 글을 규칙으로 읽기', '6/6 = 100%, 값 변조 없음, 1ms 미만'),
    ('장소 선정', '임베딩', 'bge-m3, 후보 이름 2,175개', '1위 정답 5/12 = 42%, 문턱 0.88 초과 0/12, 후보 임베딩 41.8초'),
    ('장소 선정', '자모 오타', '정답 이름이 목록에 있는 경우', '2/2가 1위. 경복굼 0.11, 광장시자 0.09, 즉시'),
    ('장소 선정', '키워드 조회', '카카오 서울 범위, 이름이 특정되는 질의', '2026-09-26, 1회: 4/6이 1위 정답, 호출당 1초 안팎. 2026-09-27 재측정(1회)에서 경복궁의 로마자 질의는 1~5위가 모두 식당 체인 경복궁 지점이었다. 이후 카카오 값은 직접 받지 않고 관광공사가 확인한 이름만 받는다'),
]
# 사실표 D: 평균·편차는 이동 보고의 구간 GroupKFold 5폴드 × 시드 5 결과다.
MOB_ROWS = [
    ('이동 비교', 'v1 logreg', '특징 27개, 탐침 8,648건, 현행 판정 라벨', '판정 일치 정확도 0.808±0.118, 미채택'),
    ('이동 비교', 'v1 HGB', '동일 조건, HistGradientBoosting', '0.848±0.120, 지하철 0.992·버스 0.405, 회귀 71/85'),
    ('이동 비교', 'v1 MLP', '동일 조건, MLP 64-32', '0.823±0.122, 미채택'),
    ('이동 비교', '기준선', '다수결과 현행 코드·시간표', '다수결 0.678, 현행 1.000은 라벨 생성 경로와의 일치다'),
    ('이동 비교', 'v1 한계', 'HGB 근거없음 판정 보존', '확정답 전환 376/376, 성립 전환 56/376. 회귀 오답 14건은 시간표가 필요하다'),
    ('이동 비교', 'v2 HGB', '근거없음 구간 9종, 탐침 11,656건, 특징 33개, class_weight·격자 27조합', '0.893±0.078, 근거없음 재현율 0.697, 성립 전환 275/3,342, 회귀 73/85'),
    ('이동 결정', '미채택', '판정은 코드와 시간표 조회를 유지한다', '근거없음의 성립 전환 0과 근거 등급 산출을 지키며 현행에 없는 기능을 더할 때 재검토한다'),
]

def find_table(doc, first_header):
    hits = [t for t in doc.tables if t.cell(0, 0).text.strip() == first_header]
    if len(hits) != 1:
        raise RuntimeError(f'표 검색 실패: {first_header}')
    return hits[0]

def append_rows(table, rows):
    for values in rows:
        row = table.add_row()
        for cell, value in zip(row.cells, values):
            setc(cell, value)
    keep_table_tidy(table)

def revise_v4(d, name):
    if '데이터 전처리 결과서' in name:
        set_line(d, '전처리 목적', 'guguroute의 분류 모델 학습·평가 데이터와 고객 계획 운영 입력을 정제하고, 장소 조회 및 이동 시간표의 근거를 관리한다')
        set_line(d, '전처리 범위', '기존 감정·요청 종류·문제 코드 학습 데이터, 고객 계획 읽기, 외부 장소 처리, 이동 팀 시간표 전처리')
        insert_after(d, '2.1 데이터 출처 및 현황', [
            SERVICE_NOTE + ' 기존 학습 데이터는 유지하고 운영 입력과 이동 팀 보고를 함께 정리한다.',
            LABEL_NOTE,
            '고객 계획은 글·사진·PDF·docx·xlsx를 받는다. 파일 종류는 바이트로 가리며 파일 5개·10MB·글 20,000자 한도를 적용한다. '
            '값마다 rule·llm_span·lookup·customer 방법과 원문 위치 또는 조회 출처를 남긴다(계획 읽기 API 문서).',
            MOB_SOURCE,
            '이동 팀 수집 규모는 지하철 시간표 463,326행 중 판정 대상 444,915행, 출발 없음 18,411행이다. '
            '공항 리무진 8,949행·180노선, 시내버스 717노선·정류장 41,820행, 역 순서 777간선·793역, '
            '환승 도보 213쌍·74역, 혼잡도 65,169행, 공휴일 46일이다(이동 팀 보고, 2026-09-16).',
        ])
        append_rows(find_table(d, '이슈 유형'), [
            ('라벨 판 차이', 'issue_code', '제품 18종·학습 17종', 'v2 학습본 유지, v3 재라벨·재학습 필요', 'booking_revert_request는 기존 모델이 출력할 수 없다'),
            ('계획 읽기 누락', '사진의 줄', '전체·반쪽 받아쓰기 대조', '완전성 검사 후 규칙으로 읽는다', '09-27, 합성 사진 1장·1회, 6/6, 변조 0·누락 0, 56.6초'),
            ('값 변조', '남은 줄·인용', '원문에 글자 그대로 있는가', '없는 인용은 버리고 원문 조각을 사용한다', '09-27 같은 입력 2회 결과 같음, 원문 밖 인용 거절 0'),
            ('규칙 오인식', '인원·끼니·장소', '시각 일부를 인원으로 읽거나 식사 순서를 잘못 놓음', '인원 패턴·원문 순서·끼니 말·활동어 분리를 수정했다', '2026-09-27~28 팀 수정 보고'),
            ('조회 차단', '장소 근거', '속도 제한·시간 초과·예산', 'blocked에 기록하고 장소 부재와 구분한다', '09-27 질의 9개·호출 11번, 몰림 10에서 30으로 변경, 하루 1,000 유지'),
            ('장소 재사용', '외부 장소 응답', '공용 목록 저장 보류', '실시간 조회·여행 전용 행, 응답 캐시 0', '관광공사 목록 8,015행 삭제, 설계서 장소 해석 절·마이그레이션 029'),
            ('이동 정합성', '시각·행선지·역 순서', '단일 소스보다 소스 간 대조', '자정 넘김·지선 필터·중복 종착 행 등을 수정했다', '이동 팀 보고 09-16: 결함 9건, 행선지 문제 41,510행·종착 열차 3,651행'),
        ])
        append_rows(find_table(d, '필드'), [
            ('intake_sources', '원문·줄', '못 읽은 부분은 확인 대상으로 남긴다', '전체·반쪽 대조', '바이트 형식·한도 검사', 'PDF·docx·xlsx 파서, 사진 받아쓰기'),
            ('intake_claims', '값·방법·근거', '모르는 값은 만들지 않는다', '수정 이력 보존', '원문 밖 인용 거절', 'rule·llm_span·lookup·customer'),
            ('날짜·예약번호', '날짜·문자열', '첫날이 없으면 묻는다', '원문 위치로 구분', '필수값 검사', '예약번호는 원문을 유지한다'),
            ('places.trip_scope', '여행 참조', '미확정 장소는 확인 필요', '공용·여행별 유일성 분리', '다른 여행에서 재사용하지 않는다', '외부 관광공사·카카오·구글, 마이그레이션 029'),
            ('이동 시각·행선지', '시간표 필드', "출발 없음 '000000' 제외", '종착 행의 같은 값은 중복 처리', '열차 단위 행선지 복원·FR_CODE 역 순서', '이동 팀 보고 09-16 기준'),
        ])
        append_rows(find_table(d, '처리 단계'), [
            ('계획 글자화', '글·사진·PDF·docx·xlsx', '줄 번호가 붙은 원문', '전용 파서 또는 받아쓰기·완전성 검사'),
            ('규칙·원문 인용', '원문 줄', '시각·일차·날짜·예약번호·인원·끼니', '규칙을 먼저 적용하고 남은 줄만 LLM으로 위치를 찾는다'),
            ('날짜·장소 해석', '원문 근거와 조회', '확정값 또는 확인 필요', '날짜 우선순위 적용, 장소 정확 일치·자모·관광공사·카카오 이름 재확인'),
            ('확인·등록', '근거가 붙은 항목', 'trip_intakes·intake_sources·intake_claims', '필수값 검사와 규칙 배치 후 등록한다'),
            ('외부 장소 처리', '관광공사·카카오·구글 조회값', '그 여행 전용 places 행', '공용 목록·일정 생성 후보·다른 여행에 노출하지 않는다'),
            ('이동 정규화', '공공 시간표·역 순서·환승 데이터', '판정용 조회 데이터', '소스 간 정합성 검사, 벡터 색인 없이 B-tree로 정확 조회한다'),
        ])
        append_rows(find_table(d, '구분'), [
            ('학습 유지', '지침과 데이터 판', 'v3 지침·v2 학습본, 재학습 없음', 'ml/label_with_gemma.py, 커밋 36cc1b99. 새 지침 적용은 다음 학습 과제다'),
            ('운영 평가', '계획 웹 경로', '09-28 합성 사진 1장·1회, 6/6 항목·6/6 장소, 50.9초', '빠진 줄 0·예약번호 1건·등록을 막는 문제 0, 2026-09-27~28 팀 실측 보고, 각 1회'),
            ('운영 평가', '장소 해석', '09-27 질의 9개·1회, 6/9 = 67%', '남산타워 별칭·한강 카약 근접 후보·북한산 둘레길 근접 구간은 미완'),
            ('운영 평가', '일정 생성 요청', '09-28, 1회, 2박3일·넷이서·실내 위주 요청', '모델 없이 규칙으로 일수 3·인원 4를 읽었다. 첫날은 비워 두고 일정 생성기로 3일 일정을 등록했다(2026-09-27~28 팀 실측, 각 1회)'),
            ('운영 시험', '계획 읽기', '09-28 e2e 15·규칙 22·장소와 날짜 22·일정 짜기 1 통과', '전체 live 제외 1,604 통과는 2026-09-27~28 팀 시험 보고이며 이번 작성에서 재실행하지 않았다'),
            ('장소 정책', '저장·출처 표시', '수집 기본 꺼짐·원본 JSON 저장 중단·응답 캐시 0', '관광공사 출처와 저작권 정책 링크를 표시한다. 호출 서비스명은 guguroute이다'),
            ('장소 현황', '09-28 개발 DB 집계', '관광공사 목록 0행·공용 112행·여행 전용 21행', '공용 중 관광공사 id 잔존 5행은 이전 시연용이다. 전용 행은 개발·시험 데이터다(2026-09-28 개발 DB 집계)'),
            ('장소 한계', '보존·약관 해석', '여행 종료 뒤 전용 행 삭제 미구현', '서면 문의는 사용자 승인 대기이며, 약관 해석은 확정하지 않았다(설계서 장소 해석 절·마이그레이션 029)'),
            ('이동 검증', '09-16 팀 보고', 'C1~C6·회귀 85건 통과, 탐침 8,648건', '판단불가 376/8,648 = 4.35%, 이번 작성에서 재실행하지 않았다'),
            ('이동 개인정보', '공공데이터만 사용', '개인정보 해당 없음, 경로 API 원값·가공값 저장 안 함', '스키마로 저장을 제한하고 음성 시험 12건으로 확인한 팀 보고다'),
            ('평가 한계', '계획 읽기 소표본', '합성 사진 1장·글 몇 건·대부분 각 1회', '실제 사진·손글씨·저해상도 품질 미확보. 평가셋 60건은 계획이며 아직 없다'),
        ])
        tail = find_table(d, '구분')._tbl
        insert_after(d, tail, [
            '관광공사 콘텐츠 캐싱 제한을 고려해 해석 확정 전 저장을 보류한 팀 결정이다. 카카오는 이름 찾기에만 쓰고 '
            '관광공사로 재확인하며, 관광공사에 없으면 그 여행 항목에만 둔다. 카카오도 응답 캐시 0과 호출 예산을 적용한다. '
            '근거는 고객 계획 읽기 설계서 장소 해석 절, 마이그레이션 029다.',
            '이동 팀의 관광공사 걷기 코스 전국 1,069건 로컬 수집분(50d4b240, 2026-09-21)은 '
            '09-27 실시간 조회 결정 이전의 정리 대상이다. 현재 활용 데이터로 제시하지 않는다.',
            '이동 팀 커밋 보고 기준 추가 변경은 버스 운행구간 정규화(f91adde7, 09-24), 판정 계약 v0.8·회귀 140 재정의'
            '(8641ca49, 09-24), 환승 칸 표(dfea34fd, 09-25), 운임 fare_krw(2d188edc, 09-25)다. '
            '버스 소요시간은 ML이 아니라 공공 통행시간 프로파일 OA-21217의 구간 p50/p90을 규칙 v0.9에 반영했다'
            '(6126599d·296ffa0b, 09-25). 회귀 168 어긋남 0·합성 단위 14는 해당 커밋 보고다.',
        ])
        fig = flow(FIG_DIR / '그림5_계획읽기.png', '고객 계획 읽기', [
            ('원문 처리', ['글·파일 접수', '파서·사진 받아쓰기\n완전성 검사', '규칙으로 먼저 읽기', '남은 줄만 LLM\n원문 인용 검증']),
            ('해석·확인', ['날짜 근거 해석', '장소 조회·재확인', '필수값 검사\n확인 화면', '등록·근거 보존\n외부 장소는 여행 전용']),
        ])
        insert_after(d, '그림 1.', [('img', fig, '그림 5. 고객 계획 원문 처리와 확인·등록 흐름. 왼쪽 열 다음 오른쪽 열로 이어진다', 13.0)])
        change = '계획 읽기·장소 처리·이동 전처리 추가, 지침과 학습 데이터 판 구분'
    elif '머신러닝_딥러닝' in name:
        set_line(d, '목표', '기존 분류 학습 결과를 유지하고, 이동 판정 ML 대조와 고객 계획 읽기 방식 선정의 결과·한계를 비교한다')
        insert_after(d, '2.1 후보 모델 목록', [SERVICE_NOTE + ' EXP-01~21은 3차 결과를 유지했다. 2026-09-17 이후 재학습은 없다.', LOCAL_NOTE])
        results = find_table(d, '구분')
        append_rows(results, MOB_ROWS + PLAN_ROWS)
        insert_after(d, results._tbl, [MOB_SOURCE,
            '이동 비교는 구간 단위 GroupKFold 5폴드·시드 5를 사용한다. 라벨은 현행 판정이며 사람이 검수한 분류 정답과의 정확도로 해석하지 않는다. '
            'v2 성립 전환 건수는 이동 보고의 대표 시드 집계다. 버스 소요시간 슬롯은 ML 학습이 아니라 '
            '공공 통행시간 프로파일을 규칙 v0.9에 반영했다(6126599d·296ffa0b, 2026-09-25).',
            PLAN_SOURCE,
            '받아쓰기는 원문 보존에, 구조 읽기는 규칙에 맡긴다. 규칙이 못 읽은 줄만 LLM이 원문 위치를 가리킨다. '
            '장소는 임베딩 점수로 확정하지 않고 자모 오타 교정과 실시간 조회로 확인한다.',
            '구현 뒤 실측은 별도다. 09-27 전체·반쪽 받아쓰기와 규칙 읽기는 6/6·56.6초, '
            '09-28 웹 사진 경로는 6/6 항목·6/6 장소·50.9초다. 같은 합성 사진 1장, 각 1회이며 '
            '방식 선정 표의 받아쓰기 단독 시간과 직접 비교하지 않는다(2026-09-27~28 팀 실측, 각 1회).',
        ])
        insert_after(d, '3.2 과적합', [LABEL_NOTE,
            '2026-09-28 기준 사람 검수 라벨은 0건이다. 팀 브랜치의 홀드아웃 자료는 템플릿이며 검수 완료 라벨이 아니다. '
            '요청 종류·문제 코드 점수는 교사(Gemma) 일치도다.',
            '다음 과제는 v3 재라벨·재학습, 사람 정답 홀드아웃 확보, 실제 사진·손글씨·저해상도 평가다. '
            '계획 읽기 평가셋 60건은 아직 없으며, 장소 별칭과 앞뒤 장소에 가까운 후보 선택도 남아 있다. '
            '새 비교는 소표본 실측과 팀 보고이므로 제품 전체 품질로 일반화하지 않는다.',
        ])
        change = '기존 실험 유지, 이동 ML 미채택 비교·계획 읽기 방식 선정 추가'
    else:
        insert_after(d, '프레임워크 / 버전', [SERVICE_NOTE + ' 선정된 kf-deberta-base 3종은 그대로다.', LOCAL_NOTE, LABEL_NOTE])
        append_rows(find_table(d, '구분'), [
            ('어휘 한계', '문제 코드', '제출 17종·제품 18종', 'booking_revert_request를 출력할 수 없다. v3로 재라벨·재학습한 뒤 연결을 검토한다'),
            ('어휘 구분', '요청·감정·심각도', '요청 5종, 모델 감정 2종·제품 감정 3종, 제품 심각도 4종', '심각도 학습 데이터는 없으며 제품은 LLM 값을 사용한다(app/modules/travel_ops/feedback.py 및 제출 모델 config.json)'),
            ('검수 한계', '사람 라벨', '2026-09-28 기준 0건', '요청 종류·문제 코드 성능은 교사 일치도이며 사람 정답 정확도가 아니다'),
            ('무결성', 'SHA256SUMS.txt', '2026-09-28, 17/17 일치', 'SHA256SUMS.txt 대조 결과다(2026-09-28). 로컬 제출 파일도 빌드에서 재대조하며 검사 기록을 남긴다'),
            ('미채택 비교', 'model_hgb.pkl', '2.9MB, 특징 27개, 0.848±0.120', '이동 팀 보고 2026-09-16 기준, 회귀 71/85, 제품 판정 경로에 넣지 않는다'),
            ('미채택 비교', 'model_hgb_v2.pkl', '1.6MB, 특징 33개, 0.893±0.078', '이동 팀 보고 2026-09-16 기준, 회귀 73/85, 근거없음의 성립 전환 275/3,342'),
        ])
        insert_after(d, '3.2 성능', [MOB_SOURCE])
        change = '제품 미연결 정정, 라벨 어휘 차이·해시 확인·미채택 이동 모델 추가'
    append_rows(find_table(d, '변경일'), [('2026.09.28', '전체', change, '전체', 'v2.0')])
    # 그림은 본문 높이의 80% 이하로 제한한다. 표지 그림도 동일 검사한다.
    # 양식의 소수 twip 속성을 같은 길이의 정수로 정규화한다.
    for section in d.sections:
        margins = section._sectPr.find(qn('w:pgMar'))
        if margins is not None:
            for key, value in list(margins.attrib.items()):
                if '.' in value:
                    margins.set(key, str(round(float(value))))
    sec = d.sections[0]
    max_h = int((sec.page_height - sec.top_margin - sec.bottom_margin) * 0.8)
    max_w = int(sec.page_width - sec.left_margin - sec.right_margin)
    for shape in d.inline_shapes:
        scale = min(1, max_h / shape.height, max_w / shape.width)
        if scale < 1:
            shape.width = int(shape.width * scale)
            shape.height = int(shape.height * scale)
    # 긴 식별자와 파일명이 표 밖으로 밀려나지 않도록 Word 줄바꿈을 허용한다.
    for table in d.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    prop = p._p.get_or_add_pPr()
                    wrap = OxmlElement('w:wordWrap')
                    wrap.set(qn('w:val'), '1')
                    prop.append(wrap)

def write_change_summary():
    import difflib
    import hashlib
    records = []
    packaged = ML / '_drive_upload/학습한_ML_DL_모델_3차_여행'
    manifest = packaged / 'SHA256SUMS.txt'
    if not manifest.exists():
        raise SystemExit('모델 해시 근거가 없다')
    for line in manifest.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip():
            continue
        expected, rel = line.split(maxsplit=1)
        rel = rel.lstrip('*')
        fp = packaged / rel
        h = hashlib.sha256()
        with fp.open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                h.update(block)
        if h.hexdigest() != expected.lower():
            raise SystemExit(f'모델 해시 불일치: {rel}')
        records.append({'file': rel, 'sha256': expected, 'result': 'OK'})
    (OUT_DIR / '검사결과.json').write_text(json.dumps({'model_hashes': records, 'docx_reopen_checks': 'PASS'}, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# 변경요약 4차', '',
             '- 기준: 3차 제출본과 사실표 A~E. 제출일을 2026. 9. 28.로 바꾸고 기존 변경 이력을 유지한 채 v2.0 행을 추가했다.',
             '- A1~A4: 라벨 지침 v3·제품 18종과 학습 v2·모델 17종을 구분했다. booking_revert_request 미지원과 재학습 필요를 명시했다. 근거: 36cc1b99, 2026-09-22 및 사실표 확인일 09-28.',
             '- A6: 전처리 목적·학습 목표·모델 구성/추론/라우팅·그림 4를 정정했다. 로컬 어댑터는 시험까지이며 제품 분류는 LLM이다. 근거: composition.py::build_classifier, infrastructure/ml, tests/unit/ml, e8f9c458 및 사실표 09-28.',
             '- A5·A7·A8: 해시 일치, 사람 라벨 미확보, 심각도 미학습을 기록했다. 해시는 로컬 제출 파일을 다시 읽어 검증했다.',
             '- B: 전처리 품질·필드·파이프라인·재현성 표 및 그림 5에 계획 읽기를 추가했다. 학습 결과에는 방식 선정 실측을 별도 비교로 추가했다. 근거: 계획 읽기 설계서 §0·§1·§3·§4·§8, rest-endpoints.md 계획 읽기 절, 84b0f7a9 및 사실표 09-26~28.',
             '- C: 장소 목록 삭제·실시간 조회·응답 캐시 중단·여행 전용 행·출처 표시·잔존 시연 행·삭제 미구현을 반영했다. 근거: 0639e54e·094e5019·473ada20, migrations.md 029, 사실표 09-27~28. 법적 해석을 새로 확정한 문서가 아니다.',
             '- D: 이동 전처리와 ML 비교를 팀 보고로 추가했다. 미채택 결론과 모델 파일 정보를 기록했다. 걷기 코스는 정책 결정 이전 정리 대상으로만 표기했다. 근거: team/role-mobility의 2026-09-16 보고 두 건, f91adde7·8641ca49·dfea34fd·2d188edc·6126599d·296ffa0b·50d4b240 및 사실표.',
             '- E: 제품 guguroute·팀 A-COPilot을 사용했다. 표지의 저장소 URL·작성자·공유 드라이브는 유지했다.',
             '- 빌드 변경: FORMS와 OUT 환경변수, OUT 안 임시·캐시·크기 기록, 원본 쓰기 제거, 저장 후 재열기 검사, 그림 크기 제한, 상세 변경 목록과 해시 검사 자동 생성.',
             '', '## 1차 검수 반영 R1~R7', '',
             '- R1: 제출 DOCX·검수본문의 내부 메모명을 실제 코드·설계서·팀 보고·집계 출처로 바꾸고 공개 금지 검사 목록에 추가했다.',
             '- R2: 감정 부정·긍정 라벨 비율 문장과 표를 복원했다. datasets/ml/sentiment_ko/data/preprocess_stats.json의 split_label_ratio를 소수 둘째 자리로 반올림하고 split_sizes에서 분할비와 전체 분모를 계산했다. 학습 0.5·0.5, 검증·시험 0.4999·0.5001이 근거다.',
             '- R3: 카카오 4/6 행에 측정일·횟수, 09-27 로마자 질의 재측정의 식당 오인식과 관광공사 확인 이름만 받는 변경을 추가했다. 근거: 09-26 설계서 실측 및 09-27 팀 실측 보고.',
             '- R4: 기존 교사 라벨 도구 뒤에 파일 파서·사진 처리·원문 인용·장소 조회 도구를 추가했다. 근거: app/modules/travel_ops/intake/sources.py와 계획 읽기 설계서.',
             '- R5: 모델 개요의 설명 세 문단을 모델 유형·담당 태스크·프레임워크 및 버전 세 줄 뒤로 옮겼다. 다른 두 문서의 절 안 설명은 유지했다.',
             '- R6: 그림 5 설명에 왼쪽 열 다음 오른쪽 열로 이어짐을 명시했다.',
             '- R7: 세 문서에 동일한 팀 A-COPilot·여행 운영 서비스 guguroute 소개 문장을 적용했다.',
             '', '## 사실표 밖 수치', '',
             '새 실측·추정 수치는 추가하지 않았다. 지시문이 유지하도록 한 3차 수치(전처리 건수·분할·EXP-01~21 지표·하이퍼파라미터·환경 버전·CPU 지연·파일 크기)는 기존 빌드와 datasets/ml JSON에서 그대로 읽었다. 이는 사실표의 신규 수치와 별개인 기존 결과의 재수록이다.',
             '분할 표의 80.0%·10.0%·10.0%와 분모 199,889건은 기존 JSON split_sizes의 건수와 합계로 계산했다. 라벨 비율 0.50은 같은 파일 split_label_ratio의 반올림값이다. 새 실측·추정값이 아니다. 상세 출처는 아래와 같다.',
             '', '## 기존 수치 근거 파일', '']
    paths = sorted({p for p in ML.rglob('*.json') if p.name in ('metrics.json','preprocess_stats.json','pool_real_stats.json','labeling_stats.json','pii_audit.json','environment.json','cpu_eval.json','comparison.json') and '_drive_upload' not in p.parts})
    for p in paths:
        # 수치 파일을 직접 파싱하여 읽을 수 있는 근거인지 확인한다.
        json.loads(p.read_text(encoding='utf-8'))
        lines.append('- datasets/ml/' + p.relative_to(ML).as_posix())
    lines += ['', '- 합성 필터 건수: datasets/ml/intent_ko/data/synth_labeled.jsonl.',
              '- 모델 크기: datasets/ml/sentiment_ko/sota/kakaobank__kf-deberta-base/model.safetensors의 파일 크기. OUT의 model_files.json에 기록했다.',
              '- 기존 고정 설정과 장치 사양: _build/build_데이터전처리_3종_여행.py 및 3차 검수본문. 이번 작성에서 장치를 다시 측정하지 않았다.',
              '', '## 확인 범위와 미확인 사항', '',
              '- DOCX 저장 후 재열기, 금지 문자, 양식 예시 잔존, 비공개 식별자·IP 검사 통과.',
              '- 모델 파일 해시는 로컬 SHA256SUMS.txt와 직접 대조했다. 결과는 검사결과.json에 기록했다.',
              '- 이동 실험, 계획 읽기 실측, 개발 DB 집계, 전체 제품 시험은 재실행하지 않았다. 사실표·팀 보고의 날짜와 조건을 인용했다.',
              '- 실제 사진·손글씨·저해상도 평가, 사람 검수 라벨, 관광공사 서면 해석, 여행 종료 후 전용 행 삭제는 확보·완료된 것으로 쓰지 않았다.',
              '- 문서 페이지 렌더링·육안 검수 상태는 별도 검수기록.md를 따른다.',
              '', '## 모든 본문 변경 목록', '', '아래는 3차 검수본문과 새 DOCX에서 추출한 검수본문의 전체 변경이다. 삭제 줄과 추가 줄을 함께 기록해 문장·표·숫자 변경을 빠짐없이 남겼다. 위 항목이 각 변경의 이유와 출처다.', '']
    for new in sorted((OUT_DIR / '검수본문').glob('*.md')):
        old = FORMS / 'w3/데이터전처리_여행/검수본문' / new.name.replace('_4차_', '_3차_')
        before = old.read_text(encoding='utf-8').splitlines()
        after = new.read_text(encoding='utf-8').splitlines()
        lines += ['### ' + new.stem, '', '```diff', *difflib.unified_diff(before, after, fromfile=old.name, tofile=new.name, lineterm=''), '```', '']
    (OUT_DIR / '변경요약_4차.md').write_text('\n'.join(lines), encoding='utf-8')


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
    outs = [build_preprocess(s, True), build_training(s, True), build_model(s, True)]
    write_change_summary()
    print("\n생성 완료:", *[o.name for o in outs], sep="\n  ")


if __name__ == "__main__":
    main()

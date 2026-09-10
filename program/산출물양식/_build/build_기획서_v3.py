# -*- coding: utf-8 -*-
"""프로젝트 기획서 2차 (v3): w2 병합본 md 를 양식 docx 로 옮긴다.

입력: program/산출물양식/w2/기획서/기획서_병합본_코덱스_2차.md 가 있으면 그것,
      없으면 _1차.md 에 Claude 교차검토 R1(결정을 [실측]으로 쓴 표시)·R2(SOM 행)를 기계 적용.
표는 docx_tables 로 진짜 Word 표, 그림은 w2/표와시각자료/클로드 의 PNG.
★기계 부분(양식 로드·표지·깃허브 칸·잠김 재시도)은 v2 와 같다.
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from docxfill import Doc  # noqa: E402
from docx_tables import insert_table_after  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FORMS = os.path.dirname(HERE)
W2 = os.path.join(FORMS, "w2")
TEMPLATE = os.path.join(FORMS, "[기획] 프로젝트 기획서_양식.docx")
OUT = os.path.join(FORMS, "[기획] 프로젝트 기획서_2차_여행.docx")
FIG = os.path.join(W2, "표와시각자료", "클로드")

SECTIONS = ["프로젝트 주제", "문제 정의", "시장조사 및 BM 분석", "시스템 구성 기획",
            "모델링 계획", "데이터 수집 전략", "역할분담(R&R)"]

# ── 입력 고르기 ─────────────────────────────────────────────────────
src2 = os.path.join(W2, "기획서", "기획서_병합본_코덱스_2차.md")
src1 = os.path.join(W2, "기획서", "기획서_병합본_코덱스_1차.md")
if os.environ.get("PLAN_SRC"):  # 실무본 등 다른 원고를 쓸 때
    SRC = os.environ["PLAN_SRC"]
    md = open(SRC, encoding="utf-8").read()
elif os.path.exists(src2):
    SRC = src2
    md = open(src2, encoding="utf-8").read()
else:
    SRC = src1
    md = open(src1, encoding="utf-8").read()
    # R1 — 결정·계획을 [실측] 으로 쓴 표시 (교차검토_클로드_병합본_1차 R1)
    R1 = {
        "[실측 — 결정문 확인]": "[결정 2026-09-10]",
        "[실측 — 확정 가격]": "[결정 2026-09-10]",
        "[실측 — 결정문]": "[결정 2026-09-10]",
        "[실측 — 상품 상한]": "[결정 2026-09-10]",
        "[실측 — 확정 시나리오 설정]": "[결정 — 확정 시나리오]",
        "[실측 — 시나리오 설정]": "[결정 — 확정 시나리오]",
        "[실측 — 시나리오 구성]": "[결정 — 확정 시나리오]",
        "[실측 — 시나리오]": "[결정 — 확정 시나리오]",
        "[실측 — WBS 예정일]": "[결정 — WBS 계획일]",
        "[실측 — 설계값]": "[결정]",
        "[실측 — 기준 항목 구성]": "[결정 — v11 §12]",
        "[실측 — 기준 구성]": "[결정 — v11 §12]",
        "[실측 — 기준 문서]": "[결정 — v11 §3]",
        "[실측 — 설계 구성]": "[결정 — v11 §9-C]",
        "[실측 — 기존 계획량]": "[결정 — WBS 계획]",
        "[실측 — 설계대응의 공백 분류]": "[제안 — 설계대응 분석]",
        "[실측 — 중간 일정]": "[결정 — 중간발표일]",
    }
    for a, b in R1.items():
        md = md.replace("`" + a + "`", "`" + b + "`").replace(a, b)
    # R2 — SOM 행에 손익용 판매 가정을 두지 않는다
    md = re.sub(r"^\| SOM 산정 경로 \|.*$",
                "| SOM | 정상 운영 연간의 신규 최초 결제 여행 | 검증된 획득 채널·전환 실적 | "
                "**산정하지 않는다** | 손익 계산용 1,200건은 아래 「미검증 획득 시나리오」다. SOM 으로 인용하지 않는다. |",
                md, flags=re.M)
    # R5 — 이미 있는 그림을 본문이 부르게 한다
    for key, fig in (("TAM·SAM의 소수점", "[그림: F3 시장 — 아는 것과 모르는 것]"),
                     ("후속 계산은 표시용", "[그림: F2 기여이익 폭포]"),
                     ("음수 상한은", "[그림: F1 CAC-손익분기]")):
        md = re.sub(r"^(" + re.escape(key) + r".*)$", r"\1\n\n" + fig, md, count=1, flags=re.M)

md = md.split("=====검토응답=====")[0]

# ── 글자 정리 ───────────────────────────────────────────────────────
BANNED_MAP = {"—": "-", "–": "-", "→": " > ", "⇒": " > ", "★": "", "☆": "",
              "✓": "O", "✔": "O", "✕": "X", "✗": "X", "▸": "-", "…": "...", "⇄": "<>",
              "①": "(1)", "②": "(2)", "③": "(3)", "④": "(4)", "⑤": "(5)", "⑥": "(6)",
              "\u2212": "-", "＝": "="}


def latex(s):
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"\1÷\2", s)
    s = re.sub(r"\\text\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"_\{([^{}]*)\}", r"\1", s)
    for a, b in (("\\times", "×"), ("\\approx", "≈"), ("\\qquad", "   "), ("\\quad", "  "),
                 ("\\le", "≤"), ("\\ge", "≥"), ("\\(", ""), ("\\)", ""), ("\\,", ""),
                 ("\\left", ""), ("\\right", "")):
        s = s.replace(a, b)
    return s.replace("\\", "").replace("{", "").replace("}", "")


def clean(s):
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1(\2)", s)   # 바깥 링크는 주소를 남긴다
    s = re.sub(r"\[([^\]]+)\]\(<?[^)]*>?\)", r"\1", s)                # 로컬 경로는 지운다
    s = s.replace("**", "").replace("`", "")
    s = latex(s)
    for a, b in BANNED_MAP.items():
        s = s.replace(a, b)
    return re.sub(r"  +", " ", s).strip()


# 수식 블록(\[ ... \])을 한 줄로
md = re.sub(r"\\\[(.*?)\\\]", lambda m: " ".join(m.group(1).split()), md, flags=re.S)

FIGMAP = [(("F1", "CAC-손익", "손익분기"), "F1_CAC_손익분기.png", "그림. CAC에 따른 연 손익분기 판매량(추정)"),
          (("F2", "폭포"), "F2_기여이익_폭포.png", "그림. 여행 1건의 기여이익(CAC 차감 전, 추정)"),
          (("F3", "아는 것과 모르는 것", "시장 깔때기"), "F3_시장_아는것과모르는것.png", "그림. 인바운드 시장 — 아는 것과 모르는 것"),
          (("현재 변경 대응",), "D1_변경대응_현재과정.png", "그림. 지금 여행자가 일정 변경에 대응하는 과정"),
          (("시스템 구성",), "D2_시스템구성_실행경계.png", "그림. 시스템 구성과 실행 경계"),
          (("변경·선택·실패", "변경, 선택, 실패"), "D3_변경선택실패_흐름.png", "그림. 변경·선택·실패 흐름")]


# 코덱스 판을 1차로 쓴다(2026-09-10 사용자 지시). 없으면 Claude 판.
FIG_CODEX = os.path.join(W2, "표와시각자료", "코덱스")
CODEX_NAME = {"F1_CAC_손익분기.png": "F1_CAC_손익분기.png", "F2_기여이익_폭포.png": "F2_기여이익_폭포_기본.png",
              "F3_시장_아는것과모르는것.png": "F3_시장_깔때기.png", "D1_변경대응_현재과정.png": "D1_변경대응_현재과정_코덱스.png",
              "D2_시스템구성_실행경계.png": "D2_시스템구성_코덱스.png", "D3_변경선택실패_흐름.png": "D3_변경선택실패_코덱스.png"}


def fig_path(png):
    c = os.path.join(FIG_CODEX, CODEX_NAME.get(png, png))
    return c if os.path.exists(c) else os.path.join(FIG, png)


def fig_for(line):
    for keys, png, cap in FIGMAP:
        if any(k in line for k in keys):
            return png, cap
    return None


# ── md → 절별 items + 표 ────────────────────────────────────────────
parts = re.split(r"^## (.+)$", md, flags=re.M)
sec = {parts[i].strip(): parts[i + 1] for i in range(1, len(parts) - 1, 2)}
missing = [s for s in SECTIONS if s not in sec]
assert not missing, "절이 없다: %s" % missing

TABLES = []   # (marker, caption, header, rows)
n_tab = 0
used_fig = set()
sec_items = {}
for s in SECTIONS:
    items, lines = [], sec[s].splitlines()
    i, last_bold = 0, None
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1
            continue
        if ln.lstrip().startswith("|"):
            block = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            rows = [[clean(c) for c in r.strip("|").split("|")] for r in block
                    if not re.match(r"^\|[-: |]+\|$", r)]
            n_tab += 1
            marker = "@@표%d@@" % n_tab
            cap = "표 %d. %s" % (n_tab, last_bold or s)
            header, body = rows[0], rows[1:]
            body = [r + [""] * (len(header) - len(r)) if len(r) < len(header) else r[:len(header)] for r in body]
            TABLES.append((marker, cap, header, body))
            items.append(marker)
            continue
        m = re.match(r"^\[그림: (.+)\]$", ln.strip())
        if m:
            f = fig_for(m.group(1))
            if f and os.path.exists(fig_path(f[0])) and f[0] not in used_fig:
                used_fig.add(f[0])
                items.append(("img", fig_path(f[0]), clean(f[1]), 6.2))
            i += 1
            continue
        if re.match(r"^\*\*[^*].*\*\*$", ln.strip()):
            last_bold = clean(ln)
            items.append(("b", last_bold))
        elif re.match(r"^\s*[-*] ", ln):
            items.append(("l", clean(re.sub(r"^\s*[-*] ", "", ln))))
        else:
            items.append(clean(ln))
        i += 1
    sec_items[s] = items

# ── 양식 채우기 ─────────────────────────────────────────────────────
d = Doc(TEMPLATE, os.path.join(HERE, "_tmp_plan_v3"))
d.replace_text("SK 네트웍스 Family AI 00기 : _____팀", "SK 네트웍스 Family AI 32기 : 6팀 A-COP")
d.replace_text("2026. 4. 18. ", "2026. 9. 10.")
d.replace_text("000", "김지혜, 서유현, 송채영, 정세환, 최상욱, 최연우")
for s in SECTIONS:
    d.after_heading(s, sec_items[s])
d.save(OUT)

# ── 저장 뒤: 표지 깃허브 칸 + 진짜 표 ───────────────────────────────
from docx import Document as _Docx  # noqa: E402

_doc = _Docx(OUT)
for _tb in _doc.tables[:2]:
    for _row in _tb.rows:
        if _row.cells[0].text.strip() == "깃허브 경로" and not _row.cells[1].text.strip():
            _row.cells[1].paragraphs[0].add_run("https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM")
for marker, cap, header, rows in TABLES:
    insert_table_after(_doc, marker, cap, header, rows)
# 표를 붙인 뒤 자리표시 문단을 지운다
for p in list(_doc.paragraphs):
    if re.fullmatch(r"@@표\d+@@", p.text.strip()):
        p._element.getparent().remove(p._element)
left = [p.text for p in _doc.paragraphs if "@@표" in p.text]
assert not left, "표 자리표시가 남았다: %s" % left[:3]

for _try in range(5):
    try:
        _doc.save(OUT)
        break
    except PermissionError:
        time.sleep(0.4)
else:
    _base, _ext = os.path.splitext(OUT)
    OUT = _base + "_새버전" + _ext
    print("  원본이 잠겨 새 이름으로 저장한다:", os.path.basename(OUT))
    _doc.save(OUT)

# 그림이 페이지 아래로 잘리지 않게 맞춘다 (2026-09-10 사용자 지적)
from fit_images import fit as _fit  # noqa: E402
_fit(OUT)
# 제목 개요(문서 탭·탐색 창) — 2026-09-10 사용자 요청, 코덱스 작성
import subprocess as _sp  # noqa: E402
_sp.run([sys.executable, os.path.join(HERE, "add_outline.py"), OUT], check=False)
_ol = os.path.splitext(OUT)[0] + "_outline.docx"
if os.path.exists(_ol):
    os.replace(_ol, OUT)  # 개요 스크립트는 _outline 으로 저장한다 — 원본 자리로 옮긴다
print("입력:", os.path.basename(SRC), "| 표", len(TABLES), "| 그림", len(used_fig), "| 저장:", os.path.basename(OUT))

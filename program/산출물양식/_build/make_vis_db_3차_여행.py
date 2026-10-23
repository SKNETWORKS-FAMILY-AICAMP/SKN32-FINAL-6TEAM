# -*- coding: utf-8 -*-
"""DB 설계서 3차(여행) 그림 셋 — 적용 상태 · 전체 ERD · 여행 핵심 ERD.

    python build_DB설계서_3차_여행.py --text-only   # 먼저 본문판
    python make_vis_db_3차_여행.py

★2차 그림 스크립트 셋(w2/표와시각자료/코덱스/make_vis_db_코덱스.py 의 draw_status,
  make_figs_codex.py 의 make_erd, make_erd_wide_코덱스.py 의 draw_erd)을 옮겨 왔다. **그림은 문서를 읽어
  그린다** — 3차 본문판의 엔터티 상태·관계 설명·칼럼 표가 바뀌면 그림도 따라 바뀐다.
★2차와 달라진 것:
  · 상태가 셋이다 — 구현 파일 존재 / 설계만 존재 / 흡수(별도 표 없음, trip_constraints)
  · 관계 설명에 「(제안)」이 없으면 구현된 FK 로 그린다(R-01·R-02·R-34·R-35 가 014 로 구현됐다)
  · 핵심 ERD 에서 흡수된 조건 표와 그 관계(3·4)를 뺀다 — 표 10개 · 관계 10개
  · 전체 ERD 범례의 「Trip 관련 4개 표의 상태가 두 문서에서 불일치」 메모를 지운다(3차에서 두 문서가 맞는다)
"""
from pathlib import Path
import os
import re
from collections import Counter
from html import escape

GRAPHVIZ_BIN = Path(r"C:\Program Files\Graphviz\bin")
if GRAPHVIZ_BIN.is_dir():
    os.environ["PATH"] = str(GRAPHVIZ_BIN) + os.pathsep + os.environ.get("PATH", "")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, Rectangle
from matplotlib.ticker import MaxNLocator
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "w3" / "데이터수집_여행"
SOURCE = BASE / "_중간" / "DB설계서_3차_본문판.docx"
OUTPUT = BASE / "그림"
AS_OF = "문서 기준: 2026-09-18 · 마이그레이션 001-016(015 적용 보류)"

BLUE, ORANGE, GRAY, INK, LIGHT = "#2a78d6", "#eb6834", "#757575", "#303030", "#f3f3f3"
DPI = 200
FONT = "Malgun Gothic"

plt.rcParams.update({
    "font.family": FONT, "axes.unicode_minus": False, "font.size": 9,
    "figure.facecolor": "white", "savefig.facecolor": "white",
    "text.color": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
})


# ── 문서 읽기 ──────────────────────────────────────────────────────────
def clean(value):
    return re.sub(r"\s+", " ", value).strip()


def rows_of(table):
    return [[clean(cell.text) for cell in row.cells] for row in table.rows]


def find_table(document, prefix):
    matches = [t for t in document.tables if rows_of(t)[0][:len(prefix)] == prefix]
    if len(matches) != 1:
        raise ValueError(f"표를 하나로 식별할 수 없습니다: {prefix}")
    return matches[0]


def status_of(text):
    if "구현 파일 존재" in text:
        return "impl"
    if "설계만 존재" in text:
        return "design"
    if "흡수" in text:
        return "absorbed"
    raise ValueError(f"해석할 수 없는 상태: {text}")


def read_document():
    document = Document(SOURCE)
    entity_rows = rows_of(find_table(document, ["구분", "테이블", "제약 대상"]))[1:]
    entities = {}
    for row in entity_rows:
        if row[1] in entities:
            raise ValueError(f"중복 엔터티: {row[1]}")
        entities[row[1]] = {"status": status_of(row[0]), "row": row}
    relationships = {}
    for identifier, parent, child, description in rows_of(
            find_table(document, ["관계명", "주 엔터티", "종 엔터티"]))[1:]:
        relationships[identifier] = {"parent": parent.split()[-1], "child": child.split()[-1],
                                     "description": description}
    columns, current = {}, None
    ordered_column_tables = []
    for block in document.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            match = re.search(r"테이블\s*:\s*([A-Za-z_][A-Za-z_0-9]*)", Paragraph(block, document).text)
            if match:
                current = match.group(1)
        elif tag == "tbl":
            values = rows_of(Table(block, document))
            if values[0][:4] == ["컬럼명", "타입", "PK", "FK"]:
                if current is None or current in columns:
                    raise ValueError(f"칼럼 표의 테이블명을 확인할 수 없습니다: {current}")
                columns[current] = [{"name": r[0], "type": r[1], "pk": r[2] == "O", "fk": r[3] == "O",
                                     "required": r[4] == "O", "description": r[5]} for r in values[1:]]
                ordered_column_tables.append(values)
                current = None
    return entity_rows, entities, relationships, columns, ordered_column_tables


# ── 1. 적용 상태 ───────────────────────────────────────────────────────
AREAS = {
    "여행 일정": ["trips", "itinerary_versions", "itinerary_items", "trip_constraints"],
    "장소": ["places", "place_catalog", "source_sync_state"],
    "예약": ["bookings", "supplier_bookings"],
    "감시": ["watch_observations", "watch_changes", "watch_schedule", "evidences"],
    "알림": ["notifications", "outbox"],
    "사건 코어": ["customer_cases", "case_events", "action_requests", "change_requests", "tenants",
              "customers", "agent_runs", "team_tasks", "action_approvals", "prompts", "llm_calls",
              "feedback_analytics_reports"],
    "업체 실행": ["suppliers", "delegation_scopes", "booking_actions"],
    "지식": ["knowledge_documents", "knowledge_chunks"],
}
#: 로컬 개발 DB(acop_cs) 실측 2026-09-18 — 표 29개 = 이 문서의 구현 표 24 + 커머스 5.
LOCAL_DB_TABLES = 29
COMMERCE_TABLES = 5


def draw_status(entities):
    assigned = [n for names in AREAS.values() for n in names]
    if [n for n, c in Counter(assigned).items() if c != 1] or set(assigned) != set(entities):
        raise ValueError("영역 분류와 문서 엔터티가 일치하지 않습니다")
    labels = list(AREAS)
    count = {s: [sum(entities[n]["status"] == s for n in AREAS[a]) for a in labels]
             for s in ("impl", "design", "absorbed")}
    impl_total = sum(count["impl"])
    if impl_total + COMMERCE_TABLES != LOCAL_DB_TABLES:
        raise ValueError(f"구현 표 {impl_total} + 커머스 {COMMERCE_TABLES} ≠ 로컬 DB {LOCAL_DB_TABLES}")

    fig, ax = plt.subplots(figsize=(6.3, 4.9), dpi=DPI)
    # ★하단 설명이 x축 이름과 겹치지 않게 아래 여백을 넓히고 설명을 위에서 아래로 쓴다(2차 그림의 겹침 수정).
    fig.subplots_adjust(left=0.19, right=0.94, top=0.76, bottom=0.30)
    pos = list(range(len(labels)))
    left = [0] * len(labels)
    for key, color, name in (("impl", BLUE, "마이그레이션 존재"), ("design", ORANGE, "설계만 존재"),
                             ("absorbed", GRAY, "흡수(별도 표 없음)")):
        ax.barh(pos, count[key], left=left, color=color, height=0.65, label=name)
        for y, start, value in zip(pos, left, count[key]):
            if value:
                ax.text(start + value / 2, y, str(value), ha="center", va="center",
                        color="white", weight="bold", fontsize=10)
        left = [a + b for a, b in zip(left, count[key])]
    for y, total in zip(pos, left):
        ax.text(total + 0.16, y, f"{total}개", ha="left", va="center", fontsize=8.5)
    ax.set_yticks(pos, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, max(map(len, AREAS.values())) + 1.3)
    ax.set_xlabel("테이블 수", fontsize=9)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=7))
    ax.grid(axis="x", color="#dedede", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(0.08, 0.94, "영역별 DB 설계·구현 현황", fontsize=15, weight="bold")
    fig.text(0.08, 0.885, f"총 {len(entities)}개 · 마이그레이션 존재 {impl_total}개 · 설계만 존재 "
             f"{sum(count['design'])}개 · 흡수 {sum(count['absorbed'])}개", fontsize=9.5, color=GRAY)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.015), ncol=3, frameon=False, fontsize=8.3,
              borderaxespad=0)
    fig.text(0.08, 0.175, va="top", s=
             AS_OF + "\n"
             f"로컬 개발 DB 표 {LOCAL_DB_TABLES}개 = 마이그레이션 존재 {impl_total} + 커머스 {COMMERCE_TABLES}"
             " · 검증 환경·운영 적용은 미확인\n"
             "분류: 근거는 감시, 변경 요청·분석 보고서는 사건 코어에 포함",
             fontsize=7.8, color=GRAY, linespacing=1.6)
    path = OUTPUT / "DB_적용상태_3차.png"
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


# ── 2. 전체 ERD (graphviz) ─────────────────────────────────────────────
TITLES_ALL = [
    "여행", "일정 버전", "일정 항목", "여행·항목 조건", "내부 장소", "우리 예약", "공급자 예약 원장",
    "장소 카탈로그", "수집 동기화 상태", "감시 관측", "감시 변화", "감시 일정", "고객 지원 사건", "사건 이력",
    "실행 요청", "발송 대기열", "판정 근거", "공급자", "위임 범위", "예약 실행·보상", "변경 접수", "알림",
    "테넌트", "고객", "에이전트 실행", "팀 작업", "실행 승인", "프롬프트", "모델 호출", "지식 문서", "지식 청크",
    "분석 보고서",
]
CORE_FOREIGN_KEYS = {"customers": ["tenant_id"], "agent_runs": ["case_id"], "team_tasks": ["run_id"],
                     "action_approvals": ["action_id"], "llm_calls": ["prompt_id", "run_id"],
                     "knowledge_chunks": ["document_id"]}
LOGICAL = {"R-04", "R-08", "R-09", "R-10", "R-11", "R-17", "R-33"}
ABSORBED_RELATIONS = {"R-03", "R-04"}


def draw_full_erd(entity_rows, relationships, column_tables):
    from graphviz import Digraph

    if len(entity_rows) != 32 or len(column_tables) != 22:
        raise ValueError("DB 설계서의 표 구성이 바뀌었다 — 엔터티·칼럼 대응을 확인한다")
    graph = Digraph("db_erd3", engine="dot", format="png")
    graph.attr(charset="UTF-8", fontname=FONT, fontsize="19", fontcolor="#333333", bgcolor="white",
               dpi="200", rankdir="LR", nodesep="0.35", ranksep="1.0", pad="0.35", splines="polyline",
               labelloc="t",
               label=f"여행 DB 엔터티·관계도\nDB 설계서 3차 기준 · 주요 컬럼과 복합 키 · 문서의 관계 "
                     f"{len(relationships)}개")
    graph.attr("node", fontname=FONT, fontsize="11", shape="box", color=GRAY, fontcolor="#333333",
               margin="0.16,0.10")
    graph.attr("edge", fontname=FONT, fontsize="9", color=BLUE, fontcolor="#333333", arrowsize="0.65")
    names = set()
    for index, row in enumerate(entity_rows):
        status, name, primary_key = row[:3]
        names.add(name)
        kind = status_of(status)
        columns = []
        if index < len(column_tables):
            detail = column_tables[index][1:]
            keys = [r for r in detail if r[2] == "O" or r[3] == "O"]
            others = [r for r in detail if r not in keys and r[0] != "tenant_id"][:4]
            chosen = {r[0] for r in keys + others}
            for col in detail:
                if col[0] in chosen:
                    flags = [f for f, on in (("PK", col[2] == "O"), ("FK", col[3] == "O")) if on]
                    columns.append((f"[{'·'.join(flags)}] " if flags else "") + col[0])
        else:
            columns.append("[PK] " + primary_key)
            columns.extend("[FK] " + k for k in CORE_FOREIGN_KEYS.get(name, []))
            if name == "feedback_analytics_reports":
                columns.append("tenant_id (FK 선언 없음)")
        heading = f"{TITLES_ALL[index]} · {name}" + (" (흡수)" if kind == "absorbed" else "")
        body = "".join(f'<TR><TD ALIGN="LEFT">{escape(c)}</TD></TR>' for c in columns)
        label = ('<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3">'
                 f'<TR><TD BGCOLOR="{LIGHT}"><B>{escape(heading)}</B></TD></TR>{body}</TABLE>>')
        graph.node(name, label=label, penwidth="1.5",
                   style={"impl": "solid", "design": "dotted", "absorbed": "dashed"}[kind],
                   color=BLUE if kind == "impl" else GRAY)
    for rid, rel in relationships.items():
        parent, child, description = rel["parent"], rel["child"], rel["description"]
        if parent not in names or child not in names:
            raise ValueError(f"관계의 엔터티를 찾지 못했습니다: {rid}")
        if rid in {"R-09", "R-11"}:
            card, tail, head = "N:M", "0..N", "0..N"
        elif rid == "R-19":
            card, tail, head = "1:1", "0..1", "0..1"
        else:
            card, tail, head = "1:N", ("0..1" if description.startswith("0..1") else "1"), "0..N"
        logical = rid in LOGICAL
        proposed = "(제안)" in description
        kind = "논리·FK 없음" if logical else ("제안 FK" if proposed else "FK")
        if rid in ABSORBED_RELATIONS:
            kind = "흡수·표 없음"
        graph.edge(parent, child, label=f"{rid}  {card}\n{kind}", taillabel=tail, headlabel=head,
                   labeldistance="1.5", color=GRAY if logical or rid in ABSORBED_RELATIONS else BLUE,
                   style="dotted" if logical else ("dashed" if proposed else "solid"), tooltip=description)
    with graph.subgraph(name="cluster_legend") as legend:
        legend.attr(label="범례·해석", color=GRAY, fontname=FONT, fontsize="12")
        legend.node("legend_implemented", "실선 테두리: 구현 파일 존재", color=BLUE)
        legend.node("legend_design", "점선 테두리: 설계만 존재", style="dotted")
        legend.node("legend_absorbed", "파선 테두리: 흡수(별도 표 없음)", style="dashed")
        legend.node("legend_notes",
                    "PK: 기본 키 · FK: 외래 키 (제안 포함)\n"
                    "관계선: 실선=구현 FK / 파선=제안 FK / 점선=논리 참조\n"
                    "1:N 등은 최대 관계 수, 양 끝 숫자는 선택성 포함\n"
                    "복합 PK·FK는 여러 컬럼에 함께 표시\n"
                    "구현 파일 존재 표는 로컬 개발 DB에 있음 · 검증 환경 적용은 미확인\n"
                    "일정 조건은 표 없이 trips.constraints · itinerary_items.detail 에 둔다",
                    shape="note", fontsize="10")
    path = OUTPUT / "DB_ERD_전체_3차.png"
    path.write_bytes(graph.pipe(format="png"))
    return path


# ── 3. 여행 핵심 ERD (matplotlib) ───────────────────────────────────────
TITLES = {
    "trips": "여행 정본", "itinerary_versions": "일정 버전", "itinerary_items": "일정 항목",
    "watch_schedule": "감시 일정", "watch_observations": "대상 관측", "watch_changes": "관측 변화",
    "change_requests": "사건·변경 요청", "evidences": "판정 근거", "notifications": "변경 통지·예정 안내",
    "outbox": "발송 대기 메시지",
}
ROUTE_RELATION = {1: "R-01", 2: "R-02", 6: "R-12", 7: "R-13", 8: "R-18", 9: "R-19", 10: "R-20"}


def draw_core_erd(entities, relationships, columns):
    if not set(TITLES).issubset(columns):
        raise ValueError("핵심 10개 테이블의 컬럼 정의를 모두 읽지 못했습니다")
    implemented_route = {n for n, rid in ROUTE_RELATION.items()
                         if "(제안)" not in relationships[rid]["description"]}
    width, height = 12.4, 14.8
    font_size, box_width = 14, 2.66
    header_height, line_height, bottom_padding, gap = 0.54, 0.21, 0.02, 0.32
    layout = [["itinerary_versions", "itinerary_items"],
              ["trips", "watch_schedule", "evidences"],
              ["notifications", "outbox"],
              ["watch_observations", "watch_changes", "change_requests"]]
    fig = plt.figure(figsize=(width, height), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)
    ax.axis("off")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    def text_width(value, bold=False):
        prop = font_manager.FontProperties(family=FONT, size=font_size, weight="bold" if bold else "normal")
        return renderer.get_text_width_height_descent(value, prop, False)[0] / DPI

    def wrap_name(value, available, bold=False):
        lines, line = [], ""
        for part in re.findall(r"[^_]+_?", value):
            if line and text_width(line + part, bold) > available:
                lines.append(line)
                line = ""
            for char in part:
                if line and text_width(line + char, bold) > available:
                    lines.append(line)
                    line = ""
                line += char
        if line:
            lines.append(line)
        return lines

    boxes, rows = {}, {}
    for col_index, names in enumerate(layout):
        x, y = 0.28 + col_index * 3.06, 0.90
        for name in names:
            table_rows = [(c, wrap_name(c["name"], box_width - 0.72, c["pk"])) for c in columns[name]]
            table_rows = [(c, lines, len(lines) * line_height) for c, lines in table_rows]
            h = header_height + sum(r[2] for r in table_rows) + bottom_padding
            boxes[name] = dict(x=x, y=y, w=box_width, h=h)
            rows[name] = table_rows
            y += h + gap
    bottom = max(b["y"] + b["h"] for b in boxes.values())
    footer_y = bottom + 0.64
    if footer_y + 2.73 > height - 0.12:
        plt.close(fig)
        raise RuntimeError("전체 컬럼이 목표 높이를 넘습니다")

    ax.text(0.28, 0.12, "여행 일정·감시·알림 핵심 관계", fontsize=22, weight="bold", va="top")
    ax.text(0.28, 0.49, "10개 테이블 · 전체 컬럼 · 기본키와 외래키", fontsize=14, color=GRAY, va="top")
    ax.text(6.40, 0.49, "파랑: 마이그레이션 존재   주황: 설계만 존재", fontsize=14, color=GRAY, va="top")

    def point(name, side, fraction=0.5):
        b = boxes[name]
        return {"top": (b["x"] + b["w"] * fraction, b["y"]),
                "bottom": (b["x"] + b["w"] * fraction, b["y"] + b["h"]),
                "left": (b["x"], b["y"] + b["h"] * fraction),
                "right": (b["x"] + b["w"], b["y"] + b["h"] * fraction)}[side]

    routes = []

    def connect(points, number, logical=False, label_segment=0):
        routes.append((points, number, logical, label_segment))

    def vertical(parent, child, number, logical=False, fraction=0.5):
        connect([point(parent, "bottom", fraction), point(child, "top", fraction)], number, logical)

    a, b = point("trips", "left", 0.18), point("itinerary_versions", "right", 0.30)
    lane = (a[0] + b[0]) / 2
    connect([a, (lane, a[1]), (lane, b[1]), b], 1, label_segment=1)
    vertical("itinerary_versions", "itinerary_items", 2)
    vertical("watch_observations", "watch_changes", 5, logical=True)
    vertical("trips", "watch_schedule", 6)
    a, b = point("trips", "right", 0.72), point("change_requests", "bottom", 0.25)
    connect([a, (6.10, a[1]), (6.10, bottom + 0.18), (b[0], bottom + 0.18), b], 7, label_segment=2)
    a, b = point("trips", "right", 0.20), point("notifications", "left", 0.12)
    connect([a, (6.28, a[1]), (6.28, b[1]), b], 8, label_segment=1)
    vertical("notifications", "outbox", 9)
    a, b = point("change_requests", "bottom", 0.75), point("evidences", "right", 0.70)
    connect([a, (a[0], bottom + 0.42), (6.24, bottom + 0.42), (6.24, b[1]), b], 10, label_segment=1)
    a, b = point("watch_observations", "right", 0.35), point("change_requests", "right", 0.18)
    connect([a, (12.28, a[1]), (12.28, b[1]), b], 11, label_segment=1)
    vertical("watch_changes", "change_requests", 12)

    for points, number, logical, segment in routes:
        for p, q in zip(points, points[1:]):
            if p[0] != q[0] and p[1] != q[1]:
                raise RuntimeError(f"직교하지 않는 관계선: {number}")
            for box in boxes.values():
                l, r, t, lo, eps = box["x"], box["x"] + box["w"], box["y"], box["y"] + box["h"], 1e-8
                if abs(p[0] - q[0]) < eps:
                    hit = l + eps < p[0] < r - eps and max(min(p[1], q[1]), t) < min(max(p[1], q[1]), lo) - eps
                else:
                    hit = t + eps < p[1] < lo - eps and max(min(p[0], q[0]), l) < min(max(p[0], q[0]), r) - eps
                if hit:
                    raise RuntimeError(f"관계선이 표를 가로지릅니다: {number}")
        if logical:
            color, style = GRAY, (0, (1.1, 2.1))
        elif number in implemented_route:
            color, style = BLUE, "solid"
        else:
            color, style = ORANGE, (0, (4, 2))
        xs, ys = zip(*points)
        ax.plot(xs, ys, color=color, linewidth=1.2, linestyle=style, solid_capstyle="butt", zorder=1)
        ax.add_patch(FancyArrowPatch(points[-2], points[-1], arrowstyle="-|>", mutation_scale=14,
                                     shrinkA=0, shrinkB=0, color=color, linewidth=0, zorder=2))
        p, q = points[segment:segment + 2]
        ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, str(number), fontsize=14, color=color,
                ha="center", va="center", zorder=5, bbox=dict(facecolor="white", edgecolor="none", pad=0.4))

    fitted = []
    for name, box in boxes.items():
        x, y, w, h = (box[k] for k in ("x", "y", "w", "h"))
        color = BLUE if entities[name]["status"] == "impl" else ORANGE
        ax.add_patch(Rectangle((x, y), w, h, facecolor="white", edgecolor=color, linewidth=1.2, zorder=3))
        ax.add_patch(Rectangle((x, y), w, header_height, facecolor=color, edgecolor="none", zorder=3))
        for value, ty, bold in ((TITLES[name], y + 0.15, True), (name, y + 0.40, False)):
            fitted.append((ax.text(x + 0.07, ty, value, fontsize=14, weight="bold" if bold else "normal",
                                   color="white", va="center", zorder=4), x + w - 0.06))
        row_y = y + header_height
        for index, (column, lines, row_h) in enumerate(rows[name]):
            if index % 2 == 0:
                ax.add_patch(Rectangle((x + 0.007, row_y), w - 0.014, row_h, facecolor=LIGHT,
                                       edgecolor="none", zorder=3))
            for li, line in enumerate(lines):
                fitted.append((ax.text(x + 0.07, row_y + (li + 0.5) * line_height, line, fontsize=font_size,
                                       va="center", zorder=4, weight="bold" if column["pk"] else "normal"),
                               x + w - 0.60))
            marks = "/".join(m for m, on in (("PK", column["pk"]), ("FK", column["fk"])) if on)
            ax.text(x + w - 0.05, row_y + row_h / 2, marks, fontsize=14, ha="right", va="center",
                    color=color, weight="bold", zorder=4)
            row_y += row_h

    ax.text(0.28, footer_y, "관계 읽기", fontsize=16, weight="bold", va="top")
    legend_y = footer_y + 0.35
    for x0, color, style, label in ((0.30, BLUE, "solid", "구현 외래키"),
                                    (2.45, ORANGE, (0, (4, 2)), "제안 외래키"),
                                    (4.75, GRAY, (0, (1.1, 2.1)), "논리 관계")):
        ax.plot([x0, x0 + 0.38], [legend_y] * 2, color=color, linestyle=style, linewidth=1.2)
        ax.text(x0 + 0.45, legend_y, label, fontsize=14, va="center")
    ax.text(7.00, legend_y, "화살표: 주체 → 연결 대상", fontsize=14, va="center")
    explanations = [
        ("1  여행 → 버전: 1 대 0개 이상", "7  여행 → 요청: 1 대 0개 이상"),
        ("2  버전 → 항목: 1 대 0개 이상", "8  여행 → 알림: 1 대 0개 이상"),
        ("5  관측 ↔ 변화: 양쪽 모두 0개 이상", "9  알림 ↔ 발송: 양쪽 모두 0개 또는 1개"),
        ("6  여행 → 감시: 1 대 0개 이상", "10  요청 → 근거: 1 대 0개 이상"),
        ("", "11  관측 → 요청: 0개 또는 1개 대 0개 이상"),
        ("", "12  변화 → 요청: 0개 또는 1개 대 0개 이상"),
    ]
    for index, pair in enumerate(explanations):
        y = footer_y + 0.64 + index * 0.22
        for x, value in zip((0.28, 6.40), pair):
            if value:
                fitted.append((ax.text(x, y, value, fontsize=14, va="center"), x + 5.72))
    notes = [
        "PK: 기본키 · FK: 외래키 · 같은 표의 여러 PK는 복합키 · 11·12는 컬럼 정의의 제안 FK",
        "일정 조건은 별도 표 없이 trips.constraints · itinerary_items.detail(jsonb)에 둔다 — 그림에서 뺐다",
        "외부 참조: 여행의 고객, 항목의 예약·장소, 요청의 사건은 그림 범위 밖",
        "파랑 표는 로컬 개발 DB에 있다 · 검증 환경 적용은 미확인 · 관측과 변화 사이에는 직접 FK가 없음",
    ]
    for index, value in enumerate(notes):
        fitted.append((ax.text(0.28, footer_y + 1.95 + index * 0.22, value, fontsize=14, color=GRAY,
                               va="center"), width - 0.28))

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for t, right_limit in fitted:
        extent = t.get_window_extent(renderer)
        if extent.x1 > ax.transData.transform((right_limit, 0))[0] + 0.5:
            plt.close(fig)
            raise RuntimeError(f"글자가 배정 폭을 넘었습니다: {t.get_text()}")
        if extent.y0 < 0 or extent.y1 > fig.bbox.height:
            plt.close(fig)
            raise RuntimeError(f"글자가 캔버스를 넘었습니다: {t.get_text()}")
    if len(boxes) != 10 or len(routes) != 10:
        raise RuntimeError("테이블 또는 관계 수가 예상과 다릅니다")
    path = OUTPUT / "DB_ERD_여행핵심_3차.png"
    try:
        fig.savefig(path, dpi=DPI)
    finally:
        plt.close(fig)
    return path


def main():
    font_manager.findfont(font_manager.FontProperties(family=FONT), fallback_to_default=False)
    if not SOURCE.is_file():
        raise FileNotFoundError(f"본문판이 없다 — build_DB설계서_3차_여행.py --text-only 를 먼저: {SOURCE}")
    entity_rows, entities, relationships, columns, column_tables = read_document()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for made in (draw_status(entities), draw_full_erd(entity_rows, relationships, column_tables),
                 draw_core_erd(entities, relationships, columns)):
        print("저장:", made)


if __name__ == "__main__":
    main()

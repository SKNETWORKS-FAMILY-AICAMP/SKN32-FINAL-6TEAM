from pathlib import Path
import os

GRAPHVIZ_BIN = Path(r"C:\Program Files\Graphviz\bin")
if GRAPHVIZ_BIN.is_dir():
    os.environ["PATH"] = str(GRAPHVIZ_BIN) + os.pathsep + os.environ.get("PATH", "")

import re
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle, FancyArrowPatch
from matplotlib.ticker import MaxNLocator
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


ROOT = Path.cwd()
SOURCE = ROOT / (
    "program/산출물양식/w2/제출본/"
    "[데이터 수집 및 저장] DB_저장소 설계 문서_2차_여행.docx"
)
OUTPUT = ROOT / "program/산출물양식/w2/표와시각자료/코덱스"

BLUE = "#2a78d6"
ORANGE = "#eb6834"
GRAY = "#757575"
INK = "#303030"
LIGHT = "#f3f3f3"
DPI = 200

plt.rcParams.update({
    "font.family": "Malgun Gothic",
    "axes.unicode_minus": False,
    "font.size": 9,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
})


def clean(value):
    return re.sub(r"\s+", " ", value).strip()


def rows_of(table):
    return [[clean(cell.text) for cell in row.cells] for row in table.rows]


def find_table(document, prefix):
    matches = [
        table for table in document.tables
        if rows_of(table)[0][:len(prefix)] == prefix
    ]
    if len(matches) != 1:
        raise ValueError(f"표를 하나로 식별할 수 없습니다: {prefix}")
    return matches[0]


def read_document():
    if not SOURCE.is_file():
        raise FileNotFoundError(f"워크스페이스 루트에서 실행하세요: {SOURCE}")

    document = Document(SOURCE)
    entity_table = find_table(document, ["구분", "테이블", "제약 대상"])
    relationship_table = find_table(document, ["관계명", "주 엔터티", "종 엔터티"])

    entities = {}
    for row in rows_of(entity_table)[1:]:
        status, name = row[:2]
        if name in entities:
            raise ValueError(f"중복 엔터티: {name}")
        if "설계만 존재" in status:
            implemented = False
        elif "구현 파일 존재" in status:
            implemented = True
        else:
            raise ValueError(f"해석할 수 없는 상태: {name}: {status}")
        entities[name] = {"implemented": implemented, "row": row}

    relationships = {}
    for row in rows_of(relationship_table)[1:]:
        identifier, parent, child, description = row
        relationships[identifier] = {
            "parent": parent.split()[-1],
            "child": child.split()[-1],
            "description": description,
        }

    # 문단의 테이블명과 바로 뒤 컬럼 정의 표를 연결한다.
    # 표 번호를 고정하지 않아 표지나 앞부분 표가 추가되어도 읽을 수 있다.
    columns = {}
    current_name = None
    for block in document.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(block, document)
            match = re.search(r"테이블\s*:\s*([A-Za-z_][A-Za-z_0-9]*)",
                              paragraph.text)
            if match:
                current_name = match.group(1)
        elif tag == "tbl":
            table = Table(block, document)
            values = rows_of(table)
            if values[0][:4] == ["컬럼명", "타입", "PK", "FK"]:
                if current_name is None:
                    raise ValueError("컬럼 정의 표에 대응하는 테이블명이 없습니다.")
                if current_name in columns:
                    raise ValueError(f"중복 컬럼 정의: {current_name}")
                columns[current_name] = [
                    {
                        "name": row[0],
                        "type": row[1],
                        "pk": row[2] == "O",
                        "fk": row[3] == "O",
                        "required": row[4] == "O",
                        "description": row[5],
                    }
                    for row in values[1:]
                ]
                current_name = None

    return entities, relationships, columns


AREAS = {
    "여행 일정": [
        "trips", "itinerary_versions", "itinerary_items", "trip_constraints",
    ],
    "장소": ["places", "place_catalog", "source_sync_state"],
    "예약": ["bookings", "supplier_bookings"],
    "감시": [
        "watch_observations", "watch_changes", "watch_schedule", "evidences",
    ],
    "알림": ["notifications", "outbox"],
    "사건 코어": [
        "customer_cases", "case_events", "action_requests", "change_requests",
        "tenants", "customers", "agent_runs", "team_tasks",
        "action_approvals", "prompts", "llm_calls", "feedback_analytics_reports",
    ],
    "업체 실행": ["suppliers", "delegation_scopes", "booking_actions"],
    "지식": ["knowledge_documents", "knowledge_chunks"],
}

TITLES = {
    "trips": "여행 정본",
    "itinerary_versions": "일정 버전",
    "itinerary_items": "일정 항목",
    "trip_constraints": "일정 조건",
    "watch_schedule": "감시 일정",
    "watch_observations": "대상 관측",
    "watch_changes": "관측 변화",
    "change_requests": "사건·변경 요청",
    "evidences": "판정 근거",
    "notifications": "변경 통지·예정 안내",
    "outbox": "발송 대기 메시지",
}


def validate(entities, relationships, columns):
    assigned = [name for names in AREAS.values() for name in names]
    duplicates = [name for name, count in Counter(assigned).items() if count != 1]
    if duplicates or set(assigned) != set(entities):
        raise ValueError(
            "영역 분류와 문서 엔터티가 일치하지 않습니다. "
            f"중복={duplicates}, "
            f"미분류={sorted(set(entities) - set(assigned))}, "
            f"문서에 없음={sorted(set(assigned) - set(entities))}"
        )
    if len(entities) != 32:
        raise ValueError(f"예상 엔터티 32개와 다릅니다: {len(entities)}")
    if len(TITLES) != 11 or not set(TITLES).issubset(columns):
        raise ValueError("핵심 11개 테이블의 컬럼 정의를 모두 읽지 못했습니다.")

    expected_relations = {
        "R-01": ("trips", "itinerary_versions"),
        "R-02": ("itinerary_versions", "itinerary_items"),
        "R-03": ("itinerary_versions", "trip_constraints"),
        "R-04": ("itinerary_items", "trip_constraints"),
        "R-11": ("watch_observations", "watch_changes"),
        "R-12": ("trips", "watch_schedule"),
        "R-13": ("trips", "change_requests"),
        "R-18": ("trips", "notifications"),
        "R-19": ("notifications", "outbox"),
        "R-20": ("change_requests", "evidences"),
    }
    for identifier, pair in expected_relations.items():
        relation = relationships.get(identifier)
        if relation is None or (relation["parent"], relation["child"]) != pair:
            raise ValueError(f"관계 표 확인이 필요합니다: {identifier}")

    # 관계 표에 별도 행이 없는 두 연결은 컬럼 정의의 FK를 근거로 추가한다.
    request_columns = {c["name"]: c for c in columns["change_requests"]}
    for field, target in [
        ("observation_id", "watch_observations.observation_id"),
        ("change_id", "watch_changes.change_id"),
    ]:
        column = request_columns[field]
        if not column["fk"] or target not in column["description"]:
            raise ValueError(f"변경 요청의 제안 FK를 확인할 수 없습니다: {field}")


def draw_status(entities):
    labels = list(AREAS)
    implemented = [
        sum(entities[name]["implemented"] for name in AREAS[label])
        for label in labels
    ]
    design_only = [
        len(AREAS[label]) - count
        for label, count in zip(labels, implemented)
    ]

    fig, ax = plt.subplots(figsize=(6.3, 4.5), dpi=DPI)
    fig.subplots_adjust(left=0.19, right=0.94, top=0.77, bottom=0.24)

    positions = list(range(len(labels)))
    ax.barh(positions, implemented, color=BLUE, height=0.65,
            label="마이그레이션 존재")
    ax.barh(positions, design_only, left=implemented, color=ORANGE,
            height=0.65, label="설계만 존재")

    for y, present, planned in zip(positions, implemented, design_only):
        if present:
            ax.text(present / 2, y, str(present), ha="center", va="center",
                    color="white", weight="bold", fontsize=10)
        if planned:
            ax.text(present + planned / 2, y, str(planned),
                    ha="center", va="center", color="white",
                    weight="bold", fontsize=10)
        ax.text(present + planned + 0.16, y, f"{present + planned}개",
                ha="left", va="center", fontsize=8.5)

    ax.set_yticks(positions, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, max(map(len, AREAS.values())) + 1.3)
    ax.set_xlabel("테이블 수", fontsize=9)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=7))
    ax.grid(axis="x", color="#dedede", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.text(0.08, 0.94, "영역별 DB 설계·구현 현황",
             fontsize=15, weight="bold")
    fig.text(
        0.08, 0.885,
        f"총 {len(entities)}개 · 마이그레이션 존재 {sum(implemented)}개"
        f" · 설계만 존재 {sum(design_only)}개",
        fontsize=9.5, color=GRAY,
    )
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.015),
              ncol=2, frameon=False, fontsize=8.5, borderaxespad=0)

    fig.text(
        0.08, 0.115,
        "문서 기준: 2026-09-10 · 마이그레이션 001-013\n"
        "파일 존재 기준이며 실제 DB 적용 여부는 미확인\n"
        "분류: 근거는 감시, 변경 요청·분석 보고서는 사건 코어에 포함",
        fontsize=8, color=GRAY, linespacing=1.65,
    )
    fig.savefig(OUTPUT / "DB_적용상태_코덱스.png", dpi=DPI)
    plt.close(fig)


def draw_erd(entities, relationships, columns):
    # 2480 x 2960 px, 200 dpi. 6.2인치 삽입 시 14pt -> 7pt.
    width, height = 12.4, 14.8
    font_size = 14
    box_width = 2.66
    header_height, line_height = 0.54, 0.21
    bottom_padding, gap = 0.02, 0.32
    layout = [
        ["itinerary_versions", "itinerary_items", "trip_constraints"],
        ["trips", "watch_schedule", "evidences"],
        ["notifications", "outbox"],
        ["watch_observations", "watch_changes", "change_requests"],
    ]

    fig = plt.figure(figsize=(width, height), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)
    ax.axis("off")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    def text_width(value, bold=False):
        prop = font_manager.FontProperties(
            family="Malgun Gothic", size=font_size,
            weight="bold" if bold else "normal",
        )
        return renderer.get_text_width_height_descent(
            value, prop, False
        )[0] / DPI

    def wrap_name(value, available, bold=False):
        # 밑줄을 보존하며 줄바꿈한다. 원래 컬럼명은 생략하지 않는다.
        lines, line = [], ""
        parts = re.findall(r"[^_]+_?", value)
        for part in parts:
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
        x = 0.28 + col_index * 3.06
        y = 0.90
        for name in names:
            table_rows = []
            for column in columns[name]:
                lines = wrap_name(
                    column["name"], box_width - 0.72, column["pk"]
                )
                table_rows.append(
                    (column, lines, len(lines) * line_height)
                )
            h = (
                header_height
                + sum(row[2] for row in table_rows)
                + bottom_padding
            )
            boxes[name] = dict(x=x, y=y, w=box_width, h=h)
            rows[name] = table_rows
            y += h + gap

    bottom = max(b["y"] + b["h"] for b in boxes.values())
    footer_y = bottom + 0.64
    if footer_y + 2.73 > height - 0.12:
        plt.close(fig)
        raise RuntimeError(
            "전체 컬럼이 목표 높이를 넘습니다. 데이터 변경을 확인하세요."
        )

    ax.text(
        0.28, 0.12, "여행 일정·감시·알림 핵심 관계",
        fontsize=22, weight="bold", va="top",
    )
    ax.text(
        0.28, 0.49, "11개 테이블 · 전체 컬럼 · 기본키와 외래키",
        fontsize=14, color=GRAY, va="top",
    )
    ax.text(
        6.40, 0.49, "파랑: 마이그레이션 존재   주황: 설계만 존재",
        fontsize=14, color=GRAY, va="top",
    )

    def point(name, side, fraction=0.5):
        b = boxes[name]
        if side == "top":
            return b["x"] + b["w"] * fraction, b["y"]
        if side == "bottom":
            return b["x"] + b["w"] * fraction, b["y"] + b["h"]
        if side == "left":
            return b["x"], b["y"] + b["h"] * fraction
        return b["x"] + b["w"], b["y"] + b["h"] * fraction

    routes = []

    def connect(points, number, logical=False, label_segment=0):
        routes.append((points, number, logical, label_segment))

    def vertical(parent, child, number, logical=False, fraction=0.5):
        connect(
            [
                point(parent, "bottom", fraction),
                point(child, "top", fraction),
            ],
            number, logical,
        )

    def across(parent, child, number, parent_fraction, child_fraction):
        a = point(parent, "left", parent_fraction)
        b = point(child, "right", child_fraction)
        lane = (a[0] + b[0]) / 2
        connect(
            [a, (lane, a[1]), (lane, b[1]), b],
            number, label_segment=1,
        )

    across("trips", "itinerary_versions", 1, 0.18, 0.30)
    vertical("itinerary_versions", "itinerary_items", 2)

    a = point("itinerary_versions", "left", 0.65)
    b = point("trip_constraints", "left", 0.20)
    connect(
        [a, (0.12, a[1]), (0.12, b[1]), b],
        3, label_segment=1,
    )

    vertical("itinerary_items", "trip_constraints", 4, logical=True)
    vertical("watch_observations", "watch_changes", 5, logical=True)
    vertical("trips", "watch_schedule", 6)

    a = point("trips", "right", 0.72)
    b = point("change_requests", "bottom", 0.25)
    connect(
        [
            a,
            (6.10, a[1]),
            (6.10, bottom + 0.18),
            (b[0], bottom + 0.18),
            b,
        ],
        7, label_segment=2,
    )

    a = point("trips", "right", 0.20)
    b = point("notifications", "left", 0.12)
    connect(
        [a, (6.28, a[1]), (6.28, b[1]), b],
        8, label_segment=1,
    )

    vertical("notifications", "outbox", 9)

    a = point("change_requests", "bottom", 0.75)
    b = point("evidences", "right", 0.70)
    connect(
        [
            a,
            (a[0], bottom + 0.42),
            (6.24, bottom + 0.42),
            (6.24, b[1]),
            b,
        ],
        10, label_segment=1,
    )

    a = point("watch_observations", "right", 0.35)
    b = point("change_requests", "right", 0.18)
    connect(
        [a, (12.28, a[1]), (12.28, b[1]), b],
        11, label_segment=1,
    )

    vertical("watch_changes", "change_requests", 12)

    # 모든 선분이 표 내부를 통과하지 않는지 검사한다.
    for points, number, logical, segment in routes:
        for a, b in zip(points, points[1:]):
            if a[0] != b[0] and a[1] != b[1]:
                raise RuntimeError(f"직교하지 않는 관계선: {number}")

            for box in boxes.values():
                left, right = box["x"], box["x"] + box["w"]
                top, low = box["y"], box["y"] + box["h"]
                eps = 1e-8

                if abs(a[0] - b[0]) < eps:
                    hit = (
                        left + eps < a[0] < right - eps
                        and max(min(a[1], b[1]), top)
                        < min(max(a[1], b[1]), low) - eps
                    )
                else:
                    hit = (
                        top + eps < a[1] < low - eps
                        and max(min(a[0], b[0]), left)
                        < min(max(a[0], b[0]), right) - eps
                    )

                if hit:
                    raise RuntimeError(
                        f"관계선이 표를 가로지릅니다: {number}"
                    )

        color = GRAY if logical else ORANGE
        style = (0, (1.1, 2.1)) if logical else (0, (4, 2))
        xs, ys = zip(*points)

        ax.plot(
            xs, ys, color=color, linewidth=1.2, linestyle=style,
            solid_capstyle="butt", zorder=1,
        )
        ax.add_patch(FancyArrowPatch(
            points[-2], points[-1],
            arrowstyle="-|>", mutation_scale=14,
            shrinkA=0, shrinkB=0,
            color=color, linewidth=0, zorder=2,
        ))

        a, b = points[segment:segment + 2]
        ax.text(
            (a[0] + b[0]) / 2,
            (a[1] + b[1]) / 2,
            str(number),
            fontsize=14, color=color,
            ha="center", va="center", zorder=5,
            bbox=dict(facecolor="white", edgecolor="none", pad=0.4),
        )

    fitted = []
    for name, box in boxes.items():
        x, y, w, h = (box[k] for k in ("x", "y", "w", "h"))
        color = BLUE if entities[name]["implemented"] else ORANGE

        ax.add_patch(Rectangle(
            (x, y), w, h,
            facecolor="white", edgecolor=color,
            linewidth=1.2, zorder=3,
        ))
        ax.add_patch(Rectangle(
            (x, y), w, header_height,
            facecolor=color, edgecolor="none", zorder=3,
        ))

        for text_value, text_y, bold in [
            (TITLES[name], y + 0.15, True),
            (name, y + 0.40, False),
        ]:
            t = ax.text(
                x + 0.07, text_y, text_value,
                fontsize=14,
                weight="bold" if bold else "normal",
                color="white", va="center", zorder=4,
            )
            fitted.append((t, x + w - 0.06))

        row_y = y + header_height
        for index, (column, lines, row_h) in enumerate(rows[name]):
            if index % 2 == 0:
                ax.add_patch(Rectangle(
                    (x + 0.007, row_y), w - 0.014, row_h,
                    facecolor=LIGHT, edgecolor="none", zorder=3,
                ))

            for line_index, line in enumerate(lines):
                t = ax.text(
                    x + 0.07,
                    row_y + (line_index + 0.5) * line_height,
                    line,
                    fontsize=font_size, va="center", zorder=4,
                    weight="bold" if column["pk"] else "normal",
                )
                fitted.append((t, x + w - 0.60))

            marks = "/".join(
                mark
                for mark, present in [
                    ("PK", column["pk"]),
                    ("FK", column["fk"]),
                ]
                if present
            )
            ax.text(
                x + w - 0.05, row_y + row_h / 2, marks,
                fontsize=14, ha="right", va="center",
                color=color, weight="bold", zorder=4,
            )
            row_y += row_h

    ax.text(
        0.28, footer_y, "관계 읽기",
        fontsize=16, weight="bold", va="top",
    )

    legend_y = footer_y + 0.35
    ax.plot(
        [1.65, 2.03], [legend_y] * 2,
        color=ORANGE, linestyle=(0, (4, 2)), linewidth=1.2,
    )
    ax.text(
        2.10, legend_y, "제안 외래키",
        fontsize=14, va="center",
    )
    ax.plot(
        [4.10, 4.48], [legend_y] * 2,
        color=GRAY, linestyle=(0, (1.1, 2.1)), linewidth=1.2,
    )
    ax.text(
        4.55, legend_y, "논리 관계",
        fontsize=14, va="center",
    )
    ax.text(
        7.00, legend_y, "화살표: 주체 → 연결 대상",
        fontsize=14, va="center",
    )

    explanations = [
        (
            "1  여행 → 버전: 1 대 0개 이상",
            "7  여행 → 요청: 1 대 0개 이상",
        ),
        (
            "2  버전 → 항목: 1 대 0개 이상",
            "8  여행 → 알림: 1 대 0개 이상",
        ),
        (
            "3  버전 → 조건: 1 대 0개 이상",
            "9  알림 ↔ 발송: 양쪽 모두 0개 또는 1개",
        ),
        (
            "4  항목 → 조건: 0개 또는 1개 대 0개 이상",
            "10  요청 → 근거: 1 대 0개 이상",
        ),
        (
            "5  관측 ↔ 변화: 양쪽 모두 0개 이상",
            "11  관측 → 요청: 0개 또는 1개 대 0개 이상",
        ),
        (
            "6  여행 → 감시: 1 대 0개 이상",
            "12  변화 → 요청: 0개 또는 1개 대 0개 이상",
        ),
    ]

    for index, pair in enumerate(explanations):
        y = footer_y + 0.64 + index * 0.22
        for x, value in zip((0.28, 6.40), pair):
            t = ax.text(x, y, value, fontsize=14, va="center")
            fitted.append((t, x + 5.72))

    # 원본 범례의 네 문장을 유지한다.
    note_y = footer_y + 1.95
    notes = [
        "PK: 기본키 · FK: 외래키 · 같은 표의 여러 PK는 복합키",
        "11·12는 컬럼 정의의 제안 FK이며, 나머지 연결은 관계 표 기준",
        "외부 참조: 여행의 고객, 항목의 예약·장소, 요청의 사건은 그림 범위 밖",
        "관측과 변화 사이에는 직접 FK가 없음 · 마이그레이션의 실제 DB 적용은 미확인",
    ]
    for index, value in enumerate(notes):
        t = ax.text(
            0.28, note_y + index * 0.22, value,
            fontsize=14, color=GRAY, va="center",
        )
        fitted.append((t, width - 0.28))

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for t, right_limit in fitted:
        extent = t.get_window_extent(renderer)
        limit_px = ax.transData.transform((right_limit, 0))[0]
        if extent.x1 > limit_px + 0.5:
            plt.close(fig)
            raise RuntimeError(
                f"글자가 배정 폭을 넘었습니다: {t.get_text()}"
            )
        if extent.y0 < 0 or extent.y1 > fig.bbox.height:
            plt.close(fig)
            raise RuntimeError(
                f"글자가 캔버스를 넘었습니다: {t.get_text()}"
            )

    if len(boxes) != 11 or len(routes) != 12:
        raise RuntimeError("테이블 또는 관계 수가 원본과 다릅니다.")

    try:
        fig.savefig(OUTPUT / "DB_ERD_여행핵심_코덱스.png", dpi=DPI)
    finally:
        plt.close(fig)


def main():
    font_manager.findfont(
        font_manager.FontProperties(family="Malgun Gothic"),
        fallback_to_default=False,
    )
    entities, relationships, columns = read_document()
    validate(entities, relationships, columns)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # 실행 대상만 ERD로 제한한다. draw_status 함수는 원본 그대로 보존한다.
    draw_erd(entities, relationships, columns)


if __name__ == "__main__":
    main()
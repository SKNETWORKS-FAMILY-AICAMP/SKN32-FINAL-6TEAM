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

# 전체 컬럼의 가독성을 유지하도록 ERD 높이는 늘리고 폭은 6.3인치로 고정한다.
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
    width = 6.3
    box_width = 2.56
    left_x, right_x = 0.29, 3.45
    header_height = 0.57
    row_height = 0.19
    bottom_padding = 0.07
    gap = 0.52

    layout = [
        ("trips", "watch_schedule"),
        ("itinerary_versions", "notifications"),
        ("itinerary_items", "outbox"),
        ("trip_constraints", "evidences"),
        ("watch_observations", "change_requests"),
        ("watch_changes", None),
    ]
    boxes = {}
    cursor = 1.35
    for left, right in layout:
        heights = []
        for name, x in [(left, left_x), (right, right_x)]:
            if name is None:
                continue
            height = header_height + len(columns[name]) * row_height + bottom_padding
            boxes[name] = {"x": x, "y": cursor, "w": box_width, "h": height}
            heights.append(height)
        cursor += max(heights) + gap

    height = cursor + 2.15
    fig = plt.figure(figsize=(width, height), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)
    ax.axis("off")

    ax.text(0.29, 0.28, "여행 일정·감시·알림 핵심 관계",
            fontsize=14, weight="bold", va="top")
    ax.text(0.29, 0.66, "11개 테이블 · 전체 컬럼 · 기본키와 외래키",
            fontsize=9, color=GRAY, va="top")
    ax.text(0.29, 0.95, "파랑: 마이그레이션 존재   주황: 설계만 존재",
            fontsize=8, color=GRAY, va="top")

    def point(name, side, fraction=0.5):
        b = boxes[name]
        if side == "top":
            return b["x"] + b["w"] * fraction, b["y"]
        if side == "bottom":
            return b["x"] + b["w"] * fraction, b["y"] + b["h"]
        if side == "left":
            return b["x"], b["y"] + b["h"] * fraction
        return b["x"] + b["w"], b["y"] + b["h"] * fraction

    def connect(points, number, logical=False, label_segment=0):
        color = GRAY if logical else ORANGE
        style = (0, (1.1, 2.1)) if logical else (0, (4, 2))
        xs, ys = zip(*points)
        ax.plot(xs, ys, color=color, linewidth=0.95, linestyle=style,
                solid_capstyle="butt", zorder=1)
        ax.add_patch(FancyArrowPatch(
            points[-2], points[-1],
            arrowstyle="-|>", mutation_scale=8,
            color=color, linewidth=0, zorder=2,
        ))
        a, b = points[label_segment:label_segment + 2]
        x, y = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        ax.text(
            x, y, str(number), fontsize=7.5, color=color,
            ha="center", va="center", zorder=5,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.1},
        )

    def vertical(parent, child, number, logical=False, fraction=0.5):
        connect([point(parent, "bottom", fraction),
                 point(child, "top", fraction)], number, logical)

    def across(parent, child, number, fraction=0.13):
        a = point(parent, "right", fraction)
        b = point(child, "left", fraction)
        mid = (a[0] + b[0]) / 2
        connect([a, (mid, a[1]), (mid, b[1]), b],
                number, label_segment=2)

    def via_center(child, number, lane, source_fraction, target_fraction):
        a = point("trips", "right", source_fraction)
        b = point(child, "top", target_fraction)
        bend_y = b[1] - 0.22
        connect([a, (lane, a[1]), (lane, bend_y),
                 (b[0], bend_y), b], number, label_segment=2)

    vertical("trips", "itinerary_versions", 1)
    vertical("itinerary_versions", "itinerary_items", 2)

    a = point("itinerary_versions", "left", 0.78)
    b = point("trip_constraints", "left", 0.13)
    connect([a, (0.12, a[1]), (0.12, b[1]), b], 3, label_segment=2)

    vertical("itinerary_items", "trip_constraints", 4, logical=True)
    vertical("watch_observations", "watch_changes", 5, logical=True)
    across("trips", "watch_schedule", 6, fraction=0.12)
    via_center("change_requests", 7, lane=3.02,
               source_fraction=0.82, target_fraction=0.12)
    via_center("notifications", 8, lane=3.24,
               source_fraction=0.64, target_fraction=0.50)
    vertical("notifications", "outbox", 9)

    # 근거는 변경 요청의 하위 행이므로 화살표를 위쪽으로 배치한다.
    connect([point("change_requests", "top", 0.72),
             point("evidences", "bottom", 0.72)], 10)
    across("watch_observations", "change_requests", 11, fraction=0.22)

    a = point("watch_changes", "right", 0.20)
    b = point("change_requests", "bottom", 0.50)
    lane = 3.19
    bottom_y = b[1] + 0.22
    connect([a, (lane, a[1]), (lane, bottom_y),
             (b[0], bottom_y), b], 12, label_segment=2)

    fitted_texts = []
    for name, box in boxes.items():
        x, y, w, h = box["x"], box["y"], box["w"], box["h"]
        color = BLUE if entities[name]["implemented"] else ORANGE
        ax.add_patch(Rectangle(
            (x, y), w, h, facecolor="white",
            edgecolor=color, linewidth=1, zorder=3,
        ))
        ax.add_patch(Rectangle(
            (x, y), w, header_height,
            facecolor=color, edgecolor="none", zorder=3,
        ))
        ax.text(x + 0.09, y + 0.16, TITLES[name],
                fontsize=9, weight="bold", color="white",
                va="center", zorder=4)
        text = ax.text(x + 0.09, y + 0.39, name,
                       fontsize=8.2, color="white", va="center", zorder=4)
        fitted_texts.append((text, x + w - 0.08))

        for index, column in enumerate(columns[name]):
            row_y = y + header_height + index * row_height
            if index % 2 == 0:
                ax.add_patch(Rectangle(
                    (x + 0.007, row_y), w - 0.014, row_height,
                    facecolor=LIGHT, edgecolor="none", zorder=3,
                ))
            marks = []
            if column["pk"]:
                marks.append("PK")
            if column["fk"]:
                marks.append("FK")
            marker = "/".join(marks)
            column_text = ax.text(
                x + 0.075, row_y + row_height / 2, column["name"],
                fontsize=8, va="center", zorder=4,
                weight="bold" if column["pk"] else "normal",
            )
            fitted_texts.append((column_text, x + w - 0.47))
            ax.text(x + w - 0.06, row_y + row_height / 2, marker,
                    fontsize=7.5, ha="right", va="center",
                    color=color, weight="bold", zorder=4)

    footer_y = cursor - 0.16
    ax.text(0.29, footer_y, "関係".replace("関", "관").replace("係", "계") + " 읽기",
            fontsize=10, weight="bold", va="top")

    ax.plot([0.30, 0.58], [footer_y + 0.35] * 2,
            color=ORANGE, linestyle=(0, (4, 2)), linewidth=1)
    ax.text(0.65, footer_y + 0.35, "제안 외래키",
            fontsize=8, va="center")
    ax.plot([2.13, 2.41], [footer_y + 0.35] * 2,
            color=GRAY, linestyle=(0, (1.1, 2.1)), linewidth=1)
    ax.text(2.48, footer_y + 0.35, "논리 관계", fontsize=8, va="center")
    ax.text(4.1, footer_y + 0.35, "화살표: 주체 → 연결 대상",
            fontsize=7.8, va="center")

    explanations = [
        ("1  여행 → 버전: 1 대 0개 이상",
         "7  여행 → 요청: 1 대 0개 이상"),
        ("2  버전 → 항목: 1 대 0개 이상",
         "8  여행 → 알림: 1 대 0개 이상"),
        ("3  버전 → 조건: 1 대 0개 이상",
         "9  알림 ↔ 발송: 양쪽 모두 0개 또는 1개"),
        ("4  항목 → 조건: 0개 또는 1개 대 0개 이상",
         "10  요청 → 근거: 1 대 0개 이상"),
        ("5  관측 ↔ 변화: 양쪽 모두 0개 이상",
         "11  관측 → 요청: 0개 또는 1개 대 0개 이상"),
        ("6  여행 → 감시: 1 대 0개 이상",
         "12  변화 → 요청: 0개 또는 1개 대 0개 이상"),
    ]
    for index, (left, right) in enumerate(explanations):
        y = footer_y + 0.63 + index * 0.19
        ax.text(0.29, y, left, fontsize=7.7, va="center")
        ax.text(3.28, y, right, fontsize=7.7, va="center")

    ax.text(
        0.29, footer_y + 1.89,
        "PK: 기본키 · FK: 외래키 · 같은 표의 여러 PK는 복합키\n"
        "11·12는 컬럼 정의의 제안 FK이며, 나머지 연결은 관계 표 기준\n"
        "외부 참조: 여행의 고객, 항목의 예약·장소, 요청의 사건은 그림 범위 밖\n"
        "관측과 변화 사이에는 직접 FK가 없음 · 마이그레이션의 실제 DB 적용은 미확인",
        fontsize=7.7, color=GRAY, va="top", linespacing=1.6,
    )

    # 글자를 축소하거나 잘라내지 않고 실제 렌더링 폭을 검사한다.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for text, right_limit in fitted_texts:
        extent = text.get_window_extent(renderer)
        limit_px = ax.transData.transform((right_limit, 0))[0]
        if extent.x1 > limit_px:
            plt.close(fig)
            raise RuntimeError(
                f"글자가 배정 폭을 넘었습니다: {text.get_text()}. "
                "맑은 고딕 설치 상태를 확인하세요."
            )

    fig.savefig(OUTPUT / "DB_ERD_여행핵심_코덱스.png", dpi=DPI)
    plt.close(fig)


def main():
    font_manager.findfont(
        font_manager.FontProperties(family="Malgun Gothic"),
        fallback_to_default=False,
    )
    entities, relationships, columns = read_document()
    validate(entities, relationships, columns)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    draw_status(entities)
    draw_erd(entities, relationships, columns)


if __name__ == "__main__":
    main()
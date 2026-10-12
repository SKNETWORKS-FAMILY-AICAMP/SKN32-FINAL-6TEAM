import os
import sys
import json
import struct
from html import escape
from pathlib import Path

GRAPHVIZ_BIN = Path(r"C:\Program Files\Graphviz\bin")
if GRAPHVIZ_BIN.is_dir():
    os.environ["PATH"] = (
        str(GRAPHVIZ_BIN) + os.pathsep + os.environ.get("PATH", "")
    )

from graphviz import Digraph


BLUE = "#2a78d6"
GRAY = "#777777"
DARK = "#333333"
LIGHT = "#eeeeee"
FONT = "Malgun Gothic"

MIN_FONT_PT = 28
PAGE_WIDTH_IN = 6.2
PAGE_HEIGHT_IN = 7.78
PAD_IN = 0.02
DPI = 200

# 7차: 제목 묶음만 네 줄에서 두 줄로 합친다.
# 제목 33.6pt, 나머지 28pt, 상자 배치·간선·상태 문구는 유지한다.
# 제목 각 줄의 폭은 JSON 그리기 명령으로 28.7인치 이내인지 확인한다.
# 실제 PNG 크기로 쪽 배치 최소 글자 크기를 판정한다.
# 기준 미달이면 오류를 내고 PNG를 저장하지 않는다.

EXTRA_PADDING_LABELS = {
    "조회 인자",
    "알림 발송 · 미구현",
    "담당 선택",
    "TeamResult",
    "후속 실행 · 미확인",
}

LANES = [
    ("external", "고객·외부 접점", [
        ("discord", "디스코드 알림\n[결정][미구현]", True),
        (
            "mcp",
            "MCP 도구 [구현: 선언·함수·시험]\n"
            "[미구현: 외부 전송 기동]\n"
            "[미확보: 호출자 인증]",
            False,
        ),
        ("agent", "개인 에이전트\n[결정: 외부 주체]", False),
        ("rest", "REST 접수\n[구현: 코드 확인]", False),
        ("approver", "승인자\n[코드 확인: 승인 API]", False),
        ("query_api", "조회 API\n[구현: 코드 확인]", False),
        ("plan_link", "여행계획서 링크·안내\n[결정][미구현]", True),
    ]),
    ("coordination", "접수·조정", [
        ("context", "ContextPack 생성\n상태·정책·근거 [구현]", False),
        ("case_intake", "Case 접수·분류\n[구현]", False),
        (
            "controller",
            "Controller [구현]\n"
            "답변·제안 분기 / 바깥함 빈 목록\n"
            "여행 알림 발행 미연결",
            False,
        ),
        (
            "replan",
            "묶음 재계획·전체 일정 검증\n"
            "일정·Case·바깥함 함께 반영\n"
            "[결정][미구현]",
            True,
        ),
        ("registry", "TeamRegistry\n담당·수행 기능 선택 [구현]", False),
    ]),
    ("team", "Team", [
        (
            "team",
            "여행 Team [구현: 여섯 로컬 Team 활성 등록]\n"
            "Activity · Booking Handoff · Mobility · Dining · Lodging · Flight\n"
            "기능 제한 v2 §04·§08 / 내부 절차 v2 §03·§04",
            False,
        ),
    ]),
    ("execution", "검증·승인·실행", [
        (
            "fact_check",
            "제안 사실 대조 [구현: 호출]\n"
            "제안 도착 시 / 기본 분류 미연결",
            False,
        ),
        (
            "action",
            "Action Layer\n"
            "[구현: 요청 저장]\n"
            "[미구현: 공급자 실행]",
            False,
        ),
        (
            "approval",
            "사람 승인 API\n"
            "승인 시 재대조·기록\n"
            "[구현: 호출 확인]",
            False,
        ),
        (
            "review",
            "전달 전 검토 [구현: 호출 자리]\n"
            "[꺼짐][미구현: 담당 Team]",
            False,
        ),
    ]),
    ("storage", "저장소", [
        ("outbox", "outbox · 발행 대기 바깥함\n[구현]", False),
        (
            "trip_store",
            "Trip·일정 버전 저장소\n"
            "다음 확인 시점 [결정][미구현]",
            True,
        ),
        (
            "observation_store",
            "여행 조회·관측 저장소\n[구현: DDL 확인]",
            False,
        ),
        (
            "case_store",
            "Case·이벤트·실행·승인 저장소\n"
            "[구현: 코드·DDL 확인]",
            False,
        ),
    ]),
    ("periodic", "주기 작업·외부 연동", [
        ("trip_watch", "여행 감시 되잡기\n[결정][미구현]", True),
        (
            "place_observer",
            "장소 관측 모듈 [구현]\n운영 사건 감지 제한",
            False,
        ),
        (
            "event_bundle",
            "사건 묶음 · 같은 여행의 사건\n[결정][미구현]",
            True,
        ),
        ("worker", "바깥함 일꾼\n[구현]", False),
        ("routing_retry", "분류·라우팅 되잡기\n[구현]", False),
        ("read_tools", "읽기 도구·외부 소스\n[구현: 일부]", False),
        (
            "remote_place",
            "원격 Place Verification\n"
            "[구현: 시뮬레이터]\n"
            "[미등록][A2A 꺼짐]",
            False,
        ),
    ]),
]

LANE_PAIRS = [
    ("execution", "storage"),
    ("external", "periodic"),
    ("coordination", "team"),
]

# 의미 방향은 항상 source → target이다.
EDGES = [
    ("agent", "rest", "요청 · 종단 미확보", False),
    ("rest", "case_intake", "응답 전 분류", False),
    ("agent", "mcp", "외부 접속 · 미구현", True),
    ("mcp", "case_intake", "생성·분류", False),
    ("case_intake", "routing_retry", "후속 실행 · 미확인", True),
    ("routing_retry", "controller", "후속 실행 · 미확인", True),
    ("case_intake", "controller", "REST 실행", False),
    ("controller", "registry", "담당 선택", False),
    ("controller", "team", "TeamTask", False),
    ("team", "read_tools", "조회 인자", False),
    ("read_tools", "team", "결과·출처", False),
    ("read_tools", "team", "이동 조회 · 미구현", True),
    ("team", "controller", "TeamResult", False),
    ("controller", "case_store", "답변·근거", False),
    ("case_store", "query_api", "답변 조회", False),
    ("controller", "fact_check", "ActionProposal", False),
    ("fact_check", "approval", "승인 요청", False),
    ("context", "fact_check", "별도 근거", False),
    ("approver", "approval", "승인 의사", False),
    ("approval", "controller", "재실행 · 미구현", True),
    ("approval", "action", "공급자 실행 · 미구현", True),
    ("trip_watch", "event_bundle", "감지 사건 · 미구현", True),
    ("event_bundle", "case_intake", "사건 접수 · 미구현", True),
    ("place_observer", "observation_store", "장소 관측", False),
    ("replan", "trip_store", "일정 반영 · 미구현", True),
    ("replan", "case_store", "Case 반영 · 미구현", True),
    ("replan", "outbox", "통지 반영 · 미구현", True),
    ("outbox", "worker", "대기 메시지", False),
    ("worker", "discord", "알림 발송 · 미구현", True),
    ("trip_store", "plan_link", "최신 일정 · 미구현", True),
    ("controller", "remote_place", "A2A · 꺼짐·미등록", True),
]

EXPECTED_COUNTS = {"solid": 17, "dashed": 14, "invis": 26}
STATUS_WORDS = ("미구현", "미확인", "꺼짐", "미등록", "미확보")


def build():
    g = Digraph("multi_agent_architecture", engine="dot", format="png")
    g.attr(
        charset="UTF-8",
        fontname=FONT,
        fontsize="33.6",
        fontcolor=DARK,
        bgcolor="white",
        dpi=str(DPI),
        rankdir="TB",
        nodesep="0.02",
        ranksep="0.02",
        pad=str(PAD_IN),
        splines="spline",
        labelloc="t",
        label=(
            "AI 시스템 아키텍처 (멀티 에이전트 아키텍처) · 코드 기준 2026-09-10\n"
            "실선: 코드 확인 · 점선: 미구현 또는 미확인"
        ),
    )
    g.attr(
        "node",
        fontname=FONT,
        fontsize=str(MIN_FONT_PT),
        shape="box",
        color=GRAY,
        fontcolor=DARK,
        margin="0.04,0.02",
        height="0",
    )
    g.attr(
        "edge",
        fontname=FONT,
        fontsize=str(MIN_FONT_PT),
        color=BLUE,
        fontcolor=DARK,
        arrowsize="0.65",
    )

    lane_level = {
        key: level
        for level, pair in enumerate(LANE_PAIRS)
        for key in pair
    }
    lane_nodes = {key: nodes for key, _, nodes in LANES}
    order = {}
    boxes = set()
    counts = {"solid": 0, "dashed": 0, "invis": 0}

    for key, title, nodes in LANES:
        with g.subgraph(name="cluster_" + key) as c:
            c.attr(
                label=title,
                fontsize=str(MIN_FONT_PT),
                color=LIGHT,
                penwidth="1.2",
                style="rounded",
                margin="4",
                labeljust="r" if key == "periodic" else "c",
            )
            for index, (name, label, dashed) in enumerate(nodes):
                assert name not in boxes, f"노드 중복: {name}"
                assert len(label.splitlines()) <= 3, name
                boxes.add(name)
                order[name] = (lane_level[key], index)
                c.node(
                    name,
                    label,
                    style="dashed" if dashed else "solid",
                )

            for upper, lower in zip(nodes, nodes[1:]):
                c.edge(
                    upper[0],
                    lower[0],
                    style="invis",
                    weight="100",
                )
                counts["invis"] += 1

    for level in range(len(LANE_PAIRS) - 1):
        for column in range(2):
            upper_key = LANE_PAIRS[level][column]
            lower_key = LANE_PAIRS[level + 1][column]
            g.edge(
                lane_nodes[upper_key][-1][0],
                lane_nodes[lower_key][0][0],
                style="invis",
                weight="100",
            )
            counts["invis"] += 1

    for edge_index, (source, target, phrase, dashed) in enumerate(EDGES):
        assert source in boxes and target in boxes
        if dashed:
            assert any(status in phrase for status in STATUS_WORDS)

        style = "dashed" if dashed else "solid"
        counts[style] += 1

        padding = 10 if phrase in EXTRA_PADDING_LABELS else 4
        label = (
            '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" '
            f'CELLPADDING="{padding}"><TR><TD>'
            f'{escape(phrase)}</TD></TR></TABLE>>'
        )
        attrs = {
            "label": label,
            "style": style,
            "minlen": "0",
            "weight": "10" if phrase == "답변 조회" else "1",
            "id": f"flow_{edge_index}_{source}_to_{target}",
        }

        if order[source] > order[target]:
            source, target = target, source
            attrs["dir"] = "back"

        if source == "replan":
            attrs["tailport"] = "w"
        if target == "replan":
            attrs["headport"] = "w"

        if (source, target) == ("read_tools", "team"):
            attrs["headport"] = "ne"

        if (source, target) == ("approval", "controller"):
            attrs["headport"] = "n"

        attrs["headclip"] = "true"
        attrs["tailclip"] = "true"

        g.edge(source, target, **attrs)

    assert len(boxes) == 28
    assert counts == EXPECTED_COUNTS
    return g


def measure_and_validate(layout, png_bytes):
    objects = layout.get("objects", [])
    edges = layout.get("edges", [])

    assert sum(o.get("shape") == "box" for o in objects) == 28
    assert sum(
        o.get("name", "").startswith("cluster_") for o in objects
    ) == 6

    actual_counts = {
        style: sum(e.get("style", "solid") == style for e in edges)
        for style in EXPECTED_COUNTS
    }
    assert actual_counts == EXPECTED_COUNTS, actual_counts

    for edge in edges:
        if edge.get("style") == "dashed":
            assert any(
                status in edge.get("label", "")
                for status in STATUS_WORDS
            ), edge.get("id")

    # 루트 그래프의 제목 두 줄만 검사한다.
    title_lines = [
        item
        for item in layout.get("_ldraw_", [])
        if item.get("op") == "T"
    ]
    if len(title_lines) != 2:
        raise RuntimeError(
            "제목 두 줄의 실측 정보를 확인하지 못했습니다. "
            "PNG를 저장하지 않았습니다."
        )
    for line in title_lines:
        line_width_in = float(line["width"]) / 72
        if line_width_in > 28.7:
            raise RuntimeError(
                f"제목 폭 초과: {line_width_in:.3f}인치 > 28.7인치. "
                f"해당 줄: {line['text']}. "
                "PNG를 저장하지 않았습니다."
            )

    font_sizes = []
    for obj in [layout] + objects + edges:
        for key, instructions in obj.items():
            if key.endswith("draw_") and isinstance(instructions, list):
                font_sizes.extend(
                    float(item["size"])
                    for item in instructions
                    if item.get("op") == "F"
                )
    assert font_sizes, "그리기 명령에서 글자 크기를 찾지 못했습니다"
    actual_min_font_pt = min(font_sizes)
    assert actual_min_font_pt >= MIN_FONT_PT

    # PNG의 IHDR에서 실제 픽셀 크기를 읽는다. 외부 이미지 모듈 불필요.
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(png_bytes) >= 33
    assert png_bytes[8:16] == b"\x00\x00\x00\x0dIHDR"
    width_px, height_px = struct.unpack(">II", png_bytes[16:24])
    assert width_px > 0 and height_px > 0

    width_in = width_px / DPI
    height_in = height_px / DPI

    # size·ratio·viewport·후처리 축소 없이 렌더했는지 경계와 대조한다.
    # PNG가 축소됐는데 원래의 28pt를 곱하는 잘못된 판정을 막는다.
    x0, y0, x1, y1 = map(float, layout["bb"].split(","))
    expected_width_px = ((x1 - x0) / 72 + 2 * PAD_IN) * DPI
    expected_height_px = ((y1 - y0) / 72 + 2 * PAD_IN) * DPI
    if (
        abs(width_px - expected_width_px) > 2
        or abs(height_px - expected_height_px) > 2
    ):
        raise RuntimeError(
            "JSON 경계와 PNG 실측 불일치: "
            f"경계 예상 {expected_width_px:.2f} × "
            f"{expected_height_px:.2f}px, "
            f"PNG {width_px} × {height_px}px. "
            "렌더 배율을 확인하기 전에는 가독성을 판정할 수 없습니다."
        )

    scale = min(
        1.0,
        PAGE_WIDTH_IN / width_in,
        PAGE_HEIGHT_IN / height_in,
    )
    page_width_in = width_in * scale
    page_height_in = height_in * scale
    page_font_pt = actual_min_font_pt * scale

    report = (
        f"상자 28 | 실선 17 | 점선 14 | "
        f"PNG {width_px} × {height_px}px @ {DPI}dpi "
        f"({width_in:.3f} × {height_in:.3f}인치) | "
        f"쪽 배치 {page_width_in:.3f} × "
        f"{page_height_in:.3f}인치 | "
        f"쪽 배치 최소 {page_font_pt:.4f}pt"
    )
    print(report)

    # 반올림한 표시값이 아니라 실제 계산값으로 통과 여부를 결정한다.
    if page_font_pt < 6.0:
        raise RuntimeError(
            "가독성 기준 미달: "
            f"{PAGE_WIDTH_IN} × {PAGE_HEIGHT_IN}인치에 맞추면 "
            f"최소 {page_font_pt:.4f}pt입니다. "
            "제목 묶음만 두 줄로 합쳤으며, "
            "상자 배치·간선·다른 문구·글자 크기는 그대로입니다. "
            "PNG를 저장하지 않았습니다."
        )

    return width_in, height_in, page_font_pt


def render(output_stem):
    g = build()

    # 중간 파일 없이 메모리에서 생성하고 실제 PNG를 검사한다.
    layout = json.loads(g.pipe(format="json"))
    png_bytes = g.pipe(format="png")
    measure_and_validate(layout, png_bytes)

    # 기준을 통과한 경우에만 출력 파일을 생성한다.
    with open(str(output_stem) + ".png", "wb") as output:
        output.write(png_bytes)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("사용법: python 스크립트.py 확장자_없는_출력_경로")
    render(sys.argv[1])

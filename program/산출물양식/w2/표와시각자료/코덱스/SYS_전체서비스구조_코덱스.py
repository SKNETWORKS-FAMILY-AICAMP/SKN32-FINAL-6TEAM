import os
import sys
import json
import math
import shutil
import struct
import subprocess
from html import escape
from pathlib import Path
from graphviz import Digraph

GRAPHVIZ_BIN = Path(r"C:\Program Files\Graphviz\bin")
if GRAPHVIZ_BIN.is_dir():
    os.environ["PATH"] = (
        str(GRAPHVIZ_BIN) + os.pathsep + os.environ.get("PATH", "")
    )

DOT = shutil.which("dot")
if not DOT:
    raise RuntimeError("Graphviz dot 실행 파일을 찾지 못했습니다.")

FONT = "Malgun Gothic"
BLUE, GRAY, DARK = "#2a78d6", "#777777", "#333333"
FONT_SIZE = 24.0
DPI = 200
PAD = 0.04
PAGE_WIDTH, PAGE_HEIGHT = 6.2, 9.0
MIN_PRINT_FONT = 6.0
STATUSES = ("미구현", "미확인", "꺼짐", "미등록", "미확보")

# 자동 배치에서 생긴 제목 관통을 없애기 위해 좌표와 경로를 고정한다.
# dot 실행 파일의 -Kneato -n2 모드로 지정한 경로를 그대로 렌더링한다.
# size 강제 축소, 순위 지정, 보이지 않는 배치 간선은 사용하지 않는다.
# 좌표 단위는 pt이며, 아래 배치는 위에서 아래로 읽는다.
W, H = 1740.0, 2345.0
BOXES = {}

GROUPS = [
    ("users", None, "로컬 기계 밖 · 요청 주체"),
    ("local", None, "로컬 기계"),
    ("entry", "local", "API 1/3 · 외부 요청 신뢰 경계"),
    ("api", "local", "API 2/3 · 사건 처리"),
    ("action", "local", "API 3/3 · 실행 권한 경계"),
    ("jobs", "local", "별도 작업 프로세스"),
    ("db", "local", "DB · PostgreSQL · pgvector"),
    ("external", None, "로컬 기계 밖 · 외부 연동"),
    ("data", "external", "외부 데이터 경계"),
    ("remote", None, "별도 원격 경계"),
]

# 경계, 이름, 상자 내용, 점선 여부.
NODES = [
    (
        "users", "customer",
        "고객 · [결정] 요청·링크 열기\n"
        "개인 에이전트로 요청\n[미구현] 링크 화면",
        False,
    ),
    (
        "users", "agent",
        "개인 에이전트 · [구현] REST\n"
        "[미구현] MCP 외부 기동\n[미확보] 실제 연결 성공",
        False,
    ),
    (
        "users", "operator",
        "운영자 · [구현] 운영 화면\n"
        "사건 조회·추적·승인\n바깥함 관리",
        False,
    ),
    (
        "entry", "rest",
        "REST 접수\n[구현] HTTP 요청·응답",
        False,
    ),
    (
        "entry", "mcp",
        "MCP · [구현] 목록·상세·접수 선언\n"
        "[미구현] 문서화된 외부 기동",
        True,
    ),
    (
        "api", "classification",
        "분류 · [구현] 메시지 분류\nCase 생성 트랜잭션 밖",
        False,
    ),
    (
        "api", "routing",
        "라우팅 · [구현] 기본 라우팅\n"
        "승인 제안 기능에 도달 못함\nv2 §02·08",
        False,
    ),
    (
        "api", "background",
        "응답 후 작업 · [구현]\n"
        "BackgroundTasks\n응답 뒤 실행 작업 등록",
        False,
    ),
    (
        "api", "controller",
        "Controller · [구현] Case 상태기계\n"
        "사건 한 건의 상태 전이\n작업 위임·판단 결과 처리",
        False,
    ),
    (
        "api", "team",
        "[구현] 여행 Team · activity · mobility\n"
        "booking_handoff · dining\nlodging · flight",
        False,
    ),
    (
        "action", "validation",
        "검증 · [구현] 제안 사실 대조\n승인 요청 기록 처리",
        False,
    ),
    (
        "action", "approval_api",
        "승인 API · 승인 완료\n"
        "[구현] 승인·거절·재대조\n사건 상태 전이",
        False,
    ),
    (
        "action", "provider_execution",
        "공급자 실행\n[미구현] 승인 뒤 재실행·실행 연결",
        True,
    ),
    (
        "action", "revalidated",
        "재검증된 일정\n"
        "[결정] 조정·재검증 후 통지\n[미구현] 여행 통지 연결",
        True,
    ),
    (
        "jobs", "recovery",
        "되잡기 작업 · [구현]\n멈춘 분류·라우팅 사건\n읽기·재처리",
        False,
    ),
    (
        "jobs", "watch",
        "여행 감시\n[미구현] 관측 변화 → Case 생성",
        True,
    ),
    (
        "jobs", "watch_recovery",
        "여행 감시 되잡기\n[미구현] 별도 감시 되잡기",
        True,
    ),
    (
        "jobs", "worker",
        "바깥함 일꾼 · [구현]\noutbox 행 읽기·발행 함수 호출",
        False,
    ),
    (
        "jobs", "publisher",
        "디스코드 발송 함수\n[미구현] 실제 발송",
        True,
    ),
    (
        "db", "case_store",
        "사건·실행·여행 조회 자료\n"
        "[구현] Case 생성\n생성 이벤트·상태 저장",
        False,
    ),
    (
        "db", "approval_store",
        "승인 저장소 · [구현]\nAction 제안·승인 요청·승인 기록",
        False,
    ),
    (
        "db", "outbox",
        "바깥함 · outbox · [구현]\n보낼 메시지를 DB에 먼저 기록",
        False,
    ),
    (
        "db", "trip",
        "Trip 저장소\n[미구현] 여행 전체 상태 저장",
        True,
    ),
    (
        "local", "plan_link",
        "여행계획서 링크 · [결정][미구현]\n"
        "최신 일정·변경 이유\n업체 미확정 상태·재요청",
        True,
    ),
    (
        "data", "sources",
        "외부 소스 · [구현] 조회 어댑터\n"
        "관광정보·기상·공휴일·국가유산",
        False,
    ),
    (
        "external", "llm",
        "LLM API · [구현] 언어 모델 호출\n"
        "임베딩 API\n문서를 검색용 숫자 벡터로 변환",
        False,
    ),
    (
        "external", "discord",
        "알림 채널 · [결정] 디스코드 한 채널\n"
        "고객 통지 · [미구현] 실제 발송 연결",
        True,
    ),
    (
        "remote", "a2a",
        "A2A 에이전트 · [구현·비활성] 꺼짐\n"
        "A2A 서버 · Place Verification 시뮬레이터\n"
        "에이전트 사이 원격 작업 위임",
        True,
    ),
]

# 출발, 도착, 상태 라벨, 점선 여부, 양방향 여부.
FLOWS = [
    ("agent", "rest", "[구현] 접수", False, False),
    ("agent", "mcp", "[미구현] 외부 기동", True, False),
    ("rest", "case_store", "[구현] Case 생성", False, False),
    ("case_store", "classification", "[구현] 분류", False, False),
    ("rest", "agent", "[구현] 응답", False, False),
    ("background", "controller", "[구현] 작업 등록", False, False),
    ("controller", "team", "[구현] TeamTask", False, False),
    ("team", "controller", "[구현] 판단·제안", False, False),
    ("controller", "validation", "[구현] 사실 대조", False, False),
    ("validation", "approval_store", "[구현] 승인 기록", False, False),
    ("operator", "approval_api", "[구현] 승인·거절", False, False),
    ("approval_api", "case_store", "[구현] 상태 전이", False, False),
    ("approval_api", "provider_execution", "[미구현] 실행 연결", True, False),
    ("controller", "sources", "[구현] 조회", False, True),
    ("controller", "llm", "[구현] 모델 호출", False, True),
    ("recovery", "case_store", "[구현] 읽기·기록", False, True),
    ("recovery", "controller", "[구현] 재처리", False, True),
    ("watch", "case_store", "[미구현] Case 생성", True, False),
    ("revalidated", "outbox", "[미구현] 여행 통지", True, False),
    ("outbox", "worker", "[구현] 행 읽기", False, False),
    ("worker", "publisher", "[구현] 함수 호출", False, False),
    ("publisher", "discord", "[미구현] 발송", True, False),
    ("customer", "plan_link", "[미구현] 링크", True, True),
    ("plan_link", "trip", "[미구현] 상태", True, True),
]

POSITIONS = {
    "customer": (285, 2128),
    "agent": (850, 2128),
    "operator": (1420, 2128),
    "rest": (855, 1919),
    "mcp": (310, 1919),
    "classification": (855, 1752.75),
    "routing": (855, 1610.25),
    "background": (855, 1477.25),
    "controller": (855, 1315.75),
    "team": (855, 1154.25),
    "plan_link": (310, 1757.5),
    "case_store": (310, 1567.5),
    "approval_store": (310, 1415.5),
    "outbox": (310, 1263.5),
    "trip": (310, 1111.5),
    "validation": (855, 973.75),
    "approval_api": (855, 831.25),
    "provider_execution": (855, 688.75),
    "revalidated": (855, 546.25),
    "recovery": (310, 902.5),
    "watch": (310, 769.5),
    "watch_recovery": (310, 636.5),
    "worker": (310, 503.5),
    "publisher": (310, 380),
    "sources": (1440, 1330),
    "llm": (1440, 1140),
    "discord": (1440, 503.5),
    "a2a": (1440, 294.5),
}

# 왼쪽, 아래, 오른쪽, 위.
BOUNDS = {
    "users": (20, 2071, 1720, 2227.75),
    "local": (20, 294.5, 1150, 2033),
    "entry": (40, 1871.5, 1110, 1995),
    "api": (595, 1078.25, 1130, 1828.75),
    "action": (595, 479.75, 1130, 1049.75),
    "db": (40, 1040.25, 575, 1662.5),
    "jobs": (40, 313.5, 575, 997.5),
    "external": (1160, 427.5, 1720, 1482),
    "data": (1180, 1263.5, 1700, 1410.75),
    "remote": (1160, 213.75, 1720, 384.75),
}

# FLOWS와 같은 순서: 실제 경로의 꼭짓점들, 선 옆 라벨 중심.
# 이 꼭짓점들은 상자나 보이지 않는 노드가 아니다.
ROUTES = [
    (
        [(820, 2076.0232), (820, 1954.84988)],
        (750.3768, 2014.0232),
    ),
    (
        [(694.9912, 2128), (480, 2128), (480, 2050),
         (310, 2050), (310, 1954.84988)],
        (584, 2154.12512),
    ),
    (
        [(730.7388, 1919), (712.7388, 1919), (712.7388, 1920),
         (505, 1920), (505, 1567.5), (449.2588, 1567.5)],
        (405.7488, 1682),
    ),
    (
        [(449.2588, 1567.5), (467.2588, 1567.5), (467.2588, 1640),
         (680, 1640), (680, 1752.75), (714.6144, 1752.75)],
        (749.6232, 1692),
    ),
    (
        [(890, 1954.84988), (890, 2076.0232)],
        (959.6232, 2014.84988),
    ),
    (
        [(855, 1425.2732), (855, 1367.7268)],
        (757.25, 1396.5),
    ),
    (
        [(815, 1263.7732), (815, 1206.2268)],
        (718.7512, 1235),
    ),
    (
        [(895, 1206.2268), (895, 1263.7732)],
        (991.2488, 1235),
    ),
    (
        [(1038.51, 1350), (1080, 1350), (1080, 902.90012),
         (855, 902.90012), (855, 937.90012)],
        (757.25, 912.90012),
    ),
    (
        [(698.49, 973.75), (506.2612, 973.75),
         (506.2612, 1415.5), (488.2612, 1415.5)],
        (408.5112, 1194.625),
    ),
    (
        [(1279.6144, 2128), (1105, 2128),
         (1105, 831.25), (985.6332, 831.25)],
        (1008.7512, 1686),
    ),
    (
        [(724.3668, 831.25), (505, 831.25), (505, 1560),
         (467.2588, 1560), (467.2588, 1567.5), (449.2588, 1567.5)],
        (407.25, 1323.25),
    ),
    (
        [(855, 779.2732), (855, 724.59988)],
        (745.2512, 751.93654),
    ),
    (
        [(1038.51, 1315.75), (1220, 1315.75), (1220, 1210),
         (1440, 1210), (1440, 1294.15012)],
        (1289.6232, 1242),
    ),
    (
        [(1038.51, 1285), (1195, 1285), (1195, 1040),
         (1440, 1040), (1440, 1088.0232)],
        (1320, 1013.87488),
    ),
    (
        [(434.6356, 902.5), (452.6356, 902.5), (452.6356, 1060),
         (105, 1060), (105, 1567.5), (170.7412, 1567.5)],
        (201.2488, 1324),
    ),
    (
        [(185.3644, 902.5), (167.3644, 902.5), (167.3644, 1040),
         (705, 1040), (705, 1080), (1130, 1080),
         (1130, 1300), (1038.51, 1300)],
        (248.99, 1016.5),
    ),
    (
        [(488.6356, 769.5), (506.6356, 769.5), (506.6356, 1500),
         (152.7412, 1500), (152.7412, 1567.5), (170.7412, 1567.5)],
        (395.3856, 1475.5),
    ),
    (
        [(706.7412, 546.25), (530, 546.25),
         (530, 1263.5), (480.01, 1263.5)],
        (420.2512, 710.25),
    ),
    (
        [(310, 1227.65012), (310, 1209.65012),
         (80, 1209.65012), (80, 557.34988),
         (310, 557.34988), (310, 539.34988)],
        (195, 1183.525),
    ),
    (
        [(310, 467.65012), (310, 415.84988)],
        (212.25, 441.75),
    ),
    (
        [(420.0088, 380), (1225.3644, 380),
         (1225.3644, 503.5), (1243.3644, 503.5)],
        (822.6866, 353.87488),
    ),
    (
        [(285, 2076.0232), (285, 2058.0232),
         (105, 2058.0232), (105, 1827.4768),
         (310, 1827.4768), (310, 1809.4768)],
        (186.6256, 2014.0232),
    ),
    (
        [(130.2412, 1757.5), (55, 1757.5), (55, 1160),
         (489.7588, 1160), (489.7588, 1111.5), (471.7588, 1111.5)],
        (136.6256, 1681.5),
    ),
]


def dot(g, fmt):
    result = subprocess.run(
        [DOT, "-Kneato", "-n2", "-T" + fmt],
        input=g.source.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )
    if result.returncode or result.stderr.strip():
        raise RuntimeError(
            result.stderr.decode("utf-8", errors="replace")
        )
    return result.stdout


def measure():
    """다른 파일 없이 설치된 글꼴로 상자의 자연 크기를 측정한다."""
    g = Digraph()
    g.attr(
        "node",
        fontname=FONT,
        fontsize="24",
        shape="box",
        margin="0.08,0.05",
        height="0",
    )
    for _, name, label, _ in NODES:
        g.node(name, label)

    result = subprocess.run(
        [DOT, "-Tjson"],
        input=g.source.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )
    if result.returncode:
        raise RuntimeError(
            result.stderr.decode("utf-8", errors="replace")
        )
    return {
        obj["name"]: (
            float(obj["width"]) * 72,
            float(obj["height"]) * 72,
        )
        for obj in json.loads(result.stdout)["objects"]
        if "pos" in obj
    }


def rect(x, y, w, h):
    return x-w/2, x+w/2, y-h/2, y+h/2


def make_skeleton(sizes):
    g = Digraph("service_architecture", engine="neato")
    g.attr(
        charset="UTF-8",
        fontname=FONT,
        fontsize="24",
        fontcolor=DARK,
        bgcolor="white",
        dpi=str(DPI),
        rankdir="TB",
        pad=str(PAD),
        splines="polyline",
        notranslate="true",
        overlap="true",
        label=(
            "시스템 구성도\n"
            "코드 기준 2026-09-10 · 작업 트리\n"
            "━━ 실선: 코드 확인    ┄┄ 점선: 미구현 또는 미확인\n"
            "실선은 실행 중임을 뜻하지 않음"
        ),
        labelloc="t",
        lp=f"{W/2},{H-45}",
        bb=f"0,0,{W},{H}",
    )
    g.attr(
        "node",
        fontname=FONT,
        fontsize="24",
        shape="box",
        height="0",
        color=GRAY,
        fontcolor=DARK,
        margin="0.08,0.05",
    )
    g.attr(
        "edge",
        fontname=FONT,
        fontsize="24",
        color=BLUE,
        fontcolor=DARK,
        arrowsize="0.55",
    )

    clusters = {}
    for name, parent, title in GROUPS:
        c = Digraph("cluster_" + name)
        x0, y0, x1, y1 = BOUNDS[name]
        c.attr(
            label=title,
            lp=f"{(x0+x1)/2},{y1-22}",
            bb=f"{x0},{y0},{x1},{y1}",
            fontname=FONT,
            fontsize="24",
            fontcolor=DARK,
            color=GRAY,
            style="dashed" if name == "remote" else "solid",
        )
        clusters[name] = c

    for parent, name, label, dashed in NODES:
        x, y = POSITIONS[name]
        w, h = sizes[name]
        BOXES[name] = rect(x, y, w, h)
        clusters[parent].node(
            name,
            label,
            pos=f"{x},{y}!",
            width=str(w/72),
            height=str(h/72),
            fixedsize="true",
            style="dashed" if dashed else "solid",
        )

    for name, parent, title in reversed(GROUPS):
        target = g if parent is None else clusters[parent]
        target.subgraph(clusters[name])

    # 테두리는 하나다. 세 열은 범례 내부의 글자 배치일 뿐이다.
    # 업무 상자 28개를 셀 때 이 범례 노드만 제외한다.
    columns = [
        [
            "로컬 · [결정] 일정 검증·변화 대응",
            "→ 조정·재검증·통지·최신 링크",
            "[미구현] 여행 전체 지속관리 연결",
            "API 1/3 · [구현] case:write",
            "tenant_id는 본문이 아닌 인증 결과",
            "[실측 · 정적 확인]",
            "app/presentation/api/cases.py:102~111",
            "MCP 한계: 2.5",
        ],
        [
            "API 2/3 · [구현] 접수·조회·입력 재개",
            "승인·운영 화면",
            "Controller + Case 상태기계",
            "여섯 로컬 Team 등록 · 작업·판단 결과 교환",
            "Team 내부 v2 §03~04 · 계약 v2 §06",
            "API 3/3 · Action · [구현]",
            "상태 변경·외부 실행 통제",
            "Team은 제안만 반환 · v2 §02·06",
        ],
        [
            "DB · [구현] PostgreSQL · pgvector",
            "pgvector: 문서 의미 검색용 벡터 저장",
            "외부 연동 · API 실제 응답 성공은 미검증",
            "외부 데이터 · 응답은 조회 근거",
            "현장 확인 아님 · [실측 · 정적 확인]",
            "app/infrastructure/travel/base.py:200~209",
            "키·설정 조립 및 Team 연결: 2.5",
            "원격 · [구현·비활성] 코어 원격 호출 꺼짐",
        ],
    ]
    label = (
        '<<TABLE BORDER="1" CELLBORDER="0" '
        'CELLSPACING="0" CELLPADDING="8">'
        '<TR><TD COLSPAN="3">범례 · 경계 설명</TD></TR><TR>'
    )
    label += "".join(
        '<TD ALIGN="LEFT">'
        + '<BR ALIGN="LEFT"/>'.join(map(escape, column))
        + "</TD>"
        for column in columns
    )
    label += "</TR></TABLE>>"
    g.node(
        "boundary_legend",
        label,
        shape="plain",
        pos=f"{W/2},0!",
    )
    return g


def spline_position(path, both):
    """직선마다 제어점 4개를 기록하여 재라우팅을 막는다."""
    start, end = path[0], path[-1]

    def inset(a, b, distance):
        length = math.hypot(b[0]-a[0], b[1]-a[1])
        return (
            a[0] + (b[0]-a[0])*distance/length,
            a[1] + (b[1]-a[1])*distance/length,
        )

    body = list(path)
    if both:
        body[0] = inset(start, path[1], 8)
    body[-1] = inset(end, path[-2], 8)

    points = [body[0]]
    for a, b in zip(body, body[1:]):
        points.extend([
            (
                a[0] + (b[0]-a[0])/3,
                a[1] + (b[1]-a[1])/3,
            ),
            (
                a[0] + 2*(b[0]-a[0])/3,
                a[1] + 2*(b[1]-a[1])/3,
            ),
            b,
        ])

    def xy(p):
        return f"{p[0]:.4f},{p[1]:.4f}"

    return (
        ("s," + xy(start) + " " if both else "")
        + "e," + xy(end) + " "
        + " ".join(map(xy, points))
    )


def build():
    g = make_skeleton(measure())

    def port(name, point):
        bounds = BOXES[name]
        sides = ("w", "e", "s", "n")
        return min(
            sides,
            key=lambda side: abs(
                point[0 if side in ("w", "e") else 1]
                - bounds[sides.index(side)]
            ),
        )

    for flow, route in zip(FLOWS, ROUTES):
        a, b, label, dashed, both = flow
        path, label_position = route
        g.edge(
            a,
            b,
            style="dashed" if dashed else "solid",
            dir="both" if both else "forward",
            tailport=port(a, path[0]),
            headport=port(b, path[-1]),
            xlabel=label,
            xlp=f"{label_position[0]},{label_position[1]}",
            pos=spline_position(path, both),
        )
    return g


def rects(layout):
    """JSON 글자 영역에 세로 여유를 더한 검사 사각형."""
    rectangles = []
    objects = [layout] + layout.get("objects", []) + layout.get("edges", [])
    for obj in objects:
        for key in ("_ldraw_", "_hldraw_", "_tldraw_"):
            size = FONT_SIZE
            for op in obj.get(key, []):
                if op["op"] == "F":
                    size = float(op["size"])
                elif op["op"] == "T":
                    x, y = op["pt"]
                    width = op["width"]
                    if op["align"] == "c":
                        x -= width/2
                    elif op["align"] == "r":
                        x -= width
                    rectangles.append((
                        x, x+width,
                        y-size*0.34, y+size*1.02,
                        op["text"],
                    ))
    return rectangles


def intersects(a, b, rectangle):
    lo, hi = 0.0, 1.0
    for start, delta, low, high in (
        (a[0], b[0]-a[0], rectangle[0], rectangle[1]),
        (a[1], b[1]-a[1], rectangle[2], rectangle[3]),
    ):
        if abs(delta) < 1e-9:
            if not low < start < high:
                return False
        else:
            u, v = (low-start)/delta, (high-start)/delta
            lo = max(lo, min(u, v))
            hi = min(hi, max(u, v))
            if lo >= hi:
                return False
    return True


def segments(obj):
    for op in obj.get("_draw_", []):
        points = op.get("points", [])
        if op["op"] in ("b", "B"):
            for j in range(0, len(points)-3, 3):
                p = points[j:j+4]
                previous = p[0]
                for k in range(1, 41):
                    t = k/40
                    u = 1-t
                    current = [
                        u**3*p[0][d]
                        + 3*u*u*t*p[1][d]
                        + 3*u*t*t*p[2][d]
                        + t**3*p[3][d]
                        for d in (0, 1)
                    ]
                    yield previous, current
                    previous = current
        elif op["op"] in ("L", "p", "P"):
            following = points[1:]
            if op["op"] in ("p", "P"):
                following += points[:1]
            yield from zip(points, following)


def check(layout):
    nodes = [o for o in layout.get("objects", []) if "pos" in o]
    edges = layout.get("edges", [])
    counts = {
        "boxes": sum(o["name"] != "boundary_legend" for o in nodes),
        "solid": sum(e.get("style") == "solid" for e in edges),
        "dashed": sum(e.get("style") == "dashed" for e in edges),
        "invisible": sum(e.get("style") == "invis" for e in edges),
    }
    assert counts == {
        "boxes": 28, "solid": 17, "dashed": 7, "invisible": 0
    }, counts
    assert len(nodes) == 29 and len(edges) == 24

    for edge in edges:
        assert "headport" in edge and "tailport" in edge
        if edge.get("style") == "dashed":
            assert any(
                status in edge.get("xlabel", "")
                for status in STATUSES
            )

    rectangles = rects(layout)
    overlap_pairs = [
        (a[4], b[4])
        for i, a in enumerate(rectangles)
        for b in rectangles[i+1:]
        if min(a[1], b[1])-max(a[0], b[0]) > 1
        and min(a[3], b[3])-max(a[2], b[2]) > 1
    ]
    if overlap_pairs:
        raise RuntimeError(f"글자 겹침: {overlap_pairs}")

    hits = []
    for obj in layout.get("objects", []) + edges:
        # 상자·경계선·간선·양쪽 화살촉 모두 검사한다.
        for key in ("_draw_", "_hdraw_", "_tdraw_"):
            lines = list(segments({"_draw_": obj.get(key, [])}))
            for rectangle in rectangles:
                if any(
                    intersects(a, b, rectangle)
                    for a, b in lines
                ):
                    hits.append((
                        obj.get("name", obj.get("xlabel", "")),
                        rectangle[4],
                    ))
    if hits:
        raise RuntimeError(f"선·글자 교차: {hits}")

    for obj in nodes:
        if obj["name"] == "boundary_legend":
            continue
        x, y = map(float, obj["pos"].split(","))
        width = float(obj["width"])*72
        height = float(obj["height"])*72
        for r in rects({"objects": [obj]}):
            if (
                r[0] < x-width/2-0.1
                or r[1] > x+width/2+0.1
                or r[2] < y-height/2-0.1
                or r[3] > y+height/2+0.1
            ):
                raise RuntimeError(f"상자 글자 넘침: {obj['name']}")

    sizes = [
        float(op["size"])
        for obj in [layout] + layout.get("objects", []) + edges
        for key in ("_ldraw_", "_hldraw_", "_tldraw_")
        for op in obj.get(key, [])
        if op["op"] == "F"
    ]
    smallest = min(sizes)
    x0, y0, x1, y1 = map(float, layout["bb"].split(","))
    width = (x1-x0)/72 + 2*PAD
    height = (y1-y0)/72 + 2*PAD
    print_font = smallest * min(
        1, PAGE_WIDTH/width, PAGE_HEIGHT/height
    )
    if print_font < MIN_PRINT_FONT:
        raise RuntimeError(
            f"쪽 맞춤 최소 {print_font:.3f}pt: 6pt 미달"
        )
    return counts, width, height, smallest, print_font


def main(write=True):
    if write and len(sys.argv) != 2:
        raise SystemExit(
            "사용법: python 스크립트.py 출력경로_확장자없이"
        )

    assert len(NODES) == 28
    assert len(FLOWS) == len(ROUTES) == 24
    assert all(
        len(label.splitlines()) <= 3
        for _, _, label, _ in NODES
    )

    g = build()
    for forbidden in ("newrank", "constraint=false", "rank=same"):
        assert forbidden not in g.source
    for character in g.source:
        value = ord(character)
        assert not (
            0x3040 <= value <= 0x30FF
            or 0x3400 <= value <= 0x4DBF
            or 0x4E00 <= value <= 0x9FFF
            or character in "。、"
        ), character

    layout = json.loads(dot(g, "json"))
    counts, width, height, smallest, json_pt = check(layout)
    dot(g, "svg")
    png = dot(g, "png")

    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    pixel_width, pixel_height = struct.unpack(">II", png[16:24])
    png_pt = smallest * min(
        1,
        PAGE_WIDTH*DPI/pixel_width,
        PAGE_HEIGHT*DPI/pixel_height,
    )
    if png_pt < MIN_PRINT_FONT:
        raise RuntimeError(
            f"PNG 쪽 맞춤 최소 {png_pt:.3f}pt: 6pt 미달"
        )

    # Graphviz 16 실측:
    # 자연 크기: 23.691111 × 35.174722인치.
    # PNG: 4738 × 7035px, 쪽 맞춤 최소 6.140725pt.
    # 여유를 더한 JSON 글자 영역 기준: 넘침·겹침·선통과 모두 0.
    # 브라우저 검사는 읽기 전용 환경의 임시 폴더 제한으로 실행하지 못했다.
    # 이 검사를 check_text_fit.js의 브라우저 실측이라고 부르지 않는다.
    # 내용 삭제·업무 상자 통합은 없다. 경계 설명만 하단 범례로 옮겼다.
    if write:
        with open(sys.argv[1] + ".png", "wb") as output:
            output.write(png)

    return counts, width, height, min(json_pt, png_pt)


if __name__ == "__main__":
    main()

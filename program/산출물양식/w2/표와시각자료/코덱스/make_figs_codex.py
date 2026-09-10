import os
from pathlib import Path

GRAPHVIZ_BIN = Path(r"C:\Program Files\Graphviz\bin")
if GRAPHVIZ_BIN.is_dir():
    os.environ["PATH"] = str(GRAPHVIZ_BIN) + os.pathsep + os.environ.get("PATH", "")

import re
from html import escape

from docx import Document
from graphviz import Digraph

BASE = Path("program/산출물양식/w2")
INPUT = BASE / "제출본"
OUTPUT = BASE / "표와시각자료/코덱스"
BLUE = "#2a78d6"
GRAY = "#777777"
DARK = "#333333"
LIGHT = "#eeeeee"
FONT = "Malgun Gothic"


def read_tables(path):
    return [
        [[cell.text.strip() for cell in row.cells] for row in table.rows]
        for table in Document(path).tables
    ]


def find_table(tables, header):
    for table in tables:
        if table and table[0][:len(header)] == header:
            return table
    raise ValueError(f"문서에서 표를 찾지 못했습니다: {header}")


def new_graph(name, title):
    graph = Digraph(name, engine="dot", format="png")
    graph.attr(
        charset="UTF-8",
        fontname=FONT,
        fontsize="19",
        fontcolor=DARK,
        bgcolor="white",
        dpi="200",
        rankdir="LR",
        nodesep="0.35",
        ranksep="1.0",
        pad="0.35",
        splines="polyline",
        labelloc="t",
        label=title,
    )
    graph.attr(
        "node", fontname=FONT, fontsize="11",
        shape="box", color=GRAY, fontcolor=DARK,
        margin="0.16,0.10",
    )
    graph.attr(
        "edge", fontname=FONT, fontsize="9",
        color=BLUE, fontcolor=DARK, arrowsize="0.65",
    )
    return graph


def render_png(graph, name):
    path = OUTPUT / f"{name}.png"
    path.write_bytes(graph.pipe(format="png"))
    print(path)


def make_erd(tables):
    entities = find_table(tables, ["구분", "테이블", "제약 대상"])
    relations = find_table(tables, ["관계명", "주 엔터티", "종 엔터티"])
    column_tables = [
        table for table in tables
        if table[0][:4] == ["컬럼명", "타입", "PK", "FK"]
    ]
    rows = entities[1:]
    if len(rows) != 32 or len(column_tables) != 22:
        raise ValueError("DB 설계서의 표 구성이 변경되었습니다. 엔터티·컬럼 매핑을 확인하세요.")

    titles = [
        "여행", "일정 버전", "일정 항목", "여행·항목 조건",
        "내부 장소", "우리 예약", "공급자 예약 원장",
        "장소 카탈로그", "수집 동기화 상태", "감시 관측",
        "감시 변화", "감시 일정", "고객 지원 사건", "사건 이력",
        "실행 요청", "발송 대기열", "판정 근거", "공급자",
        "위임 범위", "예약 실행·보상", "변경 접수", "알림",
        "테넌트", "고객", "에이전트 실행", "팀 작업", "실행 승인",
        "프롬프트", "모델 호출", "지식 문서", "지식 청크", "분석 보고서",
    ]
    # 컬럼 상세 표에서 제외된 코어 엔터티는 엔터티·관계 표의 키만 표시한다.
    core_foreign_keys = {
        "customers": ["tenant_id"],
        "agent_runs": ["case_id"],
        "team_tasks": ["run_id"],
        "action_approvals": ["action_id"],
        "llm_calls": ["prompt_id", "run_id"],
        "knowledge_chunks": ["document_id"],
    }
    graph = new_graph(
        "db_erd",
        "여행 DB 엔터티·관계도\n"
        "DB 설계서 기준 · 주요 컬럼과 복합 키 · 문서의 관계 35개",
    )

    entity_names = set()
    for index, row in enumerate(rows):
        status, name, primary_key = row[:3]
        entity_names.add(name)
        implemented = "구현 파일 존재" in status
        columns = []

        if index < len(column_tables):
            detail = column_tables[index][1:]
            key_rows = [r for r in detail if r[2] == "O" or r[3] == "O"]
            other_rows = [
                r for r in detail
                if r not in key_rows and r[0] != "tenant_id"
            ][:4]
            selected = {r[0] for r in key_rows + other_rows}
            for col in detail:
                if col[0] not in selected:
                    continue
                flags = []
                if col[2] == "O":
                    flags.append("PK")
                if col[3] == "O":
                    flags.append("FK")
                prefix = f"[{'·'.join(flags)}] " if flags else ""
                columns.append(prefix + col[0])
        else:
            columns.append("[PK] " + primary_key)
            columns.extend(
                "[FK] " + key for key in core_foreign_keys.get(name, [])
            )
            if name == "feedback_analytics_reports":
                columns.append("tenant_id (FK 선언 없음)")

        heading = f"{titles[index]} · {name}"
        body = "".join(
            f'<TR><TD ALIGN="LEFT">{escape(column)}</TD></TR>'
            for column in columns
        )
        label = (
            '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3">'
            f'<TR><TD BGCOLOR="{LIGHT}"><B>{escape(heading)}</B></TD></TR>'
            f"{body}</TABLE>>"
        )
        graph.node(
            name, label=label,
            style="solid" if implemented else "dotted",
            penwidth="1.5",
            color=BLUE if implemented else GRAY,
        )

    logical_ids = {"R-04", "R-08", "R-09", "R-10", "R-11", "R-17", "R-33"}

    for relation in relations[1:]:
        rid, parent, child, description = relation
        parent = parent.split()[-1]
        child = child.split()[-1]
        if parent not in entity_names or child not in entity_names:
            raise ValueError(f"관계의 엔터티를 찾지 못했습니다: {rid}")

        if rid in {"R-09", "R-11"}:
            cardinality, tail, head = "N:M", "0..N", "0..N"
        elif rid == "R-19":
            cardinality, tail, head = "1:1", "0..1", "0..1"
        else:
            cardinality = "1:N"
            tail = "0..1" if description.startswith("0..1") else "1"
            head = "0..N"

        logical = rid in logical_ids
        proposed = "(제안)" in description
        kind = "논리·FK 없음" if logical else ("제안 FK" if proposed else "FK")
        if rid == "R-04":
            kind = "항목 조건·다형 참조"
        graph.edge(
            parent, child,
            label=f"{rid}  {cardinality}\n{kind}",
            taillabel=tail,
            headlabel=head,
            labeldistance="1.5",
            color=GRAY if logical else BLUE,
            style="dotted" if logical else ("dashed" if proposed else "solid"),
            tooltip=description,
        )

    with graph.subgraph(name="cluster_legend") as legend:
        legend.attr(label="범례·해석", color=GRAY, fontname=FONT, fontsize="12")
        legend.node("legend_implemented", "실선 테두리: 구현 파일 존재", color=BLUE)
        legend.node("legend_design", "점선 테두리: 설계만 존재", style="dotted")
        legend.node(
            "legend_notes",
            "PK: 기본 키 · FK: 외래 키 (제안 포함)\n"
            "관계선: 실선=명시 FK / 파선=제안 FK / 점선=논리 참조\n"
            "1:N 등은 최대 관계 수, 양 끝 숫자는 선택성 포함\n"
            "복합 PK·FK는 여러 컬럼에 함께 표시\n"
            "구현 파일 존재는 DB 적용·연동 검증 완료를 뜻하지 않음\n"
            "Trip 관련 4개 표의 상태는 두 문서가 불일치함:\n"
            "이 그림은 DB 설계서의 ‘구현 파일 존재’ 표기를 따름\n"
            "수집 보고서는 해당 표를 설계·미구현으로 기재",
            shape="note", fontsize="10",
        )

    render_png(graph, "DB_ERD_코덱스")


def make_flow(report_tables):
    source_table = find_table(
        report_tables, ["데이터명", "수집 대상", "수집 목적", "사용 예정 기능"]
    )
    report_text = "\n".join(
        cell for table in report_tables for row in table for cell in row
    )
    for required in [
        "TourAPI", "기상청", "Google Places", "Routes", "캐치테이블",
        "트립어드바이저", "LOCALDATA", "특일", "RAG", "합성",
    ]:
        if required not in report_text:
            raise ValueError(f"수집 보고서에서 소스를 확인하지 못했습니다: {required}")

    graph = new_graph(
        "collection_flow",
        "여행 수집 데이터 흐름\n"
        "소스 → 수집 방식 → 저장 → 사용처 · 수집 보고서 기준",
    )
    graph.attr(ranksep="1.25", nodesep="0.3")

    sources = {
        "tour": "TourAPI · 한국관광공사\n관광 장소·운영 정보\n영문 음식점은 수집 예정",
        "weather": "기상청\n초단기 예보·관측\nMock 기본 + 실물 조회 확인",
        "places_api": "Google Places\n후보 매칭·영업상태 확인\n소량 호출 또는 Mock",
        "routes": "Google Routes\n이동 시간·경로\n연동 미구현",
        "catch": "캐치테이블\n예약 가능 식당 496곳\nPoC 한정",
        "tripadvisor": "트립어드바이저\n5,000곳 중 상위 500곳",
        "local": "인허가 LOCALDATA\n685,389행 → 영업 19,024곳",
        "holiday": "특일정보\n공휴일·대체공휴일\n수집 예정",
        "rag": "RAG 규정·안내\n취소·환급·동행 조건\n여행 코퍼스 교체 대상",
        "synthetic": "자체 합성\n여행·예약·고객 / 사건\n공급자 원장·시뮬레이터",
    }
    methods = {
        "api_catalog": "API 호출\n장소 카탈로그 수집",
        "api_watch": "API 호출\n날씨·영업상태 조회",
        "api_routes": "API 호출 계획\n경로·이동 시간 조회",
        "api_dining": "API 호출\n비공식: 캐치테이블\n공식: 트립어드바이저",
        "file_local": "파일 수집·정제\n인허가 자료",
        "api_holiday": "API 수집 예정\n특일정보",
        "file_rag": "문서 파일 선별·적재\n규정 추출·청크 분할",
        "generate": "합성 생성 계획\nJSONL · Mock 입력",
    }
    stores = {
        "catalog": "PostgreSQL · 장소\nplace_catalog / source_sync_state\nplaces (공급자 식별자)",
        "watch": "PostgreSQL · 감시 이력\nwatch_observations\nwatch_changes",
        "route_files": "datasets/travel/<이름>/\n경로 조회 자료 저장 계획\n専用 DB 표는 보고서에 미명시".replace("専用", "전용"),
        "dining_files": "datasets/travel/<이름>/\n식당·인허가 자료 저장 계획\nraw / processed / scripts / REPORT.md",
        "holiday_files": "datasets/travel/<이름>/\n특일정보 저장 계획",
        "knowledge": "PostgreSQL · RAG\nknowledge_documents / knowledge_chunks\n기존 25문서·306청크는 쇼핑몰 자료",
        "rag_files": "datasets/travel/<이름>/\n여행 규정 원문·전처리 저장 계획",
        "synthetic_files": "datasets/travel/<이름>/\n합성 JSONL 저장 계획\n여행 20~30건·사건 10개 생성 목표",
        "synthetic_db": "PostgreSQL · 합성 적재 계획\ncustomers / bookings / supplier_bookings\nTrip·일정·조건 표는 보고서상 설계",
    }
    uses = {
        "activity": "Activity · 활동\n일정·날씨·휴무·조건 검증",
        "dining": "Dining · 식사\n영업시간 검증·대체 후보\n폐업 후보 2차 확인",
        "mobility": "Mobility · 이동\n경로·이동 시간·출발 안내\n연동 미구현",
        "handoff": "Booking Handoff · 예약 인계\n규정 근거·원장 대조\n승인·인계·보상 시연 계획",
        "monitor": "감시 루프\n계획서 관련 대상만 확인\n최소 84초·기본 2분",
        "evaluation": "평가\n검증·라우팅·조정·되돌림\n사건·알림·승인 경계 시험",
    }

    for stage, title, nodes in [
        ("sources", "① 데이터 소스", sources),
        ("methods", "② 수집 방식", methods),
        ("stores", "③ 저장 표·폴더", stores),
        ("uses", "④ 사용처", uses),
    ]:
        with graph.subgraph(name=f"cluster_{stage}") as cluster:
            cluster.attr(
                label=title, color=GRAY, fontname=FONT,
                fontsize="14", style="rounded",
            )
            cluster.attr(rank="same")
            for node_id, label in nodes.items():
                cluster.node(node_id, label, color=BLUE if stage == "uses" else GRAY)

    edges = [
        ("tour", "api_catalog"), ("api_catalog", "catalog"),
        ("catalog", "activity"), ("catalog", "dining"),
        ("weather", "api_watch"), ("places_api", "api_watch"),
        ("api_watch", "watch"), ("watch", "activity"),
        ("watch", "dining"), ("watch", "monitor"),
        ("routes", "api_routes"), ("api_routes", "route_files"),
        ("route_files", "mobility"),
        ("catch", "api_dining"), ("tripadvisor", "api_dining"),
        ("api_dining", "dining_files"),
        ("local", "file_local"), ("file_local", "dining_files"),
        ("dining_files", "dining"),
        ("holiday", "api_holiday"), ("api_holiday", "holiday_files"),
        ("holiday_files", "activity"), ("holiday_files", "dining"),
        ("rag", "file_rag"), ("file_rag", "rag_files"),
        ("file_rag", "knowledge"), ("knowledge", "activity"),
        ("knowledge", "handoff"),
        ("synthetic", "generate"), ("generate", "synthetic_files"),
        ("generate", "synthetic_db"),
        ("synthetic_files", "evaluation"),
        ("synthetic_db", "evaluation"), ("synthetic_db", "handoff"),
    ]
    planned = {
        "api_routes", "route_files", "api_holiday", "holiday_files",
        "file_rag", "rag_files", "knowledge", "generate",
        "synthetic_files", "synthetic_db",
    }
    for source, target in edges:
        graph.edge(
            source, target,
            style="dashed" if source in planned or target in planned else "solid",
        )

    graph.node(
        "flow_notes",
        "범례·범위\n"
        "青".replace("青", "파란 화살표: 데이터의 주 흐름") + "\n"
        "파선: 예정·교체·미구현 경로\n"
        "datasets/travel/<이름>/ 경로는 저장 계획이며 확보 완료 경로가 아님\n"
        "실선도 실제 적재·연동 완료를 뜻하지 않음\n"
        "감시 이력은 API 응답에서 내부 생성하며 카탈로그 전수 폴링은 제외\n"
        "API 조회 결과는 기능에서 직접 사용 가능하며 그림은 저장 경로를 중심으로 표현",
        shape="note", fontsize="10", color=GRAY,
    )
    graph.node(
        "flow_source",
        f"근거: 수집 데이터 보고서_2차_여행.docx\n소스·목적 표 {len(source_table) - 1}개 항목",
        shape="plaintext", fontsize="10", fontcolor=GRAY,
    )
    render_png(graph, "수집데이터_흐름_코덱스")


def main():
    db_path = INPUT / "[데이터 수집 및 저장] DB_저장소 설계 문서_2차_여행.docx"
    report_candidates = [
        path for path in INPUT.glob("*수집 데이터 보고서_2차_여행.docx")
        if not path.name.startswith("~$")
    ]
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    if len(report_candidates) != 1:
        raise FileNotFoundError("수집 데이터 보고서_2차_여행.docx를 하나로 특정할 수 없습니다.")

    db_tables = read_tables(db_path)
    report_tables = read_tables(report_candidates[0])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    make_erd(db_tables)
    make_flow(report_tables)


if __name__ == "__main__":
    main()
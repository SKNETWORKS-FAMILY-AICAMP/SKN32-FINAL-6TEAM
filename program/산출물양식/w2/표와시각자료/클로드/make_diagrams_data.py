# -*- coding: utf-8 -*-
"""수집 데이터·DB 그림 — Claude 판. E1 ERD, E2 데이터 흐름.
ERD 관계는 DB 설계서 관계 표에서 읽는다. 구현 여부는 마이그레이션 001~013 대조 결과(실선=DDL 있음, 점선=설계만)."""
import os, re
import graphviz
from docx import Document

GV = "C:" + chr(92) + "Program Files" + chr(92) + "Graphviz" + chr(92) + "bin"
if os.path.isdir(GV):
    os.environ["PATH"] = GV + os.pathsep + os.environ.get("PATH", "")
HERE = os.path.dirname(os.path.abspath(__file__))
FORMS = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DB = os.path.join(FORMS, "w2", "제출본", "[데이터 수집 및 저장] DB_저장소 설계 문서_2차_여행.docx")
FONT, INK, MUTED, BLUE, SURF = "Malgun Gothic", "#0b0b0b", "#8a8985", "#2a78d6", "#fcfcfb"
DESIGN_ONLY = {"trips", "itinerary_versions", "itinerary_items", "trip_constraints", "watch_schedule", "evidences",
               "suppliers", "delegation_scopes", "booking_actions", "change_requests", "notifications"}
GROUPS = [("여행 일정", ["trips", "itinerary_versions", "itinerary_items", "trip_constraints"]),
          ("장소·예약", ["places", "bookings", "supplier_bookings", "place_catalog", "source_sync_state"]),
          ("감시·알림", ["watch_schedule", "watch_observations", "watch_changes", "change_requests", "notifications", "evidences"]),
          ("Case 코어", ["tenants", "customers", "customer_cases", "case_events", "agent_runs", "team_tasks", "action_requests", "action_approvals", "outbox"]),
          ("업체 실행·위임", ["suppliers", "delegation_scopes", "booking_actions"]),
          ("지식·모델", ["prompts", "llm_calls", "knowledge_documents", "knowledge_chunks", "feedback_analytics_reports"])]


def base(name, rankdir):
    g = graphviz.Digraph(name, format="png", engine="dot")
    g.attr(rankdir=rankdir, bgcolor=SURF, fontname=FONT, fontsize="14", dpi="200", pad="0.3",
           nodesep="0.3", ranksep="0.5", labelloc="t", labeljust="l")
    g.attr("node", fontname=FONT, fontsize="10", shape="box", style="rounded,filled", fillcolor="white",
           color=MUTED, fontcolor=INK, margin="0.12,0.06")
    g.attr("edge", fontname=FONT, fontsize="8.5", color=MUTED, fontcolor=MUTED, arrowsize="0.6")
    return g


def erd():
    d = Document(DB)
    rel = [t for t in d.tables if t.rows[0].cells[0].text.strip() == "관계명"][0]
    edges = []
    for r in rel.rows[1:]:
        a, b, c = r.cells[1].text, r.cells[2].text, r.cells[3].text
        ma, mb = re.search(r"E-\d+\s+(\w+)", a), re.search(r"E-\d+\s+(\w+)", b)
        if ma and mb:
            card = "1:N" if re.match(r"\s*1\b", c) else "0..1:N"
            edges.append((ma.group(1), mb.group(1), card))
    g = base("E1", "LR")
    g.attr(label="DB ERD — 테이블 32개와 관계 %d개 · 실선 = 마이그레이션 DDL 있음 · 점선 = 설계만 있음" % len(edges))
    for title, names in GROUPS:
        with g.subgraph(name="cluster_" + title) as c:
            c.attr(label=title, color=MUTED, style="rounded", fontcolor=INK, fontsize="11")
            for n in names:
                if n in DESIGN_ONLY:
                    c.node(n, n, style="rounded,dashed,filled")
                else:
                    c.node(n, n)
    for a, b, card in edges:
        g.edge(a, b, label=card, color=BLUE if a == "trips" or b == "trips" else MUTED)
    return g, len(edges)


def flow():
    g = base("E2", "LR")
    g.attr(label="수집 데이터 흐름 — 소스 > 수집 방식 > 저장 > 사용처")
    src = [("tour", "TourAPI 관광정보 (무료)"), ("kma", "기상청 예보·관측 (무료)"), ("places", "Google Places 영업상태 (유료·월 5,000건 무료)"),
           ("routes", "Google Routes 경로 (유료)"), ("catch", "캐치테이블 매장 496곳 (PoC 한정)"), ("ta", "트립어드바이저 500곳 (공식 API)"),
           ("lic", "인허가 LOCALDATA 영업 19,024곳"), ("hol", "특일정보 공휴일 (수집 예정)"), ("rag", "공개 약관·환급 규정 (RAG)"), ("syn", "합성 여행 20~30건·사건 10개")]
    how = [("m_api", "API 호출"), ("m_file", "파일 내려받기"), ("m_doc", "문서 선별·적재"), ("m_gen", "자체 생성")]
    store = [("s_pg", "PostgreSQL\nplace_catalog · places · watch_observations · watch_changes"), ("s_kb", "PostgreSQL 지식\nknowledge_documents · knowledge_chunks"),
             ("s_ds", "datasets/travel/\nraw · processed (원본 JSON 보존, CSV 파생)")]
    use = [("u_act", "Activity 판정"), ("u_din", "Dining 판정·대체 식당"), ("u_mob", "Mobility 경로·출발 역산"), ("u_bh", "Booking Handoff 규정"),
           ("u_w", "감시 루프 (최소 84초·기본 2분)"), ("u_ev", "평가·시연")]
    for col, items in (("소스", src), ("수집 방식", how), ("저장", store), ("사용처", use)):
        with g.subgraph(name="cluster_" + col) as c:
            c.attr(label=col, color=MUTED, style="rounded", fontcolor=INK)
            for k, v in items:
                c.node(k, v)
    E = [("tour", "m_api"), ("kma", "m_api"), ("places", "m_api"), ("routes", "m_api"), ("catch", "m_api"), ("ta", "m_api"),
         ("lic", "m_file"), ("hol", "m_api"), ("rag", "m_doc"), ("syn", "m_gen"),
         ("m_api", "s_pg"), ("m_api", "s_ds"), ("m_file", "s_ds"), ("m_doc", "s_kb"), ("m_gen", "s_ds"),
         ("s_pg", "u_act"), ("s_pg", "u_din"), ("s_pg", "u_mob"), ("s_pg", "u_w"), ("s_kb", "u_bh"), ("s_kb", "u_act"), ("s_ds", "u_din"), ("s_ds", "u_ev")]
    for a, b in E:
        g.edge(a, b, color=BLUE)
    return g


if __name__ == "__main__":
    g, n = erd()
    print("저장:", os.path.basename(g.render(filename="E1_DB_ERD", directory=HERE, cleanup=True)), "관계", n)
    print("저장:", os.path.basename(flow().render(filename="E2_수집데이터_흐름", directory=HERE, cleanup=True)))

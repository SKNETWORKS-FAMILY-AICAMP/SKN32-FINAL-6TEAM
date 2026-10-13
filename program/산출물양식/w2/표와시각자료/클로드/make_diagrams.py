# -*- coding: utf-8 -*-
"""기획서 도식 셋 — Claude 판 (graphviz).

D1 지금 고객이 변경에 대응하는 과정 (우리 없이)
D2 시스템 구성과 실행 경계
D3 변경·선택·실패 흐름

★상태는 색이 아니라 선으로: 실선 = 있다 [실측], 점선 = 없다·미구현, 굵은 파랑 = 주 경로.
★문구의 근거: v11 §4-C·§5·§6-A~§6-C, 결정 10·11·13, 확정시나리오_설계대응.
"""
import os
import graphviz

# anaconda 의 dot 은 pango 플러그인이 깨져 글자 폭을 잘못 잰다(글자가 상자를 넘친다). 설치본을 먼저 쓴다
_GV = r"C:\Program Files\Graphviz\bin"
if os.path.isdir(_GV):
    os.environ["PATH"] = _GV + os.pathsep + os.environ.get("PATH", "")

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "Malgun Gothic"
INK, INK2, MUTED, BLUE, SURF = "#0b0b0b", "#52514e", "#8a8985", "#2a78d6", "#fcfcfb"


def base(name, rankdir="LR"):
    g = graphviz.Digraph(name, format="png", engine="dot")
    g.attr(rankdir=rankdir, bgcolor=SURF, fontname=FONT, fontsize="13", pad="0.3",
           nodesep="0.35", ranksep="0.45", dpi="200", labelloc="t", labeljust="l")
    g.attr("node", fontname=FONT, fontsize="11", shape="box", style="rounded,filled",
           fillcolor="white", color=MUTED, fontcolor=INK, margin="0.14,0.08")
    g.attr("edge", fontname=FONT, fontsize="9.5", color=MUTED, fontcolor=INK2, arrowsize="0.7")
    return g


def todo(g, nid, label, **kw):
    """없다·미구현 — 점선 테두리"""
    g.node(nid, label, style="rounded,dashed,filled", **kw)


def d1():
    g = base("D1", rankdir="TB")
    g.attr(label="D1  지금 여행자가 일정 변경에 대응하는 과정 — 우리 없이\n"
                 "확정 시나리오 18:00 저녁 식당 당일 임시휴무(요식-P7)를 예로. 단계마다 도구가 바뀌고, 앞 단계로 되돌아간다", fontsize="13")
    steps = [("s1", "문제를 알아챈다\n(현장 안내문 · 지도 앱)"),
             ("s2", "사실 확인\n공지 · 지도 · 번역 도구"),
             ("s3", "대안 찾기\n근처 식당 · 영업 · 카드 결제"),
             ("s4", "이동 다시 계산\n다음 일정(19:30 마트)에 늦나"),
             ("s5", "예약이 있으면 업체 연락\n취소 · 위약금"),
             ("s6", "동행자에게 전달")]
    for nid, lab in steps:
        g.node(nid, lab)
    # 두 줄로 — 한 줄이면 A4 폭에서 글자가 너무 작다
    with g.subgraph() as r:
        r.attr(rank="same")
        for nid in ("s1", "s2", "s3"): r.node(nid)
    with g.subgraph() as r:
        r.attr(rank="same")
        for nid in ("s4", "s5", "s6"): r.node(nid)
    for a, b in zip(steps, steps[1:]):
        g.edge(a[0], b[0], color=INK2)
    g.edge("s3", "s2", label="다시 확인", style="dashed", constraint="false")
    g.edge("s4", "s3", label="안 맞으면 다시", style="dashed", constraint="false")
    g.node("out", "세 상태가 따로 논다\n내 일정표  ·  업체 예약  ·  실제로 한 것",
           shape="box", style="rounded,bold,filled", color=INK, fillcolor="white")
    g.edge("s6", "out", color=INK2)
    g.node("note", "재확인 시간·놓친 일정·추가 지출은 아직 안 쟀다 [미확보]",
           shape="plaintext", fontcolor=INK2, fontsize="10", style="")
    g.edge("out", "note", style="invis")
    return g


def d2():
    g = base("D2", rankdir="TB")
    g.attr(label="D2  시스템 구성과 실행 경계\n실선 = 있다 [실측 2026-09-10 정적 확인]   점선 = 없다·미구현   파랑 = 고객에게 닿는 두 접점", fontsize="13")
    with g.subgraph(name="cluster_out") as c:
        c.attr(label="바깥", color=MUTED, style="rounded,dashed", fontcolor=INK2)
        c.node("trav", "여행자\n(확정 페르소나: 대만인 친구 2명)")
        c.node("agent", "개인 에이전트\n일정을 만들어 가져온다")
    with g.subgraph(name="cluster_touch") as c:
        c.attr(label="접점 둘", color=BLUE, style="rounded", fontcolor=BLUE)
        c.node("api", "인증 API\n한국어로 낸다 · 번역은 에이전트", color=BLUE, penwidth="1.6")
        todo(c, "link", "여행계획서 링크\n여행별 토큰 · 로그인 없음 · 늘 최신\n고객 선택 언어(기본 한·영, 결정 11)", color=BLUE, penwidth="1.6")
    with g.subgraph(name="cluster_core") as c:
        c.attr(label="A-COP 코어", color=INK2, style="rounded", fontcolor=INK)
        c.node("cls", "분류  case_type + intent\n(두 축, v11 §5-B)")
        c.node("team", "Team 모듈 여섯\nActivity · Dining · Mobility · Booking Handoff\nLodging · Flight (등록만)\n제안만 낸다")
        c.node("verify", "코드 검증\n시간 · 예산 · 동행 조건")
        todo(c, "trip", "Trip 상태\n일정 버전 · 잠긴 예약 · 조건\ntrips 마이그레이션 없음")
        todo(c, "gate", "실행 게이트\ntier == simulated 만 자동\n코드에 0회")
        c.node("watch", "감시 루프 (상태를 가진다)\n최소 84초 · 기본 2분 · 틱당 5건\nfingerprint 5필드 — 영업·휴무 없음")
        c.node("deliv", "배달 루프 (바깥함 일꾼)\n중복 방지 UNIQUE\n알림 세 시점 (결정 10)")
    with g.subgraph(name="cluster_src") as c:
        c.attr(label="외부 데이터 (넓은 것부터, §7-C)", color=MUTED, style="rounded", fontcolor=INK2)
        c.node("free", "공공 API 무료\nTourAPI · 기상청")
        todo(c, "paid", "Places · Routes 유료\n단가 공개 · 사용량 [미확보]\nread.route · read.transit = None")
        todo(c, "new5", "신규 다섯 [미확보]\n대기질 · 실시간 운행 · 도로 통제\n당일 휴무 · 재고")
    g.node("vendor", "업체 예약처\n변경 링크로 인계 · 승인 필요")
    g.node("human", "사람 인계\n1건 15분 상한 [추정]")
    g.node("disc", "디스코드 웹훅\n무료 채널 하나")

    g.edge("agent", "api", color=BLUE, penwidth="1.4")
    g.edge("trav", "link", color=BLUE, penwidth="1.4", label="열람 · 재요청")
    g.edge("api", "cls"); g.edge("link", "cls", style="dashed")
    g.edge("cls", "team"); g.edge("team", "verify", label="제안")
    g.edge("verify", "trip", style="dashed", label="적용")
    g.edge("team", "gate", style="dashed", label="실행 요청")
    g.edge("gate", "vendor", style="dashed")
    g.edge("free", "watch"); g.edge("paid", "watch", style="dashed"); g.edge("new5", "watch", style="dashed")
    g.edge("watch", "cls", label="Case 를 만들기만 한다")
    g.edge("trip", "deliv", style="dashed"); g.edge("deliv", "disc")
    g.edge("disc", "trav", color=BLUE, label="알림 (열람은 못 잰다)")
    g.edge("verify", "human", label="해 없음 · 근거 부족")
    return g


def d3():
    g = base("D3", rankdir="TB")
    g.attr(label="D3  변경 · 선택 · 실패 흐름\n부분 반영은 없다 — 전부 적용하거나 전부 안 한다 (v11 §6-C)", fontsize="13")
    g.node("in1", "감시가 변화 감지\n(시스템 시작 3/6)")
    g.node("in2", "고객 신고 · 질문 · 재요청\n(고객 시작 3/6)")
    g.node("bundle", "여행별 사건 묶음\n한 스윕 · 한 Trip 은 Case 하나")
    g.node("gen", "후보 만들기\n찾는 순서: 장거리 차편 > 액티비티 = 숙박 > 요식 > 이동\n(순서는 탐색용이지 비교 기준이 아니다)")
    g.node("elim", "탈락 규칙\n필수 조건 위반 · 필수값 미확인\n잠긴 예약 변경 · 실행 권한 없음")
    g.node("cmp", "비교할 수 있나?", shape="diamond", style="filled", fillcolor="white")
    g.node("side", "나란히 제시 — 순위 없이\n근거 · 확인 시각 · 미확인 항목\n고객이 고른다  [제안]\n예: 이동-B1 건대입구 / 뚝섬")
    g.node("best", "최고 안 하나를 먼저 적용\n변경 수 > 추가 비용 > 시간 차 > 되돌리기 쉬움\n동률은 후보 id 로 결정")
    g.node("rever", "최신 버전으로 다시 검증\n버전 · 사건 개정번호를 반영 직전에 확인")
    g.node("save", "일정 버전 + 배달 예정을 한 번에 저장", style="rounded,bold,filled", color=INK)
    g.node("notify", "알림 (1) 변경  +  링크 갱신\n출발 안내 재산정 · 낡은 안내 무효화")
    g.node("fail", "실패 — 상태 보존 + 사람 인계\n근거 부족 · 해 없음 · 탐색 상한\n버전 경합 · 배달 실패", style="rounded,dashed,filled")
    g.node("vend", "업체 예약 변경은 따로\n변경 링크 인계 · 완료를 추정하지 않는다")

    for a, b in (("in1", "bundle"), ("in2", "bundle"), ("bundle", "gen"), ("gen", "elim"), ("elim", "cmp")):
        g.edge(a, b, color=BLUE, penwidth="1.3")
    g.edge("cmp", "side", label="비교값 미확인 또는 동률")
    g.edge("cmp", "best", label="확인됨 · 우열 분명", color=BLUE, penwidth="1.3")
    g.edge("side", "rever", label="고객 선택 뒤")
    g.edge("best", "rever", color=BLUE, penwidth="1.3")
    g.edge("rever", "save", color=BLUE, penwidth="1.3")
    g.edge("save", "notify", color=BLUE, penwidth="1.3")
    g.edge("elim", "fail", label="남는 후보 없음", style="dashed")
    g.edge("rever", "fail", label="경합 · 재검증 실패", style="dashed")
    g.edge("save", "vend", label="예약이 걸린 항목", style="dashed")
    g.edge("notify", "in2", label="마음에 안 들면 API · 웹으로 재요청", style="dashed", constraint="false")
    return g


if __name__ == "__main__":
    for f, name in ((d1, "D1_변경대응_현재과정"), (d2, "D2_시스템구성_실행경계"), (d3, "D3_변경선택실패_흐름")):
        out = f().render(filename=name, directory=HERE, cleanup=True)
        print("저장:", os.path.basename(out))

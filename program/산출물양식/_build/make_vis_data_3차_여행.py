# -*- coding: utf-8 -*-
"""수집 데이터 보고서 3차(여행) 그림 셋 — 흐름 · 확보 상태 · 수량.

    python make_vis_data_3차_여행.py

★2차 그림(w2/표와시각자료/코덱스/make_vis_data_코덱스.py, 클로드/make_diagrams_data.py)의 모양을
  이어받고 값만 2026-09-18 실측으로 바꾼다. 값의 근거는 build_수집데이터보고서_3차_여행.py 머리 주석.
★출력은 새 폴더(w3/데이터수집_여행/그림/)에 쓴다 — 2차 그림을 덮지 않는다.
"""
from pathlib import Path
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

HERE = Path(__file__).resolve().parent
OUTPUT = HERE.parent / "w3" / "데이터수집_여행" / "그림"
AS_OF = "보고서 기준 2026. 9. 18."

BLUE, ORANGE, GREEN, GRAY, DARK = "#2a78d6", "#eb6834", "#1f8a70", "#777777", "#333333"

plt.rcParams.update({
    "font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 10,
    "text.color": DARK, "axes.labelcolor": DARK, "xtick.color": DARK, "ytick.color": DARK,
    "figure.facecolor": "white", "savefig.facecolor": "white", "hatch.linewidth": 0.7,
})


def save(fig, name):
    fig.savefig(OUTPUT / name, dpi=200)
    plt.close(fig)
    return OUTPUT / name


# ── 수량 ──────────────────────────────────────────────────────────────
def draw_quantities():
    fig, ax = plt.subplots(figsize=(6.3, 8.0))
    fig.subplots_adjust(left=0.27, right=0.95, top=0.82, bottom=0.25)
    fig.text(0.06, 0.96, "소스별 수집·필터링 수량", fontsize=16, weight="bold", va="top")
    fig.text(0.06, 0.915, AS_OF + "  |  완료 실적과 예정량 구분", fontsize=9, color=GRAY)
    fig.legend(handles=[Patch(facecolor=BLUE, label="수집 완료"),
                        Patch(facecolor=ORANGE, label="필터링 후"),
                        Patch(facecolor="white", edgecolor=GRAY, hatch="////", label="수집 예정")],
               loc="upper left", bbox_to_anchor=(0.05, 0.895), ncol=3, frameon=False, fontsize=9,
               handlelength=1.5, columnspacing=1.4)
    labels = ["관광공사 관광정보", "소비자상담\n(여행 품목)", "쇼핑 리뷰\n감정 말뭉치", "캐치테이블",
              "트립어드바이저", "음식점 인허가", "감시 관측", "관광공사 음식점\n영문 정보"]
    ax.set_xscale("log")
    ax.set_xlim(1, 30_000_000)
    ax.set_ylim(len(labels) - 0.45, -0.65)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9.3)
    ax.tick_params(axis="y", length=0, pad=9)
    ax.xaxis.set_major_locator(FixedLocator([1, 100, 10_000, 1_000_000]))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{int(v):,}"))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.tick_params(axis="x", labelsize=8.5)
    ax.set_xlabel("수량 · 로그 축(밑 10, 왼쪽 기준 1)", fontsize=9, labelpad=8)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color="#dddddd", linewidth=0.6)
    for spine in ax.spines.values():
        spine.set_visible(False)

    def bar(y, value, label, color=None, planned=False):
        ax.barh(y, value - 1, left=1, height=0.25, color="white" if planned else color,
                edgecolor=GRAY if planned else "none", hatch="////" if planned else None, linewidth=0.8)
        ax.annotate(label, xy=(value, y), xytext=(5, 0), textcoords="offset points", va="center",
                    fontsize=8.8, color=GRAY if planned else DARK)

    bar(0, 2_063, "2,063건", BLUE)
    bar(1 - 0.16, 1_236_805, "1,236,805행", BLUE)
    bar(1 + 0.16, 101_112, "고유 101,112건", ORANGE)
    bar(2 - 0.16, 199_908, "199,908건", BLUE)
    bar(2 + 0.16, 199_889, "199,889건", ORANGE)
    bar(3, 496, "496곳", BLUE)
    bar(4 - 0.16, 5_000, "5,000곳", BLUE)
    bar(4 + 0.16, 500, "500곳", ORANGE)
    bar(5 - 0.16, 685_389, "685,389행", BLUE)
    bar(5 + 0.16, 19_024, "19,024곳", ORANGE)
    bar(6, 7, "관측 7건 · 변화 1건", BLUE)
    ax.axhspan(6.55, len(labels) - 0.45, color="#f5f5f5", zorder=0)
    ax.axhline(6.55, color="#bbbbbb", linewidth=0.8, linestyle="--")
    bar(7, 1_200, "약 1,200건 · 예정", planned=True)

    notes = [
        "관광정보: 서울 전 분류 전수 수집(좌표 결측 0, 전체 대조 어긋남 0).",
        "소비자상담: 2종 원천 행 수 → 여행 품목 139,539행 → 정규화·중복·길이 필터 후 고유 건수.",
        "  그중 표본 6,287건에 교사 라벨 6,067건 확정(데이터 전처리 결과서 3차).",
        "쇼핑 리뷰: 전처리(정규화 후 중복 제거) 뒤 199,889건.",
        "트립어드바이저: 5개 지역 각 1,000곳 → 리뷰 수 상위 각 100곳. 인허가: 좌표·지역·영업 조건 적용.",
        "소스별 단위가 다르고 중복 가능성이 있어 합산하지 않는다. 예정량은 완료 실적에서 뺀다.",
    ]
    for i, note in enumerate(notes):
        fig.text(0.06, 0.165 - i * 0.024, note, fontsize=7.9)
    return save(fig, "수집데이터_소스별수량_3차.png")


# ── 확보 상태 ─────────────────────────────────────────────────────────
STATUS_COLOR = {"확보": BLUE, "연결": GREEN, "일부": ORANGE, "예정": GRAY}
STATUS_BG = {"확보": "#eaf2fc", "연결": "#e5f3ee", "일부": "#fdf0e9", "예정": "#eeeeee"}


def draw_status():
    rows = [
        ("관광공사 관광정보", "확보", "서울 전 분류 2,063건 전수 수집\n좌표 결측 0 · 전체 대조 어긋남 0"),
        ("감시 관측·변화", "확보", "관측 7건 · 변화 1건 저장\n운영 상태는 일정 감시가 조회"),
        ("캐치테이블", "확보", "496곳 수집 · 영업시간 확보\n브레이크타임 267곳"),
        ("트립어드바이저", "일부", "5,000곳 수집 → 500곳 선별\n상세 150곳 조회 · 가격대 129곳"),
        ("음식점 인허가", "확보", "685,389행 확보\n지역·영업 조건 적용 후 19,024곳"),
        ("소비자상담 여행 품목", "확보", "여행 품목 139,539행 · 고유 101,112건\n교사 라벨 6,067건(학습)"),
        ("쇼핑 리뷰 감정 말뭉치", "확보", "199,908건 확보\n전처리 후 199,889건(학습)"),
        ("기상 예보·특보", "연결", "Open-Meteo · 기상청 대체 사슬\n필요할 때 조회 · 저장 안 함"),
        ("대기질", "연결", "에어코리아 1차 · Open-Meteo 대체\n미세먼지 경보 기준 판정"),
        ("재난문자·지진", "연결", "재난문자 API(키 없으면 샘플 CSV)\n지진정보 조회"),
        ("교통 돌발·도로 통제", "연결", "UTIC · ITS 합산\n지하철 무정차는 소스 없음"),
        ("특일 · 국가유산 좌표", "연결", "공휴일 · 유적 좌표\n필요할 때 조회"),
        ("구글 장소 영업시간", "예정", "연동 코드 없음\n지금은 등록 때 받은 장소 속성으로 판정"),
        ("이동 시간·경로", "예정", "ODsay · Google Routes 연동 전\n지금은 등록 때 받은 경로 후보로 판정"),
        ("관광공사 음식점 영문", "예정", "서울 관광 음식점 약 1,200건\n다국어 명칭·주소 수집 예정"),
        ("취소·환급 규정 (RAG)", "예정", "여행 문서 0건\n쇼핑몰 25문서 · 306청크 교체 대상"),
        ("동행 조건·변경 안내", "예정", "공개 안내 문서 · 변경 링크\n표본 조사 및 수집 예정"),
        ("합성 여행·예약·고객", "일부", "확정 시나리오 여행 1건 구현\n목표 20~30건"),
        ("합성 사건 시나리오", "일부", "사건 6개 재생 입력 구현\n목표 10개"),
        ("합성 공급자 원장", "예정", "모의 예약·실패 입력(MVP 다음)\n실제 업체 연동 자료 아님"),
    ]
    fig, ax = plt.subplots(figsize=(6.3, 11.6))
    ax.axis("off")
    fig.subplots_adjust(left=0.04, right=0.96, top=0.915, bottom=0.10)
    fig.text(0.06, 0.975, "데이터 소스별 확보 상태", fontsize=16, weight="bold", va="top")
    fig.text(0.06, 0.945, AS_OF + "  |  저장소·DB 실측 기준", fontsize=9, color=GRAY)
    table = ax.table(cellText=rows, colLabels=["데이터 소스", "상태", "확보 범위 및 남은 작업"],
                     colWidths=[0.30, 0.11, 0.59], cellLoc="left", colLoc="left", bbox=[0, 0, 1, 1])
    table.auto_set_font_size(False)
    table.set_fontsize(8.6)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#dddddd")
        cell.set_linewidth(0.5)
        cell.PAD = 0.05
        cell.get_text().set_linespacing(1.35)
        if row == 0:
            cell.set_facecolor(BLUE)
            cell.get_text().set_color("white")
            cell.get_text().set_weight("bold")
        else:
            cell.set_facecolor("white" if row % 2 else "#f7f7f7")
            if col == 1:
                status = rows[row - 1][1]
                cell.set_facecolor(STATUS_BG[status])
                cell.get_text().set_color(STATUS_COLOR[status])
                cell.get_text().set_weight("bold")
        if col == 1:
            cell.get_text().set_ha("center")
    notes = [
        "확보: 수집분이 저장돼 있음   연결: 조회 코드가 붙어 필요할 때 읽음(저장 안 함)",
        "일부: 응답 확인·일부 필드·목표 일부만 확보   예정: 계획 단계이거나 연동 코드 없음",
        "확보 상태는 이용 권한·품질 검수·운영 연동 완료를 뜻하지 않는다.",
    ]
    for i, note in enumerate(notes):
        fig.text(0.06, 0.075 - i * 0.02, note, fontsize=8.0)
    return save(fig, "수집데이터_확보상태_3차.png")


# ── 흐름 ─────────────────────────────────────────────────────────────
def draw_flow():
    import graphviz

    # ★anaconda 의 dot 은 글꼴 플러그인(pango)을 못 불러 한글 폭을 Times 로 재고, 글자가 상자 밖으로
    #   나간다(2026-09-18 실측). 2차 그림처럼 별도 설치본을 먼저 쓴다.
    installed = r"C:\Program Files\Graphviz\bin"
    if os.path.isdir(installed):
        os.environ["PATH"] = installed + os.pathsep + os.environ.get("PATH", "")

    ink, muted, surf = "#0b0b0b", "#8a8985", "#fcfcfb"
    g = graphviz.Digraph("flow3", format="png", engine="dot")
    g.attr(rankdir="LR", bgcolor=surf, fontname="Malgun Gothic", fontsize="15", dpi="200", pad="0.3",
           nodesep="0.22", ranksep="0.7", labelloc="t", labeljust="l",
           label="여행 수집 데이터 흐름 · 소스 > 수집 방식 > 저장 > 사용처 (2026. 9. 18. 기준)\n"
                 "실선 = 동작 중 · 점선 = 예정 또는 연동 전")
    g.attr("node", fontname="Malgun Gothic", fontsize="10", shape="box", style="rounded,filled",
           fillcolor="white", color=muted, fontcolor=ink, margin="0.12,0.06")
    g.attr("edge", color=BLUE, arrowsize="0.6")
    planned = {"places", "routes", "rag", "ta_en", "m_doc", "s_kb"}
    columns = [
        ("① 데이터 소스", [
            ("tour", "TourAPI 관광정보\n서울 2,063건"),
            ("wx", "기상 예보·특보\nOpen-Meteo · 기상청"),
            ("air", "대기질\n에어코리아 · Open-Meteo"),
            ("dis", "재난문자 · 지진"),
            ("trf", "교통 돌발 · 도로 통제\nUTIC · ITS"),
            ("etc", "특일 · 국가유산 좌표"),
            ("places", "Google Places 영업상태\n연동 전"),
            ("routes", "ODsay · Google Routes 경로\n연동 전"),
            ("food", "요식업장 3종(팀원 수집)\n캐치테이블 · 트립어드바이저 · 인허가"),
            ("ftc", "공정위 소비자상담\n여행 품목 139,539행"),
            ("rev", "쇼핑 리뷰 말뭉치\n199,908건"),
            ("msg", "고객 자유 문장 · 일정 등록"),
            ("syn", "확정 시나리오 재생\n여행 1건 · 사건 6개"),
            ("rag", "공개 약관 · 규정 (RAG)\n여행 문서 교체 예정"),
        ]),
        ("② 수집 방식", [
            ("m_sync", "카탈로그 동기화\n페이지별 재개 · 전체 대조"),
            ("m_api", "필요할 때 조회\n속도 제한 · 캐시 · 대체 사슬"),
            ("m_file", "파일 내려받기 · 정제"),
            ("m_llm", "로컬 Gemma 4\n마스킹 후 분류 · 추출 · 교사 라벨"),
            ("m_doc", "문서 선별 · 적재"),
        ]),
        ("③ 저장", [
            ("s_cat", "PostgreSQL 장소\nplace_catalog · source_sync_state · places"),
            ("s_trip", "PostgreSQL 여행\ntrips · itinerary_versions · itinerary_items"),
            ("s_watch", "PostgreSQL 감시\nwatch_observations · watch_changes"),
            ("s_case", "PostgreSQL Case · 발송 대기열\ncustomer_cases · case_events · outbox"),
            ("s_ml", "datasets/ml/\n학습 · 검증 · 시험 조각"),
            ("s_ds", "datasets/travel/\n수집 원본 · 정제본"),
            ("s_kb", "PostgreSQL 지식\nknowledge_documents · chunks"),
        ]),
        ("④ 사용처", [
            ("u_watch", "일정 감시\n90분 앞 항목 점검 · 자동 조정"),
            ("u_desk", "고객 신고 처리\n지연 · 휴무 · 품절 · 재요청"),
            ("u_notify", "알림 발송\n고객 언어로 번역"),
            ("u_model", "분류 모델 학습\n감정 · 요청 종류 · 문제 코드"),
            ("u_team", "Activity · Dining · Mobility 판정"),
        ]),
    ]
    for title, items in columns:
        with g.subgraph(name="cluster_" + title) as c:
            c.attr(label=title, color=muted, style="rounded", fontcolor=ink, fontsize="12")
            for key, text in items:
                c.node(key, text, style="rounded,dashed,filled" if key in planned else "rounded,filled")
    edges = [
        ("tour", "m_sync"), ("wx", "m_api"), ("air", "m_api"), ("dis", "m_api"), ("trf", "m_api"),
        ("etc", "m_api"), ("places", "m_api"), ("routes", "m_api"), ("food", "m_file"), ("ftc", "m_file"),
        ("rev", "m_file"), ("msg", "m_llm"), ("syn", "m_api"), ("rag", "m_doc"),
        ("m_sync", "s_cat"), ("m_api", "s_watch"), ("m_api", "u_watch"), ("m_file", "s_ds"),
        ("m_file", "m_llm"), ("m_llm", "s_ml"), ("m_llm", "s_case"), ("m_doc", "s_kb"),
        ("s_cat", "u_team"), ("s_cat", "u_watch"), ("s_trip", "u_watch"), ("s_trip", "u_desk"),
        ("s_case", "u_desk"), ("s_case", "u_notify"), ("s_ml", "u_model"), ("s_ds", "u_team"),
        ("s_kb", "u_team"), ("u_watch", "s_trip"), ("u_desk", "s_trip"),
    ]
    for a, b in edges:
        dashed = a in planned or b in planned
        g.edge(a, b, style="dashed" if dashed else "solid", color=GRAY if dashed else BLUE)
    path = g.render(filename="수집데이터_흐름_3차", directory=str(OUTPUT), cleanup=True)
    return Path(path)


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for made in (draw_flow(), draw_status(), draw_quantities()):
        print("저장:", made)

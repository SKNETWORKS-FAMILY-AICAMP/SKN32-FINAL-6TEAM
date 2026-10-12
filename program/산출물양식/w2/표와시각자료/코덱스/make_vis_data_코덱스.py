from pathlib import Path
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
from docx import Document


ROOT = Path.cwd()
SOURCE = (
    ROOT / "program" / "산출물양식" / "w2" / "제출본"
    / "[데이터 수집 및 저장] 수집 데이터 보고서_2차_여행.docx"
)
OUTPUT = ROOT / "program" / "산출물양식" / "w2" / "표와시각자료" / "코덱스"

BLUE = "#2a78d6"
ORANGE = "#eb6834"
GRAY = "#777777"
DARK = "#333333"
LIGHT = "#eeeeee"

plt.rcParams.update({
    "font.family": "Malgun Gothic",
    "axes.unicode_minus": False,
    "font.size": 10,
    "text.color": DARK,
    "axes.labelcolor": DARK,
    "xtick.color": DARK,
    "ytick.color": DARK,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
    "hatch.linewidth": 0.7,
})


def read_report():
    document = Document(SOURCE)

    # 문서의 표 순번은 표지와 제목 표 포함 여부에 따라 달라지므로
    # 개요와 데이터 양 표를 실제 내용으로 찾는다.
    overview = None
    quantities = None
    for table in document.tables:
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        text = "\n".join(" ".join(row) for row in rows)
        if all(word in text for word in ("데이터명", "수집 대상", "수집 목적")):
            overview = text
        if all(word in text for word in (
            "전체 수집 데이터 건수", "필터링 후 기준"
        )):
            quantities = text

    if overview is None or quantities is None:
        raise ValueError("원본 문서에서 개요 또는 데이터 양 표를 찾지 못했습니다.")

    combined = overview + "\n" + quantities
    for value in ("496", "5,000", "500", "685,389", "19,024", "40", "1,200"):
        pattern = rf"(?<![\d,]){re.escape(value)}(?![\d,])"
        if not re.search(pattern, combined):
            raise ValueError(f"원본의 수량이 변경되었거나 누락되었습니다: {value}")

    for source in ("캐치테이블", "트립어드바이저", "인허가", "특일"):
        if source not in combined:
            raise ValueError(f"원본에서 데이터 소스를 확인할 수 없습니다: {source}")


def save_figure(fig, filename):
    # 여백을 포함한 폭을 6.3인치로 유지한다.
    fig.savefig(OUTPUT / filename, dpi=200)
    plt.close(fig)


def draw_quantities():
    fig, ax = plt.subplots(figsize=(6.3, 6.6))
    fig.subplots_adjust(left=0.25, right=0.97, top=0.78, bottom=0.31)

    fig.text(
        0.06, 0.95, "소스별 수집·필터링 수량",
        fontsize=16, weight="bold", va="top"
    )
    fig.text(
        0.06, 0.90, "보고서 기준 2026. 9. 10.  |  완료 실적과 예정량 구분",
        fontsize=9, color=GRAY
    )
    fig.legend(
        handles=[
            Patch(facecolor=BLUE, label="수집 완료"),
            Patch(facecolor=ORANGE, label="필터링 후"),
            Patch(facecolor="white", edgecolor=GRAY, hatch="////",
                  label="수집 예정"),
        ],
        loc="upper left", bbox_to_anchor=(0.05, 0.872),
        ncol=3, frameon=False, fontsize=9,
        handlelength=1.5, columnspacing=1.4
    )

    # 로그 축은 0을 표현할 수 없으므로 막대의 왼쪽 기준을 1로 둔다.
    ax.set_xscale("log")
    ax.set_xlim(1, 20_000_000)
    ax.set_ylim(4.55, -0.65)
    ax.set_yticks(range(5))
    ax.set_yticklabels([
        "캐치테이블",
        "트립어드바이저",
        "음식점 인허가",
        "특일 정보",
        "관광공사 음식점\n영문 정보",
    ], fontsize=9.5)
    ax.tick_params(axis="y", length=0, pad=9)

    ticks = [1, 100, 10_000, 1_000_000]
    ax.xaxis.set_major_locator(FixedLocator(ticks))
    ax.xaxis.set_major_formatter(
        FuncFormatter(lambda value, position: f"{int(value):,}")
    )
    ax.xaxis.set_minor_locator(NullLocator())
    ax.tick_params(axis="x", labelsize=8.5)
    ax.set_xlabel("수량 · 로그 축(밑 10, 왼쪽 기준 1)", fontsize=9, labelpad=10)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color="#dddddd", linewidth=0.6)

    for spine in ax.spines.values():
        spine.set_visible(False)

    def bar(y, value, label, color=None, planned=False):
        ax.barh(
            y, value - 1, left=1, height=0.25,
            color="white" if planned else color,
            edgecolor=GRAY if planned else "none",
            hatch="////" if planned else None,
            linewidth=0.8
        )
        ax.annotate(
            label, xy=(value, y), xytext=(5, 0),
            textcoords="offset points", va="center",
            fontsize=9, color=GRAY if planned else DARK
        )

    bar(0, 496, "496곳", BLUE)
    bar(1 - 0.16, 5_000, "5,000곳", BLUE)
    bar(1 + 0.16, 500, "500곳", ORANGE)
    bar(2 - 0.16, 685_389, "685,389행", BLUE)
    bar(2 + 0.16, 19_024, "19,024곳", ORANGE)

    ax.axhspan(2.60, 4.55, color="#f5f5f5", zorder=0)
    ax.axhline(2.60, color="#bbbbbb", linewidth=0.8, linestyle="--")
    bar(3, 40, "약 40건 · 예정", planned=True)
    bar(4, 1_200, "약 1,200건 · 예정", planned=True)

    notes = [
        "트립어드바이저: 5개 지역 각 1,000곳 수집 → 리뷰 수 상위 각 100곳.",
        "인허가: 원본 행 수 → 좌표·지역 조건 적용 후 영업/정상 업소.",
        "캐치테이블: 별도 필터링 수량은 제시되지 않아 수집량만 표시.",
        "소스별 단위가 다르고 중복 가능성이 있어 합산하지 않음.",
        "예정량은 완료 실적에서 제외. 출처: 수집 데이터 보고서 개요·데이터 양.",
    ]
    for index, note in enumerate(notes):
        fig.text(0.06, 0.155 - index * 0.026, note, fontsize=8.3)

    save_figure(fig, "수집데이터_소스별수량_코덱스.png")


def draw_status():
    # 확보는 수집분 존재, 일부는 응답·일부 필드 확인,
    # 예정은 정식 수집·저장 완료 근거가 아직 없는 경우로 구분한다.
    rows = [
        ("캐치테이블", "확보",
         "496곳 수집·영업시간 확보\n브레이크타임 267곳"),
        ("트립어드바이저", "일부",
         "5,000곳 수집 → 500곳 선별\n상세 150곳 조회·가격대 129곳"),
        ("음식점 인허가", "확보",
         "685,389행 확보\n지역·영업 조건 적용 후 19,024곳"),
        ("특일 정보", "예정",
         "2026~2027 공휴일·대체공휴일\n약 40건 수집 예정"),
        ("관광공사 음식점\n영문 정보", "예정",
         "서울 관광 음식점 약 1,200건\n다국어 명칭·주소 수집 예정"),
        ("관광공사 관광정보", "일부",
         "키워드검색 응답·분류 확인\n정식 수집 전·완료량 미집계"),
        ("기상청 예보·관측", "예정",
         "실물 조회 확인 계획\n저장 완료량 미집계"),
        ("구글 장소 영업시간", "예정",
         "소량 호출·모의 조회 계획\n수집 완료량 미집계"),
        ("구글 이동 시간·경로", "예정",
         "이동 시간·경로 연동 전\n연동 후 수집량 집계"),
        ("내부 감시 관측·변화", "예정",
         "저장 구조 존재·실적 미집계\n소스별 수집량은 연동 후 결정"),
        ("취소·환급 규정", "예정",
         "여행 규정으로 전량 교체 예정\n기존 쇼핑몰 문서·청크 제외"),
        ("동행 조건·변경 안내", "예정",
         "공개 안내 문서·변경 링크\n표본 조사 및 수집 예정"),
        ("합성 여행·예약·고객", "예정",
         "여행 20~30건 생성 목표\n생성 완료량 미집계"),
        ("합성 사건 시나리오", "예정",
         "사건 10개 생성 목표\n생성 완료량 미집계"),
        ("합성 공급자 원장", "예정",
         "모의 예약·실패 입력 생성 계획\n실제 업체 연동 자료 아님"),
    ]

    fig, ax = plt.subplots(figsize=(6.3, 9.4))
    ax.axis("off")
    fig.subplots_adjust(left=0.04, right=0.96, top=0.89, bottom=0.14)

    fig.text(
        0.06, 0.965, "데이터 소스별 확보 상태",
        fontsize=16, weight="bold", va="top"
    )
    fig.text(
        0.06, 0.925, "보고서 기준 2026. 9. 10.  |  수집분·확인 범위 기준",
        fontsize=9, color=GRAY
    )

    table = ax.table(
        cellText=rows,
        colLabels=["데이터 소스", "상태", "확보 범위 및 남은 작업"],
        colWidths=[0.30, 0.11, 0.59],
        cellLoc="left",
        colLoc="left",
        bbox=[0, 0, 1, 1],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)

    status_colors = {"확보": BLUE, "일부": ORANGE, "예정": GRAY}
    status_backgrounds = {
        "확보": "#eaf2fc",
        "일부": "#fdf0e9",
        "예정": "#eeeeee",
    }

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#dddddd")
        cell.set_linewidth(0.5)
        cell.PAD = 0.055
        cell.get_text().set_linespacing(1.4)
        if row == 0:
            cell.set_facecolor(BLUE)
            cell.get_text().set_color("white")
            cell.get_text().set_weight("bold")
        else:
            cell.set_facecolor("white" if row % 2 else "#f7f7f7")
            if col == 1:
                status = rows[row - 1][1]
                cell.set_facecolor(status_backgrounds[status])
                cell.get_text().set_color(status_colors[status])
                cell.get_text().set_weight("bold")
        if col == 1:
            cell.get_text().set_ha("center")

    notes = [
        "확보: 수집분 존재   일부: 응답 확인 또는 상세 필드 일부 확보",
        "예정: 수집·생성 계획 단계 또는 저장 완료 근거가 제시되지 않음",
        "확보 상태는 이용 권한·품질 검수·운영 연동 완료를 뜻하지 않음.",
        "출처: 수집 데이터 보고서 개요·데이터 양. 상태는 위 기준으로 분류.",
    ]
    for index, note in enumerate(notes):
        fig.text(0.06, 0.108 - index * 0.023, note, fontsize=8.2)

    save_figure(fig, "수집데이터_확보상태_코덱스.png")


def main():
    read_report()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    draw_quantities()
    draw_status()


if __name__ == "__main__":
    main()
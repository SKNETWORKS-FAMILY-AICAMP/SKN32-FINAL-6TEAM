from pathlib import Path
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib import font_manager

ROOT = Path.cwd()
SOURCE = ROOT / "program/산출물양식/w2/기획서/기획서_실무본.md"
OUTPUT = ROOT / "program/산출물양식/w2/표와시각자료/코덱스"

BLUE = "#2a78d6"
ORANGE = "#eb6834"
INK = "#303030"
GRAY = "#777777"
LIGHT = "#eeeeee"
WHITE = "#ffffff"

FONT_PATH = Path("C:/Windows/Fonts/malgun.ttf")
if FONT_PATH.exists():
    font_manager.fontManager.addfont(str(FONT_PATH))

plt.rcParams.update({
    "font.family": "Malgun Gothic",
    "axes.unicode_minus": False,
    "font.size": 9,
    "figure.facecolor": WHITE,
    "savefig.facecolor": WHITE,
})

TEXT_ITEMS = []


def canvas(height, title, subtitle):
    fig = plt.figure(figsize=(6.3, height), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 6.3)
    ax.set_ylim(height, 0)
    ax.axis("off")
    text(ax, 0.28, 0.30, title, size=15, weight="bold", ha="left")
    text(ax, 0.28, 0.65, subtitle, size=9, color=GRAY, ha="left")
    return fig, ax


def text(ax, x, y, value, size=9, color=INK, weight="normal",
         ha="center"):
    artist = ax.text(
        x, y, value, fontsize=size, color=color, weight=weight,
        ha=ha, va="center", linespacing=1.4, zorder=5,
    )
    TEXT_ITEMS.append((ax.figure, artist, None))
    return artist


def box(ax, x, y, w, h, title, body=None, color=BLUE,
        planned=False, size=10, body_size=8.8, fill=WHITE):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0,rounding_size=0.07",
        linewidth=1.25,
        edgecolor=color,
        facecolor=fill,
        linestyle=(0, (4, 3)) if planned else "-",
        zorder=3,
    )
    ax.add_patch(patch)
    if body:
        title_artist = text(
            ax, x + w / 2, y + h * 0.29, title,
            size=size, color=color, weight="bold",
        )
        body_artist = text(
            ax, x + w / 2, y + h * 0.68, body,
            size=body_size,
        )
        artists = [title_artist, body_artist]
    else:
        artists = [text(
            ax, x + w / 2, y + h / 2, title,
            size=size, color=color, weight="bold",
        )]
    for artist in artists:
        TEXT_ITEMS.append((ax.figure, artist, (x, y, w, h)))
    return (x, y, w, h)


def edge(ax, points, color=GRAY, dashed=False, both=False):
    style = (0, (4, 3)) if dashed else "-"
    if len(points) > 2:
        ax.plot(
            [p[0] for p in points[:-1]],
            [p[1] for p in points[:-1]],
            color=color, linewidth=1.05, linestyle=style,
            solid_capstyle="round", zorder=2,
        )
    arrow = FancyArrowPatch(
        points[-2], points[-1],
        arrowstyle="<->" if both else "-|>",
        mutation_scale=10,
        linewidth=1.05,
        linestyle=style,
        color=color,
        shrinkA=0,
        shrinkB=1,
        zorder=2,
    )
    ax.add_patch(arrow)


def down(ax, x, y1, y2, color=GRAY):
    edge(ax, [(x, y1), (x, y2)], color=color)


def note(ax, x, y, label, size=8.3, color=GRAY):
    artist = text(ax, x, y, label, size=size, color=color)
    artist.set_bbox({
        "facecolor": WHITE,
        "edgecolor": "none",
        "pad": 1.2,
    })


def footer(ax, height, value):
    ax.plot([0.28, 6.02], [height - 0.52, height - 0.52],
            color=LIGHT, linewidth=1)
    text(ax, 0.28, height - 0.28, value,
         size=8, color=GRAY, ha="left")


def save(fig, filename):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for target_fig, artist, bounds in TEXT_ITEMS:
        if target_fig is not fig or bounds is None:
            continue
        x, y, w, h = bounds
        p1 = artist.axes.transData.transform((x, y))
        p2 = artist.axes.transData.transform((x + w, y + h))
        left, right = sorted((p1[0], p2[0]))
        bottom, top = sorted((p1[1], p2[1]))
        extent = artist.get_window_extent(renderer)
        if (
            extent.x0 < left + 3 or extent.x1 > right - 3
            or extent.y0 < bottom + 3 or extent.y1 > top - 3
        ):
            raise RuntimeError(
                f"상자 안의 글자 배치를 확인하세요: {artist.get_text()}"
            )
    destination = OUTPUT / filename
    fig.savefig(destination, dpi=200)
    plt.close(fig)
    print(destination.relative_to(ROOT))


def draw_current_process():
    height = 9.2
    fig, ax = canvas(
        height,
        "일정 변경, 여행자가 다시 잇는 과정",
        "휴무·지연·운행 중단 이후, 확인부터 전달까지 직접 처리",
    )

    steps = [
        ("1  알아채기", "현장에 도착하거나 공지를 보고 문제 발견"),
        ("2  사실 확인", "영업·운행·예약 조건을 각각 다시 확인"),
        ("3  대안 찾기", "갈 수 있는 장소와 이동 수단을 재탐색"),
        ("4  이동 재계산", "이동 시간과 다음 예약에 미칠 영향 확인"),
        ("5  업체 연락", "변경·취소 가능 여부를 묻고 같은 정보를 재설명"),
        ("6  동행자 전달", "바뀐 장소·시각·다음 행동을 다시 공유"),
    ]
    for index, (title, body) in enumerate(steps):
        y = 1.05 + index * 0.91
        box(ax, 0.70, y, 4.90, 0.70, title, body)
        if index < len(steps) - 1:
            down(ax, 3.15, y + 0.70, y + 0.91)

    text(ax, 3.15, 6.93, "전달을 마쳐도 세 상태는 따로 남는다",
         size=11, weight="bold", color=ORANGE)

    box(ax, 0.28, 7.27, 1.80, 0.91,
        "우리 일정", "계획에서 바꾼\n장소와 시각", color=ORANGE)
    box(ax, 2.25, 7.27, 1.80, 0.91,
        "업체 예약", "예약처가 확정한\n변경 여부", color=GRAY)
    box(ax, 4.22, 7.27, 1.80, 0.91,
        "실제 이동", "여행자가 향하는\n목적지와 경로", color=GRAY)

    text(ax, 3.15, 8.47,
         "일정 수정만으로 예약 변경과 실제 이동이 함께 맞춰지지 않는다.",
         size=9, color=ORANGE)
    footer(ax, height, "근거: 기획서 실무본 · 문제 정의")
    save(fig, "D1_변경대응_현재과정_코덱스.png")


def draw_architecture():
    height = 11.5
    fig, ax = canvas(
        height,
        "여행 관리 시스템 구성과 실행 경계",
        "실선: 기존 기반·참여 주체   점선: 구현·보강·연결 예정",
    )

    box(ax, 0.35, 1.00, 1.85, 0.50, "개인 에이전트")
    box(ax, 2.45, 1.00, 1.85, 0.50, "여행자")

    box(ax, 0.35, 1.78, 1.85, 0.63,
        "인증 연동", "기존 기반 · 권한 보강", body_size=8.2)
    box(ax, 2.45, 1.78, 1.85, 0.63,
        "여행계획서 링크", "최신 상태의 정본", planned=True,
        body_size=8.2)
    down(ax, 1.275, 1.50, 1.78)
    down(ax, 3.375, 1.50, 1.78)

    ax.add_patch(FancyBboxPatch(
        (0.20, 2.72), 4.25, 7.66,
        boxstyle="round,pad=0,rounding_size=0.08",
        facecolor="#f7f7f7", edgecolor="#bbbbbb",
        linewidth=1, zorder=0,
    ))
    text(ax, 0.38, 2.92, "서비스 코어",
         size=10, weight="bold", ha="left")

    box(ax, 0.40, 3.17, 3.85, 0.58,
        "대상·요청 분류", "객체 종류와 요청 의도로 모듈 선택",
        body_size=8.5)
    edge(ax, [(1.275, 2.41), (1.275, 2.58),
              (1.85, 2.58), (1.85, 3.17)])
    edge(ax, [(3.375, 2.41), (3.375, 2.58),
              (2.80, 2.58), (2.80, 3.17)])

    text(ax, 2.325, 4.02, "업무 판정 모듈 여섯 · 제안만 생성",
         size=9.2, color=BLUE, weight="bold")
    module_specs = [
        (0.42, 4.22, "활동", BLUE),
        (2.40, 4.22, "식사", BLUE),
        (0.42, 4.82, "이동", BLUE),
        (2.40, 4.82, "예약 인계", BLUE),
        (0.42, 5.42, "숙박 · 등록만", GRAY),
        (2.40, 5.42, "항공 · 등록만", GRAY),
    ]
    for x, y, label, color in module_specs:
        box(ax, x, y, 1.82, 0.43, label,
            color=color, planned=True, size=9.1)

    down(ax, 2.325, 3.75, 3.86, color=BLUE)
    down(ax, 2.325, 5.91, 6.13, color=BLUE)

    box(ax, 0.40, 6.13, 3.85, 0.63,
        "코드 검증", "시간·이동·예산·동행·예약 조건",
        planned=True)
    box(ax, 0.40, 7.19, 3.85, 0.76,
        "실행 게이트", "권한 검사 · 시연용 공급자만 자동 실행\n실제 업체 자동 변경 차단",
        planned=True, color=ORANGE, body_size=8.5)
    down(ax, 2.325, 6.76, 7.19)

    box(ax, 0.40, 8.33, 3.85, 0.76,
        "여행 상태", "최신 일정·잠긴 예약·조건·변경 이력\n버전 검사 후 함께 저장",
        planned=True, body_size=8.5)
    down(ax, 2.325, 7.95, 8.33)

    box(ax, 0.40, 9.51, 3.85, 0.61,
        "배달 루프", "알림 재시도 · 중복 발송 차단",
        planned=True)
    down(ax, 2.325, 9.09, 9.51)

    box(ax, 4.70, 2.98, 1.30, 0.79,
        "감시 루프", "변경 비교\n사건 생성",
        planned=True, size=9.2, body_size=8.4)
    edge(ax, [(4.70, 3.45), (4.25, 3.45)],
         color=BLUE, dashed=True)

    box(ax, 4.70, 4.12, 1.30, 1.48,
        "외부 데이터",
        "장소·영업\n기상·운행\n도로·경로\n정책·대체 소스",
        planned=True, size=9.2, body_size=8.2)
    edge(ax, [(5.35, 4.12), (5.35, 3.77)],
         color=BLUE, dashed=True)
    edge(ax, [(4.70, 4.45), (4.22, 4.45)],
         color=BLUE, dashed=True)

    box(ax, 4.70, 6.11, 1.30, 0.76,
        "人".replace("人", "사람 인계"),
        "실패·충돌\n解決".replace("解決", "검토"),
        planned=True, color=ORANGE, size=9.2, body_size=8.3)
    edge(ax, [(4.25, 6.45), (4.70, 6.45)],
         color=ORANGE, dashed=True)

    box(ax, 4.70, 7.21, 1.30, 0.74,
        "업체 예약처", "변경 링크\n승인 필요",
        color=ORANGE, size=9.2, body_size=8.3)
    edge(ax, [(4.25, 7.60), (4.70, 7.60)],
         color=ORANGE, dashed=True)

    box(ax, 4.70, 9.44, 1.30, 0.76,
        "디스코드", "고객 알림",
        planned=True, size=9.2, body_size=8.5)
    edge(ax, [(4.25, 9.82), (4.70, 9.82)],
         color=BLUE, dashed=True)

    edge(ax, [(0.40, 8.71), (0.29, 8.71),
              (0.29, 2.52), (3.375, 2.52), (3.375, 2.41)],
         color=BLUE, dashed=True)

    text(ax, 3.15, 10.66,
         "되돌림·다른 안 요청도 두 접점에서 같은 검증 경로로 들어간다.",
         size=8.8)
    footer(ax, height, "근거: 기획서 실무본 · 시스템 구성 기획 · 구현 계획 기준")
    save(fig, "D2_시스템구성_코덱스.png")


def draw_change_flow():
    height = 12.0
    fig, ax = canvas(
        height,
        "변경을 감지하고 하나의 일정으로 적용",
        "후보는 비교하되 하나를 선택 · 실패하면 기존 상태 보존",
    )

    x, w, center = 0.35, 3.73, 2.215

    box(ax, 0.35, 1.03, 1.78, 0.57,
        "시스템 감지", "기상·운행·도로", body_size=8.3)
    box(ax, 2.30, 1.03, 1.78, 0.57,
        "고객 신고·질문", "지연·휴무·품절", body_size=8.3)
    edge(ax, [(1.24, 1.60), (1.24, 1.76),
              (center, 1.76), (center, 1.94)])
    edge(ax, [(3.19, 1.60), (3.19, 1.76), (center, 1.76)])

    box(ax, x, 1.94, w, 0.65,
        "사건 묶음", "영향받은 항목·잠긴 예약·현재 버전")
    down(ax, center, 2.59, 2.85)

    box(ax, x, 2.85, w, 0.62,
        "후보 생성", "남은 일정과 필수 조건을 바탕으로 조합")
    down(ax, center, 3.47, 3.76)

    box(ax, x, 3.76, w, 0.77,
        "판정에 필요한 값 확보", "영업·기상·경로·이동 시간\n출처와 확인 시각 기록",
        body_size=8.5)
    box(ax, 4.65, 3.76, 1.35, 0.85,
        "대체 소스", "1차 실패 시 조회\n성공하면 값 반환",
        size=9.2, body_size=8.0)
    edge(ax, [(4.08, 4.17), (4.65, 4.17)],
         color=BLUE, both=True)

    down(ax, center, 4.53, 4.96)
    box(ax, x, 4.96, w, 0.84,
        "탈락 규칙 적용", "필수 조건 위반 후보 제외\n시간·이동·예산·동행·예약",
        body_size=8.5)

    box(ax, 4.65, 4.99, 1.35, 0.80,
        "치명 결함", "대체도 실패\n서버 중단",
        color=ORANGE, size=9.2, body_size=8.3)
    down(ax, 5.325, 4.61, 4.99, color=ORANGE)

    down(ax, center, 5.80, 6.16)
    box(ax, x, 6.16, w, 0.74,
        "하나를 골라 적용 준비", "동률이어도 하나 선택\n선택 근거와 확인 시각 기록",
        body_size=8.5)
    down(ax, center, 6.90, 7.24)

    box(ax, x, 7.24, w, 0.80,
        "전체 일정 재검증", "필수 조건·권한·최신 버전 검사\n버전 충돌은 재계산",
        body_size=8.5)

    box(ax, 4.65, 7.10, 1.35, 1.12,
        "상태 보존", "기존 일정 유지\n부분 적용 금지\n사람에게 인계",
        color=ORANGE, size=9.2, body_size=8.2)
    down(ax, 5.325, 5.79, 7.10, color=ORANGE)

    edge(ax, [(4.08, 5.42), (4.35, 5.42),
              (4.35, 7.37), (4.65, 7.37)], color=ORANGE)
    note(ax, 4.35, 6.22, "후보\n없음", size=8, color=ORANGE)
    edge(ax, [(4.08, 7.77), (4.65, 7.77)], color=ORANGE)
    note(ax, 4.37, 7.62, "실패", size=8, color=ORANGE)

    down(ax, center, 8.04, 8.51, color=BLUE)
    note(ax, center, 8.27, "통과", color=BLUE)
    box(ax, x, 8.51, w, 0.78,
        "일정·알림 함께 저장", "버전 조건부 쓰기 · 원자적 변경\n중복·부분 적용·낡은 버전 방지",
        body_size=8.4)
    down(ax, center, 9.29, 9.69)

    box(ax, x, 9.69, w, 0.84,
        "최신 일정과 다음 행동 안내", "여행계획서 링크 갱신 · 알림 배달\n고객은 되돌림·다른 안 요청 가능",
        body_size=8.4)
    box(ax, 4.65, 9.61, 1.35, 1.00,
        "업체 예약", "변경 링크 인계\n고객 승인 필요\n완료 여부 별도",
        color=ORANGE, size=9.2, body_size=8.1)
    edge(ax, [(4.08, 10.10), (4.65, 10.10)], color=ORANGE)

    text(ax, 3.15, 11.00,
         "내부 일정 적용과 실제 업체 예약 변경은 별도로 관리한다.",
         size=9.2, color=ORANGE, weight="bold")
    footer(ax, height, "근거: 기획서 실무본 · 시스템 구성 기획 · 모델링 계획")
    save(fig, "D3_변경선택실패_코덱스.png")


def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(
            "워크스페이스 루트에서 실행하세요. 입력 파일을 찾을 수 없습니다: "
            + str(SOURCE)
        )

    source_text = SOURCE.read_text(encoding="utf-8-sig")
    required_sections = ("문제 정의", "시스템 구성 기획", "모델링 계획")
    if not all(section in source_text for section in required_sections):
        raise ValueError("입력 기획서의 필수 절을 확인할 수 없습니다.")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    draw_current_process()
    draw_architecture()
    draw_change_flow()


if __name__ == "__main__":
    main()
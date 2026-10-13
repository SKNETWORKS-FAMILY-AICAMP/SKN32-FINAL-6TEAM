# -*- coding: utf-8 -*-
"""취소·환불 한 건이 시스템을 지나는 것을 프레임마다 그려서 영상으로 만든다.

    python program/onboarding/trace/animate_case.py

★이건 슬라이드쇼가 아니다. 정지 그림을 확대하거나 넘기지 않는다.
  화면 하나가 계속 살아 있고, 그 안에서 케이스 하나가 실제로 움직인다.
  매 프레임을 그 시각(t)의 상태로 새로 그린다.

  `make_trace_video.py` 와 `make_trace_video_youtube.py` 는 미리 만든 PNG 를
  카메라로 훑는 방식이다. 근본이 다르므로 지우지 않고 따로 둔다.

무엇이 움직이나
  - 케이스 토큰 하나가 열두 역을 순서대로 지난다. 길을 따라 실제로 이동한다
  - 지나간 길은 색이 차오르고, 지금 있는 역은 커지며 빛난다
  - 오른쪽 기록판에 값이 한 줄씩 쌓인다. 새로 생긴 줄은 미끄러져 들어온다
  - 상태 배지가 바뀔 때 이전 값이 사라지고 새 값이 올라온다

수치와 코드 경로는 `program/onboarding/trace_refund_case.html` 에서 가져왔다.
지어낸 값은 없다.
"""
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
OUT = HERE / "취소환불_케이스_움직임.mp4"

W, H, FPS = 1920, 1080, 30

BG = (247, 248, 251)
INK = (22, 28, 40)
DIM = (107, 116, 136)
FAINT = (168, 176, 192)
LINE = (219, 224, 234)
CARD = (255, 255, 255)
RED = (184, 68, 47)        # 코어 2
BLUE = (47, 91, 216)       # 코어 1
GREEN = (13, 122, 77)      # 모델
PURPLE = (107, 63, 160)    # 근거 조합
GREY = (107, 116, 136)     # 기록

FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _cache:
        name = "malgunbd.ttf" if bold else "malgun.ttf"
        _cache[key] = ImageFont.truetype(str(FONTS / name), size)
    return _cache[key]


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


# ── 열두 역 ────────────────────────────────────────────────────────────────
# (번호, 짧은 이름, 담당, 색, 오른쪽 기록판에 더할 줄, 상태 배지)
STATIONS = [
    (1, "신원 확인", "코어 2 · 정세환", RED,
     [("Principal", 'tenant_id = "demo"'), ("", 'scopes = {"case:write"}')],
     None, "API 키를 확인한다. 여기서 붙은 tenant_id 가 이후 모든 조회에 붙는다."),
    (2, "중복 확인", "코어 2 · 정세환", RED,
     [("멱등성 키", "a3f1c9... (sha256)"), ("", "action_requests 조회 = 없음")],
     None, "같은 요청이 아까 왔는지 먼저 본다. 두 번 눌러도 Case 는 하나다."),
    (3, "Case 생성", "코어 1 · 최연우", BLUE,
     [("customer_cases", "1행 생성"), ("case_events", "created")],
     ("classifying", 1), "행과 이벤트가 한 트랜잭션이다. new 는 찰나에만 있다."),
    (4, "문의 분류", "모델 · 송채영", GREEN,
     [("intent", '"return"'), ("issue_code", '"return_fee_or_period"'),
      ("sentiment", '"negative"')],
     ("routing", 2), '"취소" 라고 썼지만 환불을 원하는 문의라 return 으로 간다.'),
    (5, "팀 라우팅", "코어 1 · 최연우", BLUE,
     [("owner_team_id", '"return_refund"')],
     ("running", 3), "여섯 팀의 자기소개만 보고 고른다. 정확히 하나여야 한다."),
    (6, "기능 선택", "코어 1 · 최연우", BLUE,
     [("capability", '"return.check_eligibility"')],
     None, "intent 로 시작하는 첫 capability 에서 멈춘다."),
    (7, "근거 조합", "근거 조합", PURPLE,
     [("ContextPack", "정책 3,600 토큰"), ("degraded", "false"), ("omissions", "[]")],
     None, "12,000 토큰을 넘으면 정해진 순서로 뺀다. 뺐으면 뺐다고 적는다."),
    (8, "Team 판단", "모델 · 서유현", GREEN,
     [("검사 5종", "전부 통과"), ("next_action", '"respond"'), ("proposals", "[]")],
     None, "환불이 맞다고 판단해도 실행하지 않는다. 제안까지만 돌려준다."),
    (9, "답변 검토", "모델 · 송채영", GREEN,
     [("response_review", "enabled = false")],
     None, "이 단계는 지금 꺼져 있다. 고객이 받는 문장은 코드에 적힌 고정 문구다."),
    (10, "상태 반영", "코어 1 · 최연우", BLUE,
     [("case_events", "completed"), ("state_json", "answer 저장")],
     ("resolved", 4), "답은 나갔는데 기록이 없는 상황이 안 생긴다. 한 트랜잭션이다."),
    (11, "고객 응답", "코어 2 · 정세환", RED,
     [("응답", "status · answer · evidence")],
     None, "답변에 근거가 같이 나간다. 왜 그렇게 판단했는지 되짚을 수 있어야 한다."),
    (12, "기록", "공통", GREY,
     [("남은 표", "customer_cases 1행"), ("", "case_events 4행"),
      ("", "action_requests 1행")],
     None, "지금 상태는 이벤트를 순서대로 적용한 결과다. 언제든 다시 만든다."),
]

INTRO = 7.0
PER = 8.6
OUTRO = 11.0
TOTAL = INTRO + PER * len(STATIONS) + OUTRO

MAP_X, MAP_Y, MAP_W = 70, 230, 1080
COLS, ROWS = 4, 3
CELL_W, CELL_H = MAP_W // COLS, 172
BOX_W, BOX_H = 218, 96


def station_xy(index):
    """뱀 모양으로 배치한다. 12개를 가로로 늘어놓으면 한 칸이 너무 좁다."""
    row, col = divmod(index, COLS)
    if row % 2 == 1:
        col = COLS - 1 - col
    cx = MAP_X + col * CELL_W + CELL_W // 2
    cy = MAP_Y + row * CELL_H + BOX_H // 2
    return cx, cy


def path_points():
    """역과 역을 잇는 길. 줄이 바뀌는 곳은 옆으로 돌아 내려간다."""
    pts = []
    for i in range(len(STATIONS)):
        pts.append(station_xy(i))
        if i + 1 < len(STATIONS) and (i + 1) % COLS == 0:
            row = i // COLS
            cx, cy = station_xy(i)
            edge = cx + BOX_W // 2 + 40 if row % 2 == 0 else cx - BOX_W // 2 - 40
            pts.append((edge, cy))
            pts.append((edge, cy + CELL_H))
    return pts


PATH = path_points()


def token_position(progress):
    """0에서 1 사이 값으로 길 위의 좌표를 돌려준다."""
    segs = [(PATH[i], PATH[i + 1]) for i in range(len(PATH) - 1)]
    lens = [math.dist(a, b) for a, b in segs]
    total = sum(lens)
    want = max(0.0, min(1.0, progress)) * total
    for (a, b), seg_len in zip(segs, lens):
        if want <= seg_len or seg_len == 0:
            t = 0 if seg_len == 0 else want / seg_len
            return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        want -= seg_len
    return PATH[-1]


def progress_at_station(index):
    """역 index 의 중심이 길 전체에서 몇 퍼센트 지점인지.

    ★첫 판은 세그먼트의 시작점만 비교해서 마지막 역과 모퉁이 뒤의 역을 못 찾고
      1.0 을 돌려줬다. 그래서 토큰이 한 역 뒤에 멈춰 있었다.
      길 위의 점을 순서대로 걸으며 그 역의 좌표를 만나는 지점까지 재는 것이 맞다.
    """
    target = station_xy(index)
    total = sum(math.dist(PATH[i], PATH[i + 1]) for i in range(len(PATH) - 1))
    walked = 0.0
    for i, point in enumerate(PATH):
        if math.dist(point, target) < 1:
            return walked / total
        if i + 1 < len(PATH):
            walked += math.dist(point, PATH[i + 1])
    return 1.0


STATION_P = [progress_at_station(i) for i in range(len(STATIONS))]


def rounded(draw, box, r, fill=None, outline=None, width=2):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def centered(draw, cx, y, text, f, fill):
    w = draw.textbbox((0, 0), text, font=f)[2]
    draw.text((cx - w / 2, y), text, font=f, fill=fill)


def state_of(index):
    """역 index 를 지난 시점의 (상태, 버전). 아직 없으면 None."""
    last = None
    for i in range(index + 1):
        if STATIONS[i][5]:
            last = STATIONS[i][5]
    return last


def rows_until(index):
    """역 index 까지 쌓인 기록판 줄. (역번호, 이름, 값)."""
    out = []
    for i in range(index + 1):
        for name, value in STATIONS[i][4]:
            out.append((STATIONS[i][0], name, value))
    return out


def draw_frame(t):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img, "RGBA")

    # ── 머리말 ──────────────────────────────────────────────────────────
    d.text((70, 62), "취소·환불 한 건이 지나는 길", font=font(40, True), fill=INK)
    d.text((70, 122), '"어제 주문한 거 취소하고 환불받고 싶어요. 아직 안 왔어요."',
           font=font(21), fill=DIM)
    d.line([(70, 186), (W - 70, 186)], fill=LINE, width=2)

    intro = ease(t / INTRO) if t < INTRO else 1.0
    if t < INTRO:
        alpha = int(255 * (1 - intro))
        if alpha > 4:
            d.rectangle([(0, 200), (W, H)], fill=(BG[0], BG[1], BG[2], alpha))

    # 지금 몇 번째 역인가
    if t < INTRO:
        idx, local = -1, 0.0
    else:
        raw = (t - INTRO) / PER
        idx = min(len(STATIONS) - 1, int(raw))
        local = raw - idx
    outro = t > INTRO + PER * len(STATIONS)

    # 길 위의 위치. 앞 절반은 이동, 뒤 절반은 그 역에 머문다.
    if idx < 0:
        travel = 0.0
    elif idx == 0:
        travel = STATION_P[0] * ease(local / 0.35)
    else:
        prev, here = STATION_P[idx - 1], STATION_P[idx]
        travel = prev + (here - prev) * ease(local / 0.35)
    if outro:
        travel = 1.0

    # ── 지나온 길 ───────────────────────────────────────────────────────
    for i in range(len(PATH) - 1):
        d.line([PATH[i], PATH[i + 1]], fill=(226, 231, 240), width=9)
    steps = 260
    done_pts = [token_position(k / steps * travel) for k in range(steps + 1)]
    for i in range(len(done_pts) - 1):
        share = i / max(1, len(done_pts) - 1)
        color = mix(RED, GREEN, share)
        d.line([done_pts[i], done_pts[i + 1]], fill=color, width=9)

    # ── 역 열두 개 ──────────────────────────────────────────────────────
    for i, (num, name, owner, color, _rows, _st, _cap) in enumerate(STATIONS):
        cx, cy = station_xy(i)
        passed, now = i < idx, i == idx
        grow = 12 * ease((local - 0.30) / 0.25) if now else 0
        bw, bh = BOX_W + grow, BOX_H + grow
        box = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)

        if now:
            for k in range(3):     # 지금 역은 테두리를 겹쳐 빛나게 한다
                pad = 8 + k * 7
                rounded(d, (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad),
                        20 + pad, outline=color + (46 - k * 14,), width=3)
            fill, edge, tone = color, color, (255, 255, 255)
        elif passed:
            fill, edge, tone = CARD, color, color
        else:
            fill, edge, tone = (243, 245, 249), (226, 231, 240), FAINT

        rounded(d, box, 18, fill=fill, outline=edge, width=3 if now else 2)
        centered(d, cx, cy - 34, "%d" % num, font(21, True),
                 tone if now else (color if passed else FAINT))
        centered(d, cx, cy - 6, name, font(23, True), tone)
        centered(d, cx, cy + 26, owner.split(" · ")[0], font(16),
                 (255, 255, 255, 205) if now else FAINT)

    # ── 케이스 토큰 ─────────────────────────────────────────────────────
    # ★역에 도착하면 토큰이 역 이름을 덮는다. 도착하는 순간 역 안으로 흡수시킨다.
    #   "그 역에서 처리되는 중" 이라는 뜻도 같이 된다.
    land = 1.0 - ease((local - 0.30) / 0.10) if idx >= 0 else 0.0
    if idx >= 0 and not outro and land > 0.02:
        tx, ty = token_position(travel)
        pulse = 1 + 0.10 * math.sin(t * 6.0)
        for r, a in ((40 * pulse, 26), (28 * pulse, 52)):
            rr = r * (0.4 + 0.6 * land)
            d.ellipse((tx - rr, ty - rr, tx + rr, ty + rr),
                      fill=(255, 176, 32, int(a * land)))
        core = 15 * (0.4 + 0.6 * land)
        d.ellipse((tx - core, ty - core, tx + core, ty + core),
                  fill=(255, 158, 20) + (int(255 * land),),
                  outline=(255, 255, 255) + (int(255 * land),), width=3)

    # ── 오른쪽 기록판 ───────────────────────────────────────────────────
    px, py, pw, ph = 1240, 230, 610, 640
    rounded(d, (px, py, px + pw, py + ph), 20, fill=CARD, outline=LINE, width=2)
    d.text((px + 26, py + 22), "지금까지 만들어진 것", font=font(23, True), fill=INK)
    d.text((px + 26, py + 56), "값이 정해질 때마다 한 줄씩 쌓인다",
           font=font(16), fill=DIM)

    rows = rows_until(idx) if idx >= 0 else []
    fresh = len(STATIONS[idx][4]) if idx >= 0 else 0
    slide = ease((local - 0.34) / 0.24) if idx >= 0 else 0.0

    y = py + 104
    for i, (num, name, value) in enumerate(rows):
        new = i >= len(rows) - fresh
        if new and slide <= 0.01:
            continue
        off = (1 - slide) * 26 if new else 0
        a = int(255 * (slide if new else 1.0))
        color = STATIONS[num - 1][3]
        d.text((px + 26, y + off), "%02d" % num, font=font(14, True), fill=color + (a,))
        if name:
            d.text((px + 62, y + off), name, font=font(18, True), fill=INK + (a,))
        d.text((px + 250, y + off), value, font=font(18), fill=DIM + (a,))
        y += 31
        if y > py + ph - 40:
            break

    # ── 상태 배지 ───────────────────────────────────────────────────────
    bx, by = 1240, 910
    d.text((bx, by - 34), "Case 상태", font=font(17, True), fill=DIM)
    st = state_of(idx) if idx >= 0 else None
    if st is None:
        rounded(d, (bx, by, bx + 300, by + 62), 16, fill=(243, 245, 249),
                outline=LINE, width=2)
        d.text((bx + 24, by + 18), "아직 Case 가 없다", font=font(21), fill=FAINT)
    else:
        name, version = st
        just = STATIONS[idx][5] is not None
        pop = 1.0 if not just else ease(local / 0.30)
        color = BLUE if name != "resolved" else GREEN
        rounded(d, (bx, by, bx + 300, by + 62), 16, fill=CARD, outline=color, width=3)
        d.text((bx + 24, by + 16), "%s   v%d" % (name, version), font=font(25, True),
               fill=color + (int(255 * (0.35 + 0.65 * pop)),))
        if just and pop < 1.0:
            r = 34 + 76 * (1 - pop)
            d.ellipse((bx + 150 - r, by + 31 - r, bx + 150 + r, by + 31 + r),
                      outline=color + (int(150 * (1 - pop)),), width=4)

    # ── 아래 설명 ───────────────────────────────────────────────────────
    if idx >= 0 and not outro:
        num, name, owner, color, _r, _s, cap = STATIONS[idx]
        fade = min(ease(local / 0.18), ease((1 - local) / 0.14))
        a = int(255 * fade)
        rounded(d, (70, 905, 1160, 1010), 16, fill=CARD + (a,),
                outline=color + (a,), width=2)
        d.text((96, 921), "%02d  %s" % (num, name), font=font(20, True), fill=color + (a,))
        d.text((96, 955), cap, font=font(21), fill=INK + (a,))
        d.text((1134 - d.textbbox((0, 0), owner, font=font(16))[2], 923), owner,
               font=font(16), fill=DIM + (a,))

    # ── 마무리 ──────────────────────────────────────────────────────────
    if outro:
        k = ease((t - (INTRO + PER * len(STATIONS))) / 2.4)
        a = int(248 * k)
        d.rectangle([(0, 0), (W, H)], fill=(12, 16, 26, a))
        if k > 0.25:
            f = ease((k - 0.25) / 0.55)
            # ★글 뒤에 판을 깐다. 덮개만으로는 뒤 화면 글자가 비쳐 읽기 힘들다.
            rounded(d, (W / 2 - 560, 330, W / 2 + 560, 700), 26,
                    fill=(20, 26, 40, int(235 * f)), outline=(70, 84, 112, int(200 * f)),
                    width=2)
            centered(d, W / 2, 372, "문의 한 건이 남긴 것", font(44, True),
                     (255, 255, 255, int(255 * f)))
            lines = ["customer_cases 1행 · case_events 4행 · action_requests 1행",
                     "새로 생긴 파일은 하나도 없다. 전부 데이터베이스 행이다.",
                     "지금 상태는 이벤트를 순서대로 적용한 결과다. 언제든 다시 만든다."]
            for i, line in enumerate(lines):
                centered(d, W / 2, 470 + i * 52, line, font(26),
                         (222, 228, 240, int(255 * ease((k - 0.35 - i * 0.10) / 0.4))))
    return img


def main():
    frames = int(TOTAL * FPS)
    print("길이 %d분 %d초 · %d프레임" % (TOTAL // 60, TOTAL % 60, frames))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(OUT)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(frames):
        proc.stdin.write(np.asarray(draw_frame(n / FPS), dtype=np.uint8).tobytes())
        if n % (FPS * 10) == 0:
            print("   %3d%%" % (100 * n // frames))
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg 실패")
    print("만듦: %s  (%.1f MB)" % (OUT, OUT.stat().st_size / 1048576))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""화면과 같은 배치를 프레임마다 그려서 영상으로 만든다.

    python program/onboarding/trace/animate_sheets.py

★슬라이드쇼가 아니다. 미리 만든 그림을 넘기지 않는다. 매 프레임을 그 시각의
  상태로 새로 그린다. 줄이 한 줄씩 나타나고, 화살표가 밀고, 오른쪽 칸에
  덩어리가 미끄러져 들어온다.

★내용을 옮겨 적지 않는다. `sheet_data.SHEETS` 와 `trace_data.STEPS` 를 쓴다.
  화면(취소환불_케이스_추적_그림.html)과 같은 값이므로 둘이 어긋날 수 없다.
  낱장의 원본은 `trace/steps.py` 다.

★`animate_case.py` 는 지우지 않는다. 그쪽은 노선도 위를 토큰이 지나는 다른
  그림이다. 이 파일은 낱장 배치를 그대로 움직이는 것이다.
"""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from sheet_data import BAR, SHEETS  # noqa: E402
from trace_data import FILES_NOTE, STEPS  # noqa: E402

OUT = HERE / "취소환불_케이스_낱장.mp4"
W, H, FPS = 1920, 1080, 30

BG = (245, 246, 250)
CARD = (255, 255, 255)
SOFT = (251, 252, 254)
WARM = (255, 253, 246)
INK = (22, 28, 40)
DIM = (107, 116, 136)
FAINT = (152, 161, 180)
LINE = (219, 224, 234)
TODO = (242, 244, 248)
DONE = (226, 230, 238)

FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
_cache = {}


def font(size, bold=False, mono=False):
    key = (size, bold, mono)
    if key not in _cache:
        if mono:
            name = "consolab.ttf" if bold else "consola.ttf"
        else:
            name = "malgunbd.ttf" if bold else "malgun.ttf"
        path = FONTS / name
        # ★윈도우 글꼴 자리를 못 박고 쓴다. 다른 운영체제나 글꼴이 빠진
        #   윈도우에서는 여기서 무슨 파일이 없는지 알려 주고 멈춘다.
        #   PIL 이 내는 OSError 만 보면 무엇을 깔아야 하는지 알 수 없다.
        if not path.exists():
            raise SystemExit(
                "글꼴이 없다: %s\n"
                "  이 영상은 윈도우의 맑은 고딕(malgun)과 Consolas 를 쓴다.\n"
                "  다른 환경에서 돌리려면 FONTS 를 그 환경의 글꼴 폴더로 바꾼다." % path)
        _cache[key] = ImageFont.truetype(str(path), size)
    return _cache[key]


def has_hangul(text):
    return any("가" <= ch <= "힣" or "ㄱ" <= ch <= "ㆎ" for ch in text)


def tfont(text, size, bold=False, mono=True):
    """글자에 맞는 글꼴. Consolas 에는 한글이 없어 네모로 깨진다.

    ★고정폭이 예쁘다고 한글까지 Consolas 로 넘기면 전부 두부가 된다.
      한글이 한 자라도 섞이면 맑은 고딕으로 통째로 그린다.
    """
    return font(size, bold, mono=(mono and not has_hangul(text)))


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


def wrap(draw, text, f, width):
    """글자 폭을 재서 줄을 나눈다. 한글은 어절 단위로 끊는다."""
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=f) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ── 시간표 ────────────────────────────────────────────────────────────────
# 한 단계 안에서 무엇이 언제 나타나는지. 초 단위이고 단계 시작이 0 이다.
T_CARD = 0.00, 0.40      # 낱장이 올라온다
T_IN = 0.45, 1.30        # 들어온 문서가 한 줄씩
T_ARROW = 1.35, 1.70     # 화살표가 민다
T_OUT = 1.70, 2.90       # 나간 문서가 한 줄씩, 바뀐 줄은 색으로
T_CHIP = 2.95, 3.25      # 상태 칩
T_PACK = 3.30, 3.95      # 오른쪽 칸에 덩어리가 들어온다
T_WHY = 4.00, 4.35       # 설명이 밝아진다
STEP = 5.2               # 한 단계 길이
INTRO, OUTRO = 4.0, 5.0
TOTAL = INTRO + STEP * len(SHEETS) + OUTRO


def seg(t, span):
    """span=(a,b) 안에서 0..1. 밖이면 0 또는 1."""
    a, b = span
    if t <= a:
        return 0.0
    if t >= b:
        return 1.0
    return ease((t - a) / (b - a))


def reveal(t, span, count, i):
    """줄 i 가 얼마나 나타났나. count 줄이 span 안에서 차례로 나온다."""
    if count <= 0:
        return 0.0
    a, b = span
    hold = (b - a) / max(count, 1)
    return seg(t, (a + hold * i, a + hold * i + hold * 1.4))


def rounded(d, box, r, fill=None, outline=None, width=2):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def fade_text(d, xy, text, f, color, alpha, dx=0.0):
    if alpha <= 0.01:
        return
    d.text((xy[0] + dx, xy[1]), text, font=f, fill=mix(BG, color, alpha))


# ── 화면 조각 ─────────────────────────────────────────────────────────────
def draw_bar(d, idx, sub):
    """열두 칸 진행바. 화면 위쪽에 있는 것과 같다."""
    x0, x1, y = 40, W - 40, 74
    gap, n = 7, len(BAR)
    cw = (x1 - x0 - gap * (n - 1)) / n
    for i, b in enumerate(BAR):
        x = x0 + i * (cw + gap)
        color = rgb(b["color"])
        if i < idx:
            fill, num, nm = DONE, (143, 151, 168), (170, 178, 193)
        elif i == idx:
            fill = mix(TODO, color, ease(min(sub / 0.35, 1.0)))
            num, nm = (255, 255, 255), color
        else:
            fill, num, nm = TODO, (188, 195, 208), (170, 178, 193)
        rounded(d, (x, y, x + cw, y + 30), 7, fill=fill)
        f = font(17, bold=(i == idx))
        t = str(i + 1)
        d.text((x + cw / 2 - d.textlength(t, font=f) / 2, y + 4), t, font=f, fill=num)
        f2 = font(17, bold=(i == idx))
        d.text((x + cw / 2 - d.textlength(b["name"], font=f2) / 2, y + 36),
               b["name"], font=f2, fill=nm)


def draw_sheet(d, s, t, color):
    """낱장. 구조 좌표 / 들어온 문서 / 화살표 / 나간 문서 / 칩 / 코드 / 설명."""
    x0, y0, x1, y1 = 40, 140, 1370, 1000
    rise = (1 - seg(t, T_CARD)) * 26
    y0 += rise
    rounded(d, (x0, y0, x1, y1 + rise), 18, fill=CARD, outline=LINE, width=2)
    a = seg(t, T_CARD)

    # 머리
    fade_text(d, (x0 + 30, y0 + 24), "%02d" % s["n"], font(58, True), color, a)
    fade_text(d, (x0 + 108, y0 + 42), s["head"], font(36, True), INK, a)
    ry = y0 + 34
    for i, line in enumerate(s["action"]):
        f = font(21, bold=(i == 0))
        tw = d.textlength(line, font=f)
        fade_text(d, (x1 - 30 - tw, ry), line, f, INK if i == 0 else DIM, a)
        ry += 28

    top = y0 + 118
    bot = y0 + 560

    # 왼쪽 구조 좌표
    cx0, cx1 = x0 + 26, x0 + 330
    rounded(d, (cx0, top, cx1, bot), 13, fill=SOFT, outline=color, width=2)
    fade_text(d, (cx0 + 16, top + 13), "구조 좌표", font(20, True), color, a)
    cy = top + 48
    for label, values in s["coord"]:
        fade_text(d, (cx0 + 16, cy), label, font(17), FAINT, a)
        cy += 23
        for v in values:
            fade_text(d, (cx0 + 16, cy), v, font(20), INK, a)
            cy += 26
        cy += 12

    # 가운데 두 문서
    gap = 26
    dw = (x1 - 26 - (cx1 + 22) - gap - 52) / 2
    ix0 = cx1 + 22
    ox0 = ix0 + dw + gap + 52

    def one(dx0, label, lines, marks, span, ec, lab_color):
        rounded(d, (dx0, top, dx0 + dw, bot), 13, fill=SOFT, outline=ec, width=2)
        fade_text(d, (dx0 + 16, top + 13), label, font(20, True), lab_color, a)
        ly = top + 48
        for i, line in enumerate(lines):
            r = reveal(t, span, len(lines), i)
            on = i in marks
            fade_text(d, (dx0 + 18, ly), line, font(20, bold=on),
                      color if on else INK, r, dx=(1 - r) * -10)
            ly += 31

    one(ix0, s["in_label"], s["in_lines"], set(), T_IN, LINE, DIM)
    one(ox0, s["out_label"], s["out_lines"], set(s["mark"]), T_OUT, color, color)

    # 화살표. 밀고 지나간다.
    ap = seg(t, T_ARROW)
    ax = ix0 + dw + 12 + ap * 22
    ay = (top + bot) / 2
    if ap > 0.01:
        c = mix(BG, color, ap)
        d.line([(ax, ay), (ax + 26, ay)], fill=c, width=5)
        d.polygon([(ax + 26, ay - 11), (ax + 42, ay), (ax + 26, ay + 11)], fill=c)

    # 상태 칩
    ca = seg(t, T_CHIP)
    chx = x0 + 26
    for label, hexcolor in s["states"]:
        cc = rgb(hexcolor)
        f = tfont(label, 21, True)
        tw = d.textlength(label, font=f) + 40
        if ca > 0.01:
            rounded(d, (chx, bot + 24, chx + tw, bot + 70), 11,
                    fill=CARD, outline=mix(BG, cc, ca), width=3)
            d.text((chx + 20, bot + 33), label, font=f, fill=mix(BG, cc, ca))
        chx += tw + 14

    # 코드 경로
    fade_text(d, (x0 + 26, bot + 92), "코드", font(17, True), FAINT, a)
    fade_text(d, (x0 + 76, bot + 92), s["code"], tfont(s["code"], 19), DIM, a)

    # 설명
    wa = seg(t, T_WHY)
    wy = bot + 128
    rounded(d, (x0 + 26, wy, x1 - 26, wy + 92), 13,
            fill=WARM, outline=mix(LINE, color, wa), width=2)
    dd = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for i, line in enumerate(wrap(dd, s["why"], font(23), x1 - x0 - 100)[:2]):
        fade_text(d, (x0 + 50, wy + 18 + i * 32), line, font(23), INK, a)

    # 파일 이야기
    fy = wy + 108
    fb = font(18, True)
    for head, body in FILES_NOTE:
        fade_text(d, (x0 + 26, fy), head, fb, INK, a)
        ind = x0 + 26 + d.textlength(head, font=fb) + 12
        rows = wrap(dd, body, font(18), x1 - 26 - ind)
        for j, line in enumerate(rows[:2]):
            fade_text(d, (ind if j == 0 else x0 + 26, fy + j * 25), line,
                      font(18), DIM, a)
        fy += 25 * min(len(rows), 2) + 6


def draw_pack(idx, t):
    """오른쪽 누적 칸. 이번에 생긴 것만 색이 들어온다.

    ★덩어리를 따로 그린 뒤 잘라 붙인다. 바로 그리면 넘친 것이 제목 위로
      올라가고 카드 밖으로 새어 나간다.
    """
    x0, x1, y0, y1 = 1400, W - 40, 140, 1000
    card = Image.new("RGB", (x1 - x0, y1 - y0), CARD)
    d = ImageDraw.Draw(card)
    rounded(d, (0, 0, x1 - x0 - 1, y1 - y0 - 1), 18, fill=CARD, outline=LINE, width=2)
    d.text((24, 20), "지금까지 만들어진 것", font=font(24, True), fill=INK)

    fresh = len(STEPS[idx]["add"])
    note = ("%d번 단계에서 %d개가 새로 붙었습니다" % (idx + 1, fresh)) if fresh         else ("%d번 단계는 새로 만드는 것 없이 지나갑니다" % (idx + 1))
    d.text((24, 56), note, font=font(18), fill=DIM)

    color = rgb(SHEETS[idx]["color"])
    pa = seg(t, T_PACK)

    rows = []
    for i in range(idx + 1):
        for kind, name, lines in STEPS[i]["add"]:
            rows.append((STEPS[i]["n"], kind, name, lines, i == idx))

    LH, HH = 22, 34
    top, floor = 92, (y1 - y0) - 96      # ★상태 배지 자리를 남긴다.
    sw, sh = x1 - x0 - 44, floor - top
    surf = Image.new("RGB", (sw, sh), CARD)
    sd = ImageDraw.Draw(surf)

    def height(lines):
        return HH + len(lines) * LH + 14

    total = sum(height(r[3]) + 14 for r in rows)
    y = -max(0, total - sh)              # 넘치면 위를 잘라 낸다. 새 것이 늘 보인다.

    for n, kind, name, lines, is_new in rows:
        h = height(lines)
        yy = y + (1 - pa) * 24 if is_new else y
        alpha = pa if is_new else 1.0
        if yy + h > -20 and yy < sh + 20 and alpha > 0.02:
            ec = mix(CARD, color, alpha) if is_new else LINE
            rounded(sd, (0, yy, sw - 1, yy + h), 11,
                    fill=CARD, outline=ec, width=3 if is_new else 2)
            kf = font(15, True)
            kw = sd.textlength(kind, font=kf)
            if is_new:
                rounded(sd, (2, yy + 2, sw - 3, yy + HH), 9, fill=ec)
                rounded(sd, (10, yy + 7, 24 + kw, yy + HH - 5), 5, fill=(255, 255, 255))
                kc, nc = (26, 32, 48), (255, 255, 255)
            else:
                sd.line([(0, yy + HH), (sw - 1, yy + HH)], fill=LINE, width=2)
                kc, nc = DIM, mix(CARD, INK, alpha)
            sd.text((15, yy + 9), kind, font=kf, fill=kc)
            sd.text((15 + kw + 26, yy + 7), name, font=tfont(name, 19, True), fill=nc)
            if is_new:
                tag = "이번에 생김"
                tw = sd.textlength(tag, font=kf)
                rounded(sd, (sw - 18 - tw - 16, yy + 7, sw - 10, yy + HH - 5), 5,
                        fill=(255, 255, 255))
                sd.text((sw - 26 - tw, yy + 9), tag, font=kf, fill=(26, 32, 48))
            # ★긴 줄은 글자를 줄여서 칸 안에 넣는다. 그냥 그리면 잘려 나간다.
            size = 17
            while size > 13 and any(
                    sd.textlength(l, font=tfont(l, size)) > sw - 30 for l in lines):
                size -= 1
            for i, line in enumerate(lines):
                sd.text((15, yy + HH + 8 + i * LH), line,
                        font=tfont(line, size), fill=mix(CARD, INK, alpha))
        y += h + 14

    card.paste(surf, (22, top))

    # 상태 배지
    st = None
    for i in range(idx + 1):
        if STEPS[i].get("state"):
            st = STEPS[i]["state"]
    by = (y1 - y0) - 66
    d.text((24, by), "Case 상태", font=font(19), fill=DIM)
    if st:
        label = "%s  v%d" % (st[0], st[1])
        c = rgb("#0d7a4d") if st[0] == "resolved" else rgb("#2f5bd8")
        f = tfont(label, 22, True)
        tw = d.textlength(label, font=f) + 34
        rounded(d, (128, by - 8, 128 + tw, by + 38), 10, fill=CARD, outline=c, width=3)
        d.text((145, by - 2), label, font=f, fill=c)
    else:
        d.text((128, by), "아직 Case 가 없습니다", font=font(19), fill=FAINT)
    return card, (x0, y0)


def draw_cover(d, t, closing=False):
    a = ease(min(t / 1.0, 1.0)) if not closing else 1.0
    d.rectangle((0, 0, W, H), fill=BG)
    if closing:
        head = "한 건이 남긴 것"
        lines = ["customer_cases 1행  resolved v4",
                 "case_events 4행  created, classified, routed, completed",
                 "action_requests 1행  succeeded",
                 "agent_runs 1행 · llm_calls 분류에 쓴 프롬프트와 모델",
                 "",
                 "새로 생긴 파일은 없다. 전부 데이터베이스 행이다."]
    else:
        head = "취소·환불 한 건이 지나는 길"
        lines = ['고객: "어제 주문한 거 취소하고 환불받고 싶어요. 아직 안 왔어요."',
                 "",
                 "이 한 문장이 열두 단계를 지나 답으로 돌아올 때까지",
                 "무엇이 어떻게 만들어지는지 한 건으로 따라간다.",
                 "",
                 "왼쪽은 그 단계의 구조 좌표와 문서 두 벌, 오른쪽은 지금까지 쌓인 것이다."]
    f = font(58, True)
    d.text((W / 2 - d.textlength(head, font=f) / 2, 300), head,
           font=f, fill=mix(BG, INK, a))
    for i, line in enumerate(lines):
        if not line:
            continue
        g = tfont(line, 28, mono=(closing and i < 4))
        aa = ease(min(max(t - 0.8 - i * 0.18, 0) / 0.6, 1.0))
        d.text((W / 2 - d.textlength(line, font=g) / 2, 430 + i * 46), line,
               font=g, fill=mix(BG, DIM if i else INK, aa))


def draw_frame(t):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    if t < INTRO:
        draw_cover(d, t)
        return img
    if t >= INTRO + STEP * len(SHEETS):
        draw_cover(d, t - (INTRO + STEP * len(SHEETS)), closing=True)
        return img

    local = t - INTRO
    idx = min(int(local // STEP), len(SHEETS) - 1)
    sub = local - idx * STEP
    color = rgb(SHEETS[idx]["color"])

    d.text((40, 26), "취소·환불 한 건이 지나는 길", font=font(24, True), fill=INK)
    tail = "%d / %d 단계" % (idx + 1, len(SHEETS))
    d.text((W - 40 - d.textlength(tail, font=font(22)), 30), tail,
           font=font(22), fill=DIM)

    draw_bar(d, idx, sub)
    draw_sheet(d, SHEETS[idx], sub, color)
    card, at = draw_pack(idx, sub)
    img.paste(card, at)
    return img


def main():
    frames = int(TOTAL * FPS)
    print("길이 %d분 %d초 · %d프레임 · %dx%d" % (TOTAL // 60, TOTAL % 60, frames, W, H))
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

# -*- coding: utf-8 -*-
"""그림 열일곱 장을 이어 붙여 영상 하나로 만든다.

    python program/onboarding/trace/make_trace_images.py   (먼저 그림을 만든다)
    python program/onboarding/trace/make_trace_video.py

★장면 사이를 겹쳐 넘긴다(crossfade). 툭툭 끊기면 낱장을 순서대로 본 것이지
  하나의 흐름으로 안 읽힌다. 위쪽 진행바가 겹치는 동안 이어져 보이는 것이
  이 영상의 핵심이다.

★머무는 시간을 장마다 다르게 준다. 글이 많은 장을 같은 시간 두면 못 읽는다.
  아래 HOLD 가 그 표다. 단위는 초다.

★libx264 로 뽑고 픽셀 형식을 yuv420p 로 맞춘다. 이걸 안 하면 어떤 재생기와
  브라우저에서 소리 없이 검은 화면만 나온다.
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "images")
OUT = os.path.join(HERE, "취소환불_케이스_추적.mp4")

WIDTH, HEIGHT = 1920, 1080
FPS = 30
FADE = 0.55            # 겹쳐 넘기는 시간

#: 파일 앞머리로 찾는다. 없으면 기본 6.0 초.
HOLD = {
    "00_": 7.0,    # 전체 지도. 처음이라 여유를 준다
    "01_구조": 11.0,  # 항목이 스물일곱 개다. 제일 길게
    "07_": 7.5,    # 근거 조합. 개념이 낯설다
    "08_": 7.5,    # 팀 판단. 검사 다섯 가지
    "13_": 9.0,    # 상태 열둘
    "14_": 9.0,    # 계약 문서
    "15_": 11.0,   # 분기 표 아홉 줄
}
DEFAULT_HOLD = 6.0


def hold_for(name):
    for prefix, seconds in HOLD.items():
        if name.startswith(prefix):
            return seconds
    return DEFAULT_HOLD


def load(path):
    """흰 캔버스 가운데에 비율을 지켜 얹는다. 장마다 높이가 달라서 필요하다."""
    img = Image.open(path).convert("RGB")
    scale = min((WIDTH - 80) / img.width, (HEIGHT - 80) / img.height)
    w, h = int(img.width * scale), int(img.height * scale)
    canvas = Image.new("RGB", (WIDTH, HEIGHT), "white")
    canvas.paste(img.resize((w, h), Image.LANCZOS),
                 ((WIDTH - w) // 2, (HEIGHT - h) // 2))
    return np.asarray(canvas, dtype=np.uint8)


def main():
    # ★파일명 순서가 곧 재생 순서다. 00 전체지도, 01 구조좌표, 그다음 단계 01~12,
    #   마지막 13~15 순으로 정렬된다("구" 가 "문" 보다 앞이라 구조좌표가 먼저 온다).
    #   그림 이름을 바꿀 때 이 순서가 깨지지 않는지 확인한다.
    names = sorted(f for f in os.listdir(SRC) if f.endswith(".png"))
    if not names:
        raise SystemExit("그림이 없다. 먼저 make_trace_images.py 를 돌린다.")
    frames = [load(os.path.join(SRC, n)) for n in names]

    plan = [(n, hold_for(n)) for n in names]
    total = sum(s for _, s in plan) + FADE * (len(plan) - 1)
    print("장면 %d개, 약 %d분 %d초" % (len(plan), total // 60, total % 60))
    for n, s in plan:
        print("   %-42s %.1f초" % (n, s))

    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", "%dx%d" % (WIDTH, HEIGHT), "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    fade_n = int(FADE * FPS)
    for i, (frame, (_name, seconds)) in enumerate(zip(frames, plan)):
        for _ in range(int(seconds * FPS)):
            proc.stdin.write(frame.tobytes())
        if i + 1 < len(frames):
            nxt = frames[i + 1]
            for k in range(fade_n):
                t = (k + 1) / fade_n
                blend = (frame * (1 - t) + nxt * t).astype(np.uint8)
                proc.stdin.write(blend.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg 가 실패했다")

    size = os.path.getsize(OUT) / 1048576
    print("\n만듦: %s  (%.1f MB)" % (OUT, size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

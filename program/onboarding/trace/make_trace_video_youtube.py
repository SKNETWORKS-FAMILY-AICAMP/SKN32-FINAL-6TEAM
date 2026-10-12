# -*- coding: utf-8 -*-
"""A-COP 취소 및 환불 케이스 추적 영상을 만든다.

저장소 루트에서 다음 명령 하나를 실행한다.

    python program/onboarding/trace/make_trace_video_youtube.py

기존 draw.py, steps.py, finale.py, make_trace_images.py와 images 폴더는
수정하지 않는다. 영상용 스틸은 이 스크립트가 trace 폴더 아래의 임시 폴더에
다시 그린 뒤 자동으로 정리한다.
"""

import argparse
import hashlib
import importlib
import json
import math
import os
from fractions import Fraction
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import wave

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
IMAGE_DIR = HERE / "images"
VIDEO_OUT = HERE / "취소환불_케이스_추적_유튜브.mp4"
SRT_OUT = HERE / "취소환불_케이스_추적_자막.srt"
NARRATION_OUT = HERE / "취소환불_케이스_추적_내레이션.txt"
CHAPTERS_OUT = HERE / "취소환불_케이스_추적_챕터.txt"
THUMB_OUT = HERE / "취소환불_케이스_추적_썸네일.png"
REPORT_OUT = HERE / "S-TRACE-VIDEO_리포트.md"

WIDTH = 1920
HEIGHT = 1080
FPS = 30
SAMPLE_RATE = 48000
READING_CHARS_PER_SECOND = 7.2

NAVY = (26, 20, 12)
CYAN = (232, 192, 70)
WHITE = (248, 248, 246)

STEP_COLORS = [
    (47, 68, 184),
    (47, 68, 184),
    (216, 91, 47),
    (77, 122, 13),
    (216, 91, 47),
    (216, 91, 47),
    (160, 63, 107),
    (77, 122, 13),
    (77, 122, 13),
    (216, 91, 47),
    (47, 68, 184),
    (136, 116, 92),
]

FONT_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
FONT_REGULAR_PATH = FONT_DIR / "malgun.ttf"
FONT_BOLD_PATH = FONT_DIR / "malgunbd.ttf"

CAPTION_CACHE = {}
BACKGROUND_CACHE = {}
INTRO_TITLE = None
INTRO_QUOTE = None
OUTRO_TITLE = None
OUTRO_CARDS = []


class Scene:
    def __init__(
        self,
        key,
        title,
        still,
        caption_texts,
        kind="board",
        step=0,
        minimum_duration=10.0,
        fixed_duration=None,
    ):
        self.key = key
        self.title = title
        self.still = still
        self.caption_texts = list(caption_texts)
        self.kind = kind
        self.step = step
        self.minimum_duration = float(minimum_duration)
        self.fixed_duration = fixed_duration
        self.duration = 0.0
        self.cues = []
        self.start = 0.0


SCENES = [
    Scene(
        "intro",
        "도입",
        "",
        [
            "취소 및 환불 문의 한 건이 A-COP 안으로 들어온다.",
            "고객의 한 문장은 내부 전달 문서를 바꾸며 이동한다.",
            "권한 확인부터 답변과 기록까지 열두 단계를 따라간다.",
        ],
        kind="intro",
        minimum_duration=10.0,
        fixed_duration=10.0,
    ),
    Scene(
        "map",
        "전체 경로",
        "00_전체지도.png",
        [
            "이 영상은 열두 단계를 전부 통과한 한 건의 경로를 보여 준다.",
            "가로는 시간이고, 다섯 줄은 각 단계를 맡는 런타임과 기록 영역이다.",
        ],
        minimum_duration=10.0,
    ),
    Scene(
        "structure",
        "구조 좌표",
        "01_구조좌표.png",
        [
            "컴포넌트, 모듈, Agent Team 인스턴스, Port는 서로 다른 구조다.",
            "채운 동그라미만 이 건이 실제로 지난다. 뺄 수 있는 것과 없는 것도 다르다.",
        ],
        minimum_duration=12.0,
    ),
    Scene(
        "step01",
        "1. 신원 확인",
        "01_문_앞에서_신원_확인.png",
        [
            "먼저 API 키와 case:write 권한을 확인한다. 통과한 요청에만 Principal을 만든다.",
            "여기서 붙은 tenant_id는 이후 모든 조회 조건에 따라간다. 아직 Case 상태는 없다.",
        ],
        kind="step",
        step=1,
        minimum_duration=12.0,
    ),
    Scene(
        "step02",
        "2. 중복 확인",
        "02_같은_요청이_아까_왔었나.png",
        [
            "요청 ID, 고객, 메시지, 작업 종류를 재료로 멱등성 키를 만든다.",
            "같은 요청이 열 번 와도 실제 처리는 한 번이다. 이 건은 처음이라 계속 간다.",
        ],
        kind="step",
        step=2,
        minimum_duration=12.0,
    ),
    Scene(
        "step03",
        "3. Case 생성",
        "03_Case_를_만들고_첫_이벤트를_남긴다.png",
        [
            "Case 한 행과 created 이벤트를 한 트랜잭션에서 만든다.",
            "이때 classifying v1 상태가 처음 생긴다. 1번과 2번에는 Case 상태가 없었다.",
        ],
        kind="step",
        step=3,
        minimum_duration=12.0,
    ),
    Scene(
        "step04",
        "4. 문의 분류",
        "04_의도·이슈·감성을_한_번에_분류.png",
        [
            "취소라고 썼지만 환불을 원하는 문의다. 그래서 intent는 return으로 분류된다.",
            "issue_code, sentiment, severity도 함께 정해진 목록 안에서 뽑는다.",
        ],
        kind="step",
        step=4,
        minimum_duration=12.0,
    ),
    Scene(
        "step05",
        "5. Team 라우팅",
        "05_어느_팀_일인지_찾는다.png",
        [
            "Team Registry가 intent return을 받는 활성 팀을 찾는다.",
            "정확히 하나인 return_refund가 선택된다. 둘이거나 없으면 사람에게 넘긴다.",
        ],
        kind="step",
        step=5,
        minimum_duration=12.0,
    ),
    Scene(
        "step06",
        "6. 기능 선택",
        "06_그_팀의_무슨_기능을_쓸지_고른다.png",
        [
            "intent와 같거나 intent로 시작하는 첫 capability를 고른다.",
            "목록의 첫 항목인 return.check_eligibility에서 멈춘다. 순서가 동작을 정한다.",
        ],
        kind="step",
        step=6,
        minimum_duration=12.0,
    ),
    Scene(
        "step07",
        "7. 근거 조합",
        "07_근거를_모아_예산_안으로_자른다.png",
        [
            "Case 상태, 정책 문서, 과거 Case, 도구로 읽은 사실을 ContextPack으로 모은다.",
            "12,000 토큰을 넘으면 정해진 순서로 줄인다. 빠진 근거는 omissions에 남긴다.",
        ],
        kind="step",
        step=7,
        minimum_duration=12.0,
    ),
    Scene(
        "step08",
        "8. Team 판단",
        "08_Team_이_판단한다.png",
        [
            "return_refund Team이 주문, 반품 이력, 정책을 읽고 다섯 검사를 수행한다.",
            "Team은 환불을 실행하지 않는다. 판단과 제안만 돌려주고 실행은 승인 경로에서 한다.",
        ],
        kind="step",
        step=8,
        minimum_duration=12.0,
    ),
    Scene(
        "step09",
        "9. 답변 검토",
        "09_답변_문장을_만들고_톤을_검토한다.png",
        [
            "답변 초안과 사실 대조, 톤 검토를 맡는 9번 단계가 있다.",
            "하지만 response_review.enabled는 false다. 지금은 Team의 고정 문구가 그대로 나간다.",
        ],
        kind="step",
        step=9,
        minimum_duration=12.0,
    ),
    Scene(
        "step10",
        "10. 상태 반영",
        "10_결과를_상태로_반영한다.png",
        [
            "TeamResult의 next_action이 respond라서 completed 이벤트를 남긴다.",
            "Case는 resolved v4가 되고, 답변과 근거가 같은 트랜잭션에서 저장된다.",
        ],
        kind="step",
        step=10,
        minimum_duration=12.0,
    ),
    Scene(
        "step11",
        "11. 고객 응답",
        "11_고객이_답을_받는다.png",
        [
            "고객이 Case를 조회하면 본인 Case인지 다시 확인한다.",
            "상태, 답변, 근거를 함께 돌려준다. 판단 이유를 나중에 되짚을 수 있다.",
        ],
        kind="step",
        step=11,
        minimum_duration=12.0,
    ),
    Scene(
        "step12",
        "12. 기록",
        "12_기록이_남는다.png",
        [
            "이 한 건은 다섯 표에 흔적을 남긴다. Case 상태와 실행, 프롬프트 기록이 이어진다.",
            "case_events는 고치지 않고 추가만 한다. 이벤트를 재생하면 처리 경로를 복원할 수 있다.",
        ],
        kind="step",
        step=12,
        minimum_duration=12.0,
    ),
    Scene(
        "lifecycle",
        "상태 생명주기",
        "13_상태생명주기.png",
        [
            "단계 열둘과 상태 열둘은 다른 축이다. 같은 번호로 대응하지 않는다.",
            "1번 신원 확인과 2번 중복 확인은 Case 생성 전이라 상태가 없다.",
            "이 건은 classifying, routing, running을 지나 resolved로 끝난 통과 경로다.",
        ],
        minimum_duration=14.0,
    ),
    Scene(
        "contracts",
        "전달 계약",
        "14_계약문서.png",
        [
            "한 문의는 HTTP 요청, Principal, ContextPack의 모습으로 바뀐다.",
            "Team에는 TeamTask가 들어가고 판단은 TeamResult로 나온다.",
            "정의되지 않은 필드를 거부하는 계약이 Core와 Team의 경계를 지킨다.",
        ],
        minimum_duration=14.0,
    ),
    Scene(
        "branches",
        "아홉 갈래",
        "15_분기.png",
        [
            "앞의 열두 단계는 전부 통과한 길이다. 실제로는 아홉 군데에서 갈린다.",
            "근거 부족, 입력 부족, 기간 만료 같은 경우는 신호를 남기고 멈추거나 넘긴다.",
            "공통 원칙은 하나다. 모르면 비워 두고, 조용히 넘어가지 않는다.",
        ],
        minimum_duration=16.0,
    ),
    Scene(
        "outro",
        "마무리",
        "",
        [
            "한 건의 답은 분류와 판단만으로 끝나지 않는다.",
            "권한, 근거, 상태 전이, 감사 기록이 한 경로로 이어진다.",
            "이것이 A-COP이 취소 및 환불 문의 한 건을 처리한 전체 추적이다.",
        ],
        kind="outro",
        minimum_duration=10.0,
        fixed_duration=10.0,
    ),
]


def text_character_count(text):
    return sum(1 for character in text if not character.isspace())


def cue_natural_duration(text):
    return max(3.6, text_character_count(text) / READING_CHARS_PER_SECOND + 1.0)


def frame_aligned(seconds):
    return round(seconds * FPS) / FPS


def layout_scenes():
    elapsed_frames = 0
    for scene in SCENES:
        natural = [cue_natural_duration(text) for text in scene.caption_texts]
        natural_total = sum(natural)
        if scene.fixed_duration is not None:
            scene.duration = frame_aligned(scene.fixed_duration)
        else:
            scene.duration = frame_aligned(max(scene.minimum_duration, natural_total))

        scale = scene.duration / natural_total
        scene.start = elapsed_frames / FPS
        cue_start_frames = 0
        scene.cues = []
        for index, text in enumerate(scene.caption_texts):
            if index + 1 == len(scene.caption_texts):
                cue_end_frames = int(round(scene.duration * FPS))
            else:
                scaled = natural[index] * scale
                cue_end_frames = cue_start_frames + max(1, int(round(scaled * FPS)))
            scene.cues.append(
                (
                    cue_start_frames / FPS,
                    cue_end_frames / FPS,
                    text,
                )
            )
            cue_start_frames = cue_end_frames

        scene_frames = int(round(scene.duration * FPS))
        if scene.cues:
            start, unused_end, text = scene.cues[-1]
            scene.cues[-1] = (start, scene_frames / FPS, text)
        elapsed_frames += scene_frames

    total = elapsed_frames / FPS
    if not 180.0 <= total <= 360.0:
        raise RuntimeError("계산된 영상 길이가 3분에서 6분 사이가 아니다: %.3f초" % total)
    return total


def safe_text(value):
    if isinstance(value, str):
        right = chr(0x2192)
        left = chr(0x2190)
        both = chr(0x2194)
        double_right = chr(0x21D2)
        long_dash = chr(0x2014)
        short_dash = chr(0x2013)
        replacements = {
            "없음  " + right + " 계속 진행": "없음이면 계속 진행",
            "있음  " + right + " 그때 Case 를 그대로 반환": "있으면 그때 Case 를 그대로 반환",
            "routing_failed " + right + " 사람에게": "routing_failed 이면 사람에게",
            "초안 생성 " + right + " 사실 대조 " + right + " 톤 검토": "초안 생성, 사실 대조, 톤 검토",
            "created " + right + " classified": "created, classified",
            right + " routed " + right + " completed": "routed, completed",
        }
        for old, new in replacements.items():
            value = value.replace(old, new)
        for character in (right, left, both, double_right):
            value = value.replace(character, "=")
        value = value.replace(long_dash, "-")
        value = value.replace(short_dash, "-")
        return value
    if isinstance(value, tuple):
        return tuple(safe_text(item) for item in value)
    if isinstance(value, list):
        return [safe_text(item) for item in value]
    if isinstance(value, dict):
        return {safe_text(key): safe_text(item) for key, item in value.items()}
    return value


def render_clean_stills(target):
    sys.path.insert(0, str(HERE))
    import draw

    draw.OUT = str(target)
    original_step = draw.step

    def clean_step(*args, **kwargs):
        clean_args = safe_text(args)
        clean_kwargs = safe_text(kwargs)
        return original_step(*clean_args, **clean_kwargs)

    draw.step = clean_step

    for module_name in ("steps", "finale", "make_trace_images"):
        sys.modules.pop(module_name, None)

    steps = importlib.import_module("steps")
    finale = importlib.import_module("finale")
    image_entry = importlib.import_module("make_trace_images")

    image_entry.sheet_map()
    image_entry.sheet_structure()
    steps.build_steps()
    finale.sheet_lifecycle()
    finale.sheet_contracts()
    finale.sheet_branches()

    expected = {scene.still for scene in SCENES if scene.still}
    missing = sorted(name for name in expected if not (target / name).exists())
    if missing:
        raise RuntimeError("영상용 스틸 생성 실패: " + ", ".join(missing))


def image_hashes():
    results = {}
    for path in sorted(IMAGE_DIR.glob("*.png")):
        results[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return results


def find_program(name):
    executable = shutil.which(name)
    if executable:
        return executable
    raise RuntimeError(name + " 실행 파일을 PATH에서 찾을 수 없다")


def font(size, bold=False):
    path = FONT_BOLD_PATH if bold else FONT_REGULAR_PATH
    if not path.exists():
        raise RuntimeError("Malgun Gothic 글꼴 파일을 찾을 수 없다: " + str(path))
    return ImageFont.truetype(str(path), size=size)


def fit_board(path):
    # cv2.imread 는 Windows 에서 한글 경로를 못 읽는다(ANSI API 를 쓴다).
    # 그림 이름이 전부 한글이라 여기서 전부 실패했다. 바이트로 읽어 디코딩한다.
    buffer = np.frombuffer(Path(path).read_bytes(), dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("이미지를 읽을 수 없다: " + str(path))
    raw_height, raw_width = image.shape[:2]
    scale = min(WIDTH / raw_width, HEIGHT / raw_height)
    new_width = int(round(raw_width * scale))
    new_height = int(round(raw_height * scale))
    resized = cv2.resize(
        image,
        (new_width, new_height),
        interpolation=cv2.INTER_AREA,
    )
    canvas = np.full((HEIGHT, WIDTH, 3), 255, dtype=np.uint8)
    x_offset = (WIDTH - new_width) // 2
    y_offset = (HEIGHT - new_height) // 2
    canvas[
        y_offset:y_offset + new_height,
        x_offset:x_offset + new_width,
    ] = resized
    geometry = (x_offset, y_offset, new_width, new_height)
    return canvas, geometry


def gradient_background(width, height):
    key = (width, height)
    if key in BACKGROUND_CACHE:
        return BACKGROUND_CACHE[key].copy()

    position = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None, None]
    top = np.array([34, 25, 13], dtype=np.float32)[None, None, :]
    bottom = np.array([17, 11, 7], dtype=np.float32)[None, None, :]
    row = top * (1.0 - position) + bottom * position
    base = np.repeat(row, width, axis=1).astype(np.uint8)

    for x in range(0, width, 80):
        cv2.line(base, (x, 0), (x, height), (42, 38, 32), 1)
    for y in range(0, height, 80):
        cv2.line(base, (0, y), (width, y), (42, 38, 32), 1)

    BACKGROUND_CACHE[key] = base
    return base.copy()


def text_layer(size, items):
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for item in items:
        text, position, font_size, bold, color, anchor = item
        draw.text(
            position,
            text,
            font=font(font_size, bold),
            fill=color,
            anchor=anchor,
        )
    return np.asarray(image)


def prepare_text_layers():
    global INTRO_TITLE
    global INTRO_QUOTE
    global OUTRO_TITLE
    global OUTRO_CARDS

    INTRO_TITLE = text_layer(
        (WIDTH, HEIGHT),
        [
            (
                "A-COP CASE TRACE",
                (WIDTH // 2, 188),
                28,
                True,
                (104, 211, 239, 255),
                "mm",
            ),
            (
                "취소 및 환불 문의 한 건",
                (WIDTH // 2, 282),
                68,
                True,
                (248, 249, 251, 255),
                "mm",
            ),
            (
                "권한 확인부터 답변과 기록까지",
                (WIDTH // 2, 356),
                34,
                False,
                (183, 193, 209, 255),
                "mm",
            ),
        ],
    )

    INTRO_QUOTE = text_layer(
        (WIDTH, HEIGHT),
        [
            (
                "고객",
                (450, 522),
                22,
                True,
                (98, 205, 235, 255),
                "lm",
            ),
            (
                "어제 주문한 거 취소하고 환불받고 싶어요",
                (WIDTH // 2, 522),
                40,
                True,
                (248, 249, 251, 255),
                "mm",
            ),
        ],
    )

    OUTRO_TITLE = text_layer(
        (WIDTH, HEIGHT),
        [
            (
                "A-COP CASE TRACE",
                (WIDTH // 2, 170),
                27,
                True,
                (104, 211, 239, 255),
                "mm",
            ),
            (
                "답변과 근거와 기록이 남았다",
                (WIDTH // 2, 280),
                64,
                True,
                (248, 249, 251, 255),
                "mm",
            ),
            (
                "열두 단계를 모두 통과한 취소 및 환불 문의 한 건",
                (WIDTH // 2, 358),
                32,
                False,
                (183, 193, 209, 255),
                "mm",
            ),
        ],
    )

    card_specs = [
        ("intent = return", 405),
        ("response_review.enabled = false", 960),
        ("status = resolved v4", 1515),
    ]
    OUTRO_CARDS = []
    for text, center_x in card_specs:
        layer = text_layer(
            (500, 82),
            [
                (
                    text,
                    (250, 41),
                    24,
                    True,
                    (250, 250, 250, 255),
                    "mm",
                )
            ],
        )
        OUTRO_CARDS.append((center_x, layer))


def alpha_blend(frame, rgba, x=0, y=0, strength=1.0):
    height, width = rgba.shape[:2]
    roi = frame[y:y + height, x:x + width]
    rgb = rgba[:, :, :3][:, :, ::-1].astype(np.float32)
    alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
    alpha *= max(0.0, min(1.0, strength))
    roi[:] = (
        roi.astype(np.float32) * (1.0 - alpha) + rgb * alpha
    ).astype(np.uint8)


def wrap_words_for_width(draw, text, text_font, max_width):
    paragraphs = text.split("\n")
    lines = []
    for paragraph in paragraphs:
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else current + " " + word
            box = draw.textbbox((0, 0), candidate, font=text_font)
            if box[2] - box[0] <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = word
            else:
                fragment = ""
                for character in word:
                    candidate_fragment = fragment + character
                    fragment_box = draw.textbbox(
                        (0, 0),
                        candidate_fragment,
                        font=text_font,
                    )
                    if fragment and fragment_box[2] - fragment_box[0] > max_width:
                        lines.append(fragment)
                        fragment = character
                    else:
                        fragment = candidate_fragment
                current = fragment
        if current:
            lines.append(current)
    return lines


def caption_art(text):
    if text in CAPTION_CACHE:
        return CAPTION_CACHE[text]

    image = Image.new("RGBA", (WIDTH, 178), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (150, 12, WIDTH - 150, 164),
        radius=24,
        fill=(8, 14, 28, 225),
        outline=(83, 112, 156, 140),
        width=2,
    )
    draw.text(
        (188, 31),
        "A-COP CASE TRACE",
        font=font(19, True),
        fill=(108, 207, 236, 255),
    )

    text_font = font(36, True)
    lines = wrap_words_for_width(draw, text, text_font, 1480)
    if len(lines) > 2:
        text_font = font(32, True)
        lines = wrap_words_for_width(draw, text, text_font, 1500)

    line_height = 45
    total_height = line_height * len(lines)
    top = 103 - total_height / 2
    for index, line in enumerate(lines):
        box = draw.textbbox((0, 0), line, font=text_font)
        width = box[2] - box[0]
        draw.text(
            ((WIDTH - width) / 2, top + index * line_height),
            line,
            font=text_font,
            fill=(247, 249, 252, 255),
        )

    result = np.asarray(image)
    CAPTION_CACHE[text] = result
    return result


def caption_at(scene, local_time):
    for start, end, text in scene.cues:
        if start <= local_time < end:
            edge = min(local_time - start, end - local_time)
            strength = min(1.0, max(0.0, edge / 0.22))
            return text, strength
    if scene.cues and math.isclose(local_time, scene.duration):
        return scene.cues[-1][2], 0.0
    return "", 0.0


def add_caption(frame, scene, local_time):
    text, strength = caption_at(scene, local_time)
    if text:
        alpha_blend(
            frame,
            caption_art(text),
            0,
            HEIGHT - 178,
            strength,
        )


def smooth(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def interpolate_anchors(local_time, anchors):
    if local_time <= anchors[0][0]:
        return anchors[0][1:]
    for first, second in zip(anchors, anchors[1:]):
        if first[0] <= local_time <= second[0]:
            span = second[0] - first[0]
            amount = smooth((local_time - first[0]) / span)
            return tuple(
                left + (right - left) * amount
                for left, right in zip(first[1:], second[1:])
            )
    return anchors[-1][1:]


def render_view(board, center_x, center_y, zoom):
    if (
        abs(zoom - 1.0) < 0.002
        and abs(center_x - 0.5) < 0.002
        and abs(center_y - 0.5) < 0.002
    ):
        return board.copy()

    crop_width = max(2, int(round(WIDTH / zoom)))
    crop_height = max(2, int(round(HEIGHT / zoom)))
    center_pixel_x = int(round(center_x * WIDTH))
    center_pixel_y = int(round(center_y * HEIGHT))
    left = max(0, min(WIDTH - crop_width, center_pixel_x - crop_width // 2))
    top = max(0, min(HEIGHT - crop_height, center_pixel_y - crop_height // 2))
    crop = board[top:top + crop_height, left:left + crop_width]
    return cv2.resize(
        crop,
        (WIDTH, HEIGHT),
        interpolation=cv2.INTER_LINEAR,
    )


def world_to_view(point, center_x, center_y, zoom):
    crop_width = WIDTH / zoom
    crop_height = HEIGHT / zoom
    left = min(
        max(center_x * WIDTH - crop_width / 2.0, 0.0),
        WIDTH - crop_width,
    )
    top = min(
        max(center_y * HEIGHT - crop_height / 2.0, 0.0),
        HEIGHT - crop_height,
    )
    return (
        int((point[0] - left) * zoom),
        int((point[1] - top) * zoom),
    )


def dim_slice(frame, x1, y1, x2, y2, amount=0.52):
    x1 = max(0, min(WIDTH, int(x1)))
    x2 = max(0, min(WIDTH, int(x2)))
    y1 = max(0, min(HEIGHT, int(y1)))
    y2 = max(0, min(HEIGHT, int(y2)))
    if x2 <= x1 or y2 <= y1:
        return
    roi = frame[y1:y2, x1:x2]
    tint = np.empty_like(roi)
    tint[:] = NAVY
    cv2.addWeighted(
        roi,
        1.0 - amount,
        tint,
        amount,
        0,
        dst=roi,
    )


def add_progress(frame, step, local_time):
    cv2.rectangle(frame, (0, 0), (WIDTH, 126), (250, 251, 253), -1)
    left = 64
    gap = 10
    slot_width = (WIDTH - left * 2 - gap * 11) // 12
    y1 = 38
    y2 = 78
    fill = smooth(local_time / 0.9)

    for index in range(12):
        x1 = left + index * (slot_width + gap)
        x2 = x1 + slot_width
        cv2.rectangle(frame, (x1, y1), (x2, y2), (232, 235, 241), -1)

        if index + 1 < step:
            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                STEP_COLORS[index],
                -1,
            )
        elif index + 1 == step:
            cv2.rectangle(
                frame,
                (x1, y1),
                (x1 + int(slot_width * fill), y2),
                STEP_COLORS[index],
                -1,
            )

        label = str(index + 1)
        size = cv2.getTextSize(
            label,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            1,
        )[0]
        text_color = (
            (255, 255, 255)
            if index + 1 <= step
            else (151, 158, 171)
        )
        cv2.putText(
            frame,
            label,
            (x1 + (slot_width - size[0]) // 2, y1 + 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            text_color,
            1,
            cv2.LINE_AA,
        )


def prepare_step_versions(board, geometry):
    board_without_old_progress = board.copy()
    cv2.rectangle(
        board_without_old_progress,
        (0, 0),
        (WIDTH, 126),
        (255, 255, 255),
        -1,
    )

    hidden = board_without_old_progress.copy()
    x_offset, y_offset, raw_width, raw_height = geometry
    x1 = int(x_offset + raw_width * 0.582)
    x2 = int(x_offset + raw_width * 0.852)
    y1 = int(y_offset + raw_height * 0.232)
    y2 = int(y_offset + raw_height * 0.515)

    sample = hidden[y1:y2, x1:x2]
    if sample.size:
        median = np.median(sample.reshape(-1, 3), axis=0)
        fill_color = tuple(int(value) for value in median)
    else:
        fill_color = (254, 252, 251)
    cv2.rectangle(hidden, (x1, y1), (x2, y2), fill_color, -1)

    # ★줄 위치를 상수로 찍으면 글자 중간이 잘린다. 실제로 그랬다.
    #   그림은 bbox_inches="tight" 로 저장돼 여백이 장마다 달라서 비율이 안 맞는다.
    #   그래서 글자가 실제로 있는 행을 찾아 그 덩어리를 한 줄로 삼는다.
    region = board_without_old_progress[y1:y2, x1:x2]
    if region.size:
        darkness = 255 - region.min(axis=2)            # 글자가 있으면 값이 크다
        row_has_text = darkness.max(axis=1) > 60
    else:
        row_has_text = np.zeros(0, dtype=bool)

    runs = []
    start = None
    for index, filled in enumerate(row_has_text):
        if filled and start is None:
            start = index
        elif not filled and start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, len(row_has_text)))

    # 너무 얇은 덩어리는 글자가 아니라 상자 테두리다. 빼지 않으면 빈 줄이 하나 공개된다.
    runs = [(a, b) for a, b in runs if b - a >= 6]
    margin = max(3, int(raw_height * 0.004))
    bands = [
        (x1, max(y1, y1 + a - margin), x2, min(y2, y1 + b + margin))
        for a, b in runs
    ]
    if not bands:      # 못 찾으면 통째로 한 번에 공개한다. 아무것도 안 나오는 것보다 낫다
        bands = [(x1, y1, x2, y2)]
    return board_without_old_progress, hidden, bands


def reveal_lines(board, hidden, bands, count):
    result = hidden.copy()
    for x1, y1, x2, y2 in bands[:count]:
        result[y1:y2, x1:x2] = board[y1:y2, x1:x2]
    return result


def step_anchors(duration):
    return [
        (0.00 * duration, 0.50, 0.50, 1.00),
        (0.15 * duration, 0.50, 0.47, 1.02),
        (0.27 * duration, 0.39, 0.45, 1.16),
        (0.41 * duration, 0.55, 0.45, 1.06),
        (0.68 * duration, 0.72, 0.44, 1.18),
        (0.88 * duration, 0.72, 0.50, 1.12),
        (1.00 * duration, 0.53, 0.76, 1.08),
    ]


def board_anchors(scene):
    duration = scene.duration
    if scene.key == "map":
        return [
            (0.00 * duration, 0.50, 0.50, 1.00),
            (0.30 * duration, 0.50, 0.46, 1.06),
            (0.70 * duration, 0.64, 0.46, 1.12),
            (1.00 * duration, 0.50, 0.50, 1.00),
        ]
    if scene.key == "structure":
        return [
            (0.00 * duration, 0.50, 0.50, 1.00),
            (0.25 * duration, 0.29, 0.46, 1.18),
            (0.58 * duration, 0.71, 0.46, 1.18),
            (1.00 * duration, 0.50, 0.50, 1.00),
        ]
    if scene.key == "lifecycle":
        return [
            (0.00 * duration, 0.50, 0.50, 1.00),
            (0.22 * duration, 0.52, 0.36, 1.14),
            (0.57 * duration, 0.45, 0.53, 1.15),
            (0.85 * duration, 0.35, 0.70, 1.16),
            (1.00 * duration, 0.50, 0.50, 1.00),
        ]
    if scene.key == "contracts":
        return [
            (0.00 * duration, 0.50, 0.50, 1.00),
            (0.22 * duration, 0.25, 0.45, 1.16),
            (0.52 * duration, 0.61, 0.45, 1.16),
            (0.80 * duration, 0.56, 0.72, 1.12),
            (1.00 * duration, 0.50, 0.50, 1.00),
        ]
    if scene.key == "branches":
        return [
            (0.00 * duration, 0.50, 0.50, 1.00),
            (0.20 * duration, 0.50, 0.35, 1.10),
            (0.50 * duration, 0.50, 0.52, 1.12),
            (0.82 * duration, 0.50, 0.67, 1.12),
            (1.00 * duration, 0.50, 0.50, 1.00),
        ]
    return [
        (0.0, 0.50, 0.50, 1.00),
        (duration, 0.50, 0.50, 1.00),
    ]


def add_flow(frame, scene, local_time, view):
    start_time = scene.duration * 0.24
    end_time = scene.duration * 0.76
    if not start_time <= local_time <= end_time:
        return

    center_x, center_y, zoom = view
    source = world_to_view(
        (WIDTH * 0.44, HEIGHT * 0.45),
        center_x,
        center_y,
        zoom,
    )
    target = world_to_view(
        (WIDTH * 0.68, HEIGHT * 0.45),
        center_x,
        center_y,
        zoom,
    )
    cv2.line(frame, source, target, (205, 220, 224), 3, cv2.LINE_AA)

    speed = 2.3 / max(0.1, end_time - start_time)
    for index in range(6):
        phase = ((local_time - start_time) * speed + index / 6.0) % 1.0
        eased = smooth(phase)
        x = int(source[0] + (target[0] - source[0]) * eased)
        arc = math.sin(math.pi * phase) * 24
        y = int(source[1] + (target[1] - source[1]) * eased - arc)
        cv2.circle(frame, (x, y), 13, (240, 223, 147), -1, cv2.LINE_AA)
        cv2.circle(frame, (x, y), 7, CYAN, -1, cv2.LINE_AA)


def render_step(scene, board, geometry, prepared, local_time):
    clean_board, hidden, bands = prepared
    reveal_start = scene.duration * 0.29
    reveal_end = scene.duration * 0.80
    band_span = max(0.01, (reveal_end - reveal_start) / len(bands))
    count = int((local_time - reveal_start) / band_span) + 1
    count = max(0, min(len(bands), count))

    staged = reveal_lines(clean_board, hidden, bands, count)
    anchors = step_anchors(scene.duration)
    view = interpolate_anchors(local_time, anchors)
    frame = render_view(staged, *view)

    if 0.21 * scene.duration <= local_time < 0.40 * scene.duration:
        dim_slice(frame, 0, 126, 270, HEIGHT - 178, 0.45)
        dim_slice(frame, 1420, 126, WIDTH, HEIGHT - 178, 0.45)
    elif 0.63 * scene.duration <= local_time < 0.88 * scene.duration:
        dim_slice(frame, 0, 126, 790, HEIGHT - 178, 0.56)
    elif 0.88 * scene.duration <= local_time:
        dim_slice(frame, 0, 126, WIDTH, 610, 0.34)

    add_flow(frame, scene, local_time, view)
    add_progress(frame, scene.step, local_time)
    add_caption(frame, scene, local_time)
    return frame


def add_board_motion(frame, scene, local_time, view):
    if scene.key in ("map", "contracts"):
        world_y = HEIGHT * (0.48 if scene.key == "map" else 0.43)
        start = world_to_view(
            (WIDTH * 0.16, world_y),
            *view,
        )
        end = world_to_view(
            (WIDTH * 0.84, world_y),
            *view,
        )
        phase = (local_time * 0.22) % 1.0
        x = int(start[0] + (end[0] - start[0]) * smooth(phase))
        cv2.circle(
            frame,
            (x, start[1]),
            12,
            (235, 214, 126),
            -1,
            cv2.LINE_AA,
        )
        cv2.circle(
            frame,
            (x, start[1]),
            6,
            CYAN,
            -1,
            cv2.LINE_AA,
        )
    elif scene.key == "branches":
        row = min(8, int(local_time / scene.duration * 9))
        world_y = HEIGHT * (0.27 + row * 0.050)
        first = world_to_view((WIDTH * 0.03, world_y), *view)
        second = world_to_view((WIDTH * 0.97, world_y + 50), *view)
        overlay = frame.copy()
        cv2.rectangle(overlay, first, second, (90, 120, 40), -1)
        cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, dst=frame)


def render_board(scene, board, local_time):
    view = interpolate_anchors(local_time, board_anchors(scene))
    frame = render_view(board, *view)
    if 1.0 < local_time < scene.duration - 1.0:
        dim_slice(frame, 0, 0, WIDTH, 106, 0.16)
    add_board_motion(frame, scene, local_time, view)
    add_caption(frame, scene, local_time)
    return frame


def draw_path(frame, local_time, total_duration, completed=False):
    points = [
        (165 + index * 144, 690 + int(math.sin(index * 0.9) * 38))
        for index in range(12)
    ]
    for first, second in zip(points, points[1:]):
        cv2.line(frame, first, second, (78, 91, 111), 3, cv2.LINE_AA)

    if completed:
        fill_to = 12
    else:
        path_progress = smooth(
            max(
                0.0,
                (local_time - total_duration * 0.53)
                / max(0.1, total_duration * 0.42),
            )
        )
        fill_to = min(12, int(path_progress * 12) + 1)

    for index, point in enumerate(points):
        active = index < fill_to
        color = STEP_COLORS[index] if active else (73, 70, 66)
        cv2.circle(frame, point, 27, color, -1, cv2.LINE_AA)
        cv2.circle(frame, point, 27, (194, 189, 181), 2, cv2.LINE_AA)
        label = str(index + 1)
        size = cv2.getTextSize(
            label,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            1,
        )[0]
        cv2.putText(
            frame,
            label,
            (point[0] - size[0] // 2, point[1] + size[1] // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            WHITE,
            1,
            cv2.LINE_AA,
        )

    if completed:
        phase = (local_time * 0.28) % 1.0
    else:
        phase = max(
            0.0,
            min(
                1.0,
                (local_time - total_duration * 0.53)
                / max(0.1, total_duration * 0.42),
            ),
        )
    position = phase * 11
    index = min(10, int(position))
    amount = position - index
    x = int(
        points[index][0]
        + (points[index + 1][0] - points[index][0]) * amount
    )
    y = int(
        points[index][1]
        + (points[index + 1][1] - points[index][1]) * amount
    )
    cv2.circle(frame, (x, y), 17, (241, 222, 141), -1, cv2.LINE_AA)
    cv2.circle(frame, (x, y), 9, CYAN, -1, cv2.LINE_AA)


def render_intro(scene, local_time):
    frame = gradient_background(WIDTH, HEIGHT)
    title_strength = smooth((local_time - 0.3) / 1.8)
    quote_strength = smooth((local_time - 2.6) / 1.2)
    quote_strength *= 1.0 - smooth((local_time - 6.2) / 0.8) * 0.45

    alpha_blend(frame, INTRO_TITLE, strength=title_strength)
    if quote_strength > 0.0:
        overlay = frame.copy()
        cv2.rectangle(
            overlay,
            (365, 455),
            (1555, 592),
            (40, 44, 54),
            -1,
        )
        cv2.addWeighted(
            overlay,
            0.72 * quote_strength,
            frame,
            1.0 - 0.72 * quote_strength,
            0,
            dst=frame,
        )
        alpha_blend(frame, INTRO_QUOTE, strength=quote_strength)

    draw_path(frame, local_time, scene.duration)
    add_caption(frame, scene, local_time)
    return frame


def render_outro(scene, local_time):
    frame = gradient_background(WIDTH, HEIGHT)
    alpha_blend(
        frame,
        OUTRO_TITLE,
        strength=smooth((local_time - 0.3) / 1.5),
    )
    draw_path(frame, local_time, scene.duration, completed=True)

    card_colors = [
        (66, 110, 27),
        (82, 78, 71),
        (139, 76, 29),
    ]
    for index, item in enumerate(OUTRO_CARDS):
        center_x, layer = item
        left = center_x - 250
        top = 440
        cv2.rectangle(
            frame,
            (left, top),
            (left + 500, top + 82),
            card_colors[index],
            -1,
        )
        alpha_blend(
            frame,
            layer,
            left,
            top,
            smooth((local_time - 1.8 - index * 0.35) / 0.8),
        )

    add_caption(frame, scene, local_time)
    return frame


def audio_chunk(start_sample, sample_count, scene_starts):
    samples = np.arange(
        start_sample,
        start_sample + sample_count,
        dtype=np.float64,
    )
    time_values = samples / SAMPLE_RATE
    chord_sets = [
        (130.81, 196.00, 261.63, 329.63),
        (110.00, 164.81, 220.00, 261.63),
        (87.31, 130.81, 174.61, 220.00),
        (98.00, 146.83, 196.00, 246.94),
    ]
    result = np.zeros(sample_count, dtype=np.float64)
    absolute_seconds = int(start_sample // SAMPLE_RATE)
    chord = chord_sets[(absolute_seconds // 8) % len(chord_sets)]
    chord_phase = np.mod(time_values, 8.0)
    envelope = np.minimum(1.0, chord_phase / 1.1)
    envelope *= np.minimum(1.0, (8.0 - chord_phase) / 1.4)

    for index, frequency in enumerate(chord):
        result += np.sin(
            2.0 * math.pi * frequency * time_values + index * 0.37
        ) * (0.22 - index * 0.025)
        result += np.sin(
            2.0 * math.pi * frequency * 0.5 * time_values + index * 0.21
        ) * 0.07

    result *= envelope * 0.10

    for start in scene_starts:
        delta = time_values - start
        active = (delta >= 0.0) & (delta < 1.2)
        if np.any(active):
            bell = np.sin(2.0 * math.pi * 523.25 * delta[active])
            bell += 0.45 * np.sin(
                2.0 * math.pi * 783.99 * delta[active]
            )
            result[active] += (
                bell * np.exp(-delta[active] * 4.0) * 0.045
            )

    return np.clip(result, -0.22, 0.22).astype(np.float32)


def write_audio_wave(path, total_duration):
    total_samples = int(round(total_duration * SAMPLE_RATE))
    scene_starts = [scene.start for scene in SCENES]
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        start = 0
        while start < total_samples:
            count = min(SAMPLE_RATE, total_samples - start)
            values = audio_chunk(start, count, scene_starts)
            pcm = np.round(values * 32767.0).astype("<i2")
            handle.writeframes(pcm.tobytes())
            start += count


def create_thumbnail():
    width = 1280
    height = 720
    base = gradient_background(width, height)
    image = Image.fromarray(base[:, :, ::-1])
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (66, 62, 1214, 658),
        radius=30,
        outline=(65, 116, 154),
        width=3,
    )
    draw.text(
        (96, 98),
        "A-COP CASE TRACE",
        font=font(28, True),
        fill=(100, 210, 239),
    )
    draw.text(
        (96, 160),
        "취소 및 환불 문의",
        font=font(61, True),
        fill=(249, 250, 252),
    )
    draw.text(
        (96, 235),
        "한 건의 내부 추적",
        font=font(61, True),
        fill=(249, 250, 252),
    )

    draw.rounded_rectangle(
        (96, 355, 430, 447),
        radius=18,
        fill=(39, 50, 70),
        outline=(92, 137, 175),
        width=2,
    )
    draw.text(
        (263, 401),
        "고객 문의",
        font=font(30, True),
        fill=(244, 247, 250),
        anchor="mm",
    )

    draw.rounded_rectangle(
        (850, 355, 1184, 447),
        radius=18,
        fill=(31, 112, 76),
        outline=(106, 221, 164),
        width=2,
    )
    draw.text(
        (1017, 401),
        "resolved v4",
        font=font(28, True),
        fill=(244, 247, 250),
        anchor="mm",
    )

    line_y = 401
    draw.line(
        (448, line_y, 832, line_y),
        fill=(82, 132, 164),
        width=5,
    )
    for index in range(6):
        x = 480 + index * 64
        draw.ellipse(
            (x - 10, line_y - 10, x + 10, line_y + 10),
            fill=(84, 200, 230),
        )

    draw.text(
        (96, 535),
        "12단계",
        font=font(40, True),
        fill=(109, 218, 170),
    )
    draw.text(
        (290, 535),
        "데이터 흐름",
        font=font(40, True),
        fill=(237, 220, 139),
    )
    draw.text(
        (594, 535),
        "근거와 기록",
        font=font(40, True),
        fill=(177, 190, 211),
    )

    image.save(THUMB_OUT, format="PNG", optimize=True)


def srt_time(seconds):
    milliseconds = int(round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return "%02d:%02d:%02d,%03d" % (
        hours,
        minutes,
        secs,
        milliseconds,
    )


def clock_time(seconds):
    rounded = int(round(seconds))
    minutes, secs = divmod(rounded, 60)
    return "%02d:%02d" % (minutes, secs)


def plain_wrap(text, limit=38):
    words = text.split(" ")
    lines = []
    current = ""
    for word in words:
        candidate = word if not current else current + " " + word
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


def chapter_rows():
    chapter_keys = [
        ("intro", "도입"),
        ("map", "전체 경로와 구조"),
        ("step01", "진입과 Case 생성"),
        ("step04", "분류와 라우팅"),
        ("step07", "근거와 Team 판단"),
        ("step10", "상태 반영과 기록"),
        ("lifecycle", "상태, 계약, 분기"),
        ("outro", "마무리"),
    ]
    starts = {scene.key: scene.start for scene in SCENES}
    return [
        "%s %s" % (clock_time(starts[key]), title)
        for key, title in chapter_keys
    ]


def write_text_outputs():
    srt_lines = []
    narration_lines = [
        "# A-COP 취소 및 환불 케이스 추적 내레이션 대본",
        "",
        "평서문으로 읽는다. 화면의 하드 자막과 같은 시간 구간을 사용한다.",
        "",
    ]

    cue_number = 1
    for scene in SCENES:
        narration_lines.append(
            "## %s %s" % (clock_time(scene.start), scene.title)
        )
        narration_lines.append("")
        for start, end, text in scene.cues:
            absolute_start = scene.start + start
            absolute_end = scene.start + end
            srt_lines.extend(
                [
                    str(cue_number),
                    "%s --> %s"
                    % (
                        srt_time(absolute_start),
                        srt_time(absolute_end),
                    ),
                    plain_wrap(text),
                    "",
                ]
            )
            narration_lines.append(
                "[%s - %s] %s"
                % (
                    clock_time(absolute_start),
                    clock_time(absolute_end),
                    text,
                )
            )
            cue_number += 1
        narration_lines.append("")

    SRT_OUT.write_text("\n".join(srt_lines), encoding="utf-8")
    NARRATION_OUT.write_text(
        "\n".join(narration_lines),
        encoding="utf-8",
    )
    CHAPTERS_OUT.write_text(
        "\n".join(chapter_rows()) + "\n",
        encoding="utf-8",
    )


def forbidden_text_files(paths):
    codepoints = (
        0x2014,
        0x2013,
        0x2190,
        0x2192,
        0x2194,
        0x21D2,
    )
    found = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for codepoint in codepoints:
            if chr(codepoint) in text:
                found.append((path.name, codepoint))
    return found


def render_video(ffmpeg, clean_dir, audio_path, total_duration):
    boards = {}
    geometries = {}
    prepared_steps = {}

    for scene in SCENES:
        if scene.still:
            board, geometry = fit_board(clean_dir / scene.still)
            boards[scene.key] = board
            geometries[scene.key] = geometry
            if scene.kind == "step":
                prepared_steps[scene.key] = prepare_step_versions(
                    board,
                    geometry,
                )

    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s:v",
        "%dx%d" % (WIDTH, HEIGHT),
        "-r",
        str(FPS),
        "-i",
        "pipe:0",
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-tune",
        "animation",
        "-profile:v",
        "high",
        "-level:v",
        "4.1",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(FPS),
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-ar",
        str(SAMPLE_RATE),
        "-ac",
        "1",
        "-movflags",
        "+faststart",
        "-shortest",
        str(VIDEO_OUT),
    ]

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    print(
        "영상 %.1f초, %dfps 렌더링" % (total_duration, FPS),
        flush=True,
    )

    total_written_frames = 0
    try:
        for scene_index, scene in enumerate(SCENES, start=1):
            scene_frames = int(round(scene.duration * FPS))
            board = boards.get(scene.key)
            geometry = geometries.get(scene.key)
            prepared = prepared_steps.get(scene.key)

            for local_frame in range(scene_frames):
                local_time = local_frame / FPS
                if scene.kind == "intro":
                    frame = render_intro(scene, local_time)
                elif scene.kind == "outro":
                    frame = render_outro(scene, local_time)
                elif scene.kind == "step":
                    frame = render_step(
                        scene,
                        board,
                        geometry,
                        prepared,
                        local_time,
                    )
                else:
                    frame = render_board(scene, board, local_time)

                process.stdin.write(frame.tobytes(order="C"))
                total_written_frames += 1

            elapsed = total_written_frames / FPS
            print(
                "  %02d/%02d %s %s"
                % (
                    scene_index,
                    len(SCENES),
                    clock_time(elapsed),
                    scene.title,
                ),
                flush=True,
            )

        process.stdin.close()
        error_output = process.stderr.read().decode(
            "utf-8",
            errors="replace",
        )
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(
                "ffmpeg 인코딩 실패\n" + error_output.strip()
            )
    except Exception:
        try:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
        except Exception:
            pass
        if process.poll() is None:
            process.kill()
        raise


def probe_video(ffprobe):
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,pix_fmt,sample_rate,channels",
        "-of",
        "json",
        str(VIDEO_OUT),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "ffprobe 실패\n" + completed.stderr.strip()
        )

    data = json.loads(completed.stdout)
    video_streams = [
        stream
        for stream in data.get("streams", [])
        if stream.get("codec_type") == "video"
    ]
    audio_streams = [
        stream
        for stream in data.get("streams", [])
        if stream.get("codec_type") == "audio"
    ]
    if len(video_streams) != 1:
        raise RuntimeError("비디오 스트림이 정확히 하나가 아니다")
    if len(audio_streams) != 1:
        raise RuntimeError("오디오 스트림이 정확히 하나가 아니다")

    video = video_streams[0]
    audio = audio_streams[0]
    format_data = data.get("format", {})
    return {
        "codec_name": video.get("codec_name", ""),
        "width": str(video.get("width", "")),
        "height": str(video.get("height", "")),
        "fps": video.get("r_frame_rate", ""),
        "pix_fmt": video.get("pix_fmt", ""),
        "audio_codec": audio.get("codec_name", ""),
        "sample_rate": str(audio.get("sample_rate", "")),
        "channels": str(audio.get("channels", "")),
        "duration": format_data.get("duration", "0"),
        "size": format_data.get("size", "0"),
    }


def top_level_atoms(path):
    atoms = []
    file_size = path.stat().st_size
    with path.open("rb") as handle:
        offset = 0
        while offset + 8 <= file_size:
            handle.seek(offset)
            header = handle.read(8)
            if len(header) != 8:
                break
            size_32, atom_type = struct.unpack(">I4s", header)
            header_size = 8
            if size_32 == 1:
                extended = handle.read(8)
                if len(extended) != 8:
                    break
                atom_size = struct.unpack(">Q", extended)[0]
                header_size = 16
            elif size_32 == 0:
                atom_size = file_size - offset
            else:
                atom_size = size_32
            if atom_size < header_size:
                break
            atoms.append((atom_type.decode("ascii", errors="replace"), offset))
            offset += atom_size
    return atoms


def faststart_check(path):
    atoms = top_level_atoms(path)
    positions = {name: offset for name, offset in atoms}
    return (
        "moov" in positions
        and "mdat" in positions
        and positions["moov"] < positions["mdat"]
    )


def decode_check(ffmpeg):
    command = [
        ffmpeg,
        "-v",
        "error",
        "-i",
        str(VIDEO_OUT),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0",
        "-f",
        "null",
        os.devnull,
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "완성 영상 디코딩 검사 실패\n" + completed.stderr.strip()
        )
    return True


def program_version(executable):
    completed = subprocess.run(
        [executable, "-version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0 or not completed.stdout:
        return "확인 실패"
    return safe_text(completed.stdout.splitlines()[0])


def verify_probe(probe, total_duration):
    failures = []
    if probe["codec_name"] != "h264":
        failures.append("codec_name=" + probe["codec_name"])
    if probe["width"] != str(WIDTH):
        failures.append("width=" + probe["width"])
    if probe["height"] != str(HEIGHT):
        failures.append("height=" + probe["height"])
    try:
        actual_rate = Fraction(probe["fps"])
    except Exception:
        actual_rate = Fraction(0, 1)
    if actual_rate != Fraction(FPS, 1):
        failures.append("fps=" + probe["fps"])
    if probe["pix_fmt"] != "yuv420p":
        failures.append("pix_fmt=" + probe["pix_fmt"])
    if probe["audio_codec"] != "aac":
        failures.append("audio_codec=" + probe["audio_codec"])
    actual_duration = float(probe["duration"])
    if not 180.0 <= actual_duration <= 360.0:
        failures.append("duration=" + probe["duration"])
    if abs(actual_duration - total_duration) > 1.0:
        failures.append(
            "계획 길이와 실제 길이 차이=%.3f"
            % abs(actual_duration - total_duration)
        )
    if failures:
        raise RuntimeError("기술 규격 검증 실패: " + ", ".join(failures))


def write_report(
    probe,
    hashes_before,
    hashes_after,
    faststart,
    decoded,
    total_duration,
    ffmpeg_version,
    ffprobe_version,
):
    unchanged = hashes_before == hashes_after and len(hashes_before) == 17
    size_mib = int(probe["size"]) / 1048576.0
    report = """# S-TRACE-VIDEO 완료 리포트

## 결과

A-COP에 들어온 취소 및 환불 문의 한 건이 답변과 기록으로 남을 때까지를 %.1f초 영상으로 만들었다.
도입과 마무리는 각각 10초다. 기존 정지 그림 17장은 수정하거나 삭제하지 않았다.

## 만든 파일

- `program/onboarding/trace/%s`
- `program/onboarding/trace/%s`
- `program/onboarding/trace/%s`
- `program/onboarding/trace/%s`
- `program/onboarding/trace/%s`
- `program/onboarding/trace/%s`

## 재생성

```powershell
python program/onboarding/trace/make_trace_video_youtube.py
```

이 명령 하나가 영상용 스틸을 임시 생성하고 영상, 자막, 대본, 챕터, 썸네일, 리포트를 다시 만든다.
중간 산출물을 손으로 만들 필요가 없다.

## 읽기 시간 계산

장면별 체류 시간을 고정 초 목록으로 적지 않았다.
한국어 자막의 공백 제외 글자 수와 초당 %.1f자 기준으로 각 자막 시간을 계산하고, 장면별 최소 시간과 비교해 더 긴 값을 사용했다.
계산 뒤 모든 경계를 30fps 프레임에 맞췄다.

## 필수 항목 확인

- 화면 내부 움직임: 각 단계에서 왼쪽 문서와 오른쪽 문서 사이를 데이터 입자가 이동한다.
- 줄의 순차 등장: 오른쪽 전달 문서의 내용을 여덟 구간으로 나누어 순서대로 공개한다.
- 진행바: 각 단계가 시작될 때 해당 칸이 약 0.9초 동안 채워진다.
- 시선 유도: 입력, 변환, 출력, 결론 순서로 확대 이동하고 설명하지 않는 영역을 어둡게 처리한다.
- 한국어 자막: 영상에 태워 넣었고 같은 시간축의 SRT 파일을 만들었다.
- 도입과 마무리: 각각 10초다.
- 규격: 1920x1080, 30fps, H.264, yuv420p, faststart다.
- 길이: %.1f초로 3분에서 6분 사이에 있다.

## 기술 검증

`ffprobe`로 코덱, 해상도, 프레임률, 픽셀 형식, 길이, 크기를 확인했다.
`ffmpeg`로 영상과 오디오 스트림 전체를 다시 디코딩해 재생 오류도 확인했다.

```text
codec_name=%s
width=%s
height=%s
r_frame_rate=%s
pix_fmt=%s
audio_codec=%s
sample_rate=%s
channels=%s
duration=%s
size=%s bytes, %.1f MiB
faststart=%s
decode_check=%s
```

실행 환경은 다음과 같다.

```text
%s
%s
```

## 내용 정확성

- 단계 12개와 상태 12개를 별도 축으로 설명했다.
- 1번 신원 확인과 2번 중복 확인에는 Case 상태가 없다고 명시했다.
- Team은 실행하지 않고 판단과 제안만 돌려준다고 명시했다.
- 실행은 승인 경로에서 한다고 설명했지만 원문에 없는 구체 실행 결과나 코드 경로는 추가하지 않았다.
- 9번 검토 단계는 `response_review.enabled = false`로 표시했다.
- 취소라는 표현이 들어왔지만 intent는 return이라는 장면을 독립 자막으로 강조했다.
- 본 경로는 전부 통과한 길이며 마지막에 아홉 갈래를 보여 준다.
- 확인되지 않은 숫자, 필드, 코드 경로는 새로 만들지 않았다.

## 음향과 저작권

음성 합성은 쓰지 않았다.
외부 음악과 외부 샘플도 쓰지 않았다.
배경음은 생성기 안에서 사인파만으로 합성한 무보컬 패드다.
제3자 음원 데이터가 포함되지 않는다.
사람 내레이션은 별도 대본에 맞춰 나중에 녹음할 수 있다.

## 보존과 제외 사항

- 기존 PNG 수: %d장
- 생성 전후 SHA-256 일치: %s
- 기존 PNG를 영상에 바로 굽지 않고 원본 Python 데이터에서 임시 스틸을 다시 그렸다.
- 원본에 있던 금지 기호는 영상용 임시 스틸에서 등호와 일반 문장으로 바꾸었다.
- 최신 지시에 따라 모든 새 파일을 `program/onboarding/trace/` 아래에만 만들었다.
- 외부 BGM은 넣지 않았다. 대신 외부 샘플이 없는 합성 배경음을 넣었다.
""" % (
        total_duration,
        VIDEO_OUT.name,
        SRT_OUT.name,
        NARRATION_OUT.name,
        CHAPTERS_OUT.name,
        THUMB_OUT.name,
        REPORT_OUT.name,
        READING_CHARS_PER_SECOND,
        float(probe["duration"]),
        probe["codec_name"],
        probe["width"],
        probe["height"],
        probe["fps"],
        probe["pix_fmt"],
        probe["audio_codec"],
        probe["sample_rate"],
        probe["channels"],
        probe["duration"],
        probe["size"],
        size_mib,
        "true" if faststart else "false",
        "true" if decoded else "false",
        ffmpeg_version,
        ffprobe_version,
        len(hashes_before),
        "true" if unchanged else "false",
    )
    REPORT_OUT.write_text(report, encoding="utf-8")
    return unchanged


def render_preview_frame(clean_dir, scene_key, seconds, output_path):
    scene = next(scene for scene in SCENES if scene.key == scene_key)
    if not scene.still:
        raise RuntimeError("미리보기는 정지 화면 장면만 지원한다")
    board, geometry = fit_board(clean_dir / scene.still)
    local_time = max(0.0, min(scene.duration - 1.0 / FPS, seconds))
    if scene.kind == "step":
        prepared = prepare_step_versions(board, geometry)
        frame = render_step(
            scene,
            board,
            geometry,
            prepared,
            local_time,
        )
    else:
        frame = render_board(scene, board, local_time)
    # 쓰기도 같은 이유로 imwrite 를 못 쓴다. 인코딩해서 바이트로 쓴다.
    ok, encoded = cv2.imencode(".png", frame)
    if not ok:
        raise RuntimeError("미리보기 이미지를 저장하지 못했다")
    Path(output_path).write_bytes(encoded.tobytes())


def main():
    parser = argparse.ArgumentParser(
        description="A-COP 취소 및 환불 케이스 추적 영상을 만든다."
    )
    parser.add_argument(
        "--preview-step",
        default="",
        help="전체 영상 대신 지정한 장면의 미리보기 PNG를 만든다",
    )
    parser.add_argument(
        "--preview-seconds",
        type=float,
        default=7.0,
        help="미리보기 장면 안의 시간",
    )
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    total_duration = layout_scenes()
    prepare_text_layers()

    hashes_before = image_hashes()
    if len(hashes_before) != 17:
        raise RuntimeError(
            "기존 PNG가 17장이 아니다: %d장" % len(hashes_before)
        )

    with tempfile.TemporaryDirectory(
        prefix=".trace_build_",
        dir=str(HERE),
    ) as temporary_name:
        temporary = Path(temporary_name)
        clean_dir = temporary / "stills"
        clean_dir.mkdir(parents=True, exist_ok=True)

        print("영상용 스틸을 임시 생성", flush=True)
        render_clean_stills(clean_dir)

        if args.preview_step:
            preview_path = HERE / (
                "trace_preview_%s.png" % args.preview_step
            )
            render_preview_frame(
                clean_dir,
                args.preview_step,
                args.preview_seconds,
                preview_path,
            )
            print("미리보기 완료: " + str(preview_path))
            return 0

        ffmpeg = find_program("ffmpeg")
        ffprobe = find_program("ffprobe")
        audio_path = temporary / "background.wav"

        write_text_outputs()
        create_thumbnail()
        write_audio_wave(audio_path, total_duration)

        violations = forbidden_text_files(
            [SRT_OUT, NARRATION_OUT, CHAPTERS_OUT]
        )
        if violations:
            raise RuntimeError(
                "금지 기호가 텍스트 산출물에 남았다: "
                + repr(violations)
            )

        render_video(
            ffmpeg,
            clean_dir,
            audio_path,
            total_duration,
        )

    hashes_after = image_hashes()
    if hashes_before != hashes_after:
        raise RuntimeError("기존 PNG의 해시가 달라졌다")

    probe = probe_video(ffprobe)
    verify_probe(probe, total_duration)
    faststart = faststart_check(VIDEO_OUT)
    if not faststart:
        raise RuntimeError("faststart 검증 실패")
    decoded = decode_check(ffmpeg)

    unchanged = write_report(
        probe,
        hashes_before,
        hashes_after,
        faststart,
        decoded,
        total_duration,
        program_version(ffmpeg),
        program_version(ffprobe),
    )
    if not unchanged:
        raise RuntimeError("기존 PNG 보존 검증 실패")

    violations = forbidden_text_files(
        [
            SRT_OUT,
            NARRATION_OUT,
            CHAPTERS_OUT,
            REPORT_OUT,
        ]
    )
    if violations:
        raise RuntimeError(
            "금지 기호가 최종 텍스트 파일에 남았다: "
            + repr(violations)
        )

    print("완료: " + str(VIDEO_OUT))
    print(
        "검증: codec=%s, %sx%s, fps=%s, pix_fmt=%s, duration=%s"
        % (
            probe["codec_name"],
            probe["width"],
            probe["height"],
            probe["fps"],
            probe["pix_fmt"],
            probe["duration"],
        )
    )
    print("리포트: " + str(REPORT_OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

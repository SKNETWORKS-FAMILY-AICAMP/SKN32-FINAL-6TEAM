# 파일: program/산출물양식/_build/build_시스템구성도_v3.py
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# 같은 폴더의 A 스크립트에서 공통 변환·검증·저장 함수를 가져온다.
from build_아키텍처_v3 import build, FORMS, W2

CONFIG = {
    "src": (
        W2 / "아키텍처" / "시스템구성도_코덱스_3차.md"
    ),
    "template": (
        FORMS / "[모델배포] 시스템 구성도_양식.docx"
    ),
    "fig": (
        W2 / "표와시각자료" / "코덱스"
        / "SYS_전체서비스구조_코덱스.png"
    ),
    "out": (
        FORMS / "[모델배포] 시스템 구성도_2차_여행.docx"
    ),
    "stop": [
        "Claude에게 넘기는 목록",
        "반박 처리표",
    ],
    "anchors": {
        "1.": ("t", 2),
        "2.": ("t", 4),
        "2.1": ("p", 16),
        "2.2": ("p", 19),
        "2.3": ("p", 22),
        "2.4": ("p", 27),
        "2.5": ("p", 30),
        "3.": ("t", 5),
        "3.1": ("p", 33),
        "3.2": ("p", 38),
        "3.3": ("p", 44),
        "4.": ("t", 7),
    },
    "image_table": 3,
    "image_before": "1.",
    "main_tables": {
        "3.3": 6,
        "4.": 8,
    },
    "label_table": 8,
    "security": {
        "section": "4.",
        "heading": 48,
        "questions": [49, 50, 51, 52],
    },
}

if __name__ == "__main__":
    build(CONFIG)

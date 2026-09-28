# -*- coding: utf-8 -*-
"""데이터 경로 — 이동 엔진이 읽는 자료 폴더(DATA_DIR) 한 곳.

☆`[2026-09-29 문제목록 #48]` **import 할 때 `.env` 를 읽지 않는다.** 앞 판은 이 모듈을 불러오는 순간 저장소 맨 위
  `.env` 를 통째로 `os.environ` 에 넣었다(load_dotenv) — 서버 프로세스 안에서 앱 설정(app.core.settings)과 다른 길로
  환경이 바뀌는 숨은 통로였다. 이제 값이 들어오는 길은 둘이다.
    · 서버      — 기동 때 `configure(settings.mobility_data_dir)`(출처 "settings"). 설정의 정본은 app.core.settings.
    · 명령줄·시험 — `load_cli_env()` 가 저장소 맨 위 `.env` 의 DATA_DIR 을 읽는다(출처 "cli_env"). 데이터 기기의
      판정 회귀·자기점검·pytest 가 지금처럼 돈다. `runtime.build_verifier` 는 아무도 설정하지 않았을 때만 이것을 부른다.
  아무 것도 안 했으면 출처는 "unset" 이고 경로는 존재하지 않는 `/data` 다 — 적재가 「판정기 입력이 없다」로 멈춘다.

수집 쪽 `mobility_scripts/collect/_paths.py` 와 같은 폴더 규칙(DATA_DIR/travel/raw·processed)을 쓴다.

_paths.py 와 다른 점 둘
  · **폴더를 만들지 않는다.** 판정 엔진이 import 만으로 빈 폴더를 만드는 건 맞지 않는다
  · 저장소 루트를 `parents[n]` 으로 세지 않는다. `.git` 을 앵커로 위로 훑는다 —
    패키지 자리를 옮겨도 안 깨지고, 누가 `final_project_cs/.env` 를 놓아도 안 속는다

★ 다른 모듈은 `from .paths import PROCESSED` 를 **함수 안에서** 한다 — configure() 뒤의 값을 본다.
  모듈 맨 위에서 값을 복사해 두면 configure() 가 안 먹는다.
"""
import os
from pathlib import Path


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / ".git").exists():
            return p
    # .git 이 없는 배포본 — 패키지에서 여섯 칸 위가 저장소 루트다(69: mobility/engine/ 로 한 칸 더 깊이)
    return here.parents[6]


REPO_ROOT = _repo_root()
RULES_DIR = Path(__file__).resolve().parent / "rules"
UNSET_DIR = Path("/data")          # 설정하지 않았을 때의 자리 — 있을 리 없는 경로라 적재가 멈춘다

SOURCE = "unset"
DATA_DIR = TRAVEL = RAW_MOBILITY = RAW_BLOG = PROCESSED = None


def _layout(data_dir, source):
    global SOURCE, DATA_DIR, TRAVEL, RAW_MOBILITY, RAW_BLOG, PROCESSED
    DATA_DIR = Path(data_dir)
    TRAVEL = DATA_DIR / "travel"
    RAW_MOBILITY = TRAVEL / "raw" / "mobility"
    RAW_BLOG = TRAVEL / "raw" / "blog"
    PROCESSED = TRAVEL / "processed"
    SOURCE = source


_layout(UNSET_DIR, "unset")


def configure(data_dir, source="settings"):
    """자료 폴더를 정한다(서버 기동 때). 빈 값은 받지 않는다 — 조용히 옛 자리를 쓰지 않는다."""
    if not data_dir:
        raise ValueError("이동 자료 폴더(mobility_data_dir)가 비었다")
    _layout(data_dir, source)


def load_cli_env():
    """명령줄 도구·시험 전용 — 저장소 맨 위 `.env` 를 읽고(dotenv) DATA_DIR 이 있으면 그 자리로.
    서버는 이것을 부르지 않는다(configure 로 설정 값을 넘긴다). 이미 환경변수가 있으면 그것이 이긴다(dotenv 규칙)."""
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
    if os.environ.get("DATA_DIR"):
        _layout(os.environ["DATA_DIR"], "cli_env")
    return SOURCE

# datasets/mobility/scripts/_paths.py — 수집·전처리 스크립트 공용 경로. .env 의 DATA_DIR 기준
# 70: import 는 값만 정한다(부작용 없음). 폴더는 쓰는 스크립트가 쓰기 직전에 ensure_dirs() 로 만든다 —
#     읽기만 하는 곳(점검)은 부르지 않는다. DATA_DIR 미설정 기본값은 저장소 루트 기준 data/ (→ data/travel) ·
#     절대경로 /data 금지(.env 없는 CI 에서 import 시점 mkdir 이 PermissionError 로 수집을 죽였다).
# 82: 자리가 datasets/mobility/scripts/ 로 바뀌었다. 저장소 루트는 parents[n] 으로 세지 않고 final_project_cs/app 이 있는
#     조상을 위로 찾는다. 산출은 여전히 **정본** DATA_DIR/travel/processed/mobility/ — git 에 올리는 줄인 판
#     (datasets/mobility/processed/mobility/)은 reduce_75.py 가 정본에서 만든다(README 「갱신 순서」).
import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "final_project_cs" / "app").is_dir())   # SKN32-FINAL-6TEAM/
load_dotenv(REPO_ROOT / ".env")

_env_data_dir = os.environ.get("DATA_DIR", "").strip()
DATA_DIR = Path(_env_data_dir) if _env_data_dir else REPO_ROOT / "data"
TRAVEL = DATA_DIR / "travel"
RAW_MOBILITY = TRAVEL / "raw" / "mobility"
RAW_BLOG = TRAVEL / "raw" / "blog"
PROCESSED = TRAVEL / "processed"


def ensure_dirs() -> None:
    """산출 폴더 셋을 만든다 — 수집 스크립트가 쓰기 직전에 한 번 부른다(import 시점엔 만들지 않는다)."""
    for p in (RAW_MOBILITY, RAW_BLOG, PROCESSED):
        p.mkdir(parents=True, exist_ok=True)

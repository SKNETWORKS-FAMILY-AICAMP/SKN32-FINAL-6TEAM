"""`acop_composer_ui` — Composer API 클라이언트(UI 전용).

`final_project_ui` 가 pip 로 설치해 import 한다. 대상(cs·sample)의 Python 을
import 하는 것이 아니라, **sample 이 만들어 배포한 라이브러리**를 쓰는 것이라
`final_project_ui/CLAUDE.md` §0.3 이 금지하는 대상이 아니다.
"""
from acop_composer_ui.client import (
    DEFAULT_SUBJECT,
    DEPLOYMENT_HEADER,
    ComposerClient,
    ComposerResponse,
    Transport,
)

__all__ = ["ComposerClient", "ComposerResponse", "Transport", "DEFAULT_SUBJECT",
           "DEPLOYMENT_HEADER"]
__version__ = "0.1.0"

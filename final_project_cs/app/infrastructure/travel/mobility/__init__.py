# -*- coding: utf-8 -*-
"""이동·동선 판정 엔진 — 자기완결 패키지.

안에서는 상대 import 만 쓴다. 밖으로 나가는 의존은 하나뿐이다:
`paths.py` 가 저장소 루트의 `.env` 에서 `DATA_DIR` 을 읽는다(파일 읽기지 import 가 아니다).
그래서 이 패키지는 `final_project_cs/` 만 sys.path 에 있으면 돈다 —
저장소 루트가 sys.path 에 없어도 된다.

  from app.infrastructure.travel.mobility.runtime import get_verifier

★ 판정을 돌리려면 시간표가 필요하다. `.env` 의 `DATA_DIR` 이 없거나 그 아래
  `travel/processed/mobility/` 가 비어 있으면 `build_verifier()` 가
  `RuntimeError: 판정기 입력이 없다` 로 멈춘다 — 코드가 깨진 게 아니라 데이터가 없는 것이다.
  시간표(195MB)는 git 밖이다.
"""

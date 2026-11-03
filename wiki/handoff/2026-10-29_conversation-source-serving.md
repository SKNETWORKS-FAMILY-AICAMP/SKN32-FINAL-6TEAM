---
type: report
title: 대화 서빙 이어받기 — 장소 소개·일반 추천·실제 해석 경로
description: 기존 격리 사본에 후속 구현과 시험을 추가했다. 장소 소개 실모델 수락·보안·배포는 HOLD다.
status: draft
domain: travel
---

# 2026-10-29 대화 서빙 후속 인계

기존 [중단 재개 인계](2026-10-29_explain-writer-serving-resume.md)의 후속입니다. 원본 코드에는 통합하지 않았습니다. 다음 세션도 아래 **기존 격리 후보**에서 이어갑니다.

`C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/schedule-explain-impl-20261029/wt`

## 한 일 목록

- 관광공사의 신원·확인 시각이 있는 이름·분류·주소만 모델에게 주는 `place_narrative.py`를 추가했습니다. 특정 장소 description의 다중 읽기·단일 읽기를 연결했습니다. 고객 제목·메모·예약·좌표·UUID·질문 원문은 **이 추가 작성 호출**에서 제외했습니다.
- 일반 추천은 기존 general_requests에서 추천 이유·조건을 설명하도록 보완했습니다. 전체 일정 day/query와 특정 장소 description/target을 구분하도록 해석 SYSTEM을 수정했습니다. 스키마·사용자 프롬프트 고정 해시 3개는 유지했습니다.
- 실제 decide→읽기/실제 분기→writer→고객 answer를 실행하는 시험을 추가했습니다. 모델 전송·공공자료·영속성은 합성 대역이며 DB 포함 실서비스 시험과 구분합니다.
- 독립 검토가 발견한 필드 역할 역전·JSON 재시도의 호출 비용 누락·문장 거절 원인 과장을 보완했습니다. 설명은 물리적 SDK 요청마다 예산·남은 시한을 검사합니다. 자료·작성 실패는 원인과 확인 자료를 보여 줍니다.

## 실측과 수락 상태

| 범위 | 결과 |
|---|---|
| 최종 관련 회귀 | **401/401 = 100%** |
| 독립 검토 재실행 부분집합 | **34/34 = 100%** — 위 401에 포함, 합산 금지 |
| architecture·contract·security 선택 관문 | **630/631 = 99.84%**, 기존 XML HOLD 실패1; 별도 31 deselected |
| ruff F·E9 | 종료0 |
| 유료 실모델 합성 질문의 해석 경로 | **3/3 = 100%**, 작은 개발 표본 |
| 장소 소개 실모델 문장 채택 | **0/1 = 0%**, 검사 거절·원인 및 자료 목록 반환 |
| 일정 설명·일반 추천 실모델 답 | 각각 **1/1 = 100%**, 작은 표본만 |

유료 실제 호출은 **5/5회 한도**를 사용했습니다. 입력 29,142·출력 848토큰이며 고객 자료 전송0입니다. 현재 단가·실제 청구액은 확인하지 않아 금액은 확정하지 않습니다. 장소 소개의 실패 원문은 보존되지 않아 표현 문제인지 실제 근거 오류인지 알 수 없습니다. **최종 문장형·SYSTEM·실패 안내 보완 뒤 유료 재호출은 하지 않았습니다.** 일반 답은 추천과 이유를 썼지만 조건 비교 문장은 없었습니다.

독립 검토는 **격리 오프라인 후보 한정 승인**입니다. 장소 소개는 현재 분류·위치만 다루며 풍부한 역사·특징·취향 적합성의 자유 서술은 지원하지 않습니다. 유효한 의역도 제한 문장형 밖이면 거절할 수 있습니다. 기존 일정 의미 검사의 복잡한 한국어·여러 문장 순서·새 이름 한계도 남아 있습니다. 전체 서빙 완료율은 **분모 모름**입니다.

로컬 E4B 재측정·DB 포함 전체 통합·최종 장소 소개 실모델 수락은 남아 있습니다. DoD는 이전 인계의 자식 격리 문제 때문에 이번에 다시 실행하지 않았습니다. 26/26 통과로 세지 않습니다.

## 보존·증거·다음 위치

- 보안 XML 원본·격리 후보 SHA256은 모두 `4139dd065887867094dd053a5e9de007697efe039a57a64b200dd15584bd3a0a`입니다. XML 수정·삭제·HOLD 해제0, 생산 DB·설정·서빙 교체·배포·push·TeamFlow 쓰기0입니다.
- 새 clone·모델·DB·전체 데이터 사본0입니다. 기존 사본은 임의 release·삭제하지 않았습니다. 최종 disk_guard inventory는 entries=[]·unregistered_dirs=[], free_bytes=182979661824·최소32212254720·목표400000000000입니다. scratch 등록·전체 디스크 쓰기 보호를 보장하는 값은 아닙니다.
- 세션 폴더의 `conversation-backup/`에 변경 직전 7파일과 양쪽 handoff 목차, `conversation-manifest.json`·`conversation-changes.patch`에 이번 코드·시험·계약의 해시·차이가 있습니다. 앞선 resume 백업·r8·실패 XML도 보존했습니다.
- 이번 백업은717,144바이트, 새 source/test 3파일은27,044바이트, patch는51,542바이트입니다. 백업·시험 증거·유료 기록·검토·patch 등의 합계는1,073,297바이트이며 `conversation-artifacts.json`에 파일별 크기를 남겼습니다. disk_guard 출력은 `conversation-inventory.json`에도 보존했습니다.
- 실행 증거: `ev/conversation-joint-final.xml`, `ev/conversation-gates.xml`, `paid/conversation-live/SUMMARY.json`, `review4/independent-review4.md`. 후속 상세 보고서는 격리 후보의 `final_project_cs/wiki/records/reports/2026-10-29_conversation-source-serving.md`입니다.

다음에는 이 격리 후보의 상세 보고서와 review4를 먼저 읽고, 합성 개발 표본으로 최종 장소 소개 수락부터 확인합니다. 유료 추가 호출은 예산 상한을 먼저 정합니다. 운영 배포·원본 역복사·보안 XML 변경은 하지 않습니다.

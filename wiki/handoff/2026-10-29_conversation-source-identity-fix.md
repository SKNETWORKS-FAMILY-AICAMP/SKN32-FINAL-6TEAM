---
type: report
title: 대화 서빙 후보 출처 신원 검증 수정 인계
description: 독립 검토 실패 2건 재현 후 수정, 합성 회귀 검증. 서비스·보안 HOLD 유지.
status: draft
domain: travel
---

# 2026-10-29 출처 신원 검증 수정

기존 [독립 검토](2026-10-29_conversation-independent-review.md)의 실패 2건을 수정했습니다. 기존 후보 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/schedule-explain-impl-20261029/wt`를 재사용했습니다. 원본 제품 코드는 변경하지 않았습니다.

한 일 목록:

- 적용 지침·wiki 응답 계약·역할·관련 `_coord` NOTICE를 확인하고 수정 범위를 등록했습니다. 계약 설명을 구현 전에 보완했습니다. 이번 검토는 같은 세션의 검증이며 새 독립 승인으로 표시하지 않습니다.
- 기존 독립 검토 시험 그대로 실행하여 **5/7 = 71.43%**, 신원 불일치·종류 누락 실패 2건을 재현했습니다. 실제 응답 대신 요청 ID를 넣고 누락 종류를 요청값으로 채우던 경위를 확인했습니다.
- `TourApiPlace.by_content_id`가 응답 한 건의 명시적 ID·종류를 요청과 비교한 뒤에만 출처·확인 시각을 붙이고 분류를 만듭니다. 누락·불일치·비정상 자료형·다중 행을 거절하고 고정 진단 코드를 셉니다. 요청값으로 누락 필드를 추정하지 않습니다.
- 합성 HTTP 봉투→실제 어댑터→해석·작성→고객 답 경로를 시험했습니다. 거절한 행의 이름·주소·주입 문자열은 작성기·고객 답·진단 로그에 전달되지 않습니다. 모델을 호출하지 않고 기존 `source_missing`·확인 시각·장소 재선택/공식 자료 확인 안내를 제공합니다. 재시도·다른 출처로의 무음 대체는 없습니다. 정상 응답은 구조화 작성기를 통해 출처와 함께 답합니다.
- 새 clone·DB·모델 사본 없이 단일 시험 프로세스·CPU 스레드 1로 실행했습니다. 유료 호출·고객 데이터·운영 접근·push·배포·삭제·release는 없습니다. 이전 paid·review·실패 증거를 보존했습니다.

| 직접 실행 | 결과 |
|---|---|
| 기존 독립 검토 재실행 | **7/7 = 100%**, 기존 실패 2건 포함 |
| 최종 관련 회귀 19파일 | **565/565 = 100%**, 로컬 HTTP 4건 별도 제외 |
| 합성 loopback HTTP 회귀 | **4/4 = 100%**, 외부 통신·DB 차단 |
| architecture·contract·security 선택 관문 | **630/631 = 99.84%**, 기존 scanner/XML 실패 1·별도 31 deselected |
| ruff F·E9 | 변경 코드·새 시험 종료 0 |

최초 회귀는 모든 소켓을 차단하여 **564/568 = 99.30%**, 합성 HTTP 서버 시험 4건이 하네스 제약으로 실패했습니다. 실패 로그를 보존하고 해당 4건만 합성 127.0.0.1 서버를 허용해 검증했습니다. 최종 회귀의 4건 제외를 성공으로 세지 않았습니다. 최초 probe 경로 오류도 보존했습니다. 집계가 겹치는 실행을 합산하지 않습니다.

보안 검사기·예외·보호 XML은 변경하지 않았습니다. 원본·후보 XML SHA256은 모두 `4139dd065887867094dd053a5e9de007697efe039a57a64b200dd15584bd3a0a`이며 검사기는 각자의 세션 시작 해시를 유지합니다. 기존 실패를 지우거나 승인으로 바꾸지 않았습니다. 서비스·보안 HOLD 유지, 전체 서비스 완료율은 **분모 모름**입니다.

증거는 후보 상위 `identity-fix/`의 `red.xml`, `red-repro.log`, `review-green-final.xml`, `regression-final.xml`, `loopback.xml`, `gates.xml`, `lint-final.log`, 실행 명령·수정 전 백업·패치·해시 목록입니다. 상세 보고서는 후보 `final_project_cs/wiki/records/reports/2026-10-29_conversation-source-identity-fix.md`입니다. 실제 제공처·실모델·DB 통합·브라우저·현재 E4B·전체 DoD·운영 수락은 이번에 검증하지 않았습니다. 새 독립 검토와 기존 서비스 수락 한계는 남아 있습니다.

디스크 inventory는 `identity-fix/disk-inventory-final.json`에 보존합니다. entries=[]·unregistered_dirs=[], free_bytes=182635560960, minimum=32212254720, target=400000000000입니다. 생성 파일별 크기는 `identity-fix/artifacts.json`에 남깁니다. 기존 scratch가 모두 등록되거나 모든 쓰기가 보호된다는 뜻은 아닙니다.

정정(후속 검토): 로컬 OpenAI 엄격 스키마 시험 **3/3 = 100%** 통과(`strict-schema.xml`). 객체 폐쇄·선택 필드 nullable/null 제거·대역 SDK 전송 검증이며 실제 공급자 API 수락은 아닙니다.

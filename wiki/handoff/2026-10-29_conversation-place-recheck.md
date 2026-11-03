---
type: report
title: 대화 후보 장소 소개 실모델 1회 재검증 인계
description: 공공 필드 단어 오거절 수정·429 회귀 통과. 과거 실패의 구체 원인과 서비스 및 보안 HOLD는 유지.
status: draft
domain: travel
---

# 2026-10-29 장소 소개 재검증 인계

기존 [대화 서빙 인계](2026-10-29_conversation-source-serving.md)의 후속입니다. 코드 작업 위치는 그대로입니다.

`C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/schedule-explain-impl-20261029/wt`

## 한 일 목록

- 원본·후보 지침과 wiki 계약·review4·관련 `_coord` NOTICE를 읽고 별도 recheck NOTICE로 같은 파일 범위를 알렸습니다. 새 에이전트·clone·모델·DB 복제 없이 기존 후보를 재사용했습니다. 검토는 이번 세션 자체 검토이며 독립 승인 추가가 아닙니다.
- 장소 소개 검사기가 공공 장소명/분류/주소 원값 안의 `주소`·`분류`도 역할 역전으로 오인하는 결함을3/3건 재현하고 수정했습니다. 필드별 문장형·원값 보존·역할 역전/부정문 거절은 유지합니다. 과거 합성문화원 실패 원문은 없어 **이 결함이 이전0/1의 원인이라고 단정하지 않습니다**. 당시 구체 원인은 미확정입니다.
- 합성 공개 필드만 유료 작성 모델 `gpt-6-luna`에1회 호출했습니다. 실제 원문은 “합성문화원은 관광지로 분류된 장소예요. 합성문화원은 서울 종로구 합성길 1에 위치해 있어요.”이며 검사 통과, 최종 고객 답에 출처·합성 확인 시각·자료 한계를 붙였습니다. **실모델 작성1/1 = 100%**, 작은 개발 표본입니다. 실제 해석까지 새로 유료 검증한 결과는 아닙니다.
- 이번1/1회 한도를 소진했습니다. 입력449·출력63토큰, actual max_completion_tokens1600, finish_reason=stop입니다. 실제 청구/계정 spend는 확인 자료가 없어null입니다. 이전5회와 별도 기록이며 추가 호출하지 않았습니다. 원문·최종 답은 세션 `paid/place-recheck/RESULT.json`에 보존했습니다. 최종 코드에서는 같은 원문을 오프라인으로 재검사·고객 dispatcher 재생했습니다. 두 번째 실호출이 아닙니다.
- 실제 decide→FailoverChat→OpenAIChat→SDK 대역→읽기/단일 분기→작성→고객 answer의 개인정보 시험을 추가했습니다. 합성 연락처5형식×4경로20/20 = 100%, 공개 필드 단어3개·역할 역전/부정문4개·실모델 원문 재검사1개를 합쳐 새28개입니다. SDK·자료·영속성은 합성 대역이며 DB 포함 실서비스 검증과 구분합니다.

## 최종 결과와 보류

| 범위 | 결과 |
|---|---|
| 관련 회귀13파일 | **429/429 = 100%** — 이전401+새28을 같은 실행에서 셈 |
| architecture·contract·security 선택 관문 | **630/631 = 99.84%**, 기존 scanner/XML HOLD 실패1, 별도31 deselected |
| ruff F·E9 | source·새 시험·probe 종료0 |
| 이번 실모델 장소 소개 작성 | **1/1 = 100%** — 합성 공개 필드 한 표본 |
| 이번 유료 물리 요청 | **1/1회**, 추가0 |

보안 scanner 수정·예외 추가·보호 XML 변경·HOLD 해제0입니다. 원본·후보 보호 XML SHA256은 계속 `4139dd065887867094dd053a5e9de007697efe039a57a64b200dd15584bd3a0a`입니다. 푸시·배포·서빙 교체·TeamFlow 쓰기·원본 코드 통합·삭제0입니다.

과거0/1 원인은 원문 부재로 미확정입니다. 임의 이름·주소·예약번호까지 기존 해석 경로에서 전부 마스킹한다는 보장도 없습니다. 이번에는 연락처 패턴의 API 마스킹과 추가 작성 호출의 공개 필드 한정, 최종 answer의 오류 비공개를 확인했습니다. 고객 소유 질문 metadata 전체를 없애는 시험은 아닙니다. DB 포함 통합·현재 E4B·일반 추천 조건 비교·일정 설명 의미 검사 한계·운영 수락은 남아 있습니다. 전체 서빙 완료율은 **분모 모름**, 서비스·보안 HOLD를 유지합니다.

세션 상세 보고서는 후보의 `final_project_cs/wiki/records/reports/2026-10-29_conversation-place-recheck.md`입니다. 증거는 `ev/conversation-recheck-regression-final.xml`, `ev/conversation-recheck-gates.xml`·`.log`, `ev/conversation-literal-red.xml`, `paid/place-recheck/RESULT.json`입니다. 수정 전 파일·목차는 `recheck-backup/`, 이번 차이는 `recheck-changes.patch`·`recheck-manifest.json`에 보존합니다. 기존 백업·paid·실패 XML은 그대로입니다.

최종 `disk_guard inventory`: entries=[]·unregistered_dirs=[], free_bytes=182877392896, minimum=32212254720, target=400000000000입니다. scratch 등록이나 모든 쓰기 보호를 뜻하지 않습니다. 새 대형 사본은 없고 파일별 생성 크기는 `recheck-manifest.json`·`recheck-artifacts.json`을 확인합니다. 기존 사본을 임의 release하지 않았습니다.

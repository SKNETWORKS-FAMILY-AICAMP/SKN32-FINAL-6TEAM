---
type: report
title: 출처 공식 스키마 후속 검토
description: 공식 문서·코드 대조, 제외 시험과 문장 정정. 서비스·보안 HOLD 유지.
status: draft
domain: travel
---

# 출처 공식 스키마 후속 검토

**명시된 요청/항목 형식은 후보와 호환됩니다. 실제 제공처 JSON 전체 수락은 미확인, 서비스·보안 HOLD 유지입니다.** 전체 서비스 완료율: **분모 모름**.

기존 schedule-explain-impl-20261029/wt 재사용. 규칙/RULE·wiki 역할/코드 경로/응답 계약·coord answer-contracts/identity/paid serving 확인. 제품 코드·공유 계약 변경 없음.

| 이번 실행 | 결과 |
|---|---|
| 이전 제외 HTTP 시험 | **4/4 = 100%**, 다른 59 deselected |
| 공식 문서 기반 합성 시험 | **1/1 = 100%** |
| 기존 strict 시험 | **3/3 = 100%** |
| 보호 scanner/XML 전후 해시 | **4/4 = 100%** 일치 |

이전 565건은 재실행하지 않았고 새 단일 569/569 회귀 통과로 합산하지 않습니다.

[공식 포털](https://www.data.go.kr/data/15101578/openapi.do)의 HTML const swaggerJson을 키 없는 urllib GET으로 확보했습니다(web open은 unsupported content-type). 추출은 review7/official-detailCommon2.json. 데이터 API 호출은 없습니다.

공식 host apis.data.go.kr/B551011/KorService2, /detailCommon2. 필수 쿼리 MobileOS·MobileApp·contentId·serviceKey, 선택 _type·numOfRows·pageNo. 후보는 필수 항목을 포함하고 문서의 이름만 보냅니다. contentTypeId는 목록에 없고 후보도 생략합니다. 넣으면 오류라는 과거 주석은 재실측하지 않았습니다.

body.items.item은 object, contentid/contenttypeid/title/addr1/mapx/mapy는 string. 후보의 단일 object 정규화·명시적 문자열 신원 비교와 호환됩니다. 정수와 1행 list는 로컬 추가 허용이며 공식 보장이라 하지 않습니다. source/confirmed_at은 검증 뒤 로컬 부착입니다.

**한계:** 공식 schema 최상위는 header/body이고 xml.name=response만 있어 실제 JSON response 래퍼를 확정하지 못합니다. 응답 required 목록도 없어 신원 필드의 항상 존재를 증명하지 못합니다. 시험은 문서 item 필드를 모두 string으로 만들고 합성 ID/이름/주소/좌표와 기존 코드의 response 래퍼를 붙였습니다. 필드/요청 호환성이지 authentic production response나 전체 wire 인증이 아닙니다. 고객·키·원시 캐시는 열지 않았습니다.

원본 identity-fix 인계와 후보 보고서의 손상된 strict-schema.xml 참조를 실제 testcase 3개 및 소스와 대조하고 재실행했습니다. 마지막 문장만 근거 기반 정정하며 유실 원문 복원이라고 하지 않습니다. 원본 백업 review7/doc-backup, 최초 문장/testcase sentence-correction.json. 최초 쓰기에서 PowerShell stdin 한글 손상을 발견하여 UTF-8로 바로 정정했습니다. 도구 오류와 중간 실패를 숨기지 않습니다. 이전 독립 보고서는 당시 기록으로 보존합니다.

HTTP 실행: 기존 date_risk_env_312 Python + identity-fix/run_loopback.py, tests/unit/infrastructure/test_llm_failover.py -k test_http_ -q -p no:cacheprovider. 닫힌 포트·timeout·503 재시도·정상 로컬 HTTP, fake OpenAI SDK, 127.0.0.1만 허용, 외부 socket/DB 차단. 문서/strict는 기존 run_isolated.py로 socket/DB 차단. SCHEDEXPL_ROOT=기존 wt/final_project_cs, PYTHONDONTWRITEBYTECODE=1, OMP/MKL/OPENBLAS_NUM_THREADS=1, 단일 pytest. 증거 review7/loopback.log/xml·schema.log/xml·test_official_documented.py·protected-start/final.json.

한 일: 규칙/wiki/coord 검토, 공식 문서/코드 비교, 제외 4건과 문서/strict 4건 실행, 문장 정정, 해시/inventory/인계. 유료 호출·민감 자료·운영 변경·clone·push·삭제 0건. scanner/XML과 기존 실패는 유지하고 재승인하지 않습니다.

남은 일: 공식 JSON 봉투 문서 또는 승인된 비민감 실제 응답으로 wrapper/필수값 검증. 실제 제공처 성공·현재 실모델·DB/브라우저·전체 DoD·배포 미확인. 서비스·보안 HOLD 유지, 유료/운영 호출 승인 없음.

디스크 inventory review7/disk-inventory.json: entries/unregistered_dirs가 비어도 모든 scratch 보호를 뜻하지 않습니다. 새 사본 0, 증거/백업 크기 review7/artifacts.json. 가드는 모든 쓰기를 막지 않습니다.

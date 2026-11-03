---
type: report
title: 대화 출처 신원 수정 독립 검토
description: 기존 후보 재사용, 합성 경계와 실제 어댑터 구조화 계약 검증. 서비스·보안 HOLD 유지.
status: draft
domain: travel
---

# 2026-10-29 출처 신원 수정 독립 검토

판정: **검토한 ID·종류 수정 범위는 통과, 서비스·보안 수락은 HOLD 유지**입니다. 제품 코드·계약은 수정하지 않았습니다. 인계 문서의 마지막 손상 문장 1건은 아래 P2 문서 결함으로 남깁니다. 전체 서비스 완료율은 **분모 모름**입니다.

검토자: 이번 독립 Codex 세션. 구현 세션의 자기 검증 결과를 새 독립 승인으로 재사용하지 않았습니다. 기존 후보 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/schedule-explain-impl-20261029/wt`를 재사용했습니다. 적용 루트·cs AGENTS/CLAUDE/RULE, wiki 응답 계약·개발 역할·코드 경로와 scratch `_coord`의 answer-contracts·conversation independent/source identity·paid serving NOTICE를 읽었습니다. 원본 루트 사용자 지시를 우선하며 새 NOTICE에 읽기 전용 검토 범위를 등록했습니다.

## 직접 확인 결과

| 실행 | 결과 | 범위·제외 |
|---|---|---|
| 독립 경계 + 기존 집중 6파일 | 142/142 = **100%** | 합성 전송, 실제 TourApiPlace·해석·작성·응답 코드 |
| 독립 경계 최종 + 엄격 스키마 | 31/31 = **100%** | 앞 실행과 경계 27건 중복, 추가 실제 SDK 경로 1건 + 기존 strict 3건 |
| 관련 회귀 19파일 | 565/565 실행 = **100%** | 4 deselected. 선택 전체 569건 중 실행 565/569 = **99.30%**; 미실행 4건을 통과로 세지 않음 |
| 보호 파일 전후 해시 | 4/4 = **100%** 일치 | 원본·후보 scanner와 보호 XML 각각. scanner 예외·코드·XML 수정 없음 |

실행 시각은 review6 JUnit timestamp, 자세한 원문은 `review6/focused.log`, `strict-and-boundaries.log`, `regression.log`와 동명 XML입니다. 겹치는 실행을 합산하지 않습니다. 최초 위치 조회 오류는 도구 기록에 남아 있으며 시험 실패로 바꾸거나 숨기지 않았습니다.

- 응답 contentid·contenttypeid의 누락·불일치·잘못된 자료형·다중 행을 실제 어댑터에서 거절합니다. 요청값으로 채우거나 이름 검색·다른 출처로 다시 시도하지 않습니다. 거절 행의 이름·주소·주입 문자열은 작성기·고객 답·진단에 나오지 않습니다.
- 전각·아라비아 숫자, 지수 표기, percent/NUL, BOM, zero-width, CRLF를 ID에 넣은 독립 반례를 거절했습니다. JSON에 없는 bytes는 파싱 뒤 객체 경계에서 별도 시험했습니다. 이 결과는 모든 가능한 인코딩의 증명이 아닙니다.
- 현재 정규화 계약은 flat `source='tour_api'`, content_id, content_type_id, timezone이 있는 confirmed_at입니다. source를 모순된 nested 객체(provider/ID/종류)로 바꾸면 source_unverified로 거절되고 작성기를 호출하지 않습니다. 임의 nested 객체를 다른 생산 계약으로 인정하지 않았습니다.
- missing/예외/ID·종류 불일치에서 확인 실패·확인 시각·고정 오류 코드·장소 재선택 또는 공식 자료 확인을 제공합니다. 폐업·인증키 오류·한도 초과를 확인한 것으로 지어내지 않습니다. 예외에 넣은 합성 키·연락처는 노출되지 않습니다. 원인 상세를 모르면 source_missing/source_unavailable보다 구체적으로 단정하지 않습니다.
- 정상 객체형·1행 목록형 JSON 봉투 모두 실제 TourApiPlace → introduce → 구조화 작성기 → 고객 답까지 수락했습니다. HTTP 요청은 KorService2/detailCommon2 + contentId + _type=json이며 contentTypeId는 보내지 않습니다. source와 confirmed_at은 검증 후 붙습니다.
- 실제 운영용 코드 클래스 `FailoverChat`·`OpenAIChat`·`strict_schema`를 거쳐 합성 SDK create까지 실행했습니다. 모든 object의 additionalProperties=false와 required=properties를 재귀 확인하고 정상 해석·작성·resolved 응답 수락을 확인했습니다. 해석용 유료 스키마와 로컬 evidence enum은 기존 시험으로 구별했습니다. 모델 SDK만 대역이며 유료 공급자의 서버가 이 요청을 수락했다는 뜻은 아닙니다.
- 합성 전화번호 다섯 표기·이메일, 개인 숙소 이름·좌표·메모·예약번호의 실제 모델 어댑터 전송 경로 검사를 재실행했습니다. 추가 장소 작성 호출에는 고객 문맥이 없고 해석 호출의 연락처는 가려집니다. 기존 보존 모델 출력 1건은 오프라인 재생이며 이번 실호출이 아닙니다.

## 발견 사항과 수락 한계

**P2 문서 결함**: 검토 대상 원본 handoff 마지막 줄과 후보 상세 보고서에 `?? ??? API ...`가 실제 ASCII 물음표로 저장돼 있습니다. UTF-8 strict 디코딩은 성공하므로 터미널 코드페이지 현상과 다릅니다. 복원할 원문은 확인하지 못했습니다. 기존 기록을 추정해서 고치지 않았습니다. `identity-fix/strict-schema.xml`의 실제 3개 testcase는 test_openai_strict_schema의 object closure/nullable/실제 structured 전송 검증입니다. 손상된 한 문장을 생산 제공처 수락의 증거로 읽으면 안 됩니다.

제공처 문서의 진위와 합성 모양의 그럴듯함을 구분했습니다. [공식 공공데이터포털 서비스](https://www.data.go.kr/data/15101578/openapi.do?recommendDataYn=Y)는 한국관광공사·JSON/XML·공통정보 제공을 확인할 수 있지만 이번 웹 조회에서는 detailCommon2의 정확한 출력 스키마 본문을 확보하지 못했습니다(직접 open은 unsupported content-type). 검색에 나온 제3자 재배포 문서는 정본으로 쓰지 않았습니다. 따라서 **현재 공식 wire schema의 모든 필드·형식 인증 및 실제 제공처 성공 응답 수락은 미확인**입니다. 합성 fixture를 authentic production response라고 부르지 않습니다. 소스 주석의 과거 실측도 이번 실측으로 재명명하지 않습니다. 실서비스 점검을 위해 키·고객 자료에 접근하거나 실제 API를 호출하지 않았습니다.

실모델의 현재 해석 정확도·전체 E4B·DB 통합·브라우저·전체 DoD·운영 배포 수락은 미실행입니다. 기존 scanner/XML 실패를 다시 승인하지 않았으며 기존 HOLD를 유지합니다. 이번은 병합이 아닌 제한 검토이므로 전체 통합 관문을 주장하지 않습니다. 외부 socket·DB는 기존 run_isolated.py로 막고 단일 pytest 프로세스·CPU 스레드 1로 실행했습니다. socket 차단 때문에 실제 HTTP 서버 4건을 제외했고 이 세션에서 loopback 재실행은 하지 않았습니다.

## 한 일·인계

한 일: 규칙/wiki/coord 확인, 후보 재사용, 새 독립 반례 28건 작성, 기존 경계·privacy·strict·19파일 회귀 실행, 보호 해시 전후 대조, 문서 손상과 공식 schema 미확보 한계 기록, 보고·인계 추가. 제품 코드 수정·유료 호출·고객 데이터·운영 변경·push·배포·새 clone·삭제·release는 0건입니다.

다음 담당: 손상된 문장은 원문 증거가 있는 담당자가 별도 정정 기록으로 보완하고, 서비스 수락은 제공처 공식 스키마와 실제 성공 응답·현 모델 해석을 확보한 뒤 따로 판정해야 합니다. 운영 호출 승인이 이번 검토에 포함된다고 해석하지 않습니다.

재실행: 기존 session/run_isolated.py에 SCHEDEXPL_ROOT=wt/final_project_cs, PYTHONDONTWRITEBYTECODE=1, OMP/MKL/OPENBLAS_NUM_THREADS=1을 주고 review6/test_independent.py 및 기존 시험 경로를 pytest 인자로 전달했습니다. 모든 실행은 -q -p no:cacheprovider -p pytest_asyncio.plugin --junitxml=review6/<이름>.xml. 19파일 목록은 identity-fix/regression-command.json과 같고 -k 'not test_http_'만 추가했습니다. 네트워크/DB 차단 및 fake 설정은 runner 코드에 남아 있습니다.

증거: 기존 session/review6/의 독립 시험·finalize.py·로그·JUnit·protected-start/final.json·disk-inventory.json·artifacts.json. 파일 크기 합계는 artifacts.json에 기록합니다. inventory의 entries/unregistered_dirs가 비어 있어도 모든 scratch가 등록·보호됐다는 의미는 아닙니다. 원본·후보 XML SHA256은 `4139dd065887867094dd053a5e9de007697efe039a57a64b200dd15584bd3a0a`로 동일합니다. scanner는 원본과 후보의 시작 해시가 서로 다르며 이번에는 각각 유지됐다는 뜻입니다.

---
type: report
title: ST4F-746 예약 합성 주소 치환 가능성 독립 검토
status: draft
domain: travel
---

2026-10-29 후속 결론: **HOLD 유지, 보존된 제품·시험·스캐너 파일 수정 0건**. 연결 가짜 객체만 사용하는 7/9 = 77.8% 시험 지적은 TEST-NET 합성값으로 바꿔도 이번 비교의 동작을 유지했습니다. 실제 공인 DNS 검증에 들어가는 2/9 = 22.2%는 같은 방법으로 바꾸면 시험 의미가 깨집니다. 별도 스캐너 허용 선언 1건까지 있어, 이 치환만으로 예외 없는 원본 detector 관문을 통과시킬 수 없습니다.

## 실제 실행 비교

기존 released 후보의 동일한 세 시험 파일을 디스크에서 읽고, pytest Module의 메모리 source만 바꿨습니다. 제품 함수·스캐너·assertion·시험 목록은 변경하지 않았습니다. 순차 실행, xdist 없음, pytest 자동 플러그인·conftest 로드 없음, cache 쓰기 없음입니다. 이 구성은 통합 관문이 아니라 세 파일의 통제된 비교 실험입니다. 각 variant에서 같은 114개를 수집했고 skip/error는 모두 0입니다. DB는 기동하지 않았으며 외부 서비스 설정은 mock/합성값입니다.

| 비교 대상 | 통과 | 실패 | exit |
|---|---|---|---|
| 변경 없는 기준 시험 | 114/114 = 100% | 0 | 0 |
| 9곳 모두 TEST-NET-1로 치환 | 110/114 = 96.5% | 4 | 1 |
| 공인 DNS 검증용 2곳을 유지하고 7곳만 치환 | 114/114 = 100% | 0 | 0 |

최초 실행은 필수 Settings 환경변수를 비운 상태여서 기준·7곳 치환 모두 111/114 = 97.4%, 일괄 치환 107/114 = 93.9%였습니다. 공통 3실패는 Settings의 필수 입력 누락으로 XML에서 확인했습니다. 이를 별도 configured 실행의 합성 설정으로 해결했으며 최초 실패 XML/로그는 그대로 보존했습니다. configured 실행은 `python scratch/st4f746-fixture-review-20261029/configured.py`로 생성했습니다. 실행 폴더가 이미 있으면 다시 쓰지 않고 중단하므로 재현 시 새 결과 폴더가 필요합니다.

일괄 치환의 추가 실패는 `test_redirect_to_private_or_unlisted_host_is_blocked_before_following`, `test_redirect_count_is_bounded`, `test_html_metadata_is_read_without_running_or_returning_scripts`, `test_non_text_response_is_not_downloaded_as_metadata`입니다. 모두 앞선 DNS 검사에서 `private_destination`으로 끝나 원래 검증할 unsupported_host/redirect_limit/metadata/content-type 경로에 도달하지 못합니다. DNS 재검증 시험 하나는 치환 후에도 통과할 수 있지만, 시작 DNS부터 거부되어 통과하는 경우라 원래 의미를 보존했다는 증거가 아닙니다.

## 위치별 판정

| 후보 시험 위치 | 치환 대상 수 | 판정 |
|---|---|---|
| activity_public_web_fallback 217·222행 | 2 | `_public_addresses`와 연결 객체를 함께 대체하며 전달 IP 일치 assertion도 함께 치환. 이번 비교에서 유지 |
| activity_public_web_text_evidence 206행 | 1 | DNS 결과·HTTP/HTTPS 연결 모두 가짜 객체. 이번 비교에서 유지 |
| social_links 324·359·393·424행 | 4 | `_request`에 주는 주소이고 연결 객체는 가짜. 크기·head 중단·timeout 시험 결과 유지 |
| social_links 231·258행 | 2 | 실제 `_public_addresses`의 공인성·redirect 재검증 입력. 단순 예약값 치환 불가 |
| security scanner 35행 | 1 | 기존 허용 선언. 시험 fixture가 아니며 이번 사용자 범위의 detector/예외 변경 금지에 해당 |

[RFC 5737 §3–4](https://www.rfc-editor.org/rfc/rfc5737.html#section-3)는 TEST-NET 세 대역을 문서·예시용으로 예약하고 공용 인터넷에 나타나지 않도록 설명합니다. 이번 실제 제품 `_public_addresses` 함수에 DNS 결과만 mock하여 독립 호출한 결과, 기존 fixture는 accepted, TEST-NET-1/2/3 대표값은 3/3 = 100% `private_destination`입니다. DNS 또는 연결을 실제 외부로 보내지 않았습니다. `is_global`을 mock하거나 제품 공인성 검사를 바꿔 통과시키지 않았습니다.

## 스캐너·증거 보존과 차단 조건

변경 없는 로컬 원본 detector를 그대로 import하여 네 지적 파일을 재검사했습니다. 기준은 4파일/10건입니다. 7곳만 치환하면 남는 것은 2파일/3건(공인 DNS fixture 2건, 기존 scanner 선언 1건)입니다. 9곳을 모두 바꿔도 scanner 선언 1건이 남고, 앞서 보인 의미 손상이 생깁니다. source-comparison의 scanner 값 치환 결과는 원인 구분용 문자열 계산일 뿐 적용 후보나 승인된 수정이 아닙니다. scanner 파일·함수·전역·허용 목록은 어떤 실행에서도 바꾸지 않았습니다.

이번은 네 지적 파일 및 동일 세 시험의 비교이며 저장소 전체 보안 PASS가 아닙니다. 기존 manifest·CS 범위 결과·전체 저장소 timeout 기록을 그대로 보존합니다. 파일을 제외하거나 검사 열거 범위를 줄인 새 관문을 만들지 않았고, 필수 관문 인정은 기존 2/3 = 66.7%·HOLD를 유지합니다. 원격 최신성·운영 수락은 이번에 검증하지 않았습니다.

원래 후보의 fixture 파일 해시가 이미 독립 검토 증거에 들어 있습니다. 기존 후보 파일을 바꾸면 보존된 기준의 재현성이 깨지고, scanner 선언을 없애는 일은 명시된 detector/예외 변경 금지와 충돌합니다. 따라서 보존본은 변경하지 않았습니다. 7곳 치환은 메모리 실험 결과만 남겼으며 통합 가능한 수정으로 제출하지 않습니다. 후속 담당은 **원본 증거와 분리된 새 작업 버전에서** 공인 DNS fixture의 의미를 유지할 시험 설계와 기존 허용 선언 처리에 대한 별도 범위 결정을 먼저 마련해야 합니다. 예약 주소를 공인으로 취급하거나 scanner 예외를 숨겨 통과시키는 방법은 채택하지 않습니다.

루트/CS 및 후보 규칙, 현재 wiki 인덱스·개발 역할, coord NOTICE를 읽고 전용 NOTICE를 추가했습니다. 기존 소유자 NOTICE는 그대로이며 매니저·보안·통합 소유자에게 HOLD와 read-only 경계를 공유했습니다. 별도 에이전트·integration reservation·tracker 쓰기·prod 쓰기·push·clone·대형 산출물·삭제는 0건입니다. 소유자 회신이나 승인 완료로 주장하지 않습니다.

증거는 [독립 비교 폴더](../../../../scratch/st4f746-fixture-review-20261029/)의 `configured/runs.json`, `configured/*.xml`, `dns-proof.json`, `source-comparison.json`, `final-preservation.json`, `inventory-final.json`, `artifact-size-final.json`입니다. 기존 보호 집합과 이전 검토 전체 및 대상 파일의 중복 제거 보호 수는 910/910 = 100%이며 SHA256 일치입니다. 원래 실패·timeout·성공 XML과 원본/후보 scanner 모두 보존했습니다. private 로그의 원래 주소·접속값은 wiki/채팅에 재게시하지 않습니다.

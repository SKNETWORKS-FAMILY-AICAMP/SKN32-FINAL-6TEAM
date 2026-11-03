---
type: report
title: ST4F-746 원본 스캐너 지적·범위 독립 추적
status: draft
domain: travel
---

2026-10-29 사용자 요청의 남은 보안 관문을 검토했습니다. **릴리스 HOLD 유지**입니다. 제품·스캐너·예외·XML은 고치지 않았고 push·배포·운영 쓰기·자료 삭제·새 clone은 0건입니다.

최초 4파일/10건은 **4/4 = 100% 시험 문맥 확인, 실제 비밀정보 0/10 = 0%**입니다. 한 공인 IPv4를 시험 DNS·가짜 연결 응답에 넣은 9곳과 그 주소를 허용하는 기존 스캐너 선언 1곳입니다. fallback 217/222행은 `_public_addresses`와 `_PinnedHTTPSConnection`을 함께 patch하며 전달 IP를 검증합니다. text-evidence 206행도 DNS와 HTTP/HTTPS 연결을 모두 patch합니다. social-links 231/258행은 DNS 대역, 324/359/393/424행은 가짜 연결을 통한 크기·timeout 시험입니다. scanner 35행은 기존 허용 목록입니다. 키·웹훅·SSH 자격증명이 아니라 오탐입니다. 현재 공인 주소의 DNS 소유권이나 운영 인프라 전체 비밀 부재를 주장하지 않습니다. redacted `fixture-trace.json`에 각 경위와 해시가 있습니다.

후보 HEAD `006268853c0d52c8ff926727f4243230738beb98`의 Git blob과 현재 작업 파일을 각각 검사해도 원본 detector는 **양쪽 동일 4파일/10건**입니다. 이번 아침 복구 변경이 도입한 지적이 아닙니다. 원본 scanner raw SHA `ab4c349e5f614a7d1f25932d354ea9c472fd9471619f4a6832bce8bb9f12ff94`, 후보 `3d3ac186596e0d7ca1a33d1c0f85a9e0f7fc80e532b1dff68f0b01f7642a135d`입니다. 여섯 함수 AST가 6/6 = 100% 동일하며 동작 차이는 후보의 기존 ALLOWED_IPS 전역입니다. 원본 4파일 실패와 후보 0파일 통과가 함께 성립하는 직접 원인입니다. 예외 추가·삭제·승인 처리나 detector 축소를 하지 않았습니다.

| 고정 범위 | 원본 detector | 후보 detector |
|---|---|---|
| 현재 로컬 원본 efeb873a… CS: 추적8999, 텍스트7859, 누락0 | 지적0 | 지적0 |
| 후보00626885… 작업 트리 CS: 추적10871, 텍스트9674, 누락0 | 4파일/10건 | 지적0 |

전체 저장소 추적은 원본17190, 후보19185입니다. 원본에만158, 후보에만2153 경로입니다. CS 범위와 전체 저장소 범위는 다른 분모입니다. 전체 저장소 내용 진단은 최초 원본 단계에서 **248초 후 세션 소유 프로세스만 중지**했으며 완료·통과로 세지 않습니다. 파일을 제외하거나 범위를 줄여 통과를 만들지 않았습니다. CS 검사는 스캐너가 명시한 본래 범위의 별도 비교이고 전체 저장소 통과를 대신하지 않습니다. 두 전체 추적 manifest·해시를 보존했습니다. 현재 로컬 원본은 후보의 최신 원격 통합 기준선이 아닙니다. fetch·원격 통합·원격 최신성 검증은 이번에 하지 않았습니다.

기능 비교는 보존된 수정 전 `recover_for_routes`만 프로세스 메모리로 바꾼 동일 후보 시험 환경에서 14/20 = 70%(6실패), 현재 후보 20/20 = 100%였습니다. 전체 기준선 코드를 되돌린 시험과 구분합니다. 새 XML 두 개는 그대로 보존했습니다.

필수 관문은 아래 실제 종료 결과를 따릅니다. 최초 contract는 기존 PG55495가 중지된 조건에서 240초 timeout이었고 로그에 F가 남았으나 완결 XML은 없습니다. DB 중지만을 실패 원인으로 확정하지 않습니다. 그 뒤 기존 PG/DB를 재사용해 기동했습니다. 새 DB·자료 사본은 만들지 않았습니다. 필수 관문 실패·timeout을 과거 통과 XML로 대체하지 않습니다.

| 관문 | 실제 실행 결과 |
|---|---|
| contract | exit=timeout, 240.05초; tests=미완료, failures=미확정, errors=미확정, skipped=미확정 |
| security | exit=1, 155.84초; tests=125, failures=1, errors=0, skipped=0 |
| dod | exit=0, 118.08초; tests=미완료, failures=미확정, errors=미확정, skipped=미확정 |
| PG-ready contract | exit=0, 20.66초; tests=367, failures=0, errors=0, skipped=0 |
| PG-ready security | exit=0, 26.7초; tests=125, failures=0, errors=0, skipped=0 |
| PG-ready dod | exit=0, 113.63초; tests=미완료, failures=미확정, errors=미확정, skipped=미확정 |

기존 증거·XML·원본/후보 scanner·복구 코드 **857/857 = 100%** SHA256 보존을 확인했습니다. 기존 보호 집합을 중복 합산하지 않습니다. 이전 124/125 실패 XML과 125/125 성공 XML은 모두 원문 그대로이며 새 결과로 덮지 않았습니다.

루트/CS AGENTS·RULE·후보 CLAUDE·현재 wiki 인덱스·역할·Mobility·여행조회/접수 계약을 읽었습니다. 기존 coord80개를 private 스냅숏으로 읽고, 사용자 지시에 따라 전용 NOTICE로 다른 작업자에게 읽기 검토 범위·HOLD·PG 사용을 알렸습니다. 기존 소유자 NOTICE와 다른 작업자 파일은 고치지 않았습니다. 통합 예약·추가 에이전트·tracker 변경은 없습니다.

남은 일은 동일한 최신 통합 판에서 변경 없는 원본 detector의 실패 처리와 필수3관문을 확정하고, 별도의 운영 수락을 수행하는 것입니다. 오탐 판정 자체는 원본 보안 관문 통과 승인이 아닙니다. 분모가 없는 운영 완료율은 만들지 않습니다.

증거: [독립 보안 검토 폴더](../../../../scratch/st4f746-security-gate-20261029/), `scope-manifests.json`, `cs-scope-results.json`, `targeted-baseline-candidate.json`, `fixture-trace.json`, `function-comparison.json`, `gates.json`, `preservation.json`, `inventory.json`, `sizes.json`. raw 시험 로그는 private 증거이며 본문·채팅에 비밀값을 옮기지 않았습니다.

PG-ready 후보 스캐너 필수 관문은 계약367/367·보안125/125·DoD26/26 = 100%, 3/3 = 100%입니다. 원본 detector를 메모리에 연결한 동일 후보 전체 보안은 124/125, exit=1입니다. 파일 열거·시험 범위를 유지했고 scanner 파일은 변경하지 않았습니다. 이 원본 보안 실패 때문에 필수 관문 인정은 2/3 = 66.7%이며 HOLD입니다. 후보 HEAD의 지적4파일은 LF 정규화 후 작업 파일과 4/4 = 100% 동일합니다. PG55495는 본 세션 시작 전 중지였고 제한 시험 후 정상 중지했습니다. DB 원본·기존 XML은 보존합니다. disk inventory와 새 산출물 바이트는 증거 JSON을 따릅니다.

최종 집계: 후보 스캐너 관문3/3=100%(계약367/367·보안125/125·DoD26/26=100%). 원본 detector 전체 보안124/125=99.2%, 필수 인정2/3=66.7%·HOLD입니다. 기존 증거857/857=100% SHA 보존, PG55495 정상 중지·DB 보존, 신규 clone/대형 산출물0건입니다. DoD 재실행은113.63초·26/26=100%입니다. 최초 timeout·실패와 성공 XML은 별도 경로에 모두 보존했습니다.

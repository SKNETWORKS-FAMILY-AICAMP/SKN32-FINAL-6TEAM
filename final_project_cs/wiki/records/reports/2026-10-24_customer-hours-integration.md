---
type: report
title: 고객 운영시간 격리 통합 검증
description: 최신 팀과 날짜위험 패치를 보존하는 고객 항목 한정 운영시간
status: draft
domain: travel
---

# 계약과 진행

10-13 사용자 결정에 따라 공식 관광/활동/식당/Google 정보를 우선합니다. 고객 입력은 `items[n].hours`의 `{open, close, closed_days}` 또는 삭제 `null`입니다. 닫는 값 `24:00`은 허용하고, 시각 역전·중복 요일·전일 휴무·추가 속성은 `invalid_value` 422로 거절합니다. 등록은 해당 항목 `detail.customer_hours`에만 저장합니다. 공용 장소/다른 고객으로 전파하지 않습니다. 장소 교체 시 제거합니다. 화면은 고객 출처를 명시합니다.

기준 팀 `325ba25d88c91ce97da61f2bda635e5888fe3b40` + 검증된 날짜위험 tree `4bbbe3bf671cfaccc49a77247697cad09e6d0dc0`. 신규 격리본 전체 tracked 파일 복제에서 누락 0 확인. 원본과 기존 검증사본 수정 금지. 날짜 deferred/cache, 최신 검색/add-search/check:false 유지.

## 최종 격리 실행

`customer_hours_delivery_01/verified-results.json`에 각 자식 명령의 returncode와 JUnit 실패·오류·skip 수를 기록했습니다. `verified-code-hashes.json`의 같은 코드/시험 해시에서 모든 명령을 다시 실행했습니다. 실행 중 코드 변경 0입니다.

| 검증 | 결과 |
|---|---|
| 고객 운영시간 기능(입력·등록 몸통·수정 저장·422 endpoint·공식 우선·항목 격리·재개·교체·새벽) | 40/40 = 100% |
| 영향 회귀(여행 intake/risk/itinerary checks + unit/intake) | 1030/1030 = 100% |
| architecture + contract + security (`not live and not db`) | 607/607 = 100% |
| 웹 Vitest 전체(SSR 편집 부품·저장 payload·재열기·삭제·SSE 포함) | 1159/1159 = 100% |
| Ruff F/E9 · TypeScript · ESLint · Next build | 각각 exit 0 |

기능 시험은 회귀 묶음에 포함되므로 합산하지 않습니다. 웹 부품은 React SSR로 label/값/공식 출처 입력칸 숨김을 검증했습니다. 입력·저장 payload와 source→view 매핑은 실제 함수로 검증했습니다. 운영앱/서버 기동·실DB·push·배포는 하지 않았습니다.

## 구현 범위

- `_checked` 입력 검증과 항목별 hours claim 저장, 장소 교체 시 제거. `check:false`를 포함한 기존 저장 동작을 유지합니다.
- 공식 관광·활동·식당·대표장소 정보 뒤에만 고객값을 사용합니다. 시각 없는 식당 원장 open/closed 판정도 고객값보다 우선하도록 회귀를 추가했습니다.
- review/SSE는 `hours_state`, `customer_hours`, 고객 출처 문구를 내보냅니다. 등록은 `detail.customer_hours`에만 저장합니다.
- TripStore의 단일/배치 항목 변환에서 읽기용 장소 보기에만 붙입니다. 대체 장소에는 이전 값을 넘기지 않습니다. 새벽 Google open/closed 우선, unknown/unmatched일 때만 고객값 사용, 기존 source failure/deferred 안내는 유지합니다.
- 최신팀의 등록 여행 재편집 경로 `reopen.py`도 필요해 manifest 범위를 명시적으로 넓혔습니다. 재개 claim 보존·hours만 수정/삭제해도 새 버전에 반영하도록 검증했습니다.
- 웹의 기존 「직접 고치기」에서 입력/저장/재열기/지우기( null )를 지원합니다. 종료 00:00→24:00 변환, 공식 출처 입력 숨김, 알 수 없는 운영시간을 「모두 확인」으로 알리지 않는 안내를 포함합니다. 최신 검색/add-search 및 날짜 deferred/cache 코드는 구버전으로 덮지 않았습니다.
- 원본 26후보를 그대로 복사하지 않았습니다. 과거 지도 unknown 전용 필터/바로가기 스타일과 live/DB 시험은 최소 통합에 수입하지 않았으며, 실제 선택은 delivery의 `scope-disposition.json`에 남깁니다.

## RED와 중간 실패의 구분

- `red-validation.log`: hours 미지원 unknown_field 13실패 → 입력검증 GREEN.
- `green-validation-red-integration.log`: 검증 13통과, 고객 사실/등록 경로 6실패 → GREEN.
- `red-review-trip`, `red-dawn-clear`, `red-reflow-unmatched`, `red-ledger-precedence`, `red-reopen`: 각 기능 부재를 실행으로 확인한 RED이며 최종 40시험에 포함됩니다.
- 웹 `red-web-model`, `red-web-ui-collected`, `red-sse`, `red-announcement`의 기능 RED → 최종 GREEN. 최초 `.test.tsx` 선택은 프로젝트 glob이 `.test.ts`라 수집 0이었고 기능 RED로 세지 않았습니다. 별도 `.test.ts` entry가 실제 JSX 시험을 수집합니다.
- `feature-final.log`의 4실패는 뒤늦게 추가한 실제 endpoint 422 시험이 응답의 `detail.error.code`를 `detail.code`로 잘못 읽은 시험 오류입니다. 직전 regression은 그 4건 추가 전 수집이었습니다. 실제 422는 이미 반환됐으며 계약을 확인해 시험 경로를 고친 뒤 feature/regression/gates를 동일 최종 해시로 재실행했습니다.
- `git diff --cached --check 4bbbe3bf671cfaccc49a77247697cad09e6d0dc0`는 올바른 날짜위험 기준 tree에 대해 실행했지만, 추가된 CRLF 줄과 새 시험 파일 EOF 빈 줄을 공백 오류로 잡았습니다. 기준 오류가 아니라 실제 변경줄 형식 문제였으며 해당 추가줄의 CR만 제거하고 EOF 빈 줄만 정리했습니다. 수정 전 검증/patch 증거는 delivery `pre-whitespace/`에 보존하고 같은 최종 파일 해시로 전체 검증을 다시 실행합니다.
- 최초 node_modules 복사는 긴 경로에서 부분 실패했습니다. 확장길이 원본/대상으로 재복사하고 27010파일 SHA256 비교에서 누락/상이 0(장경로 30)을 확인했습니다. 원본 의존성/전역 설정은 변경하지 않았습니다.
- 첫 `run_final.py`는 Node 작업에도 확장경로 cwd를 넘겨 Vite root 정규화 오류 및 Next prerender 실패가 났습니다. 이를 통과로 보고하지 않고 로그를 보존했습니다. Python 보안 스캔에는 확장경로를 유지하고 Node cwd만 일반 Windows 경로로 고친 `run_verified.py`에서 모든 자식 명령/전체 XML이 통과했습니다.

## 안전·검증 한계

- 원본 `C:/_proj/파이널스페이스`와 기존 날짜 검증사본에 쓰지 않았습니다. 신규 사본은 전체 tree+날짜 수정 index를 복제하고 시작 write-tree 동일성을 확인했습니다. 최종 tracked/누락/patch 해시는 delivery manifest에 기록합니다. 보안 detector 자체는 변경하지 않았습니다. CS subtree tracked 10706개 모두 접근 가능, detector 대상 text 9468개입니다. 전체 저장소 tracked 누락 검사는 별도 package에서 수행합니다.
- 실DB 트랜잭션/운영 인증/실Google/운영 브라우저 연결은 확인하지 않았습니다. DB 경계는 기록형 connection 대역, 실제 순수 변환 및 endpoint 함수로 검증했습니다. 결과를 실DB e2e 통과라고 부르지 않습니다.
- `scripts.verify_dod_v11` 전체 실행은 미완료입니다. 하위 subprocess까지 네트워크/실DB 차단을 유지하기 위한 신규 startup guard 작성이 도구 승인 대기 만료로 차단되어 재시도/우회하지 않았습니다. 이 한계는 통과에서 제외하며 부모가 승인된 환경에서 독립 실행해야 합니다.
- 현재 결과는 격리 코드 통합/명시 시험 통과이지 배포 완료가 아닙니다. 부모 독립리뷰와 위 미검증 경계는 남아 있습니다.

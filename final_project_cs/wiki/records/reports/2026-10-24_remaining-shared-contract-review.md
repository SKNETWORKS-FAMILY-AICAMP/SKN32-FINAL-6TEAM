---
type: report
title: 남은 공유 7경로의 최신 계약 대조와 비스트리밍 부하 동원 격리 후보
status: draft
validation_status: partial
---

# 공유 7경로 후속 검토 — 2026-10-24

기준 커밋 `635cb3424c75f6621bf75430766f27083dfaa00e`, tree `b5bfeeaf30426f9183bfba12f800434287d339b7`. 날짜·고객 운영시간 검증본의 전체 18,996개 tracked 파일을 독립 Git 객체 저장소와 raw byte 사본으로 복제·대조했습니다. 기존 원본·공유 검증본은 수정하지 않았고 UUID/historical 패치를 중복 적용하지 않았습니다. 구현 담당은 이번 격리 작업이며 매니저/사용 기능 담당의 독립 검토는 대기입니다.

## B안 4경로는 후속 사용자 결정으로 대체됨

이전 큐의 assemble.py · candidates.py · review.py · web-intakes.md에 `kind_known`과 후보 0개를 넣는 B안은 다시 구현하지 않았습니다. [10-19 후속 기록](2026-10-19_계획읽기_종류모름_처리확인.md) 121~174행은 사용자 결정 “후보 보이고 묻기·직접 고르기”, 서버/화면 구현을 기록하며 142행은 옛 미커밋 B안을 쓰지 않는다고 명시합니다. 현행 [접수 계약](../../external/rest-endpoints/web-intakes.md)의 후보·검색·직접 고르기와 D-025를 유지합니다. 기능이 없다는 이전 큐 판단을 최신 결정 확인 없이 구현하면 후속 결정을 되돌리는 결과가 됩니다. 기존 함수·관련 회귀의 이번 실행 결과는 외부 scratch 인계에 남깁니다. B안 RED/GREEN은 **해당 없음(폐기된 계약)**이며 실제로 실행했다고 주장하지 않습니다.

## 비스트리밍 부하 동원

Settings의 `llm_overflow_max_inflight`/`llm_overflow_hedge_seconds`는 기본 0입니다. 최신 FailoverChat에 busy 지연·API 우회 및 slow 병렬 후보를 좁게 추가했습니다. max_inflight는 hard semaphore가 아니라 **우회 기준**이며 다른 경로가 실패하면 원래 로컬로 돌아가므로 진행 수가 기준을 넘을 수 있습니다(10-15 사용자 계약). API 예산 예약은 caller 스레드, worker마다 contextvars 사본, inflight 반납은 실제 종료 때입니다. caller는 검증 통과 winner만 기록하고 loser는 health만 반영합니다. 스트리밍·이미지·예열은 동원하지 않으며 기존 동작을 유지합니다.

TDD: 설정 누락 RED→배선 GREEN, busy 큐 대기 assertion RED→우회 통과, hedge 부재 RED→병렬 응답 통과. 추가 negative probe로 deferred local이 API 예산을 두 번 예약하는 문제(2!=1)와 loser가 winner 반환 뒤 503 재시도하는 문제(2!=1)를 확인하고 각각 최소 수정·재시험했습니다. 모든 실패 원문/XML은 scratch에 보존했습니다.

## 미통과와 승인 경계

`busy-green`은 파일명일 뿐 통과가 아닙니다. 실제 65개 중 61 통과·4 실패였습니다. 변경 전 기준판의 기존 63개 중 같은 4개가 같은 `service/socket bind denied`로 실패했고, 63개 공통 test id의 결과 차이는 0입니다. 네 시험은 루프백 HTTP 서버를 만들며 현재 사용자 지시의 서비스 기동 금지와 충돌합니다. 시험을 빼거나 안전 가드를 풀지 않았습니다. 최종 확장 파일 전체는 73개 중 69 통과·동일 4개 차단이며, 과거 65개 모두를 포함합니다. 이 결과는 전체 GREEN이 아닙니다.

실모델·실API·실DB·서비스 기동·배포·운영 설정 변경·push는 수행하지 않았습니다. 이미 진행 중인 transport는 강제로 취소하지 못하며 timeout까지 계속될 수 있습니다. winner 확정 뒤 wrapper 재시도는 막지만 진행 중 SDK/HTTP 내부 처리를 물리적으로 취소한다는 보장은 없습니다. 운영 활성화 전 독립 동시성·예산 provider·transport cancellation 검토와 허용된 HTTP 회귀 실행이 필요합니다. 이 후보는 병합·운영 승인 완료가 아닙니다.

전체 실행 로그·patch·manifest·원본 보존 증거·최종 보안 관문 결과는 profile scratch `remaining_shared_implementation/` 인계를 정본으로 사용합니다. 탐색 one-liner의 SyntaxError와 최초 Windows tar extractall 오류는 시험 실패와 구분해 보존했고, 정상 멀티라인 script와 개별 Path 추출로 복구했습니다.

## 최종 실행 결과

- 계약·보안·구조 관문: 후보 **607/607 = 100%**, 같은 가드·범위의 기준판도 607/607. 최초 양쪽 3개 실패는 `git check-ignore` 두 시험·tracked 전체 보안검사의 상대경로 subprocess 차단이었습니다. bare `git`만 검증된 MinGit 절대경로로 고정한 실행 도구 수정이며 제품이나 검사 기대값은 바꾸지 않았습니다. 후보 CS tracked 10,709개 중 텍스트 9,471/9,471개를 extended path로 스캔, 누락 0. 기준은 텍스트 9,470/9,470개, 후보의 추가 보고서 1개 차이입니다.
- 최종 관련 회귀: 후보 **319/323 = 98.8%**, 실패 4·오류/건너뜀 0. 기준판은 309/313, 같은 네 루프백 소켓 시험 실패. 공통 313개 test id의 결과 변경 0, 추가10개 통과. 최초 65개도 최종 확장 범위에 모두 포함하며 누락하지 않았습니다.
- 날짜·고객시간·현재 못찾은 장소 카드·종류 먼저 판정·숙소/식당 후보·streaming·모델 경로 등 보존 묶음은 250/250(최종323에 포함하므로 합산하지 않음). 새 부하 동원 회귀는 10/10이며 같은 최종323의 부분집합입니다.
- ruff F/E9, 새 추가줄 보안 패턴검사, 이번 follow-up patch의 기준 커밋 대비 공백검사는 통과했습니다. 이전 날짜 패치의 CRLF 공백 보류는 별개로 남아 있습니다.
- 안전 가드 자체의 network/DB/bind/shell 거부·허용 MinGit 조회/정확한 ignore exit·Git 변경 거부 3/3 통과. 네 HTTP 시험을 살리려고 서비스 기동 금지나 보안 범위를 완화하지 않았습니다.

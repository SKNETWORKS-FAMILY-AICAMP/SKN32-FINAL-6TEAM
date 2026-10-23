# guguroute wiki 검토 · 사용자 지시 반영 상태

갱신 2026-10-11T22:40:55+09:00. 댓글 9/9 지시·문서 반영, 대상 6/6 항목 수정. 제품 코드·배포 완료 집계가 아닙니다.

[댓글별 상태·설명 HTML](wiki-review-v2.html#comment-status)

## 책임 용어

| 이름 | 역할 |
|---|---|
| 분류 에이전트 | 목표 계약의 판단 주체. 질의·계획·상황·사용자 성향으로 담당·순서·우선순위를 정합니다. 현재 라벨 분류만으로 이 전체 역할의 구현 완료를 증명하지 않습니다. |
| Controller | 현재 코드의 공통 실행 장치. 분류 모델 자체가 아니며 등록된 담당 실행·검증·반영을 진행합니다. |
| TeamRegistry | 등록·활성 정보를 대조해 담당을 찾고 실행 가능한지 확인합니다. 고객 성향을 판단하는 모델이 아닙니다. |
| TeamExecutorPort | 에이전트 팀 실행 계약. 실행 구현이 등록된 팀을 호출합니다. |
| Activity·Dining·Mobility 에이전트 팀 | 배정된 활동·식당·이동 업무의 계산·제안 담당. 다른 팀 전체의 순서 결정 주체가 아닙니다. |
| 모니터링 툴의 여행 상태 점검 | 외부 자료로 일정 문제를 발견합니다. 실행 간격은 설정값입니다. |
| 현재 WatchBatch·watch_planners | 현재 코드의 여러 문제 계산 처리와 계산 등록 지점. 고정 순서는 목표 계약과 다른 구현 상태로 기록합니다. |
| 운영자 웹 앱·운영 모니터링 화면 | 개발·QA의 정책 설정과 오류·지연 사후 분석 도구. 상주 상담원 업무 화면을 뜻하지 않습니다. |

## W01 · 현재 사양은 wiki, 계획서는 안내 자료

**기존 문서 정정 반영 완료.**

W01 문서 정정 완료 현재 사양은 wiki, 계획서는 안내 자료 루트·cs 작업 규칙과 문서 입구를 wiki 정본으로 통일했습니다. 옛 계획 기록은 보존했습니다. AGENTS.md · index.md · index.md · AGENTS.md · CLAUDE.md · RULE.md · README.md

[실제 반영·검증 근거](wiki-review-v6.html#W01). 이전 제안은 백업에 보존했습니다.

## W02 · 고객 웹·개인 AI 연동·공유 계획서의 역할 명시

수정 계획 기본안 채택; wiki·코드 적용 상태와 별개

“별도 접점”을 지우고, 고객이 이용하는 화면과 API의 역할을 적습니다.

- A · 현재 웹 기능까지 범위에 포함 **확정 선택** — 웹 입력·일정 구성·검증·수정·감시 설정, 개인 AI 연동, 공유 계획서 열람을 함께 설명합니다.
- B · 웹은 입력·검토 중심 — 최초 자동 일정 구성은 시험 기능으로 표시합니다. 현재 기능을 제품 약속에서 좁히는 선택입니다.
- C · 개인 AI 중심으로 제공 — 개인 AI가 일정을 만들고 웹은 검토·관리만 합니다. 현재 웹 일정 구성 기능의 역할을 축소합니다.

반영·후속 작업:

1. scope·positioning·system-context의 “자체 앱 없음/계획 생성은 우리 일 아님”을 현재 웹 흐름에 맞게 바꿉니다.
2. 범위표에 고객 웹 화면, 개인 AI 연동(API/MCP), 공유 계획서 링크를 적습니다. 모두 같은 여행 상태를 사용하며 독립 앱 3개를 만들자는 뜻이 아닙니다.
3. 최초 일정 구성과 여행 중 재계획을 분리하고 지원 지역·자료·검증 수준을 각 기능에 연결합니다.

정본·대상:

- [wiki/product/scope.md](C:/Users/playdata2/Documents/final_workspace/wiki/product/scope.md)
- [wiki/product/positioning.md](C:/Users/playdata2/Documents/final_workspace/wiki/product/positioning.md)
- [wiki/architecture/system-context.md](C:/Users/playdata2/Documents/final_workspace/wiki/architecture/system-context.md)
- [final_project_cs/wiki/external/rest-endpoints.md](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/external/rest-endpoints.md)

## W03 · 항로 지킴이 켜짐: 검증한 변경을 자동 적용

수정 계획 기본안 채택; wiki·코드 적용 상태와 별개

항로 지킴이를 켜면 변경 필요 여부를 판단하고, 검증한 대체안을 적용한 결과를 제시합니다.

- A · 현재 모드와 예외를 한 표로 정리 **확정 선택** — 켜짐은 자동 적용, 꺼짐은 변경 제안. 고정 일정·재난은 기존 별도 규칙을 유지합니다.
- B · 조건별 자동 변경 범위 설정 — 날씨·휴무·이동별로 허용 범위를 고객이 고릅니다. 설정과 검증 비용이 늘어납니다.
- C · 여행 등록 때 변경 권한 요약 — 고객이 등록할 때 자동 변경 범위를 확인합니다. 기존 여행의 재확인 절차가 추가됩니다.

반영·후속 작업:

1. 고객 설정 명칭을 항로 지킴이로 통일하고, 옛 설문 값 replace/ask_first는 구현 대응표에만 둡니다.
2. 일반 사건은 켜짐=재계획→재검증→새 일정 저장→알림, 꺼짐=제안→고객 선택으로 적습니다.
3. 고정 일정은 확인 후 변경, 재난은 일정 정지 후 고객이 명시적으로 재개, 업체 예약·결제는 자동 실행 범위 밖이라고 적습니다.
4. 설문 미응답 여행의 guardian 표시·auto_on_disruption·pending.decide 경로를 대조합니다. 코드 버그로 단정하지 않고 동작 검사 항목으로 등록합니다.
5. 미응답은 꺼짐(먼저 확인)을 기본안으로 정하고 표시·판정·알림이 같은 값을 읽도록 맞춥니다. 고객이 직접 켠 기록은 유지합니다. 적용 전 실제 호출 경로와 기존 데이터 호환성을 검사합니다.
6. REST 재난 재개 절의 “자정에 자동 해제” 문장은 고객 명시 재개 규칙으로 교체합니다.
7. 재난 정지의 우선순위는 일반 자동 변경보다 높습니다. 여행 종료 후 남은 항목이 없으면 감시·재안내를 끝내고 정지 이력만 보존합니다. 이것은 자동 재개가 아닙니다.

정본·대상:

- [wiki/product/positioning.md](C:/Users/playdata2/Documents/final_workspace/wiki/product/positioning.md)
- [wiki/product/scope.md](C:/Users/playdata2/Documents/final_workspace/wiki/product/scope.md)
- [wiki/decisions/D-020-trip-survey-and-ask-first.md](C:/Users/playdata2/Documents/final_workspace/wiki/decisions/D-020-trip-survey-and-ask-first.md)
- [final_project_cs/wiki/external/rest-endpoints.md](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/external/rest-endpoints.md)

## W04 · 개인 AI를 로그인·동의로 연결하고 여행 권한 검사 공유

B안 선택 반영 완료 · 개인 AI OAuth 구현·연결 검증 남음

개인 AI의 guguroute 연결은 키 복사 대신 로그인·권한 동의 방식까지 이번 구현 범위에 포함합니다. 선택·wiki 반영은 완료했지만 OAuth 구현 완료로 표시하지 않습니다.

이번 사용자 지시의 문서 반영은 완료했습니다. 새 코드 구현·배포 완료는 별도입니다.

- A · 기존 인증 유지 + 공통 권한 검사 — 웹은 쿠키, 개인 AI는 에이전트 키, 공유 링크는 읽기 전용입니다. OAuth는 다음 단계로 둡니다.
- B · 개인 AI OAuth까지 이번에 구현 **확정 선택** — 키 복사 대신 로그인·동의로 연결합니다. 코드 교환·만료·폐기 검사까지 구현 범위가 커집니다.
- C · 웹·공유 링크 먼저 출시 — 개인 AI 연결은 준비 기능으로 표시합니다. 개발량은 줄지만 기존 개인 AI 제공 범위를 늦춥니다.

반영·후속 작업:

1. B안 OAuth를 이번 구현 범위로 기록합니다.
2. 로그인·동의·코드 교환·PKCE·권한·소유자·만료·폐기·실제 MCP 연결을 구현·검증합니다.
3. 웹 로그인·에이전트 키와 개인 AI OAuth의 완료 상태를 구분합니다.

정본·대상:

- [final_project_cs/wiki/external/rest-endpoints.md](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/external/rest-endpoints.md)
- [final_project_cs/wiki/decisions/D-CS-011-browser-session-cookie.md](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/decisions/D-CS-011-browser-session-cookie.md)
- [final_project_cs/wiki/decisions/D-CS-012-agent-auth-claude-style.md](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/decisions/D-CS-012-agent-auth-claude-style.md)
- [final_project_cs/wiki/external/web-auth-transfer.md](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/external/web-auth-transfer.md)
- [wiki/architecture/system-context.md](C:/Users/playdata2/Documents/final_workspace/wiki/architecture/system-context.md)
- [final_project_cs/app/domains/travel_ops/components/itinerary/plan_link.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/app/domains/travel_ops/components/itinerary/plan_link.py)
- [final_project_cs/app/domains/travel_ops/entry/trip_api.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/app/domains/travel_ops/entry/trip_api.py)
- [final_project_cs/app/domains/travel_ops/modules/web_account/web_cookie.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/app/domains/travel_ops/modules/web_account/web_cookie.py)

## W05 · 자동 처리·고객 보완 입력·개발자/QA 사후 분석

수정 계획 기본안 채택; wiki·코드 적용 상태와 별개

실시간 상담원 인계를 없애고, 자동 복구와 고객의 직접 해결을 지원하면서 결함 자료를 축적합니다.

- A · 기존 DB에 결함·영향 기록 + 사후 분석 **확정 선택** — 현재 규모에 맞게 시작합니다. 개발자·QA 조회는 별도 내부 권한으로 제한합니다.
- B · 관측 도구에 결함 집계 위임 — 중복 오류와 추적을 도구가 묶습니다. 외부 전송 범위·보존 비용·영향 고객 연결을 추가 설계해야 합니다.
- C · 처음부터 전용 수집 작업자 분리 — 오류가 많아도 고객 처리와 자원을 분리합니다. 대기열·재전송·누락 검사 운영이 늘어납니다.

반영·후속 작업:

1. 실시간 상담원 대기·수동 처리 완료 기준을 제거합니다. 자동 재조회·대체 자료·재분류 후에도 실패하면 원인을 구분합니다.
2. 고객이 고칠 수 있는 장소명·주소·날짜 등만 입력 요청합니다. 검증된 후보가 있으면 추천순으로 최대 3개와 추천 이유를 제시하고, 없으면 직접 입력 필드를 제공합니다. 외부 API 장애를 고객 입력 탓으로 돌리지 않습니다.
3. 장소 미매칭, 처리 오류, 고객 건의를 별도 유형으로 저장합니다. 오류 발생 기록과 동일 결함 묶음, 영향 고객 연결을 분리합니다. 고객 건의와 장소 입력은 검증 전 공용 자료에 자동 반영하지 않습니다.
4. 개발자·QA는 결함 유형·재현 조건·영향 고객·해결 판본을 사후 조회합니다. 고객 요청을 대신 처리하거나 일정 DB를 직접 고치는 권한은 부여하지 않습니다.
5. 대기열 지연·DB 기록 지연이 기준을 넘으면 수집 작업자를 분리하고, 동일 결함은 집계·표본 상세로 저장합니다. 영향 고객 연결과 발생 건수는 표본으로 줄이지 않습니다.
6. 수집 이벤트에는 발생 고유 ID·배포 판본·정책 판본·상관 식별자를 기록합니다. 에이전트 팀은 도메인 결과를 반환하고 공통 실행 경로가 구조화한 기록을 저장합니다. 상담원 인계 의미를 없애려고 Case 상태 이름을 이번 문서 작업에서 바로 바꾸지는 않습니다.
7. 배경 감시와 개인 AI 경로에서도 처리 실패 결과가 조용히 사라지지 않게 합니다. 고객 안내는 실패/복구의 상태 전환과 여행 범위로 중복을 막습니다.
8. 실제 support 화면의 “운영팀 답변 대기”와 문의 응답 타입을 건의·문제 신고 접수로 개편합니다. 접수 성공은 기록 완료만 뜻하고 고객 문제 해결을 뜻하지 않습니다. 계정 차단 문구의 “운영자에게 문의”도 자동 안내·건의 기록 경로로 바꿉니다.
9. 고객의 업무 처리 결과는 완료/입력 필요/변경 보류/처리 불가로 설명하고, 내부 escalated가 상담원 대기라는 뜻으로 화면에 번역되지 않게 응답 대응표를 만듭니다. 상태기계 변경이 필요하면 계약 판올림과 이관을 별도 작업으로 수행합니다.
10. 진단 DB 저장 실패는 제한된 마스킹 이벤트를 로컬 영속 대기 파일에 보관하고 복구 후 같은 발생 ID로 전송합니다. 용량 상한과 유실 지표를 둡니다. DB와 대기 파일 모두 실패하면 내부 관측에 수집 저하를 표시하고 영속 기록을 보장했다고 세지 않습니다.
11. 서비스 설정·배포·결함 분석은 개발자의 유지보수 역할입니다. 고객 요청마다 운영관리자 승인을 기다리는 구조를 뜻하지 않으며, 고객 여행 편집 권한과 분리합니다.

정본·대상:

- [wiki/delivery/dod.md](C:/Users/playdata2/Documents/final_workspace/wiki/delivery/dod.md)
- [final_project_cs/wiki/decisions/D-CS-014-routing-reroute.md](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/decisions/D-CS-014-routing-reroute.md)
- [final_project_cs/wiki/external/rest-endpoints.md](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/external/rest-endpoints.md)
- [wiki/architecture/notifications.md](C:/Users/playdata2/Documents/final_workspace/wiki/architecture/notifications.md)
- [final_project_cs/frontend/apps/web/src/features/support/support.tsx](C:/Users/playdata2/Documents/final_workspace/final_project_cs/frontend/apps/web/src/features/support/support.tsx)
- [final_project_cs/frontend/apps/web/src/features/support/client.ts](C:/Users/playdata2/Documents/final_workspace/final_project_cs/frontend/apps/web/src/features/support/client.ts)
- [final_project_cs/app/domains/travel_ops/modules/web_account/admin_customer_api.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/app/domains/travel_ops/modules/web_account/admin_customer_api.py)
- [final_project_cs/app/domains/travel_ops/modules/web_account/web_cookie.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/app/domains/travel_ops/modules/web_account/web_cookie.py)

## W06 · 조회에 실패한 작업만 보류하고 독립 기능 유지

A안 선택 반영 완료 · 자동 복구·고객 안내 인수 검증 남음

외부 자료 조회가 실패하면 그 자료가 필요한 작업만 보류합니다. 기존 일정과 독립적으로 검증할 수 있는 기능은 유지합니다. 상주 상담원 인계는 만들지 않습니다.

이번 사용자 지시의 문서 반영은 완료했습니다. 새 코드 구현·배포 완료는 별도입니다.

- A · 기능·요청 단위 장애 격리 **확정 선택** — 실패한 조회와 변경만 멈추고 기존 일정·정상 기능은 유지합니다. 현재 구조에 가장 적합합니다.
- B · 해당 여행의 자동 변경 전체 보류 — 여행 일부의 필수 자료가 빠지면 그 여행의 변경을 모두 보류합니다. 정상 항목도 기다리게 됩니다.
- C · 장애 소스를 쓰는 자동 변경 전체 중지 — 장애 소스에 의존하는 모든 여행의 변경을 잠시 중지합니다. 광범위한 소스 장애 대응에는 단순하지만 영향이 큽니다.

반영·후속 작업:

1. D-018을 그대로 승인하지 않고, 기동 필수 기반·외부 조회·고객 입력 부족·안전 사건의 처리표로 다시 작성합니다. “사람 인계”를 자동 복구/고객 안내/결함 기록으로 교체합니다.
2. DB·인증·테넌트 격리 같은 필수 기반을 보장할 수 없으면 해당 앱/기능의 준비 상태를 실패로 처리합니다. 외부 소스 하나가 불통인 것과 구분합니다.
3. 일시 오류는 시간·횟수 예산 안에서 재시도하고 대체 자료를 사용합니다. 연속 실패 소스는 회로 차단(잠시 호출을 쉬고 시험 요청으로 복구 확인)을 적용합니다. 값·영업·안전을 추정해 정상 판정하지 않습니다.
4. 자료가 없으면 의존하는 변경을 저장하지 않고 기존 일정과 마지막 확인 시각·검증 불가 상태를 표시합니다. 영향 항목 안내는 상태 전환 때 보내고 반복 오류 알림을 합칩니다.
5. 복구 후 최신 일정 판·자료 유효시간·고객 모드를 다시 확인하고 재검증합니다. 낡은 제안을 그대로 재실행하지 않으며 다른 여행·항목은 계속 처리합니다.
6. 실패 중인 조회의 재시도는 지수 간격과 무작위 분산을 사용하되 기존 설정·호출 예산에 상한을 둡니다. 인증 거부·잘못된 입력은 같은 조건으로 자동 재시도하지 않습니다.
7. 알림 중복 키는 여행·장애 회차·상태 전환 종류를 포함합니다. 장애 자료가 새로 조회되었다는 이유만으로 기존 재난 정지를 해제하지 않습니다.
8. D-017의 “점검 소스 실패는 알리지 않는다”를 명시적으로 대체합니다. 일시 재시도 중에는 알림을 만들지 않고, 주자료·대체 자료가 시간/횟수 예산 안에서 모두 실패해 영향을 확정했을 때 여행별 장애 회차에 한 번, 정상 재검증으로 회복했을 때 한 번 안내합니다.
9. 설정 오류로 필수 기반을 보장할 수 없는 기동 실패와 외부 조회 하나의 실패를 분리합니다. 불확실한 상태에서 접근 권한을 완화하거나 쓰기를 재개하지 않습니다.

정본·대상:

- [wiki/decisions/D-018-decision15-stop-paths.md](C:/Users/playdata2/Documents/final_workspace/wiki/decisions/D-018-decision15-stop-paths.md)
- [wiki/architecture/notifications.md](C:/Users/playdata2/Documents/final_workspace/wiki/architecture/notifications.md)
- [wiki/decisions/D-017-watch-cadence-golden-time.md](C:/Users/playdata2/Documents/final_workspace/wiki/decisions/D-017-watch-cadence-golden-time.md)

## W07 · 모니터링 툴의 실행 간격과 자료 최신성 구분

용어 수정 반영 완료 · 자료 최신성 실측 남음

기능 이름은 모니터링 툴입니다. “3분 감시”를 기능 이름처럼 쓰지 않습니다. 실행 간격·원본 게시 지연·캐시 유지시간·실제 감지 지연을 구분합니다.

이번 사용자 지시의 문서 반영은 완료했습니다. 새 코드 구현·배포 완료는 별도입니다.

- A · 자료별 지연표 작성 **확정 선택** — 게시 지연·수집 간격·캐시·판정·통지를 각각 기록합니다.
- B · 안전 자료만 우선 새로 수집 — 감지 지연은 줄지만 호출 한도와 비용 검증이 먼저 필요합니다.
- C · 전체 자료 수집 주기 통일 — 관리하기 쉽지만 소스별 제한을 만족시키기 어렵습니다.

반영·후속 작업:

1. D-017에 소스별 게시/수집/캐시/판정/통지 시간을 한 표로 추가합니다.
2. “최대 3분”을 실제 경로별 상한 또는 미측정으로 교체하고 20분 캐시와 모순을 제거합니다.

정본·대상:

- [wiki/decisions/D-017-watch-cadence-golden-time.md](C:/Users/playdata2/Documents/final_workspace/wiki/decisions/D-017-watch-cadence-golden-time.md)

## W08 · 분류 에이전트가 담당·순서·우선순위를 결정

책임 정정 반영 완료 · 현재 코드와 요구의 차이 확인

고객 질의·계획서·상황·사용자 성향을 바탕으로 분류 에이전트가 담당 팀과 처리 순서·우선순위를 정한다는 지시를 반영했습니다. Activity에 다른 팀의 조정을 맡긴 추천과 Controller를 새 판단 주체로 삼은 제안은 철회합니다.

이번 사용자 지시의 문서 반영은 완료했습니다. 새 코드 구현·배포 완료는 별도입니다.

- A · Activity 조정 유지 — 기각 — 현재 코드의 경로 설명일 뿐 채택 설계가 아닙니다. 다른 팀의 우선순위는 Activity에 맡기지 않습니다.
- B · 문제마다 별도 사건으로 처리 — 현재의 함께 처리하는 결정을 바꾸는 대안입니다. 일정 버전·알림이 여러 번 생길 수 있습니다.
- C · 분류 에이전트가 담당·순서·우선순위 결정 — 사용자 확정 **확정 선택** — Controller는 검증·실행 장치입니다. 사용자 성향과 현재 상황을 반영한 처리 계획 계약·코드·시험을 맞춥니다.

반영·후속 작업:

1. 분류 에이전트를 판단 주체로 계약에 명시하고 Activity 조정·Controller 새 판단 주체 제안을 철회합니다.
2. 현재 라벨 분류·단일 담당 선택·고정 순서 코드를 목표 처리 계획과 구분합니다.
3. 질의·계획·상황·사용자 성향으로 담당·순서·우선순위·이유·의존 관계를 반환하는 계약을 정의합니다.
4. 실행 장치가 등록 팀·권한·도구/시간 예산·순환·동시 편집·중복 방지 경계를 검증합니다.
5. 각 팀은 배정 업무를 계산하며 전체 일정 검증을 통과한 허용 변경만 적용합니다.

정본·대상:

- [wiki/decisions/D-017-watch-cadence-golden-time.md](C:/Users/playdata2/Documents/final_workspace/wiki/decisions/D-017-watch-cadence-golden-time.md)
- [final_project_cs/wiki/decisions/D-CS-013-domain-folder-layout.md](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/decisions/D-CS-013-domain-folder-layout.md)
- [final_project_cs/wiki/teams/composition.md](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/teams/composition.md)

## W09 · 무료 자료 우선·검증 불가 표시와 운영 설정

A안·운영자 웹 앱 설정 요구 반영 완료 · 구현 남음

무료 자료를 우선 사용하고 확인하지 못한 영업 상태는 검증 불가로 표시합니다. 운영자 웹 앱에서 자료 선택 정책·호출 예산·확인 주기를 바꿀 수 있게 하는 요구를 추가했습니다. 설정 화면·저장·실제 조회 연결은 아직 구현 완료가 아닙니다.

이번 사용자 지시의 문서 반영은 완료했습니다. 새 코드 구현·배포 완료는 별도입니다.

- A · 무료 자료 우선 + 검증 불가 표시 **확정 선택** — 낮 조회 가능한 자료와 한계를 적습니다. 구글 호출 제한을 유지합니다.
- B · 필요한 장소만 유료 재조회 — 휴무 확인 범위를 넓히지만 고객·여행별 비용 상한을 다시 정해야 합니다.
- C · 고객 휴무 신고 중심 — 외부 조회 비용은 줄지만 선제 감지 범위를 축소합니다.

반영·후속 작업:

1. 무료 자료 우선·검증 불가 표시를 현재 정책에 반영합니다.
2. 운영자 웹 앱의 장소 영업 상태 확인 설정·저장·조회 연결을 구현합니다.
3. 권한·변경 이유·설정 판본·호출 예산·새벽 제한·복구를 검사합니다.

정본·대상:

- [wiki/decisions/D-020-trip-survey-and-ask-first.md](C:/Users/playdata2/Documents/final_workspace/wiki/decisions/D-020-trip-survey-and-ask-first.md)
- [final_project_cs/wiki/decisions/D-CS-009-daytime-closure-detection.md](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/decisions/D-CS-009-daytime-closure-detection.md)
- [final_project_cs/wiki/decisions/D-CS-010-google-calls-in-dawn-batch-only.md](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/decisions/D-CS-010-google-calls-in-dawn-batch-only.md)

## W10 · 평가 첫 화면을 여행 평가로 교체

**기존 문서 정정 반영 완료.**

W10 문서 정정 완료 평가 첫 화면을 여행 평가로 교체 평가 입구·골든·절차 안내를 여행 자료로 연결했습니다. 쇼핑몰 수치·표본 분석은 기록으로 보존했습니다. index.md

[실제 반영·검증 근거](wiki-review-v6.html#W10). 이전 제안은 백업에 보존했습니다.

## W11 · v11은 보존하고 wiki 정리 후 v12 새로 작성

v11 수정 제외 반영 완료 · 전체 정리 후 v12 신규 작성 대기

W11은 계획서 v11 자체가 아니라 현재 출시 검증 문서의 문제를 가리켰습니다. v11은 현재 기준으로 사용하지 않고 과거 원문으로 보존합니다. wiki·구현 차이를 정리한 뒤 v12 안내서를 새로 작성하며 v12 완료로 표시하지 않습니다.

이번 사용자 지시의 문서 반영은 완료했습니다. 새 코드 구현·배포 완료는 별도입니다.

- A · 요구별 검증표 재작성 — 요구 ID·검사·결과·미구현 상태를 연결합니다.
- B · 고객 시나리오별 출시표 — 설명은 쉽지만 공통 보안·계약 조건이 중복됩니다.
- C · 기존 번호 유지 + 대응표 — 이력 연결은 쉽지만 옛 번호와 현재 의미를 계속 함께 관리합니다.

반영·후속 작업:

1. v11 원문은 보존하고 현재 기준에서 제외합니다.
2. wiki·구현·검증 정리가 끝난 뒤 v12 안내서를 새로 씁니다.
3. 현재 출시 검증과 안내서 판올림을 구분합니다.

정본·대상:

- [wiki/delivery/release-gate.md](C:/Users/playdata2/Documents/final_workspace/wiki/delivery/release-gate.md)
- [wiki/delivery/dod.md](C:/Users/playdata2/Documents/final_workspace/wiki/delivery/dod.md)
- [wiki/decisions/D-023-no-commerce-assets-in-use.md](C:/Users/playdata2/Documents/final_workspace/wiki/decisions/D-023-no-commerce-assets-in-use.md)

## W12 · 에이전트 팀의 자료 조회는 허용된 도구로 통제

수정 계획 기본안 채택; wiki·코드 적용 상태와 별개

에이전트 팀은 허용된 도구로 조회하고, 변경 제안은 Controller가 검증한 뒤 등록된 적용기로 실행합니다.

- A · 통제된 읽기 도구 허용 **확정 선택** — 허용 목록·예산·tenant 격리·근거 반환을 도구 실행 경로에서 강제합니다.
- B · 공통 실행 계층에서 모든 자료 선조회 — 에이전트 팀은 받은 입력만 읽습니다. 도메인을 모르는 공통 실행 계층에 여행별 조회 순서를 넣게 되는 문제가 있습니다.
- C · 전용 자료 조회 서비스 분리 — 도구 정책을 모으기 쉽지만 서비스·호출 계약이 추가됩니다.

반영·후속 작업:

1. 에이전트 팀 경계·불변식 문서의 “읽기 전면 금지”를 자료 조회/외부 변경/내부 상태 변경 표로 바꿉니다.
2. 에이전트 팀은 허용된 Port로 조회하고 제안만 반환합니다. 인증 문맥·예산·근거를 강제하며 Controller에 여행별 계산을 넣지 않습니다.

정본·대상:

- [final_project_cs/wiki/teams/team-boundary.md](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/teams/team-boundary.md)
- [final_project_cs/wiki/quality/invariants.md](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/quality/invariants.md)

## W13 · 쇼핑몰 시험 재료를 여행 재료로 대체

**기존 문서 정정 반영 완료.**

W13 요청 범위 반영 W13 · 과거 쇼핑몰 자산의 현재 실행 차단 여행 정책·요청·권한 시험으로 교체하고 과거 원문을 보존했습니다. 새 DB에서 옛5표 재생성을 차단했습니다. 기존 업무DB 삭제·공개 배포는 하지 않았습니다. 수정 결과·근거·남은 범위 보기

[실제 반영·검증 근거](wiki-review-v6.html#W13). 이전 제안은 백업에 보존했습니다.

## W14 · DB 안내는 현재 논리 구조와 환경별 적용 기록으로

**기존 문서 정정 반영 완료.**

W14 문서 정정 완료 DB 안내는 현재 논리 구조와 환경별 적용 기록으로 여행 데이터 안내·스키마 안내·SQL 적용 안내를 다시 썼습니다. 실행 대상 89개·보류 1개를 자동 집계하며 DB 적용 수와 구분했습니다. index.md · index.md · migrations.md

[실제 반영·검증 근거](wiki-review-v6.html#W14). 이전 제안은 백업에 보존했습니다.

## W15 · 학습·평가·서비스 채택 판정 분리

**기존 문서 정정 반영 완료.**

W15 문서 정정 완료 학습·평가·서비스 채택 판정 분리 현재 학습 안내를 cs 모델 평가 정본으로 연결하고, 과거 Qwen 쇼핑몰 학습 실험을 records에 분리했습니다. finetuning.md

[실제 반영·검증 근거](wiki-review-v6.html#W15). 이전 제안은 백업에 보존했습니다.

## W16 · 기능별 책임과 공유 계약 변경 절차 명시

**기존 문서 정정 반영 완료.**

W16 · 문서 보완 완료 · 2026-10-11 재검토 기능별 책임과 공유 계약 변경 절차 기능별 구현·검토 책임과 공유 계약 변경 절차를 보완했습니다. 팀원 배치는 README를 유지하고, 상시 인증·DB 전담 인명은 미확정으로 표시했습니다. 현재 코드·시험 경로와 고객 여행 웹 위치도 대조했습니다. 기능 책임·검토 절차 · 현재 코드·시험 경로 · 재검토 보고서 실제 반영 내용·검사·백업 보기 등록·구조 시험 10/10 통과. 상시 전담 인명 확정·운영 반영 완료를 뜻하지 않습니다. 이 항목은 최신 재검토 결과이며 나머지 항목의 확인 시점은 원래 검토판을 따릅니다.

[실제 반영·검증 근거](wiki-review-v6.html#W16). 이전 제안은 백업에 보존했습니다.

## W17 · 현재 제출 계획과 과거 주차표 분리

**기존 문서 정정 반영 완료.**

W17 문서 정정 완료 현재 제출 계획과 과거 주차표 분리 오늘 표시와 옛 쇼핑몰 작업표를 분리했습니다. 기존 최종 발표일과 문서 정비 순서만 남겼으며 새 마감일은 만들지 않았습니다. timeline.md

[실제 반영·검증 근거](wiki-review-v6.html#W17). 이전 제안은 백업에 보존했습니다.

## W18 · 환경별 앱·DB·감시·모델 상태 분리

**기존 문서 정정 반영 완료.**

W18 요청 범위 반영 W18 · 환경별 상시 운영 점검·복구 절차 공식 Docker·Google SRE 자료와 현재 코드로 운영 절차를 개정했습니다. 환경별 과거 관측·이번 미확인을 구분했습니다. 새 상시 계측·준비 검사·운영 배포 완료를 뜻하지 않습니다. 수정 결과·근거·남은 범위 보기

[실제 반영·검증 근거](wiki-review-v6.html#W18). 이전 제안은 백업에 보존했습니다.

## W19 · datasets 전체 Git 제외 규칙으로 안내 통일

**기존 문서 정정 반영 완료.**

W19 문서 정정 완료 datasets 전체 Git 제외 규칙으로 안내 통일 datasets 전체 Git 제외와 README·REPORT 우선 규칙으로 수정했습니다. index.md

[실제 반영·검증 근거](wiki-review-v6.html#W19). 이전 제안은 백업에 보존했습니다.

## W20 · 결정 상태·구현 상태·배포 상태를 따로 표시

수정 계획 기본안 채택; wiki·코드 적용 상태와 별개

draft 하나로 미확정·미구현을 판단하지 않도록 메타데이터를 나눕니다.

- A · 결정/구현/검증 필드 분리 **확정 선택** — 명시적 결정 근거와 현재 확인 상태를 함께 기록합니다.
- B · 본문 상태표만 통일 — 바로 적용하기 쉽지만 자동 집계가 어렵습니다.
- C · 결정 문서만 엄격한 메타데이터 — 부담은 작지만 일반 계약 페이지 상태의 모호함이 남습니다.

반영·후속 작업:

1. document-standard에 decision_status·implementation_status·verified_at·supersedes의 의미와 예시를 정의합니다.
2. 본문의 사용자 결정과 실제 근거를 대조해 페이지별로 전환합니다. 일괄 accepted 승격은 하지 않습니다.

정본·대상:

- [wiki/decisions/D-020-trip-survey-and-ask-first.md](C:/Users/playdata2/Documents/final_workspace/wiki/decisions/D-020-trip-survey-and-ask-first.md)
- [wiki/decisions/D-018-decision15-stop-paths.md](C:/Users/playdata2/Documents/final_workspace/wiki/decisions/D-018-decision15-stop-paths.md)

## W21 · 깨진 링크 3곳을 실제 자료로 연결

**기존 문서 정정 반영 완료.**

W21 문서 정정 완료 깨진 링크 3곳을 실제 자료로 연결 확인된 깨진 경로 3곳을 고쳤습니다. 파일을 찾지 못한 옛 체크리스트는 미확보로 표시하고 현재 계약으로 연결했습니다. rest-endpoints.md · D-CS-011-browser-session-cookie.md · dining-agent-design.md

[실제 반영·검증 근거](wiki-review-v6.html#W21). 이전 제안은 백업에 보존했습니다.

## W22 · wiki 검사 범위를 현재·기록·백업으로 구분

**기존 문서 정정 반영 완료.**

W22 문서 정정 완료 wiki 검사 범위를 현재·기록·백업으로 구분 현재·생성물·기록·백업·이관 폴더를 분리하고 실제 깨진 링크는 실패하게 했습니다. 전체 결과를 JSON으로 저장합니다. check_wiki.py

[실제 반영·검증 근거](wiki-review-v6.html#W22). 이전 제안은 백업에 보존했습니다.

## W23 · 불변식 요약 숫자를 카탈로그에서 계산

**기존 문서 정정 반영 완료.**

W23 문서 정정 완료 불변식 요약 숫자를 카탈로그에서 계산 기존 ARCH-007 시험을 카탈로그에 연결하고 등록 72개를 자동 집계했습니다. 등록 수를 시험 통과 수로 표시하지 않습니다. invariant-summary.generated.md

[실제 반영·검증 근거](wiki-review-v6.html#W23). 이전 제안은 백업에 보존했습니다.

## W24 · ODsay 제품 미사용과 연구 대조 범위 구분

수정 계획 기본안 채택; wiki·코드 적용 상태와 별개

제품 미사용을 유지하고, 연구용 대조는 승인·조건 확인 뒤 별도로 기록합니다.

- A · 제품 미사용 유지 + 연구 근거 확인 **확정 선택** — 키 안내가 제품 연결 승인처럼 보이지 않게 표시합니다.
- B · 연구용 키 안내도 보류 표시 — 오해는 줄지만 이미 승인된 연구가 있다면 안내가 과도하게 제한됩니다.
- C · 승인된 연구 절차를 독립 문서로 분리 — 재현은 편하지만 승인 근거·약관·자료 보관 검토가 먼저 필요합니다.

반영·후속 작업:

1. D-CS-005와 api-key-issue-guide에 제품 운영/독립 대조의 적용 범위를 표시합니다.
2. 후속 승인 원문과 실제 사용·보관을 확인하기 전 연구 허용이나 약관 적합성을 확정하지 않습니다. 기존 키·자료를 삭제하지 않습니다.

정본·대상:

- [final_project_cs/wiki/decisions/D-CS-005-odsay-not-used.md](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/decisions/D-CS-005-odsay-not-used.md)
- [final_project_cs/wiki/external/api-key-issue-guide.md](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/external/api-key-issue-guide.md)

## W25 · 현재 계약을 위에, 변경 이력은 근거 링크로

**기존 문서 정정 반영 완료.**

W25 문서 정정 완료 현재 계약을 위에, 변경 이력은 근거 링크로 감시 결정·모델 비교·에이전트 팀 안내 등의 현재 결론과 시점별 기록을 분리했습니다. 옛 본문과 링크를 보존했습니다. D-017-watch-cadence-golden-time.md

[실제 반영·검증 근거](wiki-review-v6.html#W25). 이전 제안은 백업에 보존했습니다.

## 설명·검증 근거

[선택별 쉬운 설명·공식 근거·현재 코드 대조](wiki-review-v2.html#architecture-terms)

이전 Claude 검토는 당시 제안의 이력입니다. 이번 사용자 결정은 이전 제안보다 우선합니다. 이번 변경에 대해 새 Claude 검토를 받았다고 표시하지 않습니다.


## 2026-10-11 추가 댓글 반영

공통·여행 시험 분리, 실제 SQL 조회·그림, 판본별 독립 보고서 링크, 책임표 설계 상태, 문서의 상태 표시, wiki 검사 범위의 설명을 반영했습니다. 기존 DB 두 곳에는 옛 이커머스 표가 남아 있습니다. [실제 현황과 예시](../sql_review_2026-10-11/index.html)를 현재 확인 결과로 읽습니다.


## 2026-10-12 나머지 추천안 진행 승인

사용자 별도 지정 항목을 우선하고, 언급하지 않은 나머지는 문서 추천안으로 진행합니다. 승인 표시와 실제 문서·구현·배포 상태는 구분합니다. v11은 역사 기록으로 보존하고 v12는 전체 wiki 정리 후 새로 작성합니다.

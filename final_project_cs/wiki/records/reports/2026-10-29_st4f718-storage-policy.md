---
type: report
title: ST4F-718 저장 자원·quota·로그아웃 개인정보 후속
status: draft
domain: travel
---

# ST4F-718 저장 자원·quota·로그아웃 개인정보 후속

독립 검토 뒤 **새 격리 후보를 만들고 검증했습니다. 필수 관문 2/3 = 66.7% HOLD**이며 통합·정책 승인·종결·운영 반영은 아닙니다. 원본 제품 코드·기존 XML·스캐너 수정, push, 운영 쓰기, 트래커 변경은 각각 0건입니다. 담당은 이번 Codex 세션이며 독립 검토자/정책 승인자는 미확보입니다.

## 판단 이유와 계약 경계

현재 확인된 제품 결정은 2026-10-22 ST4F-718 D3의 **같은 브라우저 origin에서 여행별 자동 시작 한 번**입니다. 방문/완주 기록도, 서버 고객별 이력도 아닙니다. 다른 기기·브라우저 데이터 삭제 뒤 재생은 허용합니다. 로그아웃에 이력 삭제를 붙이라는 후속 확정은 찾지 못했습니다. 따라서 로그아웃마다 지우거나 50개/임의 TTL로 잊는 방식은 기존 약속을 바꾸므로 채택하지 않았습니다. 독립 검토의 원문과 루트/CS AGENTS·RULE·wiki 입구·역할·경로·실제 coord NOTICE 61개를 읽었습니다. private snapshot은 작업 폴더에 있습니다.

영속적인 정확한 집합은 여행 수에 비례하는 정보가 필요합니다. 유한한 기기에서 모든 신규 여행의 무제한 성공까지 약속할 수 없습니다. 후보는 전체 배열을 읽고 다시 쓰는 localStorage를 여행별 고정 크기 IndexedDB 레코드로 바꾸고 **브라우저 origin quota를 실제 자원 한계로 사용**합니다. 오래된 항목을 버리는 앱 cap/TTL·무음 메모리 폴백·서버 저장을 추가하지 않았습니다. 저장 완료 뒤에만 자동 시작을 허용하고 quota/권한/손상/비지원/blocked이면 자동 시작을 보류합니다. 지속 오류 알림에 오류 코드와 종료 카드의 수동 보기 안내를 표시합니다. 정상 추가는 이력 10,000개 뒤에도 metadata get 1 + 여행 getKey 1 + add 1이며 전체 스캔/JSON 재작성은 0입니다. 시간 복잡도 전체를 O(1)이라고 주장하지 않습니다(인덱스 검색·ID 해시·DB 내부 비용은 남습니다).

표식은 기기별 비추출 HMAC-SHA-256 키로 만든 64자 값과 true이며 raw 여행 ID·고객·제목·토큰·시각을 새 저장소에 넣지 않습니다. **익명화나 개인정보 정책 승인이라고 주장하지 않습니다.** 같은 origin 스크립트는 키로 후보 ID를 대입할 수 있습니다. 로그아웃 뒤 기기 표식 보존을 안내하고, 구 v1 raw 배열은 claim 또는 계정 화면 SignOut에서 이관한 후 제거합니다. 계정 캐시·동의 정리는 이관보다 먼저 완료합니다. 이관/원문 제거가 실패하면 원문을 버리지 않고 자동 재생을 보류하며, 로그아웃 화면에는 식별자가 남았다는 경고와 사이트 데이터 삭제 시 이력/재생 방지도 초기화된다는 설명을 보여 줍니다. 저장소가 금지된 상태에서 강제 삭제와 이력 보존을 동시에 약속하지 않습니다.

구 v1의 1회 JSON 파싱과 해시 배열 비용은 남습니다. 이전 50 cap에서 이미 유실한 ID는 복원하지 못합니다. 손상/비문자 배열을 조용히 비우지 않습니다. 기기 키만 사라진 부분 손상도 새 키 발급·중복 허용으로 넘기지 않습니다. 다중 탭은 readwrite 트랜잭션으로 직렬화하고, 비동기 저장 뒤 화면/세션이 바뀌었으면 늦은 화면 열기를 막습니다. commit 후 화면이 사라졌더라도 시작 허용 이력을 되돌리지 않습니다.

공유 계약 제안은 코드보다 먼저 격리 wiki에 작성했습니다. [계약 후보](../evidence/2026-10-29_st4f718-storage-policy/credits-device-history.md)의 장기 보존·고객 안내·동의 철회/여행 삭제 연계는 매니저·웹/인증·개인정보 책임자의 검토가 필요합니다. 이 세션은 임의 보존 기간이나 법률 판단을 확정하지 않았습니다. 기술 근거는 [IndexedDB 트랜잭션과 abort](https://www.w3.org/TR/IndexedDB/) 및 [Web Crypto HMAC](https://www.w3.org/TR/webcrypto/)입니다.

## 새 실행 증거

| 범위 | 실측 |
|---|---|
| 최종 웹 전체 | 1,241/1,241 = 100%, 실패/skip 0 |
| 그중 새 실제 종료 callback 전이 | 10/10 = 100% |
| 실제 Edge 저장·경합·logout·privacy 관측 | 22/22 = 100% |
| 실제 오류 Toast 컴포넌트, 390px | 코드·지속·닫기 3/3 = 100% |
| 최종 후보 변이 검출 | 4/4 = 100%, 각 실제 assertion 실패/exit 1 |
| 타입 검사·변경 파일 lint | 2/2 = 100%, 각 exit 0 |
| 새 전용 PG 계약 | 367/367 = 100% |
| 새 전용 PG DoD | 26/26 = 100% |
| 새 전용 PG 보안 | 124/125 = 99.2%, scanner 시험 1실패·기준선 3경로 탐지 |
| 필수 관문 | 2/3 = 66.7%, HOLD |
| 원본 XML/스캐너 SHA256 | 2/2 = 100% 유지 |
| 이전 718 공개 manifest | 11/11 = 100% 유지 |
| 불변 scanner로 최종 후보 파일 개별 검사 | 7/7 = 100%, 신규 탐지 0 |

독립 검토의 1,255건은 그 사본에 추가한 검토 전용 24건을 포함합니다. 이번은 추적된 기준 1,231건(저장 계약에 맞춰 기존 4건을 실제 Edge async 시험으로 교체) + 새 callback 10건입니다. 옛 동기 boolean/raw-array 가정을 억지로 통과시키거나 skip한 수치가 아닙니다. 모든 검토용 추가 시험을 이식했다고 주장하지 않습니다.

Edge에서는 256개 신규 여행과 256개 재요청, reload·브라우저 프로세스 재시작, 두 탭 같은 여행(허용 1/2)·다른 여행(보존 2/2), v1 128개 이관, 10,000개 이관/정상 호출 수, 실제 logout 함수 및 실제 SignOut 본문을 확인했습니다. 원시 ID 제거·기기별 키 분리·로그아웃 표식 보존·손상/권한 거절·제거 실패·기기 키 부분 손상도 포함합니다. callback은 실제 본문과 실제 tripEnded를 실행해 끝 경계·이미 종료·채팅/상세/알림 센터·저장 실패·세션/화면 변경 뒤 늦은 결과를 확인했습니다.

quota 증거는 구분합니다. **실제 localStorage를 QuotaExceededError까지 채운 경우 새 후보는 한 번만 허용했습니다. IndexedDB 최종 commit abort와 이관 실패는 QuotaExceededError를 주입하여 rollback·반복 보류·원문 보존·회복 뒤 한 번 허용을 검증했습니다.** CDP quota를 낮춘 실제 IndexedDB 작은 쓰기/1MiB 쓰기는 성공하여 native IDB quota 재현으로 세지 않았습니다. native IDB 디스크 포화나 OS crash 검증은 아닙니다.

50 cap·중복 허용·저장 실패 후 허용·raw ID 저장 변이는 최종 helper 소스의 별도 복제본에서 실행했습니다. 본 후보 소스를 바꾸지 않았고 SHA256도 확인했습니다. 실제 ToastView를 합성 페이지에서 렌더한 [화면](../evidence/2026-10-29_st4f718-storage-policy/notice.png)을 눈으로 확인했습니다. 전체 TripScreen mount·실제 서버·실제 휴대폰 종료 전환 수락과는 구분합니다. 모든 브라우저 문서는 격리 합성 문서이며 실제 고객/운영 API 호출은 0입니다.

### 불변 스캐너 조건의 최종 정정

원본과 clone의 스캐너가 동일하다는 초기 가정은 최종 해시 검산에서 기각했습니다. 원본은 빈 허용 목록이고, 선행 Git baseline 스캐너에는 공개 예제 주소의 기존 허용 항목이 있습니다. 줄바꿈만의 차이도 아니었습니다. 원본 원바이트 2/2와 clone의 자체 baseline 내용 2/2를 각각 보존했으며 두 정책이 같다고 보고하지 않습니다. 이 차이는 후보 patch에 포함하지 않았습니다.

최종 보안 수치는 `immutable_scanner_plugin.py`를 사용한 `python -m pytest tests/security -q` 재실행을 기준으로 합니다. 파일을 수정하지 않고 원본 scanner 원문을 `runpy`로 불러 해당 수집 시험의 함수로 실행했으며 **검사 대상 REPO만 격리 CS 경로로 지정**했습니다. regex·허용 목록·파일 범위·판정을 바꾸지 않았습니다. 실행 원문 SHA256은 최초 원본과 일치합니다. 기존 baseline의 완화된 허용 목록으로 최종 보안 수락을 주장하지 않습니다. 원본 조건의 추가 탐지 경로·기존 XML 실패는 아래 보존 raw 로그에 남기며 공개 근거에 탐지 문자열을 싣지 않습니다. 원본과 정책이 다른 baseline의 정합성 처리 역시 통합 전 검토 사항입니다.

최종 검산 첫 두 시도는 이 차이를 assert로 중단했고 DB 정지/최종 evidence 내보내기 전에 멈췄습니다. 앞선 인계 작성 명령은 별도로 실행되어 초안이 먼저 생겼으며 이 정정과 최종 집계를 반영한 문서만 결과로 사용합니다.

## 재실행·보존·다음 조건

작업 폴더는 `scratch/st4f718-storage-20261029/`이며 원본/이전 검토 사본과 hardlink를 공유하지 않는 새 clone `r`를 사용했습니다. baseline은 `cf8d976034b8c559147bd32862b678f98255e5cb`입니다. npm 설치와 전체 Next build는 하지 않았고 기존 node_modules를 읽는 junction, 별도 Vite cache를 사용했습니다. 검사 명령은 `python check_web.py`(Vitest/tsc), `python lint.py`, 설정의 node로 `browser.cjs`/`notice.cjs`, `python mutations_final.py`, `python gates.py`입니다. gate 실행기는 세 자식 종료 코드를 0/1/0으로 그대로 전달합니다.

초기 esbuild 미설치 실행 실패는 설치된 TypeScript/rolldown으로 수정했습니다. CDP quota 가정 실패 2건·Toast CSS loader 실패·PowerShell 명령 파싱 실패·새 callback 시험 타입 오류·브라우저 IPC 반복의 5초 timeout도 scratch에 남겼습니다. 마지막 것은 제한을 늘리지 않고 페이지 안에서 반복하도록 고쳤습니다. 이전 gate/웹의 같은 이름 로그는 최종 재실행 로그이며 별도 보존한 timeout JSON·초기 browser JSON/로그·변이 폴더를 성공 결과로 합산하지 않았습니다.

PG는 loopback 56318의 새 `calendar_test`/`pgdata`에서 migration·프롬프트 등록 후 실행했습니다. 최종 database/port/data_directory를 확인하고 전용 PG만 정상 정지하여 연결 거절을 확인했습니다. 데이터·프로필·사본·초기 실패·raw 보안 로그는 보존했습니다. raw 보안 로그의 기존 탐지 문자열은 공개 evidence로 복사하지 않았습니다. 기존 XML·스캐너·허용 목록·판정 규칙의 수정/제외/완화는 0건입니다.

[후보 patch](../evidence/2026-10-29_st4f718-storage-policy/candidate.patch)는 위 baseline에 대한 **7파일 델타**입니다. 선행 718 수정과 740 부모가 있는 저장소/bundle 전체를 통합하면 안 됩니다. 실제 최신 통합 tip에서 필요한 선행 변경을 확인하고 patch만 재검토·재검증해야 합니다. 이번은 최신 원격 tip 통합 검증도, 독립 검토 완료도 아닙니다.

남은 조건은 기존 immutable XML 보안 HOLD의 정식 처리, 보존/실패 정책의 공동 검토, 최신 통합 tip 수락, 전체 종료 화면·실서버·휴대폰 수락입니다. native IndexedDB quota·브라우저 축출/사이트 삭제·구버전 탭 공존도 추가 환경 검증이 남습니다. 운영 완료 항목의 분모는 모름이며 퍼센트를 만들지 않습니다. 통합/commit/push/배포/트래커 변경/종결은 모두 0건입니다.

[집계·해시](../evidence/2026-10-29_st4f718-storage-policy/summary.json) · [브라우저 관측](../evidence/2026-10-29_st4f718-storage-policy/browser.json) · [인계](../../../../wiki/handoff/2026-10-29_st4f718-storage-policy.md).

최종 원본 scanner 재실행은 124/125 = 99.2%이며 같은 시험 1건이 실패했습니다. 탐지 경로는 선행 clone의 `tests/security/test_no_infra_in_tracked_files.py`, `tests/unit/travel/test_social_links.py`, 기존 `security-ready.xml`의 3개입니다. 원본의 빈 허용 목록으로 선행 clone의 기존 공개 예제 문자열도 탐지한 결과이며, 이번 후보 7파일은 원본 scanner로 7/7 = 100% 무탐지입니다. 이 경로 차이를 정책 예외로 지우지 않았습니다. 최종 내보내기 중 시스템 Python에 pytest가 없어 1회 중단했고 기존 검증 환경에서 재실행했습니다. PG 정지/최종 evidence는 재실행 성공 뒤 확인했습니다.

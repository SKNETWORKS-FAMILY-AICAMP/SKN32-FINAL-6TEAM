---
type: report
title: ST4F-718 크레딧 보존 수정 독립 검토
status: draft
domain: travel
---

# ST4F-718 크레딧 보존 수정 독립 검토

후보 `cf8d976034b8c559147bd32862b678f98255e5cb`의 **50개 초과 이력 보존 수정은 독립 재현 시험에서 유효합니다. 필수 관문은 2/3 = 66.7%로 HOLD를 유지합니다.** 운영 수락·통합 승인·티켓 종결을 의미하지 않습니다. 제품 코드 변경·커밋·push·배포·트래커 쓰기는 각각 0건입니다.

검토자는 이번 별도 Codex 세션입니다. 이전 구현 세션의 시험 결과를 새 실행 결과로 재사용하지 않았습니다. 루트/CS AGENTS·CS RULE·양쪽 wiki 입구·개발 역할·코드 경로와 실제 `_coord` NOTICE 61개를 읽고 private snapshot으로 보존했습니다. 718 구현자의 완료/HOLD 및 인접 작업의 보존 경계를 확인했습니다. 새 `--no-hardlinks` clone `scratch/st4f718-independent-20261029/r`에서 실행했습니다. 기존 후보·다른 세션의 사본·DB·원본 제품 코드는 수정하지 않았습니다. 패키지는 기존 설치본에 새 사본의 junction으로 접근하고 Vite cache는 새 작업 폴더로 분리했습니다. 새 npm 설치·Next 전체 build는 하지 않았습니다.

## 검토 발견

1. **P2 — 이력에 애플리케이션 차원의 자원 상한이 없습니다.** [저장 함수](../../../../scratch/st4f718-independent-20261029/r/final_project_cs/frontend/apps/web/src/features/trip/ending-credits.ts:85)는 전체 배열을 읽어 필터하고 새 배열·JSON을 매번 만듭니다. 저장 크기와 호출당 읽기·복사 비용은 누적 ID 수/길이에 따라 늘어납니다. Edge에서 합성 ID 10,000개를 넣은 뒤 추가하면 10,001개·UTF-16 문자열 860,018바이트였습니다(브라우저 내부 heap/디스크 총량을 뜻하지 않습니다). 단일 추가 관측 6ms는 성능 보장이나 운영 표본이 아닙니다. 실제 localStorage 잔여 용량을 채우면 새 여행의 두 호출이 모두 true이고 이력은 불변이었습니다. 기존 catch 동작이지만 제한 제거로 정상 누적 이력이 용량 한계에 도달할 수 있습니다. 자원 상한 충족으로 승인할 수 없습니다. 단순히 50개 cap/TTL을 복원하면 여행별 한 번 계약을 다시 깨므로, 영속 저장 방식·실패 처리·보존 정책을 계약과 함께 결정해야 합니다.
2. **P2, 기존 한계 — 탭 간 read/modify/write는 원자적이지 않습니다.** 실제 Edge 두 탭의 native Storage를 사용하고, 함수의 읽기와 쓰기 사이에 시험용 async barrier만 삽입했습니다. 둘 다 빈 이력을 읽고 A→B 순서로 쓰면 둘 다 true, 최종 `["tab-b"]`, 이후 원본 함수의 A 호출은 다시 true였습니다. 이는 통제된 스케줄의 알고리즘 재현이며 원본 동기 함수를 자연 경합으로 재현했다고 주장하지 않습니다. 이번 한 표현식 변경이 만든 신규 경합은 아닙니다. 다중 탭까지 엄밀한 한 번 보장을 하려면 별도 조정이 필요합니다.
3. **개인정보·보존 의미:** 저장값은 raw 여행 ID 배열이며 제목·장소·고객 정보나 토큰을 추가하지 않습니다. 그렇지만 ID는 식별 단서이고 암호화·계정별 namespace·TTL·삭제 연동은 없습니다. 실제 `logout()`를 HTTP stub과 실행해도 이력이 남는 것을 확인했습니다. 이는 기기 기준 계약과 맞지만 cap 제거는 보존량을 늘립니다. 이번 검토가 무기한 ID 보존의 개인정보 정책 승인을 대신하지 않습니다. 브라우저/프로필/포트/호스트가 다르면 별도 이력입니다. 기기 전체 공통 이력이나 서버 고객 기록으로 해석하면 안 됩니다.
4. **자료 의미와 복구 한계:** 기존 v1 키와 string[] 형식·정확한 문자열 비교·배열 순서를 유지합니다. 비문자 원소는 신규 claim 때 빠지고 기존 문자열 중복은 남습니다. 이미 본 ID는 쓰지 않으므로 그때는 잘못된 원소도 정리하지 않습니다. JSON 손상/비배열은 빈 이력으로 취급해 다음 claim이 덮습니다. 브라우저 자료 삭제는 재허용하며, 이전 cap으로 이미 유실된 ID를 복원하지 않습니다. 등록한 것은 크레딧 시작 허용 이력으로, 실제 방문·전체 시청·전달 확인이 아닙니다.

## 새 실행 결과

| 범위 | 실측 |
|---|---|
| 새 독립 저장·자료 의미 시험 | 16/16 = 100% |
| 실제 TripScreen callback 본문/실제 logout 시험 | 8/8 = 100% |
| 최종 웹 전체(새 시험 24개 포함) | 1,255/1,255 = 100%, 실패·skip 0 |
| 변이 검출(50 cap·저장 제거·중복 허용·이력 초기화) | 4/4 = 100%, 각 exit 1·실제 assertion 실패 확인 |
| Edge 기대 관측 | 12/12 = 100%, 한계 재현을 포함하므로 제품 수락 비율이 아님 |
| 최종 타입 검사 | 1/1 = 100%, exit 0 |
| 새 PG 계약 | 367/367 = 100% |
| 새 PG 보안 | 124/125 = 99.2%, 기존 XML 탐지 실패 1건 |
| 새 PG DoD | 26/26 = 100% |
| 필수 관문 | 2/3 = 66.7%, **HOLD** |

128개를 기록하고 오래된 순서로 다시 claim하면 128/128 = 100% 재생을 거부했습니다. 실제 새로고침·브라우저 프로세스 재시작·동일 origin 순차 탭에서도 첫 여행을 기억했습니다. 기존 50 cap 변이는 독립 시험 16개 중 2개가 실패했습니다. 변이 후 소스를 원바이트로 복구한 뒤 전체 시험을 실행하고 기존 후보 소스와 SHA256 일치를 확인했습니다.

TripScreen의 실제 `reachEnd` callback 본문을 추출하여 실제 `tripEnded`/claim 함수와 실행했습니다. 끝 경계 전이만 자동 시작, 이미 종료한 채 진입/끝나기 전은 claim 없음, chat/detail/notice 상태는 계획만 전환하고 이력은 소비하지 않음을 확인했습니다. 이 시험은 React 전체 mount·화면·실서버를 대신하지 않습니다. Edge도 실제 함수 선언을 추출/TypeScript 변환한 합성 HTML에서 실행했습니다. HTTP 요청 5건은 모두 합성 HTML로 응답했고 고객/서버 API를 부르지 않았습니다. 전체 TripScreen 종료 화면·실서버·휴대폰·최신 통합 tip 수락은 남습니다.

## 보존·실패·명령

명령과 실행기는 [작업 폴더](../../../../scratch/st4f718-independent-20261029/)에 보존했습니다. `python web_run.py`가 독립 시험·4개 변이·복구·초기 전체 시험·타입 검사를 실행했습니다. callback 시험 추가 뒤 `vitest run --config review.vitest.config.ts --reporter=json` 전체와 `tsc --noEmit --incremental false`를 다시 실행했습니다. Edge는 Node로 `browser-review.cjs`를 실행했습니다. `gates.py`는 각각 `python -m pytest tests/contract -q`, `python -m pytest tests/security -q`, `python -m scripts.verify_dod_v11`을 순차 실행하고 실제 자식 종료 코드 0·1·0을 기록했습니다.

새 전용 PostgreSQL은 loopback 56218, DB `calendar_test`, 자료 폴더 `scratch/st4f718-independent-20261029/pgdata`입니다. migration·프롬프트 등록 후 관문을 실행했으며 마지막 data_directory·포트·DB를 확인한 뒤 정상 정지/연결 거절을 확인했습니다. 클러스터·복제본·브라우저 프로필·스크린샷·원시 시험 JSON·로그는 모두 남겼습니다.

브라우저 초기 시도 4건의 실패도 보존했습니다. 첫 debugger 두 탭 시도는 진행이 멎어 정확한 세션 node/Edge PID와 자식만 확인해 중단했습니다. 다음 시도는 보존 프로필의 다른 origin 이력을 초기화하지 않은 fixture 오류, 세 번째는 const 재선언으로 barrier가 설치되지 않은 시험 오류, 네 번째는 탭의 storage event 반영 전에 읽은 assertion 오류였습니다. 최종 다섯 번째 실행은 독립 초기화·별도 lexical scope·storage 반영 대기를 적용해 exit 0입니다. 초기 실패를 통과 증거로 세지 않습니다. debugger 대신 async barrier를 사용한 통제 실험의 한계를 위에 명시했습니다.

원본 스캐너와 기존 XML SHA256은 시작/종료 2/2 = 100% 동일합니다. 기존 718 공개 evidence manifest의 11/11 = 100% 해시도 일치합니다. 스캐너·금지 표본·기존 XML·허용 목록·보안 실패를 수정/제외하지 않았습니다. 원시 보안 로그는 기존 탐지 문자열을 포함하므로 scratch에만 보존하고 새 공개 evidence에는 집계·해시만 적었습니다. 기존 보고서는 다시 쓰지 않았습니다.

## 다음 담당자

이력 유실 수정의 좁은 효과는 확인했지만 메모리/용량 상한과 실패 시 의미·ID 보존 정책은 위 한계로 남습니다. 740 부모가 들어 있는 bundle 전체를 통합하지 말고 기존 두 파일 `candidate.patch`만 실제 최신 통합 tip에서 검토해야 합니다. 필수 보안 HOLD의 정식 해소와 관문 재실행, 전체 종료 전환 화면·실서버·휴대폰 수락 전에는 push·배포·종결 승인을 주장하지 않습니다. 이번 세션은 해당 동작을 하지 않았습니다.

[검토 집계](../evidence/2026-10-29_st4f718-independent-review/review-summary.json) · [Edge 관측](../evidence/2026-10-29_st4f718-independent-review/browser-review.json) · [독립 시험/실행기/해시](../evidence/2026-10-29_st4f718-independent-review/) · [인계](../../../../wiki/handoff/2026-10-29_st4f718-independent-review.md).

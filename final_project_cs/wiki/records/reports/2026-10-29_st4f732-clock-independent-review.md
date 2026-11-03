---
type: report
title: ST4F-732 단계 시계 후보 독립 검토
status: draft
domain: travel
---

# ST4F-732 단계 시계 후보 독립 검토

2026-10-29 KST. **목표 결함은 독립 재현·해결 확인, 통합·운영은 HOLD 유지**입니다. 이전 작업자가 만든 단계 키 추가 후보만 검토했습니다. 원본 제품·다른 작업자 사본·공유 DB·트래커를 수정하지 않았고, commit/push/배포/삭제는 0건입니다. ST4F-718·731의 기존 보류를 해제하지 않았습니다.

루트 AGENTS, CS AGENTS/RULE, 양쪽 wiki 입구, 역할·코드 경로·문서 표준·웹 SSE 계약, 지정 후보 인계와 관련 진행 검증 인계를 읽었습니다. 실제 Hermes coord NOTICE 62개를 읽고, 732 후보 작업자의 완료·범위 해제 및 보류 조건을 확인했습니다. 담당은 이번 Codex 검토 세션이며, 앞 후보 구현과 구분한 독립 시험입니다. 별도 사람의 승인으로 표시하지 않습니다.

## 판정과 발견 사항

1. **목표 수정 유효.** 같은 React StrictMode hook을 유지하고 구형 서버 입력 `reading` 12초 → `checking`으로 바꾸면 원래 hook은 첫 렌더에 12초를 남겼습니다. 후보는 즉시 0초, 1초 후 1초였습니다. 모든 세부 단계 전환·동일 단계의 새 카운트에서도 초기화를 확인했습니다. 후보 hook 바이트는 제공된 후보와 일치합니다.
2. **[P2, 기존] 동일 hook의 실행 재시작에는 이전 tick이 남습니다.** reading 9초 → ended=true → ended=false, reading 9초 → received → reading, reading 9초 → checking → reading(중간 tick 전)에서 첫 렌더가 0 대신 9입니다. 다음 interval까지 이전 `8초째` 표시가 잠깐 재등장할 수 있습니다. `news`가 이전 실행과 같으면 오래된 `tick.news`도 다시 일치하기 때문입니다. 세 경우 모두 원래 hook에서도 재현돼 후보의 새 회귀가 아닙니다. 실행 세대나 종료/시작 경계를 포함한 초기화와 회귀 시험이 후속 대상입니다. 전체 화면 재시작에서 같은 hook이 유지되는 경로의 수락은 별도 남습니다.
3. **[의미 확인 필요, 기존] 현재 단계보다 앞선 늦은 패킷도 시계를 0으로 만듭니다.** 실제 reducer를 거쳐 hours=1/4에서 9초 대기 → places=1/4 지연 수신 시 현재 단계는 hours 그대로지만 quiet=0입니다. 전체 `serverPhases` 직렬화가 달라지기 때문이며 원래 hook도 같습니다. 주석의 “카운트가 올 때마다”에는 맞지만, “현재 단계에 소식이 없는 시간”으로 읽으면 다릅니다. 의미를 확정하기 전 새 결함 또는 해결 완료로 단정하지 않습니다.

실제 호출부에서 `readingExtras`가 있으면 Reading 화면을 유지하며 최신 stage를 전달하므로 hook 단계 전환 검증에는 근거가 있습니다. 일반 Reading→Checking은 서로 다른 컴포넌트로 바뀌어 hook이 재생성될 수 있습니다. 이번 재현을 모든 전체 앱 경로에서 발생하는 결함으로 일반화하지 않습니다.

## 직접 실행 결과

| 검증 | 이번 실행 |
|---|---|
| 수정 전 실제 React/Edge 독립 시험 | 14/19 = 73.7%, 목표12초 잔류 + 기존 경계4건 |
| 후보 실제 React/Edge 독립 시험 | 15/19 = 78.9%, 기존 경계4건 유지 |
| 목표 외 동일 결과 비교 | 18/18 = 100%, 새 실패0·목표1건 개선 |
| 전체 웹 Vitest | 1230/1230 = 100%, 실패·skip0 |
| TypeScript | 1/1 = 100%, exit0 |
| 필수 관문 | 2/3 = 66.7%, 아래 각 결과 참조 |
| DoD | 26/26 = 100%, exit0 |
| 계약 pytest | 367/367 = 100.0%, 실패0·오류0·skip0 |
| 보안 pytest | 124/125 = 99.2%, 실패1·오류0·skip0 |
| 원본 보호 파일 SHA256 | 18/18 = 100%, scanner·XML 포함 |

DoD의 항목/하위시험 수와 exit는 [직접 실행 로그](../evidence/2026-10-29_st4f732-clock-independent-review/dod-repaired.log)를 봅니다. 필수 명령은 CS cwd에서 `python -m scripts.verify_dod_v11`, `python -m pytest tests/contract -q`, `python -m pytest tests/security -q`이며 pytest에는 원시 XML·짧은 traceback 출력 옵션을 더했습니다. 초기 의존 부족 실행은 최종 통과율로 세지 않았습니다. 해당 실패·중단 로그도 scratch에 보존했습니다.

Edge 시험은 실제 React/ReactDOM·hook·실제 진행 reducer를 bundle한 독립 문서입니다. 단계별 초기화, 7/8초 문구, 새 카운트, 같은 패킷 재연결 replay, 같은 단계 역순 카운트 무시, 앞 단계 지연 패킷, 완료·wrapping·unmount cleanup, StrictMode의 활성 interval 1개, remount 초기화, 시스템 시각 전후 변경, 가상 60초 timer catchup, offline/online, 실제 CDP frozen/active, 전체 페이지 navigation을 확인했습니다. pageerror는 두 실행 모두 0입니다. 60초 경과는 부동소수점·초기 오프셋을 허용하도록 표시와 같은 floor로 비교했습니다. 초기 하네스 process 환경 누락 오류와 과도한 정확값 단언 실패는 별도 보존했으며 제품 실패로 세지 않았습니다. Rolldown의 use-client 지시어 경고·Vitest 설정 경고·Starlette deprecated 경고도 원시 로그에 보존했습니다.

## 격리와 보안 보존

`scratch/st4f732-clock-review-20261029/repo`는 기존 격리 Git 객체의 `fab3da50ab970a7d8c79ed65c1df2e666abc1cd0`를 새 archive한 사본입니다. 원본에서 Git 변경·checkout·색인 재구성을 하지 않았습니다. 사본에 독립 Git 색인을 만들고 후보 hook·후보 회귀3건 및 보호 evidence를 바이트 그대로 포함했습니다. 스캐너는 원본의 변경 없는 현재 버전입니다. 최신 원격 tip 통합 검증은 이번 범위에서 하지 않았습니다.

실 PostgreSQL16.15의 새 pgdata·DB clock732·loopback port57332를 만들고 current_database/port/data_directory 조회, 마이그레이션·프롬프트 등록 뒤 관문을 돌렸습니다. 초기 Composer 누락은 같은 커밋의 `final_project_sample/acop_composer` 패키지 archive와 사본 PYTHONPATH로 보완했습니다. sample 도메인 예시·commerce 평가를 시험 재료로 사용하지 않았습니다. 최종 필수 관문은 DB 간섭을 피하도록 순차 실행했습니다. 사본 DB는 정상 종료하고 연결 거부를 확인했습니다. pgdata·archive·로그는 삭제하지 않았습니다.

보안 관문은 통과하지 못했습니다. 보호 XML의 동일 탐지 5건이 유지되고, archive 기준선의 기존 추적 시험 파일도 현행 스캐너에 걸립니다. 예외·허용 목록·스캔 범위·XML 수정/이동/추적 해제는 0건입니다. 실패 상세가 포함된 보안 XML/로그는 비공개 scratch에 보존하고 여기에는 개수만 게시합니다. 원래 보호 파일 18개(문자열 경로 표기20건의 중복 제거)를 다시 해시로 확인했습니다. 새 공개 텍스트도 같은 불변 find_leaks로 검사했습니다.

## 남은 범위와 인계

후보의 좁은 단계 전환 수정은 검증됐지만 기존 재시작3경계·지연 패킷의 시간 의미·보안 HOLD 해결·최신 통합 tip 재검증·실제 전체 앱/SSE 수락은 남습니다. 재연결은 실제 reducer replay와 브라우저 offline/online 시험이며 실제 서버 연결 재수립 수락이 아닙니다. CDP freeze/active와 가상 시간 시험을 OS 절전·실기기 throttling 수락으로 바꾸어 말하지 않습니다. 운영 전체 수락은 **분모 모름**입니다. 후속은 위 경계의 실제 호출부 도달 여부와 시간 의미를 먼저 확인하고, 별도 승인된 보안 해결 뒤 모든 관문과 앱 수락을 다시 실행해야 합니다. 현재 후보는 통합하지 않습니다.

[집계](../evidence/2026-10-29_st4f732-clock-independent-review/summary.json) · [독립 시험 runner](../evidence/2026-10-29_st4f732-clock-independent-review/browser.cjs) · [후보 관측](../evidence/2026-10-29_st4f732-clock-independent-review/browser-candidate.json) · [수정 전 대조](../evidence/2026-10-29_st4f732-clock-independent-review/browser-baseline.json) · [원래 후보 보고](2026-10-29_st4f732-step-clock.md).

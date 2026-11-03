---
type: handoff
title: ST4F-719 중단 작업 재개 — 늦은 id mutation 네 경로 격리 수정, 보안 HOLD
status: draft
domain: travel
---

기존 `scratch/st4f719-blocker-independent-20261029/repo`를 재사용했습니다. 원본 코드 반영·커밋·push·배포·운영 쓰기는 0건입니다. [상세 보고](../../final_project_cs/wiki/records/reports/2026-10-29_st4f719-late-id-mutations-resumed.md) · [패치·검증 집계](../../final_project_cs/wiki/records/evidence/2026-10-29_st4f719-late-id-mutations/).

| 구역 | 상태 |
|---|---|
| 네 경로 수정 | **4/4 = 100%**. IntakeReview edit, TripEdit reopen, TripScreen resumed, useServerReview apply. query 객체 동일성 검사, 늦은 오류·재개 settled도 보호 |
| 정상·경합 Edge | **8/8 = 100%**, 가드 제거 변이 목표 **4/4 = 100% 검출**·복구 해시 일치 |
| 실제 PG 계정 전환 / 개인정보 화면 | **4/4 = 100% / 10/10 = 100%**. 전환 실행에 정상 대조 4건 선택 제외, 전체 등록 기준 4/8 = 50%; 정상 대조는 별도 8건 실행에서 통과 |
| 웹 단위 / 타입 | **1303/1303 = 100%**, tsc·변경 제품 파일 eslint exit 0 |
| PG 필수 관문 | **1/3 = 33.3%**. DoD26/26 통과. 계약365/367·보안124/125는 Git 실행 PermissionError. 쿠키38/38 통과 |
| 보안 HOLD | scanner·보호 XML 해시 **2/2 = 100%** 보존. 원래 탐지기의 보존 tree 별도 검사에서 기존 XML 검출 5건 유지. 우회·예외 추가 없음 |

## 매니저 검토와 적용 순서

1. 담당 Codex, 검토 요청 대상 매니저·웹/인증 담당, 기존 이슈 **ST4F-745**에 대응하는 로컬 인계입니다. 이 세션은 트래커 변경·외부 메시지를 하지 않았습니다. 독립 검토 승인 전입니다.
2. 기존 인계의 기준 `656579fe3` + `full-candidate.patch` + `providers-owner-survives-401.patch` + `final-review-fix.patch` 뒤에 이번 `late-id-mutations.patch`를 검토합니다. 패치 경로 기준은 `repo/`입니다. 현재 사본에는 모두 적용돼 있으므로 중복 적용하지 않습니다. 12파일의 최종 바이트 해시는 `source-manifest.json`에 있습니다.
3. 실제 PG 계정 경합 재현에는 기존 로컬 시험 전용 identity 화면과 별도 `real-auth-test-harness.patch`가 필요합니다. 이 화면을 운영 앱에 추가하는 승인이 아닙니다. 실제 fixture인 `actors-private.json`은 공개·복사하지 않습니다.
4. **보안 HOLD가 풀리기 전에 병합·push하지 않습니다.** Git 실행 파일 경로는 setup.json의 이전 위치가 사라졌고, 현재 기본 WindowsApps Git은 PermissionError입니다. Git 환경을 복구한 담당자가 계약·보안 관문을 다시 실행해야 합니다. scanner·XML 원본·색인은 이 작업에서 고치지 않습니다.

## 재현 명령과 경계

모두 기존 격리 작업 폴더의 실행기입니다. 새 clone이나 의존성 설치 없이 실행했습니다.

```powershell
python scratch/st4f719-blocker-independent-20261029/run_late_web.py
$env:RESULT_NAME='새로운-결과이름'
$env:SPEC='late-id-mutations'
python scratch/st4f719-blocker-independent-20261029/run_late_browser.py

$env:BROWSER_SPECS='late-id-mutations,identity'
$env:API_PROBES='0'
$env:INDEP_PROBES='0'
$env:LATE_REAL='1'
$env:LATE_CHANGED_ONLY='1'
python scratch/st4f719-blocker-independent-20261029/run_late_gates.py browser-새로운-결과이름
```

PG 실행기는 기존 클러스터의 localhost 포트·데이터 디렉터리를 확인하고 종료합니다. 실제 인증·세션은 PG, 여행 응답은 합성 stub이며 실제 여행 쓰기 종단 검증은 아닙니다. 재개 시험은 완료 콜백을 보류해 검증합니다. 일반 대조를 다시 돌릴 때는 `LATE_REAL`, `LATE_CHANGED_ONLY`, `LATE_ONLY`를 제거합니다. `run_late_mutant.py`는 시험 동안 가드를 무력화하므로 다른 실행과 동시에 돌리지 않습니다. 완료 때 원래 파일 복구·해시 일치를 확인했습니다.

## 남은 것과 디스크

- 수정 네 경로의 독립 검토·통합은 남아 있습니다. 운영 여행 API의 mutation 종단 검증은 이번 범위에서 미실행입니다. 분모 모름이므로 완료율을 만들지 않습니다.
- 현재 Git 환경 문제와 기존 XML 보안 HOLD가 해소돼야 릴리스 관문을 다시 판정할 수 있습니다.
- 최종 공개 자료·변경 소스 21파일 × 실제 fixture 값 174개 대조 일치 0건, 새 인프라 검출 0건, manifest·보호 해시 일치를 확인했습니다. 시험용 포트는 모두 닫혔습니다. 검토 폴더 1,042,149바이트·공개 evidence 39,700바이트이며 재사용 Next 캐시 순증은 포함하지 않습니다.
- 수정 전 파일·실패 로그는 보존했습니다. 새 clone·DB 전체 복사·추가 production build는 0건입니다. 캐시는 재사용했으며 순증은 분모 모름입니다. `disk_guard inventory`의 등록 0·미등록 0, 여유 183,043,936,256바이트·목표 400,000,000,000바이트를 기록했습니다. 이번 검토 폴더와 공개 자료의 최종 바이트 수는 evidence 요약에 있습니다. 사용자 자료를 용량 확보 대상으로 삼지 않았습니다.

---
type: record
date: 2026-10-12
status: locally-verified
domain: travel
---

# 완료 UIUX와 기존 수정 통합

## 통합 범위

완료된 고객 UIUX 점검, 검증 중 전체 목록·현재 일정 표시, 목록 끝 등록 버튼, 지도 방향과 충돌 회피를 함께 통합했습니다. 같은 방향의 화면 밖 이전 일정은 기존 스택 하나로 묶고, 반대 방향은 나눕니다. 지도 안 일정과 새 현재 일정은 이전 스택에서 제외합니다. 이 기준이 앞선 v4의 검증 중 강제 개별 표시를 대체합니다.

기존 CI 수정에서 구현한 로그인 조회 경쟁 방지, 화면 이동 후 알림·되돌리기 유지, 닫은 알림의 재등장 방지, 지연 안내 시점 고정, 선택 요청의 대상 일정 조회를 최신 UI에 다시 연결했습니다. 지도 도구 전환·동일 화면 좌표 관찰을 기다리는 시험과 외부 타일 대신 mock 서버 타일을 사용하는 기본 설정도 보존했습니다. 진행 중인 택시·운영 기능과 공유 작업 폴더의 다른 변경은 가져오지 않았습니다.

팀 develop의 기존 요식업 변경과 개인 저장소의 기존 이력을 정상 병합으로 보존했습니다. 개인에만 있던 자료를 팀 저장소에 추가하지 않았으며 main 변경은 수행하지 않습니다.

## 검증

| 검사 | 결과 | 범위 |
|---|---|---|
| 고객 웹 단위 시험 | 712/712 통과 | 통합본 87개 시험 파일 |
| TypeScript·ESLint·production 빌드 | 3/3 종료0 | 통합본 고객 웹 |
| mock 서버 시험 (화면 반응) | 고유 49/49 재검증 포함 통과 | 알림 유지·지연 안내·지도 도구·추가·등록·최신 지도 스택 |
| 백엔드 선택 시험 | 771/771 통과 | 구조·계약·보안·영향받은 일정 생성·요식업 |

첫 집중 화면 실행은 48/49 통과였습니다. 읽기 지연 안내의 최신 문구가 과거 초 단위 문구로 바뀐 1건을 수정한 뒤 관련 세 사례 전체를 재빌드한 제품으로 실행해 3/3 통과했습니다. 고유 49개가 확인되었으며 한 번의 중단 없는 49/49 실행으로 표시하지 않습니다. [결함과 수정](debugs/2026-10-12_1230_통합중_지연안내_문구차이.md).

실서버 확인 (cs 프로젝트 서버 응답): 안 했음. 위 화면 시험은 전용 mock 서버와 Chrome으로 실행했습니다. x600 서버 새 코드 배포·외부 로그인·실제 고객 요청 검증은 포함하지 않습니다. 전체 GitHub CI는 푸시 후 별도로 확인하며 이 기록 시점에 최종 통과로 표시하지 않습니다.

빌드는 격리 작업 사본에서 webpack과 단일 작업자를 사용했습니다. 메모리·캐시 제어만 임시 적용했으며 제품 설정은 빌드 뒤 원본으로 복원했습니다. backend 시험은 새 전용 PostgreSQL에서 현재 SQL을 적용하고 외부 통신·기존 업무 DB 접근을 차단했습니다.

재현: 고객 웹에서 `vitest run --pool=threads --maxWorkers=1`, `tsc --noEmit --incremental false`, `eslint .`, `next build --webpack`을 실행했습니다. 화면 시험은 `playwright test -c playwright.live.config.ts`의 같은 mock 서버·제품 빌드와 단일 Chrome 작업자를 사용하되 격리 포트와 재사용 빌드로 실행했습니다. 전체 화면 시험의 대체가 아닌 변경 연결에 대한 49개 집중 사례입니다.

[단위 원문](../evidence/2026-10-12_manager-develop-uiux-final/unit.log) · [타입](../evidence/2026-10-12_manager-develop-uiux-final/type.log) · [린트](../evidence/2026-10-12_manager-develop-uiux-final/lint.log) · [빌드](../evidence/2026-10-12_manager-develop-uiux-final/build.log) · [최초 화면 원문](../evidence/2026-10-12_manager-develop-uiux-final/browser.log) · [최초 화면 JSON](../evidence/2026-10-12_manager-develop-uiux-final/browser.json) · [재검증 원문](../evidence/2026-10-12_manager-develop-uiux-final/browser-retry.log) · [재검증 JSON](../evidence/2026-10-12_manager-develop-uiux-final/browser-retry.json) · [백엔드 원문](../evidence/2026-10-12_manager-develop-uiux-final/backend.log) · [지도 인계 해시](../evidence/2026-10-12_manager-develop-uiux-final/map-source-match.json)

지도 담당의 별도 시험은 단위108개와 Chrome 고유12개입니다. 최초11개 통과 후 공간 부족으로 중단된1개를 같은 코드로 재실행해 통과했으며, 이를 한 번의 중단 없는12/12 실행으로 표시하지 않습니다. 이 통합본의 위49개 시험과 겹치므로 합산하지 않습니다.

변경 전 원본은 담당 작업의 비공개 백업에 보존했습니다. 미완료 다른 기능은 각 담당 작업에서 이어갑니다.

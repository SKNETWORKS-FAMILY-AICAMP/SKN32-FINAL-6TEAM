---
type: handoff
title: EKS reading fatal 오프라인 원인 분리·관측 로그 대기 HOLD
status: draft
domain: travel
---

# EKS reading fatal 후속 인계

**PR110 draft·배포 HOLD, 운영 원인 미확정입니다.** [보고서](../records/reports/2026-10-29_eks-reading-fatal-offline-discrimination.md)·[집계](../records/evidence/2026-10-29_eks-reading-fatal-offline-discrimination/final-summary.json)를 봅니다.

한 일 목록:

- root/cs 지침·색인·지정 인계·배포판 계약 확인. 새 no-hardlinks `C:/_proj/eksfatal1029/repo`, main57f3d2f004d0 기준이며 원본 제품/Git 불변.
- 실제 기존 CI/CD 로그 읽기·PR110 draft/head3fda4eee·필수3/3=100% 확인. 운영 실패 로그는 CI/CD에 없음. 새 workflow/권한/CI 실행0.
- 배포판 reader 회귀215/215=100%, 같은42항목 실제 파이프라인+가상시계의 원인 분리7/7=100%. 7개 원인이 같은 공개 reading_model_failed를 냄. 운영 원인 재현 완료로 부르지 않음.
- PR110/main reader 관련 Git blob5/5=100% 동일. 초기 CRLF 비교 불일치는 보존, 정규화·Git blob 대조로 검증. 실제 배포판 유료 출력 상한12288, local90/API30 확보 구현을 확인.
- 새 coordination notice에 HOLD·예약없음 기록. 독립 승인/다른 작업자 확인을 주장하지 않음.
- 실제 모델/provider 호출0·새운영접수0·추가 모델/provider비용0·push/병합/배포/삭제0. 이전 비용 모름·원래3회2review/1fatal 유지. 모든 사본/로그 보존, 새 PG/listener 없음.

다음에 필요한 것은 기존 허용된 관측 경로의 별도 합성 진단 **2026-10-28 22:09:29–22:12:00 UTC** reader 경로 이유 코드입니다. 사용자에게 기존 경로나 비식별 로그를 요청했으며 아직 확보하지 못했습니다. PC에 AWS/kube 자격설정 없음, GitHub는 CI/CD만 확인했습니다. 권한 추가나 CD credential 전용으로 우회하지 않습니다. 키·본문·쿠키/CSRF·실제 ID·고객 전체 로그/DB 덤프를 수집하지 않습니다.

원인 확보→정확 예외/시계/예산 조건의 RED 재현→격리 수정→GREEN·필수관문·최신coord/main/PR 확인→보호병합·CI·기존CD·실제digest/readiness→최소동일42항목 전후 순서입니다. 사용자 배포 승인은 유효하지만 HOLD 해제 조건이 아직 없습니다. 원래 실패 회차는 지우거나 성공으로 교체하지 않고 새 측정 cohort를 따로 만듭니다. dormant merge_when_validated.py의 원래3회 모두review 전제를 덮어쓰지 않습니다. 전체 운영 검증 분모 모름.

명령·원로그·회귀XML·대역probe는 `C:/_proj/eksfatal1029`에 있습니다. 테스트 대역만 격리 repo에 추가, 제품 수정은 하지 않았습니다. 이후 실제 원인이 밝혀져야 수정할 대상이 정해집니다.

최종 검증: 새 문서/증거를 격리 사본에만 stage하여 기존 추적 텍스트 보안검사 **12/12 = 100%**, diff --check exit0, 링크/JSON/XML 검사 **12/12 = 100%**를 확인했습니다. 최종 원격 읽기에서도 main57f3d2f004d0·PR110 draft/head3fda4eee 유지입니다. 최초 색인 게시 스크립트의 인코딩 이름 오류는 색인 변경 전에 중단됐으며, 기존 백업 동일성을 확인한 후 UTF-8-SIG 이름으로 정정한 별도 스크립트로 완료했습니다. 제품 수정/원인 확정/배포는 하지 않았습니다.

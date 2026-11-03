---
type: report
title: EKS CD 진단 후보 독립 후속 검토
status: draft
domain: travel
---

# EKS CD 진단 후보 검토

2026-10-29 KST. 변경 담당·검토: 이번 Codex 세션. 이전 세션 후보를 별도 사본에서 검토했으며 이번 보완 구현은 자체 검토입니다. 별도 검토자의 승인을 주장하지 않습니다.

한 일: 루트·CS 지침, 관련 wiki 배포 계약, R/V/Hspeed/AWS/ST4F597 및 EKS `_coord` 인계를 확인했습니다. 최신 팀 main은 `20c296e778d74b16808e0e4393bf68c309a689b6`입니다. 새 격리 사본 `C:/_proj/eksreview1029/repo`에 진단 패치만 적용했습니다. scalar 및 반려 계산 후보는 넣지 않았습니다.

실행 증거: 기존 배포·잠금 시험 76/76 = 100%, 기존 후보 79/79 = 100%. 추가 보안·실패 시험은 보완 전 3/4 = 75%(CLI 예외 본문 노출 1건 실패), 보완 후 배포·잠금 포함 83/83 = 100%입니다. `URLError`·KeyError·ValueError의 본문이 CLI 로그에 출력되는 기존 결함을 합성 비밀 문자열로 재현하고 산출물과 CLI가 같은 오류 요약 함수를 쓰도록 보완했습니다. 복구 실패 시 원인 보존·DB committed 유지·성공 산출물 부재, KeyboardInterrupt의 실패·원상복구, preflight의 recovery 부재를 검증했습니다.

현재 필수 contract/security/DoD 관문은 자체 PG55741·mock 모델에서 실행 중입니다. 실행 원문·RED/GREEN·사본·PG 자료를 `C:/_proj/eksreview1029/`에 보존합니다. 다른 세션의 PG·서비스는 건드리지 않습니다.

EKS 직접 읽기 접근은 제공되지 않았습니다. 공개 health·기존 GitHub 산출물은 현재 pod/RDS/실제 접수 지연의 직접 증거가 아닙니다. 기존 합성 verify3초/recovery130초는 계측 분리 시험값이며 운영 전후 수치가 아닙니다. 신규 운영 성능 전후 측정은 없고 개선율 분모 모름입니다. 사용자는 EKS 배포를 승인했으며, 실제 통합은 최신 main·전체 CI·기존 digest/백업/복구 관문이 안전한 경우에만 진행합니다.


## 로컬 관문 완료·PR 검증 대기

필수 관문 3/3 = 100%: contract 368/368, security 125/125, DoD 26/26. 실패·skip 0이며 변경 파일 및 저장소 전체 ruff·diff 공백 검사가 성공했습니다. 자체 PG55741은 종료했고 연결 거절을 확인했습니다. 초기 Git 실행은 기본 실행 파일 접근 거절로 실패해 세션별 MinGit PATH를 사용했습니다. PR 준비 중 pathspec의 cwd 오류 1회도 보존했으며 root 기준으로 수정한 뒤 커밋·푸시에 성공했습니다. Git 기본 인증 도구의 접근 거절은 기존 gh 로그인 값을 프로세스 환경에만 전달해 해결했고 값은 출력·파일 저장하지 않았습니다.

[PR #108](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/pull/108), 후보 `12ff75af82133def1dfab9c426ac10b117c184d0`. 3경로(deploy/aws_cd.py, 배포 시험, operations/aws-main-cd.md)만 담았습니다. role-manager/develop에는 푸시하지 않았습니다. 전체 Linux CI는 `40744188210`에서 진행 중이며 main 병합·운영 배포는 아직 없습니다.

AST 비교로 gate·publish·verify·public_health·pause_worker·migration_job·check_database_backup·require_clean_jobs·wait_for_rollout 9/9 = 100% 동일함을 확인했습니다. DB SQL·환경·권한·실행 앱 코드는 변경하지 않았습니다. 실제 EKS의 현재 설정을 읽어 검증했다는 뜻은 아닙니다. 실제 배포는 기존 CD가 현재 main, 백업, migration 결과, digest·준비 상태를 확인하는 조건입니다.

기존 계산 후보의 원측정 30쌍을 다시 집계해 mixed_walk 평균 감소율 -0.9506849268%를 재현했습니다(음수는 느려짐). n 변환 기록은 180,063 검사 중 mismatch_count 351이고 별도 예시 5건만 저장되어 있음을 구분했습니다. 두 후보를 채택하지 않은 판단을 유지합니다. scalar 기존 보고의 로컬 성능을 EKS 전체 접수 속도로 일반화하지 않습니다.

[현재 집계](../evidence/2026-10-29_eks-cd-diagnostics-independent-review/local-summary.json) · [검토 후보 패치](../evidence/2026-10-29_eks-cd-diagnostics-independent-review/reviewed-candidate.patch). 원문 시험·실패·성공 로그, XML, 사본 및 pgdata는 `C:/_proj/eksreview1029/`에 보존합니다. 성능 전후 실측은 새로 만들지 않았습니다.


03:30 KST 후속: PR108 필수3/3=100% 성공. Linux 아키텍처170/170=100%, 전체시험13,322/13,788=96.62%(skip466·실패0), 원문 로그 보존. 최신 base20c296e77·head12ff75af 재확인 및 보호규칙 적용 후 main `5041362ba678271fcb856f5dade91775799711ed`에 병합했습니다. main push CI40745686436 진행 중이며 EKS CD 성공·반영 완료는 아직 주장하지 않습니다. 이전 절의 PR 진행 중 상태는 당시 기록입니다.

증거 보존 범위 정정: PR 준비 첫 git-add 실패(exit128)는 도구 응답·예외 추적으로 확인되지만 같은 로그 이름의 재실행으로 최초 stderr 파일은 남지 않았습니다. root 경로를 CS cwd에서 넘긴 harness 오류였고 수정 후 커밋에 성공했습니다. 이후 실행 helper는 기존 로그가 있으면 attempt별 새 파일을 만들도록 보완했습니다. 제품 RED/GREEN·시험 XML·원측정 자료는 별도 파일 그대로 보존되어 있습니다. 별도 provenance 스크립트의 첫 호출 인자 TypeError도 harness 오류이며, 인자 수용 보정 후 main 누출/후보 비노출 양쪽 실패종료1을 확인했습니다.

main CI40745686436 완료: 필수3/3=100%, Linux 아키텍처170/170=100%, 전체시험13,322/13,788=96.62%(466skip·실패0). Docker checkout 지연 뒤 정상 성공했으며 자동 CD40747516232가 같은 main5041362ba에서 시작했습니다. 원문은 main-ci-complete.log, 상태 snapshot은 release-status-*에 보존합니다. 이 시점은 CD 진행 중이며 운영 반영 완료가 아닙니다.


## 최종 결과 — 2026-10-28T18:54:38.328054+00:00

**승인된 진단 변경의 EKS 자동 CD가 성공했습니다.** 팀 main `5041362ba678271fcb856f5dade91775799711ed`는 최종 ls-remote에서도 일치했습니다. PR108에서 검증한 후보와 병합 main의 전체 트리 diff는 0입니다. [main CI](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40745686436)와 [CD](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40747516232)가 같은 SHA에서 success입니다. main/develop/role-manager에 직접 push하거나 보호 검사를 우회하지 않았고, 검증된 PR의 main 병합을 사용했습니다. 개인 원격 main 반영을 주장하지 않습니다.

새로 다운로드한 CD 산출물은 SHA·4앱 digest/ready **4/4 = 100%**, API/worker digest 동일, 공개 `/health`·`/` **2/2 = 100%**, DB 복구 시각·migration job·단계 시간 형식을 확인했습니다. 이는 **CD 러너가 클러스터를 읽어 작성한 기록을 검증한 증거**입니다. 이 PC에서 EKS pod/RDS를 직접 조회한 증거는 없습니다. 별도 비인증 공개 GET은 **2/2 = 100%**입니다. 공개 건강 응답을 실제 고객·모델·접수 경로의 성공으로 확대하지 않습니다.

실패 단계 시간/복구 시간 분리와 CLI 예외 본문 비공개가 이번 반영 내용입니다. 네트워크 재시도·timeout·DB forward-only·CAS 복구·OIDC 권한·앱 실행 코드는 바꾸지 않았습니다. 실제 운영 장애를 주입하거나 복구 시간을 재지 않았습니다. `failed_at`은 기존 산출물 작성 시각이며, 강제 종료/SIGKILL 등 기록을 남길 수 없는 상황까지 검증한 것은 아닙니다.

운영 접수 성능 전후 측정은 **없고 개선율 분모 모름**입니다. scalar 또는 반려 v/n 계산 변경을 이번 배포에 넣지 않았습니다. 향후 성능 귀속은 승인된 EKS/RDS 읽기, 동일 이미지·자료·모델·부하·cold/warm을 맞춘 실험이 필요합니다. 기존 자료만으로 전후 수치를 만들지 않았습니다.

한 일 목록: 이전 후보 검토 → CLI 노출 RED/보완 GREEN → 격리 필수3/3 및 배포83/83 → Linux PR/main 관문 → 보호 PR 병합 → 기존 자동 CD → 새 산출물·공개 GET·main 해시 대조 → wiki 인계와 증거 보존. 원본 제품 코드·다른 작업자 사본·로컬 공유 DB는 직접 변경하지 않았고, 자체 PG55741 종료/연결 거절을 확인했습니다. EKS에서는 승인된 기존 CD가 migration·앱 교체를 수행했으며 운영 DB가 무변경이라고 주장하지 않습니다. 사본·pgdata·원문 로그를 삭제하지 않았습니다. CD 관찰 예약을 해제합니다.

[최종 집계](../evidence/2026-10-29_eks-cd-diagnostics-independent-review/final-summary.json) · [배포 산출물](../evidence/2026-10-29_eks-cd-diagnostics-independent-review/aws-deploy-result.json) · [독립 대조](../evidence/2026-10-29_eks-cd-diagnostics-independent-review/release-verification.json). 원문 CI 로그·실패/성공 시험·추적 snapshot·보존 사본은 `C:/_proj/eksreview1029/`입니다. 루트 보고/인계/색인과 evidence는 로컬 미커밋 묶음이며 후보 제품 3경로는 PR108로 커밋·병합됐습니다.

보안 검증의 범위: CLI 시험은 기존 main 처리 대상인 URLError·KeyError·ValueError의 비공개 본문 처리와 실패 종료1을 확인했습니다. 자체 DeploymentError 문장 형식은 유지합니다. 이것을 모든 종류의 미처리 예외·프로세스 강제 종료·외부 로그 수집기 전체의 비밀정보 비공개 보장으로 확대하지 않습니다. 최종 증거 manifest는 디스크에서 9/9=100% 해시 일치를 재검산했고, 자체 PG55741 연결 거절도 마지막에 재확인했습니다.

---
type: report
title: EKS reader 기존 관측 권한 경계와 오프라인 로그 분리
status: draft
domain: travel
---

# EKS reader 관측 경계 후속

2026-10-29 KST. **운영 원인 미확정·PR110 draft·배포 HOLD를 유지합니다.** 지정 [인계](../../handoff/2026-10-29_eks-reading-fatal-offline-discrimination.md)의 후속입니다. 이번에 확보한 운영 이유 category는 `unavailable`, 사건 수는 `null`입니다. 0건 또는 timeout으로 해석하지 않습니다. 전체 운영 검증 분모 모름.

## 한 일 목록과 확인 범위

- root/cs AGENTS, cs RULE, 양쪽 wiki 색인, 개발 역할, 운영 현황, 배포판 `operations/aws-main-cd.md`, 지정 인계/보고서와 실제 reader·CD 호출 경로를 확인했습니다. coord의 fatal-diagnosis·AWS-direct·R-release·operational·diagnostics-review 알림을 읽었습니다. 과거 AWS-direct의 무효 자격 기록은 현재 모든 조직 권한이 없다는 증거로 사용하지 않았습니다. 다른 작업자 변경·예약·독립 승인 주장은 없습니다.
- 기존 GitHub 인증으로 팀 저장소 main `57f3d2f004d0600f781599a6a92e8691b49bef82`, PR110 open/draft/head `3fda4eee2613d89d56a6d146989de8f96c229852`를 읽었습니다. Git tree 응답은 truncated=false입니다. 원본 Git 명령·설정·색인은 건드리지 않았습니다.
- 활성 workflow **5/5 = 100%**의 main 원문을 메모리에서 검사했습니다. OIDC `id-token: write`는 CD(AWS)의 deploy job에만 있습니다. CD dispatch에는 읽기 전용 입력/분기가 없으며, 현재 main/CI 확인 뒤 ECR 게시·migration·앱 배포로 이어집니다. 다른 CI 4개에는 OIDC 권한이 없습니다. 새 workflow·기존 workflow 편집·dispatch·rerun·임의 코드 삽입은 모두 0입니다.
- 원격 main의 `.github/`와 `final_project_cs/deploy/` 아래 지정 확장자 파일 **39/39 = 100%**를 검사했습니다. cloudwatch/fluent-bit/fluentd/grafana/loki, `logs:FilterLogEvents`, `logs:GetLogEvents`, `pods/log`, `AssumeRoleWithWebIdentity` 문자열 일치는 없습니다. 이는 저장소 해당 범위의 검색 결과이며, live IAM/RBAC·별도 IaC·조직 로그 서비스의 부재나 접근 거부를 증명하지 않습니다. 실제 AWS 역할 ARN·저장소 비밀·변수 값은 조회하지 않았습니다.
- PC의 AWS credentials/config·kube config는 없고 AWS/KUBE/OIDC-request 환경변수도 없습니다(존재 여부만 기록). 연결된 도구 목록에서도 AWS/로그 조회 도구를 찾지 못했습니다. 기존 자격으로 live IAM/RBAC나 로그 서비스 목록을 읽을 출발점은 확인하지 못했습니다. 자격 추출·타 세션 토큰 차용·새 권한 부여는 하지 않았습니다.
- 기존 CD40754585676 artifact metadata에는 해당 SHA의 배포 결과 artifact만 있습니다. CD 코드의 bounded termination-message 읽기는 migration 결과 전용이고 앱의 reader stdout 수집기가 아닙니다. 기존 로그에 실패 시각의 reader 이유가 없다는 앞 세션 결과를 계승하며 이번에 전체 pod 로그나 DB를 새로 수집하지 않았습니다.

## OIDC·로깅 해석

GitHub OIDC는 실행 job의 `id-token: write`와 실행 환경의 요청 경로를 사용합니다. 로컬 GitHub API 읽기 인증이나 workflow 파일에 대한 읽기 권한만으로 AWS 세션을 얻었다고 볼 수 없습니다. [GitHub 공식 OIDC reference](https://docs.github.com/en/actions/reference/security/oidc). 기존 CD를 돌려 자격을 얻는 행위는 이번 무변경 범위를 벗어나므로 실행하지 않았습니다. **권한 거부 응답을 받은 것이 아니라, 허용된 독립 읽기 실행 경로를 찾지 못한 blocker**입니다.

EKS control-plane/audit 로그와 애플리케이션 컨테이너 로그는 다릅니다. reader 이유는 앱 로그이므로 control-plane CloudWatch 그룹만으로 확보된다고 가정하지 않습니다. Container Insights/Fluent Bit 등 기존 앱 로그 수집기의 설치·보존·그룹·읽기 권한은 live 미확인입니다. 새 수집기를 켜거나 유료 Logs Insights 쿼리를 실행하지 않았습니다. [AWS EKS 관측 안내](https://docs.aws.amazon.com/eks/latest/userguide/eks-observe.html), [AWS EKS 로그 유형 안내](https://docs.aws.amazon.com/prescriptive-guidance/latest/implementing-logging-monitoring-cloudwatch/logging-for-amazon-eks.html).

## 새 격리 시험으로 확인한 행동

새 no-hardlinks 사본 `C:/_proj/eksobserve1029/repo`를 배포 SHA에 고정했습니다. 원본·이전 사본은 보존하고 새 사본의 시험 파일만 추가했습니다. 동일 합성 42항목·실제 pipeline/reader/failover를 대역 공급자·가상 시계·socket 연결 차단으로 실행했습니다. 새 로그 단언 probe **7/7 = 100%**, 기존 실패 로그/비밀 비노출 **4/4 = 100%**, 기존 공급자 스트림/종료/SDK 경계 **20/20 = 100%**, 합계 **31/31 = 100%**, 실패/skip 0입니다. [집계](../evidence/2026-10-29_eks-reader-observability-boundary/offline-summary.json)·[파일별 개수](../evidence/2026-10-29_eks-reader-observability-boundary/test-counts.json).

새 probe에서 7개 주입 원인 모두 `op=reader_structured_stream path=none reasons=` 마지막 로그가 정확히 1개 나오고 해당 category가 포함됐습니다. auth/content/connect/timeout은 유료 대역의 failed 로그가 있으나, 예산 거부·외부 대체 꺼짐·서킷 열림은 유료 대역 호출과 failed 로그가 없습니다. 따라서 **`backend=openai failed`만 찾으면 호출 전 차단 3종을 놓칩니다.** 최종 `path=none`의 reason을 먼저 확인해야 합니다. 이 결과는 운영 원인 재현이나 실제 과금 시도 증거가 아닙니다. 시험의 exception·clock 주입은 운영 설정 변경 근거가 아닙니다.

## 검증된 blocker와 다음 작업

1. 지정 합성 진단 창 **2026-10-28 22:09:29–22:12:00 UTC**에 대해, 기존 앱 로그 저장 위치·보존 상태·기존 읽기 principal을 확인할 경로가 미확보입니다. live IAM/RBAC는 미평가입니다. 이 세 가지가 확인되기 전 로그 없음/권한 부족/보존 만료 중 어느 것인지도 확정할 수 없습니다.
2. 이미 권한이 있는 운영 관측 경로에서만 해당 창과 `op=reader_structured_stream`의 최종 `path=none`을 확인합니다. 내보낼 값은 정해진 backend/reason category별 **집계 건수만**입니다. 필요한 연결 근거는 기존 권한 경계 안에서 확인하며 실제 업무 ID는 내보내지 않습니다. 시각만 같다고 원래 합성 사건에 귀속하지 않습니다. 연결 근거가 없으면 창 전체 집계라고 표시합니다. 원문·예외 본문·사용자 입력/모델 출력·키·쿠키·토큰·전체 로그는 받지 않습니다. 알려지지 않은 문자열은 `other`로 정규화합니다. 이 문서는 workflow나 쿼리를 생성/실행하라는 승인이 아닙니다.
3. 최종 category가 budget/external-disabled/circuit-open이면 해당 상태·정책 조건의 기존 기록을 읽고, timeout/auth/connect/content이면 해당 공급자 경계의 기록을 읽습니다. 실패 이유만으로 budget 확대·fallback 활성화·timeout 증가·자격 교체를 적용하지 않습니다. 원인이 식별되면 새 격리 사본에서 실제 조건을 RED로 재현한 뒤 별도 변경 범위를 정합니다.
4. 기존 권한·보존 로그로 불가능하면 blocker를 유지합니다. 새 workflow/권한·수집기·배포로 우회하지 않습니다. 원래 baseline 2/3 review=66.67%, 1/3 fatal=33.33%는 보존합니다. PR110의 query 최적화를 reader 해결로 부르지 않습니다.

실제 모델/provider 호출·새 운영 접수·운영 변경·추가 권한·배포·push·삭제는 모두 **0**입니다. 이번 추가 모델/provider 과금 0이며 이전 비용은 미확보입니다. GitHub/웹 읽기 비용 원장은 조회하지 않았습니다. 파일·사본·시험 XML·실행기는 `C:/_proj/eksobserve1029`에 보존합니다. DB/listener를 만들지 않았습니다. 실행기는 `observe.py`(원격 읽기만), `offline.py`(새 사본 준비 및 pytest)이며 기존 경로 재실행은 덮어쓰기 금지 조건 때문에 새 경로가 필요합니다. 담당은 Codex, 독립 검토자 미배정입니다.

최종 문서 검증: 새 보고/인계/집계의 기존 비밀정보 탐지기 직접 검사 **5/5 = 100%**, 링크·JSON·시험 XML **6/6 = 100%**, 격리 stage diff --check exit0입니다. 추가 cs 전체 추적 파일 보안시험은 11/12 = 91.67%의 완료 점 뒤 마지막 전체 파일 순회가 오래 걸려, 명령·부모 PID를 확인한 이 세션의 PID17596만 중단했습니다. 전체 보안시험 결과는 **미완료**이며 통과로 세지 않습니다. 루트 신규 문서는 별도 직접 검사했습니다. [검증 집계](../evidence/2026-10-29_eks-reader-observability-boundary/final-verification.json). 색인 변경 전 백업은 C:/_proj/eksobserve1029/index-backups, 보고서 검증 전 사본도 같은 작업 폴더에 보존했습니다.

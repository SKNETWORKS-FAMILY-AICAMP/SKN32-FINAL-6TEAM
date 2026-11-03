---
type: report
title: EKS 성능 후속 — 배포 읽기 확인·main 통합 전제·실패 시간 진단
status: draft
domain: travel
---

# EKS 성능 후속 검증

2026-10-29 KST, Codex. 사용자 요청에 따라 루트·CS 규칙과 wiki 목차, 버스 scalar 독립 인계, R/V/Hspeed 및 현재 협업 NOTICE를 확인했습니다. 변경 담당·자체 검토는 이 세션이며 새 독립 검토자 승인을 받았다고 주장하지 않습니다. 작업 사본은 `C:/_proj/eksperf1029/repo`, 원본 제품 코드는 변경하지 않습니다. `_coord/Codex-eks-operational-20261029-NOTICE.md`에 경계를 게시했고 ST4F597의 role-manager 통합 예약을 존중합니다. push·배포·공유 DB 쓰기는 없습니다.

03:00 KST 중간 기록: x600 장부·실행 버전은 scalar 소스 `3e3b4b7b9f`이고 API·웹·관리자 healthy입니다. EKS 마지막 성공 CD는 main `20c296e77`, run `40699378486`입니다. 현재 team main과 role-manager는 각각 전용 34·10커밋으로 갈라졌고 role-manager에는 EKS CD·Dockerfile이 없습니다. 전체 브랜치 덮어쓰기 대신 main 위 작은 패치 통합 검증이 필요합니다.

추가 최적화 두 개를 실험했습니다. 중복 v 변환 제거는 혼합 walk 30쌍에서 평균 -0.95%(95% bootstrap -5.10~2.74%)로 개선을 확인하지 못했습니다. n 비교의 Python float 변환은 신호 NaN 351건에서 경고 동작이 달라져 채택하지 않았습니다. 실패·보류 코드는 scratch에 보존합니다.

확인된 운영 진단 결함을 격리 main에서 수정 중입니다. CD 실패 단계 시간이 복구 시간을 포함하고 네트워크 오류는 이유 유형을 잃습니다. 새 회귀 3개 메서드가 수정 전 실패했고 수정 후 통과했습니다. 가짜 시계로 verify 3초·복구130초인 사례가 종전 verify133초에서 분리됩니다. 재시도·타임아웃·배포 정책은 바꾸지 않습니다. 전체 CD 시험 첫 실행은 Python import 경로 누락 2건이므로 환경을 갖춘 재검증이 남았습니다.

최종 결과·한계·명령·보존 위치는 후속 절에 추가합니다. EKS 전체 접수 속도 개선은 아직 입증되지 않았으며 전체 운영 수락 비율은 분모 모름입니다.


## 최종 판정·환경별 관측 (03:0x KST)

**x600 scalar 자동 반영은 확인했습니다. EKS 접수 지연 개선은 입증하지 못했습니다.** 작은 main 통합 후보와 운영 실패 진단 개선을 격리 구현·검증했고 push·배포는 0입니다. 결과를 재현 가능한 패치로 남깁니다.

x600 첫 관측은 `3e3b4b7b9f`, 후속 메뉴 통합이 자동 반영된 마지막 관측은 `006268853c0d52c8ff926727f4243230738beb98`입니다. 장부·current_tag·API 실행 버전이 일치하고 API·웹·관리자 healthy, worker는 실행 중입니다(health 판정 없음). 실행 컨테이너의 bus_profile.py LF SHA256은 `0644fcd27249240b9c85c8a5e9fe3c7c6cd65e3917d677271f98ac7b262902de`로 검증 scalar 코드와 같습니다. 이 세션은 자동 배포를 시작하거나 설정을 바꾸지 않았습니다. x600 런타임은 Python3.12.16/NumPy1.26.4/x86_64입니다.

x600에서 `tripilot.devroro.click`으로 식별 헤더 `Guguroute-Deployment/1.0`을 붙인 GET은 `/health`, `/`, `/start` 200 및 무인증 `/v1/web/trips`401, **4/4 = 100%**입니다. 기본 Python 헤더로는 전부403이었고 헤더 포함 첫 원격 스크립트는 인용 오류였습니다. 실패 로그도 보존했습니다. 인증·고객 업무·모델 경로 성공으로 넓혀 해석하지 않습니다.

EKS의 별도 도메인 `guguroute.devroro.click`을 이 PC에서 같은 식별 헤더로 GET했습니다. health5회(전부 status=ok), `/`, `/start`, 무인증 여행조회401로 **8/8 = 100%**입니다. health 왕복 중앙값0.090980초, 범위0.082207~0.141143초입니다. 5회 네트워크·건강 점검이며 전후 실험·접수 처리속도가 아닙니다. 새 고객 세션·접수는 만들지 않았습니다.

GitHub API의 최신 성공 CD는 [40699378486](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40699378486), main `20c296e778d74b16808e0e4393bf68c309a689b6`입니다. 해당 실행의 sanitized artifact를 새로 내려받아 digest·ready **4/4 = 100%**, public GET2/2와 verify53.299초를 확인했습니다. 이 값은 10-28 배포 이력이며 현재 pod imageID를 직접 읽은 증거는 아닙니다.

## 최신 브랜치와 실제 EKS 통합 전제

최종 팀 main `20c296e77`, role-manager `006268853c`를 다시 fetch·ls-remote했습니다. 전용 커밋은 main34/role-manager15입니다. 최초 검토 tip5ded90e9 이후의 추가 변경은 메뉴 원문 SQL908·시험·기록이며 버스 소스는 같습니다. ST4F597의 완료·소유 해제 NOTICE도 확인했습니다. 다른 작업자의 사본·DB·프로세스는 변경하지 않았으며 회신을 받았다고 주장하지 않습니다.

role-manager 트리에는 main의 `.github/workflows/cd-aws.yml`, `deploy/aws_cd.py`, `deploy/aws/Dockerfile.api`, migration-job 구성이 없습니다. app/composition·DB migration·Activity 등도 다릅니다. **role-manager 전체 트리로 EKS를 덮으면 안 됩니다.** main에 적용한 버스 파일 차이는 기존 scalar 한 표현식뿐이며 새 의존성·DB 변경은 없습니다. 진단 패치는 별도로 나눴습니다.

| EKS 반영·성능 판정에 필요한 것 | 이번 증거·남은 조건 |
|---|---|
| 소스 경계 | main20c296e77 위 scalar 1표현식 + 선택적 진단17줄, 패치2개 보존. main의 CD·마이그레이션 정책 보존 |
| 런타임·자료 일치 | AWS Dockerfile은 기존 SOURCE_IMAGE 런타임·ASSET_IMAGE 자료를 보존. 실제 실행 전 linux/amd64 Python·NumPy, assets hash, 규칙 버전·부하·CPU 제한을 고정해야 함. 이번 Linux build/run 없음 |
| 로컬 관문 | 아래 main 격리 회귀 통과. 전체 CI(main)·이미지 build 관문을 대신하지 않음 |
| EKS 읽기 권한 | 로컬 aws/kubectl·AWS 설정/credentials·kubeconfig·AWS access-key/web-identity 환경 모두 없음. 과거 x600 자격 실패 기록을 현재 유효성 확인으로 재사용하지 않음. 승인된 읽기 세션의 eks:DescribeCluster, Kubernetes deployments/pods/get/list 및 pods/log 권한 필요 |
| 병목 귀속 | 현재 코드의 `intake stage timing`/`intake prefill timing`을 익명 집계하고 RDS 새 연결·TLS 왕복, DB 연결수·CPU throttling·모델 호출과 맞춰 봐야 함. CloudWatch/RDS 지표 읽기 권한도 필요. 고객 원문·토큰·전체 접수 ID는 공유 증거에 싣지 않음 |
| 전후 성능 실험 | 같은 이미지·자료·규칙·모델·네트워크, cold/warm 분리, 부하·동시성 고정, 균형 AB/BA 회차와 실패·timeout·호출수 보존. 검증된 합성 여행을 격리 환경에서 먼저 실행. 생산 접수 생성은 이번 읽기 범위에서 하지 않음 |
| 릴리스 | 사용자 승인 범위·최신 main 재대조·CI(main/web/admin)와 불변 이미지 digest 관문을 거친 뒤 기존 CD 사용. 이번 main/develop/role-manager push·workflow_dispatch·배포0 |

이 조건 전체의 완료율은 분모 모름입니다. 기본 health는 단순 status=ok여서 감시·이동 graph warmup 완료·RDS/모델 준비를 증명하지 않습니다. 풀링·readiness 변경은 측정 없는 안전한 개선으로 간주하지 않았습니다.

## 이번 구현: 실패 시간과 복구 시간 분리

V의 과거 CD 실패 분석·미반영 후보72ba5ff48를 참고하되 재시도 부분은 가져오지 않았습니다. 새 main 패치는 `failed_monotonic`을 복구 진입 전에 기록하고 artifact의 실패 단계 시간과 `timings.recovery`를 분리합니다. `URLError`는 TimeoutError·ConnectionRefusedError·gaierror·SSLError 등 **이유의 유형만** 보존하며 주소·오류 본문은 넣지 않습니다. 문자열 이유는 기존처럼 URLError만 남깁니다. 성공 경로·복구 정책·timeout·재시도 횟수는 바꾸지 않습니다.

새 회귀3개 메서드는 수정 전 모두 실패(하위 subtest 포함6실패), 수정 후 **3/3 = 100%**입니다. 고정 시계 실험에서 실제 입력은 verify3초+복구130초인데 종전 기록은 verify133초였습니다. 수정 후 verify3·recovery130으로 분리됩니다. 실제 복구 경로 시험도 추가 분리를 확인합니다. **운영 지연130초를 줄인 결과가 아니라 기록의 귀속 오류를 고친 결과**입니다. 이 세션이 구현·검토를 겸했으며 새로운 독립 검토자 승인·실제 실패 배포 수락은 없습니다.

## 새로 실행한 검증

Python3.12.15/NumPy1.26.4 Windows, 전용 PG16.15 `127.0.0.1:55739/eksperf`, dummy/mock 설정·새 여행 seed입니다. 원본 env·개인 키·고객 입력을 복사하지 않았습니다.

| 실행 | 결과 |
|---|---:|
| main 버스 표현식 변경 전 / 후 | 각각34/34 = 100% |
| main 위 독립 의미 동등성: loader·float32 bit·walk·막차 helper | 32,939/32,939 = 100% |
| 실제 ride_estimator·캐시 재생 | 각각1,152/1,152 = 100% |
| 배포·마이그레이션 잠금 회귀 | 79/79 = 100% |
| Mobility 선택 시험 | 1,481/1,607 = 92.16%, skip126·deselected222·실패0 |
| contract (Git PATH 보정 후) | 368/368 = 100% |
| security (Git PATH 보정 후) | 125/125 = 100% |
| DoD 항목 | 26/26 = 100%, 미측정·누락0 |
| 필수 관문 | 3/3 = 100% |
| 변경 파일 ruff F/E9·Git diff 공백 검사 | 각각 exit0 |

Mobility skip은 사본에 없는 공개 시각표·그래프·수집 스크립트 범위입니다. skip을 통과로 세지 않았고 실제 운영 전수 성공을 뜻하지 않습니다. 단위·관문·기존 scalar 회귀가 겹치므로 합산 제품 통과율을 만들지 않았습니다.

초기 contract366통과/2실패·security124통과/1실패는 PATH의 실행 불가 Git(WinError5)로 재현됐습니다. 테스트를 수정하지 않고 명령별 MinGit 경로를 지정한 뒤 두 관문 전체를 다시 통과했습니다. 직접 unittest 첫 전체 실행의53통과/2오류는 app import 경로 누락이며 올바른 pytest환경에서 배포79개가 통과했습니다. Python3.14의 NumPy 부재, 초기 원격 인용 실패, 가상 소스 해시용 스크립트 오류도 scratch에 그대로 남겼습니다.

## 채택하지 않은 계산 후보·재현·인계

`rejected-v-conversion/`은 v를 Python float로 먼저 바꿔 재변환을 없앤 후보입니다. 의미32,939·실제 공개자료50,000cell/480walk는 같았으나 30쌍 혼합 walk 평균 감소 -0.9507%, bootstrap95% -5.1048~2.7404%로 개선 미확인입니다. 기본 NumPy 표본수 비교를 Python float로 바꾼 `rejected-n-conversion/`은 180,063 경계 검사 중 **351건의 신호 NaN 경고 차이**가 있어 보류했습니다. 실제 정상자료 범위 밖 차이라고 무시해 채택하지 않았습니다. 최종 패치에는 두 후보 모두 없습니다.

재현 명령은 scratch의 `validate.py`, `corrected_checks.py`에 환경·순서를 포함해 남겼습니다. 핵심 실행은 main 격리 CS cwd에서 `python -m pytest tests/unit/deploy/test_aws_cd.py tests/unit/core/test_migration_lock_policy.py -q`, Mobility·contract·security, `python -m scripts.verify_dod_v11`입니다. 새 회귀의 RED/GREEN 로그, 모든 실패·성공 JUnit/로그, rejected 코드·fixture, PG data는 `C:/_proj/eksperf1029/`에 보존합니다. 자체 PG는 정확한 pgdata를 지정해 종료했고55739 연결 거부를 확인했습니다. 파일 삭제·다른 프로세스 종료0입니다.

[집계](../evidence/2026-10-29_eks-operational-performance/summary.json) · [main scalar 패치](../evidence/2026-10-29_eks-operational-performance/main-scalar.patch) · [CD 진단 패치](../evidence/2026-10-29_eks-operational-performance/cd-diagnostics.patch) · [EKS 공개 GET 실측](../evidence/2026-10-29_eks-operational-performance/eks-public.json) · [manifest](../evidence/2026-10-29_eks-operational-performance/manifest.json).

공유 증거에는 요약·공개 health 상태·소스 hash·패치만 넣고 원격 접속 스크립트·컨테이너 전체 목록·원시 securityXML·키·고객 자료는 넣지 않았습니다. 원본 제품 파일·색인·sparse 설정·DB·서비스를 변경하지 않았습니다. 커밋·push·EKS배포·유료 호출0입니다. **남은 목표는 Linux/EKS 동일 조건 실험으로 접수 지연 개선을 입증하는 것**이며 현재 분모는 모릅니다.

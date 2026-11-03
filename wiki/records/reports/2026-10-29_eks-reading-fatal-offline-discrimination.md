---
type: report
title: EKS reading_model_failed 오프라인 원인 분리·관측 경계 HOLD
status: draft
domain: travel
---

# EKS 읽기 실패 후속 진단

2026-10-29 KST. **운영 원인은 미확정이며 PR #110 draft·배포 HOLD를 유지합니다.** 새 격리 사본 `C:/_proj/eksfatal1029/repo`에서 배포 main `57f3d2f004d0600f781599a6a92e8691b49bef82`를 대상으로 재현했습니다. 원래 EKS 42항목 기준 review 2/3 = **66.67%**, fatal 1/3 = **33.33%**는 그대로입니다. 별도 진단의 `reading_model_failed`/`model_unavailable`도 원래 회차의 원인을 소급 확정하지 않습니다. 전체 운영 검증 분모는 모릅니다. [집계](../evidence/2026-10-29_eks-reading-fatal-offline-discrimination/final-summary.json).

한 일 목록:

- 원본 root/cs AGENTS·CLAUDE, cs RULE, 양쪽 wiki 색인, 지정 인계·보고서, 역할·현재 배포판 reader 계약과 실제 호출 경로를 확인했습니다. 원본 로컬 코드와 운영판 코드가 달라 운영 SHA의 no-hardlinks 사본을 새로 만들었습니다. 작업자는 Codex이며 독립 검토 승인으로 부르지 않습니다.
- GitHub 읽기 조회로 main·PR110·기존 workflow·최근 CI/CD를 재확인했습니다. PR head `3fda4eee2613d89d56a6d146989de8f96c229852`는 open/draft이며 필수 검사 3/3 = **100%** success입니다. 기존 main/CD40754585676 유지, 병합·배포·push 0입니다.
- CI40775273306·40774763719 및 CD40754585676 로그를 메모리에서 읽고 시험 개수·관측 여부만 보존했습니다. 두 CI는 기존 전체 13,324통과·466skip, 이미지 51통과입니다. 운영 실패 시각의 `path=none reasons`는 이 로그에 없고, CD 성공은 모델 읽기 성공 증거가 아닙니다. 새 CI는 실행하지 않았습니다.
- 배포판의 reader 관련 기존 11개 시험 파일을 실제 재실행해 **215/215 = 100%**, 실패·skip 0을 확인했습니다. SDK timeout/스트림 해제·reader 예산·대체 금지·유료 시간 확보·비밀 비노출·오류 공개 문구 경계를 포함합니다.
- 같은 합성 입력(691자·55줄·7일42항목)을 기존 스크립트의 AST 상수에서만 읽었습니다. 실제 `pipeline.read_source → agent_read.read → FailoverChat.reader_structured_stream`을 가상 시계·공급자 대역으로 실행했고 socket 연결을 거부했습니다. 원인 분리 probe **7/7 = 100%** 통과입니다. 이는 운영 장애 재현 성공률이 아닙니다.
- PR110과 main의 agent_read/pipeline/llm_failover/model_stream/guardrails Git blob은 **5/5 = 100%** 같습니다. 최초 디스크 대 Git blob 비교는 CRLF/LF 때문에 불일치였으며 그 초기 결과를 보존하고 Git blob끼리 다시 비교했습니다. working copy도 CRLF 정규화 후 5/5 일치합니다. query 최적화가 reader 실패를 고쳤다는 주장은 하지 않습니다.
- 최신 coordination 읽기 후 별도 `Codex-eks-fatal-diagnosis-20261029-NOTICE.md`에 범위·HOLD·예약 없음을 기록했습니다. 다른 작업자 트리·DB·프로세스는 변경하지 않았습니다.

## 재현이 분리한 것

| 주입한 오프라인 실패 | 마지막 유료 경로 이유 | 공개 오류 |
|---|---|---|
| 로컬·유료 모두 timeout | timeout | reading_model_failed |
| 로컬 timeout·유료 인증 실패 | auth | reading_model_failed |
| 로컬 timeout·유료 답 내용 오류 | content | reading_model_failed |
| 로컬 timeout·유료 연결 실패 | connect | reading_model_failed |
| 로컬 timeout·reader 예산 거부 | reader_budget_unavailable | reading_model_failed |
| 로컬 timeout·외부 대체 꺼짐 | reader_external_disabled | reading_model_failed |
| 로컬 timeout·유료 서킷 열림 | circuit_open | reading_model_failed |

[재현 행별 기록](../evidence/2026-10-29_eks-reading-fatal-offline-discrimination/failure-discrimination.json). 각 행의 유료 호출은 **대역**이며 실제 모델·외부 공급자 요청은 0입니다. 서로 다른 원인이 같은 코드·고객 문구로 축약됨을 실행으로 확인했습니다. timeout 행에서 local90초 + paid30초 = 가상120초, 그 외 행도 동일한 공개 오류입니다. 별도 운영 진단의 progress17.35초→fatal138.20초 차이120.85초는 reader120초 경계와 비슷하다는 관찰일 뿐, timeout 원인·책임 경로의 확정 근거가 아닙니다. SSE progress는 provider 요청 시작 시각과 같다고 보장되지 않습니다.

배포판은 1800자 청크·reader120초·유료 예비30초를 이미 구현합니다. 이 691자 입력은 첫 묶음 하나에 들어갑니다. 로컬 num_predict3072와 달리 배포판 OpenAI structured_stream 출력 상한은 max(300,3072×4)=12,288입니다. 3,072만 보고 토큰 부족이라고 고치거나 이미 있는 시간 확보 수정을 다시 적용하지 않습니다. 운영 관리자 override·실제 provider 응답/부하·예산 상태는 확인하지 못했습니다.

## 운영 관측 한계와 다음 단계

이 PC에는 `.aws/credentials`, `.aws/config`, `.kube/config`가 없고 AWS/KUBE 환경변수도 없습니다. GitHub 활성 workflow는 기존 CI 4개·CD AWS 1개이며 독립 읽기 관측 workflow는 없습니다. CD는 기존 OIDC 역할로 배포·migration을 수행하는 경로입니다. 로그 확보를 위해 이를 실행하거나 credential을 전용하지 않았고, 권한을 늘리지 않았습니다. 이것은 모든 가능한 조직 관측 경로가 없다는 단정이 아니라 **이번에 확인한 경로의 한계**입니다.

기존 허용된 읽기 관측 경로나 최소 비식별 로그를 사용자에게 요청했습니다. 필요한 범위는 별도 합성 진단의 **2026-10-28 22:09:29–22:12:00 UTC**입니다. `llm_failover op=reader_structured_stream path=none reasons=... seconds=...` 및 같은 창의 `backend=openai failed reason=... detail=... error=... attempt=...`에서 시각과 정해 둔 코드만 받습니다. 고객 본문·키·쿠키·CSRF·업무 ID·전체 pod 로그/DB 덤프는 받지 않습니다. 시각만으로 타 고객 사건을 이 합성 접수에 귀속시키지 말고 기존 허용된 연결 근거가 있어야 합니다. 로그가 없으면 실패 이유를 추정 수정하지 않고 HOLD를 유지합니다.

원인이 확보되면 해당 공급자 예외/시계/예산 조건을 이 사본에 재현하여 RED→수정→GREEN을 증명하고, 영향 계약·보안·DoD 및 최신 main/coord·PR 검사를 다시 확인합니다. 이후 기존 보호 병합·main CI·CD·실제 digest/readiness와 최소 동일42항목 전후 측정을 진행합니다. 원래3회 결과는 역사적 baseline으로 보존하고, 수정 후 baseline/후보 측정은 별도 cohort로 기록합니다. 기존 `merge_when_validated.py`는 원래3회 모두 review를 요구하므로 단순 재시도로 그 입력을 바꾸거나 자동 실행하지 않습니다. 사용자 배포 승인은 유지되지만 검증 조건은 아직 충족되지 않았습니다.

## 비용·보존·재실행

이번 실제 모델/provider 호출 **0**, 추가 운영 합성 접수 **0**, 관련 모델/provider 추가 과금 **0**, 운영 변경·삭제 **0**입니다. 이전 운영7건의 실제 모델/provider 비용은 여전히 미확보이며 0으로 소급하지 않습니다. 새 CI 실행도 0입니다. GitHub 읽기 조회의 요금 원장은 조회하지 않았습니다.

새 사본·probe·XML·로그는 `C:/_proj/eksfatal1029`에 보존합니다. 새 DB/listener·클러스터 리소스는 만들지 않아 종료 대상이 없고, 원래7건 합성 guest와 기존 PG·사본도 그대로입니다. 삭제 승인을 받지 않았으므로 파일 정리는 하지 않았습니다. 원본 제품 코드·Git 설정·색인 변경은 없습니다. 새 보고/증거/인계 및 백업 후 색인 링크만 기록했습니다.

재실행: `python C:/_proj/eksfatal1029/check.py`는 GitHub 읽기와 baseline 시험, `prepare_probe.py`는 대역 probe 준비, `run_probe.py`는 7행 실행입니다. 기존 로그를 xb로 여는 스크립트는 중복 실행 시 덮어쓰기를 거부하므로 새 출력 경로를 먼저 정해야 합니다. 정확 시험 명령·dummy 설정은 check.py/run_probe.py, 결과는 reader-baseline.xml·failure-probe.xml입니다. [인계](../../handoff/2026-10-29_eks-reading-fatal-offline-discrimination.md).

최종 검증: 새 문서/증거를 격리 사본에만 stage하여 기존 추적 텍스트 보안검사 **12/12 = 100%**, diff --check exit0, 링크/JSON/XML 검사 **12/12 = 100%**를 확인했습니다. 최종 원격 읽기에서도 main57f3d2f004d0·PR110 draft/head3fda4eee 유지입니다. 최초 색인 게시 스크립트의 인코딩 이름 오류는 색인 변경 전에 중단됐으며, 기존 백업 동일성을 확인한 후 UTF-8-SIG 이름으로 정정한 별도 스크립트로 완료했습니다. 제품 수정/원인 확정/배포는 하지 않았습니다.

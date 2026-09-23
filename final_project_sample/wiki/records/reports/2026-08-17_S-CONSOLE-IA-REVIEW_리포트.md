# S-CONSOLE IA 검토 리포트

검토일: 2026-08-17  
대상: 개발 콘솔 IA 제안(`/ui/`, `/ui/composer`, `/ui/quality`, `/ui/experiments`, `/ui/sample/*`, `/ui/admin`)

## 결론

제안 IA는 **제작 플랫폼 운영**이라는 목적에 대체로 맞다. 특히 첫 화면을 고객사 CS 처리량이 아니라 “현재 무엇을 조립했고, 검증 상태가 어떠하며, 마지막 실행에서 무엇이 나왔는가”로 바꾸려는 방향은 맞다.

다만 그대로 확정하면 두 가지 문제가 생긴다.

1. `quality`와 `experiments`가 독립 지표 페이지가 되어 프로젝트 구성·구성 버전·실행·증거 사이의 연결이 끊길 수 있다.
2. `/ui/sample/*`로 경로만 옮겨도 해결되지 않는다. 샘플 런타임은 “고객사 운영 UI”가 아니라 **선택한 프로젝트 구성으로 실행한 사례의 검사/재현 영역**이어야 한다.

권장하는 상위 모델은 다음과 같다.

```text
/ui/                         프로젝트 개요·현재 구성·막힘·최근 실행
  ├ /ui/composer              선언을 편집하고 구성 후보를 검증
  ├ /ui/quality               선택한 구성/버전에 대한 DoD·게이트·증거
  ├ /ui/experiments           선택한 실행군의 평가·ablation·방어 지표
  ├ /ui/sample                선택한 실행의 사례·승인·VOC·trace
  └ /ui/admin                 실제 조립 결과·Port·Team·guardrail·런타임 상태
```

핵심은 `quality`/`experiments`/`sample`을 서로 독립적인 제품 메뉴로 보는 것이 아니라, 대시보드에서 `project config → validation/evaluation run → sample runtime`으로 추적 가능한 하나의 흐름으로 만드는 것이다.

## 1. 이 IA가 놓친 축과 반드시 추가할 축

### 반드시 추가할 것

#### 프로젝트 카탈로그·소유권·수명주기

Backstage식 카탈로그는 “서비스 목록”을 복제하라는 뜻이 아니라, 이 저장소에서 **어떤 프로젝트/구성 선언을 현재 운영 중인지** 식별할 수 있어야 한다는 뜻이다. 최소한 다음이 필요하다.

- 프로젝트 이름과 목적/도메인
- 현재 선택된 `config/project.yaml` 및 구성 revision/hash
- 활성 모듈, Team, Port, 비활성 모듈
- 담당자/소유 팀, 상태(`draft`, `validated`, `running`, `blocked`, `retired` 등)
- 마지막 구성 변경과 마지막 검증 시각

현재 `config/project.yaml`은 모듈·Port·Team 선언의 단일 입력이고, Composer는 그 선언을 읽어 화면에 표시한다. 그러나 현재 UI에는 소유권·수명주기·구성 revision을 탐색하는 카탈로그가 없다. 이것은 장식이 아니라 “무엇을 돌리고 있는가”에 답하는 식별 축이다.

#### 구성 버전과 실행(run)의 연결

`agent_runs`에는 `graph_revision`, 상태, 시각이 있고 `llm_calls`에는 prompt FK, provider/model, input/output token, latency, cost가 있다. 따라서 대시보드는 숫자만 보여주지 말고 다음 연결을 제공해야 한다.

```text
구성 revision
  → 검증 결과/증거
  → 평가 run (arm, dataset, prompt snapshot)
  → 샘플 case/trace
```

이 연결이 없으면 “마지막 실행 결과”가 어느 조립 상태에서 나온 것인지 알 수 없어 재현성이 사라진다.

#### 검증 증거의 출처와 판정 상태

DoD는 28개 항목이며, `scripts/verify_dod.py`는 evidence 존재, 재현 블록, 실제 출력, 판정(`통과`, `부분 통과`, `미착수` 등)을 별도로 구분한다. 따라서 Quality 화면에는 단순한 28칸 초록색 카드보다 다음이 필요하다.

- 판정과 증거 완성도 분리
- 실제 출력 링크
- 재현 명령/실행 시각
- 부분 통과·미착수·미작성의 구분
- 어떤 구성 revision과 테스트 결과에 대한 판정인지

이 구분은 이 저장소의 중요한 자산이다. “evidence 파일이 있다”와 “검증이 통과했다”를 합치면 허수 readiness score가 된다.

#### 변경 영향과 회귀

Composer에서 Team/Port/모듈을 바꿀 때 “무엇이 깨질 수 있는가”를 보여주는 축이 필요하다. 최소 구현은 변경 전후 diff와 영향받는 DoD/테스트/평가 run 링크다. 자동 의존성 그래프를 새로 만들 필요는 없지만, `project.yaml` 변경이 어떤 검증을 무효화하는지 표시해야 한다.

#### 런타임 안전 상태

Admin에 이미 outbox `unknown`, `dead_letter`, case 상태 분포, guardrail, Port 구현이 있다. 이것은 단순 운영 통계가 아니라 제작 플랫폼의 **실행 안전 신호**다. 대시보드의 “지금 막힌 것”에는 DoD뿐 아니라 unknown/dead-letter, degraded 실행 차단, 마지막 worker 실패도 포함되어야 한다.

### Backstage/Langfuse에서 가져오되 축소할 것

| 원형 기능 | 이 플랫폼에서의 채택 | 판단 |
|---|---|---|
| Backstage 카탈로그 | 프로젝트/구성 revision/소유자/수명주기/활성 모듈 목록 | 반드시 채택 |
| Backstage scorecard | DoD 28 + 테스트 + 코퍼스 + basement 순수성의 근거 링크형 판정 | 반드시 채택. 단일 점수로 축약하지 않음 |
| Backstage scaffold template | Composer의 프로젝트 선언/검증 흐름 | 부분 채택. 템플릿 마켓플레이스는 과함 |
| TechDocs | `wiki/records/evidence`, handoff, 재현 명령으로의 링크 | 반드시 채택하되 문서 검색 제품으로 키우지 않음 |
| Langfuse trace | run/case/agent task/team task/event를 잇는 trace | 반드시 채택. 현재 case trace를 확장하는 축 |
| Langfuse 비용·토큰·latency | run/모델/prompt별 집계, 실제 비용과 예상 비용 구분 | 반드시 채택 |
| prompt version | prompt FK/version/hash/model family와 run 연결 | 반드시 채택 |
| Langfuse session | 샘플 case 또는 평가 케이스 묶음 | 필요 시 채택. 별도 세션 제품은 불필요 |
| agent graph 시각화 | 구성의 실행순서 구조도와 run trace의 두 층 | 채택. 정교한 실시간 DAG 편집기는 과함 |
| online alerting/SLO | unknown, dead-letter, timeout, gate 실패 등 명시적 blocker | 축소 채택 |
| 사용자·조직·권한 관리 | 현재 플랫폼의 API scope/tenant 경계를 보여주는 읽기 전용 점검 | 새 IAM 제품으로 확장하지 않음 |

특히 prompt version은 “프롬프트 텍스트를 화면에 크게 노출”하라는 뜻이 아니다. prompt의 version/hash와 평가 run을 연결해 재현성을 확보하라는 뜻이다. 비용도 예상치와 mock 실행의 실제 비용을 섞으면 안 된다. 평가 보고서가 실제 mock 외부 호출 0회와 예상 비용을 명시하고 있으므로, UI에도 `실제`, `추정`, `mock`을 명확히 분리해야 한다.

## 2. 대시보드 첫 화면에 와야 할 것

가설인 “지금 조립이 뭐고, 무엇이 막혀 있고, 마지막 실행 결과는?”은 맞다. 다만 빈도와 위험도 기준으로 순서를 다듬으면 다음과 같다.

### 첫 화면의 권장 순서

1. **현재 프로젝트 식별**: 프로젝트명, 구성 revision/hash, 소유자, lifecycle, 마지막 변경 시각
2. **구성 요약**: 모듈 수, 활성 Team 수, Port 구현, 실행순서 구조도, 변경/미검증 배지
3. **지금 막힌 것**: 부분 통과/미착수/미작성 DoD, 실패 테스트, 코퍼스 게이트, unknown/dead-letter, degraded 차단
4. **마지막 검증 및 실행**: 검증 run과 평가 run을 분리해 시각·구성 revision·prompt snapshot·arm 표시
5. **결과 요약**: pass rule 기준 결과, ablation 차이, 방어 지표, 비용/토큰/latency. 단, 실제 측정인지 mock인지 표시
6. **다음 행동**: `Composer에서 변경`, `Quality에서 증거 보기`, `Experiments에서 비교`, `Sample에서 trace 확인`

첫 화면에서 가장 자주 묻는 질문은 다음 네 가지다.

- 지금 어느 프로젝트/구성 revision을 보고 있는가?
- 이 구성이 검증을 통과했는가, 아니면 증거가 부족한가?
- 마지막으로 실행한 것이 정확히 어떤 구성·prompt·dataset인가?
- 사람의 판단 또는 조치가 필요한 blocker가 남아 있는가?

따라서 “최근 실행 결과”만 크게 두는 것보다 **결과의 provenance와 blocker를 먼저** 보여주는 편이 낫다. 현재 `/ui/cases`의 승인 대기·에스컬레이션 요약은 샘플 런타임에는 유용하지만, 플랫폼 랜딩의 1순위 질문은 아니다.

## 3. `/ui/sample/*` 분리 검토

분리하는 것이 맞다. 현재 `cases`, `approvals`, `voc`, `trace`는 모두 샘플 런타임을 관찰하거나 조작하는 화면이고, Composer/Admin은 제작 플랫폼 자체를 다룬다. 현재 서버도 `/`를 `/ui/cases`로 보내고, 네비게이션에 Cases/Approvals/VOC/Admin/Composer를 동급으로 섞고 있다. 이 구조는 고객사 운영 화면으로 오해하게 만든다.

다만 경로 이동만으로는 부족하다. `/ui/sample/*`에는 다음 컨텍스트가 항상 보여야 한다.

- 어떤 프로젝트와 config revision의 샘플인가
- 어떤 run/graph revision에 속하는가
- 샘플 데이터인지 실제 tenant 데이터인지
- trace가 case event만 보여주는지, agent/team/LLM 호출까지 포함하는지

권장 하위 구조는 `/ui/sample/cases`, `/ui/sample/cases/{id}`, `/ui/sample/cases/{id}/trace`, `/ui/sample/approvals`, `/ui/sample/voc`다. `approvals`는 샘플 런타임에서 실제 side effect를 일으킬 수 있으므로 “데모 승인”과 “실제 승인”을 혼동하지 않도록 명시해야 한다.

대안으로 `/ui/runtime/*`를 사용할 수 있지만, 이 저장소의 현재 자산이 demo case·VOC·trace 중심이고 “고객사 CS 런타임”이 아니라 검증용 샘플이라는 배경을 반영하면 `sample`이 더 정직하다. 단, 향후 실제 프로젝트별 실행을 관찰할 계획이면 `sample`을 고정 개념으로 만들기보다 `/ui/runs/{run_id}/...`를 내부 링크의 기준으로 두는 것이 확장에 유리하다.

## 4. 이미 있으나 화면에 드러나지 않은 자산

| 저장소 자산 | 화면에서 드러낼 의미 |
|---|---|
| `config/project.yaml` | 현재 조립 선언, 활성 모듈/Port/Team, 구성 revision |
| `config/guardrails.yaml` | 토큰 예산, timeout/retry, daily cost limit, RAG 범위, 보안 scope, 평가 규칙 |
| `wiki/records/evidence/DoD-01~28` | 판정·재현·실제 출력·한계가 있는 검증 증거 |
| `scripts/verify_dod.py` | 28개 판정의 계산 규칙과 테스트 결과 |
| `scripts/check_corpus.py` | 코퍼스 개수·chunk 범위·금지 패턴 등 corpus gate |
| `tests/architecture/` | basement가 도메인에 오염되지 않았는지, 다른 도메인에서 재사용되는지에 대한 순수성 신호 |
| `app/modules/` | 실제 도메인 Team 구현이 basement 바깥에 있다는 모듈 경계 |
| `001_schema`/`002_domain` | run, task, prompt, LLM call, knowledge, feedback report 등 관측 가능한 데이터 모델 |
| `prompts`/`llm_calls` 테이블 및 `app/tools/read_tools.py` | prompt version/hash, provider/model, token, latency, 비용의 provenance |
| `agent_runs.graph_revision` | 실행 당시 그래프 revision 고정과 재현성 |
| `outbox` 상태 | pending/unknown/dead-letter 등 사람이 확인해야 하는 실행 blocker |
| `feedback_analytics_reports` | VOC 배치 결과와 alert의 시간 범위 |
| `eval/reports/` | 540 observations, arm, prompt snapshot, dataset hash, holdout, ablation, 비용/지연 및 한계 |
| `wiki/records/handoff/10` | 이 basement를 실제 서비스가 복사해 사용하는 경계와 소비자 관점 |

여기서 중요한 것은 `eval/reports`를 하나의 “품질 점수”로 합치지 않는 것이다. 해당 보고서는 540 observation이 통제된 mock fixture이고, 실제 외부 LLM 호출·실제 과금·실제 운영 SLA·human intervention·VOC alert precision을 증명하지 않는다고 명시한다. 이 한계까지 UI에서 연결해야 한다.

## 5. 반박해야 할 점과 조정안

### “DoD 28개를 readiness score 하나로 보여주자”는 위험하다

DoD에는 통과, 부분 통과, 미착수, 미작성과 evidence 완성도라는 서로 다른 상태가 있다. 가중치를 임의로 정해 87점처럼 보이면 부분 통과와 미작성의 위험이 가려진다. 상단에는 blocker 목록과 상태 분포를 두고, 점수가 필요하면 계산식·분모·판정 시각·구성 revision을 함께 표시해야 한다.

### “평가 540행의 평균을 최신 품질로 보여주자”는 위험하다

arm, dataset hash, prompt snapshot, holdout 여부, mock/real 실행 여부가 없는 평균은 비교 불가능하다. 최소 표시 단위는 `run + arm + dataset + prompt snapshot`이고, holdout 미사용 및 평가 한계를 바로 열 수 있어야 한다.

### “비용·토큰·latency를 운영 KPI처럼 보여주자”는 위험하다

스키마에는 관측 필드가 있지만 모든 실행에 값이 채워진다는 뜻은 아니다. mock 평가의 p95 latency나 $0 비용을 실제 운영 성능처럼 크게 띄우면 안 된다. `observed`, `estimated`, `mock`, `missing` 상태를 분리한다.

### “Langfuse식 trace를 전부 구현하자”는 과하다

현재 필요한 것은 case event 타임라인을 agent run, team task, prompt/LLM call, evidence와 연결하는 최소 trace다. span 검색, 실시간 tail, 세션 분석, 복잡한 대시보드 builder는 현재 제작 목적의 핵심 질문을 해결하지 않는다.

### “Backstage식 카탈로그를 별도 플랫폼으로 만들자”는 과하다

이 저장소에는 프로젝트 선언이 우선 하나이고, 지금 필요한 것은 그 선언의 소유자·revision·수명주기·검증 상태를 읽는 카탈로그다. 다수 서비스의 검색·템플릿 마켓플레이스·조직 전체 포털까지 확장하면 basement의 범위를 벗어난다.

### “Composer에서 곧바로 변경·배포·실행하자”는 위험하다

Composer는 선언을 조립하는 곳으로 유지하되, 변경 후에는 영향 범위와 검증 필요 상태를 명확히 보여줘야 한다. 검증되지 않은 구성으로 샘플을 실행할 수 있다면 `unvalidated`임을 강하게 표시하고, 실제 side effect가 있는 approval 경로와 분리한다.

### “Admin을 설정 변경 화면으로 키우자”는 과하다

현재 Admin의 강점은 실제 조립 결과와 tenant 범위의 읽기 전용 projection이다. Port/Team/guardrail을 여기서 수정하게 만들면 Composer와 책임이 겹치고 안전 경계가 흐려진다. Admin은 실측·상태·안전 신호에 집중하는 편이 맞다.

## 권장 우선순위

1. `/ui/` 랜딩을 프로젝트 개요로 바꾸고, 현재 config revision·구성 요약·blocker·마지막 run을 연결한다.
2. 기존 cases/approvals/voc/trace를 `/ui/sample/*` 경계로 이동하되 sample/run/revision 표기를 붙인다.
3. `quality`는 DoD 28·tests·corpus·basement gate를 evidence 링크와 함께 제공한다. 점수보다 상태/근거를 우선한다.
4. `experiments`는 평가 run 단위로 arm·dataset hash·prompt snapshot·holdout·ablation·방어 지표·비용/토큰/latency를 표시하고 mock/estimated/observed를 구분한다.
5. 프로젝트 카탈로그의 최소 필드(소유자·lifecycle·revision·마지막 검증)를 추가한다.
6. 이후에만 trace의 agent/team/LLM 세부 연결과 변경 영향 diff를 확장한다.

최종적으로 제안 IA의 방향은 유지하되, 화면의 기준을 “메뉴별 지표”가 아니라 **프로젝트 구성과 그 구성에서 나온 검증·평가·샘플 실행의 추적성**으로 바꾸는 것이 이 저장소에 맞다.

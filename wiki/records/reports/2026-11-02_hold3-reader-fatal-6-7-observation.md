---
type: report
title: HOLD reader fatal #6/#7 관측 증거 — 허용 경로 3종 재확인 (2026-11-02)
status: blocked
domain: travel
impl_scope: 읽기 전용 조사. 제품 코드·설정·workflow·운영·EKS·x600 변경 0. 새 권한·자격 0. push 0.
---

# reader fatal #6/#7 관측 증거 재확인 (2026-11-02)

**결론: BLOCKED.** 이미 허용된 세 경로 어디에도 대상 창 **2026-10-28 22:09:29–22:12:00 UTC**의 운영 reader 경로 이유 코드(`llm_failover op=reader_structured_stream path=none reasons=...`, `backend=openai failed reason=...`)가 없다. 경로별로 0/3 = 0%다. 따라서 #6(관측 확보)은 판별할 수 없다. #7(통합)은 「reader fatal 해소」 전제를 확인할 수 없어 HOLD를 유지한다.

- 수행: 라우팅 세션 36cd5c의 하위 세션. 배정은 총괄 5fbd35ab가 했다.
- 선행 인계:
  - [오프라인 원인 분리](../../handoff/2026-10-29_eks-reading-fatal-offline-discrimination.md)
  - [관측 경계](../../handoff/2026-10-29_eks-reader-observability-boundary.md)
  - [telemetry blocker](../../handoff/2026-10-29_eks-reader-fatal-telemetry-blocker.md): 본문 인코딩이 깨져 `?`로 보인다. 원문은 고치지 않았다.
  - [workstreams 감사 #6/#7](../../handoff/2026-10-30_workstreams-readonly-audit.md)
  - [38개 삭제 후 인계](../../handoff/2026-11-02_proj-root38-post-deletion-handoff.md)

## 대상 창이 무엇인가

이 창은 원래 실패 회차가 아니라 **별도 합성 진단 1회**의 시간이다.

- 별도 진단 1회 `eks42-diagnostic.json`:
  - 시작 `23:09:29+01:00` = 22:09:29 UTC, 결과 수신까지 142.86 s → 약 22:11:52 UTC.
  - 공개 결과: `fatal_code=reading_model_failed`, `fatal_detail_class=model_unavailable`.
  - 이 공개 코드에는 오프라인 원인 7종이 모두 똑같이 접힌다(7/7). 그래서 공개 코드만으로는 원인을 가를 수 없다.
- 원래 3회 `eks42-before.json`의 3회차(fatal):
  - 시작 `23:04:08+01:00` = 22:04:08 UTC, 140.30 s 뒤 종료.
  - **대상 창 밖이다.** 대상 창의 이유 코드를 얻더라도 그것은 진단 회차의 원인일 뿐이다. 원래 3회차의 원인으로 소급하지 않는다(기존 인계와 같은 입장).
- private before JSON은 `wiki/records/evidence/2026-10-29_eks-checking-amd64-validation-and-baseline-fatal/eks42-before.json`·`eks42-diagnostic.json`이다.
  - 시각·상태·이벤트 시점·공개 fatal 코드만 들어 있다. 서버 측 reader 이유 코드는 없다(키 구조로 확인).
  - 정리 칸과 해시 값은 출력하지 않았다.

## 경로별 결과

| # | 경로 | 확인 범위 | 대상 창 reader 이유 코드 |
|---|---|---|---|
| 1 | GitHub Actions 기존 실행 로그 (`SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM`) | 아래 1 참조 | **0/20** |
| 2 | 보존된 eksfatal1029 증거 | 아래 2 참조 | **0** (창은 요청 문구로만 등장) |
| 3 | 이 PC의 로컬 로그 | 아래 3 참조 | **0** |

**1. GitHub Actions 기존 실행 로그**
- 인증: 기존 gh 인증(keyring)으로 읽기만 했다.
- 조회 범위: 2026-10-28 12:00 – 10-29 12:00 UTC에 생성된 실행 20/20 = 100%. 내려받은 로그는 15,766,543 B다.
- 창과 겹치는 실행: 0/20. 마지막 실행은 21:50:43에 시작해 22:03:12에 끝났다.
- 창 이후 생성된 실행: 0건(10-28 22:00 – 11-02).
- artifact: 10-28 12:00 이후 14건이 모두 창보다 먼저 만들어졌다. 마지막은 21:52 UTC다.
- 로그 내용:
  - `llm_failover`/`reader_structured_stream`/`path=none` 패턴은 1건 걸렸다. 런타임 로그가 아니라 커밋 메시지 본문이었다.
  - 창 시각 패턴은 3건 걸렸다. 모두 `+09:00` 커밋 시각(= 13:10 UTC)이라 오탐이다.

**2. 보존된 eksfatal1029 증거**
- `proj-folder-retire-20261031/eksfatal1029`: 94파일, 339,974 B.
- `proj-checkout-archive-20261029c/eksfatal1029__repo`: 18파일, 1,820,883 B.
- 대상 창 문자열이 나오는 곳: 인계·보고서 사본, `final-summary.json`, `publish.py`, `dirty.patch`. 모두 「이 창의 로그를 요청한다」는 문구다.
- `llm_failover` 문자열이 나오는 곳:
  - 오프라인 대역 replay 7개(network_calls=0).
  - 시험 코드·XML.
  - 운영 관측이 아니다.
- private before JSON 2개(위 「대상 창이 무엇인가」 참조): 공개 코드만 있다.

**3. 이 PC의 로컬 로그**
- `wiki/records/evidence/2026-10-29_eks-*` (958파일):
  - 창 시각이 걸린 곳 중 운영 reader 로그는 0이다.
  - `related.xml`에 걸린 시각은 `22:09:51+01:00`인 로컬 pytest 시각(= 21:09 UTC)이라 오탐이다.
  - 나머지는 요청 문구와 진단 JSON이다.
- 보존 tar:
  - 열어서 훑은 것: DB·.git이 아닌 tar 17개. 구성원 12,632개, 텍스트 651개(그중 로그 253개).
  - 이름에 secret/token/cookie/key/auth가 든 구성원 11개는 열지 않았다.
  - 열지 않은 tar: pgdata·dotgit 7개(DB 덤프 금지 규칙). 확장자만 맞고 tar가 아닌 파일 2개.
  - 창 시각 0. `path=none` 7줄은 모두 로컬 pytest 로그다. 내용은 `op=reader_json_stream reasons=ollama:timeout,openai:reader_external_disabled`이고 시각이 없다. 대상 경로(`reader_structured_stream`)와 환경(EKS)이 다르다.
- backups 전체에서 pgdata를 뺀 86,764파일을 전수 grep:
  - `reader_structured_stream … path=none`이 있는 것은 시험 코드·대역·보고서·로컬 pytest뿐이다.
  - 창 시각이 있는 것은 진단 JSON, 클라이언트 측 1줄 요약 `eks42-diagnostic.log`(280 B, reader 이유 코드 0), coord 공지·private coord JSON뿐이다.

## #6/#7 판별

- **#6 관측 확보: BLOCKED.**
  - 허용 경로 3/3을 확인했고, 그중 증거가 있는 경로는 0/3 = 0%다.
  - CI/CD 로그는 빌드·시험·배포 단계 로그만 담는다. 실행 시각도 모두 창 이전이라, 구조적으로 런타임 pod 로그가 들어갈 수 없다.
- **#7 통합: 수락-승인대기 아님 / HOLD 유지.**
  - reader fatal 원인이 미확정이라 RED 재현 조건을 정할 수 없다.
  - PR110 draft·배포 HOLD도 그대로다. 이번에는 원격 PR을 재조회하지 않았다.
- 전체 운영 검증 완료율: 분모 모름.

## 필요한 것 (한 줄)

운영 EKS cs API(reader) pod의 2026-10-28 22:09:29–22:12:00 UTC 앱 로그에서 `llm_failover op=reader_structured_stream path=none reasons=… seconds=…` 줄과 `backend=openai failed reason/detail/error/attempt` 줄의 **이유 코드별 건수만** 비식별 집계 1묶음이 필요하다. 기존 CloudWatch/kubectl 읽기 권한을 가진 팀 AWS·클러스터 운영자가 직접 추출해 전달해야 한다. 원문·ID·키·쿠키는 넣지 않는다.

- 로그 보존 기간은 모름이다. 이미 만료됐다면 그 사실 자체를 기록하고 새 측정 cohort로 넘어가야 한다.

## 지킨 것 / 바이트

- 금지 사항 위반 0건:
  - 새 권한·자격, CD credential 사용, workflow 실행·재실행
  - AWS/kubectl/EKS/x600 접속
  - 고객 로그·DB 덤프
  - 비밀 파일 열람(이름 규칙으로 11개 건너뜀)
  - 키·쿠키·ID 출력·저장
  - push
- 작업 폴더 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/hold3-readerfatal-1102/`:
  - 최대 15,776,459 B / 43파일. 내려받은 CI 로그, 스캔 스크립트, 집계 JSON·TSV다.
  - 고유 결과는 이 보고서에 옮겼고, 폴더는 삭제했다.
- `C:/_proj` 바로 아래에 새 폴더 0개, 격리 사본 0개.
- 새로 만든 파일은 이 보고서 1개다.

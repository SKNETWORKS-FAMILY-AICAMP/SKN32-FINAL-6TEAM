# 릴리스 체크리스트 — RC 선언 전에 확인하는 것

> v5 §20 항목 17(M3 게이트)이 요구하는 문서다.
> **"돌아간다" 와 "내보낼 수 있다" 는 다른 주장이다.** 이 문서는 뒤쪽을 확인한다.
>
> 마지막 갱신: 2026-08-20 · **338 passed, 0 failed**(`-m "not live"`)
> ★이 문서의 "DoD 18/18" 표는 v5 원본 M3 게이트 범위다. v8 확장분(29항목
> 전체)의 현재 판정은 `docs/evidence/DoD-*.md` 개별 파일이 정본이다 —
> 이 문서와 숫자가 안 맞으면 개별 evidence 파일을 따른다.

각 항목은 **재현 명령**과 **합격선**을 함께 적는다.
"확인했다" 는 근거가 아니다 — 명령과 출력이 근거다(`RULE.md` §4.0).

---

## 0. 지금 상태 요약

| | |
|---|---|
| DoD | evidence 18/18 · **통과 16** · 부분통과 2 |
| 게이트 | M1 · M2 · M3 **전부 도달** |
| ★**RC** | **아니다** — §5 의 차단 항목 참조 |

---

## 1. 빌드·테스트

```powershell
python -m pytest tests -q
```
- [x] **172 passed · failed 0 · skipped 0**
- [x] `-m "not live"` 로 실 LLM 호출 1건만 기본 제외 (의도된 설정)
- [x] 4회 연속 동일 결과 — flaky 없음
  (★한 번 있었다: `observed_at` 이 시계에 걸렸다 → `docs/reports/debugs/2026-08-14_시계에_걸린_테스트가_가끔_실패한다.md`)

```powershell
python -m scripts.verify_dod
```
- [x] evidence 18/18, 미작성 0

---

## 2. 안전 (되돌릴 수 없는 것)

- [x] `customer_cases` 를 직접 UPDATE 하는 코드 없음 — `transition_case()` 단일 진입점
- [x] `case_events` append-only (UPDATE/DELETE 없음)
- [x] Team 이 side effect 를 실행하지 않음 — `ActionProposal` 까지
- [x] MCP 3 tool 전부 `mcp:read`, payments/subscriptions 미접근 (DoD-13)
- [x] 동일 요청 10회 → `action_requests` 1행 (DoD-11)
- [x] provider timeout → `unknown`, **자동 재실행 없음** (DoD-11)
- [x] 근거 없는 제안은 승인 버튼이 잠김 + 잠긴 이유 표시
- [x] ★**`unknown` 을 사람이 푸는 운영 절차(화면·런북)** — 2026-08-20 작성 완료.
      `docs/manuals/운영_unknown상태_대응절차.md`. `unknown` 은 `customer_cases`
      상태가 아니라 `outbox.status` 라는 것부터 확인하고, 전용 조회 화면·API가
      없다는 사실도 숨기지 않고 적었다 — SQL로 찾고, `transition_case()` 로
      사람이 명시적으로 `VALID_CALLBACK`/`WAIT_EXPIRED` 를 트리거하는 절차.
      근거: `docs/reports/2026-08-20_S-OPS-UNKNOWN-RUNBOOK_리포트.md`.

---

## 3. 데이터·격리

```powershell
python -m pytest tests/security -q
```
- [x] tenant/customer 격리 — 남의 Case 는 403 이 아니라 **404**
- [x] PII masking 후 저장, LLM 에는 masked 만
- [x] audit log 에 API key 원문·결제 식별자 원문 없음
- [x] 저장소에 키 모양 리터럴 없음 (`publish_public.py` 스캐너가 검사)

---

## 4. 배포 산출물

```powershell
python -m scripts.publish_public          # 검사만
python -m scripts.publish_public --push   # 실제 배포
```
- [x] 공개 대상 183개 · 제외: `docs`·`legacy`·`.agents`·`.claude`·최상위 md(README 제외)
- [x] 스크럽 21개 파일 — 내부 문서 참조·협업 흔적 제거
- [x] 커밋 identity 가 사용자 것 (AI 흔적 0)
- [x] 배포 후 워킹 트리 복구 확인
- [ ] ★**배포용 선언으로 바꾸지 않았다** — 아래 §4-1

### 4-1. 배포 전 선언 변경

- [x] ★**`composer_ui` 자체를 제거함(2026-08-18)** — 토글이 아니라 삭제다.
      `/ui/composer`가 인증 없이 이 앱(고객 접근 가능 포트)에 물려 있던 것을
      실측으로 확인, `app/presentation/ui/composer.py`·라우터 마운트·모듈 선언을
      전부 없앴다(`docs/handoff/09`). 같은 기능은 `final_project_ui`의 인증된
      `/composer/*` 호출로만 제공한다.
- [x] `/ui/composer` 404 확인(경로 자체가 없다)

---

## 5. ★RC 를 막고 있는 것

### 5-1. judge agreement 미측정 (DoD-15)

v5 §15-4 는 judge 판정을 **사람 라벨 20건**과 대조하라고 한다. **하지 않았다.**

기계 검사는 했다 — 540행 전량에서 *근거 없이 grounding 점수를 받은 행 0건*
(`python -m eval.check_judge`, 0 아니면 exit 1). 그러나 이것이 잡는 것은
**judge 가 대놓고 틀리는 경우**뿐이다. 그럴듯하게 틀리는 경우 —
답변이 실제로 옳은지, `correctness`·`safety` 점수가 사람 판단과 맞는지 — 는 여전히 모른다.

> **judge 가 사람과 얼마나 맞는지 모르는 상태에서
> 평가 수치를 근거로 내보낼 수 없다** (`CLAUDE.md` §0.1).

**필요한 것**: golden 20건을 사람이 rubric 대로 채점 → judge 점수와 일치율·Cohen's κ 산출.
1인 환경이라 2인 독립 라벨링 + adjudication 은 불가하므로, 그 한계를 함께 적어야 한다.

### 5-2. 평가 결과의 일반화 한계 (DoD-15 · v5 §15-8)

golden 60건 × 3회는 **방향성과 불확실성**을 말한다. 다음을 증명하지 **않는다**:
- 모집단 일반화 · 장기 drift · 실제 손실률 · SLA

ablation 도 마찬가지다. `no_approval`·`no_feedback_inline`·`no_team_split` 이
차이를 안 보인 것은 **효과가 없다는 뜻이 아니라 이 지표가 재지 않는다는 뜻**이다.

### 5-3. 미해결 (차단은 아님)

- [ ] 마우스 오버 하이라이트가 튀는 UI 버그 — 원인 미특정(2026-08-20 재조사
      시도 — 이 환경엔 브라우저 제어가 없어 재현 자체를 못 함, 소스만으로는
      레이아웃을 바꾸는 hover 규칙 안 보임. `docs/reports/2026-08-20_S-UI-HOVER-JITTER_리포트.md`.
      브라우저 되는 환경에서 재시도 필요)
- [ ] 커밋 ↔ Phase 자동 매핑 없음 (사람이 읽어 대조) — ★부분 진전:
      `scripts/check_release_gate.py`(2026-08-20)가 게이트 통과 여부는
      자동화했으나 커밋↔Phase 매핑 자체는 여전히 수동
- [ ] 스크린샷 증거 `docs/screenshots/` 없음 (텍스트 실측으로 대체)
- [x] ★**실제 결제 provider 어댑터(mock) + timeout→unknown end-to-end 통합테스트**
      (2026-08-20) — `app/infrastructure/messaging/mock_payment_publisher.py`,
      `tests/integration/messaging/test_payment_timeout_unknown.py` 5건 통과.
      진짜 결제 게이트웨이는 아니지만 실제 코드 경로(outbox→worker→unknown→
      운영 절차서의 `transition_case()` 수동 트리거)를 처음부터 끝까지
      완주시켰다. 근거: `docs/reports/2026-08-20_S-PAYMENT-TIMEOUT-MOCK_리포트.md`

---

## 6. 환경 (재현하려는 사람에게)

- **PostgreSQL 은 Windows 서비스가 아니다.** conda env `pgv` 프로세스다.
  재부팅·크래시 후 안 떠 있을 수 있다 (2026-08-16 에도 죽어 있었다).
  ```powershell
  & "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\pg_ctl.exe" -D <pgdata> -o "-p 5433" -l <log> start
  ```
- **Docker 없음.** `docker/compose.yml` 은 재현용으로만 남긴다
- 임베딩 `text-embedding-3-small` = **1536차원**. 모델을 바꾸면 DDL 과 적재분을 함께 바꾼다
- 개발 서버: `.claude/launch.json` 의 `acop-ui` (포트 8041, `--reload`)

---

## 7. 판정

**RC 아님.** §5-1 이 채워지면 다시 판정한다.

세 게이트(M1·M2·M3)가 도달했다는 것과 내보낼 수 있다는 것은 다르다.
게이트는 *기능이 있는가* 를 묻고, RC 는 *그 수치를 믿을 수 있는가* 를 묻는다.

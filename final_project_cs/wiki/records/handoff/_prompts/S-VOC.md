# Codex — 스트림 S-VOC (인라인 분류 + 일일 Feedback Analytics)

## 0. 먼저 읽을 것
1. `RULE.md` §3.2(폴백 금지) §3.3(YAGNI) §3.4
2. `CLAUDE.md` ★§1 — **분류 실패는 조용히 넘기지 않는다**
3. `wiki/records/handoff/06_가드레일_수치.md` **§4 급증 정의** ← 문구 그대로 구현
4. **구현돼 있는 것 (읽어라. 고치지 마라)**: `app/core/contracts.py`,
   `app/domain/events.py`(`EventType.CLASSIFIED` / `CLASSIFICATION_FAILED`, `REQUIRED_PAYLOAD_KEYS`),
   `app/core/transition.py`, `app/infrastructure/db/repository.py`, `app/core/settings.py`
5. `../A-COP_구현계획서_v5.md` §14-3 — 읽기 전용, **수정 금지**

## 1. 소유 범위
```
app/modules/customer_ops/feedback.py
app/application/feedback_job.py
scripts/run_daily_feedback.py
tests/unit/voc/**
wiki/records/reports/ , wiki/records/history/
```
★그 밖 금지. 특히 `app/modules/customer_ops/{billing,technical}.py` 는 **다른 세션 작업 중**이다.
`app/core/**`, `app/presentation/**`, `knowledge/**`, `eval/**` 도 금지.

## 2. 만들 것

### 2-1. 인라인 분류기 (`feedback.py`)
```python
def classify(text: str) -> Classification   # sentiment · intent · issue_code · severity
```
- intent: `billing | technical | other`
- sentiment: `positive | neutral | negative`
- issue_code: 시나리오를 덮는 코드 집합을 정하고 **문서화**하라
  (예: `post_cancel_charge`, `entitlement_mismatch`, `payment_failed`, `login_issue`, …)
- ★**셋 다 나와야 한다.** 하나라도 못 내면 `ClassificationFailed` 예외를 올린다.
  `None`/기본값으로 채우지 마라 (`CLAUDE.md` §1 — 모르면 비워 두고 실패로 표시)
- LLM 을 쓰되 **주입 가능**하게 한다. 테스트는 fake 로 결정적으로 돈다
- ★API 키 없으면 예외. 폴백 금지

### 2-2. 일일 배치 (`feedback_job.py`, `scripts/run_daily_feedback.py`)
```powershell
python -m scripts.run_daily_feedback --date 2026-08-12
```
- 전일 + 직전 7일의 **intent·issue count, negative ratio, unresolved ratio** 집계
- ★급증 정의는 `06` §4 **그대로**:
  `today >= max(5, 1.5*avg7)` **AND** `today - avg7 >= 3`
- ❌ **z-score · embedding clustering · topic modeling 금지** (v5 §3 Out)
- 결과를 `feedback_analytics_reports` 에 저장
  (`UNIQUE(tenant_id, period_start, period_end)` — 재실행 시 갱신)
- alert 는 `outbox` 에 발행한다 (`app/core/transition.py` 의 `OutboxMessage` 형식 참고)
- ★`tenant_id` 조건 없는 집계 쿼리를 만들지 마라

## 3. 테스트 (`tests/unit/voc/`)
1. 분류 3필드가 전부 채워짐 / 하나라도 실패 시 **예외**
2. ★**급증 경계값** — 임계 바로 **아래**는 alert 없음, 바로 **위**는 alert 있음.
   두 조건(비율·절대차)을 **각각** 단독으로 깨는 fixture 도 포함
   (예: `today=5, avg7=4` → 비율은 만족하나 `5-4=1 < 3` → alert 없음)
3. 배치 재실행 시 report 가 **중복 생성되지 않음**
4. 집계에 다른 tenant 데이터가 섞이지 않음
- ★`pytest.skip` 금지. 데이터 없으면 **fail**
- ★테스트 전용 tenant, teardown 에서 삭제. `demo` 를 지우지 마라

## 4. 완료 조건
```powershell
python -m pytest tests -q                       # 기존 78건 통과 + skip 0
python -m scripts.run_daily_feedback --date 2026-08-12
$psql="$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'reports='||count(*) from feedback_analytics_reports"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```
★배치를 **실제로 돌려라.** 돌리지 않고 완료로 보고한 사례가 이미 있었다
(`wiki/records/reports/debugs/2026-08-12_2010_RAG검색이_한번도_동작한적이_없다.md`).

## 5. 리포트
`wiki/records/reports/2026-08-12_S-VOC_리포트.md` — §4 **실제 출력 원문**, issue_code 집합,
급증 판정식과 경계값 테스트 결과. `wiki/records/history/2026-08-12_S-VOC.md` 이력 추가.

## 6. 하지 말 것
- ❌ 분류 실패를 기본값으로 메우기
- ❌ z-score/클러스터링/토픽모델링
- ❌ `tenant_id` 없는 집계
- ❌ `pytest.skip`
- ❌ 소유 범위 밖 수정 / 계획서 수정
- ❌ 배치를 안 돌리고 "동작함"

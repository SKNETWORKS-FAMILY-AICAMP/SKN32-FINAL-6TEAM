# 구현 지시 — 개발 콘솔 P4·P5·P6

## 0. 배경

`/ui/**` 는 **개발 콘솔**이다. 사용자는 고객사가 아니라 **이 제작 플랫폼을 굴리는 우리**다.
`/ops/**` 는 고객사 대시보드(납품되는 제품)이고, 둘은 **보안·정보 경계**로 갈려 있다.

계획서: `wiki/records/plans/2026-08-17_개발콘솔_재설계_실행계획.md`
IA 검토(★네가 쓴 것): `wiki/records/reports/2026-08-17_S-CONSOLE-IA-REVIEW_리포트.md`

이미 끝난 것:
- **P1** 구성 revision — `ProjectConfig.revision` (선언 내용 sha256 앞 12자)
- **P2** 관객 분리 — `/ops` · `/ui`, `console_ui` 모듈, 경계 테스트 5종
- **P3** 대시보드 `/ui/` — `app/presentation/ui/console.py`

현재 **308 passed, 0 failed, skipped 0**.

## 1. 소유 범위

```
app/presentation/ui/console.py      ← 여기에 추가한다
app/presentation/ui/theme.py        ← 컴포넌트가 모자라면 추가만
tests/e2e/**
wiki/records/reports/
```
★금지: `app/core/**`, `app/domain/**`, `app/application/**`, `app/infrastructure/**`,
`app/presentation/api/**`, `app/presentation/ui/routes.py`, `app/composition.py`,
`config/**`, `eval/**`(읽기만), `knowledge/**`, `scripts/**`,
`wiki/records/handoff/**`, `wiki/records/evidence/**`(읽기만), `wiki/records/plans/**`.

## 2. 만들 것

### P4. `/ui/quality`

선택한 구성에 대한 **검증 상태와 근거**.

- DoD 28항목 전체를 **판정별로** 보여준다 (`wiki/records/evidence/DoD-*.md` 를 읽는다)
- 각 항목에 **근거 문서 경로**와, 그 문서가 가진 것을 표시:
  재현 명령 블록 있음/없음 · 실제 출력 있음/없음 · 판정
  (`scripts/verify_dod.py` 가 구분하는 것과 같은 축이다 — **그 파일을 읽어 기준을 맞춰라**)
- 게이트 현황: 테스트 수, `tests/architecture`(basement 순수성), 코퍼스 게이트
  ★**직접 실행하지 마라.** 화면에서 pytest 를 돌리면 안 된다.
  파일에 남은 최신 결과만 읽고, 없으면 **"측정값 없음"** 이라고 적어라

### P5. `/ui/experiments`

평가 실행을 **run 단위**로.

- `eval/reports/*.jsonl` 을 run 별로 요약: arm · dataset · provider · 행수 · ablation flag
- ★비용·토큰·latency 는 `observed` / `estimated` / `mock` / `missing` 을 **구분**해서 표시
- ablation 5종과 방어지표(`eval/datasets/attack_fixtures.jsonl`, `eval/defense_metrics.py`)를 연결
- ★holdout 사용 여부를 표시한다 (`holdout.jsonl` 은 보존 대상이다)

### P6. 최소 trace 연결

`/ui/runs/{run_id}` — 하나의 실행을 따라간다.

```
agent_runs → team_tasks → llm_calls(prompt FK) → case_events
```

★**만들지 마라**: span 검색, 실시간 tail, 세션 분석, 대시보드 빌더.
네가 검토 리포트에서 "과하다" 고 한 것들이다.

## 3. ★반드시 지킬 것 (네가 검토에서 지적한 것들이다)

| 규칙 | 이유 |
|---|---|
| **점수 하나로 뭉치지 마라** | 부분통과·미착수의 위험이 가려진다. 상태 분포 + 항목 목록 |
| **평균을 "최신 품질" 로 내지 마라** | arm·dataset·prompt snapshot 없는 평균은 비교 불가 |
| **mock 을 실제 성능처럼 보이지 마라** | `$0`·`p95` 를 크게 띄우면 거짓이 된다 |
| ★**없는 값을 0 으로 채우지 마라** | 모르면 `missing`·`측정값 없음` 이라고 적는다 |
| ★**조용히 자르지 마라** | N개만 보여주면 "전체 M개 중 M-N개는 화면에 없다" 를 적는다 |
| **관객 경계** | `/ui/**` 는 `theme.CONSOLE_NAV`·`brand="개발 콘솔"`. 고객 메시지 원문 금지 |
| **모듈 경계** | `console_ui: false` 면 새 화면도 **전부 404** 여야 한다 |

## 4. 테스트

`tests/e2e/` 에 추가. ★`pytest.skip` 금지. 실제 LLM·외부 네트워크 호출 금지.

각 화면마다 최소한 이것을 고정하라:
1. `console_ui: false` → **404**
2. 고객사 nav(`/ops/*`)가 섞이지 않는다
3. ★**거짓말 방지** — 없는 값이 0 으로 나오지 않는다 / 절삭을 말한다 / mock 이 표시된다

## 5. 완료 조건

```powershell
python -m pytest tests -q
python -m pytest tests/architecture -q      # ★basement 순수성
```
기대: **308건 이상, 0 failed, skipped 0.**

그리고 ★**실제로 띄워서 보라**:
```powershell
python -m uvicorn app.presentation.api.app:app --port 8055
curl.exe -s http://127.0.0.1:8055/ui/quality
curl.exe -s http://127.0.0.1:8055/ui/experiments
```
★HTTP 200 만 보지 마라. **본문에 무엇이 렌더링됐는지** 확인하고 리포트에 원문을 붙여라.
(이 저장소에서 "4화면 200" 을 통과시키고도 화면이 비어 있던 적이 있다.)
★확인 후 서버를 종료하라.

## 6. 리포트

`wiki/records/reports/2026-08-17_S-CONSOLE-P4P6_리포트.md`
— §5 렌더링 원문, 추가한 테스트, **발견한 결함**, 만들지 않기로 한 것과 그 이유.

## 7. 하지 말 것
- ❌ 화면에서 pytest·평가를 실행
- ❌ 점수 하나로 요약
- ❌ 없는 값을 0 으로
- ❌ 말없이 상위 N개만 표시
- ❌ 소유 범위 밖 수정
- ❌ 기존 테스트 단언을 고쳐서 통과시키기 (화면을 고쳐라)
- ❌ 띄워보지 않고 "완료"

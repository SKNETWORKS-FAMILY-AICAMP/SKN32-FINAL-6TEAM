# 구현 지시 — 개발 콘솔을 별도 설치 대상으로 분리 (안 B)

## 0. 결정

★**(B) 같은 저장소, 별도 패키지·설치 대상.** 네 검토(`wiki/records/reports/2026-08-17_S-DASHBOARD-SPLIT_검토.md`)의
결론을 그대로 채택했다. 별도 저장소(C)는 하지 않는다.

해결하려는 것은 하나다:

> 토글은 **라우트를 끄지만 코드를 지우지 않는다.**
> `console_ui: false` 여도 콘솔 소스·의존성·취약점이 납품 artifact 에 남는다.

그리고 지키려는 것:

> 다섯 내부 형식의 **drift 를 한 저장소에서 CI 로 잡는다.**

현재 **311 passed, 0 failed, skipped 0**.

## 1. 소유 범위

```
app/console/**                  ← ★새로 만든다 (콘솔 코드가 여기로 이사)
app/presentation/ui/__init__.py ← mount 배선만
pyproject.toml 또는 setup.cfg   ← 없으면 만든다 (설치 대상 분리)
tests/console/**  tests/contracts/**  tests/architecture/**
wiki/records/reports/ , wiki/records/handoff/11_*.md
```
★금지: `app/core/**`, `app/domain/**`, `app/application/**`, `app/infrastructure/**`,
`app/presentation/api/**`, `app/presentation/ui/routes.py`(고객사 화면), `app/modules/**`,
`config/**`, `eval/**`(읽기만), `knowledge/**`, `scripts/**`,
`wiki/records/evidence/**`(읽기만), `wiki/records/plans/**`.

## 2. ① 다섯 의존 대상 inventory 를 **고정**한다

콘솔이 실제로 읽는 **필드만** 적는다. 추측으로 넓게 적지 마라 — 코드를 읽고 세라.

| 대상 | 지금 읽는 것 |
|---|---|
| `config/project.yaml` | ? |
| `wiki/records/evidence/DoD-*.md` | ? |
| `eval/reports/*.jsonl` | ? |
| DB | `agent_runs`·`team_tasks`·`llm_calls`·`case_events` 의 **어느 컬럼** |
| composition | ★`/ui/admin` 이 `build_registry()` 를 **호출**한다 (파일 의존보다 강한 런타임 결합) |

`wiki/records/handoff/11_콘솔_읽기_계약.md` 에 표로 남긴다.

## 3. ② 계약 스키마 + fixture

각 대상에 **버전이 붙은 스키마**와 **positive/negative fixture** 를 만든다.

- positive — 지금 형식이 통과한다
- ★negative — **필드를 지우거나 이름을 바꾸면 실패한다**
  (이게 없으면 drift 를 못 잡는다. 이 저장소는 *검사하지 않는 규칙은 지켜지지 않는다* 를 여러 번 겪었다)

`tests/contracts/` 에 둔다. ★**실제 파일·DB 를 읽어** 검사하라 — 스키마끼리 비교하면 의미가 없다.

## 4. ③ 패키지 분리 + ★빌드 테스트

- 콘솔 코드를 `app/console/**` 로 옮긴다 (`console.py`·`composer.py`·콘솔 전용 theme 조각)
- 설치 대상을 나눈다 — 제품은 콘솔 없이 설치되고, 콘솔은 extra 로 붙는다
  (예: `pip install .` vs `pip install .[console]`. 방식은 네가 정하고 리포트에 근거를 적어라)
- ★**빌드 테스트**: 제품 설치 대상에 콘솔 모듈이 **포함되지 않음**을 검사한다.
  "토글이 꺼진다" 가 아니라 **"코드가 없다"** 를 검사해야 한다

## 5. 지켜야 할 경계 (기존 테스트가 이미 강제한다)

| 경계 | 검사 |
|---|---|
| 관객 분리 | `console_ui: false` → `/ui/*` 404, `/ops/*` 200 |
| nav 유출 없음 | 고객 화면에 Composer·Quality 안 보임 |
| PII | 개발 콘솔에 고객 메시지 원문 없음 |
| ★basement 순수성 | `tests/architecture/` — 도메인 어휘 금지 |

★콘솔이 없어도 **제품이 뜬다**는 것을 테스트로 증명하라 —
`app/console` 을 import 할 수 없는 상태에서 `/ops/*` 가 200 이어야 한다.

## 6. 완료 조건

```powershell
python -m pytest tests -q
python -m pytest tests/architecture -q
python -m pytest tests/contracts -q
```
기대: **311건 이상, 0 failed, skipped 0.**

★그리고 **실제로 띄워서** 확인하라:
```powershell
python -m uvicorn app.presentation.api.app:app --port 8056
curl.exe -s -o NUL -w "ui=%{http_code} ops=%{http_code}\n" http://127.0.0.1:8056/ui/
```
확인 후 서버를 종료하라.

## 7. 리포트

`wiki/records/reports/2026-08-17_S-CONSOLE-PACKAGE_리포트.md`
— inventory 결과, 설치 대상 분리 방식과 **왜 그 방식인지**, 빌드 테스트가 무엇을 검사하는지,
§6 출력 원문, **발견한 결함**.

## 8. 하지 말 것
- ❌ 별도 저장소로 나누기 (그건 C 다. 지금 안 한다)
- ❌ 고객사 화면(`/ops`)을 건드리기
- ❌ negative fixture 없이 "계약을 만들었다" 고 하기
- ❌ 토글 검사로 빌드 테스트를 대신하기
- ❌ 기존 테스트 단언을 고쳐서 통과시키기
- ❌ 띄워보지 않고 "완료"

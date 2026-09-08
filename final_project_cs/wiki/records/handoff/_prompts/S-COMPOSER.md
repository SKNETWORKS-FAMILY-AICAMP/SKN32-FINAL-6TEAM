# 구현 지시 — 제작 단계 모듈 구성기 GUI (`/ui/composer`)

## 0. 목적

**운영 화면이 아니라 제작 단계의 구성기**다.
팀 회의 중 Agent Team 이 3개였다가 2개로 줄거나 4개가 될 수 있고,
GraphStore·A2A 같은 기능을 넣고 뺄 수 있어야 한다.
모듈을 추가하면 **배포될 프로젝트 구성에 자리가 생기고**, 세부 구현은 담당 팀이 나중에 채운다.

★**선행 작업이 끝났다.** `config/project.yaml` 이 이미 조립의 **단일 입력**이고
(`app/composition.py` 가 하드코딩 import 없이 선언을 읽는다),
검증기가 4종을 거부한다(중복 team_id / import 불가 ref / 미지원 port / 스키마 오류).

**이 화면은 그 선언을 편집하는 얇은 UI 다.** 조립 로직을 새로 만들지 마라.

현재 기준선: **147 passed, 0 failed, skipped 0**.

## 1. 계약

★먼저 읽어라:
- `wiki/records/handoff/08_모듈_컴포넌트_목록.md` — **무엇이 컴포넌트(선택 불가)/모듈(선택 가능)/Port/인스턴스인지**
- `config/project.yaml` — 현재 선언
- `app/core/project_config.py` — 스키마와 검증
- `app/composition.py` — 선언을 어떻게 쓰는지
- `wiki/records/reports/2026-08-14_모듈구성기_설계검토.md` — 권고안과 위험

## 2. 소유 범위

```
app/presentation/ui/**        (composer 화면 추가)
tests/e2e/**
wiki/records/reports/ , wiki/records/history/
```
★금지: `app/core/**`, `app/composition.py`, `app/domain/**`, `app/modules/**`,
`app/application/**`, `app/infrastructure/**`, `app/presentation/api/**`,
`config/project.yaml`(★화면이 런타임에 쓰는 것은 별개), `config/guardrails.yaml`,
`eval/**`, `knowledge/**`, `scripts/**`, `wiki/records/handoff/**`, `wiki/records/evidence/**`.

## 3. 만들 것 — `/ui/composer`

### 3-1. ★이 화면 자체가 모듈이다

`config/project.yaml` 의 `modules.composer_ui.enabled` 가 **false 면 라우트가 없어야 한다**.
현재 기본값이 `false` 이므로 **기본 상태에서는 404** 다.

★테스트에서 `enabled: true` 로 만든 임시 선언으로 화면을 띄워 검증하라.
★"필요 없으면 안 쓸 수 있게" 가 요구사항이다. 자기 자신을 뺄 수 없는 구성기는 앞뒤가 안 맞는다.

### 3-2. 편집 대상 (읽고 → 고치고 → 검증하고 → 저장)

| 구역 | 조작 |
|---|---|
| **모듈** | `08` §2 의 7종을 체크박스로 on/off |
| **Port** | `08` §3 의 선택지에서 고르기 (미구현 값은 **고를 수 없게** 표시) |
| **Team** | 추가 / 제거 / `active` 토글. `team_id`·`implementation_ref` 입력 |
| **컴포넌트** | `08` §1 의 9종을 **읽기 전용으로 표시** — 왜 못 빼는지 이유와 함께 |

★**컴포넌트를 끌 수 있게 만들지 마라.** 목록에 보여주되 비활성으로 두고 사유를 적어라.

### 3-3. ★저장 전에 반드시 검증한다

- 저장 버튼을 누르면 **`app.core.project_config` 의 검증을 먼저 통과**해야 한다
- 실패하면 **저장하지 않고** 무엇이 왜 틀렸는지 화면에 보여준다
  (예: `team 't1' implementation_ref 'app.nonexistent:Missing' cannot be imported`)
- ★검증 로직을 **여기서 다시 구현하지 마라.** 기존 함수를 호출한다

### 3-4. 미구현 Team 을 안전하게 추가하는 흐름

`08` §6 이 정한 방식이다:
- 새 Team 을 추가할 때 **기본값을 `active: false`** 로 한다
- `active: false` 면 `implementation_ref` 의 import 검사를 **하지 않는다**(이미 그렇게 구현돼 있다)
- 화면에 "미구현 — 등록되지만 라우팅되지 않음" 을 **명시**한다

★이게 "자리만 만들고 세부는 팀이 나중에" 를 안전하게 하는 방법이다.
미구현 Team 이 라우팅되어 Case 가 죽으면 안 된다.

### 3-5. 저장 방식

- 저장 대상은 `config/project.yaml` 이다
- ★**저장 전 원본을 백업**하라 (예: `config/project.yaml.bak`)
- 저장 후 화면에 **적용되려면 재기동이 필요하다**는 것을 알려라
  (선언 캐시가 `mtime_ns` 로 무효화되지만, 이미 조립된 앱은 그대로다)

## 4. 구현 지침

- 기존 `/ui/*` 와 같은 방식(서버 사이드 렌더링 + form). SPA 프레임워크 금지
- ★모듈·Port 선택지를 **하드코딩하지 마라.** `08` 의 정의를 코드가 아는 방식으로 —
  `project_config` 의 스키마/허용값에서 읽어라. 새로 목록을 만들면 두 벌이 어긋난다
- ★PII·API 키를 화면에 노출하지 마라

## 5. 테스트 (`tests/e2e/`)

1. ★`composer_ui.enabled=false`(기본) → `/ui/composer` 가 **404**
2. ★`enabled=true` 인 임시 선언 → **200** 이고 현재 Team 두 개가 보인다
3. ★**잘못된 선언 저장 시도 → 저장되지 않고 오류 메시지**
   (없는 `implementation_ref` 를 `active: true` 로)
4. ★**Team 추가 시 기본 `active: false`** 이고 화면에 "라우팅되지 않음" 이 표시된다
5. ★컴포넌트 9종이 **읽기 전용**으로 표시된다 (끌 수 있는 입력이 없다)
6. 저장 성공 시 `config/project.yaml` 이 갱신되고 백업이 생긴다
   ★**테스트가 실제 `config/project.yaml` 을 망가뜨리면 안 된다** — 임시 경로를 쓰거나 복원하라

★`pytest.skip` 금지. 실제 LLM·네트워크 호출 금지.

## 6. 완료 조건

```powershell
python -m pytest tests -q
python -c "import sys;sys.path.insert(0,'.');from app.core.project_config import load_project_config;print(load_project_config().modules)"
```
기대: **147건 이상, 0 failed, skipped 0**, 선언이 그대로 로드된다.

★테스트 후 `config/project.yaml` 이 **원래 내용 그대로**인지 확인하고 리포트에 적어라.

## 7. 리포트

`wiki/records/reports/2026-08-14_S-COMPOSER_리포트.md` — 화면 구성, 검증 호출 지점,
모듈/Port 선택지를 어디서 읽었는지, §6 출력 원문, `project.yaml` 무결 확인.

## 8. 하지 말 것
- ❌ 컴포넌트를 끌 수 있게 만들기
- ❌ 검증 로직 재구현 (기존 함수 호출)
- ❌ 모듈·Port 목록 하드코딩
- ❌ 검증 실패한 선언을 저장
- ❌ 새 Team 기본값을 `active: true` 로
- ❌ `composer_ui` 가 꺼져 있는데 라우트가 살아 있기
- ❌ 테스트가 실제 `config/project.yaml` 을 훼손
- ❌ 돌려보지 않고 "완료"

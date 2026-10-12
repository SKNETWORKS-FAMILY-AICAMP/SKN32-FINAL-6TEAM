# 구현 지시 — 검증 4종 중 1건이 통과한다 (import 불가 ref)

## 0. 결함

`wiki/records/handoff/_prompts/S-PROJECTYAML.md` §3-3 이 요구한 검증 4종을
Claude 가 독립 검증했다. **3건은 거부되는데 1건이 통과한다.**

```
[거부] 중복 team_id            ProjectConfigError
[★통과함-결함] import 불가 ref
[거부] 미지원 port 값           ProjectConfigError
[거부] 스키마 누락              ProjectConfigError
```

재현:
```python
implementation_ref: "app.nonexistent:Missing"   # 존재하지 않는 모듈
→ load_project_config() 가 통과시킨다
```

★계약 §3-3-2 는 이렇게 정했다:
> `active: true` 인데 `implementation_ref` 가 **import 되지 않는다** → 실패

## 1. 왜 중요한가

이 선언은 곧 **GUI 의 저장 결과물**이 된다.
GUI 에서 존재하지 않는 모듈을 고르거나 오타를 내도 저장이 되고,
**기동 후에야 터진다.** 그때는 어디서 잘못됐는지 추적이 어렵다.

★`RULE.md` §3.2 — 조용히 넘어가지 말고 **명시적으로, 이른 시점에** 실패해야 한다.

## 2. 소유 범위

```
app/core/project_config.py
app/composition.py            (검증 호출 지점이 필요하면)
tests/**
wiki/records/reports/ , wiki/records/history/
```
★금지: `config/project.yaml`(현재 선언은 유효하다), `app/core/contracts.py`,
`app/domain/**`, `app/modules/**`, `app/presentation/**`, `app/infrastructure/**`,
`eval/**`, `knowledge/**`, `config/guardrails.yaml`, `scripts/**`,
`wiki/records/handoff/**`, `wiki/records/evidence/**`, `wiki/records/submission/**`.

## 3. 고칠 것

`active: true` 인 Team 의 `implementation_ref` 를 **실제로 해석**해서 검증한다.

- 형식 검사: `"패키지.모듈:클래스"` 형태인가
- ★**import 가능한가** — 모듈이 있고 그 안에 그 이름이 있는가
- ★**`TeamModule` 계약을 만족하는가** — `manifest` 속성과 `execute` 가 있는가
  (인스턴스화까지 할 필요는 없다. 클래스 수준 확인으로 충분하면 그렇게 하라)

★**Core 격리 주의**: `app/core/project_config.py` 는 `app.modules` 를
**정적 import 하면 안 된다**(`tests/contract/test_core_isolation.py` 가 검사).
`importlib` 로 **동적 해석**하는 것은 격리 위반이 아니다 —
정적 import 문이 없으면 된다. 다만 격리 테스트가 그것도 잡는다면
**해석 책임을 `composition.py` 로 옮기고** `project_config` 는 형식 검사만 하라.
어느 쪽을 골랐는지 리포트에 적어라.

- ★`active: false` 인 Team 은 **import 검사를 하지 않는다.**
  "자리만 만들고 세부는 나중에" 를 위해서다 (`wiki/records/handoff/08` §6)

## 4. 테스트

기존 검증 테스트 옆에 추가:

1. ★`active: true` + 없는 모듈 → **예외**
2. ★`active: true` + 있는 모듈이지만 **없는 클래스명** → 예외
3. ★`active: true` + 있는 클래스지만 `TeamModule` 미충족(`execute` 없음) → 예외
4. ★`active: false` + 없는 모듈 → **통과한다** (검사하지 않는다)
5. 정상 선언(`config/project.yaml`)은 그대로 통과한다

★예외 메시지에 **어느 team_id 의 어느 ref 가 왜 틀렸는지** 담아라.

## 5. 완료 조건

```powershell
python -m pytest tests -q
python -m pytest tests/contract/test_core_isolation.py -q
```
기대: **141건 이상, 0 failed, skipped 0**, 격리 테스트 통과.

그리고 아래로 **4종이 전부 거부되는지** 직접 확인하고 출력을 리포트에 붙여라:
```powershell
python -c "
import sys,pathlib,tempfile; sys.path.insert(0,'.')
from app.core.project_config import load_project_config
base='modules: {vector_rag: {enabled: true}}\nports: {team_executor: local, message_broker: outbox, graph_store: sql}\n'
bad=base+'teams:\n  - {team_id: t1, active: true, implementation_ref: \"app.nonexistent:Missing\"}\n'
p=pathlib.Path(tempfile.mkdtemp())/'b.yaml'; p.write_text(bad,encoding='utf-8')
try: load_project_config(p); print('★통과함-결함')
except Exception as e: print('거부:',type(e).__name__)
"
```

## 6. 리포트

`wiki/records/reports/2026-08-14_S-CONFIGVALIDATE_리포트.md` — 어디서 검증하게 했는지
(`project_config` vs `composition`)와 그 이유, Core 격리를 어떻게 지켰는지, §5 출력 원문.

## 7. 하지 말 것
- ❌ `app/core/` 에 `app.modules` **정적 import**
- ❌ `active: false` 인데 import 검사를 하기
- ❌ 검증 실패를 경고로 낮추기 (예외여야 한다)
- ❌ 기존 테스트 단언 약화
- ❌ 돌려보지 않고 "완료"

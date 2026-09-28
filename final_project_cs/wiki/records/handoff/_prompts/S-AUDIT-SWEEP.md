# 구현 지시 — `app/tools`·`app/infrastructure`·`scripts` 정밀 감사 (발견만, 수정 금지)

## 0. 배경

이 세션에서 Claude 가 수동으로 발견한 결함들의 공통 패턴:

1. **기본값 방치** — `create_action_request(...)` 를 `status` 인자 없이 호출해
   기본값(`proposed`)이 그대로 저장되고, 그 값을 조건으로 삼는 다른 쪽 조회
   (`/ui/approvals` 의 `_actions()`)가 의도치 않게 걸려든다. 두 번 발생했다
   (`app/presentation/api/cases.py` 의 `action.approve`, `case.create` 행).
2. **죽은 코드** — `create_llm_call`/`record_llm_call`/`register_prompt_files`
   가 정의만 있고 실제 호출부가 0건이었다. `wiki/records/handoff/04` 가 "구현됐다"고
   전제한 감사추적 기능이 실은 배선돼 있지 않았다.
3. **문서-코드 불일치** — `wiki/records/handoff/03~08` 이 삭제된 파일 경로·클래스명·
   scope 이름을 그대로 가리키고 있었다(sample→커머스 도메인 마이그레이션 잔재).

`app/core`·`app/domain`·`app/application`·`app/presentation`·`wiki/records/handoff` 는
이번 세션에 이미 훑었다. **아직 정밀하게 안 본 영역**이 `app/tools/`,
`app/infrastructure/`, `scripts/` 다. 같은 세 가지 패턴이 거기 더 있는지 찾는다.

## 1. 소유 범위 (읽기 전용 — 이 작업은 코드를 고치지 않는다)

```
읽기 대상:
  app/tools/**
  app/infrastructure/**
  scripts/**

쓰기 대상 (이것 하나만):
  wiki/records/reports/2026-08-18_S-AUDIT-SWEEP_리포트.md
```

★**절대 금지: 위 "읽기 대상"의 어떤 파일도 수정하지 않는다.** 이번 작업은
발견(finding)만 한다. 고치는 것은 다음 세션에서 Claude 가 각 발견을 검토한
뒤 별도로 계약을 써서 진행한다. 리포트 파일 하나만 새로 만든다.

## 2. 무엇을 찾는가 — 정확히 이 세 가지 패턴만

### 패턴 A — DB row 를 쓰는 함수 호출에서 `status`/`state` 류 인자를 생략해
기본값이 다른 쪽 조회 조건에 의도치 않게 걸리는 경우

`grep -rn "def create_\|def insert_\|def register_" app/infrastructure/db/repository.py`
로 기본값이 있는 함수를 전부 나열하고, 각 호출부(`app/tools/**`, `scripts/**`
포함해서 저장소 전체 `grep -rn "<함수명>("`)가 그 기본값을 의도했는지,
아니면 단순히 인자를 안 줘서 기본값이 새는지 판단한다.

### 패턴 B — 정의는 있지만 실제 호출부가 0건인 함수 (죽은 코드)

`app/tools/**`, `app/infrastructure/**`, `scripts/**` 안에서 정의된 public
함수/클래스 각각에 대해 `grep -rn "<이름>("` 로 저장소 전체(테스트 제외)
호출부를 센다. 0건이면 후보로 기록한다. ★테스트에서만 불리는 것과
런타임 경로에서 전혀 안 불리는 것을 구분해서 적는다 — 후자가 더 심각하다.

### 패턴 C — 옛 구독·청구 도메인 잔재 (문자열·주석·경로)

```
grep -rniE "\bbilling\b|\bsubscription\b|technical_entitlement|entitlement" app/tools app/infrastructure scripts
```
결과 각각이 (a) 의도된 역사적 주석/도메인 교체 설명인지 (b) 실제로 지금도
쓰이는 잘못된 값인지 판정한다. 애매하면 "판정 보류"로 적고 왜 애매한지 쓴다.

## 3. 리포트 형식

`wiki/records/reports/2026-08-18_S-AUDIT-SWEEP_리포트.md` 하나에 발견한 모든 것을
패턴별로 묶어 적는다. 항목마다:

```
- 파일:줄번호
- 패턴 (A/B/C)
- 무엇을 발견했는가 (재현 가능한 grep 명령 또는 코드 인용 포함)
- 왜 문제라고 판단했는가 / 왜 판단을 보류했는가
- 심각도 추정 (근거 포함 — "고객 답변에 영향" vs "운영 신뢰도" vs "코드 위생")
```

**아무것도 못 찾았으면 "0건 발견"이라고 정직하게 쓴다.** 억지로 채우지 않는다
(`CLAUDE.md` §3 — 오진 위에 수정을 쌓지 않는다. 여기서는 "발견 없음 위에
가짜 발견을 쌓지 않는다"로 적용된다).

## 4. 완료 조건

- [ ] `app/tools/**`, `app/infrastructure/**`, `scripts/**` 전체를 패턴 A/B/C 로 훑었다
- [ ] 리포트 파일 하나만 새로 생성했다 (다른 파일은 전혀 건드리지 않았다)
- [ ] `git status --short` 결과가 `wiki/records/reports/2026-08-18_S-AUDIT-SWEEP_리포트.md`
      한 줄(`??`)뿐임을 스스로 확인하고 리포트 맨 끝에 그 출력을 붙인다

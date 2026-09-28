# 구현 지시 — `app/domain`·`app/application`·`eval` 정밀 감사 (발견만, 수정 금지)

## 0. 배경

`wiki/records/reports/2026-08-18_S-AUDIT-SWEEP_리포트.md` 가 `app/tools`·
`app/infrastructure`·`scripts` 를 이미 훑었다(패턴 A/B/C, 결과: A 0건,
B 3건 — 이미 수정됨, C 0건). 이번엔 **아직 정밀하게 안 본** 나머지
런타임 영역을 같은 방식으로 훑는다: `app/domain`, `app/application`,
`eval`. **`app/presentation` 은 이번 범위에서 제외한다**(다른 작업이
그 영역을 동시에 손대고 있을 수 있다 — 건드리지 않는다).

## 1. 소유 범위 (읽기 전용)

```
읽기 대상:
  app/domain/**
  app/application/**
  eval/**

쓰기 대상 (이것 하나만):
  wiki/records/reports/2026-08-18_S-AUDIT-SWEEP-2_리포트.md
```

★**절대 금지**: 위 "읽기 대상"의 어떤 파일도 수정하지 않는다.
`app/presentation/**`, `app/core/**`, `app/modules/**`, `app/tools/**`,
`app/infrastructure/**`, `scripts/**`, `prompts/**` 는 이번 범위 밖이다 —
읽지도 쓰지도 않는다.

## 2. 무엇을 찾는가 — 정확히 이 세 가지 패턴만

### 패턴 A — DB row 를 쓰는 함수 호출에서 `status`/`state` 류 인자를 생략해
기본값이 다른 쪽 조회 조건에 의도치 않게 걸리는 경우

`app/application/**` 에서 `repository.create_*`/`update_*` 류 호출을 전부
찾아, 생략된 키워드 인자가 있으면 그 기본값이 다른 코드(특히
`app/presentation/ui/routes.py::_actions()` 같은 조회부 — 이건 읽기만
해도 된다, 수정은 금지)의 필터 조건과 충돌하는지 판단한다.

### 패턴 B — 정의는 있지만 실제 호출부가 0건인 함수 (죽은 코드)

`app/domain/**`, `app/application/**`, `eval/**` 안에서 정의된 public
함수/클래스 각각에 대해 저장소 전체(테스트 제외) 호출부를 센다. 0건이면
후보로 기록한다. 테스트에서만 불리는 것과 런타임 경로에서 전혀 안
불리는 것을 구분해서 적는다.

### 패턴 C — 옛 구독·청구 도메인 잔재 (문자열·주석·경로)

```
grep -rniE "\bbilling\b|\bsubscription\b|technical_entitlement|entitlement" app/domain app/application eval
```
결과 각각이 (a) 의도된 역사적 주석/도메인 교체 설명인지 (b) 실제로 지금도
쓰이는 잘못된 값인지 판정한다. `eval/datasets/golden.jsonl`·`holdout.jsonl`
은 이미 이번 세션에 커머스 도메인으로 재작성됐다고 알려져 있다 —
그 사실을 재확인하는 선에서 다루고, 다시 전량 재검사하지는 않는다
(시간 낭비다). `eval/runners/`, `eval/stats/`, `eval/*.py` 스크립트
코드 자체에 잔재가 있는지가 이번 패턴 C 의 핵심이다.

## 3. 리포트 형식

`wiki/records/reports/2026-08-18_S-AUDIT-SWEEP-2_리포트.md` 하나에 발견한 모든
것을 패턴별로 묶어 적는다. 항목마다: 파일:줄번호, 패턴, 재현 가능한 근거
(grep 명령/코드 인용), 왜 문제라고 판단했는지 또는 왜 판단을 보류했는지,
심각도 추정. **아무것도 못 찾았으면 "0건 발견"이라고 정직하게 쓴다.**

## 4. 완료 조건

- [ ] `app/domain/**`, `app/application/**`, `eval/**` 전체를 패턴 A/B/C 로 훑었다
- [ ] 리포트 파일 하나만 새로 생성했다 — `app/presentation`·`app/core`·
      `app/modules`·`app/tools`·`app/infrastructure`·`scripts`·`prompts` 는
      전혀 건드리지 않았다
- [ ] 리포트를 저장한 뒤 `git -c safe.directory='C:/Users/playdata2/Documents/final_workspace' status --short`
      를 실행해 그 출력을 리포트 맨 끝에 붙인다. 이 확인이 실패해도
      이미 저장한 리포트는 그대로 남겨 둔다(검증 실패를 이유로 결과물
      자체를 안 쓰고 끝내지 않는다).

# S-MIGRATE-DUPLICATE-GUARD — core/domain 마이그레이션 동명 충돌 가드

## 배경

`acop_basement/infrastructure/db/migrate.py`가 core 마이그레이션
(`acop_basement/infrastructure/db/migrations/`, 패키지 내부)과 domain
마이그레이션(`config/migrations/`, product 쪽)을 파일명 순서로 합쳐서
적용한다(`docs/handoff/10` §1-1). 2026-08-19 버그헌팅 라운드9
(`docs/reports/` 최신 리포트 참고)가 이 코드를 검토하며 발견한 것 —
**두 디렉터리에 우연히 같은 파일명이 생기면 `migrate.py`가 그걸 걸러내지
않고 둘 다 실행한다.** 지금 실제로 충돌하는 파일은 없어서 위험도는
낮다고 판단했지만, 이 프로젝트는 "검사하지 않는 경계는 지켜지지
않는다"를 이미 한 번(도메인 마이그레이션이 basement 패키지 안에 실렸던
사고, `docs/handoff/10` §4) 실측으로 겪었다 — 같은 종류의 재발을 막는
게 이번 스트림의 목적이다.

## 만들 것

`acop_basement/infrastructure/db/migrate.py`의 `main()`이 파일을 합치기
**전에** 두 디렉터리 사이에 동일 파일명이 있는지 검사하고, 있으면 명확한
에러(`RuntimeError` 또는 이 모듈에 새로 정의하는 전용 예외)로 즉시
멈추게 고쳐라. 조용히 둘 다 실행하거나, 조용히 하나만 건너뛰지 않는다
(이 프로젝트의 "조용한 스킵 금지" 원칙 — `CLAUDE.md` §3).

에러 메시지에는 충돌한 파일명과 두 디렉터리 경로를 모두 담아라 — 실제로
이 상황을 만난 사람이 즉시 원인을 알 수 있어야 한다.

기존 동작(정상 케이스 — 지금처럼 파일명이 겹치지 않을 때 core+domain을
파일명 순서로 합쳐 실행하는 것, 반환값·print 메시지 형식)은 그대로
유지해라 — 이 스트림은 **충돌 감지만** 추가한다.

## 테스트

`tests/unit/infrastructure/test_migrate.py`(신규 — 정확한 경로는
`tests/unit/` 아래 이 모듈에 맞는 위치를 실제로 확인해서 정해라):

- 정상 케이스: core/domain에 서로 다른 파일명만 있을 때 합쳐진 파일
  목록이 파일명 순서로 정렬됨을 검증(실제 DB 연결 없이 파일 목록 산출
  로직만 단위로 뽑아 테스트할 수 있게, 필요하면 `main()`에서 "파일 목록
  산출" 부분을 별도 함수로 분리해도 된다 — 다만 `main()`의 기존 시그니처와
  동작은 유지해라).
- 충돌 케이스: `tmp_path`로 만든 임시 core/domain 디렉터리에 같은
  파일명을 넣고, 에러가 발생하며 **DB 연결이 시도되지 않음**을 검증
  (연결 시도 여부는 `get_connection`을 monkeypatch해서 호출 안 됐음을
  확인).

## 하지 말 것

- `config/migrations/`·`acop_basement/infrastructure/db/migrations/`의
  기존 SQL 파일 내용을 건드리지 않는다.
- `acop_basement/infrastructure/db/session.py` 등 다른 모듈을 건드리지
  않는다.
- 파일명 정렬 순서 자체(`key=lambda p: p.name`)는 바꾸지 않는다 — 이번
  스트림은 충돌 감지만 추가한다.

## 검증

```powershell
python -m pytest tests/unit/infrastructure -q  # 실제 경로에 맞게 조정
python -m pytest tests/architecture -q
python -m pytest -q --ignore=tests/integration/rag
```

새 테스트 외 기존 테스트 결과는 이 스트림 전후로 동일해야 한다.

## 만들 것 (리포트)

`docs/reports/2026-08-19_S-MIGRATE-DUPLICATE-GUARD_리포트.md` — 만든/고친
파일, 정상 케이스·충돌 케이스 각각의 실행 예시, 테스트 결과.

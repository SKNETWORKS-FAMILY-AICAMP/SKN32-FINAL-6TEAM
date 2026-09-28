# S-BUGHUNT-08-전체점검 — 샘플 프로젝트 전체 버그·오류 점검 (리포트만, 수정 금지)

## 배경

라운드 1~7 이력(`wiki/records/reports/debugs/2026-08-17_버그사냥_*.md`) — 24건 이상
발견, 12건 이상 수정, 나머지는 버그 아님 확인 또는 문서화 후 보류. 그 이후
이번 세션에서 세 가지가 새로 들어왔고, 그중 두 가지는 이미 검수·수정·커밋까지
끝났다(`git log` 참고):

1. Composer 쓰기채널 v2(JWT 인증, scope 3분화) — 검수 완료, 결함 없음
   (JWT 만료/위조 테스트 누락만 발견해 보강).
2. Response Generation & Review Team(DoD-29) — 검수 중 실제 결함 2건 발견해
   수정(REV 규칙이 고객 원문에 잘못 적용되던 것, 톤 결정 규칙 자체가 빠져
   있던 것).
3. Billing/Technical Team의 `examples/` 분리 — 검수 완료, 죽은 참조 2건
   발견해 수정.

## 이번에도 다르게 한다 — ★고치지 않는다, 보고만 한다

이유는 앞선 라운드와 같다(`RULE.md` §3.6-3). **어떤 파일도 수정하지 않는다.**
새 파일도 만들지 않는다. 결과는 세션 최종 응답(stdout)으로만 낸다.

## ★주의 — 저장소가 지금 다른 세션에 의해 동시에 편집되고 있을 수 있다

`app/composition.py`, `app/presentation/ui/routes.py`,
`app/presentation/ui/theme.py`, `app/presentation/ui/__init__.py`,
`config/project.yaml`, `CLAUDE.md` 등이 이 작업을 시작하는 시점 기준
방금(수 분 이내) 수정된 채로 **아직 커밋되지 않은 상태**다 — `/ui/composer`
HTML GUI 폐기로 보이는 별개 작업이 진행 중인 것으로 추정된다(`app/presentation/
ui/composer.py` 가 이미 삭제돼 있다). 이 파일들은 **지금 이 순간에도 계속
바뀔 수 있다.** 이 파일들에서 발견한 것은 리포트에 "★진행 중인 작업 영역 —
스캔 시점 스냅샷일 뿐, 재확인 필요"라고 반드시 표시하고, 나머지 안정된
코드와 같은 확신 수준으로 보고하지 않는다. `git stash`/`git checkout`/`git
add` 등 이 변경들에 손대는 어떤 git 명령도 실행하지 않는다 — 순수 조회만
한다.

## 스캔 범위 — 저장소 전체, 단 우선순위를 둔다

**1순위 (이번 세션에 새로 생겼거나 가장 최근에 바뀌어 아직 낯선 눈으로
검토된 적 없는 코드)**:

- `app/modules/customer_ops/response_review.py`,
  `response_review_policy.py` — GEN→REV 흐름, 재시도 경계, 톤 결정 규칙
- `app/presentation/composer_auth.py`, `app/presentation/api/composer.py`,
  `app/application/composer_service.py` — JWT 인증·scope·audit 로그·
  registry allowlist
- `app/core/project_config.py` — `KNOWN_IMPLEMENTATION_REFS`,
  `_validate_active_team_implementations()` 의 예외 처리
- `eval/runners/common.py` 의 `examples.customer_ops` import 가 다른 곳에서도
  깨진 참조를 남기지 않았는지(예: `_team_context()` 호출부가 다른 가정을
  하고 있지 않은지)

**2순위 (기존에 여러 번 스캔됐지만, 위 변경들과 상호작용할 수 있는 경로)**:

- `app/application/controller.py` — Team 실행 결과를 `TeamResult` 로 받는
  경로가 `response_review.py` 의 `decisions[]`/`warnings[]` 형태와 실제로
  호환되는지(아직 자동 배선은 안 됐지만, 배선했다고 가정하면 뭐가 깨지는가)
- `app/core/contracts.py` — `TeamResult` 계약이 `extra='forbid'` 인데
  `response_review.py` 가 만드는 `decisions[]` 항목(dict)의 키가 매 분기마다
  달라도(`tone_profile`, `tone`, `first_pass` 등 선택적 키) 문제가 없는지
- `config/guardrails.yaml` 의 `security.composer_jwt_ttl_minutes: 30` 이
  `composer_auth.py` 의 `15 <= ttl <= 60` 범위 검사와 실제로 일치하는지,
  이 값이 바뀌면(예: 10분으로) 서버가 기동 시점에 죽는지 요청 시점에
  죽는지

**3순위 (전체 스윕 — 얕게, 명백한 것만)**:

- 저장소 전체에서 `except: continue`/`except Exception: pass` 류의 조용한
  스킵(CLAUDE.md §3 "조용한 스킵을 만들지 않는다")
- `tenant_id`/`customer_id` 조건 없는 SQL 조회(CLAUDE.md §1 "조건 없는
  조회 쿼리는 그 자체가 보안 결함")
- basement(`app/core`,`app/domain`,`app/application`,`app/infrastructure`,
  `app/presentation`)에 도메인 어휘나 도메인 모듈 import 가 남아 있는지
  (`tests/architecture/test_basement_is_domain_free.py` 가 이미 대부분
  잡지만, 그 테스트의 `DOMAIN_WORDS` 사전 자체가 놓치는 단어가 있는지도
  같이 봐라 — 예: "billing"·"technical" 은 리스트에 없다)

## 찾을 것

라운드 1~7 과 같은 기준(진짜 재현 가능한 결함, 잘못된 근거로 쓴 주석/문서,
문서 간 수치 불일치). **확신 없으면 "의심됨 — 확인 필요"로 표시.** 억지로
개수를 채우지 않는다 — 못 찾으면 못 찾았다고 적는다.

## 만들 것

리포트 하나만, stdout 으로. 형식:

```
### <파일:줄번호> — <한 줄 요약>
- 시나리오: <구체적 입력/상태 → 무엇이 잘못되는지>
- 왜 기존 테스트가 못 잡는가: <이유>
- 재현 시도: <실제로 재현을 시도했다면 그 결과. 못 했으면 "재현 안 해봄, 코드 읽기로만 판단">
- 위험도: 높음 | 보통 | 낮음
- (진행 중인 파일이면) ★진행 중인 작업 영역 — 스캔 시점 스냅샷일 뿐
```

## 완료 기준

이 스트림은 코드를 안 건드린다. `python -m pytest -q --ignore=tests/integration/rag`
는 시작 전과 끝난 후 결과가 같아야 한다(같지 않다면 그건 이 스트림이 아니라
동시 편집 세션 때문일 수 있으니 그 사실만 보고한다).

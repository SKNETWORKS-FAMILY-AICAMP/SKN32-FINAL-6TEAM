# S-COMPOSER-RELOAD-CONTRACT-DESIGN — Composer 적용 → customer-runtime 반영 설계 검토

## 0. 이건 코드 작성이 아니라 **설계 검토**다

★**코드를 만들지 마라.** 이번 산출물은 **설계 문서 하나**다. 근거는
반드시 `파일:줄번호`로 대라. 추측을 사실처럼 쓰지 마라.

## 1. 배경

`docs/plans/2026-08-18_Composer_배포_경계_분리_계획.md` §2가 미확인
항목으로 남겨둔 것 — "Composer 적용(`apply`) 후 실제 서비스 런타임에
반영하는 방법". 2026-08-19에 로컬 Docker 이미지 분리
(`Dockerfile.customer` vs `Dockerfile`, `docker/compose.yml`의
`app-customer`/`app-admin` 서비스)까지 끝나면서 이 질문이 더 이상
추상적이지 않다 — customer-runtime과 composer-control이 이제 **물리적으로
분리된 프로세스**로 뜨므로, 한쪽에서 바꾼 `config/project.yaml`을 다른
쪽이 어떻게 알아채는지가 실제 운영 질문이 됐다.

★이 설계는 **AWS 배포 방식 확정을 기다리지 않는다.** 로컬 두 프로세스든
컨테이너 오케스트레이션이든, "설정이 바뀌었다는 걸 다른 프로세스가 어떻게
아는가"는 배포 대상이 무엇이든 동일한 질문이다 — AWS 구체 사항(ALB,
ECS 등)은 이 설계의 범위 밖이다.

## 2. 지금 코드가 실제로 하는 일 (먼저 확인해라)

- `acop_composer/service.py`(정확한 함수명은 실제로 읽어서 확인해라)의
  `apply_candidate` 류 함수가 `config/project.yaml`을 원자적으로
  교체(`os.replace`)하고 `base_revision` 낙관적 동시성을 검사한다는 것을
  실제로 읽어라.
- `acop_basement/core/project_config.py`의 `load_project_config`가
  `@lru_cache(maxsize=8)`로 `(path, mtime_ns)` 키를 쓴다는 것을 실제로
  읽어라(`mtime_ns`가 캐시 키에 들어있으니, 파일이 바뀌면 mtime도 바뀌어
  **다음 호출**부터는 새 값을 읽는다 — 문제는 "다음 호출이 언제 오는가"다).
- customer-runtime 프로세스(`acop_basement.presentation.api.app:app`)가
  기동 시점에 `load_project_config`를 몇 번, 어느 시점에 호출하는지
  실제로 추적해라(`app/composition.py`의 `build_registry`/
  `build_team_executor`/`build_graph_store`/`build_broker` 각각이 매
  요청마다 다시 부르는지, 기동 시 한 번만 부르고 캐시된 결과를 계속
  쓰는지).

## 3. 검토할 것

### 3-1. 후보 비교

최소 세 가지를 실제 이 코드베이스 기준으로 비교해라 — 각 후보의
**정확도**(반영이 실제로 되는가), **지연**(반영까지 걸리는 시간),
**복잡도**(추가해야 하는 코드/인프라), **실패 시 동작**(반영이 실패하면
무슨 일이 일어나는가 — 조용히 옛 설정을 계속 쓰는가, 명확히 에러를
내는가)을 표로 비교해라.

1. **폴링** — customer-runtime이 주기적으로(예: N초마다) config 파일의
   mtime 또는 revision을 확인해 바뀌었으면 다시 로드. `lru_cache`가
   이미 mtime 기반이라는 것을 활용할 수 있는지, 아니면 캐시를 우회하는
   별도 폴링 루프가 필요한지 실제로 판단해라.
2. **관리 신호(admin-triggered)** — composer-control이 `apply` 성공 후
   customer-runtime에 명시적으로 신호를 보낸다(예: 내부 전용 `POST
   /internal/reload` 엔드포인트, 또는 프로세스 시그널). 이 방식이 두
   프로세스가 물리적으로 분리된 지금 구조(별도 컨테이너)에서 실제로
   구현 가능한 형태인지, 어떤 인증/네트워크 경계가 필요한지 짚어라.
3. **재기동 요구** — 반영에는 항상 customer-runtime 재기동이 필요하다고
   명시적으로 선언하고, `apply` 성공 응답에 "재기동이 필요하다"는 안내를
   포함한다. 자동화하지 않는 대신 정직하게 미반영 상태를 드러낸다.

### 3-2. ★반영 안 됨을 조용히 감추지 않는 설계

이 프로젝트는 폴백·조용한 스킵을 금지한다(`CLAUDE.md` §0.1 "신호 없는
축소는 폴백이다"). 어떤 방식을 고르든, **customer-runtime이 지금 어떤
`revision`으로 떠 있는지 확인할 방법**이 있어야 한다 — 예를 들어
`/health`나 `/introspection`(`acop_basement/introspection/contract.py`
실제 확인)이 현재 로드된 `config.revision`(`ProjectConfig.compute_revision()`,
`acop_basement/core/project_config.py` 실제 확인)을 노출하는지, 노출하지
않는다면 이번 설계에 그 노출을 포함시켜라. **"apply는 성공했는데
customer-runtime은 옛 설정으로 계속 돈다"는 상태가 겉보기엔 정상으로
보이면 안 된다.**

### 3-3. 위험과 반대 의견

★**지금 이 반영 메커니즘을 만들지 않는 게 나은 이유**도 적어라 — 예를
들어 "지금은 로컬 개발 서버 하나만 굴리고, cs도 아직 별도 프로세스로
Composer를 운영하지 않는다"면 지금 구축하는 메커니즘이 실제 운영
경험 없이 만든 추측성 설계가 될 위험이 있다. 이 경우 "지금은 §3-1의
3번(재기동 요구, 자동화 없음)만 채택하고 1·2번은 실제 배포 결정이 나온
뒤로 미룬다"는 결론도 정당하다.

## 4. 산출물

`docs/reports/2026-08-19_Composer_reload_계약_설계검토.md`

구성:
1. 지금 코드가 실제로 하는 일(§2, `파일:줄번호` 근거)
2. 후보 3종 비교표(§3-1)
3. 반영 상태를 조용히 감추지 않는 방법(§3-2)
4. ★반대 의견과 위험(§3-3)
5. **권고**: 지금 채택할 방식(또는 "지금은 재기동 요구만 채택하고
   나머지는 보류") + 채택 시 최소 구현 범위, 보류 시 재검토 트리거

★**"좋습니다"로 끝내지 마라.**

## 5. 소유 범위

```
docs/reports/  (문서 1개만)
```
★그 밖 전부 읽기 전용. `acop_basement/**`·`acop_composer/**`·`app/**`·
`config/**`를 **수정하지 마라.**

## 6. 하지 말 것

- ❌ 코드 작성·수정
- ❌ AWS 인프라(`infra/aws/**`) 언급을 이 설계의 필수 전제로 삼기 —
  이 설계는 AWS 결정과 독립적이어야 한다
- ❌ 근거 없는 비교
- ❌ 반대 의견 생략

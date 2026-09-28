# Golden/Holdout 데이터셋 재작업 논의

작성일: 2026-08-20  
범위: 설계 판단만 다룸. 데이터셋과 코드는 수정하지 않음.

## 결론

현재 데이터셋은 **팀 배정(route/team assignment) 평가에는 그대로 사용할 수 있지만, capability 선택과 capability별 실행·채점 평가에는 그대로 사용하면 안 된다.**

golden 72건이 새 팀 구조에서 모두 라우팅된다는 사실은 `expected_intent`가 새 팀의 `accepted_case_types`와 호환된다는 뜻이다. 그러나 이는 각 case가 올바른 업무 동작으로 실행된다는 뜻은 아니다. 현재 `capability_for()`가 동일한 intent 안에서 capability 접두사의 첫 매치만 선택하므로, 실제 시나리오의 동작이 데이터셋에 명시되지 않은 상태에서는 다음과 같은 문제가 생긴다.

- `g-order`의 `order.create`, `payment.status`, `order.verify`가 모두 `order.verify`로 실행될 수 있다.
- `g-return`과 `g-exchange`의 `return.request`, `refund.calculate`, eligibility 확인이 모두 `return.check_eligibility`로 실행될 수 있다.
- 결과적으로 모델이 올바른 capability를 선택했는지, 해당 capability가 시나리오를 제대로 수행했는지, capability별 오채점이 발생했는지를 평가할 수 없다.

따라서 권고는 다음과 같다.

1. **Golden은 재작업한다.** 기존 `expected_intent`는 팀/업무 영역 수준의 라벨로 유지하고, 각 case의 실제 요구 동작을 나타내는 `expected_capability`를 추가한다.
2. **Holdout은 현재 파일을 수정하지 않는다.** 프로젝트 원칙상 수정 순간 동일한 holdout이 아니게 되므로, 기존 24건은 frozen holdout으로 보존한다.
3. 다만 현재 holdout은 capability가 명시되지 않았으므로, capability-level 점수는 유효한 기준선으로 취급하지 않는다. 당분간은 팀 라우팅이나 capability와 무관한 공통 품질 항목만 평가하거나, 향후 별도 버전의 holdout을 새로 생성한다.
4. 6번째 Catalog&Verification/A2A 팀의 실제 구현과 등록 전에는 현재 재작업 범위에 팀 라우팅 분할을 포함하지 않는다. 대신 다음 데이터셋 버전의 스키마가 `expected_team`과 `expected_capability`를 구분할 수 있도록 설계 원칙만 이번 문서에 남긴다.

## 1. 그대로 사용해도 되는가

### 팀 라우팅 관점

그대로 사용해도 된다. 실측 결과 golden 72건 모두 `registry.resolve(case_type=row["expected_intent"], intent=row["expected_intent"])`에서 성공했으므로, 현재 라벨을 새 5팀 구조에서 팀 배정의 입력으로 사용하는 것 자체는 즉시 깨지지 않는다. holdout도 같은 라벨 체계를 사용한다면 동일하게 **라우팅 호환성 테스트**에는 사용할 수 있다.

다만 이 결과를 “새 구조에 맞게 데이터셋이 완전히 호환된다”로 확대 해석하면 안 된다. 검증된 것은 팀을 찾는 단계이지, 팀 안에서 수행할 구체 동작까지 올바르게 정해지는 단계가 아니다.

### capability 및 채점 관점

그대로 사용하면 안 된다. capability가 시나리오의 핵심 행위라면, 잘못된 capability로 실행된 case의 채점은 적어도 capability-level 평가에서는 무의미하다.

예를 들어 case의 실제 기대 동작이 신규 주문 생성인데 `order.verify`가 실행되면, 다음 두 경우 모두 문제가 된다.

- 실행 결과가 실패하면: 모델이나 실행기가 틀린 것이 아니라 애초에 잘못된 capability가 선택된 결과일 수 있다.
- 실행 결과가 성공하면: 주문 생성이 검증 동작으로 대체되었으므로, 실제 목표를 달성하지 않았는데도 성공처럼 보일 수 있다.

즉 현재 뭉침은 단순한 분류 해상도 부족이 아니라 **평가 대상(task) 자체가 바뀌는 문제**다. 팀 라우팅 점수는 보존되지만, capability 선택 정확도·도구 호출 정확도·시나리오 성공률·세부 채점의 해석 가능성이 손상된다.

`g-exchange`를 `g-return`과 같은 `return` intent로 처리하는 것도 같은 문제를 가진다. 팀 관점에서는 `return_refund`가 맞을 수 있지만, 교환 요청인지 환불 계산인지 자격 확인인지 구분되지 않으면 실제 기대 행동에 대한 평가가 아니다.

## 2. 재작업 방법 비교

### 안 A: `expected_capability` 추가

가장 적절한 최소 침습안이다.

각 case에 실제 시나리오를 근거로 명시적인 capability를 추가한다. 예시는 다음과 같다.

```json
{
  "case_id": "g-order-01",
  "expected_intent": "order",
  "expected_capability": "order.create"
}
```

이 방식의 장점은 다음과 같다.

- 기존 `case_id`, `expected_intent`, 데이터 내용, 팀의 case type 체계를 보존한다.
- 팀 배정(`expected_intent`)과 세부 동작(`expected_capability`)을 명확히 분리한다.
- 첫 매치 순서나 capability 등록 순서에 평가 결과가 좌우되지 않는다.
- capability별 커버리지와 실패율을 집계할 수 있다.
- 향후 팀이 분리되어도 capability 라벨은 비교적 안정적인 평가 축으로 사용할 수 있다.

단, 필드만 기계적으로 채우면 안 된다. 각 case의 본문·기대 응답·도구 호출 요구를 보고 `order.create`, `order.verify`, `payment.status`, `return.request`, `refund.calculate` 등을 판정해야 한다. 현재 자동 라우팅 결과를 정답으로 복사하면 문제를 재생산하게 된다.

또한 capability가 없는 단순 대화형 case가 있다면 임의로 capability를 부여하지 말고, 허용된 값과 예외 규칙을 별도로 정의해야 한다. `expected_capability`는 “현재 구현이 고른 capability”가 아니라 “case가 요구하는 정답 capability”여야 한다.

### 안 B: case_id/intent 세분화

예를 들어 `g-order-verify-01`, `g-order-create-01`처럼 ID 또는 intent를 세분화하는 방식이다. 의미상 분류는 가능하지만 이번 문제의 최소 해결책은 아니다.

- `expected_intent`가 팀 라우팅용 case type인지 세부 작업 intent인지 의미가 흔들린다.
- 기존 집계, 필터, fixture, 문서, 테스트가 case_id 접두사에 의존한다면 연쇄 수정이 필요하다.
- ID에 capability를 넣어도 실행기가 그 값을 명시적으로 읽지 않으면 실제 동작 선택 문제는 해결되지 않는다.
- 나중에 팀 경계와 capability 경계가 다시 바뀔 때 ID가 불필요하게 영속적인 설계 제약이 된다.

따라서 B는 새로운 데이터셋 포맷을 처음부터 설계하거나, ID 자체가 외부 시스템의 안정적인 taxonomy인 경우에만 검토할 만하다. 현재처럼 이미 사용 중인 case_id와 팀용 intent를 보존해야 하는 상황에서는 A보다 변경 폭이 크고 효과가 직접적이지 않다.

### 안 C: 실제 오채점 사례가 나올 때까지 유지

팀 라우팅만 평가하는 것이 목적이라면 단기적으로 가능하다. 그러나 현재 관찰만으로도 capability 오선택이 구조적으로 확정되어 있다. 실제 오채점 사례를 기다리는 것은 “오채점이 발생할 수 있다”를 확인하기 위해 이미 알려진 라벨 손실을 방치하는 셈이다.

특히 평가 데이터가 capability-level 성공률이나 회귀 감지에 사용된다면 C는 권고하지 않는다. 오히려 잘못된 capability로 실행한 결과가 통과하여 문제를 숨길 가능성도 있다.

### 선택

**Golden에는 A를 적용하는 것이 최선이다.** B는 이번 재작업에 포함하지 않고, C는 팀 라우팅만을 의도적으로 측정하는 별도 평가 모드에 한정한다.

재작업 시에는 최소한 다음 검증을 수행해야 한다.

- `expected_capability`가 해당 `expected_intent`/팀에서 허용되는지
- case 본문과 expected capability가 의미상 일치하는지
- 각 capability가 최소 한 건 이상 포함되는지
- 자동 선택 결과와 expected capability가 다른 case를 별도로 보고할 수 있는지
- capability 정답이 없는 case를 명시적으로 표시할 수 있는지

## 3. 6번째 Catalog&Verification/A2A 팀의 범위

이번 재작업에서 6번째 팀의 실제 라우팅 분할까지 선반영하는 것은 미룬다. 아직 팀이 미등록이고 구현되지 않았으므로, 지금 팀을 임의로 추가하거나 `order` case를 두 팀 기준으로 재분류하면 현재 평가와 미래 평가의 경계를 섞게 된다.

다만 “아무 준비도 하지 않는다”는 뜻은 아니다. 이번 golden 재작업에서 `expected_intent`를 팀 이름의 대용으로 확장하지 않고, 다음 세 층을 개념적으로 분리해 두는 것이 중요하다.

```text
case 내용
  └─ expected_capability: order.create / payment.status / catalog.verify ...
       └─ expected_team: 현재 또는 미래의 담당 팀
```

현재는 `expected_team`을 새로 채우는 작업까지 반드시 할 필요는 없다. `order`가 procurement/order/payment 팀으로 가는지 catalog/verification 팀으로 가는지는 6번째 팀의 실제 accepted case types, 우선순위, A2A 계약이 확정된 뒤 결정해야 한다.

권고 시점은 다음과 같다.

- 지금: Golden의 capability 정답을 명시해 세부 동작을 고정한다.
- 6번째 팀 등록 전: 겹치는 `order` 범위, 우선순위, 모호한 case의 처리 규칙을 설계한다.
- 6번째 팀 구현 후: 별도 버전의 routing fixture와 holdout을 만들어 팀 분배를 재검증한다.

이렇게 하면 capability 정답은 유지하면서 팀 배정만 새 topology에 맞게 재평가할 수 있다.

## 4. Golden과 holdout을 다르게 취급해야 하는가

다르게 취급해야 한다.

### Golden

Golden은 정답 기준을 개선하기 위한 관리 데이터이므로 재작업할 수 있다. 이번 경우에는 capability가 실제로 구분되어야 하는데 라벨에 빠져 있어 평가가 불완전하다는 증거가 이미 있다. 따라서 원본의 의미를 바꾸지 않는 범위에서 `expected_capability`를 추가하고, 변경 이력과 라벨링 기준을 기록하는 것이 타당하다.

다만 필드 추가는 스키마 변경이므로, 이전 실행 결과와 새 실행 결과를 무조건 같은 점수로 비교하지 말아야 한다. capability-aware 평가 도입 시점을 버전 경계로 남기고, 가능하면 기존 팀 라우팅 점수와 새 capability 점수를 별도 지표로 보고해야 한다.

### Holdout

현재 24건은 수정하지 않고 frozen 상태로 둔다. `expected_capability`를 추가하는 것처럼 값 자체를 보강하는 작업도 이 원칙 아래에서는 holdout 변경이다. 따라서 “golden과 동일한 수정”을 holdout에 적용할 수 없다.

그 결과 현재 holdout에는 두 가지 사용 한계가 있다.

- 팀 라우팅 회귀를 보는 용도: 계속 사용 가능
- capability 선택/세부 동작의 정답률을 보는 용도: 기대 capability가 없으므로 현재 상태로는 해석 불가

capability-aware holdout이 필요하면 기존 holdout을 고쳐 쓰지 말고, 라벨링 기준과 포맷을 확정한 후 새 holdout 세트를 별도 버전으로 생성해야 한다. 기존 24건과 새 세트를 섞지 말고, 각각의 생성 시점·스키마·측정 목적을 명시해야 한다.

## 최종 권고안

이번 논의의 실행 결론은 다음과 같다.

1. 데이터셋 전체를 새 5팀 이름에 맞춰 case_id까지 재구조화하지 않는다.
2. Golden은 실제 시나리오를 재검토해 `expected_capability`를 추가하는 방향으로 재작업한다.
3. `capability_for()`의 첫 매치 결과를 정답 라벨로 간주하지 않는다. 명시 라벨과 자동 선택의 불일치를 평가 대상으로 남긴다.
4. Holdout 24건은 수정하지 않는다. 기존 holdout은 팀 라우팅용으로 유지하고, capability 평가가 필요하면 새 버전을 만든다.
5. Catalog&Verification/A2A 팀의 팀 분할은 실제 구현·등록 시점으로 미룬다. 이번에는 capability와 team의 개념을 분리하는 설계 원칙만 확정한다.

이 판단은 “라우팅 성공률 100%”를 부정하는 것이 아니다. 현재 데이터셋이 팀 라우팅에는 충분하지만, 세부 capability 평가에는 충분하지 않다는 용도별 결론이다.

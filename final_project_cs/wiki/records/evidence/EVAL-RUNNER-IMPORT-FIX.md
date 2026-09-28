# evidence — `eval/runners/common.py` import 결함 수정

- 실행: 2026-08-17
- 판정: 통과

## 문제

`_team_context()`(`eval/runners/common.py:253-254`, 수정 전)가 이미 삭제된 모듈을
import 하고 있었다:

```python
from app.modules.customer_ops.billing import BillingSubscriptionTeam
from app.modules.customer_ops.technical import TechnicalEntitlementTeam
```

`app/modules/customer_ops/billing.py`·`technical.py` 는 커머스 도메인 마이그레이션
과정에서 각각 `order_shipping.py`(`OrderShippingTeam`)·`return_exchange.py`
(`ReturnExchangeTeam`)로 이름이 바뀌었다(git 이력상 rename). 이 파일은 그 갈아 끼우기
당시 갱신되지 않았다.

## 왜 지금까지 안 걸렸는가

`grep -rln "eval.runners" tests/` 결과 0건 — 이 모듈을 import 하는 pytest 테스트가
**없다.** `--provider openai` 라이브 경로는 사람이 CLI 로 수동 실행할 때만 타므로
`pytest -q -m "not live"` 로는 절대 잡히지 않는다.

## 재현 명령 (수정 전 실패 재현)

```powershell
git show HEAD:eval/runners/common.py | Select-String "BillingSubscriptionTeam"
python -c "from eval.runners import common; common._team_context"
# ImportError: cannot import name 'BillingSubscriptionTeam' from 'app.modules.customer_ops.billing'
#   (billing.py 자체가 존재하지 않음)
```

## 수정

```python
from app.modules.customer_ops.order_shipping import OrderShippingTeam
from app.modules.customer_ops.return_exchange import ReturnExchangeTeam
...
team = OrderShippingTeam if (intent in ("order", "shipping") or "no_team_split" in ablations) else ReturnExchangeTeam
```

라우팅 조건도 함께 고쳤다 — 옛 `intent == "billing"` 는 새 데이터셋에 존재하지 않는
값이라 전부 `else` 분기(`ReturnExchangeTeam`)로 잘못 빠졌을 것이다.

## 검증

```powershell
python -c "from eval.runners import common; print('import ok')"
grep -rln "BillingSubscriptionTeam|TechnicalEntitlementTeam|customer_ops\.billing|customer_ops\.technical" --include="*.py" .
```

```
import ok
./app/modules/customer_ops/order_shipping.py   (docstring 주석뿐, 실제 import 아님)
./app/modules/customer_ops/return_exchange.py  (docstring 주석뿐, 실제 import 아님)
```

실제 코드 경로에 남은 참조 0건. 실 LLM 종단 스모크(`--limit 2 --provider openai`)로
`OrderShippingTeam` 이 실제로 실행됨을 추가 확인(`wiki/records/evidence/DoD-EVAL-DATASETS_검증.md`
"실 LLM 종단 스모크" 절).

## 남은 취약점

이 클래스의 버그(리네임 후 참조 안 고침)를 재발 방지하는 자동 검사가 없다.
`eval/runners/**` 를 import 만 하는 smoke test 하나가 있으면 다음에 같은 실수를
pytest 로 잡을 수 있다. 이번 작업 범위 밖이라 추가하지 않았다 — 별도로 제안한다.

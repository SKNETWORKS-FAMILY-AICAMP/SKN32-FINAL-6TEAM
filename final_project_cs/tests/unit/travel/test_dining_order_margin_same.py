"""원장 파일(`dining/ledger.py`)의 기본 라스트오더 여유가 대체 계산의 탈락 기준과 같다. `[2026-10-05]`

원장 파일은 코어(`replan`)를 import 하지 않는 경계라 값을 따로 들고 있다 — 둘이 어긋나면 원장은 20분이 아닌 값으로 `order_ok` 를 낸다.
"""
import importlib.util
import os

from app.domains.travel_ops.components.planning import replan

LEDGER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                      "app", "domains", "travel_ops", "instances", "dining", "ledger.py")


def test_the_ledger_default_order_margin_equals_the_replan_rule():
    spec = importlib.util.spec_from_file_location("dining_ledger_margin", LEDGER)
    ledger = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ledger)
    assert ledger.DEFAULT_ORDER_MARGIN_MIN == replan.ORDER_MARGIN_MIN

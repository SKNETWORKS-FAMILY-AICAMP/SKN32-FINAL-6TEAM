"""이미 출발 안내가 있어도 고객이 직접 고른 변경은 자동 출발 재탐색과 구별한다."""
import pytest
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.actions.itinerary_actions import ItineraryApply
from .test_departure_atomic_db_v1 import _proposal
from .test_trip_reminders import world  # noqa: F401


@pytest.mark.parametrize('reason', ['customer_request', 'rollback', 'customer_choice'])
def test_customer_chosen_change_keeps_existing_apply_contract(world, reason):
    trip, _, move, arguments = _proposal(world)
    # 보류 제안은 원래 발생 원인을 보존해도 직접 선택한 변경임을 reason으로 구분한다.
    arguments['reason'] = reason
    with get_connection() as conn, conn.transaction():
        world['store'].enqueue_message(conn, trip_id=world['trip_id'], key=f'departure:{move.item_id}',
            payload={'version': trip['version'], 'text': '이미 안내'})
    with get_connection() as conn, conn.transaction():
        result = ItineraryApply().apply(conn, tenant_id=world['tenant'], customer_id=trip['customer_id'],
            case_id=None, arguments=arguments)
    assert result.summary['version'] == trip['version']+1

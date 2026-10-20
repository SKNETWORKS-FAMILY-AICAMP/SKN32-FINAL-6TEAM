"""현재 여행의 지도 선택은 재사용하고 다른 여행의 전용 장소는 제외한다."""
from uuid import UUID

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.intake.pipeline import _our_places
from app.domains.travel_ops.components.intake.reopen_commit import store_place
from app.domains.travel_ops.components.itinerary.itinerary import TripStore
from app.domains.travel_ops.components.conversation.trip_desk import TripDesk
from .test_nambu_progress_web import nambu_scene  # noqa: F401
from .test_decision_unit_web import decided  # noqa: F401
from .test_web_api import api, _fresh_limit_cache  # noqa: F401


def test_current_private_pick_is_found_without_requerying_an_external_provider(nambu_scene, decided):
    scene=nambu_scene
    current=UUID(scene['trip']['trip_id'])
    other=UUID(decided['trip']['trip_id'])
    with get_connection() as conn,conn.transaction(),conn.cursor() as cur:
        own=store_place(conn,cur,scene['tenant'],current,name='현재 여행 직접 선택',kind='activity',
            lat=37.485,lon=127.016,weather_sensitive=False,attributes={'source':'customer_pick','pick_origin':'kakao'})
        foreign=store_place(conn,cur,scene['tenant'],other,name='다른 여행 직접 선택',kind='activity',
            lat=37.49,lon=127.02,weather_sensitive=False,attributes={'source':'customer_pick','pick_origin':'kakao'})
    with get_connection() as conn:
        shared={str(p['place_id']) for p in _our_places(conn,scene['tenant'])}
        scoped={str(p['place_id']) for p in _our_places(conn,scene['tenant'],trip_id=current)}
    assert str(own) not in shared and str(foreign) not in shared
    assert str(own) in scoped and str(foreign) not in scoped
    desk=TripDesk(store=TripStore(scene['tenant']),connection_factory=get_connection,
        edit_lookups=lambda:(None,None,None))
    found=desk.find_place('현재 여행 직접 선택',trip_id=current)
    assert found is not None and found.place_id==str(own)
    assert found.latitude==37.485 and found.longitude==127.016

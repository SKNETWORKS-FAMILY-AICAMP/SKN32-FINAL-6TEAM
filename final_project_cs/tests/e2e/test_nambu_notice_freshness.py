"""발송 직전 대조는 무관한 변경과 해당 안내의 무효화를 구분한다."""
from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.infrastructure.db.session import get_connection
from app.infrastructure.notify.suppressed import NoticeSuppressed
from app.domains.travel_ops.components.itinerary.itinerary import TripStore
from app.domains.travel_ops.components.watch.notice_routing import CustomerNoticeRouter
from .test_nambu_progress_web import nambu_scene, at  # noqa: F401
from .test_decision_unit_web import decided  # noqa: F401
from .test_web_api import api, _fresh_limit_cache  # noqa: F401


@pytest.mark.parametrize('change', ['unrelated', 'retimed', 'completed'])
def test_notice_matches_its_items_even_after_a_new_trip_version(nambu_scene, monkeypatch, change):
    scene=nambu_scene
    store=TripStore(scene['tenant'])
    trip_id=UUID(scene['trip']['trip_id'])
    with get_connection() as conn,conn.transaction():
        trip,items=store.latest(conn,trip_id)
        target=items[-1]
        payload={'type':'guidance','kind':'next_item','version':trip['version'],
            'item_id':str(target.item_id),'text':'유효한 일정 안내',
            'schedule_basis':[{'item_id':str(target.item_id),'starts_at':target.starts_at.isoformat(),
                               'ends_at':target.ends_at.isoformat()}]}
        if change=='unrelated':
            items=[replace(i,title='다른 일정의 설명 변경') if i.item_id==items[0].item_id else i for i in items]
        elif change=='retimed':
            items=[replace(i,starts_at=at('22:15')) if i.item_id==target.item_id else i for i in items]
        else:
            items=[replace(i,detail={**i.detail,'execution':{'state':'completed'}})
                   if i.item_id==target.item_id else i for i in items]
        store.append_version(conn,trip_id=trip_id,base_version=trip['version'],items=items,
                             reason='test_setup',causes=[])
    sent=[]
    router=CustomerNoticeRouter(operator=lambda _m:None,connection_factory=get_connection,
        enabled=lambda:True,renderer=SimpleNamespace(text_for=lambda p:p['text']))
    monkeypatch.setattr(router,'_destination',lambda *a:(None,'discord','unused',None))
    monkeypatch.setattr(router,'_send_discord',lambda *a:sent.append(a[-1]))
    message={'topic':'trip.notice','tenant_id':scene['tenant'],'dedupe_key':f'{trip_id}:pending',
             'payload':payload}
    if change=='unrelated':
        router(message)
        assert sent==['유효한 일정 안내']
    else:
        with pytest.raises(NoticeSuppressed):
            router(message)
        assert not sent

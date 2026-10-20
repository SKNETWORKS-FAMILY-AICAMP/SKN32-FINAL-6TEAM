"""Keep a customer-named destination when its location cannot yet be resolved."""
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

from app.domains.travel_ops.components.itinerary.itinerary import StaleItinerary
from .journey_progress import terminal


def apply(*, store, connect, trip_id, base_version, decision, now, request_id):
    name = str((decision.raw or {}).get('destination_text') or '').strip()[:80]
    key = 'destination:' + str(request_id)
    with connect() as conn, conn.transaction():
        already = store.version_for_request(conn, trip_id, key)
        if already is not None:
            return {'status':'already_applied','version':already,'text':'요청하신 목적지는 이미 반영했어요.'}
        trip, items = store.latest(conn,trip_id)
        if trip['version'] != base_version:
            raise StaleItinerary('destination itinerary changed')
        target = next((i for i in items if decision.item is not None and i.item_id==decision.item.item_id),None)
        if not name or target is None or target.locked or target.booking_id or target.detail.get('booking') or target.detail.get('customer_pinned'):
            return None
        if terminal(target):
            return {'status':'edit_refused','text':f'{target.title}은(는) 이미 완료한 방문이에요. 새 방문으로 넣을지 알려 주세요.'}
        before = [i for i in items if i.kind!='mobility' and i.seq<target.seq]
        after = [i for i in items if i.kind!='mobility' and i.seq>target.seq]
        low = max((i.seq for i in before),default=target.seq)
        high = min((i.seq for i in after),default=target.seq)
        detail = {**target.detail,'requested_place':{'name':name,'status':'unresolved',
            'source':'customer_request','area':str((decision.raw or {}).get('place_text') or ''),
            'reported_at':now.isoformat()},'navigation':{'status':'needs_location'}}
        detail.pop('execution',None)
        offset = timedelta(minutes=decision.minutes or 0)
        replacement = replace(target,item_id=uuid4(),replaces_item_id=target.item_id,
            place_id=None,place=None,title=name,detail=detail, starts_at=target.starts_at+offset,
            ends_at=target.ends_at+offset if target.ends_at else None)
        updated = [replacement if i.item_id==target.item_id else i for i in items
            if not (i.kind=='mobility' and low<i.seq<high and not terminal(i))]
        updated = [replace(i,seq=n) for n,i in enumerate(sorted(updated,key=lambda i:i.seq),1)]
        from app.domains.travel_ops.components.actions.itinerary_actions import introduced_violations
        if introduced_violations(trip, items, updated):
            return None
        text = f'목적지를 {name}(으)로 바꿨어요. 정확한 지점 위치는 아직 확인 중이에요. 지점이나 지도 위치가 확인되면 그곳까지 길을 계산할 수 있어요.'
        cause = {'category':'customer_request','type':'requested_destination','request_id':key}
        version = store.append_version(conn,trip_id=trip_id,base_version=base_version,items=updated,
            reason='customer_request',causes=[cause])
        store.enqueue_notice(conn,trip_id=trip_id,version=version,payload={'text':text,'version':version,
            'language':'ko','changed':{'requested_place':name},'causes':[cause],'replay':False})
    # `item_id` — the stop that now carries the requested name; the chat attaches the 「직접 고르기」 card to it (2026-10-19 decision A).
    return {'status':'adjusted','version':version,'text':text,'navigation':'needs_location',
        'item_id':str(replacement.item_id),
        'choices':[{'label':name+' 지점 확인','message':name+' 지점을 확인해 줘'}],
        'choices_title':'요청하신 목적지'}

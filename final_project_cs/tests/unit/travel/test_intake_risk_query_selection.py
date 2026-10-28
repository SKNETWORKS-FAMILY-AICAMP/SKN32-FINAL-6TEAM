"""Only items selected for fresh judging need a DB weather sensitivity lookup."""
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.intake import risks

NOW = datetime(2030, 1, 1, 14, tzinfo=ZoneInfo('Asia/Seoul'))


def test_capped_and_past_items_do_not_read_place_sensitivity(monkeypatch):
    calls = []
    monkeypatch.setattr(risks, '_sensitivity', lambda conn, tenant, place: calls.append(place['name']))
    items = [{'id': str(i), 'kind': 'activity', 'title': '합성 일정', 'date': '2030-01-01',
              'starts_at': '13:00', 'ends_at': '16:00',
              'place': {'name': str(i), 'latitude': 37.5, 'longitude': 127.0}} for i in range(42)]
    items[0]['date'] = '2029-12-31'
    before = deepcopy(items)
    seen = []

    def check(**kwargs):
        seen.append(kwargs['place']['name'])
        return {'verdict': 'clear', 'checked_at': NOW.isoformat(), 'checks': [], 'failed_categories': []}

    result = risks.decorate(None, tenant_id='offline', review={'items': items}, mode='fresh', check=check, now=NOW)
    assert calls == seen
    assert len(calls) == 6
    assert result['items'][0]['risk']['code'] == 'past'
    assert all(item['risk']['code'] == 'item_limit' for item in result['items'][7:])
    assert items == before


def test_direct_to_item_still_resolves_sensitivity(monkeypatch):
    calls = []
    monkeypatch.setattr(risks, '_sensitivity', lambda conn, tenant, place: calls.append(tenant))
    item = {'id': 'one', 'kind': 'activity', 'date': '2030-01-01', 'starts_at': '13:00',
            'place': {'name': '합성 장소'}}
    assert risks.to_item(None, 'offline', item) is not None
    assert calls == ['offline']

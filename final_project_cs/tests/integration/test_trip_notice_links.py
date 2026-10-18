from uuid import uuid4

import pytest

from app.domains.travel_ops.components.itinerary.itinerary import TripStore
from app.domains.travel_ops.components.itinerary.plan_link import app_url, plan_url
from app.infrastructure.notify.discord import DiscordWebhook, phrase_of, render


def test_app_link_has_no_access_token_and_opens_notices():
    trip = uuid4()
    url = app_url(trip)
    assert url.endswith(f'/trips/{trip}?notices=1')
    assert '?t=' not in url and 'token' not in url
    with pytest.raises(ValueError):
        app_url('../another-trip')


@pytest.mark.parametrize('cacheable', [False, True])
def test_both_links_survive_long_discord_body_and_are_not_translated(cacheable):
    trip = uuid4()
    payload = {'app_url': app_url(trip), 'plan_url': plan_url('links-test', trip), 'locale': 'en'}
    payload.update({'template': '{title}', 'values': {'title': '일정 안내 ' * 1000}} if cacheable else {'text': '일정 안내 ' * 1000})
    phrase = phrase_of(payload)
    assert payload['app_url'] not in phrase.template
    assert payload['plan_url'] not in phrase.template
    text = render(payload)
    assert len(text) <= 2000
    assert payload['app_url'] in text and payload['plan_url'] in text
    assert '잘림' in text
    seen = []
    def translate(template, locale):
        seen.append(template)
        return '[en] ' + template
    hook = DiscordWebhook('', translator=translate)
    translated = hook.text_for(payload)
    assert payload['app_url'] in translated and payload['plan_url'] in translated
    assert all('https://' not in template for template in seen)


def test_each_cached_notice_keeps_its_own_links():
    hook = DiscordWebhook('', translator=lambda template, locale: '[en] ' + template)
    trips = [uuid4(), uuid4()]
    texts = [hook.text_for({'template': '{title}', 'values': {'title': '안내'},
                           'locale': 'en', 'app_url': app_url(trip), 'plan_url': plan_url('links-test', trip)}) for trip in trips]
    assert len(hook.phrases) == 1
    assert str(trips[0]) in texts[0] and str(trips[0]) not in texts[1]
    assert str(trips[1]) in texts[1] and str(trips[1]) not in texts[0]


@pytest.mark.parametrize('versioned', [False, True])
def test_store_replaces_untrusted_links_with_its_own_trip(monkeypatch, versioned):
    from app.domains.travel_ops.components.watch import simulation
    monkeypatch.setattr(simulation, 'mark_notice', lambda conn, tenant, trip, payload: payload)
    monkeypatch.setattr(TripStore, '_with_guardian', lambda self, conn, trip, payload: payload)
    class Cursor:
        rowcount = 1
        inserted = None
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, args):
            if sql.startswith('INSERT'): self.inserted = args[-1]
        def fetchone(self): return ('ko',)
    class Connection:
        cursor_value = Cursor()
        def cursor(self): return self.cursor_value
    import json
    conn = Connection(); trip = uuid4(); store = TripStore('links-test')
    payload = {'text': '여행 안내', 'app_url': 'https://other.invalid/steal', 'plan_url': 'https://other.invalid/plan'}
    if versioned:
        store.enqueue_notice(conn, trip_id=trip, version=2, payload=payload)
    else:
        store.enqueue_message(conn, trip_id=trip, key='link-test', payload=payload)
    saved = json.loads(conn.cursor_value.inserted)
    assert saved['app_url'] == app_url(trip)
    assert saved['plan_url'] == plan_url('links-test', trip)

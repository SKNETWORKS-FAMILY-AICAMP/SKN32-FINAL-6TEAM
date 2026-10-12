"""실제 인증 라우터 응답을 Chromium에서 그린다. 외부 요청·업무 DB는 사용하지 않는다."""
import json
from pathlib import Path
import sys
import time

import pytest
from playwright.sync_api import sync_playwright

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parents[4] / 'final_project_cs'))
from tests.security.test_personal_ai_oauth import env as fixture, pending, tokens
from app.domains.travel_ops.modules.web_account import web_cookie

sys.stdout.reconfigure(encoding='utf-8')
monkeypatch = pytest.MonkeyPatch()
try:
    env = fixture.__wrapped__(monkeypatch)
    raw = pending(env)
    headers = {'Cookie': f'{web_cookie.cookie_name()}=member'}
    login = env.client.get('/oauth/consent', params={'request': raw})
    consent = env.client.get('/oauth/consent', params={'request': raw}, headers=headers)
    tokens(env)
    grant = env.p.connections(env.customer)[0]['connection_id']
    pages = {'login': login, 'consent': consent,
             'connections': env.client.get('/oauth/connections', headers=headers),
             'disconnect': env.client.get(f'/oauth/connections/{grant}/disconnect', headers=headers)}
    output = here / ('screens-' + time.strftime('%Y%m%d_%H%M%S'))
    output.mkdir()
    evidence = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for name, response in pages.items():
            assert response.status_code == 200, (name, response.text)
            for width in (375, 1280):
                page = browser.new_page(viewport={'width': width, 'height': 900}, device_scale_factor=1)
                page.route('**/*', lambda route: route.abort())
                page.set_content(response.text, wait_until='load')
                page.screenshot(path=str(output / f'{name}-{width}.png'), full_page=True)
                details = page.evaluate('''() => ({width:innerWidth, scroll:document.documentElement.scrollWidth,
                  bodySize:getComputedStyle(document.body).fontSize,
                  controls:[...document.querySelectorAll('button,input:not([type=hidden]),select,a[href]')].map(e => ({
                    name:e.innerText||e.name, tag:e.tagName, width:e.getBoundingClientRect().width,
                    height:e.getBoundingClientRect().height, size:getComputedStyle(e).fontSize}))})''')
                assert details['scroll'] <= width, (name, details)
                assert all(c['height'] >= 44 for c in details['controls']), (name, details)
                page.keyboard.press('Tab')
                details['keyboard_focus'] = page.evaluate('''() => ({tag:document.activeElement.tagName,
                  text:document.activeElement.textContent, outline:getComputedStyle(document.activeElement).outlineStyle})''')
                assert details['keyboard_focus']['outline'] != 'none', (name, details)
                evidence.append({'screen': name, **details})
                page.close()
        browser.close()
    (output / 'checks.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print(output)
finally:
    monkeypatch.undo()

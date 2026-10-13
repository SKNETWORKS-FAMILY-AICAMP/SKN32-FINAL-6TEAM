import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'.tmp/mobility_complete_20261008'
results=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    for title, name, root_id in (
        ('readiness','readiness-report-preview-v2.html','mobility-readiness-oct11'),
        ('evidence','evidence-report-preview-v2.html','mobility-evidence-oct11')):
        for width in (736,360):
            page=browser.new_page(viewport={'width':width,'height':1100})
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('**/*', lambda route: route.abort() if route.request.url.startswith(('http://','https://')) else route.continue_())
            page.goto((OUT/name).as_uri())
            frame=page.frame_locator('iframe')
            frame.locator('#'+root_id).wait_for()
            if title=='readiness':
                assert frame.locator('.tiles button').count()==21
                frame.get_by_role('button',name='장소 사이 도보 거리 · 추가 검증 · 근거 보기',exact=True).click()
                assert frame.locator('[data-name]').inner_text()=='장소 사이 도보 거리'
                assert '0/1' in frame.locator('[data-evidence]').inner_text()
                assert frame.locator('button[aria-pressed="true"]').count()==1
                frame.locator('#'+root_id).evaluate("el=>window.dispatchEvent(new CustomEvent('openai:set_globals',{detail:{globals:{widgetState:{privateContent:{selected:0}}}}}))")
                assert frame.locator('[data-name]').inner_text()=='택시 미터 예상액'
            dims=frame.locator('#'+root_id).evaluate('(el)=>({width:innerWidth,scroll:document.documentElement.scrollWidth,buttons:[...el.querySelectorAll("button")].map(b=>({w:b.getBoundingClientRect().width,h:b.getBoundingClientRect().height,sw:b.scrollWidth,cw:b.clientWidth}))})')
            assert dims['scroll']<=dims['width']+1,dims
            assert all(b['sw']<=b['cw']+1 for b in dims['buttons']),dims
            assert not errors,errors
            page.screenshot(path=str(OUT/f'{title}-{width}-v2.png'),full_page=True)
            results.append({'visual':title,'width':width,'dimensions':dims,'page_errors':errors,
                'selection_and_restore':title=='readiness'})
            page.close()
    browser.close()
with (OUT/'readiness-visual-check-v2.json').open('x',encoding='utf-8') as f:
    json.dump(results,f,ensure_ascii=False,indent=2)
print(json.dumps({'views_checked':len(results),'overflow':0,'page_errors':0,'interactive_views':2}))

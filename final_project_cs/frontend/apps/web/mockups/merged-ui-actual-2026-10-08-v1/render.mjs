import { chromium } from '../../node_modules/playwright/index.mjs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import fs from 'node:fs/promises';
const folder=path.dirname(fileURLToPath(import.meta.url));
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1080}});
const errors=[];
page.on('pageerror',e=>errors.push(e.message));
await page.goto(pathToFileURL(path.join(folder,'index.html')).href);
for(const key of ['menu','trip','records','checks']) {
  await page.locator(`[data-tab="${key}"]`).click();
  if(await page.locator('[role=tabpanel]:visible').count()!==1) throw new Error('Visible panel count');
  await page.screenshot({path:path.join(folder,`comparison-${key}.png`),fullPage:true});
}
if(!await page.locator('#records pre').first().innerText().then(t=>t.includes('사진을 두 가지로 읽은 일정'))) throw new Error('Ours source missing');
if(!await page.locator('#records pre').last().innerText().then(t=>t.includes('여행 화면 3단계'))) throw new Error('UI source missing');
await page.locator('[data-tab="menu"]').click();
await page.locator('[data-tab="menu"]').focus();
await page.keyboard.press('ArrowRight');
if(await page.locator('[data-tab="trip"]').getAttribute('aria-selected')!=='true') throw new Error('Keyboard tabs');
for(const width of [375,1280]) {
  await page.setViewportSize({width,height:1000});
  for(const key of ['menu','trip','records','checks']) {
    await page.locator(`[data-tab="${key}"]`).click();
    const ok=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);
    if(!ok) throw new Error(`Overflow ${width} ${key}`);
  }
}
const broken=await page.locator('img').evaluateAll(images=>images.filter(i=>!i.complete||i.naturalWidth===0).length);
if(broken||errors.length) throw new Error(JSON.stringify({broken,errors}));
await fs.writeFile(path.join(folder,'verification.json'),JSON.stringify({tabs:'4/4',screenshots:'4/4',sourceExcerpts:'2/2',viewportChecks:'8/8',keyboardTabs:true,brokenImages:broken,pageErrors:errors},null,2));
await browser.close();
console.log('Comparison verified: 4 panels, 2 source excerpts, 8 viewport checks, keyboard tabs, 0 broken images.');

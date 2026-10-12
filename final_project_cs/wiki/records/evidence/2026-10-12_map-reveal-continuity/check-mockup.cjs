const { chromium } = require('C:/Users/playdata2/Documents/final_workspace/final_project_cs/frontend/apps/web/node_modules/playwright');
const { pathToFileURL } = require('node:url');
const fs = require('node:fs/promises');
const path = require('node:path');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const root = process.argv[2], results = [];
  for (const width of [375, 1280]) {
    const page = await browser.newPage({ viewport: { width, height: 950 }, reducedMotion: width === 375 ? 'reduce' : 'no-preference' });
    const errors = []; page.on('pageerror', error => errors.push(String(error)));
    await page.goto(pathToFileURL(path.join(root, 'index.html')).href);
    await page.waitForFunction(() => [...document.images].every(image => image.complete && image.naturalWidth > 0) && document.querySelector('video').readyState >= 1);
    await page.getByRole('button', { name: '3번', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('#shot').complete && document.querySelector('#shot').src.includes('step-3'));
    await page.getByRole('button', { name: '2번 · 거리 표시', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('#shot').complete && document.querySelector('#shot').src.includes('step-2'));
    const state = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth > innerWidth, duration: document.querySelector('video').duration, paused: document.querySelector('video').paused }));
    if (errors.length || state.overflow || state.duration < 5 || (width === 375 && !state.paused)) throw new Error(JSON.stringify({ errors, state }));
    await page.screenshot({ path: path.join(__dirname, `mockup-${width}.png`), fullPage: true });
    results.push({ width, ...state, errors });
    await page.close();
  }
  await fs.writeFile(path.join(__dirname, 'mockup-verification.json'), JSON.stringify(results, null, 2));
  await browser.close();
  console.log(JSON.stringify(results));
})().catch(error => { console.error(error); process.exit(1); });

import { chromium } from '../../node_modules/playwright/index.mjs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import fs from 'node:fs/promises';

const folder = path.dirname(fileURLToPath(import.meta.url));
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1080 }, deviceScaleFactor: 1 });
const errors = [];
page.on('pageerror', e => errors.push(e.message));
await page.goto(pathToFileURL(path.join(folder, 'index.html')).href);
const keys = ['menu', 'frame', 'settings', 'tests', 'records'];
for (const key of keys) {
  await page.locator(`[data-tab="${key}"]`).click();
  await page.screenshot({ path: path.join(folder, `${key}.png`), fullPage: true });
  const visible = await page.locator('[role=tabpanel]:visible').count();
  if (visible !== 1) throw new Error(`${key}: visible panels ${visible}`);
}
await page.locator('[data-tab="menu"]').click();
await page.locator('#panel-menu .merged [data-demo="guardian"]').click();
if (!(await page.locator('#panel-menu .merged .demoState').innerText()).includes('항로 지킴이')) throw new Error('guardian preview missing');
await page.locator('#panel-menu summary').click();
if (!(await page.locator('[data-source="menu-team"]').innerText()).includes('CloseMenu')) throw new Error('actual source missing');
await page.locator('[data-tab="menu"]').focus();
await page.keyboard.press('ArrowRight');
if (await page.locator('[data-tab="frame"]').getAttribute('aria-selected') !== 'true') throw new Error('keyboard tabs failed');
await page.setViewportSize({ width: 375, height: 812 });
for (const key of keys) {
  await page.locator(`[data-tab="${key}"]`).click();
  const sizes = await page.evaluate(() => [document.documentElement.scrollWidth, innerWidth]);
  if (sizes[0] > sizes[1]) throw new Error(`mobile overflow ${key} ${sizes}`);
}
await page.screenshot({ path: path.join(folder, 'mobile.png'), fullPage: true });
await browser.close();
if (errors.length) throw new Error(errors.join('\n'));
await fs.writeFile(path.join(folder, 'verification.json'), JSON.stringify({ tabs: '5/5', screenshots: '5/5', sourceEmbedding: true, guardianPreview: true, keyboardTabs: true, mobileNoOverflow: '5/5', pageErrors: errors }, null, 2));
console.log('5 tabs, 5 screenshots, actual sources, keyboard tabs, menu preview, 5 mobile widths verified.');

const { createRequire } = require('node:module');
const { resolve } = require('node:path');
const { pathToFileURL } = require('node:url');
const { existsSync, mkdirSync, copyFileSync } = require('node:fs');
const appRequire = createRequire(resolve('frontend/apps/web/package.json'));
const { chromium } = appRequire('@playwright/test');
(async () => {
  const browser = await chromium.launch({channel:'msedge', headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1120,height:1000}, deviceScaleFactor:1});
    await page.goto(pathToFileURL(resolve(__dirname,'service-improvement-flow.html')).href);
    const output = resolve(__dirname,'service-improvement-flow.png');
    if (existsSync(output)) {
      const backup = resolve(__dirname,'_backup',Date.now()+'_flow_render');
      mkdirSync(backup,{recursive:true});
      copyFileSync(output,resolve(backup,'service-improvement-flow.png'));
    }
    await page.screenshot({path:output,fullPage:true});
    const result = await page.evaluate(() => ({figures:document.querySelectorAll('svg').length,
      horizontalOverflow:document.documentElement.scrollWidth > innerWidth}));
    process.stdout.write(JSON.stringify(result));
  } finally { await browser.close(); }
})();

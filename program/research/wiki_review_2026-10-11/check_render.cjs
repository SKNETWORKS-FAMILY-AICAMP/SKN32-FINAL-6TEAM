const {chromium} = require('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1007-641-0_26.1007.641.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const {pathToFileURL} = require('url');
(async () => {
  const dir=__dirname;
  const scratch=path.resolve(dir,'../../../.tmp/wiki-review-2026-10-11');
  fs.mkdirSync(scratch,{recursive:true});
  const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const page=await browser.newPage();
  const errors=[]; page.on('pageerror',e=>errors.push(String(e)));
  const observations=[];
  for (const width of [1280,375]) {
    await page.setViewportSize({width,height:900});
    await page.goto(pathToFileURL(path.join(dir,'wiki-review-v1.html')).href);
    observations.push(await page.evaluate(()=>({width:innerWidth,documentWidth:document.documentElement.scrollWidth,articles:document.querySelectorAll('article.finding').length,svgTitle:document.querySelector('svg title').textContent,font:getComputedStyle(document.body).fontFamily})));
    await page.screenshot({path:path.join(scratch,`review-${width}.png`)});
  }
  await page.setViewportSize({width:1280,height:1000});
  await page.locator('.flow').screenshot({path:path.join(scratch,'review-flow.png')});
  await page.locator('#W05 summary').click();
  const expanded=await page.locator('#W05 details').evaluate(n=>n.open);
  await page.emulateMedia({media:'print'});
  const printReady=await page.locator('svg').isVisible();
  const passed=observations.every(x=>x.width===x.documentWidth&&x.articles===25)&&expanded&&printReady&&!errors.length;
  const result={observations,expanded,printReady,errors,passed,scratch};
  const target=path.join(dir,'render-validation-v1.json');
  fs.writeFileSync(target,JSON.stringify(result,null,2),{flag:'wx'});
  process.stdout.write(JSON.stringify(result));
  await browser.close();
  if(!passed)process.exitCode=1;
})().catch(e=>{process.stderr.write(String(e));process.exitCode=1});

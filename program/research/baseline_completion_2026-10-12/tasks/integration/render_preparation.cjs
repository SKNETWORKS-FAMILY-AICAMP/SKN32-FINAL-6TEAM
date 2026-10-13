// 외부 호출 없이 검토 준비본의 실제 화면·링크·글꼴을 확인합니다.
const fs = require('fs');
const path = require('path');
const {pathToFileURL} = require('url');
const {chromium} = require('C:/Users/playdata2/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base = __dirname;
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const output = path.join(base, 'checks', 'screens', stamp);
fs.mkdirSync(output, {recursive: true});
(async()=>{
  const browser = await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const results=[];
  for(const filename of ['finalization-flow.html','v12-outline.html','baseline-outline.html']){
    for(const width of [1440,375]){
      const page=await browser.newPage({viewport:{width,height:1000}});
      const errors=[];
      page.on('pageerror', error=>errors.push(String(error)));
      await page.goto(pathToFileURL(path.join(base,filename)).href);
      const check=await page.evaluate(()=>({
        bodyWidth:document.body.scrollWidth,viewport:innerWidth,
        title:document.title,
        font:getComputedStyle(document.querySelector('h1')).fontFamily,
        svgs:[...document.querySelectorAll('svg')].map(svg=>({width:svg.getBoundingClientRect().width, title:svg.querySelector('title')?.textContent,desc:svg.querySelector('desc')?.textContent})),
      }));
      const shot=path.join(output,filename.replace('.html',`-${width}.png`));
      await page.screenshot({path:shot,fullPage:filename==='finalization-flow.html'});
      results.push({filename,width,...check,errors,bodyOverflow:check.bodyWidth>width,screenshot:path.relative(base,shot).replaceAll('\\','/')});
      await page.close();
    }
  }
  await browser.close();
  const report={captured_at_utc:new Date().toISOString(),scope:'로컬 검토 준비본 렌더링. 고객 제품 화면 시험 아님',checks:results};
  fs.writeFileSync(path.join(output,'render-checks.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify({path:path.relative(base,output),passed:results.filter(r=>!r.bodyOverflow&&!r.errors.length).length,total:results.length,results},null,2));
})().catch(error=>{console.error(String(error));process.exitCode=1});

// 검토본 HTML·흐름 SVG를 외부 요청 없이 실제 Chromium에서 확인합니다.
const fs=require('fs'),path=require('path');
const {pathToFileURL}=require('url');
const {chromium}=require('C:/Users/playdata2/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=path.resolve(__dirname,'../../../../..');
const output=path.join(__dirname,'checks','review-screens-'+new Date().toISOString().replace(/[:.]/g,'-'));
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const checks=[];
 for(const file of ['program/plan/triPilot_구현계획서_v12.html','program/baseline/triPilot-baseline-2026-10-12.html']){
  for(const width of [1440,375]){
   const page=await browser.newPage({viewport:{width,height:1000}}),errors=[],external=[];
   await page.route('**/*',route=>{if(/^https?:/.test(route.request().url())){external.push('blocked_external');return route.abort();}return route.continue();});
   page.on('pageerror',e=>errors.push(String(e)));
   await page.goto(pathToFileURL(path.join(root,file)).href);
   const metrics=await page.evaluate(()=>({title:document.title,body:document.body.scrollWidth,viewport:innerWidth,
    images:[...document.images].map(i=>({loaded:i.complete&&i.naturalWidth>0})),
    svgTextOutside:[...document.querySelectorAll('svg text')].filter(t=>{const b=t.getBBox(),v=t.ownerSVGElement.viewBox.baseVal;return b.x<0||b.y<0||b.x+b.width>v.width||b.y+b.height>v.height}).map(t=>t.textContent),
    duplicateIds:[...document.querySelectorAll('[id]')].map(e=>e.id).filter((x,i,a)=>a.indexOf(x)!==i),
    reviewNotice:document.body.innerText.includes('최종 인수 전 검토본')}));
   await page.screenshot({path:path.join(output,path.basename(file).replace('.html',`-${width}.png`)),fullPage:false});
   for(let i=0;i<await page.locator('figure').count();i++)await page.locator('figure').nth(i).screenshot({path:path.join(output,`figure-${i}-${width}.png`)});
   checks.push({file,width,...metrics,errors,external,passed:metrics.body<=width&&metrics.reviewNotice&&!metrics.svgTextOutside.length&&!metrics.duplicateIds.length&&!errors.length&&!external.length&&metrics.images.every(i=>i.loaded)});
   await page.close();
  }
 }
 await browser.close();
 fs.writeFileSync(path.join(output,'render-checks.json'),JSON.stringify({checks,scope:'로컬 문서 렌더링; 고객 제품 화면 시험 아님'},null,2));
 console.log(JSON.stringify({output,passed:checks.filter(x=>x.passed).length,total:checks.length,checks}));
 process.exitCode=checks.every(x=>x.passed)?0:1;
})().catch(e=>{console.error(String(e));process.exitCode=1;});

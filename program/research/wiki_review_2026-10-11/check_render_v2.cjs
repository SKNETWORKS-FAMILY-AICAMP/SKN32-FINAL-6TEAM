const {chromium}=require('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1007-641-0_26.1007.641.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/playwright');
const fs=require('fs');
const path=require('path');
const {pathToFileURL}=require('url');
function save(target,data){if(fs.existsSync(target)){const b=path.join(__dirname,'_backup',new Date().toISOString().replace(/[:.]/g,'-')+'_v2-check');fs.mkdirSync(b,{recursive:true});fs.copyFileSync(target,path.join(b,path.basename(target)));}fs.writeFileSync(target,data);}
(async()=>{
 const scratch=path.resolve(__dirname,'../../../.tmp/wiki-review-v2-2026-10-11');fs.mkdirSync(scratch,{recursive:true});
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const page=await browser.newPage({acceptDownloads:true});const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 const url=pathToFileURL(path.join(__dirname,'wiki-review-v2.html')).href;await page.goto(url);await page.evaluate(()=>localStorage.clear());await page.reload();
 const checks=[];
 function check(name,passed,detail){checks.push({name,passed,detail});}
 for(const width of [1280,375]){
  await page.setViewportSize({width,height:960});
  const o=await page.evaluate(()=>({width:innerWidth,documentWidth:document.documentElement.scrollWidth,cards:document.querySelectorAll('article.finding').length,options:document.querySelectorAll('input[type=radio]').length,selected:document.querySelectorAll('input[type=radio]:checked').length}));
  check('화면 폭 '+width,o.width===o.documentWidth&&o.cards===25&&o.options===75&&o.selected===25,o);
  const png=await page.screenshot({fullPage:false});save(path.join(scratch,'review-v2-'+width+'.png'),png);
 }
 const allDefault=await page.locator('input:checked').evaluateAll(nodes=>nodes.every(x=>x.value==='A'));check('추천안 25개 기본 선택',allDefault);
 await page.locator('input[name=W04][value=B]').check();await page.reload();check('선택 저장',await page.locator('input[name=W04][value=B]').isChecked());
 await page.locator('#export').click();const data=JSON.parse(await page.locator('#export-text').inputValue());check('선택 결과 생성',data.selections.W04==='B'&&Object.keys(data.selections).length===25&&await page.locator('#export-panel').isVisible(),data.selections.W04);
 await page.locator('#reset').click();check('추천안 초기화',await page.locator('input:checked').evaluateAll(nodes=>nodes.length===25&&nodes.every(x=>x.value==='A')));
 const links=await page.locator('a[href]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href')));const missing=[];
 for(const href of links){if(/^(https?:|#)/.test(href))continue;const dest=path.resolve(__dirname,decodeURIComponent(href.split('#')[0]));if(!fs.existsSync(dest))missing.push(href);}
 check('로컬 근거·대상 링크',missing.length===0,missing);
 await page.setViewportSize({width:1280,height:1100});await page.locator('details').first().evaluate(n=>n.open=true);save(path.join(scratch,'review-v2-flow.png'),await page.locator('.flow').first().screenshot());
 check('흐름도 접근성',await page.locator('svg').evaluateAll(nodes=>nodes.length===2&&nodes.every(n=>n.getAttribute('role')==='img'&&n.getAttribute('aria-labelledby').split(' ').every(id=>!!document.getElementById(id)))));
 const terms=await page.locator('#architecture-terms').innerText();check('정확한 호출·계산 담당 설명',['Controller','TeamRegistry','TeamExecutorPort','LocalTeamExecutor','WatchBatch','watch_planners','에이전트 팀'].every(x=>terms.includes(x)));
 const work=await page.locator('#W08').innerText();check('공동 처리와 모니터링 구분',terms.includes('개발자·QA 모니터링 도구')&&work.includes('다른 에이전트 팀의 execute를 연쇄 호출하는 구조로 적지 않습니다.')&&work.includes('항목 수 상한'));
 // Opening print should expose all details without starting an OS print dialog.
 await page.evaluate(()=>{window.print=()=>{window.__printed=true;};});await page.locator('#print').click();await page.emulateMedia({media:'print'});check('인쇄 시 상세 노출',await page.evaluate(()=>window.__printed&&[...document.querySelectorAll('details')].every(d=>d.open)));
 await page.emulateMedia({media:'screen',reducedMotion:'reduce'});check('줄임 동작 설정',await page.locator('svg').first().isVisible());
 check('브라우저 실행 오류',errors.length===0,errors);
 const result={checked_at:new Date().toISOString(),checks,passed:checks.every(c=>c.passed),passed_count:checks.filter(c=>c.passed).length,total:checks.length,scratch};
 save(path.join(__dirname,'render-validation-v2.json'),JSON.stringify(result,null,2));process.stdout.write(JSON.stringify(result));await browser.close();if(!result.passed)process.exitCode=1;
})().catch(e=>{process.stderr.write(String(e));process.exit(1);});

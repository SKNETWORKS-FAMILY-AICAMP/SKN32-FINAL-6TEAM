// Render local documents with no external requests; preserve previous renders.
const fs=require('fs'),path=require('path');
const {pathToFileURL}=require('url');
const {chromium}=require('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1007-641-0_26.1007.641.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/playwright');
const root=__dirname,out=path.join(root,'checks','screens');
function preserve(p){if(fs.existsSync(p)){const stamp=new Date().toISOString().replace(/[:.]/g,'-');const b=path.join(root,'_backup',stamp+'_renders');fs.mkdirSync(b,{recursive:true});fs.copyFileSync(p,path.join(b,path.basename(p)));}}
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const results=[];
 for(const name of ['triPilot-baseline-v2','baseline-writing-guide-v2']){
  for(const [mode,viewport] of [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]]){
   const page=await browser.newPage({viewport});const blocked=[];const errors=[];
   await page.route(/^https?:/,route=>{blocked.push(route.request().url());return route.abort();});
   page.on('pageerror',e=>errors.push(e.message));
   await page.goto(pathToFileURL(path.join(root,name+'.html')).href);
   await page.evaluate(()=>document.fonts.ready);
   const metrics=await page.evaluate(()=>({pageWidth:document.documentElement.scrollWidth,viewport:innerWidth,svg:document.querySelectorAll('svg').length,sections:document.querySelectorAll('main>section').length,hiddenDetails:document.querySelectorAll('details:not([open])').length}));
   const shot=path.join(out,name+'-'+mode+'.png');preserve(shot);await page.screenshot({path:shot,fullPage:false});
   const figure=page.locator('figure').first();const figShot=path.join(out,name+'-hierarchy-'+mode+'.png');preserve(figShot);await figure.screenshot({path:figShot});
   const flow=page.locator('figure').nth(1);const flowShot=path.join(out,name+'-flow-'+mode+'.png');preserve(flowShot);await flow.screenshot({path:flowShot});
   if(mode==='desktop'){
    const pdf=path.join(out,name+'-print.pdf');preserve(pdf);await page.pdf({path:pdf,format:'A4',printBackground:true,margin:{top:'15mm',bottom:'15mm',left:'14mm',right:'14mm'}});
   }
   results.push({name,mode,metrics,blockedRequests:blocked,pageErrors:errors,passed:metrics.pageWidth<=metrics.viewport&&blocked.length===0&&errors.length===0});
   await page.close();
  }
 }
 await browser.close();
 const target=path.join(root,'checks','render-audit-v2.json');preserve(target);fs.writeFileSync(target,JSON.stringify({results,passed:results.filter(x=>x.passed).length,total:results.length},null,2));
 console.log(JSON.stringify(results,null,2));
})().catch(e=>{console.error(e);process.exit(1);});

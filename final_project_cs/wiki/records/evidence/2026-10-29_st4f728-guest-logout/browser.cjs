const fs=require('fs'),path=require('path'),{createRequire}=require('module');
const W=__dirname, web=path.join(W,'repo/final_project_cs/frontend/apps/web');
const req=createRequire(path.join(web,'package.json'));
const {chromium}=req('@playwright/test');
(async()=>{const {rolldown}=await import(require('url').pathToFileURL(req.resolve('rolldown')).href);const bundle=await rolldown({input:path.join(web,'src/lib/live/client.ts'),platform:'browser',transform:{define:{'process.env.NEXT_PUBLIC_API_BASE':'\"http://isolated.invalid\"'}}});const output=await bundle.generate({format:'iife',name:'sessionClient'});const source=output.output.find(x=>x.type==='chunk').code;await bundle.close();const browser=await chromium.launch({channel:'msedge',headless:true});let results=[];try{
 const page=await browser.newPage();await page.route('**/*',r=>r.abort());await page.setContent('<html><body>Isolated session regression</body></html>');await page.addScriptTag({content:source});
 for(const kind of ['session','write','member']){
 const result=await page.evaluate(async kind=>{
 const c=sessionClient;c.resetSessionState();let release,start;const ready=new Promise(r=>start=r);let writes=0;
 const json=(d,status=200)=>new Response(JSON.stringify(d),{status});
 window.fetch=async url=>{const p=new URL(url).pathname;if(p.endsWith('/auth/me'))return json({error:{code:'unauthenticated'}},401);if(p.endsWith('/auth/session')){start();return new Promise(r=>release=r);}if(p.endsWith('/auth/logout'))return json({status:'signed_out'});writes++;return json({saved:true});};
 const pending=(kind==='write'?c.api('/v1/web/trip-intakes','ko',{method:'POST',body:'{}'}):c.ensureSession('ko')).then(value=>({value}),error=>({code:error.code}));
 await ready;if(kind==='member')c.takeSession({kind:'member',csrf:'browser-test-member',guestIdleHours:null,idleExpiresAt:null,absoluteExpiresAt:null});else await c.logout('ko');
 release(json({kind:'guest',csrf_token:'browser-test-guest',guest_idle_hours:168},201));const outcome=await pending;
 return {kind,code:outcome.code??null,sessionKind:c.currentSession()?.kind??null,writes,pass:kind==='member'?outcome.value?.kind==='member'&&c.currentSession()?.kind==='member':outcome.code==='session_changed'&&c.currentSession()===null&&writes===0};
 },kind);results.push(result);
 }
 fs.writeFileSync(path.join(W,'browser-results.json'),JSON.stringify({browser:await browser.version(),results,network:'all routes aborted; fetch controlled in isolated page',fullApp:false},null,2));console.log(JSON.stringify(results));if(results.some(x=>!x.pass))process.exitCode=1;
}finally{await browser.close();}})().catch(e=>{console.error(e.message);process.exitCode=1;});

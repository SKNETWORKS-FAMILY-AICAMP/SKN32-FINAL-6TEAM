import { chromium } from '@playwright/test';
import { pathToFileURL } from 'node:url';
import { writeFile } from 'node:fs/promises';
const folder='C:/Users/playdata2/Documents/final_workspace/final_project_cs/frontend/apps/web/mockups/map-reveal-continuity-2026-10-12-v4';
const output='../map-direction-20261012-v4';
const browser=await chromium.launch({channel:'chrome'});
const results=[];
try {
  for(const width of [375,1280]) {
    const page=await browser.newPage({viewport:{width,height:812}});
    await page.goto(pathToFileURL(folder+'/index.html').href);
    await page.waitForFunction(()=>[...document.images].every(img=>img.complete&&img.naturalWidth>0));
    await page.waitForFunction(()=>[...document.querySelectorAll('video')].every(video=>video.readyState>=1));
    const result=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,images:document.images.length,videos:[...document.querySelectorAll('video')].map(video=>({duration:video.duration,width:video.videoWidth,height:video.videoHeight})),brokenLinks:[...document.querySelectorAll('a')].filter(a=>!a.getAttribute('href')).length}));
    if(result.scrollWidth>width||result.images!==6||result.videos.length!==2||result.videos.some(video=>video.duration<=0)||result.brokenLinks)throw Error(JSON.stringify(result));
    await page.screenshot({path:`${output}/mockup-${width}.png`});
    await page.locator('video').first().evaluate(video=>video.play());
    await page.waitForFunction(()=>document.querySelector('video').currentTime>.2);
    results.push({...result,playback:true});
    await page.close();
  }
  await writeFile(`${output}/mockup-check.json`,JSON.stringify(results,null,2));
  console.log('MOCKUP_PASS=2/2');
}finally{await browser.close();}

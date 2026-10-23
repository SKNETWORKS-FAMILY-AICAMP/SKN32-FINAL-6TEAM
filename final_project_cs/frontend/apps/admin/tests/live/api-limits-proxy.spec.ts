import { test, expect } from '@playwright/test';
import { createServer, type Server } from 'node:http';

// 브라우저 요청 목업을 쓰지 않는다. Next.js 중계 뒤에 mock 서버를 연결해 전달을 검증한다.
let upstream: Server;
const received: {url:string;cookie:string;method:string;csrf:string;body:string}[]=[];
test.beforeAll(async()=>{
  upstream=createServer((request,response)=>{
    let body='';request.on('data',chunk=>body+=chunk);request.on('end',()=>{
      received.push({url:request.url||'',cookie:request.headers.cookie||'',method:request.method||'',csrf:String(request.headers['x-csrf-token']||''),body});
      response.setHeader('Content-Type','application/json');response.end(JSON.stringify({ok:true}));
    });
  });
  await new Promise<void>((resolve,reject)=>{upstream.once('error',reject);upstream.listen(3371,'127.0.0.1',resolve);});
});
test.afterAll(async()=>{await new Promise<void>((resolve,reject)=>upstream.close(error=>error?reject(error):resolve()));});

test('API 한도·감시 이력·시뮬레이션 경로와 검색 조건을 실제 중계한다',async({request})=>{
  const headers={Cookie:'acop_ui=operator-cookie; customer_session=private-customer-cookie; acop_admin_csrf=test-csrf','X-CSRF-Token':'test-csrf'};
  const id='11111111-1111-4111-8111-111111111111';
  for(const path of ['api-limits', 'watch-runs?status=failed&limit=5',`watch-runs/${id}?after=12&limit=100`,'simulations']){
    const response=await request.get(`/admin/api/${path}`,{headers});
    expect(response.status()).toBe(200);expect(received.at(-1)?.url).toBe(`/admin/api/${path}`);
    expect(received.at(-1)?.cookie).toContain('acop_ui=operator-cookie');
    expect(received.at(-1)?.cookie).not.toContain('customer_session');
  }
  const response=await request.patch(`/admin/api/simulations/${id}`,{headers,data:{enabled:true}});
  expect(response.status()).toBe(200);expect(received.at(-1)).toMatchObject({method:'PATCH',csrf:'test-csrf',body:'{"enabled":true}'});
  const count=received.length;
  expect((await request.get('/admin/api/private-env')).status()).toBe(404);
  expect((await request.get('/admin/api/watch-runs/not-a-uuid')).status()).toBe(404);
  expect(received).toHaveLength(count);
});

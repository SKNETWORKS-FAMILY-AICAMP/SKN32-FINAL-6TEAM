import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { NextRequest } from 'next/server';
import { GET, POST, PATCH } from '../app/admin/api/[...segments]/route';

const customer='11111111-2222-4333-8444-555555555555';
const trip='66666666-7777-4888-8999-aaaaaaaaaaaa';
const fetchMock=vi.fn();
function request(method:string) {
  return { method, headers:new Headers({'x-csrf-token':'test-csrf'}),
    cookies:{getAll:()=>[{name:'acop_ui',value:'test-session'},{name:'unrelated',value:'not-forwarded'}]},
    nextUrl:new URL('http://127.0.0.1:3300/admin/api/session?check=1'),
    text:async()=>'{"reason":"unit check"}',
  } as unknown as NextRequest;
}
describe('운영 프록시의 QA·공지 경로와 격리',()=>{
  beforeEach(()=>{
    vi.stubEnv('ADMIN_OPS_API_URL','http://127.0.0.1:8070');
    fetchMock.mockReset();
    fetchMock.mockImplementation(async()=>new Response('{"ok":true}',{status:200,headers:{'content-type':'application/json'}}));
    vi.stubGlobal('fetch',fetchMock);
  });
  afterEach(()=>{vi.unstubAllGlobals();vi.unstubAllEnvs();});
  it.each([
    ['GET',['qa-account']],['PATCH',['qa-account']],['POST',['qa-account','open']],
    ['GET',['notice-deliveries',trip]],['GET',['users',customer,'trips',trip,'draft']],
    ['POST',['simulations',trip,'mock-receipts']],
  ])('정상 %s %j 경로를 기존 운영 인증 경계로 보낸다',async(method,segments)=>{
    const invoke=method==='POST'?POST:method==='PATCH'?PATCH:GET;
    const response=await invoke(request(method as string),{params:Promise.resolve({segments:segments as string[]})});
    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url,options]=fetchMock.mock.calls[0];
    expect(String(url)).toBe('http://127.0.0.1:8070/admin/api/'+(segments as string[]).join('/')+'?check=1');
    expect(options.headers.get('cookie')).toBe('acop_ui=test-session');
    expect(options.headers.get('x-csrf-token')).toBe('test-csrf');
    expect(options.redirect).toBe('manual');
  });
  it.each([
    ['qa-account','open','extra'],['qa-account','delete'],['notice-deliveries','invalid'],
    ['users',customer,'trips',trip,'unknown'],['unknown'],['..','qa-account'],
  ])('미등록 경로 %j를 외부 호출 전에 거절한다',async(...segments)=>{
    const response=await GET(request('GET'),{params:Promise.resolve({segments})});
    expect(response.status).toBe(404);expect(fetchMock).not.toHaveBeenCalled();
  });
  it('여행 상세의 쓰기는 계속 거절한다',async()=>{
    const response=await POST(request('POST'),{params:Promise.resolve({segments:['users',customer,'trips',trip]})});
    expect(response.status).toBe(405);expect(fetchMock).not.toHaveBeenCalled();
  });
  it('외부 운영 API 주소를 거절한다',async()=>{
    vi.stubEnv('ADMIN_OPS_API_URL','https://other.example');
    const response=await GET(request('GET'),{params:Promise.resolve({segments:['qa-account']})});
    expect(response.status).toBe(503);expect(fetchMock).not.toHaveBeenCalled();
  });
  it('운영 API 연결 실패를 성공으로 표시하지 않는다',async()=>{
    fetchMock.mockRejectedValue(new Error('network'));
    const response=await GET(request('GET'),{params:Promise.resolve({segments:['qa-account']})});
    expect(response.status).toBe(503);
  });
});

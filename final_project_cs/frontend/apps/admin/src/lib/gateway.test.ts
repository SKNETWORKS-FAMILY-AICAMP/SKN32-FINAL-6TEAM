import { afterEach, describe, expect, it, vi } from 'vitest';
import { createAdminGateway } from './gateway';
import { createDemoSnapshot } from './demo/fixtures';
import { watchState } from './model';
import type { AdminCommand } from './model';

describe('명시적인 데모 경계', () => {
  it.each(['DEMO', ' demo '])('미지원 모드 %s는 데모로 바꾸지 않는다', mode => {
    expect(() => createAdminGateway(mode)).toThrow('연결 미설정');
  });
  it('조회 사본을 고쳐도 내부 데이터는 바뀌지 않고 초기화는 변경을 지운다', async () => {
    const gateway = createAdminGateway('demo');
    const copy = await gateway.snapshot(); copy.users[0].blocked = true;
    expect((await gateway.snapshot()).users[0].blocked).toBe(false);
    await gateway.execute({ type:'block-user', userId:'demo-user-01', blocked:true, reason:'비정상 반복 요청' });
    expect((await gateway.snapshot()).users[0].blocked).toBe(true);
    await gateway.reset(); expect(await gateway.snapshot()).toEqual(createDemoSnapshot());
  });
});

describe('실제 운영 연결', () => {
  afterEach(() => vi.unstubAllGlobals());
  it('기본 모드는 실제 API를 읽으며 실패해도 데모로 전환하지 않는다', async () => {
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: '운영자 로그인이 필요합니다.' }), { status: 401 }));
    vi.stubGlobal('fetch', request);
    await expect(createAdminGateway(undefined).snapshot()).rejects.toThrow('운영자 로그인이 필요합니다.');
    expect(request).toHaveBeenCalledWith('/admin/api/snapshot', expect.objectContaining({ credentials: 'same-origin' }));
  });
  it('실제 쓰기는 세션 CSRF를 붙이고 데모 초기화는 거절한다', async () => {
    const request = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ authenticated: true, csrf: 'session-csrf' }))).mockResolvedValueOnce(new Response(JSON.stringify({ ok: true })));
    vi.stubGlobal('fetch', request);
    const gateway = createAdminGateway('live');
    await gateway.execute({ type: 'block-user', userId: 'customer', blocked: true, reason: '남용' });
    expect(request).toHaveBeenLastCalledWith('/admin/api/commands', expect.objectContaining({ method: 'POST', headers: expect.objectContaining({ 'X-CSRF-Token': 'session-csrf' }) }));
    await expect(gateway.reset()).rejects.toThrow('운영 자료는 초기화할 수 없습니다.');
  });
});

describe('저장·감사 기록의 원자성', () => {
  const commands: AdminCommand[] = [
    { type:'block-user', userId:'demo-user-01', blocked:true, reason:'' },
    { type:'user-limit', userId:'demo-user-01', limit:80, period:'today', reason:' ' },
    { type:'save-limits', chatLimit:80, rules:[], reason:'' },
    { type:'api-cap', apiId:'google-places', daily:2000, monthly:31000, reason:'' },
    { type:'inquiry-status', inquiryId:'inq-01', status:'처리 중', assignee:'demo.operator', reason:'' },
    { type:'maintenance', enabled:true, message:'점검', messageEn:'', endsAt:'2026-09-29T16:00', reason:'' },
    { type:'approval', approvalId:'approval-01', approve:true, reason:'' },
    { type:'delegation', delegationId:'delegation-01', active:true, reason:'' },
    { type:'resolve-outbox', outboxId:'outbox-01', resolution:'confirmed_delivered', reason:'' },
  ];
  it.each(commands)('$type는 사유 없으면 데이터와 기록을 모두 보존한다', async command => {
    const gateway = createAdminGateway('demo'); const before = await gateway.snapshot();
    await expect(gateway.execute(command)).rejects.toThrow('사유');
    expect(await gateway.snapshot()).toEqual(before);
  });
  it('차단·해제는 기존 사용자 ID와 키 발급 이력을 유지한다', async () => {
    const gateway = createAdminGateway('demo'); const before = (await gateway.snapshot()).users[0];
    await gateway.execute({ type:'block-user', userId:before.id, blocked:true, reason:'확인 중' });
    await gateway.execute({ type:'block-user', userId:before.id, blocked:false, reason:'확인 완료' });
    const next = await gateway.snapshot();
    expect(next.users[0]).toEqual(before); expect(next.audit).toHaveLength(3);
    expect(next.audit[0]).toMatchObject({before:'차단',after:'정상',reason:'확인 완료',actor:'demo.operator'});
  });
  it('답변과 공지는 별도 사유 대신 본문을 기록한다', async () => {
    const gateway = createAdminGateway('demo');
    await gateway.execute({ type:'reply', inquiryId:'inq-01', body:'  오늘만 한도를 늘렸습니다.  ' });
    let next = await gateway.snapshot();
    expect(next.inquiries[0].status).toBe('답변 완료');
    expect(next.audit[0].reason).toBe('오늘만 한도를 늘렸습니다.');
    await gateway.execute({ type:'publish-notice', notice:{ kind:'안내',title:'갱신 안내',body:'장소 정보 갱신이 지연됩니다.',titleEn:'',bodyEn:'',startsAt:'2026-09-29T14:00',endsAt:'2026-09-30T14:00' } });
    next = await gateway.snapshot(); expect(next.notices).toHaveLength(2); expect(next.audit[0].reason).toContain('장소 정보 갱신이 지연됩니다.');
  });
  it.each(['confirmed_delivered','confirmed_not_delivered'] as const)('%s는 결과만 기록하며 재발송하지 않고 이중 처리를 거절한다', async resolution => {
    const gateway = createAdminGateway('demo');
    const cmd = { type:'resolve-outbox' as const, outboxId:'outbox-01', resolution, reason:'수신 채널에서 확인' };
    await gateway.execute(cmd);
    const next = await gateway.snapshot();
    expect(next.outbox[0]).toMatchObject({status:'unknown',attempts:1,resolution,resolvedBy:'demo.operator',note:'수신 채널에서 확인'});
    await expect(gateway.execute(cmd)).rejects.toThrow('이미 기록');
    expect(await gateway.snapshot()).toEqual(next);
  });
  it('잘못된 상한·중복 감시 단계·역전 게시 기간은 저장되지 않는다', async () => {
    const gateway = createAdminGateway('demo'); const before = await gateway.snapshot();
    await expect(gateway.execute({ type:'api-cap',apiId:'google-places',daily:2000,monthly:1000,reason:'검증' })).rejects.toThrow('월 운영 상한');
    await expect(gateway.execute({ type:'save-limits',chatLimit:80,rules:[{id:'a',threshold:80,multiplier:2},{id:'b',threshold:80,multiplier:3}],reason:'검증' })).rejects.toThrow('중복');
    await expect(gateway.execute({ type:'publish-notice',notice:{kind:'안내',title:'테스트',body:'본문',titleEn:'',bodyEn:'',startsAt:'2026-09-30T14:00',endsAt:'2026-09-29T14:00'} })).rejects.toThrow('게시 종료');
    expect(await gateway.snapshot()).toEqual(before);
  });
  it('기본·예외 한도와 점검 전환이 성공하고 각 기록을 남긴다', async () => {
    const gateway = createAdminGateway('demo');
    await gateway.execute({type:'save-limits',chatLimit:60,rules:[{id:'r',threshold:75,multiplier:3}],reason:'시연 변경'});
    await gateway.execute({type:'user-limit',userId:'demo-user-01',limit:80,period:'today',reason:'여행 중 추가 확인'});
    await gateway.execute({type:'maintenance',enabled:true,message:'시연 점검',messageEn:'Maintenance',endsAt:'2026-09-29T16:00',reason:'정기 점검'});
    const next = await gateway.snapshot(); expect(next.chatLimit).toBe(60); expect(next.users[0].exceptionLimit).toBe(80); expect(next.maintenance.enabled).toBe(true); expect(next.audit).toHaveLength(4);
  });
});
describe('일·월 예산 경계', () => {
  it('상한 조정 뒤 재점검은 갱신된 상태와 시각을 표시한다', async () => {
    const gateway = createAdminGateway('demo'); const before = await gateway.snapshot();
    await gateway.execute({type:'api-cap',apiId:'kakao',daily:2000,monthly:31000,reason:'데모 상한 검토'});
    await gateway.execute({type:'check-server'});
    const next = await gateway.snapshot();
    expect(Date.parse(next.server.checkedAt)).toBeGreaterThan(Date.parse(before.server.checkedAt));
    expect(next.server.checks.find(check => check.name === '외부 API')?.status).toBe('정상');
  });
  it('하루가 남아 있어도 월 한도 도달이면 멈춤이고 미계측은 0이 아니다', () => {
    const snapshot = createDemoSnapshot();
    expect(watchState({...snapshot.apis[0],used:1,monthlyUsed:31000},snapshot.watchRules)).toBe('멈춤');
    expect(watchState(snapshot.apis[2],snapshot.watchRules)).toBe('미계측');
    expect(snapshot.apis[2].used).toBeNull();
  });
});

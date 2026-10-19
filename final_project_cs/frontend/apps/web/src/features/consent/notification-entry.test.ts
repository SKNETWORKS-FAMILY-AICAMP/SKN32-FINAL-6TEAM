import { beforeEach, describe, expect, it, vi } from 'vitest';
import { openApi } from '@/lib/live/client';
vi.mock('@/lib/live/client',()=>({openApi:vi.fn()}));
import { notificationLoginPath, notificationTripAccess } from './notification-entry';

const path='/trips/11111111-2222-4333-8444-555555555555';
describe('notification authentication before consent',()=>{
  it('takes a visitor or guest straight to login and preserves the exact trip',()=>{
    expect(notificationLoginPath(path,'?notices=1',false)).toBe('/mypage/account?login=1&returnTo='+encodeURIComponent(path+'?notices=1'));
  });
  it('keeps a signed-in member on their trip for the normal ownership check',()=>{
    expect(notificationLoginPath(path,'?notices=1',true)).toBeNull();
  });
  it.each([['/trips/new','?notices=1'],['//other.example/path','?notices=1'],[path,''],['/start','?notices=1']])('does not change other entry paths', (pathname,search)=>{
    expect(notificationLoginPath(pathname,search,false)).toBeNull();
  });
});

describe('notification trip ownership',()=>{
  beforeEach(()=>{ vi.mocked(openApi).mockReset(); });
  it('admits an authenticated owner, including a guest test account',async()=>{
    vi.mocked(openApi).mockResolvedValue({trip_access:true});
    expect(await notificationTripAccess(path,'ko')).toBe(true);
    expect(openApi).toHaveBeenCalledWith('/v1/web/auth/me?trip_id='+path.split('/')[2],'ko');
  });
  it.each([false,undefined])('requires login when ownership is not confirmed: %s',async value=>{
    vi.mocked(openApi).mockResolvedValue({trip_access:value});
    expect(await notificationTripAccess(path,'ko')).toBe(false);
  });
  it('does not turn a connection failure into another consent request',async()=>{
    vi.mocked(openApi).mockRejectedValue(new Error('network'));
    let failure: unknown;
    try { await notificationTripAccess(path,'ko'); } catch (error) { failure=error; }
    expect(failure).toBeInstanceOf(Error);
    expect((failure as Error).message).toBe('network');
  });
  it('never probes an invalid or external path',async()=>{
    expect(await notificationTripAccess('//other.example/trips/new','ko')).toBe(false);
    expect(openApi).not.toHaveBeenCalled();
  });
});

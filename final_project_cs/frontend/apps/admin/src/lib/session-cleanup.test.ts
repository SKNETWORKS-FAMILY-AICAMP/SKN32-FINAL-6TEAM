import { QueryClient, QueryObserver } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { endOperatorQueries } from './session-cleanup';

function operatorClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, refetchOnWindowFocus: false } } });
}

describe('운영자 조회 캐시 경계', () => {
  it('A의 Case를 비운 뒤 B의 권한 조회를 실행하고 A의 자료를 반환하지 않는다', async () => {
    const client = operatorClient();
    const caseKey = ['operation-cases', 'c1'];
    const aData = { case_id: 'c1', evidence: 'A의 합성 여행 Case 근거' };
    const readA = vi.fn(async () => aData);
    const readB = vi.fn(async (): Promise<typeof aData> => { throw new Error('403: case:read permission denied'); });
    await client.fetchQuery({ queryKey: ['admin'], queryFn: async () => ({ operator: 'A' }) });
    await client.fetchQuery({ queryKey: caseKey, queryFn: readA });

    await endOperatorQueries(client);

    expect(client.getQueryCache().getAll()).toHaveLength(0);
    const observer = new QueryObserver(client, { queryKey: caseKey, queryFn: readB });
    const returnedData: unknown[] = [];
    const unsubscribe = observer.subscribe(result => { if (result.data !== undefined) returnedData.push(result.data); });
    try {
      await vi.waitFor(() => expect(observer.getCurrentResult().status).toBe('error'));
      expect(readA).toHaveBeenCalledTimes(1);
      expect(readB).toHaveBeenCalledTimes(1);
      expect(returnedData).toHaveLength(0);
      expect(observer.getCurrentResult().data).toBeUndefined();
    } finally {
      unsubscribe();
      client.clear();
    }
  });

  it('취소가 끝난 다음 캐시를 비운다', async () => {
    const client = operatorClient();
    client.setQueryData(['source-policy'], { operator: 'A' });
    let finishCancel!: () => void;
    const cancel = vi.spyOn(client, 'cancelQueries').mockImplementation(() => new Promise<void>(resolve => { finishCancel = resolve; }));
    const clear = vi.spyOn(client, 'clear');

    const cleanup = endOperatorQueries(client);
    expect(cancel).toHaveBeenCalledWith();
    expect(clear).not.toHaveBeenCalled();
    finishCancel();
    await cleanup;
    expect(clear).toHaveBeenCalledOnce();
    expect(client.getQueryCache().getAll()).toHaveLength(0);
  });

  it('진행 중인 이전 운영자의 조회가 늦게 끝나도 캐시를 다시 채우지 않는다', async () => {
    const client = operatorClient();
    let finishRead!: (value: { operator: string }) => void;
    let querySignal!: AbortSignal;
    const pending = client.fetchQuery({ queryKey: ['diagnostics', 'A'], queryFn: ({ signal }) => {
      querySignal = signal;
      return new Promise<{ operator: string }>(resolve => { finishRead = resolve; });
    } });
    const settled = pending.catch(cause => cause);

    await endOperatorQueries(client);

    expect(querySignal.aborted).toBe(true);
    expect(client.getQueryCache().getAll()).toHaveLength(0);
    finishRead({ operator: 'A' });
    await settled;
    expect(client.getQueryCache().getAll()).toHaveLength(0);
  });
});

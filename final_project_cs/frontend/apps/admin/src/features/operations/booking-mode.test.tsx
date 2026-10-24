import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { OperationsSettings } from './connected';

const state = vi.hoisted(() => ({ value: false }));
vi.mock('./source-policy', () => ({ SourcePolicySettings: () => null }));
vi.mock('../../lib/gateway', () => ({ operationCases: vi.fn(), operationSettings: vi.fn(), saveOperationSettings: vi.fn() }));
vi.mock('@tanstack/react-query', () => ({ useQuery: () => ({ data: { revision: 2, limits: [
  { name: 'travel.booking.enabled', label: '예약 마스터 — 새 예약 검색 · 등록 · 업체 인계', value: state.value, type: 'bool', text_ko: '기존 예약 정보와 잠금은 보존합니다.' },
  { name: 'unrelated', label: '다른 기능', value: true, type: 'bool' }
] }, isPending: false, isError: false, refetch: vi.fn() }) }));

describe('product admin booking master settings', () => {
  it.each([false, true])('renders the dedicated booking section from backend state %s', value => {
    state.value = value;
    const html = renderToStaticMarkup(<OperationsSettings />);
    expect(html).toContain('<legend>예약 기능</legend>');
    expect(html).toContain('기존 예약 정보와 잠금은 보존합니다.');
    expect(html.match(/예약 마스터 — 새 예약 검색/g)?.length).toBe(1);
    expect(html).toContain(value ? 'value="true" selected=""' : 'value="false" selected=""');
    expect(html).toContain('다른 기능');
    expect(html).toContain('현재 값 다시 읽기');
  });
});

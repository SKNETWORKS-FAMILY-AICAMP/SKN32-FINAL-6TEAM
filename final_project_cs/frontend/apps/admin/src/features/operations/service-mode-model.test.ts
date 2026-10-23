import { describe, expect, it } from 'vitest';
import { isServiceSetting, serviceModeTable } from './service-mode-model';

const cells = [
  { name: 'web.limits_enabled', label: '횟수 제한 켜기', value: false },
  { name: 'service.mode_enabled', label: '서비스 모드(켜면 하루 한도 + 회원 · 게스트 한 시간 한도)', value: false, text_ko: '하는 일: …' },
  { name: 'service.member.place_search.per_hour', label: '서비스 모드 — 회원(로그인) — 장소 검색 · 대체 후보 · 사진 — 한 시간', value: 120, min: 1, max: 100000 },
  { name: 'service.guest.place_search.per_hour', label: '서비스 모드 — 게스트(로그인 안 함) — 장소 검색 · 대체 후보 · 사진 — 한 시간', value: 20, min: 1, max: 100000 },
  { name: 'service.member.message.per_hour', label: '서비스 모드 — 회원(로그인) — 채팅 메시지 — 한 시간', value: 60 },
];

describe('service mode settings', () => {
  it('pulls the switch and one row per action with both tiers, in the server order', () => {
    const { toggle, rows } = serviceModeTable(cells);
    expect(toggle?.id).toBe('service.mode_enabled');
    expect(rows.map(row => [row.action, row.label, row.cells.member?.value, row.cells.guest?.value])).toEqual([
      ['place_search', '장소 검색 · 대체 후보 · 사진', 120, 20],
      ['message', '채팅 메시지', 60, undefined],
    ]);
  });

  it('keeps the other settings in the plain list', () => {
    expect(cells.filter(cell => !isServiceSetting(cell)).map(cell => cell.name)).toEqual(['web.limits_enabled']);
  });
});

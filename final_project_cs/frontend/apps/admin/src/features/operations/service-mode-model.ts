// `[2026-10-22 사용자 지시]` 서비스 모드 — 운영 설정 목록(`/admin/limits`)에서 스위치 하나와 「작업 × 등급」 한 시간 한도 표를 뽑는다.
// 이름 규칙은 cs 프로젝트 서버 `web_guard.py` 그대로: `service.mode_enabled` · `service.<member|guest>.<작업>.per_hour`.

export const SERVICE_MODE = 'service.mode_enabled';
export const TIERS = ['member', 'guest'] as const;
export type Tier = (typeof TIERS)[number];
export const TIER_LABELS: Record<Tier, string> = { member: '회원(로그인)', guest: '게스트(로그인 안 함)' };

export type SettingCell = { key?: string; name?: string; label?: string; label_ko?: string; value: number | string | boolean; min?: number; max?: number; text_ko?: string };
export type ServiceRow = { action: string; label: string; cells: Partial<Record<Tier, SettingCell & { id: string }>> };

const PATTERN = /^service\.(member|guest)\.([a-z_]+)\.per_hour$/;
const idOf = (cell: SettingCell) => cell.key || cell.name || '';

/** 서비스 모드에 속한 설정인가 — 일반 목록에서는 빼고 이 칸에서만 그린다. */
export const isServiceSetting = (cell: SettingCell) => idOf(cell) === SERVICE_MODE || PATTERN.test(idOf(cell));

/** 스위치 칸과 작업별 줄(서버가 보낸 순서 그대로). 라벨 「서비스 모드 — 등급 — 작업 — 한 시간」에서 작업 이름만 떼어 쓴다. */
export function serviceModeTable(cells: SettingCell[]): { toggle: (SettingCell & { id: string }) | null; rows: ServiceRow[] } {
  let toggle: (SettingCell & { id: string }) | null = null;
  const rows = new Map<string, ServiceRow>();
  for (const cell of cells) {
    const id = idOf(cell);
    if (id === SERVICE_MODE) { toggle = { ...cell, id }; continue; }
    const match = PATTERN.exec(id);
    if (!match) continue;
    const [, tier, action] = match as unknown as [string, Tier, string];
    const parts = (cell.label_ko || cell.label || action).split(' — ');
    const row = rows.get(action) ?? { action, label: parts.length >= 4 ? parts[2] : action, cells: {} };
    row.cells[tier] = { ...cell, id };
    rows.set(action, row);
  }
  return { toggle, rows: [...rows.values()] };
}

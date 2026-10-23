'use client';
import { serviceModeTable, TIERS, TIER_LABELS, type SettingCell } from './service-mode-model';

type Value = number | string | boolean;

/**
 * `[2026-10-22 사용자 지시]` 「서비스 모드」 — 스위치 하나와 작업별 「회원 · 게스트」 한 시간 한도 표. 운영 설정 폼 안에 들어가
 * 같은 저장 단추 · 변경 사유로 함께 저장된다(값이 바뀐 칸만 `changes` 에 실린다).
 */
export function ServiceModeFields({ cells, changes, onChange }: { cells: SettingCell[]; changes: Record<string, Value>; onChange: (id: string, value: Value) => void }) {
  const { toggle, rows } = serviceModeTable(cells);
  if (!toggle && !rows.length) return null;
  const on = Boolean(toggle ? changes[toggle.id] ?? toggle.value : false);
  return <fieldset style={{ margin: '1rem 0', padding: '1rem', border: '1px solid #ccc', borderRadius: 8 }}>
    <legend><strong>서비스 모드</strong> {on ? '켜짐 — 한도 적용 중' : '꺼짐 — 시험 단계(한 시간 한도를 세지도 막지도 않음)'}</legend>
    {toggle && <label style={{ display: 'block', marginBottom: '1rem' }}>{toggle.label_ko || toggle.label}
      <small style={{ display: 'block', whiteSpace: 'pre-line' }}>{toggle.text_ko}</small>
      <select value={String(on)} onChange={e => onChange(toggle.id, e.target.value === 'true')}><option value="true">켜짐</option><option value="false">꺼짐</option></select>
    </label>}
    {rows.length > 0 && <div style={{ overflowX: 'auto' }}><table>
      <caption style={{ textAlign: 'left' }}>한 사람이 한 시간에 할 수 있는 횟수 — 넘으면 다음 정시까지 그 작업만 막힙니다</caption>
      <thead><tr><th scope="col">작업</th>{TIERS.map(tier => <th key={tier} scope="col">{TIER_LABELS[tier]}</th>)}</tr></thead>
      <tbody>{rows.map(row => <tr key={row.action}><th scope="row">{row.label}</th>{TIERS.map(tier => {
        const cell = row.cells[tier];
        return <td key={tier}>{cell ? <input type="number" aria-label={`${row.label} — ${TIER_LABELS[tier]} — 한 시간 횟수`} min={cell.min} max={cell.max}
          value={String(changes[cell.id] ?? cell.value)} onChange={e => onChange(cell.id, Number(e.target.value))} style={{ width: '7rem' }} /> : '—'}</td>;
      })}</tr>)}</tbody>
    </table></div>}
  </fieldset>;
}

'use client';
import type { SettingCell } from './service-mode-model';

export const BOOKING_SETTING = 'travel.booking.enabled';
export const isBookingSetting = (cell: SettingCell) => (cell.key || cell.name) === BOOKING_SETTING;

type Value = number | string | boolean;
/** Same authenticated settings form, revision, reason and save/readback as other runtime settings. */
export function BookingModeFields({ cells, changes, onChange }: { cells: (SettingCell & { editable?: boolean })[]; changes: Record<string, Value>; onChange: (id: string, value: Value) => void }) {
  const cell = cells.find(isBookingSetting);
  if (!cell) return null;
  const on = (changes[BOOKING_SETTING] ?? cell.value) === true;
  return <fieldset style={{ margin: '1rem 0', padding: '1rem', border: '1px solid #ccc', borderRadius: 8 }}>
    <legend>예약 기능</legend>
    <label>{cell.label_ko || cell.label || '예약 마스터'}
      <small style={{ display: 'block', whiteSpace: 'pre-line' }}>{cell.text_ko}</small>
      <select aria-label="예약 마스터" disabled={cell.editable === false} value={String(on)} onChange={e => onChange(BOOKING_SETTING, e.target.value === 'true')}>
        <option value="false">꺼짐</option><option value="true">켜짐</option>
      </select>
    </label>
    <p>기본 꺼짐입니다. 켜더라도 미구현 예약 기능을 추가하거나 업체 거래 승인을 대신하지 않습니다.</p>
  </fieldset>;
}

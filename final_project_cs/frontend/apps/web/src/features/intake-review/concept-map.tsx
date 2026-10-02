"use client";

import type { ReviewItem } from "@/lib/live/intake-review";
import { useT } from "@/lib/settings";
import { cx } from "./cx";
import type { PinSpot } from "./review-model";
import styles from "./review-map.module.css";

/** 「①②③…」 for the stops that have no pin yet (the mockup's 「② 올리브영 · 위치 미정」). Past twenty it falls back to a plain number. */
const circled = (n: number) => n >= 1 && n <= 20 ? String.fromCodePoint(0x245f + n) : String(n);

/**
 * The map of the mockup — a visit-order diagram drawn from the real coordinates (the pins keep their true places relative
 * to each other, the streets behind them are only a picture). A stop with no coordinates is not given a pin; it is shown as
 * 「위치 미정」 between its neighbours, so a missing place is never drawn as if it were somewhere.
 */
export function ConceptMap({ items, spots, selected, onSelect }: {
  /** One day's stops, in order. */
  items: readonly ReviewItem[];
  spots: readonly PinSpot[];
  /** A stop's id, or a leg's `from:to`. */
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const t = useT();
  const spot = new Map(spots.map((entry) => [entry.id, entry]));
  const legs = items.slice(1).map((item, index) => ({ key: `${items[index].id}:${item.id}`, from: spot.get(items[index].id), to: spot.get(item.id) }));
  return <div className={styles.map}>
    <svg className={styles.bg} viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
      <rect width="400" height="300" fill="#e9ebe6" />
      <path d="M40 30Q90 0 150 25Q170 60 120 80Q60 85 40 30Z" fill="#dde5d6" />
      <path d="M190 175Q240 155 282 188Q292 230 240 246Q190 240 190 175Z" fill="#dde5d6" />
      <path d="M-20 262C70 236 150 284 240 258S370 228 430 246L430 320L-20 320Z" fill="#d6e1e8" />
      <g stroke="#fff" fill="none" strokeLinecap="round">
        <path d="M0 112H400M0 176H400M108 0V300M262 0V300M30 0L170 300M340 0L304 300" strokeWidth="7" />
        <path d="M0 60H400M0 222H400M60 0V240M180 0V250M320 0V230M210 0L150 300" strokeWidth="3" />
      </g>
    </svg>
    <div className={styles.layer}>
      <svg className={styles.route} viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true" focusable="false">
        {legs.map(({ key, from, to }) => from && to && <polyline key={key} className={cx(selected === key && styles.on)} points={`${from.x},${from.y} ${to.x},${to.y}`} />)}
      </svg>
      {items.map((item, index) => {
        const at = spot.get(item.id);
        if (!at) return null;
        const name = item.place?.name ?? item.title;
        return at.located
          ? <button key={item.id} type="button" className={cx(styles.pin, selected === item.id && styles.pin_on)} style={{ left: `${at.x}%`, top: `${at.y}%` }} aria-pressed={selected === item.id} aria-label={t(`${index + 1}번 ${name}`, `Stop ${index + 1}: ${name}`)} onClick={() => onSelect(item.id)}><i>{index + 1}</i></button>
          : <button key={item.id} type="button" className={cx(styles.nopin, selected === item.id && styles.nopin_on)} style={{ left: `${at.x}%`, top: `${at.y}%` }} aria-pressed={selected === item.id} onClick={() => onSelect(item.id)}>{circled(index + 1)} {name} · {t("위치 미정", "location not set")}</button>;
      })}
    </div>
    <span className={styles.note}>{t("위치 개념도 · 실제 지도 아님", "Concept map · not a real map")}</span>
  </div>;
}

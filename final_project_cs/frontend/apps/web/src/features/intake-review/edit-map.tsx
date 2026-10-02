"use client";

import { useT } from "@/lib/settings";
import { cx } from "./cx";
import { letterOf, type EditCard } from "./edit-model";
import { projectPoints } from "./review-model";
import type { ReviewItem } from "@/lib/live/intake-review";
import mapStyles from "./review-map.module.css";
import styles from "./edit-screen.module.css";

/**
 * The map of the edit screen (mockup 「수정 화면 지도」): the day's other stops stay grey and fixed, the current place is dark,
 * and the alternatives carry letters A, B, C… — the ones the customer can press to bring that card forward. A card whose place
 * has no coordinates gets no pin (it still has its card).
 */
export function EditMap({ order, others, cards, index, onPick }: {
  /** The position the stop being edited has in its day (1-based) — the number on its pin. */
  order: number;
  /** The day's other stops, with the position each has in the day. */
  others: readonly { item: ReviewItem; order: number }[];
  cards: readonly EditCard[];
  index: number;
  onPick: (index: number) => void;
}) {
  const t = useT();
  const located = (place: { latitude: number | null; longitude: number | null } | null) => typeof place?.latitude === "number" && typeof place?.longitude === "number";
  const points = [
    ...others.filter(({ item: other }) => located(other.place)).map(({ item: other }) => ({ id: `s:${other.id}`, lat: other.place!.latitude as number, lng: other.place!.longitude as number })),
    ...cards.flatMap((card, i) => located(card.place) ? [{ id: `c:${i}`, lat: card.place!.latitude as number, lng: card.place!.longitude as number }] : []),
  ];
  const at = projectPoints(points);
  return <div className={mapStyles.map}>
    <svg className={mapStyles.bg} viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
      <rect width="400" height="300" fill="#e9ebe6" />
      <path d="M40 30Q90 0 150 25Q170 60 120 80Q60 85 40 30Z" fill="#dde5d6" />
      <path d="M190 175Q240 155 282 188Q292 230 240 246Q190 240 190 175Z" fill="#dde5d6" />
      <path d="M-20 262C70 236 150 284 240 258S370 228 430 246L430 320L-20 320Z" fill="#d6e1e8" />
      <g stroke="#fff" fill="none" strokeLinecap="round">
        <path d="M0 112H400M0 176H400M108 0V300M262 0V300M30 0L170 300M340 0L304 300" strokeWidth="7" />
        <path d="M0 60H400M0 222H400M60 0V240M180 0V250M320 0V230M210 0L150 300" strokeWidth="3" />
      </g>
    </svg>
    <div className={mapStyles.layer}>
      {others.map(({ item: other, order: place }) => {
        const spot = at.get(`s:${other.id}`);
        return spot ? <span key={other.id} className={cx(mapStyles.pin, styles.pinGray)} style={{ left: `${spot.x}%`, top: `${spot.y}%` }} aria-hidden="true"><i>{place}</i></span> : null;
      })}
      {cards.map((card, i) => {
        const spot = at.get(`c:${i}`);
        if (!spot) return null;
        const name = card.place?.name ?? "";
        const label = i === 0 ? t(`지금 장소 ${name}`, `Current place ${name}`) : t(`후보 ${letterOf(i)} ${name}`, `Alternative ${letterOf(i)} ${name}`);
        return <button key={card.key} type="button" className={cx(mapStyles.pin, i === 0 ? styles.pinCurrent : styles.pinCandidate, i === index && styles.pinOn)}
          style={{ left: `${spot.x}%`, top: `${spot.y}%` }} aria-pressed={i === index} aria-label={label} onClick={() => onPick(i)}><i>{i === 0 ? order : letterOf(i)}</i></button>;
      })}
    </div>
    <span className={mapStyles.note}>{t("위치 개념도 · 실제 지도 아님", "Concept map · not a real map")}</span>
  </div>;
}

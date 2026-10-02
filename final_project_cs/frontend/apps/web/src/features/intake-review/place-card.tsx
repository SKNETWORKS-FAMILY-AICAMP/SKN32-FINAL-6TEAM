"use client";

import type { ReactNode } from "react";
import type { ReviewItem } from "@/lib/live/intake-review";
import { useT } from "@/lib/settings";
import { cx } from "./cx";
import { CheckRows, Mark } from "./marks";
import { statusTone, statusWord } from "./review-model";
import styles from "./review-sheet.module.css";

export interface PlaceRowProps {
  item: ReviewItem;
  /** The day's last stop — the rail ends there. */
  last: boolean;
  open: boolean;
  selected: boolean;
  onToggle: () => void;
  /** Before the name: the lock. Optional — a row with no action has none. */
  lead?: ReactNode;
  /** After the status word: edit, delete. */
  trail?: ReactNode;
  /** Under the check lines: the card's buttons. Told whether the card is open (what is only needed open is read then). */
  actions?: (open: boolean) => ReactNode;
  /** The server is checking this stop (while it streams, or again after a change) — the status word is a spinner and the card stays open. */
  checking?: boolean;
  /** The row slides in when it appears (while the check streams in). `delayMs` staggers the stops that were already there. */
  fresh?: { delayMs: number };
}

/**
 * One stop of the day: its time on the left, the rail with a dot, and the card. Closed it shows the name and the status;
 * open it shows the check lines (place · time · hours · closed day) the server worked out.
 */
export function PlaceRow({ item, last, open, selected, onToggle, lead, trail, actions, checking = false, fresh }: PlaceRowProps) {
  const t = useT();
  const name = item.place?.name ?? item.title;
  const tone = statusTone(item.status);
  const shown = open || checking;
  return <div className={cx(styles.tlr, last && styles.lastday, fresh && styles.fresh)} style={fresh?.delayMs ? { animationDelay: `${fresh.delayMs}ms` } : undefined} data-item={item.id}>
    <div className={styles.time}>{item.starts_at ?? ""}</div>
    <div className={styles.rail}><span className={cx(styles.dot, !checking && tone === "ok" && styles.dot_ok, !checking && tone === "warn" && styles.dot_warn)} /></div>
    <div className={styles.cell}>
      <div className={cx(styles.card, item.status === "review" && styles.card_review, item.locked && styles.card_locked, selected && styles.card_on, shown && styles.open)} data-key={item.id}>
        <div className={styles.top}>
          {lead}
          <button type="button" className={styles.cardHead} aria-expanded={shown} onClick={onToggle}>
            <span className={styles.name}>{name}</span>
          </button>
          {checking
            ? <span className={styles.pillWait} role="status"><i className={styles.spinner} />{t("확인 중", "Checking")}</span>
            : <span className={cx(styles.pill, item.status === "adjusted" && styles.pill_adjusted, item.status === "review" && styles.pill_review)}>
              {item.status === null ? <Mark tone="none" /> : null}{statusWord(item.status, t)}
            </span>}
          {trail}
        </div>
        <div className={styles.collapse}>
          <div className={styles.collapseIn} inert={!shown}>
            <div className={styles.cardIn}>
              <CheckRows rows={item.rows ?? []} />
              {actions?.(shown)}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>;
}

"use client";

import { useT } from "@/lib/settings";
import type { CheckLine } from "@/lib/live/intake-review";
import { cx } from "./cx";
import { ITEM_ROW_LABEL, MARK_GLYPH, MARK_TONE, markLabel, type MarkTone } from "./review-model";
import styles from "./review-sheet.module.css";

/** The little round mark in front of a check line or a card. It has a name for a screen reader, not only a colour. */
export function Mark({ tone, label }: { tone: MarkTone; label?: string }) {
  const t = useT();
  const text = label ?? markLabel(tone, t);
  return <i className={cx(styles.mk, styles[`mk_${tone}`])} role="img" aria-label={text} title={text}>{MARK_GLYPH[tone]}</i>;
}

/** A stop's or a leg's check lines: 「✓ 장소  관광공사 정보로 찾았어요」. */
export function CheckRows({ rows, fresh }: { rows: readonly CheckLine[]; fresh?: boolean }) {
  const t = useT();
  return <div className={styles.cks}>
    {rows.map((row) => {
      const tone = MARK_TONE[row.result];
      const label = ITEM_ROW_LABEL[row.row];
      return <div key={row.row} className={cx(styles.ck, styles[`ck_${tone}`], fresh && styles.ckFresh)}>
        <Mark tone={tone} />
        <b>{label ? t(...label) : row.row}</b>
        <span className={styles.ckText}>{row.text}</span>
      </div>;
    })}
  </div>;
}

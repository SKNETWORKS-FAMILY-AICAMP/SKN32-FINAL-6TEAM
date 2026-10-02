"use client";

import { ChevronDown } from "lucide-react";
import type { ReviewMove } from "@/lib/live/intake-review";
import { useT } from "@/lib/settings";
import { cx } from "./cx";
import { CheckRows, Mark } from "./marks";
import { statusTone } from "./review-model";
import styles from "./review-sheet.module.css";

export interface MoveRowProps {
  move: ReviewMove;
  open: boolean;
  selected: boolean;
  onToggle: () => void;
  /** The server is measuring this leg again (after a change). */
  checking?: boolean;
  /** The row slides in when it appears (while the check streams in). */
  fresh?: boolean;
}

/**
 * The way from one stop to the next: a line in the gap between two cards, not a card. It shows the mode, the time and the
 * server's mark; pressed, it opens to the route, the mode and the arrival the server worked out.
 *
 * ★A leg estimated in a straight line says so (`[추정]` is in the server's sentence) — the screen does not smooth it over.
 */
export function MoveRow({ move, open, selected, onToggle, checking = false, fresh = false }: MoveRowProps) {
  const t = useT();
  const tone = statusTone(move.status);
  const shown = open && !checking;
  const mode = move.mode_label ?? t("이동", "Move");
  return <div className={cx(styles.tlr, styles.mvr, move.status === "review" && styles.mvr_review, fresh && styles.fresh)} data-move={`${move.from}:${move.to}`}>
    <div className={cx(styles.time, styles.dep)}>{move.depart && <><b>{move.depart}</b><small>{t("출발", "leave")}</small></>}</div>
    <div className={styles.rail}><span className={styles.mvDot} /></div>
    <div className={styles.mvCell}>
      <div className={cx(styles.mv, shown && styles.mv_open, selected && styles.mv_on)} data-key={`${move.from}:${move.to}`}>
        <button type="button" className={styles.mvHead} aria-expanded={shown} aria-label={`${t("이동", "Move")} ${mode} ${move.summary}`} onClick={onToggle}>
          {move.mode_label && <span className={styles.mvMode}>{move.mode_label}</span>}
          <span className={styles.mvText}>{checking ? t("이동 경로 다시 찾는 중…", "Measuring the way again…") : move.summary}</span>
          {checking ? <i className={styles.spinner} /> : <Mark tone={tone} />}
          <ChevronDown size={15} aria-hidden="true" className={styles.chev} />
        </button>
        <div className={styles.collapse}>
          <div className={styles.collapseIn} inert={!shown}>
            <div className={styles.mvIn}><CheckRows rows={move.rows} /></div>
          </div>
        </div>
      </div>
    </div>
  </div>;
}

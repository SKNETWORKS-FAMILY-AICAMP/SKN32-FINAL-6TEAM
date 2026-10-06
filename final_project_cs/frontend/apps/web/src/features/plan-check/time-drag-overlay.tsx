"use client";

import { useT } from "@/lib/settings";
import { minimap } from "./day-minimap";
import { formatHm } from "./time-plan";
import { heldTexts, type TimeDrag } from "./use-time-edit";
import styles from "./plan-check.module.css";

const signed = (minutes: number) => `${minutes > 0 ? "+" : minutes < 0 ? "−" : "±"}${Math.abs(minutes)}분`;

/**
 * `[2026-10-05 사용자 지시]` Shown while the grip of a time is dragged: what is being moved and by how much, the notice when the free time is used up, and the WHOLE DAY as a strip -
 * every stop where it was (a dashed outline) and where it would stand now (filled) - so the customer sees how much of the day the drag moves. It takes no touches (the finger is on the grip).
 */
export function TimeDragOverlay({ drag }: { drag: TimeDrag }) {
  const t = useT();
  const map = minimap(drag.day.stops, drag.day.legs, drag.changes, drag.id);
  const span = Math.max(1, map.to - map.from);
  const left = (minutes: number) => `${(((minutes - map.from) / span) * 100).toFixed(2)}%`;
  const width = (start: number, end: number) => `${Math.max(1.6, (((end - start) / span) * 100)).toFixed(2)}%`;
  const delta = drag.from !== null && drag.to !== null ? drag.to - drag.from : 0;
  const what = drag.kind === "depart" ? t("출발", "Leave") : t("시작", "Start");
  const summary = map.pushed
    ? t(`다른 일정 ${map.pushed}곳이 움직여요 · 가장 많이 ${signed(map.largestPush)} · 하루 끝 ${formatHm(map.dayEnd.before)} → ${formatHm(map.dayEnd.after)}`, `${map.pushed} other stop${map.pushed > 1 ? "s" : ""} move · most ${signed(map.largestPush)} · the day ends ${formatHm(map.dayEnd.before)} → ${formatHm(map.dayEnd.after)}`)
    : t("다른 일정은 그대로예요", "No other stop moves");
  const slack = map.slackAfter === null ? null : map.slackAfter >= 0 ? t(`여유 ${map.slackAfter}분`, `${map.slackAfter} min free`) : t(`${Math.abs(map.slackAfter)}분 겹쳐요`, `${Math.abs(map.slackAfter)} min overlap`);
  return <div className={styles.dragOverlay} data-overlay="time" role="group" aria-label={t("하루 일정 미니맵", "The whole day")} data-held={drag.held ?? undefined}>
    <p className={styles.dragHead}><strong>{drag.title}</strong>
      <span>{what} {drag.from === null ? "–" : formatHm(drag.from)} → {drag.to === null ? "–" : formatHm(drag.to)} ({signed(delta)})</span></p>
    {drag.held && <p className={styles.dragHeld}>{t(...heldTexts(drag.kind, drag.held))}</p>}
    <div className={styles.miniTrack} aria-hidden="true">
      {map.blocks.map((block) => {
        const changed = block.shift !== 0 || block.after.end !== block.before.end;
        return <span key={block.id}>
          {changed && <span className={styles.miniGhost} style={{ left: left(block.before.start), width: width(block.before.start, block.before.end) }} />}
          <span className={styles.miniBlock} data-active={block.active || undefined} data-moved={(!block.active && changed) || undefined} data-fixed={block.fixed || undefined}
            style={{ left: left(block.after.start), width: width(block.after.start, block.after.end) }} />
        </span>;
      })}
    </div>
    <p className={styles.miniAxis} aria-hidden="true"><span>{formatHm(map.from)}</span><span>{formatHm(map.to)}</span></p>
    <p className={styles.dragSum}>{summary}{slack ? ` · ${slack}` : ""}</p>
  </div>;
}

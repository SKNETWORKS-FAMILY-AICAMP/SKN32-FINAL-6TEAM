"use client";

import { Bike, Bus, Car, Footprints, Lock, LockOpen, Pencil, Sparkles, Trash2, TrainFront, Undo2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui";
import { ro } from "@/lib/josa";
import { useT } from "@/lib/settings";
import { draftProblem, draftOfItem, timeline, type CheckRow, type PlanCheckView, type PlanDay, type PlanItem, type PlanMove } from "./model";
import { Act, Checks, reason, VerdictMark } from "./parts";
import type { PlanCheckActions } from "./plan-check";
import styles from "./plan-check.module.css";

/** Everything a row of the list needs from the screen, in one place (the list is drawn twice when a preview stands under the plan). */
export interface RowContext {
  done: boolean;
  /** The card or move that is open, and the stop picked on the map or in the list. */
  open: string | null;
  selected: string | null;
  frozen: string | null;
  actions: PlanCheckActions;
  explain: (why: string) => void;
  /** The stop being checked again just now (the recheck ticker). */
  rechecking: string | null;
  /** Stops changed since the last check, and what each had been (「바뀜 · 이전 …」). */
  changed: ReadonlySet<string>;
  was: Readonly<Record<string, string>>;
  /** Stops marked for deletion: grey, with 「되돌리기」 where the bin is; they are really taken out when the plan is checked again. */
  removed: ReadonlySet<string>;
  /** The checks to show for a stop while they are being ticked in again (null = the stop's own). */
  rowsFor: (item: PlanItem) => CheckRow[] | null;
  onPick: (id: string) => void;
  onToggleMove: (id: string) => void;
  onChange: (item: PlanItem) => void;
  onDelete: (item: PlanItem) => void;
  onRestore: (item: PlanItem) => void;
  onLock: (item: PlanItem) => void;
  onRecommend: (item: PlanItem) => void;
  /** ★`[2026-10-04 사용자 지시]` The time at the left of a stop is pressed to change it: the stop whose times are being edited, and the calls. */
  timeEditing: string | null;
  onEditTime: (item: PlanItem) => void;
  onSaveTime: (item: PlanItem, start: string, end: string) => Promise<void>;
  onCancelTime: () => void;
  /** `""` for the plan as it is, `"after-"` for the proposed one: the same stop stands in both lists, and an id is one element's. */
  prefix: string;
  /** Which entries to draw (the 「확인 필요」 and 「바뀜」 filters). */
  visible: (entry: ReturnType<typeof timeline>[number]) => boolean;
}

/** The days of a view, each with its timeline: stops (cards) and the moves between them. */
export function DayList({ view, days, listDay, ctx, mapDay, onShowDay, heading }: {
  view: PlanCheckView;
  days: PlanDay[];
  listDay: number | "all";
  ctx: RowContext;
  mapDay: number;
  onShowDay: (day: number) => void;
  heading: (day: PlanDay) => ReactNode;
}) {
  return <>{days.filter((day) => (listDay === "all" || day.day === listDay) && timeline(view, day.day).some(ctx.visible)).map((day) =>
    <section key={day.day} aria-labelledby={`${ctx.prefix}plan-day-${day.day}`}>
      <h3 id={`${ctx.prefix}plan-day-${day.day}`} className={styles.day}>{ctx.done
        ? <button type="button" className={styles.dayButton} aria-pressed={mapDay === day.day} onClick={() => onShowDay(day.day)}>{heading(day)}</button>
        : heading(day)}</h3>
      <ol className={styles.timeline}>{timeline(view, day.day).filter(ctx.visible).map((entry) => entry.type === "item"
        ? <ItemRow key={entry.item.id} item={entry.item} ctx={ctx} rechecking={view.rechecking === entry.item.id || ctx.rechecking === entry.item.id} />
        : <MoveRow key={entry.move.id} move={entry.move} ctx={ctx} dim={ctx.removed.has(entry.move.fromId) || ctx.removed.has(entry.move.toId)} />)}</ol>
    </section>)}</>;
}

/**
 * One stop's card: the lock, the name (opens and closes the card), its state, edit and delete; inside, its checks and
 * 「자동 추천」 · 「수정」. A tool that cannot act now stays and says why (locked, being checked, not connected yet).
 *
 * ★`[2026-10-04 사용자 지시]` The state beside the name says only what the customer must know: 「확인 필요」 when something needs a look, 「변경 완료」 when the stop was changed
 *   (blue, like 「확인 필요」 is amber); a stop that is simply fine says nothing (the old 「조정」 told no one anything). A stop marked for deletion is grey and has 「되돌리기」 where the bin is.
 */
function ItemRow({ item, ctx, rechecking }: { item: PlanItem; ctx: RowContext; rechecking: boolean }) {
  const t = useT();
  const { done, actions, explain, frozen } = ctx;
  const open = !done || ctx.open === item.id || item.verdict === null;
  const selected = done && ctx.selected === item.id;
  const checking = item.verdict === null;
  const review = item.verdict === "review";
  const removed = ctx.removed.has(item.id);
  const changed = ctx.changed.has(item.id);
  const changedFrom = ctx.was[item.id];
  const lockedWhy = t("고정한 일정이라 바꿀 수 없어요 · 잠금을 풀면 수정할 수 있어요", "Locked · unlock it to change it");
  const removedWhy = t("삭제할 일정이에요 · 「되돌리기」를 누르면 다시 쓸 수 있어요", "Marked for deletion · press Undo to keep it");
  const lockWhy = removed ? removedWhy : !actions.lock ? t("잠금은 준비 중이에요", "Locking is coming") : review ? t("확인이 필요한 일정은 먼저 고쳐야 고정할 수 있어요", "Fix this stop before locking it") : frozen;
  const changeWhy = removed ? removedWhy : !actions.replace && !actions.edit ? t("수정은 준비 중이에요", "Editing is coming") : item.locked ? lockedWhy : frozen;
  const autoWhy = removed ? removedWhy : !actions.autoRecommend ? t("자동 추천은 준비 중이에요", "Recommending is coming") : item.locked ? lockedWhy : frozen;
  const deleteWhy = !actions.remove ? t("삭제는 준비 중이에요", "Deleting is coming") : item.locked ? t("고정한 일정은 삭제할 수 없어요 · 잠금을 먼저 풀어 주세요", "Locked stops cannot be deleted · unlock it first") : frozen;
  const lockLabel = review ? t("확인이 필요한 일정은 고정할 수 없어요", "Stops that need a look cannot be locked") : item.locked ? t(`${item.title} 고정 풀기`, `Unlock ${item.title}`) : t(`${item.title} 꼭 넣을 일정으로 고정`, `Lock ${item.title} in`);
  // Being checked again (after a change, or in a full re-check): a waiting label in place of the state.
  const status: ReactNode = done && (checking || rechecking)
    ? <span className={styles.pillWait}><span className={styles.spinner} aria-hidden="true" />{rechecking ? t("재검증", "Checking") : t("확인 중", "Checking")}</span>
    : checking ? <span className={styles.spinner} role="img" aria-label={t("확인하는 중", "Checking")} />
      : removed ? <span className={styles.pill} data-state="removed">{t("삭제 예정", "To delete")}</span>
        : review ? <span className={styles.pill} data-state="review">{t("확인 필요", "Check")}</span>
          : changed ? <span className={styles.pill} data-state="changed"><span aria-hidden="true">✓ </span>{t("변경 완료", "Changed")}</span> : null;
  const note = item.locked ? lockedWhy
    : !actions.autoRecommend ? t("자동 추천은 준비 중이에요 · 수정에서 장소를 바꿀 수 있어요", "Recommending is coming · change the place in Edit")
      : item.suggestion ? t(`자동 추천은 1순위 ${ro(item.suggestion)} 바로 바꿔요`, `Recommend changes it to the first alternative, ${item.suggestion}`) : null;
  const rows = ctx.rowsFor(item) ?? item.checks;
  const timeWhy = removed ? removedWhy : !actions.edit ? t("시간 고치기는 준비 중이에요", "Changing the time is coming") : item.locked ? lockedWhy : frozen;
  return <li className={styles.entry} data-type="item" data-entry-id={item.id} data-verdict={item.verdict ?? "checking"} data-selected={selected || undefined} data-changed={changed || undefined} data-removed={removed || undefined}>
    {done
      ? <Act className={styles.time} data-editing={ctx.timeEditing === item.id || undefined} why={timeWhy} explain={explain} onPress={() => ctx.onEditTime(item)}
          title={t("눌러서 시간 고치기", "Press to change the time")} aria-label={t(`${item.title} 시간 고치기 · 지금 ${item.startsAt || "시간 없음"}`, `Change the time of ${item.title} · now ${item.startsAt || "no time"}`)}>{item.startsAt || "–"}</Act>
      : <span className={styles.time}>{item.startsAt || "–"}</span>}
    <span className={styles.rail} aria-hidden="true"><span className={styles.dot} /></span>
    <article id={`${ctx.prefix}plan-card-${item.id}`} className={styles.card} data-locked={item.locked || undefined} aria-labelledby={`${ctx.prefix}plan-item-${item.id}`} aria-busy={checking}>
      {done
        // Once done a card opens and closes (accordion: the heading holds the button).
        ? <div className={styles.cardTop}>
            <Act className={styles.icon} why={lockWhy} explain={explain} onPress={() => ctx.onLock(item)} aria-pressed={item.locked} aria-label={lockLabel} title={lockLabel}>
              {item.locked ? <Lock size={16} strokeWidth={1.8} aria-hidden="true" /> : <LockOpen size={16} strokeWidth={1.8} aria-hidden="true" />}</Act>
            <h4 className={styles.cardHeading}><button type="button" className={styles.cardHead} aria-expanded={open} aria-controls={`${ctx.prefix}plan-item-${item.id}-checks`} onClick={() => ctx.onPick(item.id)}>
              <span className={styles.cardName}>
                <span id={`${ctx.prefix}plan-item-${item.id}`} className={styles.cardTitle}>{item.title}</span>
                {changedFrom && <small className={styles.cardWritten} data-changed>{t(`바뀜 · 이전 ${changedFrom}`, `Changed · was ${changedFrom}`)}</small>}
                {item.written && <small className={styles.cardWritten}>{t(`원문 「${item.written}」`, `As written: “${item.written}”`)}</small>}
              </span>
            </button></h4>
            {status}
            <Act id={`${ctx.prefix}plan-edit-${item.id}`} className={styles.icon} why={changeWhy} explain={explain} onPress={() => ctx.onChange(item)} aria-label={t(`${item.title} 수정`, `Edit ${item.title}`)}><Pencil size={16} strokeWidth={1.8} aria-hidden="true" /></Act>
            {removed
              ? <button type="button" id={`${ctx.prefix}plan-restore-${item.id}`} className={styles.icon} data-restore onClick={() => ctx.onRestore(item)} aria-label={t(`${item.title} 삭제 되돌리기`, `Undo deleting ${item.title}`)} title={t("되돌리기", "Undo")}><Undo2 size={16} strokeWidth={1.8} aria-hidden="true" /></button>
              : <Act id={`${ctx.prefix}plan-delete-${item.id}`} className={styles.icon} why={deleteWhy} explain={explain} onPress={() => ctx.onDelete(item)} aria-label={t(`${item.title} 삭제`, `Delete ${item.title}`)}><Trash2 size={16} strokeWidth={1.8} aria-hidden="true" /></Act>}
          </div>
        : <header className={styles.cardHead}><span className={styles.cardName}><h4 id={`${ctx.prefix}plan-item-${item.id}`} className={styles.cardTitle}>{item.title}</h4>{item.written && <small className={styles.cardWritten}>{t(`원문 「${item.written}」`, `As written: “${item.written}”`)}</small>}</span>{status}</header>}
      {done && ctx.timeEditing === item.id && !removed && <TimeEditor item={item} onSave={(start, end) => ctx.onSaveTime(item, start, end)} onCancel={ctx.onCancelTime} />}
      {open && !removed && <div id={`${ctx.prefix}plan-item-${item.id}-checks`}>
        {rows.length
          ? <Checks rows={rows} />
          : <p className={styles.noChecks}>{t("서버가 이 일정에 따로 알린 것이 없어요.", "The server has nothing more on this stop.")}</p>}
        {done && !checking && <>
          <div className={styles.cardActions}>
            <Act className={styles.action} why={autoWhy} explain={explain} onPress={() => ctx.onRecommend(item)}><Sparkles size={15} strokeWidth={1.8} aria-hidden="true" />{t("자동 추천", "Recommend")}</Act>
            <Act className={styles.action} data-primary why={changeWhy} explain={explain} onPress={() => ctx.onChange(item)}><Pencil size={15} strokeWidth={1.8} aria-hidden="true" />{t("수정", "Edit")}</Act>
          </div>
          {note && <p className={styles.cardNote}>{note}</p>}
        </>}
      </div>}
    </article>
  </li>;
}

/**
 * The stop's own times, changed in place (the time at the left of the card was pressed): start and end. Whether the new times fit (hours, the way there) is the server's to say
 * when it checks the plan again; the screen only refuses an end before the start.
 */
function TimeEditor({ item, onSave, onCancel }: { item: PlanItem; onSave: (start: string, end: string) => Promise<void>; onCancel: () => void }) {
  const t = useT();
  const [start, setStart] = useState(item.startsAt);
  const [end, setEnd] = useState(item.endsAt);
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState("");
  async function save() {
    const found = draftProblem({ ...draftOfItem(item), start, end });
    if (found === "time") { setProblem(t("끝 시각이 시작보다 빨라요.", "The end is before the start.")); return; }
    if (!start) { setProblem(t("시작 시각을 적어 주세요.", "Give a start time.")); return; }
    setSaving(true);
    try { await onSave(start, end); }
    catch (error) { setProblem(reason(error)); setSaving(false); }
  }
  return <form className={styles.timeEditor} aria-label={t(`${item.title} 시간 고치기`, `Change the time of ${item.title}`)} noValidate
    onSubmit={(event) => { event.preventDefault(); void save(); }}
    onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); onCancel(); } }}>
    <label className={styles.field}>{t("시작", "Start")}<input type="time" value={start} aria-invalid={Boolean(problem)} autoFocus onChange={(event) => { setStart(event.target.value); setProblem(""); }} /></label>
    <label className={styles.field}>{t("끝", "End")}<input type="time" value={end} aria-invalid={Boolean(problem)} onChange={(event) => { setEnd(event.target.value); setProblem(""); }} /></label>
    <div className={styles.timeButtons}>
      <Button onClick={onCancel} disabled={saving}>{t("취소", "Cancel")}</Button>
      <Button variant="primary" type="submit" disabled={saving}>{saving ? t("저장하는 중…", "Saving…") : t("저장", "Save")}</Button>
    </div>
    {problem && <p className={styles.editorError} role="alert">{problem}</p>}
  </form>;
}

/** The icon for how the leg is travelled — chosen from the server's own words for the mode; none when they say something else. */
function ModeIcon({ mode }: { mode: string }) {
  const props = { size: 14, strokeWidth: 1.8, "aria-hidden": true as const };
  if (/도보|걷/.test(mode)) return <Footprints {...props} />;
  if (/지하철|전철|철도|기차/.test(mode)) return <TrainFront {...props} />;
  if (/버스/.test(mode)) return <Bus {...props} />;
  if (/택시|자동차|차량/.test(mode)) return <Car {...props} />;
  if (/자전거|따릉이/.test(mode)) return <Bike {...props} />;
  return null;
}

/**
 * ★`[2026-10-04 사용자 지시]` The way to the next place says only how long and how far (the mode is an icon and for a screen reader): the server's sentence
 * 「지하철 3호선 10분 · 1.1km」 repeated the line the mode chip had just said. The sentence is cut at the first 「n분」/「n시간」 and left whole when it has none.
 */
export function legText(summary: string): string {
  const found = /(\d+\s*시간\s*)?\d+\s*분.*$/.exec(summary);
  return found ? found[0].trim() : summary;
}

function MoveRow({ move, ctx, dim }: { move: PlanMove; ctx: RowContext; dim: boolean }) {
  const t = useT();
  const { done } = ctx;
  const open = done && ctx.open === move.id;
  const checking = move.verdict === null;
  // Only a leg that needs a look is marked: a fine one stays quiet, so the eye goes to the stops first.
  const mark = checking || move.verdict !== "review" ? null : <VerdictMark verdict={move.verdict} />;
  const line = checking ? null : <>
    <span className={styles.modeIcon}><ModeIcon mode={move.mode} /></span>
    <span className="sr-only">{move.mode}</span>
    <span className={styles.moveText}>{legText(move.summary)}</span>{mark}</>;
  return <li className={styles.entry} data-type="move" data-entry-id={move.id} data-verdict={move.verdict ?? "checking"} data-dim={dim || undefined}>
    <span className={styles.time}>{!checking && <><b>{move.departAt}</b><small>{t("출발", "leave")}</small></>}</span>
    <span className={styles.rail} aria-hidden="true"><span className={styles.dot} /></span>
    <div className={styles.move} data-open={open || undefined}>{checking
      ? <span className={styles.waiting}>{done ? t("이동 경로 다시 찾는 중…", "Finding the way again…") : t("이동 경로를 찾는 중…", "Finding the way…")}</span>
      : done
        ? <><button type="button" className={styles.moveHead} aria-expanded={open} aria-controls={`${ctx.prefix}plan-move-${move.id}-checks`} onClick={() => ctx.onToggleMove(move.id)}>{line}</button>
          {open && <Checks id={`${ctx.prefix}plan-move-${move.id}-checks`} rows={move.checks} />}</>
        : <div className={styles.moveHead}>{line}</div>}</div>
  </li>;
}

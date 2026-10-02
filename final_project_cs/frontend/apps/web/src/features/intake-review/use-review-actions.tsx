"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { IntakeEdit } from "@/lib/live/intake";
import { itemEdit } from "@/lib/live/intake-edits";
import { pickedPlace, type AutofixResult, type CandidatePlace, type Review, type ReviewItem, type ReviewMove, type ReviewedIntakeView } from "@/lib/live/intake-review";
import { useSettings, useT } from "@/lib/settings";
import { autofixUndo, restorePlace } from "./autofix-undo";
import { CardActions, LockControl, TrailControls } from "./card-controls";
import type { MoveRowProps } from "./move-row";
import type { PlaceRowProps } from "./place-card";
import { blockedReason, deleteQuestion, said, type ActionKind, type ToastText } from "./review-actions";
import { ConfirmDialog, ReviewToast, type ToastState } from "./review-overlays";
import { dayHeading } from "./review-model";
import { fetchCandidates } from "./use-candidates";

const UNDOABLE_MS = 4_500;
const PLAIN_MS = 2_800;

const restoreEdit = (item: ReviewItem) => restorePlace(item, item.place);

/**
 * What the customer can do to one stop of the finished check screen — lock it, delete it (after a question), switch it to the
 * top alternative — and the toast that follows with 「되돌리기」. Every change goes to the server (`send`) and the screen shows the
 * server's answer; while the server checks the changed stop and the legs around it again they show a spinner.
 *
 * ★The server's rules are not copied here: a button that cannot be used says why (`blockedReason`), and anything the server
 *   still refuses (a stale revision, a locked stop) comes back as its own message in the toast.
 */
export function useReviewActions({ intakeId, view, send, autofix, revalidate, outsideBusy, onEdit }: {
  intakeId: string;
  view: ReviewedIntakeView & { review: Review };
  /** Send edits and wait for the server's new plan (the screen shows it). Called with the latest revision. */
  send: (edits: IntakeEdit[]) => Promise<ReviewedIntakeView>;
  /** Ask the server to fix everything that needs it at once (`POST …/autofix`); the screen shows the plan it answers with. */
  autofix: () => Promise<AutofixResult>;
  /** Ask the server to check the same revision again from the start (`POST …/revalidate`); the screen shows its answer. */
  revalidate: () => Promise<ReviewedIntakeView>;
  /** Something else is on its way (registering, planning). */
  outsideBusy: boolean;
  onEdit?: (item: ReviewItem) => void;
}) {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const [running, setRunning] = useState<{ items: ReadonlySet<string>; moves: ReadonlySet<string> } | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [asking, setAsking] = useState<ReviewItem | null>(null);
  // Something was changed since the plan was last checked as a whole — 「여행 등록」 waits for a recheck (mockup 「다음 동작」).
  const [dirty, setDirty] = useState(false);
  const [rechecking, setRechecking] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const counter = useRef(0);
  const latest = useRef({ send, view, autofix, revalidate });
  useEffect(() => { latest.current = { send, view, autofix, revalidate }; });
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const busy = outsideBusy || running !== null || rechecking;
  const review = view.review;

  const hideToast = () => { if (timer.current) clearTimeout(timer.current); setToast(null); };
  function show(text: ToastText, undo?: () => void) {
    if (timer.current) clearTimeout(timer.current);
    counter.current += 1;
    setToast({ id: counter.current, ...text, undo });
    timer.current = setTimeout(() => setToast(null), undo ? UNDOABLE_MS : PLAIN_MS);
  }
  const nameOf = (item: ReviewItem) => item.place?.name ?? item.title;

  /** Run something that changes a stop: the stop and its legs show a spinner until the server answers; a refusal is said, not hidden. */
  async function guarded(items: readonly string[], work: () => Promise<void>) {
    const moves = review.moves.filter((move) => items.includes(move.from) || items.includes(move.to)).map((move) => `${move.from}:${move.to}`);
    setRunning({ items: new Set(items), moves: new Set(moves) });
    hideToast();
    try { await work(); }
    catch (error) { show({ message: error instanceof Error ? error.message : t("바꾸지 못했어요", "Could not change it") }); }
    finally { setRunning(null); }
  }

  /** Send the edits, then say what was done. `undo` (the edits that put it back) makes the toast carry 「되돌리기」. */
  async function commit(items: readonly string[], edits: IntakeEdit[], text: ToastText, undo?: IntakeEdit[], changes = true) {
    await latest.current.send(edits);
    if (changes) setDirty(true);                      // a lock changes nothing about the plan's check
    show(text, undo ? () => void guarded(items, () => commit(items, undo, said.undone(t))) : undefined);
  }

  const reasonFor = (action: ActionKind, item: ReviewItem) => blockedReason({ action, item, busy }, t);

  function toggleLock(item: ReviewItem) {
    const reason = reasonFor("lock", item);
    if (reason) { show({ message: reason }); return; }
    const on = !item.locked;
    void guarded([], () => commit([], [itemEdit.lock(item, on)], on ? said.locked(nameOf(item), t) : said.unlocked(nameOf(item), t), [itemEdit.lock(item, !on)], false));
  }

  function askDelete(item: ReviewItem) {
    const reason = reasonFor("delete", item);
    if (reason) { show({ message: reason }); return; }
    hideToast();
    setAsking(item);
  }

  function confirmDelete() {
    const item = asking;
    setAsking(null);
    if (!item) return;
    // The question may have been open a while: ask again with the plan as it is now.
    const now = latest.current.view.review.items.find((entry) => entry.id === item.id);
    const reason = now ? blockedReason({ action: "delete", item: now, busy }, t) : t("그 일정은 이미 없어요", "That stop is already gone");
    if (reason) { show({ message: reason }); return; }
    // The dialog's button is about to disappear — keep the focus in the list (a keyboard user would otherwise lose their place).
    requestAnimationFrame(() => document.querySelector<HTMLElement>("[data-review-list]")?.focus({ preventScroll: true }));
    void guarded([item.id], () => commit([item.id], [itemEdit.remove(item, true)], said.removed(nameOf(item), t), [itemEdit.remove(item, false)]));
  }

  function cancelDelete() {
    const item = asking;
    setAsking(null);
    // Focus goes back to the button that asked, so a keyboard user does not start over from the top.
    if (item) requestAnimationFrame(() => document.querySelector<HTMLElement>(`[data-act="delete"][data-item="${CSS.escape(item.id)}"]`)?.focus({ preventScroll: true }));
  }

  function autoFix(item: ReviewItem) {
    const reason = reasonFor("auto", item);
    if (reason) { show({ message: reason }); return; }
    void guarded([item.id], async () => {
      const list = await fetchCandidates(queryClient, intakeId, item, latest.current.view.revision, language);
      const choice = list.candidates.map((candidate) => ({ candidate, picked: pickedPlace(candidate.place) })).find((entry) => entry.picked);
      if (!choice?.picked) { show(said.noAlternative(t)); return; }
      const back = restoreEdit(item);
      await commit([item.id], [itemEdit.placePicked(item, choice.picked)], said.changedPlace(nameOf(item), choice.candidate.place.name, "auto", t), back ? [back] : undefined);
    });
  }

  /** 「전체 자동 추천」 — the server fixes every stop that needs it (a place that fits, a time that gets there) in one new revision. */
  function autoAll() {
    const reason = blockedReason({ action: "autoAll", busy, needs: review.needs.total }, t);
    if (reason) { show({ message: reason }); return; }
    const before = review.needs.total;
    const everything = review.items.map((item) => item.id);
    void guarded(everything, async () => {
      const result = await latest.current.autofix();
      if (!result.applied) { show(said.autofixNothing(result.kept, t)); return; }
      setDirty(true);
      const after = result.view.review?.needs.total ?? 0;
      const undo = autofixUndo(result.changed);                       // null when it cannot put everything back — then no 「되돌리기」
      show(said.autofixed(result.changed, Math.max(1, before - after), result.kept.filter((entry) => entry.reason === "locked" || entry.reason.startsWith("no_")).length, t),
        undo ? () => void guarded(everything, () => commit(everything, undo, said.undone(t))) : undefined);
    });
  }

  /** 「재검증」 — check the plan again from the start, then 「여행 등록」 can follow. */
  function recheck() {
    const reason = blockedReason({ action: "register", busy, needs: review.needs.total }, t);
    if (reason) { show({ message: reason }); return; }
    setRechecking(true);
    hideToast();
    void latest.current.revalidate()
      .then((next) => { setDirty(false); show(said.revalidated(next.review?.ready ?? false, next.review?.needs.total ?? 0, t)); })
      .catch((error: unknown) => show({ message: error instanceof Error ? error.message : t("다시 확인하지 못했어요", "Could not check again") }))
      .finally(() => setRechecking(false));
  }

  /** A place from the edit screen (an alternative, or one picked from the search). */
  function changePlace(item: ReviewItem, place: CandidatePlace, how: "pick" | "search") {
    const reason = reasonFor("edit", item);
    if (reason) { show({ message: reason }); return; }
    const picked = pickedPlace(place);
    if (!picked) { show({ message: t("위치 정보가 없어 고를 수 없어요", "It has no coordinates, so it cannot be picked") }); return; }
    const back = restoreEdit(item);
    void guarded([item.id], () => commit([item.id], [itemEdit.placePicked(item, picked)], said.changedPlace(nameOf(item), place.name, how, t), back ? [back] : undefined));
  }

  /** The day, start and end the customer typed on the edit screen — only what differs is sent; an undo puts the old values back. */
  function saveTimes(item: ReviewItem, times: { date: string; starts: string; ends: string }) {
    const reason = reasonFor("edit", item);
    if (reason) { show({ message: reason }); return; }
    const edits: IntakeEdit[] = [], undo: IntakeEdit[] = [];
    if (times.date && times.date !== (item.date ?? "")) { edits.push(itemEdit.date(item, times.date)); if (item.date) undo.push(itemEdit.date(item, item.date)); }
    if (times.starts && times.starts !== (item.starts_at ?? "")) { edits.push(itemEdit.starts(item, times.starts)); if (item.starts_at) undo.push(itemEdit.starts(item, item.starts_at)); }
    if (times.ends && times.ends !== (item.ends_at ?? "")) { edits.push(itemEdit.ends(item, times.ends)); if (item.ends_at) undo.push(itemEdit.ends(item, item.ends_at)); }
    if (!edits.length) return;
    void guarded([item.id], () => commit([item.id], edits, said.timesChanged(nameOf(item), t), undo.length === edits.length ? undo : undefined));
  }

  const rowProps = (item: ReviewItem): Partial<PlaceRowProps> => {
    const lockReason = reasonFor("lock", item);
    const otherReason = reasonFor("edit", item);
    const blocked = (reason: string | null) => () => show({ message: reason ?? t("지금은 쓸 수 없어요", "Not available now") });
    return {
      checking: rechecking || (running?.items.has(item.id) ?? false),
      lead: <LockControl item={item} unavailable={Boolean(lockReason)} onToggle={() => toggleLock(item)} onBlocked={blocked(lockReason)} />,
      trail: <TrailControls item={item} unavailable={Boolean(reasonFor("delete", item))} onEdit={onEdit && (() => onEdit(item))} onDelete={() => askDelete(item)} onBlocked={blocked(reasonFor("delete", item))} />,
      actions: (open) => <CardActions intakeId={intakeId} revision={view.revision} item={item} open={open} unavailable={Boolean(otherReason)} lockedNote={item.locked ? otherReason : null}
        onAuto={() => autoFix(item)} onEdit={onEdit && (() => onEdit(item))} onBlocked={blocked(otherReason)} />,
    };
  };

  const moveProps = (move: ReviewMove): Partial<MoveRowProps> => ({ checking: rechecking || (running?.moves.has(`${move.from}:${move.to}`) ?? false) });

  const heading = asking ? dayHeading(asking.day, asking.date, t) : null;
  const when = asking ? [heading?.title, asking.starts_at && asking.ends_at ? `${asking.starts_at}–${asking.ends_at}` : asking.starts_at].filter(Boolean).join(" ") : "";
  const question = asking ? deleteQuestion(nameOf(asking), when, t) : null;
  const overlay: ReactNode = <>
    <ReviewToast toast={toast} onUndo={() => { const undo = toast?.undo; if (undo) { hideToast(); undo(); } }} />
    {question && <ConfirmDialog title={question.title} detail={question.detail} confirmLabel={t("삭제", "Delete")} cancelLabel={t("취소", "Cancel")} onConfirm={confirmDelete} onCancel={cancelDelete} />}
  </>;

  return { rowProps, moveProps, overlay, busy, show, changePlace, saveTimes, autoAll, recheck, dirty, rechecking, modal: asking !== null };
}

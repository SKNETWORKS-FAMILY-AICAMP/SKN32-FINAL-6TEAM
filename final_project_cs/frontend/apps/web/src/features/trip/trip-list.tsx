"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { ArrowRight, ChevronRight, Plus, Trash2 } from "lucide-react";
import { Badge, Button, ButtonLink, PageHeading, Panel, QueryState } from "@/components/ui";
import { DATA_MODE } from "@/lib/gateway";
import type { Translate } from "@/lib/i18n";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import type { TripSummary } from "./model";
import { useDeleteTrips, useTrips } from "./use-trip";
import styles from "./trip-list.module.css";

const icon = { size: 18, strokeWidth: 1.6, "aria-hidden": true } as const;
/** How many recent trips the home card shows; more than this adds the link to the full list. */
const RECENT = 3;
/**
 * The delete dialog stays (showing `삭제 중…`) at least this long after Delete is pressed. A demo delete ends in a few
 * milliseconds, and the second click of a double press would otherwise land on the list beneath and open a trip.
 * Windows' default double-click time.
 */
const MIN_DELETING_MS = 500;

/** Registration time in Seoul, like every time on the trip screens. Null for a demo trip saved before it was kept. */
function useAdded() {
  const { language } = useSettings();
  const format = new Intl.DateTimeFormat(language === "ko" ? "ko-KR" : "en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Seoul" });
  return (trip: TripSummary) => trip.createdAt ? format.format(new Date(trip.createdAt)) : null;
}

/** The full list's delete controls. The home card passes none, so its rows stay plain links. */
interface RowControls {
  /** Select mode: each row is a checkbox and opens nothing. Null in the normal list. */
  selection: ReadonlySet<string> | null;
  onToggle: (id: string) => void;
  onDelete: (trip: TripSummary, control: HTMLButtonElement) => void;
  /** Deleting is not offered here (live); the page says why. */
  unsupported: boolean;
  /** A delete is running: nothing can be picked or asked again. */
  busy: boolean;
}

/**
 * Trip rows: title and registration time (never shown as the trip's dates). A row opens the trip, which points to the
 * check or results until the trip starts. The delete button sits beside the link, never inside it.
 */
function TripRows({ trips, compact = false, controls }: { trips: TripSummary[]; compact?: boolean; controls?: RowControls }) {
  const t = useT();
  const added = useAdded();
  const text = (trip: TripSummary, time: string | null) => <span className={styles.text}>
    <strong>{trip.title}</strong>
    {time && <small>{t(`${time} 등록`, `Added ${time}`)}</small>}
  </span>;
  const badge = (trip: TripSummary) => trip.version !== null && trip.version > 1 && <Badge>{t("바뀐 일정 있음", "Updated")}</Badge>;
  return <ul className={`${styles.list} ${compact ? styles.compact : ""}`}>{trips.map((trip) => {
    const time = added(trip);
    if (controls?.selection) {
      const checked = controls.selection.has(trip.id);
      return <li key={trip.id} className={`${styles.item} ${checked ? styles.checked : ""}`}>
        <label className={styles.row}>
          <input type="checkbox" className={styles.check} checked={checked} disabled={controls.busy} onChange={() => controls.onToggle(trip.id)} />
          {text(trip, time)}{badge(trip)}
        </label>
      </li>;
    }
    const link = <Link href={routes.trip(trip.id)} className={styles.row}>{text(trip, time)}{badge(trip)}<ChevronRight {...icon} /></Link>;
    if (!controls) return <li key={trip.id}>{link}</li>;
    return <li key={trip.id} className={styles.item}>
      {link}
      {/* The trip's time goes in the name too: two trips may share a title, and the ID decides what is deleted. */}
      <button type="button" className={styles.delete} disabled={controls.unsupported || controls.busy} onClick={(event) => controls.onDelete(trip, event.currentTarget)}
        aria-label={time ? t(`${trip.title}(${time} 등록) 삭제`, `Delete ${trip.title} (added ${time})`) : t(`${trip.title} 삭제`, `Delete ${trip.title}`)}>
        <Trash2 {...icon} />
      </button>
    </li>;
  })}</ul>;
}

/** Confirm before anything is deleted. Focus starts on Cancel and stays inside; Escape cancels; the backdrop does nothing. */
function DeleteDialog({ t, title, body, confirm, pending, onCancel, onConfirm }: {
  t: Translate; title: string; body: ReactNode; confirm: string; pending: boolean; onCancel: () => void; onConfirm: () => void;
}) {
  const cancel = useRef<HTMLButtonElement>(null);
  const remove = useRef<HTMLButtonElement>(null);
  useEffect(() => { cancel.current?.focus(); }, []);

  function keys(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") { event.preventDefault(); if (!pending) onCancel(); return; }
    if (event.key !== "Tab") return;
    if (event.shiftKey && document.activeElement === cancel.current) { event.preventDefault(); remove.current?.focus(); }
    else if (!event.shiftKey && document.activeElement === remove.current) { event.preventDefault(); cancel.current?.focus(); }
  }

  // While deleting, both buttons stay focusable (aria-disabled) so focus does not drop out of the dialog.
  return createPortal(<div className={styles.overlay}>
    <div className={styles.dialog} role="alertdialog" aria-modal="true" aria-labelledby="delete-title" aria-describedby="delete-body" onKeyDown={keys}>
      <h2 id="delete-title">{title}</h2>
      <div id="delete-body" className={styles.dialogBody}>{body}</div>
      <div className={styles.dialogActions}>
        <Button ref={cancel} aria-disabled={pending || undefined} onClick={() => { if (!pending) onCancel(); }}>{t("취소", "Cancel")}</Button>
        <Button ref={remove} variant="danger" aria-disabled={pending || undefined} onClick={() => { if (!pending) onConfirm(); }}>{pending ? t("삭제 중…", "Deleting…") : confirm}</Button>
      </div>
    </div>
  </div>, document.body);
}

/**
 * "My trips" — this browser's trips, newest first. Each row can be deleted, or `선택 삭제` turns the rows into
 * checkboxes. Deleting always asks first; what the list shows afterwards is the data layer's result.
 */
export function TripList() {
  const t = useT();
  const query = useTrips();
  const deleteTrips = useDeleteTrips();
  const added = useAdded();
  const [selection, setSelection] = useState<ReadonlySet<string> | null>(null);
  const [asking, setAsking] = useState<{ ids: string[]; single: TripSummary | null; from: HTMLElement | null } | null>(null);
  const [pending, setPending] = useState(false);
  const running = useRef(false);
  const [notice, setNotice] = useState<{ text: string; failed: boolean } | null>(null);
  const selectButton = useRef<HTMLButtonElement>(null);
  const cancelSelect = useRef<HTMLButtonElement>(null);
  const newTrip = useRef<HTMLAnchorElement>(null);
  /**
   * Where focus goes after the next render: a control that is still there, select mode's `취소`, or "rest" —
   * `선택 삭제`, else `새 여행 등록` once the list is empty.
   */
  const focusNext = useRef<HTMLElement | "cancel" | "rest" | null>(null);
  useEffect(() => {
    const target = focusNext.current;
    if (!target) return;
    focusNext.current = null;
    (target === "rest" ? selectButton.current ?? newTrip.current : target === "cancel" ? cancelSelect.current : target)?.focus();
  });

  if (query.isPending || query.error || !query.data) {
    return <QueryState loading={query.isPending} error={query.error} retry={() => void query.refetch()} />;
  }
  const trips = query.data;
  const chosen = selection ? trips.filter((trip) => selection.has(trip.id)) : [];

  function startSelecting() {
    setNotice(null);
    setSelection(new Set());
    focusNext.current = "cancel";
  }

  function stopSelecting() {
    setSelection(null);
    focusNext.current = "rest";
  }

  function toggle(id: string) {
    setSelection((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function ask(ids: string[], single: TripSummary | null, from: HTMLElement | null) {
    setNotice(null);
    setAsking({ ids, single, from });
  }

  /** Cancelling the dialog keeps select mode and the ticks; only the top `취소` leaves select mode. */
  function cancelAsk() {
    focusNext.current = asking?.from ?? "rest";
    setAsking(null);
  }

  async function confirmDelete() {
    if (!asking || !deleteTrips || running.current) return;
    running.current = true;
    setPending(true);
    const pressed = performance.now();
    const { deleted, failed } = await deleteTrips(asking.ids);
    const rest = MIN_DELETING_MS - (performance.now() - pressed);
    if (rest > 0) await new Promise((resolve) => setTimeout(resolve, rest));
    running.current = false;
    setPending(false);
    setAsking(null);
    if (failed.length === 0) {
      setNotice({ text: t(`여행 ${deleted.length}개를 삭제했어요.`, deleted.length === 1 ? "Deleted 1 trip." : `Deleted ${deleted.length} trips.`), failed: false });
      setSelection(null);
      focusNext.current = "rest";
      return;
    }
    // What failed stays — in select mode, still ticked — so it can be tried again.
    setNotice({
      text: deleted.length
        ? t(`${deleted.length}개 삭제, ${failed.length}개 삭제 실패. 다시 시도해 주세요.`, `Deleted ${deleted.length}; ${failed.length} could not be deleted. Please try again.`)
        : t("삭제하지 못했어요. 다시 시도해 주세요.", "Couldn’t delete. Please try again."),
      failed: true,
    });
    if (selection) setSelection(new Set(failed));
    focusNext.current = asking.from;
  }

  const unsupported = deleteTrips === null;
  const scope = t("이 탭에 저장된 여행과 대화 기록이 삭제돼요. 삭제한 내용은 되돌릴 수 없어요.", "The trip and its chat saved in this tab will be deleted. This can’t be undone.");
  const action = trips.length === 0 ? undefined
    : selection ? <div className={styles.selectActions}>
      <Button ref={cancelSelect} variant="quiet" disabled={pending} onClick={stopSelecting}>{t("취소", "Cancel")}</Button>
      <Button variant="danger" disabled={chosen.length === 0 || pending} onClick={(event) => ask(chosen.map((trip) => trip.id), null, event.currentTarget)}>{t(`삭제 (${chosen.length})`, `Delete (${chosen.length})`)}</Button>
    </div>
    : <Button ref={selectButton} variant="quiet" disabled={unsupported} onClick={startSelecting}>{t("선택 삭제", "Select to delete")}</Button>;
  const single = asking?.single, singleTime = single ? added(single) : null, count = asking?.ids.length ?? 0;

  return <>
    <PageHeading eyebrow="MY TRIPS" title={t("내 여행", "My trips")} action={action}
      description={DATA_MODE === "demo" ? t("이 탭에서 등록한 여행이에요. 최근에 등록한 여행이 위에 있어요.", "Trips added in this tab, newest first.") : t("이 브라우저에서 등록한 여행이에요. 최근에 등록한 여행이 위에 있어요.", "Trips added in this browser, newest first.")} />
    {unsupported && trips.length > 0 && <p className={styles.unsupported}>{t("실제 연결에서 여행 삭제는 아직 지원하지 않아요.", "Deleting trips isn’t available with the live connection yet.")}</p>}
    <p className={styles.notice} role="status">{notice && !notice.failed ? notice.text : ""}</p>
    <p className={`${styles.notice} ${styles.noticeFailed}`} role="alert">{notice?.failed ? notice.text : ""}</p>
    {trips.length === 0
      ? <Panel className={styles.empty}><p>{t("아직 등록한 여행이 없어요.", "No trips yet.")}</p></Panel>
      : <TripRows trips={trips} controls={{ selection, onToggle: toggle, onDelete: (trip, control) => ask([trip.id], trip, control), unsupported, busy: pending }} />}
    {/* Hidden while picking, so select mode is only about picking and deleting. */}
    {!selection && <div className={styles.actions}><ButtonLink ref={newTrip} href={routes.newTrip} variant="primary"><Plus {...icon} />{t("새 여행 등록", "Add a trip")}</ButtonLink></div>}
    {asking && <DeleteDialog t={t} pending={pending} onCancel={cancelAsk} onConfirm={() => void confirmDelete()}
      title={single ? t("이 여행을 삭제할까요?", "Delete this trip?") : t(`선택한 여행 ${count}개를 삭제할까요?`, count === 1 ? "Delete 1 selected trip?" : `Delete ${count} selected trips?`)}
      confirm={single ? t("삭제", "Delete") : t(`${count}개 삭제`, `Delete ${count}`)}
      body={<>
        {single
          ? <p className={styles.target}><strong>{single.title}</strong>{singleTime && <small>{t(`${singleTime} 등록`, `Added ${singleTime}`)}</small>}</p>
          : <p className={styles.target}><strong>{t(`선택한 여행 ${count}개`, count === 1 ? "1 selected trip" : `${count} selected trips`)}</strong></p>}
        <p>{scope}</p>
      </>} />}
  </>;
}

/** Home card: the most recent trips from the same list. Loading, no trips and a failed read stay inside the card. */
export function RecentTrips() {
  const t = useT();
  const query = useTrips();
  const trips = query.data ?? [];
  return <section className={styles.recent} aria-labelledby="recent-trips-title">
    <header className={styles.recentHead}>
      <h2 id="recent-trips-title">{t("내 여행", "My trips")}</h2>
      {trips.length > RECENT && <Link href={routes.trips} className={styles.all}>{t("전체일정 보기", "View all")}<ArrowRight size={14} strokeWidth={1.8} aria-hidden="true" /></Link>}
    </header>
    {query.isPending ? <p className={styles.state} role="status">{t("여행을 불러오고 있어요.", "Loading your trips.")}</p>
      : query.error ? <div className={styles.failed} role="alert">
        <p>{query.error.message}</p>
        <Button onClick={() => void query.refetch()} disabled={query.isFetching}>{t("다시 불러오기", "Try again")}</Button>
      </div>
      : trips.length === 0 ? <p className={styles.state}>{t("아직 등록한 여행이 없어요.", "No trips yet.")}</p>
      : <TripRows trips={trips.slice(0, RECENT)} compact />}
  </section>;
}

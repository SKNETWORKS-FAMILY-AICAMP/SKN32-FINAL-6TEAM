"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowLeft, Lock, LockOpen, Pencil, Search, Sparkles, Trash2, X } from "lucide-react";
import { DeviceFrame } from "@/components/layout/device-frame";
import { TripMap } from "@/features/map";
import type { PinLook } from "@/features/map/model";
import type { TripStop } from "@/features/trip/model";
import type { Language, Translate } from "@/lib/i18n";
import { eul, ro } from "@/lib/josa";
import { useSettings, useT } from "@/lib/settings";
import { foundCount, needs, progress, STAGES, tally, timeline, type ItemDraft, type LineFinding, type PlanCandidate, type PlanCheckView, type PlanItem, type PlanMove, type TripIssue } from "./model";
import { Act, Checks, letter, reason, Status, VerdictMark, VerdictPill } from "./parts";
import { PlaceChange, type ChangeSession, type SearchState } from "./place-change";
import { DeleteDialog, ResultFooter, StopEditor, TripIssues, type Registration } from "./result-parts";
import { useReveal } from "./use-reveal";
import styles from "./plan-check.module.css";

export interface PlanCheckProps {
  /** The latest snapshot. The screen paces the changes between snapshots itself (`useReveal`). */
  view: PlanCheckView;
  /** The back arrow — e.g. back to the plan entry. */
  onBack: () => void;
  /** Called once the screen has drawn everything in `view` and held it a moment — e.g. to move on after the last line. */
  onCaughtUp?: () => void;
  /** Shown above the screen's content — e.g. the new-key notice of a first visit. */
  notice?: ReactNode;
  /** What the result can change, each wired by the page. One left out stays on the screen and says it is coming. */
  actions?: PlanCheckActions;
  /** Registering the result, at the bottom of the list once the check is done. */
  registration?: Registration;
  /** Trip-wide details the server asks for before it can register. */
  tripIssues?: TripIssue[];
  /** Opens the previous review screen — kept for what this screen does not do yet. */
  onOpenPrevious?: () => void;
}

/** A place for one stop: an alternative or a search result, or just a name the server looks up. */
export type PlaceChoice = { candidate: PlanCandidate } | { name: string };

/** What 「전체 자동 추천」 did: one line per stop changed (「올리브영 → 올리브영 광화문점 11:00–12:00」), how many stayed. */
export interface AutoResult { changes: string[]; kept: number }

/**
 * The result's changes — the seams the backend connects (PLAN_CHECK_SCREEN.md §4). Each resolves once the plan is the
 * new one (the page passes the new `view`), or rejects with the server's sentence. One left out is shown but says it is
 * coming, so the screen is whole either way.
 */
export interface PlanCheckActions {
  /** Save one stop's details as drafted (the server looks a typed place up again and checks the plan again). */
  edit?: (id: string, draft: ItemDraft) => Promise<void>;
  /** Take one stop out. */
  remove?: (id: string) => Promise<void>;
  /** Answer a trip-wide detail. */
  editTrip?: (field: "first_day" | "party_size", value: string | number) => Promise<void>;
  /** The alternatives for one stop, best first (mockup 「대체 후보 A · B · C」). */
  candidates?: (id: string) => Promise<PlanCandidate[]>;
  /** Places matching words, nearest first (the change screen's search bar). */
  search?: (id: string, query: string) => Promise<PlanCandidate[]>;
  /** Put a place in one stop: a candidate or search result, or a name the server looks up. */
  replace?: (id: string, choice: PlaceChoice) => Promise<void>;
  /** The first alternative, in one press (the card's 「자동 추천」). */
  autoRecommend?: (id: string) => Promise<void>;
  /** Every stop that needs a look, changed to an alternative that fits (「전체 자동 추천」). */
  autoRecommendAll?: () => Promise<AutoResult>;
  /** Fix a stop so re-planning and recommendations keep it (「잠금」 — 「반드시 포함」). */
  lock?: (id: string, locked: boolean) => Promise<void>;
  /** Put back what the last change, delete or recommendation changed (「되돌리기」). */
  undo?: () => Promise<void>;
  /** Check the whole plan again without changing it (「재검증」); the view says which stop it is at (`rechecking`). */
  recheck?: () => Promise<void>;
}

/** How long the screen stays on what it has drawn before `onCaughtUp` — so the last line read is seen, not skipped. */
const HOLD_MS = 800;

/**
 * The plan check after 「계획 확인하기」, as the mockup `mockups/tripilot-plan-check-streaming.html` draws it: the uploaded
 * lines being read, then the places, hours and moves being checked on a map with a sheet over it, then the result —
 * cards and pins worked together, each stop locked, recommended, changed or deleted, 「전체 자동 추천 → 재검증 → 여행 등록」.
 * A phone-sized page of its own, like the start screen.
 */
export function PlanCheck({ view: latest, onBack, onCaughtUp, notice, ...result }: PlanCheckProps) {
  const { view, settled } = useReveal(latest);
  const t = useT();
  useEffect(() => {
    if (!settled || !onCaughtUp) return;
    const timer = setTimeout(onCaughtUp, HOLD_MS);
    return () => clearTimeout(timer);
  }, [settled, onCaughtUp]);
  return <DeviceFrame>
    <div className={styles.screen} data-stage={view.stage}>
      {notice}
      {view.stage === "received" || view.stage === "reading" ? <Reading view={view} onBack={onBack} /> : <Checking view={view} onBack={onBack} {...result} />}
      <p className="sr-only" role="status">{announce(view, t)}</p>
    </div>
  </DeviceFrame>;
}

function BackButton({ onBack, label }: { onBack: () => void; label?: string }) {
  const t = useT();
  return <button type="button" className={styles.back} onClick={onBack} aria-label={label ?? t("뒤로", "Back")}><ArrowLeft size={20} strokeWidth={1.6} aria-hidden="true" /></button>;
}

const stepLabels = (t: Translate) => [t("받았어요", "Received"), t("일정 읽기", "Reading"), t("장소·운영시간", "Places & hours"), t("정리 완료", "Done")];

/** One straight line with four points; the filled part follows the lines read, then the places and moves checked. */
function ProgressBar({ view, small = false }: { view: PlanCheckView; small?: boolean }) {
  const t = useT();
  const labels = stepLabels(t);
  const current = STAGES.indexOf(view.stage);
  const value = Math.round(progress(view));
  return <div className={styles.progress} data-size={small ? "small" : "large"} role="progressbar" aria-label={t("계획 확인 진행", "Plan check progress")}
    aria-valuemin={0} aria-valuemax={100} aria-valuenow={value} aria-valuetext={`${labels[current]} · ${value}%`}>
    <div className={styles.track}><span className={styles.fill} style={{ width: `${value}%` }} /></div>
    <ol className={styles.steps}>{labels.map((label, index) =>
      <li key={label} data-state={view.stage === "done" || index < current ? "done" : index === current ? "current" : "waiting"}>
        <span className={styles.node} aria-hidden="true" /><span className={styles.stepLabel}>{label}</span>
      </li>)}</ol>
  </div>;
}

/** ①② The uploaded plan, read line by line. */
function Reading({ view, onBack }: { view: PlanCheckView; onBack: () => void }) {
  const t = useT();
  const { language } = useSettings();
  const current = view.stage === "reading" ? view.lines.findIndex((line) => !line.read) : -1;
  return <div className={styles.reading}>
    <header className={styles.head}>
      <div className={styles.headRow}><BackButton onBack={onBack} /><h1 className={styles.title}>{t("계획을 확인하고 있어요", "Checking your plan")}</h1></div>
      <p className={styles.desc}>{t("사진 한 장은 1분쯤 걸려요. 이 화면을 열어 두면 끝나는 대로 보여 드려요.", "A photo takes about a minute. Keep this page open and the result will appear.")}</p>
      <ProgressBar view={view} />
    </header>
    <h2 className={styles.docLabel}>{t("올린 계획", "Your plan")}</h2>
    <ol className={styles.doc}>{view.lines.map((line, index) => {
      const state = line.read ? "read" : index === current ? "current" : "waiting";
      return <li key={line.no} className={styles.line} data-state={state}>
        <span className={styles.lineMark} aria-hidden="true">{line.read ? "✓" : ""}</span>
        <span className={styles.lineBody}>
          <span className={styles.lineText}>{line.text}</span>
          {line.read && line.found && <span className={styles.lineFound}>→ {findingLabel(line.found, language, t)}</span>}
          <span className="sr-only">{state === "read" ? t("읽음", "read") : state === "current" ? t("읽는 중", "reading") : t("기다리는 중", "waiting")}</span>
        </span>
      </li>;
    })}</ol>
    <p className={styles.found}>{t("찾은 일정", "Stops found")} <b>{foundCount(view)}</b>{t("개", "")}</p>
  </div>;
}

/** How high the sheet stands over the map: a strip, half the screen, or (nearly) all of it — the handle cycles them. */
const SHEETS = ["half", "full", "peek"] as const;
type Sheet = (typeof SHEETS)[number];

interface Toast { text: string; sub?: string; undo?: boolean }

type ResultProps = Pick<PlanCheckProps, "actions" | "registration" | "tripIssues" | "onOpenPrevious">;

/** ③④⑤ The map under a floating bar, the sheet over it. Once done, the list and the map are worked together. */
function Checking({ view, onBack, actions = {}, registration, tripIssues = [], onOpenPrevious }: { view: PlanCheckView; onBack: () => void } & ResultProps) {
  const t = useT();
  const { language } = useSettings();
  const done = view.stage === "done";
  // What the customer picked once the check is done: one card or move open, one place selected, one day on the map.
  const [open, setOpen] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [chosenDay, setChosenDay] = useState<number | null>(null);
  const [sheet, setSheet] = useState<Sheet>("half");
  // ⑤ The stop being changed (the change screen takes the sheet), the search in the top bar, ⑥ the stop asked about deleting.
  const [change, setChange] = useState<ChangeSession | null>(null);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<SearchState | null>(null);
  const [details, setDetails] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const [working, setWorking] = useState(false);
  const searchInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), toast.undo ? 4500 : 2800);
    return () => clearTimeout(timer);
  }, [toast]);

  const registered = Boolean(registration?.registeredHref);
  // Nothing can be changed while a stop or the whole plan is checked again, or once registered — buttons say why.
  const frozen = registered ? t("이미 등록한 여행이에요", "This trip is already registered")
    : view.rechecking ? t("재검증하는 중이에요 · 잠시만요", "Checking again · one moment")
      : working || view.items.some((item) => item.verdict === null) ? t("바뀐 일정을 다시 확인하는 중이에요 · 잠시만요", "Checking the change · one moment") : null;
  const explain = (why: string) => setToast({ text: why });
  const changing = change ? view.items.find((item) => item.id === change.id) ?? null : null;
  const deletingItem = view.items.find((item) => item.id === deleting) ?? null;
  /** Back to the card's own button after the change screen or the dialog closes. */
  const refocus = (id: string, which: "edit" | "delete") => requestAnimationFrame(() => document.getElementById(`plan-${which}-${id}`)?.focus());

  const firstDay = view.days[0]?.day ?? 1;
  // While checking, the map follows the day being checked; once done it shows the day picked (the first by default).
  const mapDay = changing ? changing.day : done ? chosenDay ?? firstDay : view.items.at(-1)?.day ?? firstDay;
  const days = view.days.filter((day) => view.items.some((item) => item.day === day.day));
  // Places the server could not settle have no pin; say so on the map, as the mockup's 「위치 미정」 tag does.
  const unlocated = changing ? [] : view.items.filter((item) => item.day === mapDay && item.verdict !== null && !item.coordinates);

  // Search as the words change (a moment after typing stops). No search on this server: say so, keep 「change by name」.
  useEffect(() => {
    const words = query.trim();
    if (!change || !words) { setSearch(null); return; }
    if (!actions.search) { setSearch({ query: words, list: [], state: "unsupported" }); return; }
    setSearch({ query: words, list: [], state: "loading" });
    let live = true;
    const timer = setTimeout(() => {
      actions.search!(change.id, words).then((list) => { if (live) setSearch({ query: words, list, state: "ready" }); })
        .catch((error: unknown) => { if (live) setSearch({ query: words, list: [], state: "failed", message: reason(error) }); });
    }, 250);
    return () => { live = false; clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- a new search only when the words or the stop change
  }, [query, change?.id]);

  /** A place picked on the map or in the list: selected, its day on the map; from the list it opens or closes, from the map it opens and comes into view. */
  function pick(id: string, from: "map" | "list") {
    const item = view.items.find((entry) => entry.id === id);
    if (!item) return;
    setSelected(id);
    setChosenDay(item.day);
    if (from === "list") setOpen((current) => current === id ? null : id);
    else {
      setOpen(id);
      if (sheet === "peek") setSheet("half");
      requestAnimationFrame(() => document.getElementById(`plan-card-${id}`)?.scrollIntoView({ block: "nearest" }));
    }
  }
  function showDay(day: number) {
    setChosenDay(day);
    if (view.items.find((item) => item.id === selected)?.day !== day) setSelected(null);
  }

  /** ⑤ Open the change screen for one stop: the map shows it and its alternatives, the top bar becomes a search. */
  async function startChange(item: PlanItem) {
    setOpen(item.id); setSelected(item.id); setChosenDay(item.day);
    if (sheet === "peek") setSheet("half");
    setQuery(""); setDetails(false);
    setChange({ id: item.id, list: [], index: 0, state: actions.candidates ? "loading" : "ready" });
    requestAnimationFrame(() => document.getElementById("plan-change-title")?.focus({ preventScroll: true }));
    if (!actions.candidates) return;
    try {
      const list = await actions.candidates(item.id);
      setChange((current) => current?.id === item.id ? { ...current, list, state: "ready" } : current);
    } catch (error) {
      setChange((current) => current?.id === item.id ? { ...current, state: "failed", message: reason(error) } : current);
    }
  }
  function endChange() {
    const id = change?.id;
    setChange(null); setQuery(""); setSearch(null); setDetails(false);
    if (id) refocus(id, "edit");
  }

  /** Run one change; a refusal is said in the server's words, and nothing else moves. */
  async function run(step: () => Promise<Toast | null>) {
    setWorking(true);
    try { const said = await step(); if (said) setToast(said); }
    catch (error) { setToast({ text: reason(error) }); }
    finally { setWorking(false); }
  }
  const undoable = Boolean(actions.undo);

  function replace(item: PlanItem, choice: PlaceChoice) {
    const name = "candidate" in choice ? choice.candidate.name : choice.name;
    void run(async () => {
      await actions.replace!(item.id, choice);
      setChange(null); setQuery(""); setSearch(null); setDetails(false);
      setOpen(item.id); refocus(item.id, "edit");
      return { text: t(`${eul(item.title)} ${ro(name)} 바꿨어요`, `Changed ${item.title} to ${name}`),
        sub: t("바뀐 장소와 앞뒤 이동을 다시 확인해요", "Checking the new place and the moves either side"), undo: undoable };
    });
  }
  function recommend(item: PlanItem) {
    void run(async () => {
      await actions.autoRecommend!(item.id);
      setOpen(item.id);
      return { text: item.suggestion ? t(`${eul(item.title)} ${ro(item.suggestion)} 바꿨어요`, `Changed ${item.title} to ${item.suggestion}`) : t("대체 후보 1순위로 바꿨어요", "Changed to the first alternative"),
        sub: t("대체 후보 1순위 · 바뀐 장소와 앞뒤 이동을 다시 확인해요", "First alternative · checking the new place and the moves either side"), undo: undoable };
    });
  }
  function lock(item: PlanItem) {
    const on = !item.locked;
    void run(async () => {
      await actions.lock!(item.id, on);
      return on ? { text: t(`${eul(item.title)} 꼭 넣을 일정으로 고정했어요`, `Locked ${item.title} in`), sub: t("다시 짜거나 바꿔도 빠지지 않게 서버에 알렸어요", "Re-planning and recommendations keep it") }
        : { text: t(`${item.title} 고정을 풀었어요`, `Unlocked ${item.title}`), sub: t("이제 바꾸거나 삭제할 수 있어요", "It can be changed or deleted now") };
    });
  }
  function recommendAll() {
    void run(async () => {
      const outcome = await actions.autoRecommendAll!();
      if (!outcome.changes.length) return { text: t("바꿀 수 있는 대체 일정이 없어요", "No alternative fits"), sub: outcome.kept ? t("고정한 일정이거나 시간이 맞는 후보가 없어요", "Locked, or no alternative fits the time") : undefined };
      return { text: t(`확인이 필요한 일정 ${outcome.changes.length}곳을 검증된 대체 일정으로 바꿨어요`, `Changed ${outcome.changes.length} stop${outcome.changes.length > 1 ? "s" : ""} to checked alternatives`),
        sub: outcome.changes.join(" · ") + (outcome.kept ? t(` · ${outcome.kept}곳은 그대로`, ` · ${outcome.kept} kept`) : ""), undo: undoable };
    });
  }
  function recheck() {
    void run(async () => {
      await actions.recheck!();
      return { text: t("재검증을 통과했어요", "The check passed"), sub: t("이대로 진행할 수 있어요 · 오른쪽 버튼이 「여행 등록」으로 바뀌었어요", "You can go ahead · the right button is now 「Register trip」") };
    });
  }
  function undo() {
    setToast(null);
    void run(async () => { await actions.undo!(); return { text: t("되돌렸어요", "Undone"), sub: t("바꾸기 전으로 돌렸어요", "Back to how it was") }; });
  }

  // The change screen's map: the day's other stops greyed, the stop being changed, and its alternatives A, B, C.
  const cards = change ? change.list : [];
  const mapStops: TripStop[] = changing ? changeStops(view, changing, cards) : stopsOf(view, mapDay);
  const looks = changing ? changeLooks(view, changing, cards) : undefined;
  const mapSelected = changing && change ? (change.index === 0 ? changing.id : `cand-${change.index}`) : selected ?? undefined;
  function onPin(id: string) {
    if (changing && change) {
      const index = id === changing.id ? 0 : id.startsWith("cand-") ? Number(id.slice(5)) : -1;
      if (index >= 0) setChange({ ...change, index });
      return;
    }
    if (done) pick(id, "map");
  }

  const applyWhy = !changing ? null : !actions.replace ? t("장소 바꾸기는 준비 중이에요", "Changing the place is coming")
    : changing.locked ? t("고정한 일정이라 바꿀 수 없어요 · 잠금을 풀면 수정할 수 있어요", "Locked · unlock it to change it") : frozen;

  return <div className={styles.checking} data-sheet={sheet} data-changing={changing ? true : undefined}>
    <div className={styles.map}>
      <TripMap stops={mapStops} dayNumber={mapDay} selectedId={mapSelected} looks={looks} variant="fill" onSelect={onPin} />
    </div>
    {unlocated.length > 0 && <p className={styles.unlocated}>{t("위치 미정", "No location")} · {unlocated.map((item) => item.title).join(", ")}</p>}
    <div className={styles.bar}>
      {changing
        ? <>
          <BackButton onBack={endChange} label={t("바꾸기 그만두기", "Stop changing")} />
          <div className={styles.searchField}>
            <Search size={16} strokeWidth={1.8} aria-hidden="true" />
            <input ref={searchInput} type="search" value={query} placeholder={t(`${changing.title} 대신 찾을 장소`, `A place instead of ${changing.title}`)}
              aria-label={t("장소 검색", "Search places")} autoComplete="off" onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); if (query) setQuery(""); else endChange(); } }} />
            {query && <button type="button" className={styles.clear} aria-label={t("검색어 지우기", "Clear the search")} onClick={() => { setQuery(""); searchInput.current?.focus(); }}><X size={12} strokeWidth={2} aria-hidden="true" /></button>}
          </div>
        </>
        : <>
          <BackButton onBack={onBack} />
          {done && view.title
            ? <h1 className={styles.barTitle}>{view.title}</h1>
            : <><h1 className="sr-only">{t("계획을 확인하고 있어요", "Checking your plan")}</h1><ProgressBar view={view} small /></>}
        </>}
    </div>
    <section className={styles.sheet} aria-labelledby={changing ? "plan-change-title" : "plan-check-sheet-title"}>
      {done && <button type="button" className={styles.handle} aria-label={t("목록 높이 바꾸기", "Change the list height")}
        onClick={() => setSheet((current) => SHEETS[(SHEETS.indexOf(current) + 1) % SHEETS.length])}><span aria-hidden="true" /></button>}
      {changing && change
        ? <PlaceChange item={changing} session={change} search={search} explain={explain} applyWhy={applyWhy} candidatesSupported={Boolean(actions.candidates)}
            onIndex={(index) => setChange({ ...change, index })} onApply={(candidate) => replace(changing, { candidate })} onApplyName={(name) => replace(changing, { name })}
            onPick={(candidate) => {
              const at = change.list.findIndex((entry) => entry.id === candidate.id);
              const list = at >= 0 ? change.list : [{ ...candidate, source: "search" as const }, ...change.list];
              setChange({ ...change, list, index: at >= 0 ? at + 1 : 1 }); setQuery("");
            }}
            onSheetFull={() => setSheet("full")}
            editor={actions.edit && <details className={styles.details} open={details} onToggle={(event) => setDetails(event.currentTarget.open)}>
              <summary>{t("직접 고치기 · 이름·날짜·시각·장소 없음", "Edit directly · name, date, time, no place")}</summary>
              {details && <StopEditor key={changing.id} item={changing} autoFocus={false} onCancel={() => setDetails(false)}
                onSave={async (draft) => {
                  await actions.edit!(changing.id, draft);
                  setChange(null); setDetails(false); setOpen(changing.id); refocus(changing.id, "edit");
                  setToast({ text: t("저장했어요. 서버가 일정을 다시 확인했어요.", "Saved. The server checked the plan again.") });
                }} />}
            </details>} />
        : <>
          <header className={styles.sheetHead}>
            <h2 id="plan-check-sheet-title" className={styles.sheetTitle}>{registered ? t("등록 완료", "Registered") : done ? t("계획 확인", "Plan check") : t("장소·운영시간 확인", "Places & hours")}</h2>
            <p className={styles.count}>{done ? headStatus(view, registered, t) : countText(view, t)}</p>
          </header>
          <div className={styles.sheetBody}>
            {done && tripIssues.length > 0 && <TripIssues issues={tripIssues} onSave={actions.editTrip} />}
            {days.map((day) =>
              <section key={day.day} aria-labelledby={`plan-day-${day.day}`}>
                <h3 id={`plan-day-${day.day}`} className={styles.day}>{done
                  ? <button type="button" className={styles.dayButton} aria-pressed={mapDay === day.day} onClick={() => showDay(day.day)}>{dayHeading(day, language, t)}</button>
                  : dayHeading(day, language, t)}</h3>
                <ol className={styles.timeline}>{timeline(view, day.day).map((entry) => entry.type === "item"
                  ? <ItemRow key={entry.item.id} item={entry.item} done={done} open={!done || open === entry.item.id || entry.item.verdict === null}
                      selected={done && selected === entry.item.id} rechecking={view.rechecking === entry.item.id} frozen={frozen} actions={actions} explain={explain}
                      onToggle={() => pick(entry.item.id, "list")} onChange={() => void startChange(entry.item)} onDelete={() => setDeleting(entry.item.id)}
                      onLock={() => lock(entry.item)} onRecommend={() => recommend(entry.item)} />
                  : <MoveRow key={entry.move.id} move={entry.move} done={done} open={done && open === entry.move.id} onToggle={() => setOpen((current) => current === entry.move.id ? null : entry.move.id)} />)}</ol>
              </section>)}
            {done && !view.items.length && <p className={styles.empty}>{t("남은 일정이 없어요", "No stops left")}</p>}
            {done && onOpenPrevious && <p className={styles.previous}><button type="button" onClick={onOpenPrevious}>{t("이전 확인 화면 열기", "Open the previous review screen")}</button></p>}
          </div>
          {done && <ResultFooter view={view} registration={registration} frozen={frozen} explain={explain}
            onAutoAll={actions.autoRecommendAll && recommendAll} onRecheck={actions.recheck && recheck} />}
        </>}
    </section>
    {deletingItem && <DeleteDialog item={deletingItem} undoable={undoable}
      dayLabel={t(`${deletingItem.day}일차`, `Day ${deletingItem.day}`)}
      onCancel={() => { setDeleting(null); refocus(deletingItem.id, "delete"); }}
      onDelete={async () => {
        await actions.remove!(deletingItem.id);
        setDeleting(null);
        if (selected === deletingItem.id) setSelected(null);
        setToast({ text: t(`${deletingItem.title} 일정을 삭제했어요`, `Deleted ${deletingItem.title}`),
          sub: view.moves.some((move) => move.fromId === deletingItem.id || move.toId === deletingItem.id) ? t("앞뒤 이동을 다시 계산했어요", "The moves either side were worked out again") : undefined, undo: undoable });
      }} />}
    <div className={styles.toast} role="status" data-shown={toast ? true : undefined}>
      {toast && <><span className={styles.toastText}>{toast.text}{toast.sub && <small>{toast.sub}</small>}</span>
        {toast.undo && <button type="button" className={styles.undo} onClick={undo}>{t("되돌리기", "Undo")}</button>}</>}
    </div>
  </div>;
}

function dayHeading(day: { day: number; date: string }, language: Language, t: Translate) {
  return <>{t(`${day.day}일차`, `Day ${day.day}`)}<small>{day.date ? dayLabel(day.date, language) : t("날짜 미정", "date to be set")}</small></>;
}

/**
 * One stop's card: the lock, the name (opens and closes the card), its verdict, edit and delete; inside, its checks and
 * 「자동 추천」 · 「수정」. A tool that cannot act now stays and says why (locked, being checked, not connected yet).
 */
function ItemRow({ item, done, open, selected, rechecking, frozen, actions, explain, onToggle, onChange, onDelete, onLock, onRecommend }: {
  item: PlanItem; done: boolean; open: boolean; selected: boolean; rechecking: boolean; frozen: string | null;
  actions: PlanCheckActions; explain: (why: string) => void;
  onToggle: () => void; onChange: () => void; onDelete: () => void; onLock: () => void; onRecommend: () => void;
}) {
  const t = useT();
  const checking = item.verdict === null;
  const review = item.verdict === "review";
  const lockedWhy = t("고정한 일정이라 바꿀 수 없어요 · 잠금을 풀면 수정할 수 있어요", "Locked · unlock it to change it");
  const lockWhy = !actions.lock ? t("잠금은 준비 중이에요", "Locking is coming") : review ? t("확인이 필요한 일정은 먼저 고쳐야 고정할 수 있어요", "Fix this stop before locking it") : frozen;
  const changeWhy = !actions.replace && !actions.edit ? t("수정은 준비 중이에요", "Editing is coming") : item.locked ? lockedWhy : frozen;
  const autoWhy = !actions.autoRecommend ? t("자동 추천은 준비 중이에요", "Recommending is coming") : item.locked ? lockedWhy : frozen;
  const deleteWhy = !actions.remove ? t("삭제는 준비 중이에요", "Deleting is coming") : item.locked ? t("고정한 일정은 삭제할 수 없어요 · 잠금을 먼저 풀어 주세요", "Locked stops cannot be deleted · unlock it first") : frozen;
  const lockLabel = review ? t("확인이 필요한 일정은 고정할 수 없어요", "Stops that need a look cannot be locked") : item.locked ? t(`${item.title} 고정 풀기`, `Unlock ${item.title}`) : t(`${item.title} 꼭 넣을 일정으로 고정`, `Lock ${item.title} in`);
  // Being checked again (after a change, or in a full re-check): a waiting label in place of the verdict.
  const status = done && (checking || rechecking)
    ? <span className={styles.pillWait}><span className={styles.spinner} aria-hidden="true" />{rechecking ? t("재검증", "Checking") : t("확인 중", "Checking")}</span>
    : checking ? <span className={styles.spinner} role="img" aria-label={t("확인하는 중", "Checking")} /> : <VerdictPill verdict={item.verdict!} />;
  const note = item.locked ? lockedWhy
    : !actions.autoRecommend ? t("자동 추천은 준비 중이에요 · 수정에서 장소를 바꿀 수 있어요", "Recommending is coming · change the place in Edit")
      : item.suggestion ? t(`자동 추천은 1순위 ${ro(item.suggestion)} 바로 바꿔요`, `Recommend changes it to the first alternative, ${item.suggestion}`) : null;
  return <li className={styles.entry} data-type="item" data-verdict={item.verdict ?? "checking"} data-selected={selected || undefined}>
    <span className={styles.time}>{item.startsAt || "–"}</span>
    <span className={styles.rail} aria-hidden="true"><span className={styles.dot} /></span>
    <article id={`plan-card-${item.id}`} className={styles.card} data-locked={item.locked || undefined} aria-labelledby={`plan-item-${item.id}`} aria-busy={checking}>
      {done
        // Once done a card opens and closes (accordion: the heading holds the button).
        ? <div className={styles.cardTop}>
            <Act className={styles.icon} why={lockWhy} explain={explain} onPress={onLock} aria-pressed={item.locked} aria-label={lockLabel} title={lockLabel}>
              {item.locked ? <Lock size={16} strokeWidth={1.8} aria-hidden="true" /> : <LockOpen size={16} strokeWidth={1.8} aria-hidden="true" />}</Act>
            <h4 className={styles.cardHeading}><button type="button" className={styles.cardHead} aria-expanded={open} aria-controls={`plan-item-${item.id}-checks`} onClick={onToggle}>
              <span id={`plan-item-${item.id}`} className={styles.cardTitle}>{item.title}</span>
            </button></h4>
            {status}
            <Act id={`plan-edit-${item.id}`} className={styles.icon} why={changeWhy} explain={explain} onPress={onChange} aria-label={t(`${item.title} 수정`, `Edit ${item.title}`)}><Pencil size={16} strokeWidth={1.8} aria-hidden="true" /></Act>
            <Act id={`plan-delete-${item.id}`} className={styles.icon} why={deleteWhy} explain={explain} onPress={onDelete} aria-label={t(`${item.title} 삭제`, `Delete ${item.title}`)}><Trash2 size={16} strokeWidth={1.8} aria-hidden="true" /></Act>
          </div>
        : <header className={styles.cardHead}><h4 id={`plan-item-${item.id}`} className={styles.cardTitle}>{item.title}</h4>{status}</header>}
      {open && <div id={`plan-item-${item.id}-checks`}>
        {item.checks.length
          ? <Checks rows={item.checks} />
          : <p className={styles.noChecks}>{t("서버가 이 일정에 따로 알린 것이 없어요.", "The server has nothing more on this stop.")}</p>}
        {done && !checking && <>
          <div className={styles.cardActions}>
            <Act className={styles.action} why={autoWhy} explain={explain} onPress={onRecommend}><Sparkles size={15} strokeWidth={1.8} aria-hidden="true" />{t("자동 추천", "Recommend")}</Act>
            <Act className={styles.action} data-primary why={changeWhy} explain={explain} onPress={onChange}><Pencil size={15} strokeWidth={1.8} aria-hidden="true" />{t("수정", "Edit")}</Act>
          </div>
          {note && <p className={styles.cardNote}>{note}</p>}
        </>}
      </div>}
    </article>
  </li>;
}

function MoveRow({ move, done, open, onToggle }: { move: PlanMove; done: boolean; open: boolean; onToggle: () => void }) {
  const t = useT();
  const checking = move.verdict === null;
  const line = checking ? null : <><span className={styles.mode}>{move.mode}</span><span className={styles.moveText}>{move.summary}</span><VerdictMark verdict={move.verdict!} /></>;
  return <li className={styles.entry} data-type="move" data-verdict={move.verdict ?? "checking"}>
    <span className={styles.time}>{!checking && <><b>{move.departAt}</b><small>{t("출발", "leave")}</small></>}</span>
    <span className={styles.rail} aria-hidden="true"><span className={styles.dot} /></span>
    <div className={styles.move} data-open={open || undefined}>{checking
      ? <span className={styles.waiting}>{done ? t("이동 경로 다시 찾는 중…", "Finding the way again…") : t("이동 경로를 찾는 중…", "Finding the way…")}</span>
      : done
        ? <><button type="button" className={styles.moveHead} aria-expanded={open} aria-controls={`plan-move-${move.id}-checks`} onClick={onToggle}>{line}</button>
          {open && <Checks id={`plan-move-${move.id}-checks`} rows={move.checks} />}</>
        : <div className={styles.moveHead}>{line}</div>}</div>
  </li>;
}

function countText(view: PlanCheckView, t: Translate): string {
  const count = tally(view);
  if (view.stage !== "done") return t(`장소 ${count.placesDone}/${count.places} · 이동 ${count.movesDone}/${count.moves}`, `Places ${count.placesDone}/${count.places} · Moves ${count.movesDone}/${count.moves}`);
  const left = needs(view);
  if (!left.total) return t("모두 확인했어요", "All checked");
  const parts = [left.places && t(`장소 ${left.places}곳`, `${left.places} place${left.places > 1 ? "s" : ""}`),
    left.moves && t(`이동 ${left.moves}구간`, `${left.moves} move${left.moves > 1 ? "s" : ""}`)].filter(Boolean);
  return t(`${parts.join(" · ")} 확인 필요`, `To check: ${parts.join(" · ")}`);
}

/** The done sheet's head (mockup updateHead): being checked again, registered, what needs a look, changed, or nothing to fix. */
function headStatus(view: PlanCheckView, registered: boolean, t: Translate): ReactNode {
  if (registered) return <Status result="ok">{t("여행을 등록했어요", "The trip is registered")}</Status>;
  if (view.rechecking) {
    const order = view.days.flatMap((day) => view.items.filter((item) => item.day === day.day).map((item) => item.id));
    return <span className={styles.status}><span className={styles.spinner} aria-hidden="true" />{t(`재검증 중 · ${order.indexOf(view.rechecking) + 1}/${order.length}`, `Checking again · ${order.indexOf(view.rechecking) + 1}/${order.length}`)}</span>;
  }
  if (needs(view).total) return <Status result="warn">{countText(view, t)}</Status>;
  if (view.dirty) return <Status result="filled">{t("고친 곳이 있어요 · 재검증해 주세요", "Changed · check again")}</Status>;
  return <Status result="ok">{t("고칠 곳이 없어요", "Nothing to fix")}</Status>;
}

function announce(view: PlanCheckView, t: Translate): string {
  if (view.stage === "received") return t("계획을 받았어요.", "Plan received.");
  if (view.stage === "reading") return t("일정을 읽고 있어요.", "Reading your plan.");
  if (view.stage === "checking") return t("장소와 운영시간을 확인하고 있어요.", "Checking places and opening hours.");
  return t(`확인을 마쳤어요. ${countText(view, t)}.`, `Check finished. ${countText(view, t)}.`);
}

const monthDay = (date: string) => `${date.slice(5, 7)}.${date.slice(8, 10)}`;
const weekday = (date: string, language: Language) =>
  new Intl.DateTimeFormat(language === "ko" ? "ko-KR" : "en-US", { weekday: "short", timeZone: "Asia/Seoul" }).format(new Date(`${date}T12:00:00+09:00`));

function dayLabel(date: string, language: Language): string {
  return `${monthDay(date)} ${weekday(date, language)}`;
}

function findingLabel(found: LineFinding, language: Language, t: Translate): string {
  if (found.kind === "date") return t(`날짜 · ${monthDay(found.date)}(${weekday(found.date, language)})`, `Date · ${monthDay(found.date)} (${weekday(found.date, language)})`);
  const when = [found.day !== null && t(`${found.day}일차`, `Day ${found.day}`), found.startsAt].filter(Boolean).join(" ");
  return when ? `${when} · ${found.title}` : found.title;
}

const asStop = (id: string, date: string, time: string, title: string, coordinates: TripStop["coordinates"]): TripStop =>
  ({ id, date, time, title, booking: "unknown", notes: "", coordinates });

/** The map's stops for one day. Places without coordinates are passed too: the map says they have no pin. */
function stopsOf(view: PlanCheckView, day: number): TripStop[] {
  const date = view.days.find((entry) => entry.day === day)?.date ?? "";
  return view.items.filter((item) => item.day === day).map((item) => asStop(item.id, date, item.startsAt, item.title, item.coordinates));
}

/** The change screen's map (mockup renderEditMap): the day's stops, then the alternatives as `cand-1`, `cand-2` … */
function changeStops(view: PlanCheckView, item: PlanItem, list: PlanCandidate[]): TripStop[] {
  return [...stopsOf(view, item.day), ...list.map((candidate, at) => asStop(`cand-${at + 1}`, item.date, "", candidate.name, candidate.coordinates))];
}

function changeLooks(view: PlanCheckView, item: PlanItem, list: PlanCandidate[]): Record<string, PinLook> {
  const looks: Record<string, PinLook> = {};
  view.items.filter((entry) => entry.day === item.day).forEach((entry, at) => { looks[entry.id] = { label: String(at + 1), tone: entry.id === item.id ? "current" : "muted" }; });
  list.forEach((_, at) => { looks[`cand-${at + 1}`] = { label: letter(at + 1), tone: "candidate" }; });
  return looks;
}

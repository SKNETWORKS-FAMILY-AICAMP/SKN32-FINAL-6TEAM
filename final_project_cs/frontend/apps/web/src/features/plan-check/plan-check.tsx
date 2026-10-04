"use client";

import { useContext, useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent, type ReactNode, type TouchEvent } from "react";
import { createPortal } from "react-dom";
import { ArrowLeft, ChevronsDown, ChevronsRight, ChevronsUp, Pencil, Search, Undo2, X } from "lucide-react";
import { DeviceFrame, HeaderSlot } from "@/components/layout/device-frame";
import { TripMap } from "@/features/map";
import { routeNotes, visibleShapes } from "@/features/map/route-lines";
import type { RouteShapes } from "@/lib/live/route-shapes";
import type { PinLook } from "@/features/map/model";
import type { TripStop } from "@/features/trip/model";
import type { Language, Translate } from "@/lib/i18n";
import { eul, ro } from "@/lib/josa";
import { useSettings, useT } from "@/lib/settings";
import { foundCount, isInstantRow, needs, progress, STAGES, tally, timeline, type CheckRow, type ItemDraft, type LineFinding, type PlanCandidate, type PlanCheckView, type PlanDay, type PlanItem, type ServerProgress, type TripIssue } from "./model";
import { Act, HeadBadges, letter, reason, type ListFilter } from "./parts";
import { PlaceChange, type ChangeSession, type SearchState } from "./place-change";
import { dayTimes, withTimes } from "./day-times";
import { DayList, type RowContext } from "./plan-rows";
import { ResultFooter, StopEditor, TripIssues, type Registration } from "./result-parts";
import { useFollowScroll } from "./use-follow-scroll";
import { usePullPastEnd } from "./use-pull-past-end";
import { formatHm, moveStop, parseHm, type Retime } from "./time-plan";
import { useTimeEdit } from "./use-time-edit";
import { REVEAL_MS, useReveal } from "./use-reveal";
import styles from "./plan-check.module.css";

export interface PlanCheckProps {
  /** The latest snapshot. The screen paces the changes between snapshots itself (`useReveal`). */
  view: PlanCheckView;
  /** The back arrow — e.g. back to the plan entry. */
  onBack: () => void;
  /** Called once the screen has drawn everything in `view` and held it a moment — e.g. to move on after the last line. */
  onCaughtUp?: () => void;
  /** Shown above the screen's content — e.g. a line about the connection. */
  notice?: ReactNode;
  /** The plan is still on its way to the server (`sendingOf`): the stage `received` is then not the server's word, so it is not read out as one. */
  sending?: boolean;
  /** What the result can change, each wired by the page. One left out stays on the screen and says it is coming. */
  actions?: PlanCheckActions;
  /** Registering the result, at the bottom of the list once the check is done. */
  registration?: Registration;
  /** Trip-wide details the server asks for before it can register. */
  tripIssues?: TripIssue[];
  /**
   * `[2026-10-04]` The plan as 「전체 자동 추천」 WOULD make it (the server's dry run: nothing saved), once it has been asked for. The screen stands it under `view` and lets the list
   * scroll on into it; `view` stays the plan as it is, so both pictures are held and the customer can go back up to the one before.
   */
  previewView?: PlanCheckView | null;
  /** `[2026-10-04]` The lines between the stops for the plan as it is (the server's `route-shapes` for the intake); null = none (an older server, or nothing to draw). */
  routes?: RouteShapes | null;
}

/** A place for one stop: an alternative or a search result, or just a name the server looks up. */
export type PlaceChoice = { candidate: PlanCandidate } | { name: string };

/** What 「전체 자동 추천」 did: one line per stop changed (「올리브영 → 올리브영 광화문점 11:00–12:00」), how many stayed. */
export interface AutoResult {
  changes: string[];
  kept: number;
  /** The stops it changed and what each had been (the place's name, or 「장소 미정」) — the screen marks them 「바뀜」. */
  changed?: { id: string; from: string }[];
}

/**
 * The result's changes — the seams the backend connects (PLAN_CHECK_SCREEN.md §4). Each resolves once the plan is the
 * new one (the page passes the new `view`), or rejects with the server's sentence. One left out is shown but says it is
 * coming, so the screen is whole either way.
 */
export interface PlanCheckActions {
  /** Save one stop's details as drafted (the server looks a typed place up again and checks the plan again). */
  edit?: (id: string, draft: ItemDraft) => Promise<void>;
  /**
   * `[2026-10-04]` Move several stops in time at once: each change is one stop's new start and end ("HH:MM"; `end` "" = no end time).
   * All changes go to the server in ONE request, so the plan is saved and checked again once. A change that changes nothing is skipped.
   */
  retime?: (changes: { id: string; start: string; end: string }[]) => Promise<void>;
  /** Take one stop out. */
  remove?: (id: string) => Promise<void>;
  /** Answer a trip-wide detail. */
  editTrip?: (field: "first_day" | "party_size" | "title", value: string | number) => Promise<void>;
  /** The alternatives for one stop, best first (mockup 「대체 후보 A · B · C」). */
  candidates?: (id: string) => Promise<PlanCandidate[]>;
  /** Why the list for a stop is short or empty (the server's `notes`: `no_same_kind` · `booked_needs_name` · …) — read after `candidates` has answered. */
  candidateNotes?: (id: string) => string[];
  /** Places matching words, nearest first (the change screen's search bar). */
  search?: (id: string, query: string) => Promise<PlanCandidate[]>;
  /** Put a place in one stop: a candidate or search result, or a name the server looks up. */
  replace?: (id: string, choice: PlaceChoice) => Promise<void>;
  /** The first alternative, in one press (the card's 「자동 추천」). */
  autoRecommend?: (id: string) => Promise<void>;
  /**
   * 「전체 자동 추천」: first only SHOWN (`previewRecommendAll` — nothing is saved; the screen then draws the plan as it would be), then saved
   * by `applyRecommended` or let go by `discardPreview`. `[2026-10-03]` Pushing past the end of the list or pressing the button never changes the plan.
   */
  previewRecommendAll?: () => Promise<AutoResult>;
  applyRecommended?: () => Promise<AutoResult>;
  discardPreview?: () => void;
  /** Fix a stop so re-planning and recommendations keep it (「잠금」 — 「반드시 포함」). */
  lock?: (id: string, locked: boolean) => Promise<void>;
  /** Put back what the last change, delete or recommendation changed (「되돌리기」). */
  undo?: () => Promise<void>;
  /** Whether the last change can be put back (a change whose earlier place is not known cannot) — the screen offers 「되돌리기」 only when it can. */
  canUndo?: () => boolean;
  /** Check the whole plan again without changing it (「다시 제출」); the view says which stop it is at (`rechecking`). `ids` = the stops that were changed (the ones shown being checked). */
  recheck?: (ids?: string[]) => Promise<void>;
}

/** How long the screen stays on what it has drawn before `onCaughtUp` — so the last line read is seen, not skipped. */
const HOLD_MS = 800;

/**
 * The plan check after 「계획 확인하기」, as the mockup `mockups/tripilot-plan-check-streaming.html` draws it: the uploaded
 * lines being read, then the places, hours and moves being checked on a map with a sheet over it, then the result —
 * cards and pins worked together, each stop locked, recommended, changed or deleted, 「전체 자동 추천 → 재검증 → 여행 등록」.
 * A phone-sized page of its own, like the start screen.
 */
export function PlanCheck({ view: latest, onBack, onCaughtUp, notice, sending = false, ...result }: PlanCheckProps) {
  const { view, settled } = useReveal(latest);
  const t = useT();
  useEffect(() => {
    if (!settled || !onCaughtUp) return;
    const timer = setTimeout(onCaughtUp, HOLD_MS);
    return () => clearTimeout(timer);
  }, [settled, onCaughtUp]);
  // ★`[2026-10-04 사용자 지시]` Once the map is there the header is transparent: the map reaches the top and only the home mark, the plan's name and the menu float over it.
  const floating = view.stage === "checking" || view.stage === "done";
  return <DeviceFrame floating={floating}>
    <div className={styles.screen} data-stage={view.stage} data-floating={floating || undefined}>
      {notice}
      {view.stage === "received" || view.stage === "reading" ? <Reading view={view} onBack={onBack} /> : <Checking view={view} {...result} />}
      <p className="sr-only" role="status">{sending ? t("계획을 서버로 보내고 있어요.", "Sending your plan to the server.") : announce(view, t)}</p>
    </div>
  </DeviceFrame>;
}

function BackButton({ onBack, label }: { onBack: () => void; label?: string }) {
  const t = useT();
  return <button type="button" className={styles.back} onClick={onBack} aria-label={label ?? t("뒤로", "Back")}><ArrowLeft size={20} strokeWidth={1.6} aria-hidden="true" /></button>;
}

const stepLabels = (t: Translate) => [t("받았어요", "Received"), t("일정 읽기", "Reading"), t("장소·운영시간", "Places & hours"), t("정리 완료", "Done")];

/**
 * One straight line with four points; the filled part follows the lines read, then the places and moves checked.
 * ★`[2026-10-04 사용자 지시]` A point is checked and filled when the line has filled up to it (not when the stage after it begins), and no line shows
 * through a circle: the points stand over the line, each in the middle of a quarter of the width and the line runs from the first to the last.
 */
function ProgressBar({ view }: { view: PlanCheckView }) {
  const t = useT();
  const labels = stepLabels(t);
  const current = STAGES.indexOf(view.stage);
  const exact = progress(view);
  const value = Math.round(exact);
  // The line is as far as the points it has reached: point `i` of four sits at `i / 3` of the line (`stops`), and is reached when the line is that far.
  //   The last point is the screen having drawn everything (the stage 「정리 완료」), however far the server's own count says it is.
  const last = labels.length - 1;
  const reached = (index: number) => view.stage === "done" || (index === 0 ? view.stage !== "received" : index === last ? false : exact >= (index / last) * 100 - 0.05);
  const waitingAt = labels.findIndex((_, index) => !reached(index));
  // ★`[2026-10-03]` The server's "장소 3/14 · 광장시장" count comes while it reads, so the big bar says it too.
  const at = view.serverProgress ? serverProgressText(view.serverProgress, t) : null;
  return <div className={styles.progress} data-size="large" role="progressbar" aria-label={t("계획 확인 진행", "Plan check progress")}
    aria-valuemin={0} aria-valuemax={100} aria-valuenow={value} aria-valuetext={`${labels[current]} · ${value}%${at ? ` · ${at}` : ""}`}>
    <div className={styles.track}><span className={styles.fill} style={{ width: `${Math.min(100, exact)}%` }} /></div>
    <ol className={styles.steps}>{labels.map((label, index) =>
      <li key={label} data-state={reached(index) ? "done" : index === waitingAt ? "current" : "waiting"}>
        <span className={styles.node} aria-hidden="true" /><span className={styles.stepLabel}>{label}</span>
      </li>)}</ol>
    {/* ★Under the steps, not between them and the track: `.steps` is pulled up over the track (negative margin), so a line there was drawn over the nodes (user's screenshot 2026-10-03). */}
    {at && <p className={styles.progressAt}>{at}</p>}
  </div>;
}

/**
 * `[2026-10-03 사용자]` The check's progress beside the brand in the header (it was a white bar of its own under the header):
 * the step the server is at and how far, with a thin line under it. Same `progressbar` as the big one on the reading screen.
 */
function HeaderProgress({ view }: { view: PlanCheckView }) {
  const t = useT();
  const labels = stepLabels(t);
  const current = STAGES.indexOf(view.stage);
  const value = Math.round(progress(view));
  // ★`[2026-10-03 사용자 지시]` What the server says it is at ("3/14 · 광장시장 운영시간 확인 중"): only when it sent a `progress` packet.
  // ★A "places" count belongs to the reading: once the check has begun, a left-over "13/14 · … 장소 확인 중" would keep saying that while the hours and legs are drawn.
  const at = view.serverProgress && view.serverProgress.phase !== "places" ? serverProgressText(view.serverProgress, t) : null;
  return <div className={styles.headProgress} role="progressbar" aria-label={t("계획 확인 진행", "Plan check progress")}
    aria-valuemin={0} aria-valuemax={100} aria-valuenow={value} aria-valuetext={`${labels[current]} · ${value}%${at ? ` · ${at}` : ""}`}>
    <span className={styles.headStep}>{labels[current]}<b>{value}%</b></span>
    <span className={styles.headTrack}><span style={{ width: `${value}%` }} /></span>
    {at && <span className={styles.headAt}>{at}</span>}
  </div>;
}

/** "3/14 · 광장시장 운영시간 확인 중" — the count and the step the server is at, in its words (no title when the packet names none). */
export function serverProgressText(at: ServerProgress, t: Translate): string {
  const what = at.phase === "places" ? t("장소 확인", "place check") : at.phase === "hours" ? t("운영시간 확인", "hours check") : t("이동 확인", "route check");
  return `${at.done}/${at.total} · ${at.title ? `${at.title} ` : ""}${what}${t(" 중", " in progress")}`;
}

/**
 * The plan's name in the header. ★`[2026-10-04 사용자 지시]` The name has the room (the home mark is only the mark now) and no pencil stands by it all the time: pressing the name shows the whole
 * name and a pencil for a few seconds; the pencil turns it into a field (Enter or leaving it saves, Esc keeps the name). Without a way to save it is plain text.
 */
function TripTitle({ title, onSave }: { title: string; onSave?: (value: string) => Promise<void> }) {
  const t = useT();
  const [editing, setEditing] = useState(false);
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const timer = setTimeout(() => setArmed(false), 4500);
    return () => clearTimeout(timer);
  }, [armed]);
  const [draft, setDraft] = useState(title);
  const input = useRef<HTMLInputElement>(null);
  const cancelled = useRef(false);
  useEffect(() => { if (editing) { cancelled.current = false; input.current?.select(); } }, [editing]);
  if (!onSave) return <h1 className={styles.headTitle}>{title}</h1>;
  function commit() {
    if (cancelled.current) return;
    const next = draft.trim();
    setEditing(false);
    if (next && next !== title) void onSave?.(next);
  }
  if (editing) {
    return <form className={styles.titleForm} onSubmit={(event) => { event.preventDefault(); commit(); }}>
      <input ref={input} className={styles.titleInput} value={draft} maxLength={80} aria-label={t("계획 이름", "Plan name")} autoComplete="off" enterKeyHint="done"
        onChange={(event) => setDraft(event.target.value)} onBlur={commit}
        onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); cancelled.current = true; setEditing(false); } }} />
    </form>;
  }
  return <h1 className={styles.headTitle} data-armed={armed || undefined}>
    <button type="button" className={styles.titleButton} onClick={() => setArmed((current) => !current)} aria-expanded={armed} aria-label={t(`계획 이름 · ${title}`, `Plan name · ${title}`)}>
      <span>{title}</span>
    </button>
    {armed && <button type="button" className={styles.titleEdit} onClick={() => { setDraft(title); setEditing(true); setArmed(false); }} aria-label={t(`계획 이름 바꾸기 · 지금 이름은 ${title}`, `Rename the plan · now ${title}`)}>
      <Pencil size={15} strokeWidth={1.8} aria-hidden="true" />
    </button>}
  </h1>;
}

/** 한국관광공사 이용조건 — 관광정보를 화면에 올리면 출처와 저작권 정책 링크를 같이 준다(루트 사실표 「출처 표시 유지」). 옛 목록 화면에 있던 줄을 새 화면으로 옮겼다. */
const TOUR_API_POLICY_URL = "https://api.visitkorea.or.kr/#/useServiceGuide/2";

/** What the lists follow while the server's check is drawn: the newest row of the check, and the line being read (else the last one read). */
const newestRow = (box: HTMLElement) => {
  const rows = box.querySelectorAll<HTMLElement>("li[data-type]");
  return rows[rows.length - 1] ?? null;
};
const currentLine = (box: HTMLElement) =>
  box.querySelector<HTMLElement>('li[data-state="current"]') ?? Array.from(box.querySelectorAll<HTMLElement>('li[data-state="read"]')).at(-1) ?? null;

/** ①② The uploaded plan, read line by line. */
function Reading({ view, onBack }: { view: PlanCheckView; onBack: () => void }) {
  const t = useT();
  const { language } = useSettings();
  const current = view.stage === "reading" ? view.lines.findIndex((line) => !line.read) : -1;
  // `[2026-10-03 사용자]` The list scrolls along with the line being read.
  const box = useRef<HTMLDivElement>(null);
  const follow = useFollowScroll(box, currentLine, true, view.lines);
  return <div ref={box} className={styles.reading} {...follow.handlers}>
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
    {!follow.following && <button type="button" className={styles.followPill} onClick={follow.resume}><ChevronsDown size={14} strokeWidth={1.8} aria-hidden="true" />{t("읽는 곳으로", "Follow the reading")}</button>}
  </div>;
}

/** How high the sheet stands over the map: a strip, half the screen, or (nearly) all of it — the handle cycles them. */
const SHEETS = ["half", "full", "peek"] as const;
type Sheet = (typeof SHEETS)[number];

/** Under this height (px) the sheet keeps only its handle and its two buttons: there is no room left for a list worth reading (`[2026-10-04 사용자]`). */
const COMPACT_BELOW = 190;
/** The least the sheet can be dragged to: the handle and the buttons. */
const SHEET_MIN = 104;

interface Toast { text: string; sub?: string; undo?: boolean; /** Puts back what this toast says was done (a batch of new times), instead of the plan-wide 「되돌리기」. */ revert?: () => void }

type ResultProps = Pick<PlanCheckProps, "actions" | "registration" | "tripIssues" | "previewView" | "routes">;

/** What still needs a look in a plan, leaving out the stops marked for deletion (they are leaving) and the legs that end at one. */
function needsLeft(view: Pick<PlanCheckView, "items" | "moves">, removed: ReadonlySet<string>): { places: number; moves: number; total: number } {
  const places = view.items.filter((item) => item.verdict === "review" && !removed.has(item.id)).length;
  const moves = view.moves.filter((move) => move.verdict === "review" && !removed.has(move.fromId) && !removed.has(move.toId)).length;
  return { places, moves, total: places + moves };
}

/** ③④⑤ The map under a floating bar, the sheet over it. Once done, the list and the map are worked together. */
function Checking({ view, actions = {}, registration, tripIssues = [], previewView = null, routes = null }: { view: PlanCheckView } & ResultProps) {
  const t = useT();
  const { language, skipAnimation } = useSettings();
  const done = view.stage === "done";
  // What the customer picked once the check is done: one card or move open, one place selected, one day on the map.
  const [openAt, setOpenAt] = useState<{ list: "before" | "after"; id: string } | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [chosenDay, setChosenDay] = useState<number | null>(null);
  const [sheet, setSheet] = useState<Sheet>("half");
  // ⑤ The stop being changed (the change screen takes the sheet), the search in the top bar.
  const [change, setChange] = useState<ChangeSession | null>(null);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<SearchState | null>(null);
  const [details, setDetails] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [working, setWorking] = useState(false);
  const searchInput = useRef<HTMLInputElement>(null);
  // `[2026-10-03 사용자]` The place search lives in the header, where the brand stands: small there, and wide while it has focus.
  const headerSlot = useContext(HeaderSlot);
  const [searchOpen, setSearchOpen] = useState(false);
  // The list's height: one of three presets (the handle cycles them) or a height the customer dragged it to.
  const [custom, setCustom] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const [compact, setCompact] = useState(false);
  const checkingBox = useRef<HTMLDivElement>(null);
  const sheetBox = useRef<HTMLElement>(null);
  const bodyBox = useRef<HTMLDivElement>(null);
  const junction = useRef<HTMLDivElement>(null);
  const grab = useRef<{ y: number; height: number; moved: boolean } | null>(null);
  const justDragged = useRef(false);
  /**
   * ★`[2026-10-04 사용자 지시]` 「전체 자동 추천」 is first only SHOWN: the plan as it WOULD be (nothing saved) stands under the plan as it is — one list, the same line running through — and
   * the sheet, the map and the buttons follow whichever of the two is in view (`side`). The screen holds both pictures; scrolling back up shows the plan as it was.
   * It is saved when the customer registers from it or changes something while looking at it (`settle`), and let go when the plan changes some other way.
   */
  const [recommended, setRecommended] = useState<{ count: number; was: Record<string, string> } | null>(null);
  const previewing = Boolean(recommended && previewView);
  const [side, setSide] = useState<"before" | "after">("before");
  // The counts in the head, pressed, narrow the list to what needs a look / what was changed.
  const [filter, setFilter] = useState<ListFilter | null>(null);
  // `[2026-10-04]` Stops changed since the plan was last sent (and what each had been); stops marked for deletion (really taken out when the plan is sent again).
  const [changed, setChanged] = useState<Record<string, string>>({});
  const [removed, setRemoved] = useState<string[]>([]);
  const removedSet = useMemo(() => new Set(removed), [removed]);
  // `[2026-10-04 사용자]` 한 번 더 확인할 때 바뀐 곳만 확인 표시가 다시 하나씩 켜진다.
  const [replay, setReplay] = useState<{ ids: string[]; at: number } | null>(null);
  // `[2026-10-04 사용자 결정]` 날짜 칩 줄: 하루씩 보이고(칩·좌우로 넘기기), 「전체」는 이어진 목록. `"all"` = 사용자가 「전체」를 골랐다, null = 목록이 지도의 날짜를 따라간다.
  const [dayChoice, setDayChoice] = useState<"all" | null>(null);
  // Which way the last move between days went (for the slide in); null when the list was not moved from one day to another.
  const [slide, setSlide] = useState<"next" | "prev" | null>(null);
  const swipe = useRef<{ x: number; y: number } | null>(null);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), toast.undo ? 4500 : 2800);
    return () => clearTimeout(timer);
  }, [toast]);
  // The preview is gone from the page (the plan changed some other way): the list is the plan as it is.
  const hadPreview = useRef(false);
  useEffect(() => {
    if (previewView) { hadPreview.current = true; return; }
    if (!hadPreview.current) return;
    hadPreview.current = false;
    setRecommended(null);
    setSide("before");
  }, [previewView]);
  useEffect(() => {
    const element = sheetBox.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const watcher = new ResizeObserver(() => { const next = element.getBoundingClientRect().height < COMPACT_BELOW; setCompact((current) => current === next ? current : next); });
    watcher.observe(element);
    return () => watcher.disconnect();
  }, []);

  // ★A stop stands in both lists while a proposal is under the plan: what is open, and what is being edited, belongs to ONE of them — never both (opening the one out of sight would push the one in view).
  const setOpen = (id: string | null, list: "before" | "after" = "before") => setOpenAt(id === null ? null : { list, id });
  const closeOpen = (id: string) => setOpenAt((current) => current?.id === id ? null : current);
  useEffect(() => { if (!previewing) { setOpenAt((current) => current?.list === "after" ? { ...current, list: "before" } : current); } }, [previewing]);
  /** The plan the sheet, the map and the buttons are about: the proposed one while it is in view. */
  const shown: PlanCheckView = previewing && side === "after" ? previewView! : view;
  const registered = Boolean(registration?.registeredHref);
  // Nothing can be changed while a stop or the whole plan is checked again, or once registered — buttons say why.
  const frozen = registered ? t("이미 등록한 여행이에요", "This trip is already registered")
    : view.rechecking ? t("다시 확인하는 중이에요 · 잠시만요", "Checking again · one moment")
      : working || view.items.some((item) => item.verdict === null) ? t("바뀐 일정을 다시 확인하는 중이에요 · 잠시만요", "Checking the change · one moment") : null;
  const explain = (why: string) => setToast({ text: why });
  const changing = change ? view.items.find((item) => item.id === change.id) ?? null : null;
  /** Back to the card's own button after the change screen closes. */
  const refocus = (id: string, which: "edit" | "delete") => requestAnimationFrame(() => document.getElementById(`plan-${which}-${id}`)?.focus());

  const firstDay = shown.days[0]?.day ?? 1;
  // While checking, the map follows the day being checked; once done it shows the day picked (the first by default).
  const mapDay = changing ? changing.day : done ? chosenDay ?? firstDay : shown.items.at(-1)?.day ?? firstDay;
  const days = shown.days.filter((day) => shown.items.some((item) => item.day === day.day));
  // Places the server could not settle have no pin; say so on the map, as the mockup's 「위치 미정」 tag does.
  const unlocated = changing ? [] : shown.items.filter((item) => item.day === mapDay && item.verdict !== null && !item.coordinates);

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

  /**
   * A place picked on the map or in the list. ★`[2026-10-04 사용자 지시]` Pressed again it is let go: the card closes and the pin is no longer marked.
   * From the list a card opens (and is marked) or closes; from the map a pin marks its stop, opens it and brings it into view.
   */
  function pick(id: string, from: "map" | "list", list: "before" | "after" = previewing && side === "after" ? "after" : "before") {
    const item = shown.items.find((entry) => entry.id === id);
    if (!item) return;
    if (selected === id) { setSelected(null); closeOpen(id); return; }
    setSelected(id);
    setChosenDay(item.day);
    setOpen(id, list);
    if (from === "map") {
      if (sheet === "peek") setSheet("half");
      requestAnimationFrame(() => document.getElementById(`${list === "after" ? "after-" : ""}plan-card-${id}`)?.scrollIntoView({ block: "nearest" }));
    }
  }
  function showDay(day: number) {
    setChosenDay(day);
    if (shown.items.find((item) => item.id === selected)?.day !== day) setSelected(null);
  }

  /** ⑤ Open the change screen for one stop: the map shows it and its alternatives, the top bar becomes a search. */
  async function startChange(item: PlanItem) {
    timeEdit.close();
    setOpen(item.id); setSelected(item.id); setChosenDay(item.day);
    if (sheet === "peek") setSheet("half");
    setQuery(""); setDetails(false);
    setChange({ id: item.id, list: [], index: 0, state: actions.candidates ? "loading" : "ready" });
    requestAnimationFrame(() => document.getElementById("plan-change-title")?.focus({ preventScroll: true }));
    if (!actions.candidates) return;
    try {
      const list = await actions.candidates(item.id);
      const notes = actions.candidateNotes?.(item.id) ?? [];
      setChange((current) => current?.id === item.id ? { ...current, list, notes, state: "ready" } : current);
    } catch (error) {
      setChange((current) => current?.id === item.id ? { ...current, state: "failed", message: reason(error) } : current);
    }
  }
  function endChange() {
    const id = change?.id;
    setChange(null); setQuery(""); setSearch(null); setDetails(false);
    if (id) refocus(id, "edit");
  }

  /** The proposed plan stops being one the moment the plan changes in any other way. */
  function leaveRecommended() {
    if (recommended) { setRecommended(null); setSide("before"); }
  }
  /**
   * ★`[2026-10-04 사용자 지시]` Looking at the proposed plan and then changing something means the proposed plan is the plan: it is saved first (the server's
   * own check of it is already in), and the change is made on it.
   */
  async function settle(): Promise<void> {
    if (!(recommended && previewView)) return;
    const outcome = await actions.applyRecommended!();
    setChanged((current) => ({ ...current, ...wasOf(outcome) }));
    setRecommended(null);
    setSide("before");
  }
  /** Run one change; a refusal is said in the server's words, and nothing else moves. */
  async function run(step: () => Promise<Toast | null>, keepRecommended = false) {
    setWorking(true);
    try {
      if (!keepRecommended && previewing && side === "after") await settle();
      const said = await step();
      if (!keepRecommended) leaveRecommended();
      if (said) setToast(said);
    }
    catch (error) { setToast({ text: reason(error) }); }
    finally { setWorking(false); }
  }
  /** ★`[2026-10-03 사용자 지적]` 「되돌리기」는 되돌릴 수 있을 때만 단다 (이전 장소를 모르면 누른 뒤에야 「되돌릴 수 없어요」라고 하던 것). */
  const undoNow = () => Boolean(actions.undo) && (actions.canUndo?.() ?? true);
  const markChanged = (id: string, was: string) => setChanged((current) => current[id] === undefined ? { ...current, [id]: was } : current);
  const wasText = (item: PlanItem) => item.place || item.title;

  function replace(item: PlanItem, choice: PlaceChoice) {
    const name = "candidate" in choice ? choice.candidate.name : choice.name;
    const was = wasText(item);
    void run(async () => {
      await actions.replace!(item.id, choice);
      markChanged(item.id, was);
      setChange(null); setQuery(""); setSearch(null); setDetails(false);
      setOpen(item.id); refocus(item.id, "edit");
      return { text: t(`${eul(item.title)} ${ro(name)} 바꿨어요`, `Changed ${item.title} to ${name}`),
        sub: t("바뀐 장소와 앞뒤 이동을 다시 확인해요", "Checking the new place and the moves either side"), undo: undoNow() };
    });
  }
  function recommend(item: PlanItem) {
    const was = wasText(item);
    void run(async () => {
      await actions.autoRecommend!(item.id);
      markChanged(item.id, was);
      setOpen(item.id);
      return { text: item.suggestion ? t(`${eul(item.title)} ${ro(item.suggestion)} 바꿨어요`, `Changed ${item.title} to ${item.suggestion}`) : t("대체 후보 1순위로 바꿨어요", "Changed to the first alternative"),
        sub: t("대체 후보 1순위 · 바뀐 장소와 앞뒤 이동을 다시 확인해요", "First alternative · checking the new place and the moves either side"), undo: undoNow() };
    });
  }
  function lock(item: PlanItem) {
    const on = !item.locked;
    void run(async () => {
      await actions.lock!(item.id, on);
      return on ? { text: t(`${eul(item.title)} 꼭 넣을 일정으로 고정했어요`, `Locked ${item.title} in`), sub: t("다시 짜거나 바꿔도 빠지지 않게 서버에 알렸어요", "Re-planning and recommendations keep it") }
        : { text: t(`${item.title} 고정을 풀었어요`, `Unlocked ${item.title}`), sub: t("이제 바꾸거나 삭제할 수 있어요", "It can be changed or deleted now") };
    }, true);
  }
  /**
   * ★`[2026-10-04 사용자 지시]` Deleting does not delete: the card turns grey and 「되돌리기」 stands where the bin was. The stop is really taken out when the plan is sent again (`recheck`).
   */
  function markRemoved(item: PlanItem) {
    const mark = () => {
      setRemoved((current) => current.includes(item.id) ? current : [...current, item.id]);
      closeOpen(item.id);
      return { text: t(`${item.title} 일정을 뺄 거예요`, `${item.title} will be taken out`), sub: t("「다시 제출」을 누르면 지워져요 · 카드의 되돌리기로 살릴 수 있어요", "It goes when you send the plan again · Undo on the card keeps it") };
    };
    if (previewing && side === "after") void run(async () => mark(), false);   // changing the proposed plan saves it first
    else setToast(mark());
  }
  function restore(item: PlanItem) {
    setRemoved((current) => current.filter((id) => id !== item.id));
    refocus(item.id, "delete");
  }
  // ★`[2026-10-04 사용자 지시]` The time at the left of a stop is changed in place (`useTimeEdit`): typed, dragged by the grip or stepped, the stops around it pushed along if the switch is on.
  //   What it looked like when the screen opened is kept (`baseline`): a stop whose time differs has 「되돌리기」, and the head has 「시간 초기화」.
  const baseline = useRef<Record<string, { start: string; end: string }>>({});
  useEffect(() => {
    if (done && view.items.length && !Object.keys(baseline.current).length) baseline.current = Object.fromEntries(view.items.map((item) => [item.id, { start: item.startsAt, end: item.endsAt }]));
  }, [done, view.items]);
  const adjustedIn = (plan: PlanCheckView | null) => new Set((plan?.items ?? []).filter((item) => {
    const first = baseline.current[item.id];
    return first !== undefined && (first.start !== item.startsAt || first.end !== item.endsAt);
  }).map((item) => item.id));
  const timesOf = (plan: PlanCheckView, id: string): Retime | null => {
    const item = plan.items.find((entry) => entry.id === id);
    const start = parseHm(item?.startsAt ?? "");
    return item && start !== null ? { id, start, end: parseHm(item.endsAt) } : null;
  };
  /** Send a batch of new times - ONE request, however many stops move - and say what was done; the toast's 「되돌리기」 sends the old times back. */
  async function sendTimes(list: "before" | "after", changes: Retime[], text: string, quiet = false): Promise<void> {
    const plan = list === "after" && previewView ? previewView : view;
    const was = changes.flatMap((change) => { const old = timesOf(plan, change.id); return old ? [old] : []; });
    const title = (id: string) => plan.items.find((entry) => entry.id === id)?.title ?? id;
    const clock = (change: Retime) => `${formatHm(change.start)}${change.end === null ? "" : `–${formatHm(change.end)}`}`;
    setWorking(true);
    try {
      if (list === "after" && previewing) await settle();
      await actions.retime!(changes.map((change) => ({ id: change.id, start: formatHm(change.start), end: change.end === null ? "" : formatHm(change.end) })));
      for (const change of changes) { const old = was.find((entry) => entry.id === change.id); markChanged(change.id, old ? clock(old) : ""); }
      leaveRecommended();
      setToast({
        text, sub: changes.slice(0, 2).map((change) => `${title(change.id)} → ${clock(change)}`).join(" · ") + (changes.length > 2 ? t(` 외 ${changes.length - 2}곳`, ` and ${changes.length - 2} more`) : ""),
        revert: quiet || !was.length ? undefined : () => { setToast(null); void sendTimes("before", was, t("시간을 되돌렸어요", "Put the times back"), true).catch((error: unknown) => setToast({ text: reason(error) })); },
      });
    } finally { setWorking(false); }
  }
  const timeEdit = useTimeEdit({
    views: { before: view, after: previewing ? previewView : null },
    commit: (list, changes) => sendTimes(list, changes, t(`${changes.length}개 일정의 시간을 바꿨어요`, `Changed the time of ${changes.length} stop${changes.length > 1 ? "s" : ""}`)),
  });
  /** One stop back to the time it had when the screen opened (the stops around it are pushed only if that is needed to make room). */
  function revertTime(item: PlanItem) {
    const first = baseline.current[item.id];
    const list = previewing && side === "after" ? "after" : "before";
    const plan = list === "after" && previewView ? previewView : view;
    const times = dayTimes(plan, item.day);
    const index = times.indexOf.get(item.id);
    const start = parseHm(first?.start ?? "");
    if (!first || index === undefined || start === null) return;
    const end = parseHm(first.end);
    const moved = moveStop(times.stops, times.legs, index, start, { push: true, step: 1 }).changes.filter((change) => change.id !== item.id);
    void sendTimes(list, [...moved, { id: item.id, start, end }], t(`${item.title} 시간을 처음으로 되돌렸어요`, `Put the time of ${item.title} back`), true).catch((error: unknown) => setToast({ text: reason(error) }));
  }
  /** Every stop whose time was changed back to the time it had when the screen opened, in one request. */
  function resetTimes() {
    const list = previewing && side === "after" ? "after" : "before";
    const plan = list === "after" && previewView ? previewView : view;
    const changes = [...adjustedIn(plan)].flatMap((id): Retime[] => {
      const first = baseline.current[id];
      const start = parseHm(first?.start ?? "");
      return first && start !== null ? [{ id, start, end: parseHm(first.end) }] : [];
    });
    if (!changes.length) return;
    void sendTimes(list, changes, t("시간을 모두 처음으로 되돌렸어요", "Put every time back"), true).catch((error: unknown) => setToast({ text: reason(error) }));
  }
  /** What the recommendation did or would do, as the line under the toast title. */
  const changesLine = (outcome: AutoResult) => outcome.changes.slice(0, 2).join(" · ") + (outcome.changes.length > 2 ? t(` 외 ${outcome.changes.length - 2}곳`, ` and ${outcome.changes.length - 2} more`) : "")
    + (outcome.kept ? t(` · ${outcome.kept}곳은 그대로`, ` · ${outcome.kept} kept`) : "");
  const wasOf = (outcome: AutoResult) => Object.fromEntries((outcome.changed ?? []).map((entry) => [entry.id, entry.from]));
  /**
   * ★`[2026-10-03 사용자 지시]` 자동으로 바꿀 곳이 없으면 이유만 말하고 끝내지 않는다 — 사용자가 직접 고쳐야 하는 첫 곳(확인 필요)을 열고 그 자리로 옮겨 가
   * 반짝여 보인다. 고칠 곳이 없는데 못 바꾼 것이면 이유만 말한다.
   */
  function showFirstNeed(): boolean {
    // What the customer edits is a stop, so a stop that needs a look comes first; a leg only when no stop does.
    const entries = view.days.flatMap((day) => timeline(view, day.day));
    const first = entries.find((entry) => entry.type === "item" && entry.item.verdict === "review") ?? entries.find((entry) => entry.type === "move" && entry.move.verdict === "review");
    if (!first) return false;
    const id = first.type === "item" ? first.item.id : first.move.id;
    if (first.type === "item") { setSelected(first.item.id); setChosenDay(first.item.day); }
    else setChosenDay(first.move.day);
    setDayChoice((current) => current === "all" ? current : null);                       // 하루씩 볼 때는 그 곳이 있는 날로 넘어간다
    setFilter(null);
    setOpen(id);
    if (sheet === "peek") setSheet("half");
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const row = bodyBox.current?.querySelector<HTMLElement>(`[data-entry-id="${id}"]`);
      if (!row) return;
      row.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      row.dataset.attention = "true";
      setTimeout(() => { delete row.dataset.attention; }, 2600);
    }));
    return true;
  }
  const noAlternative = (outcome: AutoResult) => {
    const moved = showFirstNeed();
    return {
      text: t("바꿀 수 있는 대체 일정이 없어요", "No alternative fits"),
      sub: moved ? t("직접 고쳐야 하는 곳으로 옮겼어요 · 이유를 읽고 수정해 주세요", "Moved to what needs your fix · read why and edit it")
        : outcome.kept ? t("고정한 일정이거나 시간이 맞는 후보가 없어요", "Locked, or no alternative fits the time") : undefined,
    };
  };
  /**
   * ★`[2026-10-03]` 「전체 자동 추천」 (the button, and one more push past the end of the list) only SHOWS the plan as it would be: the dry run of the server saves nothing.
   * ★`[2026-10-04]` It stands under the plan as it is, and the list scrolls on into it.
   */
  function recommendAll() {
    void run(async () => {
      const outcome = await actions.previewRecommendAll!();
      if (!outcome.changes.length) return noAlternative(outcome);
      setRecommended({ count: outcome.changes.length, was: wasOf(outcome) });
      setSide("after");
      return { text: t(`확인이 필요한 일정 ${outcome.changes.length}곳을 바꾼 수정안이에요`, `The proposed plan changes ${outcome.changes.length} stop${outcome.changes.length > 1 ? "s" : ""}`),
        sub: `${changesLine(outcome)} · ${t("아직 저장하지 않았어요 · 위로 올리면 변경 전이에요", "not saved yet · scroll up for the plan as it was")}` };
    }, true);
  }
  // The list scrolls on into the proposed plan the moment it is there: the hint gives way, the line runs on, the changed first day comes up.
  useEffect(() => {
    if (!previewing) return;
    const frame = requestAnimationFrame(() => requestAnimationFrame(() => {
      const box = bodyBox.current, seam = junction.current;
      if (!box || !seam) return;
      const top = seam.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop;
      box.scrollTo({ top: Math.max(0, top - 56), behavior: skipAnimation ? "auto" : "smooth" });
    }));
    return () => cancelAnimationFrame(frame);
  }, [previewing, skipAnimation]);
  /** Which of the two plans is in view: the seam above the middle of the list = the proposed one. */
  function watchSide() {
    if (!previewing) return;
    const box = bodyBox.current, seam = junction.current;
    if (!box || !seam) return;
    const seamAt = seam.getBoundingClientRect().top - box.getBoundingClientRect().top;
    const next = seamAt < box.clientHeight * 0.42 ? "after" : "before";
    setSide((current) => current === next ? current : next);
  }
  /** `[2026-10-03 사용자 지시]` The plan's own name (the header says 「내 여행」 until the customer names it): saved as the server's `trip.title`. */
  function renameTrip(value: string) {
    return run(async () => {
      await actions.editTrip!("title", value);
      return { text: t("계획 이름을 바꿨어요", "Renamed the plan"), sub: value };
    }, true);
  }
  /**
   * 「다시 제출」: the stops marked for deletion are taken out first, then the whole plan is checked again; the stops that were changed have their checks ticked in once more.
   */
  function recheck() {
    void run(async () => {
      for (const id of removed) {
        await actions.remove!(id);
        setRemoved((current) => current.filter((entry) => entry !== id));
        setChanged((current) => Object.fromEntries(Object.entries(current).filter(([key]) => key !== id)));
        setSelected((current) => current === id ? null : current);
      }
      const ids = Object.keys(changed).filter((id) => !removedSet.has(id));
      // A server that does not check the whole plan again (no `recheck`) has still taken the stops out above; what the customer changed was checked when it was saved.
      if (actions.recheck) await actions.recheck(ids);
      if (actions.recheck && ids.length && !skipAnimation) setReplay({ ids, at: 0 });
      else setChanged({});
      return actions.recheck
        ? { text: t("고친 내용을 다시 확인했어요", "Checked the changes again"), sub: t("이대로 진행할 수 있어요 · 오른쪽 버튼이 「여행 등록」으로 바뀌었어요", "You can go ahead · the right button is now 「Register trip」") }
        : { text: t("뺄 일정을 지웠어요", "Took the stops out"), sub: t("이대로 진행할 수 있어요", "You can go ahead") };
    });
  }
  /** 「여행 등록」 pressed while looking at the proposed plan: that plan is saved, and then registered. */
  function registerPreview() {
    void run(async () => {
      await settle();
      registration?.onRegister();
      return null;
    }, true);
  }
  function undo() {
    setToast(null);
    void run(async () => { await actions.undo!(); return { text: t("되돌렸어요", "Undone"), sub: t("바꾸기 전으로 돌렸어요", "Back to how it was") }; });
  }

  // The checks of the stops that were changed come in once more, one at a time, after the plan has been checked again.
  const replayQueue = useMemo(() => !replay ? [] : replay.ids.flatMap((id) => {
    const item = view.items.find((entry) => entry.id === id);
    return item ? item.checks.flatMap((row, index) => isInstantRow(row) ? [] : [{ id, index }]) : [];
  }), [replay, view.items]);
  useEffect(() => {
    if (!replay) return;
    const current = replayQueue[replay.at];
    if (current) {
      setOpen(current.id);
      requestAnimationFrame(() => document.getElementById(`plan-card-${current.id}`)?.scrollIntoView({ block: "nearest", behavior: "smooth" }));
    }
    const timer = setTimeout(() => {
      if (replay.at < replayQueue.length) setReplay({ ...replay, at: replay.at + 1 });
      else { setReplay(null); setChanged({}); }
    }, replay.at < replayQueue.length ? REVEAL_MS : 600);
    return () => clearTimeout(timer);
  }, [replay, replayQueue]);
  const rowsFor = (item: PlanItem): CheckRow[] | null => {
    if (!replay || !replay.ids.includes(item.id)) return null;
    const ticked = new Set(replayQueue.slice(0, replay.at).filter((entry) => entry.id === item.id).map((entry) => entry.index));
    return item.checks.map((row, index) => isInstantRow(row) || ticked.has(index) ? row : { ...row, result: "pending" as const, text: "" });
  };

  /** `[2026-10-03 사용자]` The list can be dragged to any height by its handle (or its head), not only the three presets. */
  const sheetLimits = () => ({ min: SHEET_MIN, max: Math.max(180, (checkingBox.current?.clientHeight ?? 600) - 64) });
  const sheetHeight = () => sheetBox.current?.getBoundingClientRect().height ?? 0;
  function grabSheet(event: PointerEvent<HTMLElement>) {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    // ★A press on a button or field inside the head (the counts, …) is that control's: capturing the pointer here sent its click to the head.
    const control = (event.target as HTMLElement).closest("button, a, input, select, textarea");
    if (control && control !== event.currentTarget) return;
    justDragged.current = false;
    grab.current = { y: event.clientY, height: sheetHeight(), moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function dragSheet(event: PointerEvent<HTMLElement>) {
    const held = grab.current;
    if (!held) return;
    const up = held.y - event.clientY;
    if (!held.moved && Math.abs(up) < 6) return;
    held.moved = true;
    setDragging(true);
    const { min, max } = sheetLimits();
    setCustom(Math.round(Math.min(max, Math.max(min, held.height + up))));
  }
  function dropSheet() {
    if (grab.current?.moved) justDragged.current = true;          // the click that ends a drag is not a press of the handle
    grab.current = null;
    setDragging(false);
  }
  function cycleSheet() {
    if (justDragged.current) { justDragged.current = false; return; }
    if (custom !== null) { setCustom(null); setSheet("half"); return; }
    setSheet((current) => SHEETS[(SHEETS.indexOf(current) + 1) % SHEETS.length]);
  }
  function nudgeSheet(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
    event.preventDefault();
    const { min, max } = sheetLimits();
    setCustom(Math.round(Math.min(max, Math.max(min, (custom ?? sheetHeight()) + (event.key === "ArrowUp" ? 40 : -40)))));
  }

  // The counts in the head, and the filters they switch.
  const needCount = needsLeft(shown, removedSet).total;
  const changedMap: Record<string, string> = previewing && side === "after" && recommended ? { ...changed, ...recommended.was } : changed;
  const changedCount = Object.keys(changedMap).filter((id) => !removedSet.has(id)).length;
  // The filter ends by itself when nothing is left to show.
  const filtering = done && filter !== null && (filter === "needs" ? needCount > 0 : changedCount > 0);
  // ★`[2026-10-04 사용자 결정]` With more than one day the list shows one day at a time, with a strip of day chips above it (and a swipe sideways to the next or
  //   the previous day); 「전체」 and the filters show every day as before. The map follows the day.
  const dayStrip = done && !changing && days.length > 1;
  const listDay: number | "all" = !dayStrip || dayChoice === "all" || filtering ? "all" : mapDay;
  const dayAt = days.findIndex((day) => day.day === listDay);
  const needsOfDay = (day: number) => timeline(shown, day).filter((entry) => (entry.type === "item" ? entry.item.verdict : entry.move.verdict) === "review"
    && !(entry.type === "item" ? removedSet.has(entry.item.id) : removedSet.has(entry.move.fromId) || removedSet.has(entry.move.toId))).length;
  function goDay(day: number) {
    const to = days.findIndex((entry) => entry.day === day);
    setSlide(dayAt >= 0 && to >= 0 && to !== dayAt ? (to > dayAt ? "next" : "prev") : null);
    setFilter(null);
    setDayChoice(null);
    showDay(day);
    bodyBox.current?.scrollTo({ top: 0 });
  }
  function stepDay(delta: 1 | -1) {
    if (dayAt < 0) return;
    const next = days[dayAt + delta];
    if (next) goDay(next.day);
  }
  function chooseAllDays() { setSlide(null); setFilter(null); setDayChoice("all"); bodyBox.current?.scrollTo({ top: 0 }); }
  /** Sideways swipes on the list move to the next day (left) or the previous (right); mostly-vertical moves are the list's own scrolling. */
  const swipeStart = (event: TouchEvent<HTMLElement>) => { swipe.current = event.touches.length === 1 ? { x: event.touches[0].clientX, y: event.touches[0].clientY } : null; };
  const swipeEnd = (event: TouchEvent<HTMLElement>) => {
    const start = swipe.current;
    swipe.current = null;
    if (!start || listDay === "all") return;
    const dx = event.changedTouches[0].clientX - start.x, dy = event.changedTouches[0].clientY - start.y;
    if (Math.abs(dx) >= 60 && Math.abs(dx) >= Math.abs(dy) * 1.6) stepDay(dx < 0 ? 1 : -1);
  };

  // Pushing on past the end of the list shows the plan with the recommended fixes under it. ★`[2026-10-04 사용자 지시]` At the end of any day (or of the whole list), not only the last.
  const canRecommend = Boolean(actions.previewRecommendAll) && done && !changing && !registered && !recommended && needsLeft(view, removedSet).total > 0;
  const pull = usePullPastEnd(bodyBox, {
    onEnd: canRecommend && !frozen ? recommendAll : undefined,
    onStart: undefined,
  });
  // `[2026-10-03 사용자]` While the check is drawn row by row the list follows the newest row (it stayed at the top while rows were added below).
  const follow = useFollowScroll(bodyBox, newestRow, !done && !changing, view);

  // The change screen's map: the day's other stops greyed, the stop being changed, and its alternatives A, B, C.
  const cards = change ? change.list : [];
  const mapStops: TripStop[] = changing ? changeStops(view, changing, cards) : stopsOf(shown, mapDay);
  const looks: Record<string, PinLook> | undefined = changing ? changeLooks(view, changing, cards)
    : removed.length ? Object.fromEntries(removed.map((id) => [id, { tone: "muted" as const }])) : undefined;
  const mapSelected = changing && change ? (change.index === 0 ? changing.id : `cand-${change.index}`) : selected ?? undefined;
  function onPin(id: string) {
    if (changing && change) {
      const index = id === changing.id ? 0 : id.startsWith("cand-") ? Number(id.slice(5)) : -1;
      if (index >= 0) setChange({ ...change, index });
      return;
    }
    if (done) pick(id, "map");
  }

  // The lines belong to the plan as it is: for the proposed one only those between stops it did not change are still true (a changed place moves its ends).
  const lineShapes = !routes || changing ? null : previewing && side === "after" && recommended
    ? { ...routes, shapes: routes.shapes.filter((shape) => !(shape.fromItemId in recommended.was) && !(shape.toItemId in recommended.was)) } : routes;
  const drawn = visibleShapes(lineShapes?.shapes, mapStops);

  const applyWhy = !changing ? null : !actions.replace ? t("장소 바꾸기는 준비 중이에요", "Changing the place is coming")
    : changing.locked ? t("고정한 일정이라 바꿀 수 없어요 · 잠금을 풀면 수정할 수 있어요", "Locked · unlock it to change it") : frozen;

  /** The rows of a list, for the plan as it is and for the proposed one. */
  const visibleIn = (changedIds: ReadonlySet<string>) => (entry: ReturnType<typeof timeline>[number]) =>
    !filtering || (filter === "needs" ? (entry.type === "item" ? entry.item.verdict : entry.move.verdict) === "review" : entry.type === "item" && changedIds.has(entry.item.id));
  /** What the time editor shows, for the list it is open on. */
  const timeUi = (list: "before" | "after"): RowContext["time"] => {
    const { edit, preview } = timeEdit;
    if (!edit || edit.list !== list || !preview) return null;
    return {
      id: edit.id, start: edit.start, end: edit.end, push: edit.push, busy: timeEdit.busy, problem: preview.problem,
      range: { min: formatHm(preview.range.min), max: formatHm(preview.range.max) }, along: preview.along, count: preview.changes.length,
      setStart: timeEdit.setStart, setEnd: timeEdit.setEnd, setPush: timeEdit.setPush, step: timeEdit.step, apply: () => void timeEdit.apply(), cancel: timeEdit.close, grip: timeEdit.grip,
    };
  };
  const contextFor = (was: Readonly<Record<string, string>>, list: "before" | "after"): RowContext => ({
    done, open: openAt?.list === list ? openAt.id : null, selected, frozen, actions, explain, rechecking: null, changed: new Set(Object.keys(was)), was, removed: removedSet, rowsFor,
    prefix: list === "after" ? "after-" : "",
    onPick: (id) => pick(id, "list", list),
    onToggleMove: (id) => setOpenAt((current) => current?.id === id && current.list === list ? null : { list, id }),
    onChange: (item) => void startChange(item),
    onDelete: markRemoved,
    onRestore: restore,
    onLock: lock,
    onRecommend: recommend,
    time: timeUi(list),
    onOpenTime: (item) => timeEdit.open(item, list),
    timeAdjusted: adjustedIn(list === "after" ? previewView : view),
    onRevertTime: revertTime,
    visible: visibleIn(new Set(Object.keys(was))),
  });
  // The plan as it would be with the time being edited (nothing saved): the editor's list is drawn from it, so the gaps move with the fingers.
  const editing = timeEdit.preview && !timeEdit.preview.problem ? timeEdit.preview.changes : [];
  const listBefore = timeEdit.edit?.list === "before" ? withTimes(view, editing) : view;
  const listAfter = previewView && timeEdit.edit?.list === "after" ? withTimes(previewView, editing) : previewView;
  const contextBefore = contextFor(changed, "before");
  const contextAfter = contextFor({ ...changed, ...(recommended?.was ?? {}) }, "after");
  const heading = (day: PlanDay) => dayHeading(day, language, t);
  const nextDay = typeof listDay === "number" && dayAt >= 0 && dayAt < days.length - 1 && !changing ? days[dayAt + 1] : null;
  const adjustedNow = adjustedIn(previewing && side === "after" ? previewView : view).size;
  const sheetTitle = registered ? t("등록 완료", "Registered") : !done ? t("장소·운영시간 확인", "Places & hours") : previewing && side === "after" ? t("수정안", "Proposed plan") : t("계획 확인", "Plan check");
  const rechecking = view.rechecking ? (() => {
    const order = view.days.flatMap((day) => view.items.filter((item) => item.day === day.day).map((item) => item.id));
    return { at: order.indexOf(view.rechecking) + 1, of: order.length };
  })() : null;

  return <div ref={checkingBox} className={styles.checking} data-sheet={custom !== null ? "custom" : sheet} data-changing={changing ? true : undefined} data-dragging={dragging || undefined} data-compact={compact && done && !changing ? true : undefined}
    style={custom !== null ? { "--sheet-h": `${custom}px` } as CSSProperties : undefined}>
    <div className={styles.map}>
      <TripMap stops={mapStops} dayNumber={mapDay} selectedId={mapSelected} looks={looks} variant="fill" topInset={64} routes={lineShapes} onSelect={onPin} />
    </div>
    {unlocated.length > 0 && <p className={styles.unlocated}>{t("위치 미정", "No location")} · {unlocated.map((item) => item.title).join(", ")}</p>}
    {changing && headerSlot && createPortal(
      <div className={styles.headSearch} data-open={searchOpen || undefined} data-hide-brand>
        <BackButton onBack={endChange} label={t("바꾸기 그만두기", "Stop changing")} />
        <div className={styles.searchField}>
          <Search size={16} strokeWidth={1.8} aria-hidden="true" />
          <input ref={searchInput} type="search" value={query} placeholder={t(`${changing.title} 대신 찾을 장소`, `A place instead of ${changing.title}`)}
            aria-label={t("장소 검색", "Search places")} autoComplete="off" onChange={(event) => setQuery(event.target.value)}
            onFocus={() => setSearchOpen(true)} onBlur={() => setSearchOpen(false)}
            onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); if (query) setQuery(""); else endChange(); } }} />
          {query && <button type="button" className={styles.clear} aria-label={t("검색어 지우기", "Clear the search")} onClick={() => { setQuery(""); searchInput.current?.focus(); }}><X size={12} strokeWidth={2} aria-hidden="true" /></button>}
        </div>
      </div>, headerSlot)}
    {!changing && headerSlot && createPortal(
      <div className={styles.headInfo}>
        {done && view.title
          ? <TripTitle title={view.title} onSave={actions.editTrip && !frozen && !registered ? renameTrip : undefined} />
          : <><h1 className="sr-only">{t("계획을 확인하고 있어요", "Checking your plan")}</h1><HeaderProgress view={view} /></>}
      </div>, headerSlot)}
    <section ref={sheetBox} className={styles.sheet} aria-labelledby={changing ? "plan-change-title" : "plan-check-sheet-title"}>
      {done && <button type="button" className={styles.handle} aria-label={t("목록 높이 바꾸기", "Change the list height")} title={t("눌러서 높이를 바꾸고, 잡고 끌어 원하는 높이로 맞춰요", "Press to change the height, or drag it to any height")}
        onClick={cycleSheet} onPointerDown={grabSheet} onPointerMove={dragSheet} onPointerUp={dropSheet} onPointerCancel={dropSheet} onKeyDown={nudgeSheet}><span aria-hidden="true" /></button>}
      {changing && change
        ? <PlaceChange item={changing} session={change} search={search} explain={explain} applyWhy={applyWhy} candidatesSupported={Boolean(actions.candidates)}
            onIndex={(index) => setChange({ ...change, index })} onApply={(candidate) => replace(changing, { candidate })} onApplyName={(name) => replace(changing, { name })}
            onPick={(candidate) => {
              const at = change.list.findIndex((entry) => entry.id === candidate.id);
              const list = at >= 0 ? change.list : [{ ...candidate, source: "search" as const }, ...change.list];
              setChange({ ...change, list, index: at >= 0 ? at + 1 : 1 }); setQuery("");
            }}
            onSheetFull={() => { setCustom(null); setSheet("full"); }}
            editor={actions.edit && <details className={styles.details} open={details} onToggle={(event) => setDetails(event.currentTarget.open)}>
              <summary>{t("직접 고치기 · 이름·날짜·시각·장소 없음", "Edit directly · name, date, time, no place")}</summary>
              {details && <StopEditor key={changing.id} item={changing} autoFocus={false} onCancel={() => setDetails(false)}
                onSave={async (draft) => {
                  const was = wasText(changing);
                  if (previewing && side === "after") await settle();
                  await actions.edit!(changing.id, draft);
                  markChanged(changing.id, was);
                  leaveRecommended();
                  setChange(null); setDetails(false); setOpen(changing.id); refocus(changing.id, "edit");
                  setToast({ text: t("저장했어요. 서버가 일정을 다시 확인했어요.", "Saved. The server checked the plan again.") });
                }} />}
            </details>} />
        : <>
          <header className={styles.sheetHead} onPointerDown={grabSheet} onPointerMove={dragSheet} onPointerUp={dropSheet} onPointerCancel={dropSheet}>
            <h2 id="plan-check-sheet-title" className={styles.sheetTitle}>{sheetTitle}</h2>
            {done && !registered && adjustedNow > 0 && <button type="button" className={styles.resetTimes} onClick={resetTimes} aria-label={t(`시간 조정 ${adjustedNow}곳 모두 처음으로`, `Put the ${adjustedNow} changed time${adjustedNow > 1 ? "s" : ""} back`)} title={t("바꾼 시간을 모두 처음으로", "Put every changed time back")}><Undo2 size={13} strokeWidth={1.8} aria-hidden="true" />{t("시간 초기화", "Reset times")}</button>}
            <p className={styles.count}>{done
              ? <HeadBadges needs={needCount} changed={changedCount} filter={filtering ? filter : null} onFilter={setFilter} registered={registered} rechecking={rechecking} />
              : countText(view, t)}</p>
          </header>
          {dayStrip && <div className={styles.dayStrip} role="tablist" aria-label={t("일차 고르기", "Choose a day")}
            onKeyDown={(event) => {
              if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
              const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('[role="tab"]'));
              const at = tabs.indexOf(document.activeElement as HTMLElement);
              const next = tabs[at + (event.key === "ArrowRight" ? 1 : -1)];
              if (next) { event.preventDefault(); next.focus(); next.click(); }
            }}>
            <button type="button" role="tab" className={styles.dayChip} aria-selected={listDay === "all"} tabIndex={listDay === "all" ? 0 : -1} onClick={chooseAllDays}>{t("전체", "All")}</button>
            {days.map((day) => {
              const wait = needsOfDay(day.day);
              return <button key={day.day} type="button" role="tab" className={styles.dayChip} aria-selected={listDay === day.day} tabIndex={listDay === day.day ? 0 : -1} onClick={() => goDay(day.day)}>
                {t(`${day.day}일차`, `Day ${day.day}`)}<small>{day.date ? dayLabel(day.date, language) : ""}</small>
                {wait > 0 && <span className={styles.dayBadge} role="img" aria-label={t(`확인 필요 ${wait}곳`, `${wait} to check`)}>{wait}</span>}
              </button>;
            })}
          </div>}
          <div ref={bodyBox} className={styles.sheetBody} {...follow.handlers} onScroll={() => { follow.handlers.onScroll(); watchSide(); }} onTouchStart={swipeStart} onTouchEnd={swipeEnd}>
            {done && tripIssues.length > 0 && <TripIssues issues={tripIssues} onSave={actions.editTrip} />}
            {filtering && <p className={styles.filterNote} role="status">{filter === "changed" ? t("바뀐 곳만 보는 중이에요", "Showing only what changed") : t("확인이 필요한 곳만 보는 중이에요", "Showing only what needs a look")}
              <button type="button" onClick={() => setFilter(null)}>{t("전체 보기", "Show all")}</button></p>}
            <div key={String(listDay)} className={styles.page} data-slide={slide ?? undefined}>
              <DayList view={listBefore} days={days} listDay={listDay} ctx={contextBefore} mapDay={mapDay} onShowDay={showDay} heading={heading} />
            </div>
            {previewing && previewView && <>
              <div ref={junction} className={styles.junction} role="separator" aria-label={t("여기부터 수정안", "The proposed plan starts here")}>
                <span className={styles.time} aria-hidden="true" />
                <span className={styles.rail} aria-hidden="true" />
                <p className={styles.junctionNote}><ChevronsUp size={14} strokeWidth={1.8} aria-hidden="true" />{t("여기부터 수정안 · 계속 올리면 변경 전 일정이에요", "The proposed plan starts here · keep going up for the plan as it was")}</p>
              </div>
              <div className={styles.page} data-proposed>
                <DayList view={listAfter ?? previewView} days={previewView.days.filter((day) => previewView.items.some((item) => item.day === day.day))} listDay={listDay} ctx={contextAfter} mapDay={mapDay} onShowDay={showDay} heading={heading} />
              </div>
            </>}
            {/* ★`[2026-10-03 사용자]` 출처 줄이 「계속 내리면 …」 안내 위에 있어야, 목록 맨 끝에 그 안내가 보여 「내리면 다음이 나온다」가 읽힌다. */}
            {done && view.items.length > 0 && <p className={styles.credit}>{t("장소 정보 출처 : ⓒ한국관광공사 · ", "Place data: ⓒKorea Tourism Organization · ")}<a href={TOUR_API_POLICY_URL} target="_blank" rel="noreferrer">{t("저작권 정책", "Copyright policy")}</a>
              {drawn.length > 0 && <><br />{lineShapes?.attribution}{routeNotes(drawn).map((note) => <span key={note} data-route-note><br />{note}</span>)}</>}</p>}
            {nextDay && <p className={styles.dayHint}>{t(`옆으로 밀면 ${nextDay.day}일차${nextDay.date ? ` ${dayLabel(nextDay.date, language)}` : ""} 일정이 나와요`, `Swipe sideways for day ${nextDay.day}`)}<ChevronsRight size={15} strokeWidth={1.8} aria-hidden="true" /></p>}
            {canRecommend && <Act className={styles.pullHint} why={frozen} explain={explain} onPress={recommendAll} data-edge={pull.edge ?? undefined}
              style={{ "--pull": pull.progress } as CSSProperties}>
              <ChevronsDown size={16} strokeWidth={1.8} aria-hidden="true" />
              <span>{t("계속 내리면 권장 수정안이 반영된 모습을 보여 드려요", "Keep scrolling to see the plan with the recommended fixes")}</span>
              <span className={styles.pullBar} aria-hidden="true"><span /></span>
            </Act>}
            {done && !view.items.length && <p className={styles.empty}>{t("남은 일정이 없어요", "No stops left")}</p>}
            {!done && !follow.following && <button type="button" className={styles.followPill} onClick={follow.resume}><ChevronsDown size={14} strokeWidth={1.8} aria-hidden="true" />{t("확인 중인 곳으로", "Follow the check")}</button>}
          </div>
          {done && <ResultFooter view={shown} registration={registration} frozen={frozen} explain={explain} needsTotal={needCount} pendingRemovals={removed.length}
            previewing={previewing && side === "after"} onAutoAll={actions.previewRecommendAll && recommendAll} onRecheck={actions.recheck || actions.remove ? recheck : undefined} onRegisterPreview={registerPreview} />}
        </>}
    </section>
    <div className={styles.toast} role="status" data-shown={toast ? true : undefined}>
      {toast && <><span className={styles.toastText}>{toast.text}{toast.sub && <small>{toast.sub}</small>}</span>
        {(toast.undo || toast.revert) && <button type="button" className={styles.undo} onClick={toast.revert ?? undo}>{t("되돌리기", "Undo")}</button>}</>}
    </div>
  </div>;
}

function dayHeading(day: { day: number; date: string }, language: Language, t: Translate) {
  return <>{t(`${day.day}일차`, `Day ${day.day}`)}<small>{day.date ? dayLabel(day.date, language) : t("날짜 미정", "date to be set")}</small></>;
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

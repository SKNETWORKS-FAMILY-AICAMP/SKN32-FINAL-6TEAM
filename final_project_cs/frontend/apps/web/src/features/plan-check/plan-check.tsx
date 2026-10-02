"use client";

import { useEffect } from "react";
import { ArrowLeft } from "lucide-react";
import { DeviceFrame } from "@/components/layout/device-frame";
import { TripMap } from "@/features/map";
import type { TripStop } from "@/features/trip/model";
import type { Language, Translate } from "@/lib/i18n";
import { useSettings, useT } from "@/lib/settings";
import { foundCount, progress, STAGES, tally, timeline, type CheckKind, type CheckResult, type CheckRow, type LineFinding, type PlanCheckView, type PlanItem, type PlanMove, type Verdict } from "./model";
import { useReveal } from "./use-reveal";
import styles from "./plan-check.module.css";

export interface PlanCheckProps {
  /** The latest snapshot. The screen paces the changes between snapshots itself (`useReveal`). */
  view: PlanCheckView;
  /** The back arrow — e.g. back to the plan entry. */
  onBack: () => void;
  /** Called once the screen has drawn everything in `view` and held it a moment — e.g. to move on after the last line. */
  onCaughtUp?: () => void;
}

/**
 * The plan check after 「계획 확인하기」: the uploaded lines being read, then the places, hours and moves being checked on
 * a map with a list below, then the result. A phone-sized page of its own, like the start screen. Mockup:
 * `mockups/tripilot-plan-check-streaming.html`, scenario 1.
 */
/** How long the screen stays on what it has drawn before `onCaughtUp` — so the last line read is seen, not skipped. */
const HOLD_MS = 800;

export function PlanCheck({ view: latest, onBack, onCaughtUp }: PlanCheckProps) {
  const { view, settled } = useReveal(latest);
  const t = useT();
  useEffect(() => {
    if (!settled || !onCaughtUp) return;
    const timer = setTimeout(onCaughtUp, HOLD_MS);
    return () => clearTimeout(timer);
  }, [settled, onCaughtUp]);
  return <DeviceFrame>
    <div className={styles.screen} data-stage={view.stage}>
      {view.stage === "received" || view.stage === "reading" ? <Reading view={view} onBack={onBack} /> : <Checking view={view} onBack={onBack} />}
      <p className="sr-only" role="status">{announce(view, t)}</p>
    </div>
  </DeviceFrame>;
}

function BackButton({ onBack }: { onBack: () => void }) {
  const t = useT();
  return <button type="button" className={styles.back} onClick={onBack} aria-label={t("뒤로", "Back")}><ArrowLeft size={20} strokeWidth={1.6} aria-hidden="true" /></button>;
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

/** ③④ The map above, the list of places and moves below. */
function Checking({ view, onBack }: { view: PlanCheckView; onBack: () => void }) {
  const t = useT();
  const { language } = useSettings();
  const done = view.stage === "done";
  // While checking, the map follows the day being checked; once done it goes back to the first day.
  const mapDay = done ? view.days[0]?.day ?? 1 : view.items.at(-1)?.day ?? view.days[0]?.day ?? 1;
  const days = view.days.filter((day) => view.items.some((item) => item.day === day.day));
  // Places the server could not settle have no pin; say so on the map, as the mockup's 「위치 미정」 tag does.
  const unlocated = view.items.filter((item) => item.day === mapDay && item.verdict !== null && !item.coordinates);
  return <div className={styles.checking}>
    <div className={styles.bar}>
      <BackButton onBack={onBack} />
      {done && view.title
        ? <h1 className={styles.barTitle}>{view.title}</h1>
        : <><h1 className="sr-only">{t("계획을 확인하고 있어요", "Checking your plan")}</h1><ProgressBar view={view} small /></>}
    </div>
    <div className={styles.map}>
      <TripMap stops={stopsOf(view, mapDay)} dayNumber={mapDay} onSelect={() => {}} />
      {unlocated.length > 0 && <p className={styles.unlocated}>{t("위치 미정", "No location")} · {unlocated.map((item) => item.title).join(", ")}</p>}
    </div>
    <section className={styles.sheet} aria-labelledby="plan-check-sheet-title">
      <header className={styles.sheetHead}>
        <h2 id="plan-check-sheet-title" className={styles.sheetTitle}>{done ? t("계획 확인", "Plan check") : t("장소·운영시간 확인", "Places & hours")}</h2>
        <p className={styles.count}>{countText(view, t)}</p>
      </header>
      <div className={styles.sheetBody}>{days.map((day) =>
        <section key={day.day} aria-labelledby={`plan-day-${day.day}`}>
          <h3 id={`plan-day-${day.day}`} className={styles.day}>{t(`${day.day}일차`, `Day ${day.day}`)}<small>{dayLabel(day.date, language)}</small></h3>
          <ol className={styles.timeline}>{timeline(view, day.day).map((entry) => entry.type === "item"
            ? <ItemRow key={entry.item.id} item={entry.item} open={!done} />
            : <MoveRow key={entry.move.id} move={entry.move} />)}</ol>
        </section>)}</div>
    </section>
  </div>;
}

function ItemRow({ item, open }: { item: PlanItem; open: boolean }) {
  const t = useT();
  const checking = item.verdict === null;
  return <li className={styles.entry} data-type="item" data-verdict={item.verdict ?? "checking"}>
    <span className={styles.time}>{item.startsAt}</span>
    <span className={styles.rail} aria-hidden="true"><span className={styles.dot} /></span>
    <article className={styles.card} aria-labelledby={`plan-item-${item.id}`} aria-busy={checking}>
      <header className={styles.cardHead}>
        <h4 id={`plan-item-${item.id}`} className={styles.cardTitle}>{item.title}</h4>
        {checking ? <span className={styles.spinner} role="img" aria-label={t("확인하는 중", "Checking")} /> : <VerdictPill verdict={item.verdict!} />}
      </header>
      {open && <Checks rows={item.checks} />}
    </article>
  </li>;
}

function MoveRow({ move }: { move: PlanMove }) {
  const t = useT();
  const checking = move.verdict === null;
  return <li className={styles.entry} data-type="move" data-verdict={move.verdict ?? "checking"}>
    <span className={styles.time}>{!checking && <><b>{move.departAt}</b><small>{t("출발", "leave")}</small></>}</span>
    <span className={styles.rail} aria-hidden="true"><span className={styles.dot} /></span>
    <div className={styles.move}>{checking
      ? <span className={styles.waiting}>{t("이동 경로를 찾는 중…", "Finding the way…")}</span>
      : <><span className={styles.mode}>{move.mode}</span><span className={styles.moveText}>{move.summary}</span><VerdictMark verdict={move.verdict!} /></>}</div>
  </li>;
}

function Checks({ rows }: { rows: CheckRow[] }) {
  const t = useT();
  return <ul className={styles.checks}>{rows.map((row) =>
    <li key={row.kind} className={styles.check} data-result={row.result}>
      <span className={styles.mark} aria-hidden="true">{GLYPH[row.result]}</span>
      <b className={styles.checkKind}>{kindLabel(row.kind, t)}</b>
      <span className={styles.checkText}>{row.result === "pending" ? t("확인하는 중…", "Checking…") : row.text}</span>
      <span className="sr-only">{resultLabel(row.result, t)}</span>
    </li>)}</ul>;
}

function VerdictPill({ verdict }: { verdict: Verdict }) {
  const t = useT();
  return <span className={styles.pill} data-verdict={verdict}>{verdictLabel(verdict, t)}</span>;
}

function VerdictMark({ verdict }: { verdict: Verdict }) {
  const t = useT();
  const result: CheckResult = verdict === "keep" ? "ok" : verdict === "adjusted" ? "filled" : "warn";
  return <span className={styles.mark} data-result={result} role="img" aria-label={verdictLabel(verdict, t)}>{GLYPH[result]}</span>;
}

const GLYPH: Record<CheckResult, string> = { ok: "✓", filled: "✎", warn: "!", bad: "✕", unknown: "–", pending: "" };

function resultLabel(result: CheckResult, t: Translate): string {
  return {
    ok: t("통과", "passed"), filled: t("채움", "filled in"), warn: t("주의", "warning"), bad: t("고쳐야 함", "needs fixing"),
    unknown: t("아직 모름", "not known yet"), pending: t("확인하는 중", "checking"),
  }[result];
}

function kindLabel(kind: CheckKind, t: Translate): string {
  return {
    place: t("장소", "Place"), time: t("시간", "Time"), hours: t("운영시간", "Hours"), closed: t("휴무일", "Closed"),
    route: t("경로", "Route"), mode: t("수단", "Mode"), arrival: t("도착", "Arrival"),
  }[kind];
}

function verdictLabel(verdict: Verdict, t: Translate): string {
  return { keep: t("유지", "Kept"), adjusted: t("조정", "Adjusted"), review: t("확인 필요", "Check") }[verdict];
}

function countText(view: PlanCheckView, t: Translate): string {
  const count = tally(view);
  if (view.stage !== "done") return t(`장소 ${count.placesDone}/${count.places} · 이동 ${count.movesDone}/${count.moves}`, `Places ${count.placesDone}/${count.places} · Moves ${count.movesDone}/${count.moves}`);
  if (!count.placesReview && !count.movesReview) return t("모두 확인했어요", "All checked");
  const parts = [count.placesReview && t(`장소 ${count.placesReview}곳`, `${count.placesReview} place${count.placesReview > 1 ? "s" : ""}`),
    count.movesReview && t(`이동 ${count.movesReview}구간`, `${count.movesReview} move${count.movesReview > 1 ? "s" : ""}`)].filter(Boolean);
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

/** The map's stops for one day. Places without coordinates are passed too: the map says they have no pin. */
function stopsOf(view: PlanCheckView, day: number): TripStop[] {
  const date = view.days.find((entry) => entry.day === day)?.date ?? "";
  return view.items.filter((item) => item.day === day)
    .map((item) => ({ id: item.id, date, time: item.startsAt, title: item.title, booking: "unknown", notes: "", coordinates: item.coordinates }));
}

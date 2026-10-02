"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { ChevronLeft } from "lucide-react";
import { SettingsMenu } from "@/components/layout/settings-menu";
import type { Review, ReviewItem, ReviewMove } from "@/lib/live/intake-review";
import { useT } from "@/lib/settings";
import { ConceptMap } from "./concept-map";
import { Mark } from "./marks";
import { MoveRow, type MoveRowProps } from "./move-row";
import { PlaceRow, type PlaceRowProps } from "./place-card";
import { dayHeading, headSummary, projectDay, timeline, type MarkTone } from "./review-model";
import styles from "./review-screen.module.css";
import sheetStyles from "./review-sheet.module.css";

type SheetSize = "peek" | "half" | "full";
const NEXT_SIZE: Record<SheetSize, SheetSize> = { peek: "half", half: "full", full: "peek" };
/** The stops that were already there when the check began come in one after another, this far apart (mockup `T.item`). */
const STAGGER_MS = 450;

const dayKeyOf = (item: Pick<ReviewItem, "day" | "date">) => `${item.day ?? "none"}|${item.date ?? ""}`;

/** While the server is still checking (mockup screen ③): the thin progress line instead of the trip's name, cards open. */
export interface StreamingView {
  /** The thin progress line for the bar over the map. */
  bar: ReactNode;
  title: string;
  count: { tone: MarkTone; text: string; spinning: boolean };
  /** Stops whose check lines are still coming in. */
  checking: ReadonlySet<string>;
  /** Said at the top of the list while it holds — the line dropped, or the model is slow. */
  notice?: { tone: "info" | "warn"; text: string } | null;
}

export interface ReviewScreenProps {
  title: string;
  review: Pick<Review, "items" | "moves" | "needs" | "ready">;
  backHref: string;
  backLabel: string;
  streaming?: StreamingView;
  /** Replaces the sheet's heading line (e.g. 「등록 완료」). */
  headline?: { title: string; tone: MarkTone; text: string };
  /** In the sheet above the list: what the customer must still settle (the date, the party size …). */
  notices?: ReactNode;
  /** In the sheet below the list. */
  below?: ReactNode;
  /** The buttons at the bottom of the sheet. */
  foot?: ReactNode;
  /** Extra things for one stop's row (the lock, edit and delete buttons, the card's own buttons). */
  rowProps?: (item: ReviewItem) => Partial<PlaceRowProps>;
  /** Extra things for one leg (it is being measured again). */
  moveProps?: (move: ReviewMove) => Partial<MoveRowProps>;
  /** Inside the frame, above everything: the toast, the question before a delete. */
  overlay?: ReactNode;
  /** A question is open: the screen behind it cannot be reached by keyboard or screen reader. */
  modal?: boolean;
}

/**
 * The check screen of the mockup: the map behind, the thin bar floating over it, and the sheet below with the day's
 * stops as cards (closed: name and status; open: the server's check lines) and the legs between them. A card and its pin
 * (or a leg and its line on the map) light up together. While the server is still checking, the cards are open and fill
 * with their lines one by one; when it is done they fold and the bar shows the trip's name.
 */
export function ReviewScreen({ title, review, backHref, backLabel, streaming, headline, notices, below, foot, rowProps, moveProps, overlay, modal = false }: ReviewScreenProps) {
  const t = useT();
  const entries = timeline(review);
  const dayKeys = [...new Set(review.items.map(dayKeyOf))];
  const [selected, setSelected] = useState<string | null>(null);
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set());
  const [pickedDay, setPickedDay] = useState<string | null>(null);
  const [size, setSize] = useState<SheetSize>("half");
  const [initial] = useState(() => entries.filter((entry) => entry.kind === "item").map((entry) => entry.key));
  const body = useRef<HTMLDivElement>(null);
  const reveal = useRef<string | null>(null);

  // The map shows one day; before the customer picks one it follows the selected stop, else the first day.
  const selectedItem = review.items.find((item) => item.id === selected) ?? review.items.find((item) => selected?.startsWith(`${item.id}:`));
  const dayKey = pickedDay && dayKeys.includes(pickedDay) ? pickedDay : selectedItem ? dayKeyOf(selectedItem) : dayKeys[0] ?? "";
  const dayItems = review.items.filter((item) => dayKeyOf(item) === dayKey);
  const summary = streaming ? { title: streaming.title, ...streaming.count }
    : headline ? { ...headline, spinning: false }
    : { title: t("계획 확인", "Check your plan"), ...headSummary(review, t), spinning: false };

  // Bring the chosen card into view once it has opened (a DOM-only side effect — no state is set here). ★Only the list scrolls,
  // and only up and down: `scrollIntoView` also moved the frame sideways (found 2026-10-03 on the real server).
  useEffect(() => {
    const key = reveal.current;
    const box = body.current;
    if (!key || !box) return;
    reveal.current = null;
    const show = () => {
      const target = [...box.querySelectorAll<HTMLElement>("[data-key]")].find((element) => element.dataset.key === key);
      if (!target) return;
      const area = box.getBoundingClientRect(), at = target.getBoundingClientRect();
      let move = 0;
      if (at.top < area.top + 6) move = at.top - area.top - 6;
      else if (at.bottom > area.bottom - 6) move = Math.min(at.top - area.top - 6, at.bottom - area.bottom + 6);
      if (move) box.scrollBy({ top: move, behavior: "smooth" });
    };
    show();
    const later = setTimeout(show, 450);               // again once the card has finished opening
    return () => clearTimeout(later);
  });

  // While it streams, the newest card stays in view (mockup `scrollSheet`).
  const streamed = streaming ? entries.length : 0;
  useEffect(() => {
    if (!streamed || !body.current) return;
    body.current.scrollTo({ top: body.current.scrollHeight, behavior: "smooth" });
  }, [streamed]);

  const choose = (key: string, itemId: string, toggle: boolean) => {
    const item = review.items.find((entry) => entry.id === itemId);
    setSelected(key);
    if (item) setPickedDay(dayKeyOf(item));
    setOpen((current) => {
      const next = new Set(current);
      if (toggle && next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
    setSize((current) => current === "peek" ? "half" : current);
    reveal.current = key;
  };

  return <div className={styles.root} data-sheet={size} data-streaming={streaming ? "" : undefined}>
    <div className={styles.behind} inert={modal}>
    <ConceptMap items={dayItems} spots={projectDay(dayItems)} selected={selected} onSelect={(id) => choose(id, id, false)} />
    <div className={styles.bar}>
      <Link href={backHref} className={styles.back} aria-label={backLabel}><ChevronLeft size={22} strokeWidth={1.8} aria-hidden="true" /></Link>
      {streaming ? <div className={styles.barProgress}>{streaming.bar}</div> : <h1 className={styles.barTitle}>{title}</h1>}
      <span className={styles.menu}><SettingsMenu /></span>
    </div>
    <section className={sheetStyles.sheet} aria-label={t("계획 확인", "Check your plan")}>
      <button type="button" className={sheetStyles.handle} aria-label={t("목록 높이 바꾸기", "Change the list height")} onClick={() => setSize(NEXT_SIZE[size])}><i /></button>
      <div className={sheetStyles.head}>
        <b className={sheetStyles.title}>{summary.title}</b>
        <span className={sheetStyles.count} role="status">{summary.spinning ? <i className={sheetStyles.spinner} aria-hidden="true" /> : <Mark tone={summary.tone} />}<span>{summary.text}</span></span>
      </div>
      <div className={sheetStyles.body} ref={body} tabIndex={-1} data-review-list="">
        {streaming?.notice && <p className={`${styles.notice} ${streaming.notice.tone === "info" ? styles.notice_info : ""}`} role="status">{streaming.notice.text}</p>}
        {notices && <div className={styles.notices}>{notices}</div>}
        {entries.length === 0
          ? <p className={sheetStyles.empty}>{streaming ? t("읽은 일정을 기다리는 중이에요…", "Waiting for the stops that were read…") : t("읽은 일정이 없어요.", "No stops were read.")}</p>
          : entries.map((entry) => {
            if (entry.kind === "day") {
              const heading = dayHeading(entry.day, entry.date, t);
              const key = `${entry.day ?? "none"}|${entry.date ?? ""}`;
              return <h2 key={entry.key} className={sheetStyles.dh}><button type="button" aria-pressed={key === dayKey} onClick={() => setPickedDay(key)}>{heading.title}{heading.sub && <small>{heading.sub}</small>}</button></h2>;
            }
            if (entry.kind === "move") {
              const key = `${entry.move.from}:${entry.move.to}`;
              return <MoveRow key={entry.key} move={entry.move} open={open.has(key)} selected={selected === key} fresh={Boolean(streaming)} onToggle={() => choose(key, entry.move.from, true)} {...moveProps?.(entry.move)} />;
            }
            const first = initial.indexOf(entry.key);
            return <PlaceRow key={entry.key} item={entry.item} last={entry.last} selected={selected === entry.item.id}
              open={streaming ? true : open.has(entry.item.id)} checking={streaming?.checking.has(entry.item.id) ?? false}
              fresh={streaming ? { delayMs: first >= 0 ? first * STAGGER_MS : 0 } : undefined}
              onToggle={() => choose(entry.item.id, entry.item.id, true)} {...rowProps?.(entry.item)} />;
          })}
        {below}
      </div>
      {foot && <div className={sheetStyles.foot}>{foot}</div>}
    </section>
    </div>
    {overlay}
  </div>;
}

"use client";

import Image from "next/image";
import { ChevronRight, Search, X } from "lucide-react";
import { Fragment, useEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type MouseEvent, type PointerEvent, type ReactNode } from "react";
import { ButtonLink } from "@/components/ui";
import { useGuardianShown } from "@/features/guardian/availability";
import { guideImage, guideSteps, SHOT_H, SHOT_W, type GuideStep } from "@/features/intro/guide-steps";
import { useRiskPanelShown } from "@/features/risk/availability";
import type { Language } from "@/lib/i18n";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import { COMPARE, FAQ, FAQ_CATEGORIES, SCOPE, SCREENS, type FaqCategory, type HelpScreen, type Pair, type ScreenId } from "./content";
import { faqCount, openingOf, ruleOf, searchHelp, shown, stepDetail, type Features, type HelpTab, type HelpTarget } from "./model";
import styles from "./help.module.css";

/** The app's words in 「」 (English “ ”) stand out, so the button to look for is easy to find. */
function Rich({ text }: { text: string }) {
  return text.split(/(「[^」]+」|“[^”]+”)/).map((part, index) => /^[「“]/.test(part) ? <b key={index}>{part}</b> : <Fragment key={index}>{part}</Fragment>);
}

/** A small picture of the part of the step's capture the intro lifts out (`area`), cut to fill 84×108. */
function thumbStyle(language: Language, { shot, area: [x0, y0, x1, y1] }: GuideStep): CSSProperties {
  const W = 84, H = 108, width = x1 - x0, height = y1 - y0, scale = Math.max(W / width, H / height);
  return { backgroundImage: `url(${guideImage(language, shot)})`, backgroundSize: `${SHOT_W * scale}px auto`,
    backgroundPosition: `${-x0 * scale + (W - width * scale) / 2}px ${-y0 * scale + (H - height * scale) / 2}px` };
}

/**
 * Chip rows scroll sideways; on a PC the mouse can drag them too (fingers and trackpads scroll by themselves). A drag of more than 5px is not a press —
 * `[2026-10-22 사용자 지적]` and the row keeps where it was dragged to when a chip is chosen (React keeps the row; nothing scrolls it back).
 */
function useDragRow() {
  const drag = useRef<{ x: number; left: number } | null>(null);
  const moved = useRef(false);
  const end = () => { drag.current = null; };
  return {
    onPointerDown: (event: PointerEvent<HTMLDivElement>) => {
      if (event.pointerType !== "mouse" || event.button !== 0) return;
      drag.current = { x: event.clientX, left: event.currentTarget.scrollLeft };
      moved.current = false;
    },
    onPointerMove: (event: PointerEvent<HTMLDivElement>) => {
      if (!drag.current) return;
      const distance = event.clientX - drag.current.x;
      if (Math.abs(distance) > 5) moved.current = true;
      if (moved.current) event.currentTarget.scrollLeft = drag.current.left - distance;
    },
    onPointerUp: end, onPointerLeave: end,
    onClickCapture: (event: MouseEvent<HTMLDivElement>) => { if (moved.current) { moved.current = false; event.preventDefault(); event.stopPropagation(); } },
  };
}

/** Brings the chosen chip into its row when it is outside it (a jump from another tab), without scrolling the page. */
function showChosen(row: HTMLElement | null) {
  const chosen = row?.querySelector<HTMLElement>('[aria-selected="true"], [aria-pressed="true"]');
  if (!row || !chosen) return;
  const left = chosen.offsetLeft - row.offsetLeft, right = left + chosen.offsetWidth;
  if (left < row.scrollLeft) row.scrollLeft = left - 8;
  else if (right > row.scrollLeft + row.clientWidth) row.scrollLeft = right - row.clientWidth + 8;
}

const TABS: readonly (readonly [HelpTab, Pair])[] = [["start", ["처음 쓰기", "Getting started"]], ["screens", ["화면별 기능", "Screen by screen"]], ["faq", ["자주 묻는 질문", "FAQ"]]];

/**
 * `[2026-10-22 사용자 결정 — ST4F-717]` 「이용 방법」 (`/help`): getting started (the intro's seven steps · guest or signed in), every screen's buttons on its
 * capture, and common questions — with one search over all three and the way to the inquiries at the end. Opened from the menu, the (?) next to the
 * language globe and the inquiries. The intro's second page stays as it is. Nothing here asks the server except the operator's switches (`/v1/web/features`):
 * what is switched off is not explained (`content.ts` `needs`). Mockup: `mockups/guguroute-help-center-2026-10-22.html`.
 */
export function HelpPage({ tab: tabParam, screen: screenParam }: { tab?: string; screen?: string }) {
  const t = useT();
  const { language } = useSettings();
  const pick = (pair: Pair) => t(...pair);
  const on: Features = { guardian: useGuardianShown() !== false, riskPanel: useRiskPanelShown() };
  const opening = openingOf(tabParam, screenParam);
  const [tab, setTab] = useState<HelpTab>(opening.tab);
  const [screenId, setScreenId] = useState<ScreenId>(opening.screen);
  const [point, setPoint] = useState<number | null>(null);
  const [category, setCategory] = useState<FaqCategory | "all">("all");
  const [openFaq, setOpenFaq] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const reveal = useRef<string | null>(null);
  const screenRow = useRef<HTMLDivElement>(null);
  const screenDrag = useDragRow(), categoryDrag = useDragRow();

  // After a jump (a search result · a step's 「이 화면 기능 보기」 · a related question), scroll what it points at under the sticky tabs.
  useEffect(() => {
    if (!reveal.current) return;
    showChosen(screenRow.current);
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.getElementById(reveal.current)?.scrollIntoView({ block: "start", behavior: reduced ? "instant" : "smooth" });
    reveal.current = null;
  });

  function go(target: HelpTarget) {
    setQuery("");
    setTab(target.tab);
    if (target.tab === "start") reveal.current = `help-step-${target.step}`;
    else if (target.tab === "screens") { setScreenId(target.screen); setPoint(target.point ?? null); reveal.current = target.point === undefined ? "help-screen" : `help-point-${target.point}`; }
    else { setCategory("all"); setOpenFaq(target.faq); reveal.current = `help-faq-${target.faq}`; }
  }

  function tabKeys(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const at = TABS.findIndex(([key]) => key === tab);
    const next = TABS[(at + (event.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length][0];
    event.preventDefault();
    setTab(next);
    requestAnimationFrame(() => document.getElementById(`help-tab-${next}`)?.focus());
  }

  const hits = searchHelp(query, pick, on);
  const screen = SCREENS.find((entry) => entry.id === screenId) ?? SCREENS[0];

  const startPanel = <>
    <div className={styles.scope}><small>A LITTLE MORE YOU</small><strong>{pick(SCOPE.badge)}</strong><p>{pick(SCOPE.note)}</p></div>
    <ol className={styles.steps}>{guideSteps.map((step, index) => (
      <li key={step.shot} id={`help-step-${index + 1}`} className={styles.step}>
        <span className={styles.thumb} style={thumbStyle(language, step)} role="img" aria-label={`${t("앱 화면", "App screen")}: ${pick(step.title)}`} />
        <div className={styles.stepBody}>
          <span className={styles.stepNo}>0{index + 1}</span>
          <h3>{pick(step.title)}</h3>
          <p>{pick(stepDetail(step, on))}</p>
          <span className={styles.stepChip}>{pick(step.chip)}</span>
          <button type="button" className={styles.link} onClick={() => go({ tab: "screens", screen: SCREENS[index].id })}>{t("이 화면 기능 보기", "See this screen")}<ChevronRight size={16} aria-hidden="true" /></button>
        </div>
      </li>
    ))}</ol>
    <h2 className={styles.sectionTitle}>{t("로그인하면 달라지는 것", "What signing in changes")}</h2>
    <div className={styles.compare}>
      <div><span className={`${styles.tag} ${styles.guestTag}`}>{t("게스트 · 이 기기에서만", "Guest · this device only")}</span><h3>{t("로그인 없이", "Without signing in")}</h3>
        <ul>{COMPARE.guest.map((line) => <li key={line[0]}><Rich text={pick(line)} /></li>)}</ul></div>
      <div><span className={styles.tag}>{t("로그인됨", "Signed in")}</span><h3>{t("로그인하면", "Signed in")}</h3>
        <ul>{COMPARE.member.map((line) => <li key={line[0]}><Rich text={pick(line)} /></li>)}</ul></div>
    </div>
    <ButtonLink href={routes.newTrip} variant="primary">{t("여행 등록하기", "Add my trip")}</ButtonLink>
  </>;

  const screensPanel = <>
    <div ref={screenRow} className={styles.chips} role="tablist" aria-label={t("화면 고르기", "Choose a screen")} {...screenDrag}>{SCREENS.map((entry) => (
      <button key={entry.id} type="button" role="tab" className={styles.chip} aria-selected={entry.id === screen.id} onClick={() => { setScreenId(entry.id); setPoint(null); }}>{pick(entry.name)}</button>
    ))}</div>
    <ScreenCard screen={screen} on={on} point={point} onPoint={setPoint} onFaq={(faq) => go({ tab: "faq", faq })} />
  </>;

  const faqPanel = <>
    <div className={styles.chips} aria-label={t("질문 분류", "Question topics")} {...categoryDrag}>{FAQ_CATEGORIES.map(([key, name]) => (
      <button key={key} type="button" className={styles.chip} aria-pressed={category === key} onClick={() => { setCategory(key); setOpenFaq(null); }}>{pick(name)}<small>{faqCount(key, on)}</small></button>
    ))}</div>
    <div className={styles.faq}>{shown(FAQ, on).filter((faq) => category === "all" || faq.category === category).map((faq) => (
      <details key={faq.id} id={`help-faq-${faq.id}`} open={openFaq === faq.id} onToggle={(event) => { const opened = event.currentTarget.open; setOpenFaq((current) => opened ? faq.id : current === faq.id ? null : current); }}>
        <summary>{pick(faq.q)}</summary>
        <div className={styles.answer}>
          {category === "all" && <span className={styles.topic}>{pick(FAQ_CATEGORIES.find(([key]) => key === faq.category)![1])}</span>}
          <p><Rich text={pick(faq.a)} /></p>
          {faq.screens.length > 0 && <div className={styles.answerLinks}>{faq.screens.map((id) => (
            <button key={id} type="button" className={styles.link} onClick={() => go({ tab: "screens", screen: id })}>{t(`${pick(SCREENS.find((entry) => entry.id === id)!.name)} 화면 보기`, `See ${pick(SCREENS.find((entry) => entry.id === id)!.name)}`)}<ChevronRight size={16} aria-hidden="true" /></button>
          ))}</div>}
        </div>
      </details>
    ))}</div>
  </>;

  const panels: Record<HelpTab, ReactNode> = { start: startPanel, screens: screensPanel, faq: faqPanel };
  return <div className={styles.page}>
    <header className={styles.head}><h1>{t("이용 방법", "How to use")}</h1><p>{t("처음 쓰는 방법부터 화면별 기능, 자주 묻는 질문까지 모았어요.", "From getting started to every screen and common questions.")}</p></header>
    <label className={styles.search}>
      <Search size={18} aria-hidden="true" />
      <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("궁금한 기능이나 질문을 찾아보세요", "Search features and questions")} aria-label={t("이용 방법에서 찾기", "Search how to use")} autoComplete="off" />
      {query && <button type="button" className={styles.clear} onClick={() => setQuery("")} aria-label={t("지우기", "Clear")}><X size={18} aria-hidden="true" /></button>}
    </label>
    {query.trim() ? <section className={styles.results} aria-label={t("찾은 내용", "Results")}>
      <p className={styles.muted} role="status">{hits.length ? t(`찾은 내용 ${hits.length}개`, `${hits.length} found`) : <>{t(`「${query.trim()}」에 맞는 내용이 없어요. 아래 「문의 작성」으로 물어봐 주세요.`, `Nothing matches “${query.trim()}”. Ask us with “Write an inquiry” below.`)}</>}</p>
      {hits.slice(0, 30).map((hit, index) => (
        <button key={index} type="button" className={styles.result} onClick={() => go(hit.target)}>
          <small>{hit.kind === "step" ? t("처음 쓰기", "Getting started") : hit.kind === "faq" ? t("자주 묻는 질문", "FAQ") : `${t("화면별 기능", "Screen by screen")} · ${pick(hit.group!)}`}</small>
          <strong>{hit.title.replace(/[「」“”]/g, "")}</strong><span>{hit.body}</span>
        </button>
      ))}
    </section> : <>
      <div className={styles.tabs} role="tablist" aria-label={t("이용 방법 구분", "Parts of how to use")} onKeyDown={tabKeys}>{TABS.map(([key, name]) => (
        <button key={key} id={`help-tab-${key}`} type="button" role="tab" aria-selected={tab === key} aria-controls="help-panel" tabIndex={tab === key ? 0 : -1} onClick={() => setTab(key)}>{pick(name)}</button>
      ))}</div>
      <div id="help-panel" role="tabpanel" aria-labelledby={`help-tab-${tab}`} className={styles.panel}>{panels[tab]}</div>
    </>}
    <section className={styles.ask} aria-labelledby="help-ask-title">
      <h2 id="help-ask-title">{t("원하는 답을 찾지 못했나요?", "Didn't find your answer?")}</h2>
      <p>{t("문의함에 남겨 주시면 답변을 드려요. 일정은 대신 고쳐 드리지 않으니, 일정 변경은 여행 화면의 채팅이나 「일정 수정」에서 해 주세요.", "Leave it in Inquiries and we will answer. We do not change your trip for you — use the chat or “Edit itinerary” on the trip screen.")}</p>
      <div className={styles.askActions}><ButtonLink href={routes.notices}>{t("공지사항", "Notices")}</ButtonLink><ButtonLink href={routes.supportNew} variant="primary">{t("문의 작성", "Write an inquiry")}</ButtonLink></div>
    </section>
  </div>;
}

/** One screen: where it opens, its capture with numbered points (or a small board for screens without one), what each number does, and related questions. */
function ScreenCard({ screen, on, point, onPoint, onFaq }: { screen: HelpScreen; on: Features; point: number | null; onPoint: (point: number | null) => void; onFaq: (faq: string) => void }) {
  const t = useT();
  const { language } = useSettings();
  const pick = (pair: Pair) => t(...pair);
  const points = shown(screen.points, on), more = shown(screen.more, on);
  const faqs = shown(FAQ, on).filter((faq) => faq.screens.includes(screen.id));
  const toggle = (index: number) => onPoint(point === index ? null : index);
  const marker = (index: number, className: string, style?: CSSProperties) => <button type="button" className={className} style={style} aria-pressed={point === index}
    aria-label={`${index + 1}. ${pick(points[index].label).replace(/[「」“”]/g, "")}`} onClick={() => { toggle(index); requestAnimationFrame(() => document.getElementById(`help-point-${index}`)?.scrollIntoView({ block: "nearest" })); }}>{index + 1}</button>;

  return <article id="help-screen" className={styles.card} aria-labelledby="help-screen-title">
    <div className={styles.screenHead}>
      <h3 id="help-screen-title">{pick(screen.name)}</h3>
      <p className={styles.where}><b>{t("여는 곳", "Where")}</b><span><Rich text={pick(screen.where)} /></span></p>
      {screen.note && <p className={styles.where}><b>{t("참고", "Note")}</b><span><Rich text={pick(screen.note)} /></span></p>}
    </div>
    <div className={styles.shotWrap}>{screen.shot
      ? <div className={styles.shot}>
          <Image src={guideImage(language, screen.shot)} alt={`${t("앱 화면", "App screen")}: ${pick(screen.name)}`} width={SHOT_W} height={SHOT_H} sizes="236px" draggable={false} />
          {points.map((entry, index) => entry.at && <Fragment key={index}>{marker(index, styles.spot, { left: `${entry.at[0] / SHOT_W * 100}%`, top: `${entry.at[1] / SHOT_H * 100}%` })}</Fragment>)}
        </div>
      : <div className={styles.board}>{screen.board?.map((row) => (
          <div key={row.title[0]} className={styles.boardRow}><span><strong>{pick(row.title)}</strong><small>{pick(row.note)}</small></span>{row.point !== undefined && row.point < points.length && marker(row.point, styles.boardSpot)}</div>
        ))}</div>}
    </div>
    <ol className={styles.points}>{points.map((entry, index) => {
      const rule = ruleOf(entry, on);
      return <li key={index} id={`help-point-${index}`} className={styles.point} aria-current={point === index || undefined} onClick={() => toggle(index)}>
        <span className={styles.number} aria-hidden="true">{index + 1}</span>
        <div><strong><Rich text={pick(entry.label)} /></strong><p><Rich text={pick(entry.desc)} /></p>{rule && <p className={styles.rule}><Rich text={pick(rule)} /></p>}</div>
      </li>;
    })}</ol>
    {more.length > 0 && <div className={styles.related}><h4>{t("이 화면의 다른 기능", "More on this screen")}</h4>
      <ul className={styles.more}>{more.map((entry) => <li key={entry.label[0]}><strong><Rich text={pick(entry.label)} /></strong> — <Rich text={pick(entry.desc)} /></li>)}</ul></div>}
    {faqs.length > 0 && <div className={styles.related}><h4>{t("이 화면에 대해 자주 묻는 질문", "Questions about this screen")}</h4>
      {faqs.map((faq) => <button key={faq.id} type="button" onClick={() => onFaq(faq.id)}>Q. {pick(faq.q)}</button>)}</div>}
  </article>;
}

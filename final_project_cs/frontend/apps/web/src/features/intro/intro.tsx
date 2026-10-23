"use client";

import Image, { getImageProps } from "next/image";
import { ChevronsDown, Plane } from "lucide-react";
import { useRouter } from "next/navigation";
import { Fragment, useCallback, useEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import { DeviceFrame } from "@/components/layout/device-frame";
import { HelpButton } from "@/components/ui/help-button";
import { LanguageButton } from "@/components/ui/language-picker";
import { useOnboarding } from "@/features/onboarding/onboarding-state";
import { RecentTrips } from "@/features/trip/trip-list";
import type { Language } from "@/lib/i18n";
import { routes } from "@/lib/routes";
import { useSettings } from "@/lib/settings";
import { useDocumentTitle } from "@/lib/use-document-title";
import { guideImage, guideSteps, SHOT_H, SHOT_W } from "./guide-steps";
import styles from "./intro.module.css";

const copy: Record<Language, Record<string, string>> = {
  en: {
    title: "GuguRoute · Your next journey",
    intro: "Let’s check your\nSeoul trip plan.",
    introDescription: "Upload your plan and we check places, opening hours and travel between them.\nSigned in, we keep watching it during the trip.",
    badge: "Seoul · up to 7 days · up to 4 people", badgeCta: "Add my trip",
    how: "How to use it",
    guide: "How to use GuguRoute", shot: "App screen", swipe: "Swipe to see each step", prevStep: "Previous step", nextStep: "Next step",
    start: "Your next journey\nstarts right here.",
    startDescription: "The places you dream of. The moments you love.\nTell us what your next trip looks like.",
    taste: "Add plan", trip: "Start trip", cta: "Start my itinerary",
    actionNote: "Review the terms, then add your plan.",
    actionNoteDone: "You have agreed to the terms. The preference questions are in the menu.",
    scrollHint: "Scroll down to explore", next: "Next screen", toEnd: "Skip to the end",
    pages: "GuguRoute introduction. Scroll down to move to the next screen.", navigation: "Introduction screens",
    label0: "Introduction", label1: "How it works", label2: "Start your itinerary",
    howEyebrow: "HOW IT WORKS", ticketLabel: "YOUR NEXT JOURNEY", ticketPartner: "TRAVEL PARTNER",
  },
  ko: {
    title: "구구루트 · 당신다운 여행의 시작",
    intro: "서울 여행 일정을\n함께 확인해요.",
    introDescription: "준비한 일정을 올리면 장소 · 운영시간 · 이동을 확인해요.\n로그인하면 여행 중에도 일정을 지켜봐요.",
    badge: "서울 · 최대 7일 · 4명까지", badgeCta: "여행 등록하기",
    how: "이렇게 사용할 수 있어요",
    guide: "구구루트 이용 방법", shot: "앱 화면", swipe: "옆으로 넘겨 단계별로 확인하세요", prevStep: "이전 단계", nextStep: "다음 단계",
    start: "다음 여행의 첫걸음,\n여기서 시작해요.",
    startDescription: "가고 싶은 곳, 좋아하는 순간.\n당신의 여행 이야기를 들려주세요.",
    taste: "계획 담기", trip: "여행 시작", cta: "내 일정 시작하기",
    actionNote: "약관 확인부터 함께할게요.",
    actionNoteDone: "약관에 동의했어요. 취향 설문은 메뉴에서 할 수 있어요.",
    scrollHint: "아래로 넘겨 보세요", next: "다음 화면", toEnd: "맨 아래로 넘어가기",
    pages: "구구루트 서비스 소개. 아래로 넘기면 다음 화면으로 가요.", navigation: "소개 화면 이동",
    label0: "서비스 소개", label1: "이용 방법", label2: "일정 시작",
    howEyebrow: "이용 방법", ticketLabel: "다음 여행", ticketPartner: "구구루트",
  },
};

/** Optimized background for all three pages; CSS cannot use next/image directly. */
const { props: { srcSet } } = getImageProps({ alt: "", src: "/images/tripilot-home-03-journey.png", width: 1672, height: 941, quality: 75 });
const imageSet = (set: string | undefined) => `image-set(${(set ?? "").split(", ").map((entry) => { const [url, density] = entry.split(" "); return `url("${url}") ${density}`; }).join(", ")})`;
const background = imageSet(srcSet);
/** `[2026-10-17 사용자 결정]` The dark theme's version of the same picture: night, lights along the river, the route lit like lanterns. */
const { props: { srcSet: nightSrcSet } } = getImageProps({ alt: "", src: "/images/tripilot-home-03-journey-night.png", width: 1672, height: 941, quality: 75 });
const nightBackground = imageSet(nightSrcSet);

/** How-it-works slides — the steps, their pictures and highlighted areas are in `guide-steps.ts` (the 「이용 방법」 screen shows the same seven). */
const guide = guideSteps;
const LIFT = 1.1;                                       // the cut is 1.1 × the screen's width

/** Where the cut sits, as fractions of the screen picture — the card follows whatever size the slide gives the screen. */
function liftStyle([x0, y0, x1, y1]: readonly number[], fill: string): CSSProperties {
  const width = x1 - x0, height = y1 - y0;
  return { "--fill": fill, "--lift": LIFT, "--cut-ratio": `${width} / ${height}`, "--cut-zoom": SHOT_W / width, "--cut-x": x0 / width, "--cut-y": y0 / height,
    "--cut-h": LIFT * (SHOT_W / SHOT_H) * (height / width), "--cut-mid": (y0 + y1) / 2 / SHOT_H } as CSSProperties;
}

const delay = (seconds: number) => ({ "--d": `${seconds.toFixed(3)}s` }) as CSSProperties;

function Lines({ text }: { text: string }) {
  return text.split("\n").map((line, index) => <Fragment key={index}>{index > 0 && <br />}{line}</Fragment>);
}

/** Title reveal by character (h1) or word (h2), keeping line breaks. */
function Reveal({ text, mode }: { text: string; mode: "char" | "word" }) {
  const base = mode === "char" ? .12 : .15, gap = mode === "char" ? .035 : .08;
  let unit = 0;
  const words = (line: string) => line.split(/(\s+)/).filter(Boolean).map((part, index) => /^\s+$/.test(part)
    ? " "
    : <span key={index} className={styles.word}>{(mode === "char" ? [...part] : [part]).map((piece, pieceIndex) => <span key={pieceIndex} className={styles.unit} style={delay(base + unit++ * gap)}>{piece}</span>)}</span>);
  return text.split("\n").map((line, index) => <Fragment key={index}>{index > 0 && <br />}{words(line)}</Fragment>);
}

export function Intro() {
  const { language } = useSettings();
  const text = copy[language];
  const pick = (pair: readonly [ko: string, en: string]) => pair[language === "ko" ? 0 : 1];
  const router = useRouter();
  // ★`[2026-10-06 user decision]` The button always goes straight to registering a plan. The terms are still required: a visitor who has not
  //   agreed is sent to the start screen by `ConsentGate` and, once they agree there, on to the plan (`onboarding.tsx`). The preference survey is
  //   no longer part of the first run — it is done on its own from the menu / My page.
  const [{ agreed }] = useOnboarding();
  const pages = useRef<HTMLElement>(null);
  const [shown, setShown] = useState<boolean[]>([true, false, false]);
  const [current, setCurrent] = useState(0);
  const [progress, setProgress] = useState(0);
  const slides = useRef<HTMLDivElement>(null);
  const [slide, setSlide] = useState(0);
  const drag = useRef<{ x: number; left: number; from: number } | null>(null);
  const stopDragWait = useRef<(() => void) | null>(null);
  const [dragging, setDragging] = useState(false);
  useEffect(() => () => stopDragWait.current?.(), []);
  useDocumentTitle(text.title);

  const sections = useCallback(() => [...(pages.current?.children ?? [])] as HTMLElement[], []);

  useEffect(() => {
    const root = pages.current;
    if (!root) return;
    const observer = new IntersectionObserver((entries) => entries.forEach((entry) => {
      const index = sections().indexOf(entry.target as HTMLElement);
      if (entry.intersectionRatio >= .6) { setShown((state) => state.map((value, i) => i === index ? true : value)); setCurrent(index); }
      else if (entry.intersectionRatio < .12) setShown((state) => state.map((value, i) => i === index ? false : value));
    }), { root, threshold: [0, .12, .6] });
    sections().forEach((section) => observer.observe(section));
    // Backup for mobile browsers that skip observer callbacks during snap scrolling.
    let frame = 0;
    const sync = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const height = root.clientHeight || 1, top = root.scrollTop;
        setShown((state) => sections().map((section, i) => {
          const distance = Math.abs(section.offsetTop - top);
          return distance < height * .4 ? true : distance > height * .9 ? false : state[i];
        }));
        const max = root.scrollHeight - root.clientHeight;
        setProgress(max > 0 ? top / max : 0);
      });
    };
    root.addEventListener("scroll", sync, { passive: true });
    root.addEventListener("scrollend", sync);
    addEventListener("resize", sync);
    return () => { observer.disconnect(); cancelAnimationFrame(frame); root.removeEventListener("scroll", sync); root.removeEventListener("scrollend", sync); removeEventListener("resize", sync); };
  }, [sections]);

  // Replay the visible page when the language changes: hide it for a frame, then reveal again.
  const [revealed, setRevealed] = useState(language);
  const replaying = revealed !== language;
  useEffect(() => {
    if (!replaying) return;
    let frame = requestAnimationFrame(() => { frame = requestAnimationFrame(() => setRevealed(language)); });
    return () => cancelAnimationFrame(frame);
  }, [replaying, language]);

  function go(index: number) {
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    pages.current?.scrollTo({ top: sections()[index]?.offsetTop ?? 0, behavior: reduced ? "instant" : "smooth" });
  }

  function backToStart() {
    pages.current?.scrollTo({ top: 0, behavior: "instant" });
    setCurrent(0);
    setShown([false, false, false]);
    requestAnimationFrame(() => setShown([true, false, false]));
  }

  const slideItems = () => [...(slides.current?.children ?? [])] as HTMLElement[];

  function trackSlide() {
    const [first, second] = slideItems();
    if (!first || !second || !slides.current) return;
    setSlide(Math.min(guide.length - 1, Math.round(slides.current.scrollLeft / (second.offsetLeft - first.offsetLeft))));
  }

  function showSlide(index: number) {
    const items = slideItems();
    if (!items[index]) return;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    slides.current?.scrollTo({ left: items[index].offsetLeft - items[0].offsetLeft, behavior: reduced ? "instant" : "smooth" });
  }

  /** Mouse drag on PC. Touch and trackpads keep the browser's own swipe. */
  function startDrag(event: PointerEvent<HTMLDivElement>) {
    if (event.pointerType !== "mouse" || event.button !== 0 || !slides.current) return;
    stopDragWait.current?.();
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { x: event.clientX, left: slides.current.scrollLeft, from: slide };
    setDragging(true);
  }

  function moveDrag(event: PointerEvent<HTMLDivElement>) {
    if (drag.current && slides.current) slides.current.scrollLeft = drag.current.left - (event.clientX - drag.current.x);
  }

  /** Past 40px, move by the dragged number of cards (at least one) in that direction; otherwise return. */
  function endDrag() {
    const start = drag.current, root = slides.current, [first, second] = slideItems();
    drag.current = null;
    if (!start || !root || !first || !second) return setDragging(false);
    const step = second.offsetLeft - first.offsetLeft, travelled = root.scrollLeft - start.left;
    const cards = Math.abs(travelled) < 40 ? 0 : Math.sign(travelled) * Math.max(1, Math.round(Math.abs(travelled) / step));
    const target = Math.min(guide.length - 1, Math.max(0, start.from + cards));
    // Snapping stays off until the glide ends, so the browser does not re-snap halfway.
    if (Math.abs(root.scrollLeft - Math.min(target * step, root.scrollWidth - root.clientWidth)) < 1) return setDragging(false);
    let timer: ReturnType<typeof setTimeout>;
    const clean = () => {
      clearTimeout(timer);
      root.removeEventListener("scroll", wait);
      root.removeEventListener("scrollend", finish);
      stopDragWait.current = null;
    };
    const finish = () => { clean(); setDragging(false); };
    // Older browsers omit scrollend; restore snapping once scrolling has been quiet.
    const wait = () => { clearTimeout(timer); timer = setTimeout(finish, 150); };
    stopDragWait.current = clean;
    root.addEventListener("scroll", wait, { passive: true });
    root.addEventListener("scrollend", finish, { once: true });
    wait();
    showSlide(target);
  }

  function keys(event: KeyboardEvent<HTMLElement>) {
    if (event.target !== pages.current) return;
    const index = Math.round(pages.current.scrollTop / pages.current.clientHeight);
    const targets: Record<string, number> = { ArrowDown: Math.min(2, index + 1), PageDown: Math.min(2, index + 1), ArrowUp: Math.max(0, index - 1), PageUp: Math.max(0, index - 1), Home: 0, End: 2 };
    if (event.key in targets) { event.preventDefault(); go(targets[event.key]); }
  }

  const controls = (next: number): ReactNode => <div className={styles.controls} data-fx="fade" style={delay(1.1)}>
    <div className={styles.scrollCue}>{next === 1 && <span className={styles.scrollHint}>{text.scrollHint}</span>}<button type="button" className={styles.down} onClick={() => go(next)} aria-label={text.next}><span aria-hidden="true">↓</span></button></div>
    {/* `[2026-10-22 사용자 지시]` 「소개 건너뛰기」는 뺐다 — 아래로 넘기면 같은 곳(마지막 장)으로 간다. */}
  </div>;
  const page = (index: number) => `${styles.page} ${shown[index] && !(replaying && index === current) ? styles.in : ""}`;

  return <DeviceFrame onBrand={backToStart} headerExtra={<><HelpButton /><LanguageButton /></>}>
    <div className={styles.progress} style={{ "--fx-p": progress.toFixed(3) } as CSSProperties} aria-hidden="true" />
    <main ref={pages} id="main-content" className={styles.pages} tabIndex={0} aria-label={text.pages} onKeyDown={keys} style={{ "--intro-bg": background, "--intro-bg-night": nightBackground } as CSSProperties}>
      <section className={`${page(0)} ${styles.hero}`} aria-labelledby="intro-title">
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow} data-fx="up" style={delay(.05)}>YOUR TRAVEL, OUR JOURNEY</p>
          <h1 id="intro-title" className={styles.title}><Reveal key={language} text={text.intro} mode="char" /></h1>
          <p className={styles.description} data-fx="up" style={delay(.5)}><Lines text={text.introDescription} /></p>
        </div>
        <div className={styles.trips} data-fx="up" style={delay(.75)}><RecentTrips /></div>
        {/* `[2026-10-22 사용자 결정]` 이 카드가 여행 등록 단추 — 셋째 장 「내 일정 시작하기」와 같은 곳으로 간다. 모양은 그대로 두고 아래 줄(글자 · 점선 길 · 핀 ·
            비행기)로 단추임을 알린다. 목업 `mockups/intro-badge-cta-2026-10-22-v1` 의 A 「비행기 길」. */}
        <button type="button" className={styles.badge} data-fx="scale" style={delay(.8)} onClick={() => router.push(routes.newTrip)} aria-label={`${text.badgeCta} · ${text.badge}`}>
          <small>A LITTLE MORE YOU</small><strong>{text.badge}</strong>
          <span className={styles.badgeGo}><span className={styles.badgeLabel}>{text.badgeCta}</span><span className={styles.badgeRoute} aria-hidden="true"><i className={styles.badgePin} /><Plane className={styles.badgePlane} size={16} strokeWidth={2} /></span></span>
        </button>
        {controls(1)}
      </section>
      <section className={`${page(1)} ${styles.how}`} aria-labelledby="how-title">
        <p className={styles.eyebrow} data-fx="up" style={delay(.05)}>{text.howEyebrow}</p>
        <h2 id="how-title" className={styles.title}><Reveal key={language} text={text.how} mode="word" /></h2>
        <div className={styles.guide} role="region" aria-roledescription="carousel" aria-label={text.guide} data-fx="left" style={delay(.45)}>
          <div ref={slides} className={`${styles.slides} ${dragging ? styles.dragging : ""}`} onScroll={trackSlide} onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={endDrag} onPointerCancel={endDrag}>{guide.map(({ shot, area, fill, title, detail, chip }, index) => (
            <div key={shot} className={styles.slide} role="group" aria-roledescription="slide" aria-label={`${index + 1} / ${guide.length}`}>
              <div className={styles.slideHead}>
                <span className={styles.stepNo}>0{index + 1}</span>
                <div><h3>{pick(title)}</h3><p>{pick(detail)}</p></div>
              </div>
              <div className={styles.shot}>
                <div className={styles.frame} style={liftStyle(area, fill)}>
                  <Image className={styles.screen} src={guideImage(language, shot)} alt={`${text.shot}: ${pick(title)}`} width={SHOT_W} height={SHOT_H} sizes="300px" draggable={false} />
                  <div className={styles.lift} aria-hidden="true">
                    <div className={styles.cut}><Image src={guideImage(language, shot)} alt="" width={SHOT_W} height={SHOT_H} sizes="640px" draggable={false} /></div>
                    <span className={styles.pin}><span className={styles.chip}>{pick(chip)}</span><span className={styles.wire} /></span>
                  </div>
                </div>
              </div>
            </div>
          ))}</div>
          <div className={styles.guideNav}>
            <button type="button" onClick={() => showSlide(slide - 1)} aria-disabled={slide === 0} aria-label={text.prevStep}><span aria-hidden="true">←</span></button>
            <p><strong aria-live="polite">{slide + 1} / {guide.length}</strong><span className={styles.swipeHint}>{text.swipe}</span></p>
            <button type="button" onClick={() => showSlide(slide + 1)} aria-disabled={slide === guide.length - 1} aria-label={text.nextStep}><span aria-hidden="true">→</span></button>
          </div>
        </div>
        {controls(2)}
      </section>
      <section className={page(2)} aria-labelledby="start-title">
        <p className={styles.eyebrow} data-fx="up" style={delay(.05)}>LET’S MAKE IT YOURS</p>
        <h2 id="start-title" className={styles.title}><Reveal key={language} text={text.start} mode="word" /></h2>
        <p className={styles.description} data-fx="up" style={delay(.5)}><Lines text={text.startDescription} /></p>
        <div className={styles.ticket} data-fx="scale" style={delay(.45)}>
          <span className={styles.ticketLabel}>{text.ticketLabel}</span>
          <div className={styles.route}><strong>{text.taste}</strong><span className={styles.routeLine} aria-hidden="true">····· →</span><strong>{text.trip}</strong></div>
          <div className={styles.ticketBottom}><span>{text.ticketPartner}</span><span>GuguRoute</span></div>
        </div>
        <div className={styles.actionArea} data-fx="up" style={delay(.95)}>
          <button type="button" className={styles.primary} onClick={() => router.push(routes.newTrip)}><span>{text.cta}</span><span aria-hidden="true">↗</span></button>
          <p className={styles.actionNote}>{agreed ? text.actionNoteDone : text.actionNote}</p>
        </div>
      </section>
    </main>
    <nav className={styles.pagination} aria-label={text.navigation}>{[0, 1, 2].map((index) => (
      <button key={index} type="button" className={styles.dot} onClick={() => go(index)} aria-current={index === current ? "step" : undefined} aria-label={`${index + 1}. ${text[`label${index}`]}`} />
    ))}</nav>
    {/* `[2026-10-22 사용자 지시]` 첫 장에서 마지막 장(일정 시작)으로 바로 — 이용 방법 장은 제 ↓ 가 같은 자리에서 마지막 장으로 간다. */}
    {current === 0 && <button type="button" className={styles.toEnd} onClick={() => go(2)} aria-label={text.toEnd} title={text.toEnd}><ChevronsDown size={24} strokeWidth={2} aria-hidden="true" /></button>}
  </DeviceFrame>;
}

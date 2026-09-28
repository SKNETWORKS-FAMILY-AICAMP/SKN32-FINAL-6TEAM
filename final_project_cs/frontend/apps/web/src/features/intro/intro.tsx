"use client";

import { getImageProps } from "next/image";
import { useRouter } from "next/navigation";
import { Fragment, useCallback, useEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type ReactNode } from "react";
import { DeviceFrame } from "@/components/layout/device-frame";
import type { Language } from "@/lib/i18n";
import { routes } from "@/lib/routes";
import { useSettings } from "@/lib/settings";
import { useDocumentTitle } from "@/lib/use-document-title";
import styles from "./intro.module.css";

const copy: Record<Language, Record<string, string>> = {
  en: {
    title: "triPilot · Your next journey",
    intro: "From plans to memories,\ntriPilot by your side.",
    introDescription: "A travel partner that understands your style\nand helps you review your plans.\nMake room for the joy of the journey.",
    badge: "Your style. Your pace. Your journey.",
    how: "A trip that feels like you.\nOne step at a time.",
    howDescription: "A little less planning stress.\nA little more looking forward.",
    step1: "Tell us what you love", detail1: "Your favorite experiences and travel companions.\nSet the starting point for a trip that fits you.",
    step2: "Bring your travel plans", detail2: "Add the places and plans you have in mind.\nSee each day come together at a glance.",
    step3: "Review and refine together", detail3: "Check travel times and visiting requirements.\nFine-tune your itinerary through conversation.",
    howNote: "You can update your preferences and plans later.",
    start: "Your next journey\nstarts right here.",
    startDescription: "The places you dream of. The moments you love.\nTell us what your next trip looks like.",
    taste: "Your style", trip: "Your trip", cta: "Start my itinerary",
    actionNote: "Review the terms, then tell us your travel preferences.",
    scrollHint: "Scroll down to explore", skip: "Skip intro", next: "Next screen",
    pages: "triPilot introduction. Scroll down to move to the next screen.", navigation: "Introduction screens",
    label0: "Introduction", label1: "How it works", label2: "Start your itinerary",
  },
  ko: {
    title: "triPilot · 당신다운 여행의 시작",
    intro: "계획부터 여행까지,\n당신 곁의 triPilot.",
    introDescription: "취향을 이해하고, 일정을 함께 살펴보는\n나만의 여행 파트너.\n당신은 여행의 설렘에만 집중하세요.",
    badge: "내 취향에 맞게, 내 일정에 여유롭게.",
    how: "당신다운 여행,\n이렇게 시작해요.",
    howDescription: "막막한 여행 준비도\n한 단계씩, triPilot과 함께.",
    step1: "나의 여행 취향 알려주기", detail1: "좋아하는 테마부터 함께 가는 사람까지.\n나에게 맞는 여행의 기준을 정해요.",
    step2: "준비한 일정 가져오기", detail2: "가고 싶은 장소와 여행 계획을 등록하면\n하루의 흐름을 한눈에 정리해요.",
    step3: "함께 점검하고 다듬기", detail3: "이동 시간과 방문 조건을 살펴보고,\n대화하며 일정을 조정해요.",
    howNote: "여행 취향과 일정은 나중에도 수정할 수 있어요.",
    start: "다음 여행의 첫걸음,\n여기서 시작해요.",
    startDescription: "가고 싶은 곳, 좋아하는 순간.\n당신의 여행 이야기를 들려주세요.",
    taste: "나의 취향", trip: "나의 여행", cta: "내 일정 시작하기",
    actionNote: "약관 확인과 여행 취향 설정부터 함께할게요.",
    scrollHint: "아래로 스크롤하며 만나보세요", skip: "소개 건너뛰기", next: "다음 화면",
    pages: "triPilot 서비스 소개. 아래로 스크롤하면 다음 화면으로 이동합니다.", navigation: "소개 화면 이동",
    label0: "서비스 소개", label1: "이용 방법", label2: "일정 시작",
  },
};

/** Optimized background for all three pages; CSS cannot use next/image directly. */
const { props: { srcSet } } = getImageProps({ alt: "", src: "/images/tripilot-home-03-journey.png", width: 1672, height: 941, quality: 75 });
const background = `image-set(${(srcSet ?? "").split(", ").map((entry) => { const [url, density] = entry.split(" "); return `url("${url}") ${density}`; }).join(", ")})`;

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
  const router = useRouter();
  const pages = useRef<HTMLElement>(null);
  const [shown, setShown] = useState<boolean[]>([true, false, false]);
  const [current, setCurrent] = useState(0);
  const [progress, setProgress] = useState(0);
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

  function keys(event: KeyboardEvent<HTMLElement>) {
    if (event.target !== pages.current) return;
    const index = Math.round(pages.current.scrollTop / pages.current.clientHeight);
    const targets: Record<string, number> = { ArrowDown: Math.min(2, index + 1), PageDown: Math.min(2, index + 1), ArrowUp: Math.max(0, index - 1), PageUp: Math.max(0, index - 1), Home: 0, End: 2 };
    if (event.key in targets) { event.preventDefault(); go(targets[event.key]); }
  }

  const controls = (next: number): ReactNode => <div className={styles.controls} data-fx="fade" style={delay(1.1)}>
    <div className={styles.scrollCue}>{next === 1 && <span className={styles.scrollHint}>{text.scrollHint}</span>}<button type="button" className={styles.down} onClick={() => go(next)} aria-label={text.next}><span aria-hidden="true">↓</span></button></div>
    <button type="button" className={styles.skip} onClick={() => go(2)}>{text.skip}<span aria-hidden="true"> ↗</span></button>
  </div>;
  const page = (index: number) => `${styles.page} ${shown[index] && !(replaying && index === current) ? styles.in : ""}`;

  return <DeviceFrame onBrand={backToStart}>
    <div className={styles.progress} style={{ "--fx-p": progress.toFixed(3) } as CSSProperties} aria-hidden="true" />
    <main ref={pages} id="main-content" className={styles.pages} tabIndex={0} aria-label={text.pages} onKeyDown={keys} style={{ "--intro-bg": background } as CSSProperties}>
      <section className={`${page(0)} ${styles.hero}`} aria-labelledby="intro-title">
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow} data-fx="up" style={delay(.05)}>YOUR TRAVEL, OUR JOURNEY</p>
          <h1 id="intro-title" className={styles.title}><Reveal key={language} text={text.intro} mode="char" /></h1>
          <p className={styles.description} data-fx="up" style={delay(.5)}><Lines text={text.introDescription} /></p>
        </div>
        <div className={styles.badge} data-fx="scale" style={delay(.8)}><small>A LITTLE MORE YOU</small><strong>{text.badge}</strong></div>
        {controls(1)}
      </section>
      <section className={`${page(1)} ${styles.how}`} aria-labelledby="how-title">
        <p className={styles.eyebrow} data-fx="up" style={delay(.05)}>HOW IT WORKS</p>
        <h2 id="how-title" className={styles.title}><Reveal key={language} text={text.how} mode="word" /></h2>
        <p className={styles.description} data-fx="up" style={delay(.5)}><Lines text={text.howDescription} /></p>
        <div className={styles.steps}>{[1, 2, 3].map((step, index) => (
          <article key={step} className={styles.step} data-fx="flip" style={delay(.45 + index * .14)}>
            <span className={styles.stepNo}>0{step}</span>
            <div><h3>{text[`step${step}`]}</h3><p><Lines text={text[`detail${step}`]} /></p></div>
          </article>
        ))}</div>
        <p className={styles.howNote} data-fx="fade" style={delay(1)}>{text.howNote}</p>
        {controls(2)}
      </section>
      <section className={page(2)} aria-labelledby="start-title">
        <p className={styles.eyebrow} data-fx="up" style={delay(.05)}>LET’S MAKE IT YOURS</p>
        <h2 id="start-title" className={styles.title}><Reveal key={language} text={text.start} mode="word" /></h2>
        <p className={styles.description} data-fx="up" style={delay(.5)}><Lines text={text.startDescription} /></p>
        <div className={styles.ticket} data-fx="scale" style={delay(.45)}>
          <span className={styles.ticketLabel}>YOUR NEXT JOURNEY</span>
          <div className={styles.route}><strong>{text.taste}</strong><span className={styles.routeLine} aria-hidden="true">····· →</span><strong>{text.trip}</strong></div>
          <div className={styles.ticketBottom}><span>TRAVEL PARTNER</span><span>triPilot</span></div>
        </div>
        <div className={styles.actionArea} data-fx="up" style={delay(.95)}>
          <button type="button" className={styles.primary} onClick={() => router.push(routes.start)}><span>{text.cta}</span><span aria-hidden="true">↗</span></button>
          <p className={styles.actionNote}>{text.actionNote}</p>
        </div>
      </section>
    </main>
    <nav className={styles.pagination} aria-label={text.navigation}>{[0, 1, 2].map((index) => (
      <button key={index} type="button" className={styles.dot} onClick={() => go(index)} aria-current={index === current ? "step" : undefined} aria-label={`${index + 1}. ${text[`label${index}`]}`} />
    ))}</nav>
  </DeviceFrame>;
}

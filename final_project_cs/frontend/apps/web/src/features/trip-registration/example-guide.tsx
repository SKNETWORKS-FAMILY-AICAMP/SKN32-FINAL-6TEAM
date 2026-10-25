"use client";

import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";
import { useSettings, useT } from "@/lib/settings";
import styles from "./example-guide.module.css";

const seenKey = "tripilot.web.example-guide.v1";

/** The first-trip guide was finished or closed in this browser — it is not offered again. A browser that keeps nothing (a private window) may see it again. */
export function exampleGuideSeen(): boolean {
  try { return localStorage.getItem(seenKey) === "done"; }
  catch { return false; }
}

function markSeen() {
  try { localStorage.setItem(seenKey, "done"); } catch { /* a private window: nothing is kept */ }
}

/**
 * ★`[2026-10-25 사용자 결정 — 예시 불러오기 첫 안내 A안]` (목업 `mockups/tripilot-registration-example-guide.html`) The screen is covered in black and one button stays lit,
 * with a bubble that tells how to try the service: ① 「예시 불러오기」 fills the box with the example plan → ② 「계획 확인하기」 starts the check (the same press as the button itself).
 * 「직접 쓸게요」 · 「닫기」 · Esc end it; once it ends it is not shown again in this browser. Pressing the lit button does what the bubble's main button does.
 */
export function ExampleGuide({ sample, submit, onLoad, onDone }: {
  sample: RefObject<HTMLButtonElement | null>; submit: RefObject<HTMLButtonElement | null>; onLoad: () => void; onDone: () => void;
}) {
  const t = useT();
  const { skipAnimation } = useSettings();
  const [step, setStep] = useState<1 | 2>(1);
  const spot = useRef<HTMLDivElement>(null);
  const tip = useRef<HTMLDivElement>(null);
  const go = useRef<HTMLButtonElement>(null);
  const target = step === 1 ? sample : submit;

  // The lit hole follows its button every frame — the page and the phone frame scroll, the window resizes.
  useLayoutEffect(() => {
    target.current?.scrollIntoView({ block: "nearest" });
    let frame = 0;
    const place = () => {
      const button = target.current, light = spot.current, bubble = tip.current;
      if (button && light && bubble) {
        const box = button.getBoundingClientRect(), pad = 6, gap = 14;
        light.style.left = `${box.left - pad}px`;
        light.style.top = `${box.top - pad}px`;
        light.style.width = `${box.width + pad * 2}px`;
        light.style.height = `${box.height + pad * 2}px`;
        const width = Math.min(343, window.innerWidth - 32);
        const left = Math.min(Math.max(box.left + box.width / 2 - width / 2, 16), window.innerWidth - 16 - width);
        const below = box.top < window.innerHeight / 2;
        bubble.dataset.side = below ? "below" : "above";
        bubble.style.width = `${width}px`;
        bubble.style.left = `${left}px`;
        bubble.style.top = below ? `${box.bottom + pad + gap}px` : "auto";
        bubble.style.bottom = below ? "auto" : `${window.innerHeight - box.top + pad + gap}px`;
        bubble.style.setProperty("--tail", `${Math.min(Math.max(box.left + box.width / 2 - left - 7, 20), width - 34)}px`);
      }
      frame = requestAnimationFrame(place);
    };
    place();
    return () => cancelAnimationFrame(frame);
  }, [target]);
  useEffect(() => { go.current?.focus({ preventScroll: true }); }, [step]);

  function finish(then?: () => void) {
    markSeen();
    onDone();
    if (then) requestAnimationFrame(then);
  }
  function advance() {
    if (step === 1) { onLoad(); setStep(2); return; }
    finish(() => submit.current?.click());                  // the check starts as if the customer had pressed 「계획 확인하기」 (the Course Keeper card first, when it is on)
  }
  function quit() {
    finish(step === 1 ? () => document.getElementById("plan-source")?.focus() : () => submit.current?.focus());
  }
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") quit(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  const words = step === 1
    ? { label: t("1 / 2 · 처음 여행이라면", "1 / 2 · Your first trip?"), title: t("예시로 한 번 해 보세요", "Try it with an example"),
        body: t("「예시 불러오기」를 눌러 일정 예시를 불러오고, 「계획 확인하기」로 장소 · 운영시간 · 이동을 검증해 보세요.", "Press “Load example” to fill in a sample plan, then “Check my plan” to check its places, opening hours and travel."),
        go: t("예시 불러오기", "Load example"), quiet: t("직접 쓸게요", "I’ll write my own") }
    : { label: t("2 / 2 · 예시를 불러왔어요", "2 / 2 · The example is in"), title: t("「계획 확인하기」를 눌러 검증해 보세요", "Press “Check my plan” to check it"),
        body: t("장소 · 운영시간 · 휴무 · 이동을 차례로 확인해 드려요.", "We check places, opening hours, closed days and travel, one by one."),
        go: t("계획 확인하기", "Check my plan"), quiet: t("닫기", "Close") };
  return createPortal(<div className={styles.coach} role="dialog" aria-modal="true" aria-labelledby="example-guide-title" data-still={skipAnimation || undefined}>
    <div ref={spot} className={styles.spot} onClick={advance} aria-hidden="true" />
    <div ref={tip} key={step} className={styles.tip}>
      <p className={styles.step}>{words.label}</p>
      <h2 id="example-guide-title" className={styles.title}>{words.title}</h2>
      <p className={styles.body}>{words.body}</p>
      <div className={styles.actions}>
        <button type="button" className={styles.quiet} onClick={quit}>{words.quiet}</button>
        <button ref={go} type="button" className={styles.go} onClick={advance}>{words.go}</button>
      </div>
    </div>
  </div>, document.body);
}

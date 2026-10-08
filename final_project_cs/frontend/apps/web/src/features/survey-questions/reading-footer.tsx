"use client";

import { useContext, useEffect, useId, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { Check, LoaderCircle } from "lucide-react";
import { OverlayRoot } from "@/components/layout/overlay-root";
import { useT } from "@/lib/settings";
import { TIMING, type QuestionFlow } from "./use-question-flow";
import styles from "./survey-questions.module.css";

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 2단계 · 목업 v9 `resultFooter` · `doneFooter`]` The bottom of the reading screen while questions are asked.
 *   - The server is still reading: 「계획 읽는 중…」 - NOT a disabled button but one that says why when pressed (`aria-disabled` · `aria-busy`).
 *   - Reading is done and questions are open: 「읽어 온 계획 확인하기」, and what is left for later.
 *   - The plan is read and the customer is not mid-answer (all answered, or nothing touched): 「질문에 모두 답했어요」 / 「계획을 다 읽었어요」 + the 5-second bar + the button + 「자동으로 넘어가지 않기」.
 */
export function ReadingFooter({ flow }: { flow: QuestionFlow }) {
  const t = useT();
  const [pressed, setPressed] = useState(false);
  const helpId = useId();
  if (flow.phase === "read") {
    return <div className={styles.footer}>
      <button type="button" className={styles.big} aria-disabled="true" aria-busy="true" aria-describedby={helpId} onClick={() => setPressed(true)}>
        <span className={styles.spin} aria-hidden="true"><LoaderCircle strokeWidth={1.8} /></span>{t("계획 읽는 중…", "Reading your plan…")}</button>
      <p id={helpId} className={styles.help} role="status">{pressed ? t("아직 읽는 중이에요. 로딩이 끝나면 단추가 켜져요.", "Still reading. The button turns on when it is done.") : t("로딩이 끝나면 단추가 켜져요.", "The button turns on when loading is done.")}</p>
    </div>;
  }
  if (flow.phase === "done") {
    return <div className={styles.footer}>
      <p className={styles.doneLine} role="status"><Check size={16} strokeWidth={1.8} aria-hidden="true" />{flow.allDone ? t("질문에 모두 답했어요", "You have answered everything") : t("계획을 다 읽었어요", "We have read your plan")}</p>
      <p className={styles.doneSub}>{t(`${Math.round(TIMING.doneMs / 1000)}초 뒤에 계획 확인 화면으로 넘어가요.`, `The plan check opens in ${Math.round(TIMING.doneMs / 1000)} seconds.`)}{!flow.allDone && ` ${t(`남은 질문 ${flow.left}개는 지금 답해도 돼요.`, `You can still answer the ${flow.left} remaining question${flow.left === 1 ? "" : "s"} now.`)}`}</p>
      <div className={styles.finishTrack} aria-hidden="true"><div className={styles.finishFill} style={{ "--finish-ms": `${TIMING.doneMs}ms` } as CSSProperties} /></div>
      <button type="button" className={styles.big} onClick={flow.release}>{t("읽어 온 계획 확인하기", "Check the plan we read")}</button>
      <button type="button" className={styles.textButton} onClick={flow.stop}>{t("자동으로 넘어가지 않기", "Do not go on by itself")}</button>
    </div>;
  }
  // `late` (and `idle`, whose warning stands over this)
  return <div className={styles.footer}>
    <button type="button" className={styles.big} onClick={flow.release}>{t("읽어 온 계획 확인하기", "Check the plan we read")}</button>
    <p className={styles.help} role="status">{flow.left > 0
      ? t(`남은 질문 ${flow.left}개는 다음에 계획을 읽을 때 다시 답할 수 있어요.`, `You can answer the ${flow.left} remaining question${flow.left === 1 ? "" : "s"} the next time a plan is read.`)
      : t("누르면 계획 확인 화면으로 가요.", "Press it to open the plan check.")}</p>
  </div>;
}

/**
 * The 20-second warning (mockup `screenIdle`): nobody touched anything for 30 seconds while questions were open after the reading. An `alertdialog` that counts down to the plan check;
 * 「계속 답하기」 (as many times as wanted) or 「자동으로 넘어가지 않기」 keep the screen. Esc is 「계속 답하기」. The behind is `inert`, Tab goes round inside.
 */
export function IdleWarning({ flow }: { flow: QuestionFlow }) {
  const t = useT();
  const layer = useRef<HTMLDivElement>(null);
  const first = useRef<HTMLButtonElement>(null);
  const copyId = useId();
  // Inside the phone frame the warning stands inside it too (`[2026-10-06]`, like the Course Keeper card).
  const root = useContext(OverlayRoot);
  const keep = flow.keepAnswering;
  useEffect(() => {
    const opener = document.activeElement;
    first.current?.focus({ preventScroll: true });
    const scope = root ? root.parentElement : document.body;
    const behind = Array.from(scope?.children ?? []).filter((element) => element !== layer.current && element !== root && !element.matches("script, [data-guardian-keep]")) as HTMLElement[];
    const was = behind.map((element) => element.inert);
    behind.forEach((element) => { element.inert = true; });
    return () => {
      behind.forEach((element, index) => { element.inert = was[index]; });
      if (opener instanceof HTMLElement && document.contains(opener)) opener.focus({ preventScroll: true });
    };
  }, [root]);
  const seconds = Math.max(0, flow.seconds);
  // Said aloud at 20 · 10 · 5 s, not every second.
  const announce = [TIMING.countdownS, 10, 5].includes(seconds) ? t(`${seconds}초 뒤에 계획 확인 화면으로 넘어가요`, `The plan check opens in ${seconds} seconds`) : null;
  function keys(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") { event.preventDefault(); keep(); return; }
    if (event.key !== "Tab") return;
    const stops = Array.from(event.currentTarget.querySelectorAll<HTMLElement>("button:not(:disabled)"));
    if (!stops.length) return;
    const at = document.activeElement;
    if (event.shiftKey && at === stops[0]) { event.preventDefault(); stops[stops.length - 1].focus(); }
    else if (!event.shiftKey && at === stops[stops.length - 1]) { event.preventDefault(); stops[0].focus(); }
  }
  if (typeof document === "undefined") return null;
  return createPortal(
    <div ref={layer} className={styles.layer} onKeyDown={keys}>
      <section className={styles.sheet} role="alertdialog" aria-modal="true" aria-labelledby={copyId}>
        <p className={styles.countdown} aria-hidden="true">{seconds}</p>
        <p id={copyId} className={styles.countCopy}>{t(`아직 보고 계신가요? ${seconds}초 뒤에 계획 확인 화면으로 넘어가요`, `Are you still there? The plan check opens in ${seconds} seconds`)}</p>
        <button ref={first} type="button" className={styles.big} onClick={keep}>{t("계속 답하기", "Keep answering")}</button>
        <button type="button" className={styles.textButton} onClick={flow.stop}>{t("자동으로 넘어가지 않기", "Do not go on by itself")}</button>
        <p className="sr-only" role="status">{announce}</p>
      </section>
    </div>,
    root ?? document.body,
  );
}

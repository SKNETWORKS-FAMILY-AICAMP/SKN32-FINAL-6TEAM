"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type MouseEvent, type PointerEvent, type ReactNode } from "react";
import type { Translate } from "@/lib/i18n";
import { DrawnCheck, OnboardingIcon } from "./icons";
import {
  answeredCount, chosenLabel, count, FOOD_STEP, isOptional, LAST_STEP, options, questions, stepNames, toggle, valid, validationHint,
  type Answers, type ChoiceKey, type CountKey, type ListKey, type Option,
} from "./model";
import styles from "./onboarding.module.css";

const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const pad = (value: number) => String(value).padStart(2, "0");

/** Nine question cards on one track: tap, swipe or use the arrow keys to move. */
export function QuestionCarousel({ t, answers, step, setAnswers, setStep, onFirstBack, onComplete, onCollapse, onFeedback, announce }: {
  t: Translate;
  answers: Answers;
  step: number;
  setAnswers: (next: Answers) => void;
  setStep: (next: number) => void;
  onFirstBack: () => void;
  onComplete: () => void;
  onCollapse: () => void;
  onFeedback: () => void;
  announce: (message: string) => void;
}) {
  const viewport = useRef<HTMLDivElement>(null);
  const track = useRef<HTMLDivElement>(null);
  const footer = useRef<HTMLDivElement>(null);
  const busy = useRef(false);
  const release = useRef(0);
  const gesture = useRef<{ id: number; x: number; y: number; dx: number; dragging: boolean } | null>(null);
  const suppressClickUntil = useRef(0);
  const [forcedError, setForcedError] = useState<{ step: number; text: string } | null>(null);
  const [touched, setTouched] = useState<ReadonlySet<string>>(new Set());
  const answered = answeredCount(answers);

  const position = useCallback((drag = 0) => {
    if (track.current) track.current.style.transform = `translateX(calc(${-step * 100}% - ${step * 12}px + ${drag}px))`;
  }, [step]);

  const fit = useCallback(() => {
    const card = viewport.current?.closest("section");
    if (card && footer.current) card.style.setProperty("--question-card-height", `${Math.max(0, card.clientHeight - footer.current.offsetHeight - 1)}px`);
    const slide = track.current?.children[step] as HTMLElement | undefined;
    if (viewport.current && slide?.offsetHeight) viewport.current.style.height = `${slide.offsetHeight}px`;
  }, [step]);

  useLayoutEffect(() => { position(); fit(); }, [position, fit]);
  useEffect(() => {
    const observer = new ResizeObserver(() => fit());
    [...(track.current?.children ?? [])].forEach((slide) => observer.observe(slide));
    const card = viewport.current?.closest("section");
    if (card) observer.observe(card);
    const resize = () => { gesture.current = null; track.current?.classList.remove(styles.dragging); position(); fit(); };
    addEventListener("resize", resize);
    return () => { observer.disconnect(); removeEventListener("resize", resize); };
  }, [fit, position]);
  useEffect(() => () => clearTimeout(release.current), []);

  function finish(next: number) {
    busy.current = false;
    document.getElementById(`question-title-${next}`)?.focus({ preventScroll: true });
  }

  function change(direction: 1 | -1, fromSwipe = false) {
    if (busy.current) return;
    if (direction > 0 && !valid(step, answers)) {
      setForcedError({ step, text: validationHint(step, answers, t) || t("이 카드의 선택을 마치면 다음으로 이동할 수 있어요.", "Complete this card before moving forward.") });
      position();
      return;
    }
    if (direction < 0 && step === 0) { if (!fromSwipe) onFirstBack(); position(); return; }
    if (direction > 0 && step === LAST_STEP) {
      if (fromSwipe) { position(); return; }
      const missing = questions.findIndex((_, index) => !valid(index, answers));
      if (missing >= 0) { setStep(missing); onFeedback(); announce(`${missing + 1} / ${questions.length}. ${t(questions[missing][0], questions[missing][1])}`); return; }
      onComplete();
      return;
    }
    const next = step + direction;
    busy.current = true;
    setStep(next);
    onFeedback();
    announce(`${next + 1} / ${questions.length}. ${t(questions[next][0], questions[next][1])}`);
    if (reducedMotion()) finish(next);
    else release.current = window.setTimeout(() => finish(next), 400);
  }

  function update(next: Answers) {
    setForcedError(null);
    setAnswers(next);
  }

  function select(event: MouseEvent<HTMLButtonElement>, key: ListKey | ChoiceKey, value: string, multiple: boolean) {
    update(toggle(answers, key, value, multiple));
    feedback(event.currentTarget, `${key}:${value}`);
  }

  function feedback(control: HTMLButtonElement, key: string) {
    control.focus({ preventScroll: true });
    onFeedback();
    if (reducedMotion()) return;
    setTouched((current) => new Set(current).add(key));
    control.animate([
      { transform: "scale(.97)", boxShadow: "0 0 0 0 #2E604700" },
      { transform: "scale(1.015)", boxShadow: "0 0 0 3px #2E604714", offset: .6 },
      { transform: "scale(1)", boxShadow: "0 0 0 0 #2E604700" },
    ], { duration: 220, easing: "cubic-bezier(.2,.8,.2,1)" });
  }

  function skip(index: number) {
    if (index === FOOD_STEP) update({ ...answers, allergies: [], diet: [], foodReligion: [], foodNone: false, foodSkip: true });
    else update({ ...answers, religion: "" });
    change(1);
  }

  function chip(key: ListKey | ChoiceKey, option: Option, multiple: boolean, icon: boolean) {
    const value = answers[key];
    const selected = Array.isArray(value) ? value.includes(option[0]) : value === option[0];
    const feedbackClass = touched.has(`${key}:${option[0]}`) ? styles.selectionFeedback : "";
    return <button key={option[0]} type="button" className={`${styles.chip} ${selected ? styles.selected : ""} ${feedbackClass}`} aria-pressed={selected} onClick={(event) => select(event, key, option[0], multiple)}>
      <span className={styles.optionCheck} aria-hidden="true"><DrawnCheck className={styles.drawnCheck} /></span>
      {icon && <span className={styles.optionIcon}><OnboardingIcon name={option[0]} size={20} /></span>}
      {t(option[1], option[2])}
    </button>;
  }

  const chips = (key: ListKey | ChoiceKey, multiple = false, grid = false, icon = false) => <div className={`${styles.chips} ${grid ? styles.grid : ""}`} role="group">{options[key].map((option) => chip(key, option, multiple, icon))}</div>;
  const label = (ko: string, en: string) => <p className={styles.groupLabel}>{t(ko, en)}</p>;
  const counter = (key: CountKey, ko: string, en: string, captionKo: string, captionEn: string, min: number) => <div className={styles.counterRow}>
    <span className={styles.counterLabel}>{t(ko, en)}<span className={styles.counterCaption}>{t(captionKo, captionEn)}</span></span>
    <div className={styles.counter}>
      <button type="button" aria-label={t(`${ko} 인원 줄이기`, `Fewer ${en.toLowerCase()}`)} disabled={answers[key] <= min} onClick={() => { update(count(answers, key, -1)); onFeedback(); }}>−</button>
      <output aria-label={t(`${ko} 인원`, `${en} count`)}>{answers[key]}</output>
      <button type="button" aria-label={t(`${ko} 인원 늘리기`, `More ${en.toLowerCase()}`)} disabled={answers[key] >= 20} onClick={() => { update(count(answers, key, 1)); onFeedback(); }}>+</button>
    </div>
  </div>;

  function body(index: number): ReactNode {
    switch (index) {
      case 0: return chips("themes", true, true, true);
      case 1: return <>{chips("companions", true)}<div className={styles.counterList}>{counter("adults", "성인", "Adults", "만 13세 이상", "Ages 13+", 1)}{counter("children", "어린이", "Children", "만 2–12세", "Ages 2–12", 0)}{counter("infants", "유아", "Infants", "만 2세 미만", "Under 2", 0)}</div></>;
      case 2: return <>
        {label("알레르기", "Allergies")}{chips("allergies", true)}
        {label("식단", "Diet")}{chips("diet", true)}
        {label("종교상 피하는 음식", "Religious food restrictions")}{chips("foodReligion", true)}
        <div className={`${styles.chips} ${styles.noneRow}`}>
          <button type="button" className={`${styles.chip} ${answers.foodNone ? styles.selected : ""} ${touched.has("food-none") ? styles.selectionFeedback : ""}`} aria-pressed={answers.foodNone} onClick={(event) => {
            update(answers.foodNone ? { ...answers, foodNone: false, foodSkip: false } : { ...answers, foodNone: true, foodSkip: false, allergies: [], diet: [], foodReligion: [] });
            feedback(event.currentTarget, "food-none");
          }}><span className={styles.optionCheck} aria-hidden="true"><DrawnCheck className={styles.drawnCheck} /></span>{t("해당 없음", "None apply")}</button>
        </div>
      </>;
      case 3: return chips("transport", true, true, true);
      case 4: return <>
        <div className={styles.budgetRow}><span>{t("전체 여행 · 1인", "Entire trip · per person")}</span><span>₩ KRW</span></div>
        {chips("budget", false, true)}
        {answers.budget === "custom" && <label className={styles.field}>{t("예산 입력 (원)", "Budget amount (KRW)")}<input type="number" min={1} inputMode="numeric" value={answers.budgetCustom} placeholder={t("예: 800000", "e.g. 800000")} onChange={(event) => update({ ...answers, budgetCustom: event.target.value })} /></label>}
      </>;
      case 5: return chips("citizen", false, true);
      case 6: return chips("priority", false, true, true);
      case 7: return <>{label("음식", "Food")}{chips("detailFood")}{label("활동", "Activities")}{chips("detailActivity")}{label("이동", "Getting around")}{chips("detailTransport")}</>;
      default: return chips("religion", false, true);
    }
  }

  function pointerDown(event: PointerEvent<HTMLDivElement>) {
    if (busy.current || !event.isPrimary || event.button !== 0) return;
    if ((event.target as HTMLElement).closest(`input, select, textarea, label, a, .${styles.questionNav}, .${styles.skip}`)) return;
    gesture.current = { id: event.pointerId, x: event.clientX, y: event.clientY, dx: 0, dragging: false };
  }

  function pointerMove(event: PointerEvent<HTMLDivElement>) {
    const current = gesture.current;
    if (!current || current.id !== event.pointerId) return;
    const dx = event.clientX - current.x, dy = event.clientY - current.y;
    if (!current.dragging) {
      if (Math.abs(dy) > 12 && Math.abs(dy) > Math.abs(dx)) { gesture.current = null; return; }
      if (Math.abs(dx) < 12 || Math.abs(dx) < Math.abs(dy) * 1.25) return;
      current.dragging = true;
      event.currentTarget.setPointerCapture(event.pointerId);
      track.current?.classList.add(styles.dragging);
    }
    current.dx = dx;
    const edge = (dx > 0 && step === 0) || (dx < 0 && (step === LAST_STEP || !valid(step, answers)));
    position(edge ? dx * .2 : dx);
  }

  function pointerEnd(event: PointerEvent<HTMLDivElement>, cancelled = false) {
    const current = gesture.current;
    if (!current || current.id !== event.pointerId) return;
    gesture.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    track.current?.classList.remove(styles.dragging);
    if (current.dragging) suppressClickUntil.current = event.timeStamp + 350;
    const threshold = Math.max(42, Math.min(70, event.currentTarget.clientWidth * .16));
    if (!cancelled && current.dragging && Math.abs(current.dx) >= threshold) change(current.dx < 0 ? 1 : -1, true);
    else position();
  }

  function keys(event: KeyboardEvent<HTMLDivElement>) {
    if ((event.target as HTMLElement).closest("input, select, textarea")) return;
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); change(event.key === "ArrowRight" ? 1 : -1, true); }
  }

  return <>
    <div ref={viewport} className={styles.viewport} id="question-viewport" aria-label={t("여행 취향 질문 카드", "Travel preference question cards")} aria-roledescription={t("캐러셀", "carousel")}
      onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={(event) => pointerEnd(event)} onPointerCancel={(event) => pointerEnd(event, true)} onKeyDown={keys}
      onClickCapture={(event) => { if (event.timeStamp < suppressClickUntil.current) { event.stopPropagation(); event.preventDefault(); } }}>
      <div ref={track} className={styles.track} onTransitionEnd={(event) => { if (event.target === track.current && event.propertyName === "transform" && busy.current) { clearTimeout(release.current); finish(step); } }}>
        {questions.map((question, index) => {
          const active = index === step;
          const error = forcedError?.step === index ? forcedError.text : validationHint(index, answers, t);
          return <article key={index} className={styles.slide} id={`slide-${index}`} role="group" aria-roledescription={t("슬라이드", "slide")} aria-labelledby={`question-title-${index}`} aria-hidden={!active} inert={!active}>
            <button type="button" className={styles.slideTop} aria-expanded="true" aria-controls="content-2" onClick={onCollapse}>
              <span className={styles.stepNumber}>02</span>
              <span className={styles.stepCopy}><span className={styles.stepTitle}>{t("여행 취향 알아보기", "Your travel preferences")}</span><span className={styles.stepSub}>{t(stepNames[index][0], stepNames[index][1])}</span></span>
              <span className={styles.slideCount} aria-label={`${t("답변한 질문", "Answered questions")} ${answered} / ${questions.length}`}>{pad(answered)} / {questions.length}</span>
              <span className={styles.chevron}><OnboardingIcon name="down" /></span>
            </button>
            <div className={styles.progressTrack} role="progressbar" aria-label={t("답변한 질문", "Answered questions")} aria-valuemin={0} aria-valuemax={questions.length} aria-valuenow={answered}>
              <div className={styles.progressFill} style={{ width: `${answered / questions.length * 100}%` }} />
            </div>
            <div className={styles.question}>
              <h2 tabIndex={-1} id={`question-title-${index}`}>{t(question[0], question[1])}</h2>
              <p className={styles.helper}>{t(question[2], question[3])}{isOptional(index) && <span className={styles.optional}>{t("선택", "Optional")}</span>}</p>
              <div>{body(index)}</div>
              <p className={styles.error} id={`validation-${index}`} role="status">{error}</p>
              <div className={styles.questionNav}>
                <button type="button" className={styles.previous} onClick={() => change(-1)}>{t("이전", "Back")}</button>
                <button type="button" className={styles.next} disabled={!valid(index, answers)} onClick={() => change(1)}>{index === LAST_STEP ? t("설정 완료", "Finish setup") : t("다음", "Next")}<OnboardingIcon name="arrow" size={15} /></button>
              </div>
              {isOptional(index) && <button type="button" className={styles.skip} onClick={() => skip(index)}>{t("응답하지 않고 넘어가기", "Skip this question")}</button>}
            </div>
          </article>;
        })}
      </div>
    </div>
    <div ref={footer} className={styles.carouselFooter}>
      <div className={styles.dots} aria-hidden="true">{questions.map((_, index) => <span key={index} className={styles.dot} aria-current={index === step ? "step" : undefined} />)}</div>
      <p className={styles.carouselHint}>{t("← 카드를 좌우로 밀어 이동하세요 →", "← Swipe the cards to move →")}</p>
    </div>
  </>;
}

export function PreferencesSummary({ t, answers, hasTrip, onJourney, onEdit }: { t: Translate; answers: Answers; hasTrip: boolean; onJourney: () => void; onEdit: () => void }) {
  return <div className={styles.success}>
    <div className={`${styles.successSymbol} ${styles.completionMotion}`} aria-hidden="true"><DrawnCheck className={styles.drawnCheck} /></div>
    <h2>{t("여행 취향을 모두 알아봤어요.", "Your preferences are all set.")}</h2>
    <p>{t("나를 닮은 여행의 첫걸음.", "A first step toward a trip that feels like you.")}<br />{t("언제든 답변을 다시 바꿀 수 있어요.", "You can change your answers anytime.")}</p>
    <div className={styles.summary}>
      <div><span>{t("선택 언어", "Language")}</span><strong>{t("한국어", "English")}</strong></div>
      <div><span>{t("여행 테마", "Travel themes")}</span><strong>{answers.themes.map((value) => chosenLabel("themes", value, t)).join(" · ")}</strong></div>
      <div><span>{t("함께하는 인원", "Travelers")}</span><strong>{answers.adults + answers.children + answers.infants}{t("명", " people")}</strong></div>
      <div><span>{t("가장 중요한 것", "Top priority")}</span><strong>{chosenLabel("priority", answers.priority, t)}</strong></div>
    </div>
    <button type="button" className={`${styles.next} ${styles.homeContinue}`} onClick={onJourney}>{hasTrip ? t("내 여행 이어보기", "Continue my trip") : t("여행 계획 등록하기", "Add my travel plan")}<OnboardingIcon name="arrow" size={16} /></button>
    <button type="button" className={`${styles.next} ${styles.homeContinue} ${styles.editPreferences}`} onClick={onEdit}>{t("여행 취향 수정하기", "Edit your preferences")}<OnboardingIcon name="arrow" size={16} /></button>
    <p className={styles.prototypeNote}>{t("데모 화면이에요. 답변은 이 페이지에서만 유지돼요.", "Demo preview. Answers stay in this page only.")}</p>
  </div>;
}

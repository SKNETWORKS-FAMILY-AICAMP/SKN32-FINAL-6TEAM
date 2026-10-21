"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type MouseEvent, type PointerEvent, type ReactNode } from "react";
import type { Translate } from "@/lib/i18n";
import { DrawnCheck, OnboardingIcon } from "./icons";
import {
  ACTIVITY_PICKS, answeredCount, answerLines, areaNames, areas, canPickPartySize, detailOptions, done, indoorParts, INTRO_STEP, LAST_STEP, options, partySizeOf, pickPartySize, questions,
  skip as skipQuestion, toggle, toggleArea, toggleDetail, unskip, valid, type Answers, type Area, type ChoiceKey, type QuestionId,
} from "./model";
import { AREA_ICONS, ChoiceChips, fieldOptions, OtherField, PairRows, PriorityAreas, TravelerSizes, usePressFeedback } from "./survey-fields";
import styles from "./onboarding.module.css";

const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const pad = (value: number) => String(value).padStart(2, "0");
const titleId = (index: number) => index === INTRO_STEP ? "question-title-intro" : `question-title-${index}`;

/** The survey explanation card, then the question cards on one track: tap, swipe or use the arrow keys to move. */
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
  const { touched, feedback } = usePressFeedback(onFeedback);
  const answered = answeredCount(answers);
  const introTitle = t("여행 취향 설문을 시작할게요", "A quick survey on how you travel");
  // Slide position on the track: the intro card comes first.
  const slide = step - INTRO_STEP;

  const position = useCallback((drag = 0) => {
    if (track.current) track.current.style.transform = `translateX(calc(${-slide * 100}% - ${slide * 12}px + ${drag}px))`;
  }, [slide]);

  const fit = useCallback(() => {
    const card = viewport.current?.closest("section");
    if (card && footer.current) card.style.setProperty("--question-card-height", `${Math.max(0, card.clientHeight - footer.current.offsetHeight - 1)}px`);
    const current = track.current?.children[slide] as HTMLElement | undefined;
    if (viewport.current && current?.offsetHeight) viewport.current.style.height = `${current.offsetHeight}px`;
  }, [slide]);

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
    document.getElementById(titleId(next))?.focus({ preventScroll: true });
  }

  const announcement = (index: number) => index === INTRO_STEP ? introTitle : `${index + 1} / ${questions.length}. ${t(...questions[index].title)}`;

  function change(direction: 1 | -1, fromSwipe = false) {
    if (busy.current) return;
    if (direction > 0 && step !== INTRO_STEP && !valid(step, answers)) {
      setForcedError({ step, text: t("이 카드의 선택을 마치면 다음으로 이동할 수 있어요.", "Complete this card before moving forward.") });
      position();
      return;
    }
    if (direction < 0 && step === INTRO_STEP) { if (!fromSwipe) onFirstBack(); position(); return; }
    advance(direction, fromSwipe, answers);
  }

  /** Move one card, or finish on the last card once every question is answered or skipped. */
  function advance(direction: 1 | -1, fromSwipe: boolean, current: Answers) {
    if (direction > 0 && step === LAST_STEP) {
      if (fromSwipe) { position(); return; }
      const missing = questions.findIndex((_, index) => !done(index, current));
      if (missing >= 0) { setStep(missing); onFeedback(); announce(announcement(missing)); return; }
      onComplete();
      return;
    }
    const next = step + direction;
    busy.current = true;
    setStep(next);
    onFeedback();
    announce(announcement(next));
    if (reducedMotion()) finish(next);
    else release.current = window.setTimeout(() => finish(next), 400);
  }

  function update(next: Answers) {
    setForcedError(null);
    setAnswers(unskip(next, step));
  }

  /** Apply a change made by a control, then give it the usual press feedback. */
  function press(event: MouseEvent<HTMLButtonElement>, next: Answers, key: string) {
    update(next);
    feedback(event.currentTarget, key);
  }

  function skip(index: number) {
    if (busy.current) return;
    const next = skipQuestion(answers, index);
    setForcedError(null);
    setAnswers(next);
    advance(1, false, next);
  }

  // `[2026-10-20 ST4F-665]` The card pieces are shared with the questions asked while a plan is read (`survey-fields.tsx`) — same look, same rules.
  const chips = (key: ChoiceKey) => <ChoiceChips name={key} options={fieldOptions(options[key], t)} selected={answers[key]} touched={touched}
    onPick={(event, value) => press(event, toggle(answers, key, value), `${key}:${value}`)} />;

  /** `other` opens a field for who it is; the draft stays when another choice is picked, but only `other` sends it. Under it, how many travel. */
  const party = () => <>
    {chips("party")}
    {answers.party === "other" && <OtherField t={t} id="party-other" value={answers.partyOther} onChange={(value) => update({ ...answers, partyOther: value })} />}
    {answers.party && <TravelerSizes t={t} labelId="party-size-label" size={partySizeOf(answers)} canPick={(n) => canPickPartySize(answers.party, n)} touched={touched}
      onPick={(event, n) => press(event, pickPartySize(answers, n), `partySize:${n}`)} />}
  </>;

  /** Un-picking an area clears and folds its details. Activities take exactly `ACTIVITY_PICKS`. */
  const priority = () => <PriorityAreas t={t} order={answers.priority} details={answers.details}
    areas={areas.map((area) => ({ id: area, label: t(...areaNames[area]), icon: AREA_ICONS[area], options: fieldOptions(detailOptions[area], t), exact: area === "activity" ? ACTIVITY_PICKS : undefined }))}
    onArea={(event, area) => press(event, toggleArea(answers, area as Area), `area:${area}`)}
    onDetail={(event, area, value) => press(event, toggleDetail(answers, area as Area, value), `${area}:${value}`)} />;

  const indoor = () => <PairRows t={t} touched={touched} selected={{ dining: answers.indoorDining, activity: answers.indoorActivity }}
    parts={indoorParts.map(([part, key, ko, en]) => ({ id: part, name: key, label: t(ko, en), options: fieldOptions(options[key], t) }))}
    onPick={(event, part, value) => {
      const key = indoorParts.find((entry) => entry[0] === part)![1];
      press(event, toggle(answers, key, value), `${key}:${value}`);
    }} />;

  function body(index: number): ReactNode {
    switch (questions[index].id) {
      case "party": return party();
      case "priority": return priority();
      case "indoor": return indoor();
      case "pace": return chips("pace");
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
    const edge = (dx > 0 && step === INTRO_STEP) || (dx < 0 && (step === LAST_STEP || (step !== INTRO_STEP && !valid(step, answers))));
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

  const head = (sub: string) => <>
    <button type="button" className={styles.slideTop} aria-expanded="true" aria-controls="content-2" onClick={onCollapse}>
      <span className={styles.stepNumber}>02</span>
      <span className={styles.stepCopy}><span className={styles.stepTitle}>{t("여행 취향 설문", "Travel preferences survey")}</span><span className={styles.stepSub}>{sub}</span></span>
      <span className={styles.slideCount} aria-label={`${t("답변한 질문", "Answered questions")} ${answered} / ${questions.length}`}>{pad(answered)} / {questions.length}</span>
      <span className={styles.chevron}><OnboardingIcon name="down" /></span>
    </button>
    <div className={styles.progressTrack} role="progressbar" aria-label={t("답변한 질문", "Answered questions")} aria-valuemin={0} aria-valuemax={questions.length} aria-valuenow={answered}>
      <div className={styles.progressFill} style={{ width: `${answered / questions.length * 100}%` }} />
    </div>
  </>;

  return <>
    <div ref={viewport} className={styles.viewport} id="question-viewport" aria-label={t("여행 취향 질문 카드", "Travel preference question cards")} aria-roledescription={t("캐러셀", "carousel")}
      onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={(event) => pointerEnd(event)} onPointerCancel={(event) => pointerEnd(event, true)} onKeyDown={keys}
      onClickCapture={(event) => { if (event.timeStamp < suppressClickUntil.current) { event.stopPropagation(); event.preventDefault(); } }}>
      <div ref={track} className={styles.track} onTransitionEnd={(event) => { if (event.target === track.current && event.propertyName === "transform" && busy.current) { clearTimeout(release.current); finish(step); } }}>
        <article className={styles.slide} id="slide-intro" role="group" aria-roledescription={t("슬라이드", "slide")} aria-labelledby={titleId(INTRO_STEP)} aria-hidden={step !== INTRO_STEP} inert={step !== INTRO_STEP}>
          {head(t("설문 안내", "Before you start"))}
          <div className={styles.question}>
            <h2 tabIndex={-1} id={titleId(INTRO_STEP)}>{introTitle}</h2>
            <p className={styles.helper}>{t(`${questions.length}가지 질문으로 여행 취향을 알아봐요.`, `${questions.length} short questions about how you like to travel.`)}</p>
            <ul className={styles.introList}>
              <li>{t("이 설문은 구구루트가 가볼 곳·식당·이동 방법 후보를 추천할 때 참고할 여행 취향 정보를 모아요.", "This survey gathers the travel preferences GuguRoute uses when recommending places to visit, restaurants, and ways to get around.")}</li>
              <li>{t("답해 주실수록 나에게 더 잘 맞는 후보와 결과를 추천받을 수 있어요.", "The more you answer, the better the suggestions and results can fit you.")}</li>
              <li>{t("답하고 싶지 않은 질문은 ‘응답하지 않고 넘어가기’를 눌러 건너뛸 수 있어요.", "Rather not answer a question? Tap “Skip this question” to move on.")}</li>
            </ul>
            <div className={styles.questionNav}>
              <button type="button" className={styles.previous} onClick={() => change(-1)}>{t("이전", "Back")}</button>
              <button type="button" className={styles.next} onClick={() => change(1)}>{t("시작하기", "Let’s begin")}<OnboardingIcon name="arrow" size={15} /></button>
            </div>
          </div>
        </article>
        {questions.map((question, index) => {
          const active = index === step;
          const error = forcedError?.step === index ? forcedError.text : "";
          return <article key={index} className={styles.slide} id={`slide-${index}`} role="group" aria-roledescription={t("슬라이드", "slide")} aria-labelledby={titleId(index)} aria-hidden={!active} inert={!active}>
            {head(t(...question.name))}
            <div className={styles.question}>
              <h2 tabIndex={-1} id={titleId(index)}>{t(...question.title)}</h2>
              <p className={styles.helper}>{t(...question.helper)}</p>
              <div>{body(index)}</div>
              <p className={styles.error} id={`validation-${index}`} role="status">{error}</p>
              <div className={styles.questionNav}>
                <button type="button" className={styles.previous} onClick={() => change(-1)}>{t("이전", "Back")}</button>
                <button type="button" className={styles.next} disabled={!valid(index, answers)} onClick={() => change(1)}>{index === LAST_STEP ? t("설문 마치기", "Finish the survey") : t("다음", "Next")}<OnboardingIcon name="arrow" size={15} /></button>
              </div>
              <button type="button" className={styles.skip} onClick={() => skip(index)}>{t("응답하지 않고 넘어가기", "Skip this question")}</button>
            </div>
          </article>;
        })}
      </div>
    </div>
    <div ref={footer} className={styles.carouselFooter}>
      <div className={styles.dots} aria-hidden="true">{[INTRO_STEP, ...questions.keys()].map((index) => <span key={index} className={styles.dot} aria-current={index === step ? "step" : undefined} />)}</div>
      <p className={styles.carouselHint}>{t("← 카드를 좌우로 밀어 이동하세요 →", "← Swipe the cards to move →")}</p>
    </div>
  </>;
}

/** The finished-survey cards: the language and who's coming first, then how the trip should run. */
const summaryCards: readonly { title: readonly [ko: string, en: string]; ids: readonly QuestionId[] }[] = [
  { title: ["기본사항", "The basics"], ids: ["party"] },
  { title: ["여행 방식", "How you travel"], ids: ["priority", "indoor", "pace"] },
];

/**
 * The answers on two cards that slide sideways like the intro's how-it-works cards: touch and trackpads scroll
 * natively, a mouse drags, and the buttons below step one card. Moving only shows a card; no answer changes.
 */
export function PreferencesSummary({ t, answers, hasTrip, onJourney, onEdit }: { t: Translate; answers: Answers; hasTrip: boolean; onJourney: () => void; onEdit: () => void }) {
  const slides = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; left: number; from: number } | null>(null);
  const [slide, setSlide] = useState(0);
  const [dragging, setDragging] = useState(false);
  const titles = summaryCards.map((card) => t(...card.title));
  const lines = (values: string[]) => values.map((line) => <span key={line} className={styles.summaryLine}>{line}</span>);

  const slideItems = () => [...(slides.current?.children ?? [])] as HTMLElement[];

  function trackSlide() {
    const [first, second] = slideItems();
    if (!first || !second || !slides.current) return;
    setSlide(Math.min(summaryCards.length - 1, Math.round(slides.current.scrollLeft / (second.offsetLeft - first.offsetLeft))));
  }

  function showSlide(index: number) {
    const items = slideItems();
    if (!items[index]) return;
    slides.current?.scrollTo({ left: items[index].offsetLeft - items[0].offsetLeft, behavior: reducedMotion() ? "instant" : "smooth" });
  }

  /** Mouse drag on PC. Touch and trackpads keep the browser's own swipe, which leaves vertical page scrolling alone. */
  function startDrag(event: PointerEvent<HTMLDivElement>) {
    if (event.pointerType !== "mouse" || event.button !== 0 || !slides.current) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { x: event.clientX, left: slides.current.scrollLeft, from: slide };
    setDragging(true);
  }

  function moveDrag(event: PointerEvent<HTMLDivElement>) {
    if (drag.current && slides.current) slides.current.scrollLeft = drag.current.left - (event.clientX - drag.current.x);
  }

  /** Past 40px, move one card in the dragged direction; otherwise return. */
  function endDrag() {
    const start = drag.current, root = slides.current, [first, second] = slideItems();
    drag.current = null;
    if (!start || !root || !first || !second) return setDragging(false);
    const step = second.offsetLeft - first.offsetLeft, travelled = root.scrollLeft - start.left;
    const target = Math.min(summaryCards.length - 1, Math.max(0, start.from + (Math.abs(travelled) < 40 ? 0 : Math.sign(travelled))));
    // Snapping stays off until the glide ends, so the browser does not re-snap halfway.
    if (Math.abs(root.scrollLeft - Math.min(target * step, root.scrollWidth - root.clientWidth)) < 1) return setDragging(false);
    root.addEventListener("scrollend", () => setDragging(false), { once: true });
    showSlide(target);
  }

  return <div className={styles.success}>
    <div className={`${styles.successSymbol} ${styles.completionMotion}`} aria-hidden="true"><DrawnCheck className={styles.drawnCheck} /></div>
    <h2>{t("여행 취향 설문을 마쳤어요", "Survey finished")}</h2>
    <p>{t("나의 여행 취향을 확인해요.", "Here’s how you like to travel.")}<br />{t("옆으로 넘겨 선택한 답변을 확인해 주세요.", "Swipe sideways to review your answers.")}</p>
    <div className={styles.summaryCarousel} role="region" aria-roledescription={t("캐러셀", "carousel")} aria-label={t("나의 여행 취향", "Your travel preferences")}>
      <div ref={slides} className={`${styles.summarySlides} ${dragging ? styles.summaryDragging : ""}`} onScroll={trackSlide} onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={endDrag} onPointerCancel={endDrag}>
        {summaryCards.map((card, index) => <section key={card.title[1]} className={styles.summaryCard} role="group" aria-roledescription={t("슬라이드", "slide")}
          aria-label={`${index + 1} / ${summaryCards.length} · ${titles[index]}`} aria-hidden={index !== slide}>
          <h3>{titles[index]}</h3>
          <div className={styles.summary}>
            {index === 0 && <div><span>{t("선택 언어", "Language")}</span><strong>{lines([t("한국어", "English")])}</strong></div>}
            {/* Priorities keep the picking order — the same order the survey sends. */}
            {card.ids.map((id) => <div key={id}><span>{t(...questions.find((question) => question.id === id)!.name)}</span><strong>{lines(answerLines(id, answers, t))}</strong></div>)}
          </div>
        </section>)}
      </div>
      <div className={styles.summaryNav}>
        <button type="button" onClick={() => showSlide(slide - 1)} aria-disabled={slide === 0} aria-label={t("이전 카드", "Previous card")}><span aria-hidden="true">←</span></button>
        <p aria-live="polite">{slide + 1} / {summaryCards.length} · {titles[slide]}</p>
        <button type="button" onClick={() => showSlide(slide + 1)} aria-disabled={slide === summaryCards.length - 1} aria-label={t("다음 카드", "Next card")}><span aria-hidden="true">→</span></button>
      </div>
    </div>
    <button type="button" className={`${styles.next} ${styles.homeContinue}`} onClick={onJourney}>{hasTrip ? t("내 여행 이어보기", "Continue my trip") : t("여행 계획 등록하기", "Add my travel plan")}<OnboardingIcon name="arrow" size={16} /></button>
    <button type="button" className={`${styles.next} ${styles.homeContinue} ${styles.editPreferences}`} onClick={onEdit}>{t("여행 취향 수정하기", "Edit your preferences")}<OnboardingIcon name="arrow" size={16} /></button>
    <p className={styles.savedNote}>{t("답변은 이 브라우저에 저장돼요. 여행을 등록할 때 함께 보내 일정 확인에 써요.", "Your answers are saved in this browser and sent with your trip to check it.")}</p>
  </div>;
}

"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { DeviceFrame } from "@/components/layout/device-frame";
import { Scene, type ScenePulse, type SceneStage } from "@/components/layout/scene";
import { routes } from "@/lib/routes";
import { useT } from "@/lib/settings";
import { useDocumentTitle } from "@/lib/use-document-title";
import { OnboardingIcon } from "./icons";
import { questions } from "./model";
import { useOnboarding } from "./onboarding-state";
import { PreferencesSummary, QuestionCarousel } from "./preferences";
import { TermsCardBody, TermsReader } from "./terms";
import styles from "./onboarding.module.css";

/** Terms and travel preferences before the first plan. Everything stays in page state. */
export function Onboarding() {
  const t = useT();
  const router = useRouter();
  const [state, setState] = useOnboarding();
  const [termsOpen, setTermsOpen] = useState(false);
  const [firstRender] = useState(() => !state.agreed && state.open === null);
  const [sceneStage, setSceneStage] = useState<SceneStage>(state.open ?? 0);
  const [pulse, setPulse] = useState<ScenePulse>();
  const [consentMotion, setConsentMotion] = useState(false);
  const [message, setMessage] = useState("");
  const cards = useRef<Record<1 | 2, HTMLElement | null>>({ 1: null, 2: null });
  useDocumentTitle(t("triPilot · 여행 시작 설정", "triPilot · Travel setup"));

  const feedback = useCallback((kind: ScenePulse["kind"] = "soft") => setPulse((current) => ({ kind, id: (current?.id ?? 0) + 1 })), []);

  function openCard(card: 1 | 2 | null) {
    if (card === 2 && !state.agreed) return;
    setState((current) => ({ ...current, open: card }));
    if (card !== null) setSceneStage(card);
    feedback();
  }

  // The expanded card takes focus, as the mockup's fixed card does.
  const opened = state.open;
  useEffect(() => {
    if (opened === null) return;
    const frame = requestAnimationFrame(() => cards.current[opened]?.querySelector<HTMLElement>("button:not(:disabled)")?.focus({ preventScroll: true }));
    return () => cancelAnimationFrame(frame);
  }, [opened]);

  useEffect(() => {
    if (opened === null || termsOpen) return;
    function escape(event: KeyboardEvent) {
      if (event.key !== "Escape" || opened === null) return;
      setState((current) => ({ ...current, open: null }));
      cards.current[opened]?.querySelector<HTMLElement>(`.${styles.cardHead}`)?.focus({ preventScroll: true });
    }
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [opened, termsOpen, setState]);

  const markRead = useCallback(() => setState((current) => current.read ? current : { ...current, read: true }), [setState]);

  function agree(checked: boolean) {
    if (!state.read) return;
    setState((current) => ({ ...current, agreed: checked, open: 1, complete: checked ? current.complete : false }));
    setConsentMotion(checked);
    feedback(checked ? "complete" : "soft");
  }

  function closeTerms() {
    setTermsOpen(false);
    requestAnimationFrame(() => document.querySelector<HTMLElement>('[data-action="read-terms"]')?.focus({ preventScroll: true }));
  }

  function complete() {
    setState((current) => ({ ...current, complete: true, open: 2 }));
    feedback("complete");
    setMessage(t("여행 취향 설정을 완료했어요.", "Your preferences are complete."));
  }

  const expanded = state.open !== null;
  const cardHead = (card: 1 | 2, title: string, sub: string, disabled: boolean, done: boolean) => <button type="button" className={styles.cardHead} aria-expanded={state.open === card} aria-controls={`content-${card}`} disabled={disabled}
    onClick={() => { const closing = state.open === card; openCard(closing ? null : card); }}>
    <span className={styles.stepNumber}>{done ? "✓" : `0${card}`}</span>
    <span className={styles.stepCopy}><span className={styles.stepTitle}>{title}</span><span className={styles.stepSub}>{sub}</span></span>
    <span className={styles.chevron}><OnboardingIcon name="down" /></span>
  </button>;
  const card = (id: 1 | 2, done: boolean, head: ReactNode, content: ReactNode) => <section ref={(node) => { cards.current[id] = node; }} id={`card-${id}`} data-card={id}
    className={`${styles.card} ${state.open === id ? styles.active : ""} ${done ? styles.done : ""}`} inert={expanded && state.open !== id}>
    {head}
    <div className={styles.cardContent} id={`content-${id}`} inert={state.open !== id} aria-hidden={state.open !== id}><div className={styles.contentInner}><div className={styles.cardPadding}><div className={styles.divider} />{content}</div></div></div>
  </section>;

  return <DeviceFrame headerInert={termsOpen}>
    <div className={styles.setup} data-terms={termsOpen}>
      <Scene stage={sceneStage} step={state.step} totalSteps={questions.length} complete={state.complete} pulse={pulse} sizes="(max-width: 720px) 100vw, 402px" />
      <div className={styles.scroller} data-locked={expanded} inert={termsOpen}>
        <main id="main-content" className={`${styles.phone} ${firstRender ? styles.firstRender : ""}`}>
          <section className={styles.intro} inert={expanded}>
            <div className={styles.eyebrow}><span className={styles.eyebrowDot} />{t("당신다운 여행의 시작", "A LITTLE ABOUT YOU")}</div>
            <h1>{t("당신의 여행,", "Your next journey.")}<br />{t("취향부터 맞춰요.", "Made more you.")}</h1>
            <p>{t("약관을 확인하고,", "Review the terms,")}<br />{t("좋아하는 것부터 함께 알아볼게요.", "then tell us what you love.")}</p>
          </section>
          <div className={styles.stack}>
            {card(1, state.agreed,
              cardHead(1, t("약관 동의", "Terms & consent"), state.agreed ? t("필수 내용을 확인했어요.", "Required consent completed.") : t("시작하기 전에 확인해 주세요.", "A quick check before you begin."), false, state.agreed),
              <TermsCardBody t={t} read={state.read} agreed={state.agreed} consentMotion={consentMotion} onReadTerms={() => setTermsOpen(true)} onAgree={agree} onContinue={() => { if (state.agreed) openCard(2); }} />)}
            {card(2, state.complete,
              cardHead(2, t("여행 취향 알아보기", "Your travel preferences"), state.complete ? t(`${questions.length}가지 질문을 모두 마쳤어요.`, `All ${questions.length} questions completed.`) : t(`${questions.length}가지 질문으로 더 나다운 여행.`, `${questions.length} questions for a trip that fits you.`), !state.agreed, state.complete),
              state.complete
                ? <PreferencesSummary t={t} answers={state.answers} hasTrip={Boolean(state.activeTripId)}
                  onJourney={() => router.push(state.activeTripId ? routes.trip(state.activeTripId) : routes.newTrip)}
                  onEdit={() => setState((current) => ({ ...current, complete: false, step: 0, open: 2 }))} />
                : state.open === 2 && <QuestionCarousel t={t} answers={state.answers} step={state.step}
                  setAnswers={(answers) => setState((current) => ({ ...current, answers }))}
                  setStep={(step) => setState((current) => ({ ...current, step }))}
                  onFirstBack={() => openCard(1)} onComplete={complete} onCollapse={() => openCard(null)} onFeedback={feedback} announce={setMessage} />)}
          </div>
          <footer className={styles.bottomNote} inert={expanded}><span className={styles.leaf}><OnboardingIcon name="leaf" size={17} /></span>{t("정답은 없어요. 당신이 좋아하는 여행이면 충분해요.", "There’s no right answer. Just the journey you love.")}</footer>
        </main>
      </div>
      {termsOpen && <TermsReader t={t} read={state.read} agreed={state.agreed} onRead={markRead} onClose={closeTerms}
        onAgree={(checked) => { agree(checked); if (checked) { setTermsOpen(false); requestAnimationFrame(() => document.getElementById("terms-check")?.focus({ preventScroll: true })); } }} />}
      <div className="sr-only" aria-live="polite">{message}</div>
    </div>
  </DeviceFrame>;
}

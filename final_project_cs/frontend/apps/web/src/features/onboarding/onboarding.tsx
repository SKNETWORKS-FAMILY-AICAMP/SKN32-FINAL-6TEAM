"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { DeviceFrame } from "@/components/layout/device-frame";
import { LanguageButton } from "@/components/ui/language-picker";
import { requiredAgreed, type ConsentCode } from "@/features/consent/consent-model";
import { saveConsents } from "@/features/consent/consent-sync";
import { Scene, type ScenePulse, type SceneStage } from "@/components/layout/scene";
import { useTrips } from "@/features/trip/use-trip";
import { localPath } from "@/lib/live/auth";
import { nextIsReplace } from "@/lib/nav-history";
import { useProfile } from "@/lib/profile";
import { saveDiscordWebhook, webhookWaiting } from "@/lib/webhook";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import { useDocumentTitle } from "@/lib/use-document-title";
import { ContactBody } from "./contact";
import { OnboardingIcon } from "./icons";
import { discordWebhookProblem, INTRO_STEP, questions } from "./model";
import { useOnboarding, useOnboardingReady } from "./onboarding-state";
import { PreferencesSummary, QuestionCarousel } from "./preferences";
import { TermsCardBody, TermsReader, termsDoc } from "./terms";
import styles from "./onboarding.module.css";

/**
 * ★`[2026-10-12 사용자 지시]` The terms card opens with its animation once. The consent gate first shows the open terms while it checks the server,
 * then sends the customer to `/start?terms=required` — that second drawing of the same card is shown without the opening animation.
 */
let termsShownOnce = false;

/**
 * Discord alerts, terms and travel preferences. Everything stays in page state.
 * ★`[2026-10-16 사용자 결정 — ST4F-601]` Two ways in, each showing only its own cards:
 *   - `termsRequired` — sent here because a screen needs the terms (the consent gate). Only the terms card; agreeing goes back to `returnTo`
 *     (the screen the customer was opening), replacing this one so the browser's back does not land on finished terms.
 *   - otherwise — the preference survey (menu 「여행 취향 설문」, 「취향 설정하기」). Agreed: the survey card opens; not yet: the terms card first, and agreeing opens the survey in place.
 *   The Discord card shows to a signed-in member only — a guest gets no alerts (web README 「게스트」).
 */
export function Onboarding({ termsRequired = false, returnTo = null }: { termsRequired?: boolean; returnTo?: string | null } = {}) {
  const [quietOpen] = useState(() => termsRequired && termsShownOnce);
  useEffect(() => { termsShownOnce = termsRequired && !quietOpen; }, [termsRequired, quietOpen]);
  const t = useT();
  const { language } = useSettings();
  const router = useRouter();
  const [storedState, setState] = useOnboarding();
  const state = termsRequired && !storedState.agreed ? { ...storedState, open: 1 as const } : storedState;
  // ★「Continue my trip」 follows the server's list (newest first), not a value this page happened to see: another tab or device counts too.
  const latestTrip = useTrips().data?.[0];
  const member = useProfile()?.session?.kind === "member";
  const showContact = !termsRequired && member;
  const showSurvey = !termsRequired;
  const ready = useOnboardingReady();
  // Only a screen of this app, never the terms screen itself (that would loop).
  const safeReturn = returnTo && localPath(returnTo) === returnTo && !returnTo.startsWith(routes.start) ? returnTo : null;
  // The document whose full text is open (null = none). `termsOpen` is what the rest of the screen reacts to.
  const [readerCode, setReaderCode] = useState<ConsentCode | null>(null);
  const termsOpen = readerCode !== null;
  const [firstRender] = useState(() => !state.agreed && state.open === null);
  const [sceneStage, setSceneStage] = useState<SceneStage>(state.open ?? 0);
  const [pulse, setPulse] = useState<ScenePulse>();
  const [consentMotion, setConsentMotion] = useState(false);
  const [message, setMessage] = useState("");
  const [webhookError, setWebhookError] = useState(false);
  const webhookInput = useRef<HTMLInputElement>(null);
  /** Focus the field once card 0 has opened because its check failed. */
  const focusWebhook = useRef(false);
  // The webhook this screen last sent: the server never answers it back, so this is how a second pass does not resend it.
  const sentWebhook = useRef<string | null>(null);
  const cards = useRef<Record<0 | 1 | 2, HTMLElement | null>>({ 0: null, 1: null, 2: null });
  useDocumentTitle(termsRequired ? t("구구루트 · 약관 동의", "GuguRoute · Terms & consent") : t("구구루트 · 여행 취향 설문", "GuguRoute · Travel preferences"));

  // The survey way in opens its card at once — the terms card first when they are not agreed yet (the same for every survey link — flow check F15).
  useEffect(() => {
    // Which card is open follows the consent store once it has been read.
    if (!termsRequired && ready) setState((current) => ({ ...current, open: storedState.agreed ? 2 : 1 }));
  }, [termsRequired, ready, storedState.agreed, setState]);

  const feedback = useCallback((kind: ScenePulse["kind"] = "soft") => setPulse((current) => ({ kind, id: (current?.id ?? 0) + 1 })), []);

  /**
   * The only check on the optional Discord alerts card, run when moving on to terms or preferences. A blank (or spaces-only)
   * field never stops anything and needs no visit to the card; a written webhook must be well formed, or the card opens
   * with the error and the field focused, keeping what was typed. Passing trims the ends.
   * ★`[2026-10-03]` The webhook goes to the server (`lib/webhook.ts`) — at once with a user key, else when the first trip
   *   gives one (it waits in page memory, never in storage: it is a secret). Blank leaves a saved one alone; it is
   *   removed on My page. A refusal never stops the customer here (the format was checked above).
   */
  function contactPasses(): boolean {
    if (!showContact) return true;
    const wrong = Boolean(discordWebhookProblem(state.webhook));
    setWebhookError(wrong);
    if (wrong) {
      if (state.open === 0) webhookInput.current?.focus();
      else {
        focusWebhook.current = true;
        setState((current) => ({ ...current, open: 0 }));
        setSceneStage(0);
      }
      return false;
    }
    const webhook = state.webhook.trim();
    if (state.webhook !== webhook) setState((current) => ({ ...current, webhook: current.webhook.trim() }));
    return true;
  }

  /**
   * ★`[2026-10-05]` The Discord address is sent to the server only once the customer has agreed to the alert-channel item (`alert_channel`): it is personal data the
   *   customer chooses to hand over, so it is collected after the consent, not before. Typed without that consent, it is dropped here (and the card said so).
   */
  function flushWebhook(allowed: boolean) {
    const webhook = state.webhook.trim();
    if (!allowed) {
      if (webhook) setState((current) => ({ ...current, webhook: "" }));
      return;
    }
    if ((webhook || webhookWaiting()) && webhook !== sentWebhook.current) {
      sentWebhook.current = webhook;
      saveDiscordWebhook(webhook || null, language).catch(() => { sentWebhook.current = null; });
    }
  }

  function openCard(card: 0 | 1 | 2 | null) {
    if (card === 2 && !state.agreed) return;
    if ((card === 1 || card === 2) && !contactPasses()) return;
    setState((current) => ({ ...current, open: card }));
    if (card !== null) setSceneStage(card);
    feedback();
  }

  function editWebhook(webhook: string) {
    setState((current) => ({ ...current, webhook }));
    if (webhookError && !discordWebhookProblem(webhook)) setWebhookError(false);
  }

  // The expanded card takes focus, as the mockup's fixed card does — the webhook field when the card 0 check sent us here.
  const opened = state.open;
  useEffect(() => {
    if (opened === null) return;
    const frame = requestAnimationFrame(() => {
      const target = opened === 0 && focusWebhook.current ? webhookInput.current : cards.current[opened]?.querySelector<HTMLElement>("button:not(:disabled)");
      focusWebhook.current = false;
      target?.focus({ preventScroll: true });
    });
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

  /** Tick or untick one item (`[2026-10-05 사용자 지시]` a required item too, at once - the full text is in the card, and 「전문 보기」 only enlarges it). */
  function toggle(code: ConsentCode, checked: boolean) {
    setState((current) => ({ ...current, choices: { ...current.choices, [code]: checked }, open: 1 }));
    setConsentMotion(checked);
    feedback(checked ? "complete" : "soft");
  }

  /**
   * 「동의하고 다음으로」: this press is what records the consent (the browser's copy at once, the server's record right behind it).
   * ★`[2026-10-06 사용자 지시]` The first agreement goes straight on to registering a plan — the preference survey is no longer part of the first run
   *   (it stays here as the third card, opened from the menu / My page).
   * ★`[2026-10-12 사용자 지시]` A customer who already agreed (e.g. sent back here because the consent check failed) goes to My trips —
   *   this press never opens the preference card (「여행 취향 설정 완료」 kept coming back after re-agreeing).
   * ★`[2026-10-16 사용자 결정 — ST4F-601]` Sent here by the gate: back to the screen being opened (`returnTo`), replacing this one; without it, as above.
   *   Come in for the survey: the survey card opens in place (it used to leave for the plan screen — flow check F3 · F14).
   */
  function continueTerms() {
    if (!requiredAgreed(state.choices)) return;
    const firstAgreement = !state.agreed;
    void saveConsents(state.choices, language);
    flushWebhook(showContact && state.choices.alert_channel);
    feedback("complete");
    if (termsRequired) {
      nextIsReplace();
      router.replace(safeReturn ?? (firstAgreement ? routes.newTrip : routes.trips));
      return;
    }
    setState((current) => ({ ...current, open: 2 }));
    setSceneStage(2);
  }

  function closeTerms() {
    const code = readerCode;
    setReaderCode(null);
    requestAnimationFrame(() => document.querySelector<HTMLElement>(code ? `[data-action="read-terms"][data-doc="${code}"]` : '[data-action="read-terms"]')?.focus({ preventScroll: true }));
  }

  function complete() {
    setState((current) => ({ ...current, complete: true, open: 2 }));
    feedback("complete");
    setMessage(t("여행 취향 설정을 완료했어요.", "Your preferences are complete."));
  }

  const expanded = state.open !== null;
  // Card 0 is optional: a bell mark and an `optional` badge instead of a step number.
  const cardHead = (card: 0 | 1 | 2, title: string, sub: string, disabled: boolean, done: boolean, badge?: ReactNode) => <button type="button" className={styles.cardHead} aria-expanded={state.open === card} aria-controls={`content-${card}`} disabled={disabled}
    onClick={() => { const closing = state.open === card; openCard(closing ? null : card); }}>
    <span className={styles.stepNumber}>{card === 0 ? <OnboardingIcon name="bell" /> : done ? "✓" : `0${card}`}</span>
    <span className={styles.stepCopy}><span className={styles.stepTitle}>{title}{badge}</span><span className={styles.stepSub}>{sub}</span></span>
    <span className={styles.chevron}><OnboardingIcon name="down" /></span>
  </button>;
  const card = (id: 0 | 1 | 2, done: boolean, head: ReactNode, content: ReactNode) => <section ref={(node) => { cards.current[id] = node; }} id={`card-${id}`} data-card={id}
    className={`${styles.card} ${state.open === id ? styles.active : ""} ${done ? styles.done : ""}`} inert={expanded && state.open !== id}>
    {head}
    <div className={styles.cardContent} id={`content-${id}`} inert={state.open !== id} aria-hidden={state.open !== id}><div className={styles.contentInner}><div className={styles.cardPadding}><div className={styles.divider} />{content}</div></div></div>
  </section>;

  return <DeviceFrame headerInert={termsOpen} headerExtra={<LanguageButton />}>
    <div className={styles.setup} data-terms={termsOpen} data-quiet-open={quietOpen || undefined}>
      <Scene stage={sceneStage} step={state.step - INTRO_STEP} totalSteps={questions.length + 1} complete={state.complete} pulse={pulse} sizes="(max-width: 720px) 100vw, 402px" />
      <div className={styles.scroller} data-locked={expanded} inert={termsOpen}>
        <main id="main-content" className={`${styles.phone} ${firstRender ? styles.firstRender : ""}`}>
          {/* ★`[2026-10-16 ST4F-601 F4]` The heading says what this screen is for — it used to promise preferences first on the terms screen too. */}
          <section className={styles.intro} inert={expanded}>
            {termsRequired
              ? <><h1>{t("약관 동의", "Terms & consent")}</h1><p>{safeReturn ? t("동의하면 보던 화면으로 돌아가요.", "Agree and you go back to the screen you were opening.") : t("동의하면 바로 시작해요.", "Agree and you can start.")}</p></>
              : <><h1>{t("여행 취향 설문", "Travel preferences")}</h1><p>{storedState.agreed ? t(`${questions.length}가지 질문에 답해 주세요. 나중에 다시 고칠 수 있어요.`, `Answer ${questions.length} questions. You can change them later.`) : t("설문을 하려면 먼저 약관에 동의해 주세요.", "Please agree to the terms before the questions.")}</p></>}
          </section>
          <div className={styles.stack}>
            {showContact && card(0, false,
              cardHead(0, t("디스코드 알림", "Discord alerts"), state.webhook.trim() ? t("입력했어요 · 설정에서 바꿀 수 있어요", "Entered · you can change it in Settings") : t("여행 알림을 받을 디스코드 채널.", "The Discord channel for your trip alerts."), false, false,
                <span className={styles.optional}>{t("선택", "Optional")}</span>),
              <ContactBody t={t} webhook={state.webhook} webhookError={webhookError} webhookInput={webhookInput}
                onWebhook={editWebhook} onContinue={() => openCard(1)} />)}
            {card(1, state.agreed,
              cardHead(1, t("약관 동의", "Terms & consent"), state.agreed ? t("필수 내용을 확인했어요.", "Required consent completed.") : t("시작하기 전에 확인해 주세요.", "A quick check before you begin."), false, state.agreed),
              <>{termsRequired && !state.agreed && <p className={styles.termsIntro} role="status">{t("이용을 위해서는 필수 약관 동의가 필요해요.", "Please agree to the required terms to use the service.")}</p>}<TermsCardBody t={t} choices={state.choices} consentMotion={consentMotion} alertTyped={showContact && Boolean(state.webhook.trim())}
                onReadDoc={setReaderCode} onToggle={toggle} onContinue={continueTerms} /></>)}
            {showSurvey && card(2, state.complete,
              cardHead(2, t("여행 취향 알아보기", "Your travel preferences"), state.complete ? t(`${questions.length}가지 질문을 모두 마쳤어요.`, `All ${questions.length} questions completed.`) : t(`${questions.length}가지 질문으로 더 나다운 여행.`, `${questions.length} questions for a trip that fits you.`), !state.agreed, state.complete),
              state.complete
                ? <PreferencesSummary t={t} answers={state.answers} hasTrip={Boolean(latestTrip)}
                  onJourney={() => router.push(latestTrip ? routes.trip(latestTrip.id) : routes.newTrip)}
                  onEdit={() => setState((current) => ({ ...current, complete: false, step: INTRO_STEP, open: 2 }))} />
                : state.open === 2 && <QuestionCarousel t={t} answers={state.answers} step={state.step}
                  setAnswers={(answers) => setState((current) => ({ ...current, answers }))}
                  setStep={(step) => setState((current) => ({ ...current, step }))}
                  onFirstBack={() => openCard(1)} onComplete={complete} onCollapse={() => openCard(null)} onFeedback={feedback} announce={setMessage} />)}
          </div>
          {showSurvey && <footer className={styles.bottomNote} inert={expanded}><span className={styles.leaf}><OnboardingIcon name="leaf" size={17} /></span>{t("정답은 없어요. 당신이 좋아하는 여행이면 충분해요.", "There’s no right answer. Just the journey you love.")}</footer>}
        </main>
      </div>
      {readerCode && termsDoc(readerCode) && <TermsReader t={t} doc={termsDoc(readerCode)!} agreed={state.choices[readerCode]} onClose={closeTerms}
        onAgree={(checked) => { const code = readerCode; toggle(code, checked); if (checked) { setReaderCode(null); requestAnimationFrame(() => document.getElementById(`consent-${code}`)?.focus({ preventScroll: true })); } }} />}
      <div className="sr-only" aria-live="polite">{message}</div>
    </div>
  </DeviceFrame>;
}

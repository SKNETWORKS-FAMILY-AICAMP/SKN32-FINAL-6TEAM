"use client";

import { createContext, useContext, useEffect, useMemo, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { z } from "zod";
import { noConsents, type ConsentMap } from "@/features/consent/consent-model";
import { readConsents, useRequiredConsents } from "@/features/consent/consent-store";
import { initialAnswers, INTRO_STEP, questions, type Answers } from "./model";

export interface OnboardingState {
  /** The documents whose full text was scrolled to the end on this page (page state only - the proof of a consent is the server's record, not this). */
  /**
   * ★`[2026-10-05]` Derived, never stored here: the required consents (service terms, personal data) are on record for the CURRENT terms version
   * (`features/consent/consent-store.ts`). A newer terms version makes this false again, so the customer is asked once more.
   */
  agreed: boolean;
  /** The boxes as the customer has ticked them on the terms card, before pressing 「동의하고 다음으로」 (that press is what records them). */
  choices: ConsentMap;
  /** Expanded card: 0 Discord alerts (optional, unnumbered), 1 terms, 2 preferences. The language card lives in the settings menu. */
  open: 0 | 1 | 2 | null;
  /**
   * Discord webhook URL for trip alerts, as typed. Optional, and page state only: it is never written to
   * this browser's storage (it is a secret). Leaving the card sends it to the server (`lib/webhook.ts`).
   */
  webhook: string;
  step: number;
  complete: boolean;
  answers: Answers;
}

const initial: OnboardingState = { agreed: false, choices: noConsents(), open: null, webhook: "", step: INTRO_STEP, complete: false, answers: initialAnswers };
const Context = createContext<[OnboardingState, Dispatch<SetStateAction<OnboardingState>>] | null>(null);
const ReadyContext = createContext(false);

/**
 * `[2026-10-01 user decision]` The start screen is asked once. What it collected — the terms, the preference answers and
 * where the questions stand — is kept in this browser and read back on the next visit, so a reload or a later visit does
 * not start over. Nothing here is sent to the server. ★Which card is open stays page-only. 「Continue my trip」 is not kept here: it reads the server's trip list (`useTrips`).
 */
const STORAGE_KEY = "tripilot.web.onboarding.v1";
const area = z.enum(["food", "activity", "mobility"]);
const text = z.string().max(200);
const saved = z.object({
  complete: z.boolean(),
  step: z.number().int().min(INTRO_STEP).max(questions.length - 1),
  answers: z.object({
    theme: text, party: text, partyOther: text, priority: z.array(area).max(3),
    details: z.object({ food: z.array(text).max(8), activity: z.array(text).max(8), mobility: z.array(text).max(8) }),
    indoorDining: text, indoorActivity: text, onDisruption: text, pace: text, skipped: z.array(z.number().int().min(0).max(questions.length - 1)).max(questions.length),
  }),
});
type Saved = z.infer<typeof saved>;

function load(): Saved | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = saved.safeParse(JSON.parse(raw));
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}

function save(state: OnboardingState) {
  const value: Saved = { complete: state.complete, step: state.step, answers: state.answers };
  try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value)); } catch { /* private window: it lives for this page only */ }
}

/**
 * The start screen's answers, remembered in this browser. ★The first render is always the empty state (so the server
 * render and the first client render agree); the saved state is read right after, and nothing is written before that read.
 */
export function OnboardingProvider({ children }: { children: ReactNode }) {
  const value = useState(initial);
  const [state, setState] = value;
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const restored = load();
    // Browser storage can only be read after hydration, or the server render and the first client render disagree.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reading an external store once, on purpose
    setState((current) => ({ ...current, ...(restored ?? {}), choices: readConsents() }));
    setReady(true);
  }, [setState]);

  useEffect(() => {
    if (ready) save(state);
  }, [ready, state.complete, state.step, state.answers]);   // eslint-disable-line react-hooks/exhaustive-deps

  // The consents are not this state's: they come from the consent store (browser copy of the server's record), so a change made anywhere else
  // (My page, the server's record read back after a sign-in) shows here too.
  const agreed = useRequiredConsents();
  const shown = useMemo<[OnboardingState, Dispatch<SetStateAction<OnboardingState>>]>(() => [{ ...state, agreed }, setState], [state, agreed, setState]);

  return <Context.Provider value={shown}><ReadyContext.Provider value={ready}>{children}</ReadyContext.Provider></Context.Provider>;
}

export function useOnboarding() {
  const value = useContext(Context);
  if (!value) throw new Error("useOnboarding must be used inside OnboardingProvider");
  return value;
}

/** False until the saved answers have been read back; a screen that decides from them waits for this. */
export function useOnboardingReady() {
  return useContext(ReadyContext);
}

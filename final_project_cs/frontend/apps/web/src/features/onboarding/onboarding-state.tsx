"use client";

import { createContext, useContext, useEffect, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { z } from "zod";
import { CONTACT_CHANGED_EVENT, readRecoveryEmail } from "@/lib/contact";
import { initialAnswers, INTRO_STEP, questions, type Answers } from "./model";

export interface OnboardingState {
  /** The full terms were scrolled to the end at least once. */
  read: boolean;
  agreed: boolean;
  /** Expanded card: 0 recovery email (optional, unnumbered), 1 terms, 2 preferences. The language card lives in the settings menu. */
  open: 0 | 1 | 2 | null;
  /**
   * Recovery email draft, as typed. Optional: blank means "not entered". It follows the email kept in this browser
   * (`lib/contact.ts`, the one My page edits) and is written there when the customer leaves the email card.
   */
  email: string;
  step: number;
  complete: boolean;
  answers: Answers;
  /** Trip that reached management in this page session, for “Continue my trip”. */
  activeTripId: string | null;
}

const initial: OnboardingState = { read: false, agreed: false, open: null, email: "", step: INTRO_STEP, complete: false, answers: initialAnswers, activeTripId: null };
const Context = createContext<[OnboardingState, Dispatch<SetStateAction<OnboardingState>>] | null>(null);
const ReadyContext = createContext(false);

/**
 * `[2026-10-01 user decision]` The start screen is asked once. What it collected — the terms, the preference answers and
 * where the questions stand — is kept in this browser and read back on the next visit, so a reload or a later visit does
 * not start over. Nothing here is sent to the server. ★Which card is open and the last trip stay page-only.
 */
const STORAGE_KEY = "tripilot.web.onboarding.v1";
const area = z.enum(["food", "activity", "mobility"]);
const text = z.string().max(200);
const saved = z.object({
  read: z.boolean(),
  agreed: z.boolean(),
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
  const value: Saved = { read: state.read, agreed: state.agreed, complete: state.complete, step: state.step, answers: state.answers };
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
    setState((current) => ({ ...current, ...(restored ?? {}), email: readRecoveryEmail() ?? "" }));
    setReady(true);
    // The email is edited on My page too: follow it, so the start screen never holds a stale copy.
    const follow = () => setState((current) => ({ ...current, email: readRecoveryEmail() ?? "" }));
    addEventListener(CONTACT_CHANGED_EVENT, follow);
    addEventListener("storage", follow);
    return () => { removeEventListener(CONTACT_CHANGED_EVENT, follow); removeEventListener("storage", follow); };
  }, [setState]);

  useEffect(() => {
    if (ready) save(state);
  }, [ready, state.read, state.agreed, state.complete, state.step, state.answers]);   // eslint-disable-line react-hooks/exhaustive-deps

  return <Context.Provider value={value}><ReadyContext.Provider value={ready}>{children}</ReadyContext.Provider></Context.Provider>;
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

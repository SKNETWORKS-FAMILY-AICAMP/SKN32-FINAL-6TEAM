"use client";

import { createContext, useContext, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { initialAnswers, INTRO_STEP, type Answers } from "./model";

export interface OnboardingState {
  /** The full terms were scrolled to the end at least once. */
  read: boolean;
  agreed: boolean;
  /** Expanded card: 0 recovery email (optional, unnumbered), 1 terms, 2 preferences. The language card lives in the settings menu. */
  open: 0 | 1 | 2 | null;
  /**
   * Recovery email draft, as typed. Optional: blank means "not entered". It is the same item as My page's recovery
   * email, but the server has no call to save it yet, so it stays in this page state and is never sent.
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

/** Page-session state only: nothing is written to storage or sent anywhere. */
export function OnboardingProvider({ children }: { children: ReactNode }) {
  const value = useState(initial);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useOnboarding() {
  const value = useContext(Context);
  if (!value) throw new Error("useOnboarding must be used inside OnboardingProvider");
  return value;
}

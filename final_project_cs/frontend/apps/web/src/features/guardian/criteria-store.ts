"use client";

import { useSyncExternalStore } from "react";
import { SURVEY_VERSION, tripSurveySchema, type TripSurvey } from "@/features/onboarding/payload";
import { DEFAULT_PACE, disruptionOf, isPace, type Guardian, type Pace } from "./model";

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 1단계]` What the customer chose on the plan screen before the plan is read: how full a day is (`pace`) and whether the Course Keeper is on (`guardian`).
 * Kept in this tab (session storage) from the plan screen through the reading and the plan check until the trip is registered - the choice is sent with the plan (`beginIntake`) and again when the plan
 * is confirmed (`confirmIntake`), where the server lays the survey it was given over its own (what the request says wins).
 * `decided`: the customer has been through the card (「켜고 진행」 / 「건너뛰기 — 끄고 진행」). Until then nothing of this is sent and the icon at the top is not shown.
 * `paceChosen`: the customer touched 「하루 일정의 여유」 here. Until then the preference survey's own answer (if there is one) stands - an untouched default must not overwrite it.
 */
export interface Criteria { pace: Pace; paceChosen: boolean; guardian: Guardian | null; decided: boolean }

const KEY = "triPilot.readingCriteria.v1";
const EMPTY: Criteria = { pace: DEFAULT_PACE, paceChosen: false, guardian: null, decided: false };
/** `[2026-10-06 사용자 지시 — 「한 번 켜면 켜진 상태가 기본」]` Once the customer has turned the Course Keeper on it stays the starting state of every plan after (kept in this browser): no card is asked again, the icon is simply on. */
const DEFAULT_KEY = "triPilot.guardianDefault.v1";
const ON_BY_DEFAULT: Criteria = { ...EMPTY, guardian: "on", decided: true };

function defaultOn(): boolean {
  try { return window.localStorage.getItem(DEFAULT_KEY) === "on"; } catch { return false; }
}

/** Keep (or forget) 「on」 as the way a plan starts. Turning it off forgets it - the card asks again next time. */
export function rememberGuardian(on: boolean) {
  try { if (on) window.localStorage.setItem(DEFAULT_KEY, "on"); else window.localStorage.removeItem(DEFAULT_KEY); } catch { /* private window: it is only kept for this page */ }
}

let current: Criteria | null = null;
const listeners = new Set<() => void>();

function load(): Criteria {
  try {
    const raw = JSON.parse(window.sessionStorage.getItem(KEY) ?? "null") as Partial<Criteria> | null;
    if (!raw || typeof raw !== "object") return defaultOn() ? ON_BY_DEFAULT : EMPTY;
    const guardian = raw.guardian === "on" || raw.guardian === "off" ? raw.guardian : null;
    const decided = raw.decided === true && guardian !== null;
    const base: Criteria = { pace: isPace(raw.pace) ? raw.pace : DEFAULT_PACE, paceChosen: raw.paceChosen === true && isPace(raw.pace), guardian, decided };
    return !decided && defaultOn() ? { ...base, guardian: "on", decided: true } : base;
  } catch { return defaultOn() ? ON_BY_DEFAULT : EMPTY; }
}

/** The choices now (`EMPTY` on the server render and where session storage is not available). */
export function readCriteria(): Criteria {
  if (typeof window === "undefined") return EMPTY;
  current ??= load();
  return current;
}

function write(next: Criteria) {
  current = next;
  try { window.sessionStorage.setItem(KEY, JSON.stringify(next)); } catch { /* kept for this page only */ }
  listeners.forEach((listener) => listener());
}

export const setPace = (pace: Pace) => write({ ...readCriteria(), pace, paceChosen: true });
/** The customer decided on the card: the Course Keeper on or off, and from here the choice is sent. */
export const decideGuardian = (guardian: Guardian) => { rememberGuardian(guardian === "on"); write({ ...readCriteria(), guardian, decided: true }); };
/** Forget it (a registered trip, or a new start). */
export const clearCriteria = () => write(defaultOn() ? ON_BY_DEFAULT : EMPTY);

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function useCriteria(): Criteria {
  return useSyncExternalStore(subscribe, readCriteria, () => EMPTY);
}

/** The fullness the 「읽는 기준」 shows and sends: what was chosen here, else the survey's own answer, else 「적당히」. */
export function paceOf(survey: TripSurvey | undefined, criteria: Criteria): Pace {
  return criteria.paceChosen ? criteria.pace : survey?.pace ?? criteria.pace;
}

/**
 * The survey with what the plan screen decided laid over it (the latest choice wins). Not decided: the survey as it was (possibly none).
 * ★「건너뛰기 — 끄고 진행」 sends `on_disruption: "ask_first"` SAID OUT LOUD - sending nothing would let the server change plans for closures and traffic stops by itself.
 */
export function withCriteria(survey: TripSurvey | undefined, criteria: Criteria): TripSurvey | undefined {
  if (!criteria.decided || !criteria.guardian) return survey;
  return tripSurveySchema.parse({ version: SURVEY_VERSION, ...(survey ?? {}), pace: paceOf(survey, criteria), on_disruption: disruptionOf(criteria.guardian) });
}

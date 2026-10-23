import { ACTIVITY_PICKS, areaNames, detailOptions, indoorParts, options as startOptions, questions as startQuestions, sizeFor, type Area, type ChoiceKey, type QuestionId } from "@/features/onboarding/model";
import type { TripSurvey } from "@/features/onboarding/payload";
import type { IntakePriorityAnswer, IntakeQuestion, IntakeSurveyAnswer } from "@/lib/live/intake";
import type { Language } from "@/lib/i18n";

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 2단계]` The questions asked while the server reads the plan (`questions[]` of the intake, `wiki/external/rest-endpoints/web-intakes.md` 「설문 질문」).
 *
 * ★The page DRAWS what the server sends: which questions, in which order, their wording and options. What it checks before drawing is the SHAPE of each kind; a question of a kind it
 * does not know, or whose shape is wrong, is left out - that one question, not the rest. An older server sends no `questions[]` and nothing is asked.
 * `[2026-10-20 ST4F-665]` The questions are the start survey's own (who · priorities · indoors or out · pace — `features/onboarding/model.ts`) and are drawn with the start survey's card pieces
 * and rules: the companions take how many travel (sent as `party_size`), activities take exactly `ACTIVITY_PICKS` details, a part the plan told (`read`) is not asked.
 * The English is the start survey's, found by the server's question and option ids; an id it does not know stays in the server's Korean.
 */
export interface Choice { id: string; label: string }
/** What the plan told for a part (the customer's words, and the plan's own words). */
export interface ReadMark { text: string; quotes: string[] }
/** A `priority` question's area details, or a `pair` question's part. */
export interface Part { id: string; label: string; options: Choice[]; read: ReadMark | null }

interface Base { id: string; title: string; why: string }
export interface SingleQuestion extends Base {
  kind: "single";
  options: Choice[];
  /** The customer may answer in their own words (`party`: 「기타」). */
  allowCustom: boolean;
  customMaxLength: number;
  customLabel: string;
  /** The option id the server holds, or `custom:<words>`. */
  answer: string | null;
}
export interface PriorityQuestion extends Base { kind: "priority"; /** The areas. */ options: Choice[]; groups: Part[]; answer: PriorityAnswer | null }
export interface PairQuestion extends Base { kind: "pair"; parts: Part[]; answer: PairAnswer | null }
export type SurveyQuestion = SingleQuestion | PriorityQuestion | PairQuestion;

export type PriorityAnswer = IntakePriorityAnswer;
export type PairAnswer = Record<string, string>;
export type SurveyAnswer = string | PriorityAnswer | PairAnswer;
/** What the customer has answered so far: the saved answers (by question id) over what the server held. */
export type Answers = Readonly<Record<string, SurveyAnswer | null>>;

/** The start survey's question for each of the server's question ids — the loading card is that card. */
const SAME_QUESTION: Readonly<Record<string, QuestionId>> = { party: "party", priority: "priority", indoor_outdoor: "indoor", pace: "pace" };
/** The start survey's options of the server's pick-one questions. */
const SAME_OPTIONS: Readonly<Record<string, ChoiceKey>> = { party: "party", pace: "pace" };
/** The own-words chip of a pick-one question (the start survey's 「기타」). */
export const CUSTOM = "custom";
const MAX_CUSTOM = 1000;

const isText = (value: unknown): value is string => typeof value === "string" && value.trim() !== "";
const isObject = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const english = <T extends readonly [string, string, string]>(list: readonly T[] | undefined, id: string) => list?.find((entry) => entry[0] === id)?.[2];

function choicesOf(raw: unknown, en: (id: string) => string | undefined): Choice[] {
  const listed: unknown[] = Array.isArray(raw) ? raw : [];
  const seen = new Set<string>();
  return listed.flatMap((option) => {
    if (!isObject(option) || !isText(option.id) || !isText(option.label) || seen.has(option.id)) return [];
    seen.add(option.id);
    return [{ id: option.id, label: en(option.id) ?? option.label }];
  });
}

function readOf(raw: unknown): ReadMark | null {
  if (!isObject(raw) || !isText(raw.text)) return null;
  return { text: raw.text, quotes: Array.isArray(raw.quotes) ? raw.quotes.filter(isText) : [] };
}

function partsOf(raw: unknown, label: (id: string) => string | undefined, option: (part: string, id: string) => string | undefined): Part[] {
  const listed: unknown[] = Array.isArray(raw) ? raw : [];
  const seen = new Set<string>();
  return listed.flatMap((part) => {
    if (!isObject(part) || !isText(part.id) || !isText(part.label) || seen.has(part.id)) return [];
    const options = choicesOf(part.options, (id) => option(part.id as string, id));
    const read = readOf(part.read);
    if (!options.length && !read) return [];
    seen.add(part.id);
    return [{ id: part.id, label: label(part.id) ?? part.label, options, read }];
  });
}

function priorityAnswerOf(raw: unknown, areas: readonly Choice[], groups: readonly Part[]): PriorityAnswer | null {
  if (!isObject(raw) || !Array.isArray(raw.areas)) return null;
  const picked = raw.areas.filter((area): area is string => typeof area === "string" && areas.some((entry) => entry.id === area));
  if (!picked.length || new Set(picked).size !== picked.length) return null;
  const details = isObject(raw.details) ? raw.details : {};
  return {
    areas: picked,
    details: Object.fromEntries(picked.flatMap((area) => {
      const group = groups.find((entry) => entry.id === area);
      const chosen = Array.isArray(details[area]) ? (details[area] as unknown[]).filter((id): id is string => typeof id === "string" && Boolean(group?.options.some((option) => option.id === id))) : [];
      return chosen.length ? [[area, chosen]] : [];
    })),
  };
}

function pairAnswerOf(raw: unknown, parts: readonly Part[]): PairAnswer | null {
  if (!isObject(raw)) return null;
  const held = Object.fromEntries(parts.flatMap((part) => {
    const value = raw[part.id];
    return typeof value === "string" && part.options.some((option) => option.id === value) ? [[part.id, value]] : [];
  }));
  return Object.keys(held).length ? held : null;
}

/** The questions of an intake that can be drawn, in the server's order. `raw` is whatever the server sent - read as data. */
export function questionsOf(raw: readonly IntakeQuestion[] | undefined | null, language: Language): SurveyQuestion[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const drawn: SurveyQuestion[] = [];
  for (const entry of raw as unknown[]) {
    if (!isObject(entry) || !isText(entry.id) || !isText(entry.title) || seen.has(entry.id)) continue;
    const id = entry.id;
    const en = language === "en";
    const start = en ? startQuestions.find((question) => question.id === SAME_QUESTION[id]) : undefined;
    const base: Base = { id, title: start?.title[1] ?? entry.title, why: start?.helper[1] ?? (isText(entry.why) ? entry.why : "") };
    let question: SurveyQuestion | null = null;
    if (entry.kind === "single") {
      const listed = SAME_OPTIONS[id] ? startOptions[SAME_OPTIONS[id]] : undefined;
      const options = choicesOf(entry.options, (option) => en ? english(listed, option) : undefined);
      const allowCustom = entry.allow_custom === true;
      const answer = allowCustom && isText(entry.custom_answer) ? `custom:${entry.custom_answer}`
        : typeof entry.answer === "string" && options.some((option) => option.id === entry.answer) ? entry.answer : null;
      const customLabel = (en ? english(listed, "other") : undefined) ?? (isText(entry.custom_label) ? entry.custom_label : en ? "Other" : "직접 입력");
      const customMaxLength = typeof entry.custom_max_length === "number" && entry.custom_max_length > 0 ? entry.custom_max_length : MAX_CUSTOM;
      if (options.length) question = { ...base, kind: "single", options, allowCustom, customLabel, customMaxLength, answer };
    } else if (entry.kind === "priority") {
      const areaName = (area: string) => en ? areaNames[area as Area]?.[1] : undefined;
      const options = choicesOf(entry.options, areaName);
      const groups = partsOf(entry.groups, areaName, (area, option) => en ? english(detailOptions[area as Area], option) : undefined);
      // Every area needs its details (or what the plan told of them); otherwise the card cannot be finished.
      if (options.length && options.every((area) => groups.some((group) => group.id === area.id))) {
        question = { ...base, kind: "priority", options, groups: groups.filter((group) => options.some((area) => area.id === group.id)), answer: priorityAnswerOf(entry.answer, options, groups) };
      }
    } else if (entry.kind === "pair") {
      const parts = partsOf(entry.parts, (part) => en ? indoorParts.find((row) => row[0] === part)?.[3] : undefined,
        (_part, option) => en ? english(startOptions.indoorDining, option) : undefined);
      // A pair whose every part the plan told has nothing to ask.
      if (parts.some((part) => !part.read)) question = { ...base, kind: "pair", parts, answer: pairAnswerOf(entry.answer, parts) };
    }
    if (!question) continue;
    seen.add(id);
    drawn.push(question);
  }
  return drawn;
}

export const answerOf = (question: SurveyQuestion, answers: Answers): SurveyAnswer | null =>
  Object.hasOwn(answers, question.id) ? answers[question.id] : question.answer;

/** Indexes of the questions not answered and not skipped: the ones still to ask. */
export function openIndexes(questions: readonly SurveyQuestion[], answers: Answers, skipped: ReadonlySet<string>): number[] {
  return questions.flatMap((question, index) => !answerOf(question, answers) && !skipped.has(question.id) ? [index] : []);
}

/** Every question has an answer (a skipped one does not count). False when there is nothing to ask. */
export const allAnswered = (questions: readonly SurveyQuestion[], answers: Answers): boolean =>
  questions.length > 0 && questions.every((question) => Boolean(answerOf(question, answers)));

/** Questions with no answer, skipped ones included - what is left for later. */
export const unanswered = (questions: readonly SurveyQuestion[], answers: Answers): number =>
  questions.filter((question) => !answerOf(question, answers)).length;

/** After the question at `at` was answered or skipped: the next open one after it, else the first open one before it; null when none is left. */
export function nextOpen(open: readonly number[], at: number): number | null {
  const others = open.filter((index) => index !== at);
  return others.find((index) => index > at) ?? others[0] ?? null;
}

// ── One card being answered: the same rules as the start survey's card ─────────────────────

/** What the card holds while the customer answers it; it goes to the server only when the card is complete and 「다음」 is pressed. */
export interface Draft {
  /** `single`: the option picked, or `CUSTOM`. */
  choice: string | null;
  custom: string;
  /** `party`: the size picked; what shows follows the start survey's rule (`sizeOf`). */
  size: number | null;
  /** `priority`: areas and their details in picking order. */
  areas: string[];
  details: Record<string, string[]>;
  /** `pair`: one pick per part. */
  parts: Record<string, string>;
}

export const EMPTY_DRAFT: Draft = { choice: null, custom: "", size: null, areas: [], details: {}, parts: {} };

/** The card for an answer already held (or none). */
export function draftOf(question: SurveyQuestion, answer: SurveyAnswer | null): Draft {
  if (question.kind === "single") {
    if (typeof answer !== "string") return EMPTY_DRAFT;
    return answer.startsWith("custom:") ? { ...EMPTY_DRAFT, choice: CUSTOM, custom: answer.slice(7) } : { ...EMPTY_DRAFT, choice: answer };
  }
  if (!isObject(answer)) return EMPTY_DRAFT;
  if (question.kind === "priority") {
    const held = priorityAnswerOf(answer, question.options, question.groups);
    return held ? { ...EMPTY_DRAFT, areas: held.areas, details: held.details } : EMPTY_DRAFT;
  }
  return { ...EMPTY_DRAFT, parts: pairAnswerOf(answer, question.parts) ?? {} };
}

/** The companions card asks how many travel under the choice — the start survey's rule. */
export const asksSize = (question: SurveyQuestion): boolean => question.kind === "single" && question.id === "party";
/** The start survey's companions value for the choice (its 「기타」 is `other`). */
export const companionsOf = (draft: Draft): string => draft.choice === CUSTOM ? "other" : draft.choice ?? "";
export const sizeOf = (draft: Draft): number | null => sizeFor(companionsOf(draft), draft.size);

/** How many details an area takes exactly (activities: `ACTIVITY_PICKS`, never more than it offers); none = one or more. */
export const exactPicks = (group: Part): number | undefined => group.id === "activity" ? Math.min(ACTIVITY_PICKS, group.options.length) : undefined;

/** Tap a chip of a pick-one question: it toggles. */
export const pickChoice = (draft: Draft, id: string): Draft => ({ ...draft, choice: draft.choice === id ? null : id });
export const pickSize = (draft: Draft, size: number): Draft => ({ ...draft, size });
/** Tap an area: picked areas rank in tapping order; un-picking drops the area and its details. */
export function pickArea(draft: Draft, area: string): Draft {
  if (!draft.areas.includes(area)) return { ...draft, areas: [...draft.areas, area] };
  return { ...draft, areas: draft.areas.filter((item) => item !== area), details: { ...draft.details, [area]: [] } };
}
/** Tap a detail: ranked the same way inside the area; a full area takes no more. */
export function pickDetail(question: PriorityQuestion, draft: Draft, area: string, id: string): Draft {
  const picked = draft.details[area] ?? [];
  const group = question.groups.find((entry) => entry.id === area);
  const exact = group ? exactPicks(group) : undefined;
  if (!picked.includes(id) && exact !== undefined && picked.length >= exact) return draft;
  return { ...draft, details: { ...draft.details, [area]: picked.includes(id) ? picked.filter((item) => item !== id) : [...picked, id] } };
}
export const pickPart = (draft: Draft, part: string, id: string): Draft => ({ ...draft, parts: { ...draft.parts, [part]: draft.parts[part] === id ? "" : id } });

/** The card can be sent: the start survey's `answered` rule, where a part the plan told needs nothing. */
export function complete(question: SurveyQuestion, draft: Draft): boolean {
  switch (question.kind) {
    case "single":
      return draft.choice !== null && (draft.choice !== CUSTOM || Boolean(draft.custom.trim())) && (!asksSize(question) || sizeOf(draft) !== null);
    case "priority":
      return draft.areas.length > 0 && draft.areas.every((area) => {
        const group = question.groups.find((entry) => entry.id === area);
        if (!group || group.read) return true;
        const picked = draft.details[area]?.length ?? 0;
        const exact = exactPicks(group);
        return exact !== undefined ? picked === exact : picked > 0;
      });
    case "pair":
      return question.parts.every((part) => part.read !== null || Boolean(draft.parts[part.id]));
  }
}

/**
 * What a complete card sends (`POST …/survey`) and the answer it leaves on screen. The companions carry how many travel (`party_size`, the same call);
 * a part the plan told is left out (the server keeps what it read).
 */
export function payloadOf(question: SurveyQuestion, draft: Draft): { answers: Record<string, IntakeSurveyAnswer>; value: SurveyAnswer } {
  switch (question.kind) {
    case "single": {
      const words = draft.custom.trim();
      const size = asksSize(question) ? sizeOf(draft) : null;
      const sent = draft.choice === CUSTOM ? { custom: words } : draft.choice ?? "";
      return { answers: { [question.id]: sent, ...(size !== null && { party_size: String(size) }) }, value: draft.choice === CUSTOM ? `custom:${words}` : draft.choice ?? "" };
    }
    case "priority": {
      const details = Object.fromEntries(draft.areas.flatMap((area) => {
        const group = question.groups.find((entry) => entry.id === area);
        const picked = draft.details[area] ?? [];
        return group && !group.read && picked.length ? [[area, [...picked]]] : [];
      }));
      const value: PriorityAnswer = { areas: [...draft.areas], details };
      return { answers: { [question.id]: value }, value };
    }
    case "pair": {
      const value: PairAnswer = Object.fromEntries(question.parts.flatMap((part) => !part.read && draft.parts[part.id] ? [[part.id, draft.parts[part.id]]] : []));
      return { answers: { [question.id]: value }, value };
    }
  }
}

// ── The start survey's answers, laid on the intake before it is first read ─────────────────

/** The start survey's companions ids (its 「기타」 sends the words instead). */
const PARTY_IDS = new Set(startOptions.party.map(([id]) => id).filter((id) => id !== "other"));

/**
 * `[2026-10-20 ST4F-665]` What the survey the registration will send (`TripSurvey` — the start survey with the plan screen's choices laid over it) already answers, as the loading
 * questions' answers: the server leaves an answered question out of the list it fixes at the intake's first read, so nothing is asked twice — and an answer given in loading would
 * lose to that survey at registration anyway (the request's survey wins). `on_disruption` stays with the Course Keeper card. Empty when there is no survey.
 */
export function startAnswers(survey: TripSurvey | undefined): Record<string, IntakeSurveyAnswer> {
  if (!survey) return {};
  const out: Record<string, IntakeSurveyAnswer> = {};
  if (survey.party) {
    out.party = PARTY_IDS.has(survey.party) ? survey.party : { custom: survey.party };
    if (survey.party_size) out.party_size = String(survey.party_size);
  }
  if (survey.priority?.length) {
    const details = survey.priority_details ?? {};
    out.priority = { areas: [...survey.priority], details: Object.fromEntries(survey.priority.flatMap((area) => details[area]?.length ? [[area, [...details[area]!]]] : [])) };
  }
  if (survey.indoor_outdoor && Object.keys(survey.indoor_outdoor).length) out.indoor_outdoor = { ...survey.indoor_outdoor } as PairAnswer;
  if (survey.pace) out.pace = survey.pace;
  return out;
}

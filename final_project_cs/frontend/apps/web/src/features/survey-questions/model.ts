import type { IntakeQuestion } from "@/lib/live/intake";
import type { Language } from "@/lib/i18n";

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 2단계]` The questions asked while the server reads the plan (`questions[]` of the intake, `wiki/external/rest-endpoints.md` 「설문 질문」).
 *
 * ★The page DRAWS what the server sends and builds nothing of its own into it: no wording, no meaning of an option, no number of questions. What it checks before drawing is the SHAPE
 * (a pick-one question has an id, a title and at least one option with an id and a label); a question that is not of a kind it knows (`single` today) or whose shape is wrong is left out
 * - that one question, not the rest. An older server sends no `questions[]` and nothing is asked.
 * The only words kept here are the English ones for the server's known question ids: the server writes Korean, and says the English screen carries them by id. An unknown id stays in Korean.
 */
export interface SurveyQuestion {
  id: string;
  title: string;
  why: string;
  options: { id: string; label: string }[];
  /** The option id the server already holds. */
  answer: string | null;
  allowCustom?: boolean;
  customMaxLength?: number;
}

/** English for the question ids the server sends today (the id and option id are the server's, never changed once sent). */
const ENGLISH: Record<string, { title: string; why: string; options: Record<string, string> }> = {
  preferred_mobility: {
    title: "How do you usually get around?",
    why: "We ask because a plan alone does not say how you travel.",
    options: { public: "Public transport", taxi: "Taxi", walk: "Mostly on foot" },
  },
  priority: {
    title: "When the plan changes, what should we look at first for a replacement?",
    why: "We ask because a plan alone does not tell us.",
    options: { activity: "A place with a similar activity", mobility: "A place that is easy to reach" },
  },
};

const isText = (value: unknown): value is string => typeof value === "string" && value.trim() !== "";

/** The questions of an intake that can be drawn, in the server's order. `view` is whatever the server sent - read as data. */
export function questionsOf(raw: readonly IntakeQuestion[] | undefined | null, language: Language): SurveyQuestion[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const drawn: SurveyQuestion[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object" || entry.kind !== "single" || !isText(entry.id) || !isText(entry.title) || seen.has(entry.id)) continue;
    const listed: ({ id?: unknown; label?: unknown } | null)[] = Array.isArray(entry.options) ? entry.options : [];
    const options = listed.filter((option): option is { id: string; label: string } => Boolean(option) && isText(option?.id) && isText(option?.label));
    if (options.length === 0) continue;
    const english = language === "en" ? ENGLISH[entry.id] : undefined;
    seen.add(entry.id);
    drawn.push({
      id: entry.id,
      title: english?.title ?? entry.title,
      why: english?.why ?? (isText(entry.why) ? entry.why : ""),
      options: options.map((option) => ({ id: option.id, label: english?.options[option.id] ?? option.label })),
      allowCustom: entry.allow_custom === true,
      customMaxLength: entry.custom_max_length,
      answer: entry.allow_custom === true && isText(entry.custom_answer) ? `custom:${entry.custom_answer}`
        : isText(entry.answer) && options.some((option) => option.id === entry.answer) ? entry.answer : null,
    });
  }
  return drawn;
}

/** What the customer has answered so far: the saved answers (`answers`, by question id) over what the server held. */
export type Answers = Readonly<Record<string, string | null>>;

export const answerOf = (question: SurveyQuestion, answers: Answers): string | null =>
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

import { z } from "zod";
import type { Language } from "@/lib/i18n";
import { options, valid, type Answers, type ChoiceKey, type ListKey } from "./model";

/** Sent in place of a skipped answer until a default is chosen for that question. */
export const UNSELECTED = "unselected";

/** Payload keys in question order. */
export const questionKeys = ["themes", "companions", "food", "transport", "budget", "nationality", "priority", "detailPriority", "religion"] as const;
export type QuestionKey = typeof questionKeys[number];

const code = (key: ListKey | ChoiceKey) => z.enum(options[key].map((option) => option[0]) as [string, ...string[]]);
const people = z.number().int().min(0).max(20);
const orUnselected = <T extends z.ZodType>(answer: T) => z.union([answer, z.literal(UNSELECTED)]);

/** What the server receives: option codes, never display labels. See PREFERENCES_CONTRACT.md. */
export const preferencesPayloadSchema = z.object({
  version: z.literal(1),
  language: z.enum(["en", "ko"]),
  answers: z.object({
    themes: orUnselected(z.array(code("themes")).min(1)),
    companions: orUnselected(z.object({ types: z.array(code("companions")).min(1), adults: people.min(1), children: people, infants: people })),
    food: orUnselected(z.object({ none: z.boolean(), allergies: z.array(code("allergies")), diet: z.array(code("diet")), religious: z.array(code("foodReligion")) })),
    transport: orUnselected(z.array(code("transport")).min(1)),
    budget: orUnselected(z.object({ range: code("budget"), amountKrw: z.number().positive().nullable() })),
    nationality: orUnselected(code("citizen")),
    priority: orUnselected(code("priority")),
    detailPriority: orUnselected(z.object({ food: code("detailFood"), activity: code("detailActivity"), transport: code("detailTransport") })),
    religion: orUnselected(code("religion")),
  }),
  /** Questions whose value came from skipDefaults, not from the traveler. */
  skipped: z.array(z.enum(questionKeys)),
});
export type PreferencesPayload = z.infer<typeof preferencesPayloadSchema>;
type PayloadAnswers = PreferencesPayload["answers"];

/**
 * The value sent for a skipped question. The traveler still sees “Not selected”.
 * A general default will be chosen per question; every question sends UNSELECTED for now.
 */
export const skipDefaults: PayloadAnswers = {
  themes: UNSELECTED, companions: UNSELECTED, food: UNSELECTED, transport: UNSELECTED, budget: UNSELECTED,
  nationality: UNSELECTED, priority: UNSELECTED, detailPriority: UNSELECTED, religion: UNSELECTED,
};

const answerOf: { [K in QuestionKey]: (a: Answers) => PayloadAnswers[K] } = {
  themes: (a) => a.themes,
  companions: (a) => ({ types: a.companions, adults: a.adults, children: a.children, infants: a.infants }),
  food: (a) => ({ none: a.foodNone, allergies: a.allergies, diet: a.diet, religious: a.foodReligion }),
  transport: (a) => a.transport,
  budget: (a) => ({ range: a.budget, amountKrw: a.budget === "custom" ? Number(a.budgetCustom) : null }),
  nationality: (a) => a.citizen,
  priority: (a) => a.priority,
  detailPriority: (a) => ({ food: a.detailFood, activity: a.detailActivity, transport: a.detailTransport }),
  religion: (a) => a.religion,
};

/** Build the payload once every question is answered or skipped. */
export function toPayload(a: Answers, language: Language): PreferencesPayload {
  const answers = Object.fromEntries(questionKeys.map((key, index) => [key, valid(index, a) ? answerOf[key](a) : skipDefaults[key]])) as PayloadAnswers;
  return { version: 1, language, answers, skipped: questionKeys.filter((_, index) => !valid(index, a)) };
}

import { z } from "zod";
import { isAnswered, PARTY_SIZES, partySizeOf, type Answers, type QuestionId } from "./model";

/**
 * The backend trip survey, `constraints.survey` on trip registration. The backend is the
 * source of truth: `final_project_cs/app/domains/travel_ops/components/planning/survey.py` (TripSurvey) and
 * wiki D-020. This schema mirrors it so the screen refuses what the server would refuse (422) before sending.
 */
export const SURVEY_VERSION = "2026-09-24.v1";

const area = z.enum(["food", "activity", "mobility"]);

export const tripSurveySchema = z.strictObject({
  version: z.literal(SURVEY_VERSION),
  on_disruption: z.enum(["replace", "ask_first"]).optional(),
  pace: z.enum(["relaxed", "moderate", "packed"]).optional(),
  theme: z.string().optional(),
  party: z.string().optional(),
  /** `[2026-10-20 B안 · ST4F-581]` How many travel, from the companions card — the server uses it only when the trip's own size is empty (`web-intakes.md` 「confirm」). */
  party_size: z.number().int().min(PARTY_SIZES[0]).max(PARTY_SIZES[PARTY_SIZES.length - 1]).optional(),
  preferred_mobility: z.array(z.string()).optional(),
  /** The server still accepts it, but the web no longer asks (nothing uses it), so it is never sent. */
  domestic: z.boolean().optional(),
  priority: z.array(area).optional(),
  priority_details: z.partialRecord(area, z.array(z.string())).optional(),
  indoor_outdoor: z.partialRecord(z.enum(["dining", "activity"]), z.enum(["indoor", "outdoor", "any"])).optional(),
  theme_details: z.array(z.string()).optional(),
});
export type TripSurvey = z.infer<typeof tripSurveySchema>;

/**
 * Build the survey from the answers. A skipped question sends no field, so the backend
 * applies its own default (pace → no density target; the rest empty).
 * `preferred_mobility` is no longer asked, so it is not sent; the backend field stays as it is.
 * `[2026-10-19]` `theme` and `on_disruption` are no longer asked either. `on_disruption` comes from the Course Keeper card
 * (`guardian/criteria-store.ts` `withCriteria`); both fields stay in the schema because the server still takes them.
 */
export function toSurvey(a: Answers): TripSurvey {
  const has = (id: QuestionId) => isAnswered(id, a);
  return tripSurveySchema.parse({
    version: SURVEY_VERSION,
    // `party` is a free string on the backend: `other` sends what was typed, trimmed.
    // `[2026-10-20]` with the size the card shows (set for 혼자 · 연인, 2 until changed for 친구 · 가족, picked for 기타): an answered card always has one.
    ...(has("party") && { party: a.party === "other" ? a.partyOther.trim() : a.party, party_size: partySizeOf(a) ?? undefined }),
    // Array order is the ranking. Areas not picked (and their details) are left out.
    ...(has("priority") && { priority: a.priority, priority_details: Object.fromEntries(a.priority.map((area) => [area, a.details[area]])) }),
    ...(has("indoor") && { indoor_outdoor: { dining: a.indoorDining, activity: a.indoorActivity } }),
    ...(has("pace") && { pace: a.pace }),
  });
}

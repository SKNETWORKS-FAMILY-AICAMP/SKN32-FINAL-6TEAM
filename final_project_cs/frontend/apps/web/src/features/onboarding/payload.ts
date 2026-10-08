import { z } from "zod";
import { isAnswered, type Answers, type QuestionId } from "./model";

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
 * applies its own default (on_disruption → replace; pace → no density target; the rest empty).
 * `preferred_mobility` is no longer asked, so it is not sent; the backend field stays as it is.
 */
export function toSurvey(a: Answers): TripSurvey {
  const has = (id: QuestionId) => isAnswered(id, a);
  return tripSurveySchema.parse({
    version: SURVEY_VERSION,
    ...(has("theme") && { theme: a.theme }),
    // `party` is a free string on the backend: `other` sends what was typed, trimmed.
    ...(has("party") && { party: a.party === "other" ? a.partyOther.trim() : a.party }),
    // Array order is the ranking. Areas not picked (and their details) are left out.
    ...(has("priority") && { priority: a.priority, priority_details: Object.fromEntries(a.priority.map((area) => [area, a.details[area]])) }),
    ...(has("indoor") && { indoor_outdoor: { dining: a.indoorDining, activity: a.indoorActivity } }),
    ...(has("onDisruption") && { on_disruption: a.onDisruption }),
    ...(has("pace") && { pace: a.pace }),
  });
}

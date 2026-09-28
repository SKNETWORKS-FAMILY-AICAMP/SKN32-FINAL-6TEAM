import { z } from "zod";
import { valid, type Answers } from "./model";

/**
 * The backend trip survey, `constraints.survey` on trip registration. The backend is the
 * source of truth: `final_project_cs/app/modules/travel_ops/survey.py` (TripSurvey) and
 * wiki D-020. This schema mirrors it so the demo rejects what the server would reject (422).
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
  domestic: z.boolean().optional(),
  priority: z.array(area).optional(),
  priority_details: z.partialRecord(area, z.array(z.string())).optional(),
  indoor_outdoor: z.partialRecord(z.enum(["dining", "activity"]), z.enum(["indoor", "outdoor", "any"])).optional(),
  theme_details: z.array(z.string()).optional(),
});
export type TripSurvey = z.infer<typeof tripSurveySchema>;

/** Our “Getting around” option is the backend's `mobility` area. */
const toArea = (code: string) => code === "transport" ? "mobility" : code;

/**
 * Build the survey from the answers. A skipped question sends no field, so the backend
 * applies its own default (on_disruption → replace; pace → no density target; the rest empty).
 */
export function toSurvey(a: Answers): TripSurvey {
  return tripSurveySchema.parse({
    version: SURVEY_VERSION,
    ...(valid(0, a) && { theme: a.theme }),
    ...(valid(1, a) && { party: a.party }),
    ...(valid(2, a) && { preferred_mobility: a.transport }),
    ...(valid(3, a) && { domestic: a.citizen === "domestic" }),
    ...(valid(4, a) && { priority: [toArea(a.priority)] }),
    ...(valid(5, a) && { priority_details: { food: [a.detailFood], activity: [a.detailActivity], mobility: [a.detailTransport] } }),
    ...(valid(6, a) && { indoor_outdoor: { dining: a.indoorDining, activity: a.indoorActivity } }),
    ...(valid(7, a) && { on_disruption: a.onDisruption }),
    ...(valid(8, a) && { pace: a.pace }),
  });
}

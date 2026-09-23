import { z } from "zod";

export const dateSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/).refine((value) => {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
});
export const timeSchema = z.string().regex(/^(?:[01]\d|2[0-3]):[0-5]\d$/);
export const scenarioSchema = z.enum(["success", "needs-review", "failed"]);
export const inputSchema = z.object({
  source: z.string().trim().min(1, "시간과 장소가 있는 여행 계획을 입력해 주세요.").max(12000, "여행 계획은 12,000자 이내로 입력해 주세요."),
  scenario: scenarioSchema.optional(),
});

const stopSchema = z.object({
  id: z.string().uuid(),
  date: dateSchema,
  time: timeSchema,
  endTime: timeSchema.optional(),
  originalTime: timeSchema.optional(),
  title: z.string().min(1),
  area: z.string(),
  kind: z.string(),
  booking: z.enum(["booked", "none", "unknown"]),
  notes: z.string(),
  movement: z.string().optional(),
  coordinates: z.object({
    lat: z.number().finite().min(-90).max(90),
    lng: z.number().finite().min(-180).max(180),
  }).nullable().optional(),
});

export const storedTripSchema = z.object({
  version: z.literal(1),
  scenario: scenarioSchema,
  startedAt: z.number().finite().nonnegative(),
  trip: z.object({
    id: z.string().uuid(),
    title: z.string().min(1),
    source: z.string().min(1).max(12000),
    startDate: dateSchema,
    endDate: dateSchema,
    status: z.enum(["processing", "ready", "active", "failed"]),
    stops: z.array(stopSchema).min(1).max(100),
    verification: z.object({
      status: z.enum(["running", "completed", "failed"]),
      progress: z.number().min(0).max(100),
      stages: z.array(z.object({
        id: z.string(),
        label: z.string(),
        description: z.string(),
        status: z.enum(["pending", "running", "completed", "failed"]),
      })).length(4),
      results: z.array(z.object({
        id: z.string().uuid(),
        stopId: z.string().uuid(),
        date: dateSchema,
        status: z.enum(["adjusted", "unchanged", "needs_review"]),
        title: z.string(),
        originalValue: z.string(),
        proposedValue: z.string().optional(),
        reason: z.string(),
        impact: z.string(),
      })),
      error: z.string().optional(),
    }),
    messages: z.array(z.object({
      id: z.string().uuid(),
      role: z.enum(["assistant", "user"]),
      text: z.string(),
      createdAt: z.string().datetime(),
    })),
  }),
}).superRefine(({ trip }, context) => {
  const fail = (message: string) => context.addIssue({ code: "custom", message });
  const dates = trip.stops.map((stop) => stop.date).sort();
  if (dates[0] !== trip.startDate || dates.at(-1) !== trip.endDate) fail("일정 날짜 불일치");
  const stops = new Map(trip.stops.map((stop) => [stop.id, stop]));
  if (stops.size !== trip.stops.length) fail("일정 식별자 중복");
  if (trip.verification.results.some((result) => !stops.has(result.stopId) || stops.get(result.stopId)?.date !== result.date)) fail("결과 참조 불일치");
  if (trip.verification.status === "completed" && trip.verification.progress !== 100) fail("완료 진행률 불일치");
  if (trip.verification.status === "completed") {
    const coveredStops = new Set(trip.verification.results.map((result) => result.stopId));
    if (trip.verification.results.length !== trip.stops.length || coveredStops.size !== trip.stops.length || trip.stops.some((stop) => !coveredStops.has(stop.id))) fail("완료 결과는 각 일정에 정확히 하나씩 필요함");
  }
  if (trip.status === "processing" && trip.verification.status !== "running") fail("진행 상태 불일치");
  if ((trip.status === "ready" || trip.status === "active") && trip.verification.status !== "completed") fail("완료 상태 불일치");
  if (trip.status === "failed" && trip.verification.status !== "failed") fail("실패 상태 불일치");
  if (trip.status === "active" && trip.verification.results.some((result) => result.status === "needs_review")) fail("미완료 여행 시작 불가");
  for (const result of trip.verification.results) {
    const stop = stops.get(result.stopId);
    if (result.status === "adjusted" && (!stop || stop.time !== result.proposedValue || stop.originalTime !== result.originalValue || stop.booking === "booked")) fail("조정 결과와 일정 불일치");
    if (result.status === "unchanged" && (!stop || stop.time !== result.proposedValue || stop.time !== result.originalValue)) fail("유지 결과와 일정 불일치");
  }
});

export type StoredTrip = z.infer<typeof storedTripSchema>;

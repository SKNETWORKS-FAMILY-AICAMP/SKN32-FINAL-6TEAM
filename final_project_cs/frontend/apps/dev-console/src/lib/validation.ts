import { z } from "zod";

export const testRequestSchema = z.object({
  target: z.enum(["activity", "dining", "mobility", "core"]),
  version: z.enum(["A", "B"]),
  fixtureMode: z.enum(["normal", "tool-error"]),
  input: z.object({
    time: z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, "시각은 00:00~23:59 형식으로 입력해 주세요."),
    durationMinutes: z.number().int("소요 시간은 정수로 입력해 주세요.").min(1, "소요 시간은 1분 이상이어야 합니다.").max(240, "소요 시간은 240분 이하여야 합니다."),
    transport: z.enum(["bus", "walk", "taxi"]),
  }).strict().readonly(),
}).strict().readonly();

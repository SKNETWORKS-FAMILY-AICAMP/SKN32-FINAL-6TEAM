import type { TripStop } from "../../features/trip/model";
import { GatewayError } from "./errors";
import { SAMPLE_PLAN } from "./sample";
import { dateSchema, timeSchema } from "./schema";
import { hasValidCoordinates } from "../../features/map/map-points";

/** Demo-only text parsing. Production extraction belongs to the agent service. */
export function parseDemoPlan(source: string): TripStop[] {
  const stops: TripStop[] = [];
  let date = "";
  let firstDate = "";
  const isSample = source === SAMPLE_PLAN;

  for (const [index, raw] of source.split(/\r?\n/).entries()) {
    const line = raw.trim();
    if (!line) continue;
    const heading = line.match(/^(?:\[)?(?:(\d+)일차|DAY\s*(\d+))(?:\s|[·:：\]-]|$)/i);
    if (heading || /^\d{4}-\d{2}-\d{2}$/.test(line)) {
      const explicit = line.match(/\d{4}-\d{2}-\d{2}/)?.[0];
      if (explicit) date = explicit;
      else if (firstDate && heading) {
        const offset = Number(heading[1] || heading[2]) - 1;
        if (!Number.isSafeInteger(offset) || offset < 0 || offset > 365) throw inputError(index, "일차는 1일부터 366일까지 적어 주세요.");
        const next = new Date(`${firstDate}T00:00:00Z`);
        next.setUTCDate(next.getUTCDate() + offset);
        date = next.toISOString().slice(0, 10);
      } else date = "";
      if (!dateSchema.safeParse(date).success) throw inputError(index, "일차 제목에 올바른 날짜(YYYY-MM-DD)를 적어 주세요.");
      firstDate ||= date;
      continue;
    }
    if (!date) throw inputError(index, "먼저 일차와 날짜를 적어 주세요. 예: 1일차 · 2026-09-15");
    const match = line.match(/^(\d{1,2}:\d{2})\s+(.+)$/);
    if (!match || !timeSchema.safeParse(match[1].padStart(5, "0")).success) throw inputError(index, "시작 시각과 장소를 적어 주세요. 예: 09:00 호텔 조식");
    const coordinateTag = match[2].match(/\[좌표\s*:\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*,\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*\]/);
    if (match[2].includes("[좌표") && !coordinateTag) throw inputError(index, "좌표는 [좌표: 위도, 경도] 형식으로 적어 주세요.");
    const coordinates = coordinateTag ? { lat: Number(coordinateTag[1]), lng: Number(coordinateTag[2]) } : undefined;
    if (coordinates && !hasValidCoordinates(coordinates)) throw inputError(index, "위도는 -90~90, 경도는 -180~180 범위여야 해요.");
    const content = (coordinateTag ? match[2].replace(coordinateTag[0], "") : match[2]).replace(/\s*·\s*$/, "").trim();
    const title = content.split(/\s*[·|]\s*/)[0].trim();
    if (!title) throw inputError(index, "장소를 적어 주세요.");
    const end = content.match(/(\d{1,2}:\d{2})\s*종료/)?.[1]?.padStart(5, "0");
    if (end && (!timeSchema.safeParse(end).success || end <= match[1].padStart(5, "0"))) throw inputError(index, "종료 시각은 같은 날의 시작 시각보다 뒤여야 해요.");
    const booking = /예약\s*(?:있음|완료|확정)|\b(?:reserved|booked)\b/i.test(content)
      ? "booked"
      : /예약\s*(?:없이|없음)|미예약|walk-in|no reservation/i.test(content) || isSample ? "none" : "unknown";
    stops.push({
      id: crypto.randomUUID(),
      date,
      time: match[1].padStart(5, "0"),
      ...(end ? { endTime: end } : {}),
      title,
      area: "입력 장소 · 상세 위치 미확인",
      kind: /식당|조식|점심|저녁|카페/.test(title) ? "식사" : /쇼핑|소품숍|마트/.test(title) ? "쇼핑" : "방문 일정",
      booking,
      notes: content,
      movement: "이동 수단과 경로는 아직 확인하지 않았어요.",
      ...(coordinates ? { coordinates } : {}),
    });
  }
  if (!stops.length) throw new GatewayError("INVALID_INPUT", "날짜 아래에 시간과 장소가 있는 일정을 하나 이상 적어 주세요.");
  if (stops.length > 100) throw new GatewayError("INVALID_INPUT", "데모에서는 한 번에 100개 일정까지 등록할 수 있어요.");
  return stops.sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`));
}

function inputError(line: number, message: string) {
  return new GatewayError("INVALID_INPUT", `${line + 1}번째 줄: ${message}`);
}

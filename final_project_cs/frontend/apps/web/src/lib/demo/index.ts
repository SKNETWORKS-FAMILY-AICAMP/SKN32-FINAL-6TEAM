import type { Trip, TripGateway, VerificationResult, VerificationStage } from "../../features/trip/model";
import { GatewayError } from "./errors";
import { parseDemoPlan } from "./parse-plan";
import { SAMPLE_PLAN } from "./sample";
import { inputSchema, storedTripSchema, type StoredTrip } from "./schema";

export { SAMPLE_PLAN } from "./sample";
export const DEMO_STORAGE_PREFIX = "tripilot.web-mvp.trip:";
export const DEMO_VERIFICATION_DURATION = 6000;

export interface DemoStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

interface DemoGatewayOptions {
  storage?: DemoStorage | (() => DemoStorage);
  now?: () => number;
  delay?: (milliseconds: number) => Promise<void>;
}

const stageDefinitions = [
  ["plan", "여행 계획 읽기", "등록한 날짜, 시간과 장소를 정리해요."],
  ["places", "장소·운영시간 확인", "장소와 운영시간을 확인하는 단계를 시연해요."],
  ["conditions", "이동·예약 조건 확인", "이동과 예약 조건 확인 단계를 시연해요."],
  ["overall", "전체 일정 검증", "여러 검증 결과를 일정에 정리해요."],
] as const;

function stages(progress: number, failed = false): VerificationStage[] {
  const active = progress < 20 ? 0 : progress < 55 ? 1 : progress < 80 ? 2 : 3;
  return stageDefinitions.map(([id, label, description], index) => ({
    id,
    label,
    description,
    status: progress === 100 || index < active ? "completed" : index === active ? failed ? "failed" : "running" : "pending",
  }));
}

function browserStorage(): DemoStorage {
  if (typeof window === "undefined") throw new GatewayError("STORAGE_UNAVAILABLE", "여행 데이터는 이 브라우저 탭에서만 열 수 있어요.");
  return window.sessionStorage;
}

/** Local, deterministic demo adapter. No place, routing, booking, or AI API is called. */
export function createDemoGateway(options: DemoGatewayOptions = {}): TripGateway {
  const now = options.now ?? Date.now;
  const delay = options.delay ?? ((milliseconds: number) => new Promise<void>((resolve) => setTimeout(resolve, milliseconds)));

  function storage(): DemoStorage {
    try {
      return typeof options.storage === "function" ? options.storage() : options.storage ?? browserStorage();
    } catch {
      throw new GatewayError("STORAGE_UNAVAILABLE", "이 브라우저에서 세션 저장소를 사용할 수 없어요. 저장소 사용을 허용한 뒤 다시 시도해 주세요.");
    }
  }

  function read(tripId: string): StoredTrip {
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(tripId)) throw notFound();
    let raw: string | null;
    try { raw = storage().getItem(DEMO_STORAGE_PREFIX + tripId); }
    catch { throw storageError(); }
    if (raw === null) throw notFound();
    try {
      const stored = storedTripSchema.parse(JSON.parse(raw));
      if (stored.trip.id !== tripId) throw new Error("ID mismatch");
      return stored;
    } catch {
      throw new GatewayError("CORRUPT_STORAGE", "저장된 여행 데이터를 읽을 수 없어요. 입력 원본이 남아 있다면 새 여행으로 다시 등록해 주세요.");
    }
  }

  function save(stored: StoredTrip): Trip {
    const checked = storedTripSchema.safeParse(stored);
    if (!checked.success) throw new GatewayError("CORRUPT_STORAGE", "여행 데이터 형식이 올바르지 않아 저장하지 못했어요.");
    try { storage().setItem(DEMO_STORAGE_PREFIX + stored.trip.id, JSON.stringify(checked.data)); }
    catch { throw storageError(); }
    return checked.data.trip;
  }

  function refresh(tripId: string): StoredTrip {
    const stored = read(tripId);
    if (stored.trip.verification.status !== "running") return stored;
    const elapsed = Math.max(0, now() - stored.startedAt);
    const nextProgress = Math.min(100, Math.floor(elapsed / DEMO_VERIFICATION_DURATION * 100));
    // Preserve monotonic progress even when the browser clock moves backwards.
    const progress = Math.max(stored.trip.verification.progress, nextProgress);
    if (stored.scenario === "failed" && progress >= 55) {
      stored.trip.status = "failed";
      stored.trip.verification = {
        status: "failed", progress: 55, stages: stages(55, true), results: [],
        error: "이동 정보 확인 실패 상황을 시연하고 있어요. 입력한 계획은 보존되어 있으며 다시 시도할 수 있어요.",
      };
    } else if (progress === 100) {
      complete(stored);
    } else {
      stored.trip.verification.progress = progress;
      stored.trip.verification.stages = stages(progress);
    }
    save(stored);
    return stored;
  }

  return {
    async createTrip(input) {
      const parsed = inputSchema.safeParse(input);
      if (!parsed.success) throw new GatewayError("INVALID_INPUT", parsed.error.issues[0]?.message ?? "여행 계획을 확인해 주세요.");
      const { source, scenario = "success" } = parsed.data;
      const stops = parseDemoPlan(source);
      const createdAt = now();
      const trip: Trip = {
        id: crypto.randomUUID(),
        title: source === SAMPLE_PLAN ? "서울, 취향을 따라 걷는 이틀" : `${stops[0].title}부터 시작하는 여행`,
        source,
        startDate: stops[0].date,
        endDate: stops.at(-1)!.date,
        status: "processing",
        stops,
        verification: { status: "running", progress: 0, stages: stages(0), results: [] },
        messages: [],
      };
      return save({ version: 1, scenario, startedAt: createdAt, trip });
    },
    async getTrip(tripId) {
      return refresh(tripId).trip;
    },
    async retryVerification(tripId) {
      const stored = read(tripId);
      const retryable = stored.trip.verification.status === "failed" || stored.trip.verification.results.some((result) => result.status === "needs_review");
      if (!retryable) throw new GatewayError("NOT_READY", "다시 시도할 검증 오류가 없어요.");
      stored.scenario = "success";
      stored.startedAt = now();
      stored.trip.status = "processing";
      stored.trip.stops = stored.trip.stops.map((stop) => {
        const { originalTime, ...rest } = stop;
        return { ...rest, time: originalTime ?? stop.time };
      });
      stored.trip.verification = { status: "running", progress: 0, stages: stages(0), results: [] };
      return save(stored);
    },
    async startTrip(tripId) {
      const stored = refresh(tripId);
      if (stored.trip.verification.results.some((result) => result.status === "needs_review")) {
        throw new GatewayError("VERIFICATION_BLOCKED", "검증 미완료 항목이 남아 있어 여행 관리를 시작할 수 없어요. 검증을 다시 시도해 주세요.");
      }
      if (stored.trip.verification.status !== "completed") throw new GatewayError("NOT_READY", "검증이 완료된 뒤 여행 관리를 시작할 수 있어요.");
      if (stored.trip.status === "active") return stored.trip;
      stored.trip.status = "active";
      const adjusted = stored.trip.verification.results.filter((result) => result.status === "adjusted").length;
      stored.trip.messages.push({
        id: crypto.randomUUID(), role: "assistant", createdAt: new Date(now()).toISOString(),
        text: `[데모 안내] 여행 계획을 등록했어요. ${adjusted ? `${adjusted}개 일정의 시작 시각에 15분을 더한 시연 결과가 반영되어 있어요.` : "입력한 시작 시각을 유지했어요."} 예약이 있는 일정은 변경하지 않았어요.\n실제 장소·이동 정보 조회, 예약 변경, 실시간 관리와 AI 응답은 연결 전이에요.`,
      });
      return save(stored);
    },
    async sendMessage(tripId, message) {
      const text = message.trim();
      if (!text || text.length > 2000) throw new GatewayError("INVALID_INPUT", "메시지를 1~2,000자 이내로 입력해 주세요.");
      // Visible pending state for the demo. Read after the delay to avoid
      // overwriting changes saved while the reply was waiting.
      await delay(350);
      const stored = read(tripId);
      if (stored.trip.status !== "active") throw new GatewayError("NOT_READY", "여행 관리를 시작한 뒤 대화를 이용할 수 있어요.");
      const createdAt = new Date(now()).toISOString();
      stored.trip.messages.push(
        { id: crypto.randomUUID(), role: "user", text, createdAt },
        { id: crypto.randomUUID(), role: "assistant", text: demoResponse(stored.trip, text), createdAt },
      );
      return save(stored);
    },
  };
}

function notFound() {
  return new GatewayError("NOT_FOUND", "이 탭에 저장된 여행을 찾을 수 없어요. 여행을 등록했던 탭에서 다시 열거나 새 여행을 등록해 주세요.");
}

function storageError() {
  return new GatewayError("STORAGE_UNAVAILABLE", "여행 데이터를 이 탭에 저장하거나 불러오지 못했어요. 브라우저의 저장소 설정과 남은 공간을 확인해 주세요.");
}

function addFifteen(time: string): string | null {
  const [hours, minutes] = time.split(":").map(Number);
  const next = hours * 60 + minutes + 15;
  return next < 24 * 60 ? `${String(Math.floor(next / 60)).padStart(2, "0")}:${String(next % 60).padStart(2, "0")}` : null;
}

function complete(stored: StoredTrip) {
  const { trip } = stored;
  const blockedId = stored.scenario === "needs-review" ? trip.stops.at(-1)!.id : null;
  // Deterministic examples, never a real travel feasibility calculation.
  const candidates = trip.stops.filter((stop, index) => {
    const proposed = addFifteen(stop.time);
    const next = trip.stops[index + 1];
    return stop.id !== blockedId && stop.booking === "none" && proposed && (!stop.endTime || proposed < stop.endTime) && (!next || next.date !== stop.date || proposed < next.time);
  }).sort((a, b) => priority(a.time) - priority(b.time)).slice(0, 2);
  const candidateIds = new Set(candidates.map((stop) => stop.id));
  const results: VerificationResult[] = trip.stops.map((stop) => {
    const base = { id: crypto.randomUUID(), stopId: stop.id, date: stop.date, title: stop.title, originalValue: stop.time };
    if (stop.id === blockedId) return {
      ...base, status: "needs_review", reason: "[데모] 이 일정의 이동 정보 확인을 마치지 못한 상황이에요.", impact: "다시 검증하기 전에는 여행 관리를 시작할 수 없어요.",
    };
    if (candidateIds.has(stop.id)) return {
      ...base, status: "adjusted", proposedValue: addFifteen(stop.time)!, reason: "[데모] 이동 여유 15분을 반영하는 일정 조정 예시예요. 실제 이동 시간은 조회하지 않았어요.", impact: "시작 시각 변경이 아래 일정과 여행 홈에 반영돼요.",
    };
    return {
      ...base, status: "unchanged", proposedValue: stop.time,
      reason: stop.booking === "booked" ? "입력 내용에 예약이 있어 시작 시각을 그대로 유지했어요. 업체 예약 확인은 수행하지 않았어요." : "[데모] 입력한 시작 시각을 유지하는 결과예요.",
      impact: "입력한 일정 유지 · 예약 변경 및 취소 실행 없음",
    };
  });
  trip.stops = trip.stops.map((stop) => candidateIds.has(stop.id) ? { ...stop, originalTime: stop.time, time: addFifteen(stop.time)! } : stop);
  trip.status = "ready";
  trip.verification = { status: "completed", progress: 100, stages: stages(100), results };
}

function priority(time: string) { return time === "11:00" ? 0 : time === "14:00" ? 1 : 2; }

function demoResponse(trip: Trip, message: string): string {
  const prefix = "[데모 응답 · 실제 AI 연결 전]\n";
  const requestedDate = message.match(/\d{4}-\d{2}-\d{2}/)?.[0];
  const requestedTime = message.match(/(?:[01]\d|2[0-3]):[0-5]\d/)?.[0];
  const stops = trip.stops.filter((stop) => !requestedDate || stop.date === requestedDate);
  if (!stops.length) return prefix + `${requestedDate}에는 등록된 일정이 없어요.`;
  const named = [...stops].sort((a, b) => b.title.length - a.title.length).filter((stop) => message.includes(stop.title));
  const selected = named.find((stop) => !requestedTime || stop.time === requestedTime) ?? named[0];
  if (selected) return prefix + `${selected.title}\n${selected.date} ${selected.time}${selected.endTime ? `–${selected.endTime}` : ""}\n${selected.notes}\n${selected.movement}\n장소 및 운영 정보는 실시간으로 확인하지 않았어요.`;
  if (/예약/.test(message)) {
    const booked = stops.filter((stop) => stop.booking === "booked");
    return prefix + (booked.length ? `입력한 계획에서 예약이 표시된 일정은 ${booked.length}개예요.\n${booked.map((stop) => `${stop.date} ${stop.time} ${stop.title}`).join("\n")}\n업체 예약 확인·변경은 실행하지 않았어요.` : "입력 내용에 예약이 있다고 표시한 일정은 없어요. 실제 예약 여부는 업체에서 확인해 주세요.");
  }
  const dates = [...new Set(stops.map((stop) => stop.date))];
  const dayNumber = (date: string) => Math.round((Date.parse(date) - Date.parse(trip.startDate)) / 86400000) + 1;
  return prefix + `현재 등록한 ${dates.length}일, ${stops.length}개 일정의 요약이에요.\n${dates.map((date) => `${dayNumber(date)}일차 · ${date}\n${stops.filter((stop) => stop.date === date).map((stop) => `${stop.time} ${stop.title}`).join(" → ")}`).join("\n\n")}\n데모에서는 일정 요약, 장소 이름을 포함한 일정 문의, 예약 목록 조회를 제공해요.`;
}

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetSessionState } from "./client";
import { answeringSession, CSRF, sessionCalls } from "./session-kit";
import { getTripRisks, itemRiskOf, problemText, requestRiskAlternatives, riskSignature, tripRisksOf } from "./risks";

const wire = { item_id: "stop-1", title: "한강 공원", status: "problem", checked_at: "2026-10-18T14:00:00+09:00", checked_for: "2026-10-18T15:00:00+09:00",
  oldest_confirmed_at: "2026-10-18T13:58:00+09:00", mode: "cached", problems: [
    { category: "traffic_control", label: "교통 통제", summary: "교통 통제: 공사", message: "공사로 양방향 전면 통제", source: "UTIC", ends_at: "2026-10-18T23:00:00+09:00", incident_id: "incident-1" },
    { category: "weather_warning", label: "기상 특보", kind: "강풍주의보", source: "KMA" }],
  unknown_categories: [{ category: "air_quality", label: "대기질", reason: "소스 응답 실패" }], categories: [] };

describe("실제 위험 응답 표시", () => {
  it("도로 원문과 종료 시각·출처를 보존하고 확인 불가를 별도로 남긴다", () => {
    const item = itemRiskOf(wire)!;
    expect(item.status).toBe("problem");
    expect(item.unknownCategories).toEqual(["대기질"]);
    expect(item.dataConfirmedAt).toBe(wire.oldest_confirmed_at);
    expect(item.problems[0]).toMatchObject({ source: "UTIC", endsAt: "2026-10-18T23:00:00+09:00", incidentId: "incident-1" });
    expect(item.problems.map(problemText)).toEqual(["공사로 양방향 전면 통제", "강풍주의보"]);
  });
  it("새 확인 시각만으로 같은 위험을 다시 알리지 않고 새 사건은 구분한다", () => {
    const first = itemRiskOf(wire)!;
    const later = itemRiskOf({ ...wire, checked_at: "2026-10-18T14:03:00+09:00" })!;
    expect(riskSignature([first])).toBe(riskSignature([later]));
    const changed = itemRiskOf({ ...wire, problems: [{ ...wire.problems[0], incident_id: "incident-2" }] })!;
    expect(riskSignature([first])).not.toBe(riskSignature([changed]));
  });
  it("누락되거나 잘못된 결과를 정상 확인으로 바꾸지 않는다", () => {
    expect(itemRiskOf({ item_id: "i1", status: "ok" })?.status).toBe("unknown");
    expect(itemRiskOf(null)).toBeNull();
    expect(() => tripRisksOf({ status: "unavailable" })).toThrow();
    expect(() => tripRisksOf({ items: [null] })).toThrow();
    expect(tripRisksOf({ items: [] }).items).toEqual([]);
  });
});

describe("위험 조회와 명시적 대안 요청", () => {
  let calls: { url: string; init: RequestInit }[], replies: Response[];
  beforeEach(() => {
    calls = []; replies = [];
    const memory = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
    vi.stubGlobal("window", { localStorage: memory, sessionStorage: memory });
    vi.stubGlobal("fetch", answeringSession(async (url, init) => {
      calls.push({ url, init }); return replies.shift() ?? new Response("{}", { status: 200 });
    }, { has: true }));
  });
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });
  const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });
  it("최초 새로 확인과 주기적 저장 정보 조회를 분리한다", async () => {
    replies.push(json({ trip_id: "t1", items: [wire], mode: "fresh" }), json({ trip_id: "t1", items: [wire], mode: "cached" }));
    await getTripRisks("t1", "ko", true);
    await getTripRisks("t1", "ko");
    expect(calls.map((call) => new URL(call.url).search)).toEqual(["?fresh=true", "?fresh=false"]);
    expect(calls.every((call) => !call.init.method || call.init.method === "GET")).toBe(true);
  });
  it("대안은 소유자 세션·CSRF를 사용한 별도 POST로만 요청한다", async () => {
    replies.push(json({ status: "offered", proposal_id: "p1" }));
    expect(await requestRiskAlternatives("t1", "stop/1", "ko")).toMatchObject({ status: "offered", proposalId: "p1" });
    expect(calls[0].url).toMatch(/\/trips\/t1\/risks\/stop%2F1\/alternatives$/);
    expect(calls[0].init.method).toBe("POST");
    expect(calls[0].init.credentials).toBe("include");
    expect(new Headers(calls[0].init.headers).get("X-CSRF-Token")).toBe(CSRF);
    expect(JSON.parse(String(calls[0].init.body))).toEqual({});
    expect(sessionCalls.some((call) => new URL(call.url).pathname.endsWith("/auth/session"))).toBe(false);
  });
  it.each(["already", "no_alternate", "unavailable", "no_risk", "stale", "ended"])("%s 상태를 성공적인 일정 변경으로 해석하지 않는다", async (status) => {
    replies.push(json({ status, proposal_id: status === "already" ? "p1" : null }));
    expect((await requestRiskAlternatives("t1", "s1", "ko")).status).toBe(status);
  });
  it.each([{ status: "offered" }, { status: "unexpected" }])("응답 누락은 확인 불가로 표시한다", async (body) => {
    replies.push(json(body));
    expect((await requestRiskAlternatives("t1", "s1", "ko")).status).toBe("unavailable");
  });
  it("후보 검증 자료의 실패와 서버 안내를 후보 없음으로 바꾸지 않는다", async () => {
    replies.push(json({ status: "unavailable", reason: "verification_failed", message: "대안의 안전 정보를 확인하지 못했어요",
      failed_categories: ["weather_warning", "traffic_control", 123, null] }));
    expect(await requestRiskAlternatives("t1", "s1", "ko")).toMatchObject({ status: "unavailable", reason: "verification_failed",
      message: "대안의 안전 정보를 확인하지 못했어요", failedCategories: ["weather_warning", "traffic_control"] });
  });
  it("조건을 만족한 후보 미확보 사유를 그대로 보존한다", async () => {
    replies.push(json({ status: "no_alternate", reason: "운영시간·이동 조건을 모두 만족하는 대안을 찾지 못했어요" }));
    expect(await requestRiskAlternatives("t1", "s1", "ko")).toMatchObject({ status: "no_alternate",
      reason: "운영시간·이동 조건을 모두 만족하는 대안을 찾지 못했어요", message: null, failedCategories: [] });
  });
});

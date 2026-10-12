import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { finishOnboarding, mockServer, start } from "./helpers";
import { openFinished } from "./plan-check-kit";

type Scenario = { code: string; expected_problem_ids?: string[]; evidence?: unknown };
type Input = { mode: "real" | "mock"; api_base: string; scenarios: Scenario[]; server_evidence?: unknown };
const inputFile = process.env.ALERT_SNAPSHOT_INPUT;
const input: Input | null = inputFile ? JSON.parse(readFileSync(inputFile, "utf8")) as Input : null;
const out = process.env.ALERT_SNAPSHOT_OUTPUT;
test.describe.configure({ mode: "serial" });
test.skip(!input || !out, "전용 실행기가 회차별 입력을 제공할 때만 화면을 보관합니다");

/** API 구현에서 근거 필드가 바뀌어도 장소·시간·실제 영향 판정 세 가지를 함께 요구한다. */
function liveMatches(value: unknown): Array<Record<string, unknown>> {
  const found: Array<Record<string, unknown>> = [];
  function visit(node: unknown, context: Record<string, unknown> = {}) {
    if (Array.isArray(node)) { node.forEach(child => visit(child, context)); return; }
    if (!node || typeof node !== "object") return;
    const obj = node as Record<string, unknown>;
    const current = { ...context, ...obj };
    const place = current.place as Record<string, unknown> | undefined;
    if (obj.verdict === "disrupted" && place && Number.isFinite(place.latitude) && Number.isFinite(place.longitude)
      && typeof current.starts_at === "string" && Array.isArray(obj.disruptions) && obj.disruptions.length > 0) {
      const stamp = Date.parse(current.starts_at);
      const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
      const date = new Date(stamp).toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
      if (Number.isFinite(stamp) && date === today && !JSON.stringify(obj).includes('"mode":"sample"')) found.push(current);
    }
    Object.values(obj).forEach(child => visit(child, current));
  }
  visit(value);
  return found;
}

async function snap(page: Page, name: string) {
  mkdirSync(out!, { recursive: true });
  const target = path.join(out!, name);
  await page.screenshot({ path: target, fullPage: true, animations: "disabled" });
}

test("mock 서버 대체안 미리 보기의 전후 화면을 구분해 보관", async ({ page, request }) => {
  test.skip(input?.mode !== "mock", "mock 서버 전용");
  await mockServer(request).reset();
  const server = await openFinished(page, request);
  await snap(page, "mock-before.png");
  await page.getByRole("button", { name: /전체 자동 추천/ }).click();
  await expect(page.getByRole("heading", { name: "수정안", exact: true })).toBeVisible();
  await expect(page.getByText(/바뀜 · 이전/).first()).toBeVisible();
  await snap(page, "mock-after.png");
  const calls = await server.received("POST", "/autofix");
  expect(calls.length).toBeGreaterThanOrEqual(1);
  expect(calls.every(call => call.body?.dry_run === true)).toBe(true);
  expect(await server.received("POST", "/edits")).toHaveLength(0);
  expect(await server.received("POST", "/confirm")).toHaveLength(0);
  writeFileSync(path.join(out!, "browser-verdict.json"), JSON.stringify({ mode: "mock", status: "passed", snapshots: 2,
    verification: "화면 반응만 확인", real_alert_verified: false }, null, 2));
});

test("실경보를 반영한 점검용 접수의 대체안과 전후 화면", async ({ page }) => {
  test.skip(input?.mode !== "real", "실제 cs 프로젝트 서버 전용");
  expect(input!.scenarios.length, "시험 일정 입력").toBeGreaterThan(0);
  // 새 빈 브라우저. 사용자의 저장된 인증 상태를 읽지 않는다.
  expect(await page.context().cookies()).toHaveLength(0);
  const blocked: string[] = [];
  const previews: Array<Record<string, unknown>> = [];
  const alternatives: Array<Record<string, unknown>> = [];
  const responses: Array<Record<string, unknown>> = [];
  await page.route("**/v1/web/**", async route => {
    const req = route.request();
    const url = new URL(req.url());
    if (url.origin !== new URL(input!.api_base).origin) {
      blocked.push("api_origin_mismatch"); await route.abort(); return;
    }
    const mutation = !["GET", "HEAD", "OPTIONS"].includes(req.method());
    if (mutation) {
      const allowedPath = /\/v1\/web\/(?:auth\/session|consents)$/.test(url.pathname)
        || url.pathname === "/v1/web/trip-intakes"
        || (/\/trip-intakes\/[0-9a-f-]+\/autofix$/.test(url.pathname) && req.postDataJSON()?.dry_run === true);
      const allowed = req.method() === "POST" && allowedPath;
      if (!allowed) { blocked.push(url.pathname); await route.abort(); return; }
    }
    await route.continue();
  });
  // 일정 원문과 실제 응답만. 인증 헤더·쿠키·URL 쿼리는 보관하지 않는다.
  page.on("response", async response => {
    const url = new URL(response.url());
    if (!/\/trip-intakes(?:\/[0-9a-f-]+)?(?:\/autofix)?$/.test(url.pathname)) return;
    if (!response.ok()) return;
    try {
      const data = await response.json() as Record<string, unknown>;
      responses.push({ endpoint: url.pathname, method: response.request().method(), data });
      if (url.pathname.endsWith("/autofix")) previews.push({ ...data, capture_intake_id: url.pathname.split("/").at(-2) });
    } catch { responses.push({ endpoint: url.pathname, status: "json_unreadable" }); }
  });
  let completed = 0;
  let noAlert = 0;
  try {
    await start(page, null);
    await finishOnboarding(page);
    for (const scenario of input!.scenarios) {
      expect(scenario.code).toMatch(/^test[1-9]\d*rt$/);
      await page.goto("/trips/new");
      await page.getByLabel("나의 여행 계획").fill(scenario.code);
      await page.getByRole("button", { name: "계획 확인하기" }).click();
      await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
      const intakeId = page.url().split("/").at(-1)!;
      let intake: Record<string, unknown> = {};
      await expect.poll(async () => {
        const response = await page.request.get(`${input!.api_base}/v1/web/trip-intakes/${intakeId}`);
        expect(response.ok()).toBe(true);
        intake = await response.json() as Record<string, unknown>;
        return ["review", "failed", "fatal"].includes(String(intake.status));
      }, { timeout: 240000, intervals: [1000, 3000] }).toBe(true);
      responses.push({ endpoint: `/v1/web/trip-intakes/${intakeId}`, method: "GET", data: intake });
      const fatal = intake.fatal as { code?: string } | null;
      if (fatal?.code === "no_live_alert") { noAlert += 1; continue; }
      expect(fatal, "실시간 경보 수집·매칭 실패는 성공으로 처리하지 않음").toBeNull();
      const review = intake.review as { test_scenario?: Record<string, unknown> };
      const metadata = review?.test_scenario;
      expect(metadata?.code, "접수 API가 시험 코드를 처리함").toBe(scenario.code);
      expect(metadata?.mode, "고정 시험을 실경보로 쓰지 않음").not.toBe("fixed");
      const matches = liveMatches(metadata);
      expect(matches.length, "당일 장소·시각·실제 영향 판정 근거").toBeGreaterThan(0);
      writeFileSync(path.join(out!, `${scenario.code}-matching.json`), JSON.stringify(matches, null, 2));
      await expect(page.getByRole("button", { name: "여행 등록", exact: true })).toBeVisible({ timeout: 240000 });
      await snap(page, `${scenario.code}-before.png`);
      await page.getByRole("button", { name: /전체 자동 추천/ }).click();
      await expect(page.getByRole("heading", { name: "수정안", exact: true })).toBeVisible();
      const currentPreviews = () => previews.filter(p => p.capture_intake_id === intakeId);
      await expect.poll(() => currentPreviews().length).toBeGreaterThan(0);
      const preview = currentPreviews().at(-1)!;
      expect(preview.applied, "미리 보기는 저장하지 않음").toBe(false);
      expect(preview.dry_run).toBe(true);
      const changed = preview.changed as Array<{ id?: string; from?: { id?: string; place?: Record<string, unknown> }; to?: { place?: Record<string, unknown>; starts_at?: string } }>;
      expect(changed.length, "실제 API 응답의 대체안").toBeGreaterThan(0);
      for (const match of matches) {
        const original = match.place as Record<string, unknown>;
        const change = changed.find(c => c.from?.place?.name === original.name);
        expect(change, `영향 장소 ${String(original.name)}의 대체안`).toBeTruthy();
        expect(change!.to?.place?.latitude, "대체 장소의 실제 좌표").toBeDefined();
        const date = new Date(String(match.starts_at)).toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
        expect(change!.to?.starts_at).toMatch(/^\d{2}:\d{2}$/);
        alternatives.push({ item_id: change!.id, place: change!.to!.place, starts_at: `${date}T${change!.to!.starts_at}:00+09:00`,
          original_place: original, original_starts_at: match.starts_at });
      }
      for (const id of scenario.expected_problem_ids ?? []) {
        expect(changed.some(change => change.id === id || change.from?.id === id), `영향 일정 ${id}의 대체안`).toBe(true);
      }
      await snap(page, `${scenario.code}-after.png`);
      completed += 1;
    }
    expect(blocked, "허용하지 않은 쓰기 요청").toEqual([]);
  } finally {
    writeFileSync(path.join(out!, "alternatives.json"), JSON.stringify(alternatives, null, 2));
    writeFileSync(path.join(out!, "intake-responses.json"), JSON.stringify(responses, null, 2));
    writeFileSync(path.join(out!, "browser-verdict.json"), JSON.stringify({ mode: "real",
      status: completed === input!.scenarios.length && blocked.length === 0 ? "passed" : noAlert === input!.scenarios.length && blocked.length === 0 ? "no_live_alert" : "failed",
      completed, noAlert, total: input!.scenarios.length, snapshots: completed * 2, blocked, server_evidence: input!.server_evidence }, null, 2));
  }
});

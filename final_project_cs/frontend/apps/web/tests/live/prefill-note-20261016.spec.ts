import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { mockServer, noHorizontalScroll, start } from "./helpers";
import { needsBadge } from "./plan-check-kit";

/**
 * `[2026-10-16 D-025]` 비서처럼 먼저 채우기 — 서버가 읽은 직후 빈칸을 채웠으면(`prefill.filled`) 그 일정의 첫 줄에 「✎ 먼저 채움 · 이유」가 보이고,
 * 목록 위 안내에 몇 곳을 채웠는지 · 이렇게 이해했어요(이동 · 조건 · 성향 원문) · 고객만 아는 질문이 보인다. 서버가 아무것도 안 보내면(옛 서버) 안내가 없다.
 * mock 서버의 화면 반응을 확인하는 자동 시험이다(실서버 아님) — 서버 응답은 `patchIntake` 로 서버가 그렇게 답한 것처럼 고쳐 쓴다.
 */
const INTAKE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const INTAKE_READ = `**/v1/web/trip-intakes/${INTAKE}`;
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- 서버 응답을 시험에서 고쳐 쓰는 자리라 모양을 고정하지 않는다
type Json = Record<string, any>;

// `[2026-10-16]` 시작 때 모방 서버를 초기화한다 — 없으면 앞 파일(`preferences.spec.ts`)이 남긴 상태로 「확인 필요」가 안 떠 전체 실행 · CI 에서 실패했다(따로 돌리면 통과)
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const REASON = "「광장시장」 — 가게 이름이 없는 자리 — 같은 지역 · 같은 종류에서 앞뒤 이동을 맞춰 보고 광장시장(으)로 채웠어요";

async function open(page: Page, request: APIRequestContext, patch?: (view: Json) => void) {
  await mockServer(request).scenario({ review: "on", board: "rich", readingPolls: 0, intakeEvents: "off" });
  if (patch) {
    await page.route(INTAKE_READ, async (route) => {
      if (route.request().method() !== "GET") { await route.continue(); return; }
      const response = await route.fetch();
      const view = await response.json();
      patch(view);
      await route.fulfill({ response, json: view });
    });
  }
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await expect(needsBadge(page)).toBeVisible();
}

function filled(view: Json) {
  const target = (view.review?.items ?? []).find((item: Json) => item.title === "광장시장") ?? view.review.items.at(-1);
  view.prefill = {
    filled: [{ item: target.id, title: target.title, owner: "dining_team", owner_label: "식당 팀", reason: REASON, gap: "meal_place", new: false }],
    questions: [{ kind: "lodging_name", question: "묵는 숙소 이름을 알려 주시면 숙소 기준으로 동선을 맞출게요", quote: null }],
    kept: [],
  };
  view.sources[0].understanding = {
    moves: [{ mode: "taxi", scope: "segment", from: "경복궁", to: "광장시장", quote: "택시로 이동할 거야" }],
    conditions: [{ code: "if_rain_indoor", quote: "비 오면 실내" }], preferences: [{ code: "kid_friendly", quote: "애들 데리고" }],
  };
}

test("서버가 먼저 채운 일정에는 「먼저 채움 · 이유」가, 목록 위에는 채운 수 · 이해한 말 · 묻는 것이 보인다", async ({ page, request }) => {
  await open(page, request, filled);
  const note = page.locator("[data-prefill-note]");
  await expect(note).toBeVisible();
  await expect(note).toContainText("1곳은 비어 있어서 먼저 채웠어요");
  await expect(note).toContainText("이렇게 이해했어요");
  await expect(note).toContainText("「택시로 이동할 거야」");
  await expect(note).toContainText("「비 오면 실내」");
  await expect(note).toContainText("「애들 데리고」");
  await expect(note.getByRole("listitem")).toHaveText(["묵는 숙소 이름을 알려 주시면 숙소 기준으로 동선을 맞출게요"]);
  // 일정 카드를 펼치면 첫 검사 줄이 「✎ 먼저 채움 · 이유」다(접힌 카드는 고칠 것만 보인다)
  const head = page.getByRole("article", { name: "광장시장", exact: true }).getByRole("heading").getByRole("button");
  await head.click();
  await expect(head).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("article", { name: "광장시장", exact: true }).getByText(`먼저 채움 · ${REASON}`)).toHaveCount(1);
  await expect(page.getByRole("article", { name: "경복궁 관람", exact: true }).getByText(/먼저 채움/)).toHaveCount(0);
});

/** `[2026-10-16 D-025 후속]` 서버가 계획에서 읽은 성향 · 조건을 담당에 넘긴다고 알린 것(`check.handoff`) — 하나는 우리가 채움, 하나는 고객 답 그대로. */
function handedOver(view: Json) {
  view.check.handoff = [
    { key: "survey.pace", label: "일정 여유", owner: "일정 짜기", value: "relaxed", text: "여유 있게", codes: ["slow_pace"], quotes: ["천천히 다닐래요"], status: "filled" },
    { key: "constraints.day_hours.end", label: "하루 끝 시각", owner: "일정 짜기 · 하루 마감", value: "21:00", text: "21:00까지", codes: ["finish_by:21:00"],
      quotes: ["9시까지는 숙소"], status: "filled" },
    { key: "survey.priority_details.mobility", label: "이동 수단", owner: "이동 판정 · 일정 짜기", value: ["public"], text: "대중교통", codes: ["prefer_transit"],
      quotes: ["지하철로"], status: "customer" },
  ];
}

test("계획에서 읽은 성향 · 조건을 어느 담당에 넘기는지 「우리가 채움」 / 「고객님 답 그대로」로 보인다", async ({ page, request }) => {
  await open(page, request, handedOver);
  const list = page.locator("[data-prefill-handoff]");
  await expect(list).toBeVisible();
  await expect(list.getByRole("listitem")).toHaveCount(3);
  await expect(list.locator('[data-mine="true"]').first()).toContainText("일정 여유 여유 있게 → 일정 짜기");
  await expect(list.locator('[data-mine="true"]').first()).toContainText("우리가 채움");
  await expect(list.locator('[data-mine="false"]')).toContainText("이동 수단 대중교통 → 이동 판정 · 일정 짜기");
  await expect(list.locator('[data-mine="false"]')).toContainText("고객님 답 그대로");
  for (const [width, height] of [[375, 812], [320, 640]]) {
    await page.setViewportSize({ width, height });
    await noHorizontalScroll(page);
  }
});

test("옛 서버(먼저 채운 기록 없음)에는 안내도 「먼저 채움」도 없다", async ({ page, request }) => {
  await open(page, request);
  await expect(page.locator("[data-prefill-note]")).toHaveCount(0);
  await expect(page.getByText(/먼저 채움|우리가 채움/)).toHaveCount(0);
});

test("375px · 320px 에서 먼저 채운 안내가 가로로 넘치지 않는다", async ({ page, request }) => {
  for (const [width, height] of [[375, 812], [320, 640]]) {
    await page.setViewportSize({ width, height });
    await open(page, request, filled);
    await expect(page.locator("[data-prefill-note]")).toBeVisible();
    await noHorizontalScroll(page);
  }
});

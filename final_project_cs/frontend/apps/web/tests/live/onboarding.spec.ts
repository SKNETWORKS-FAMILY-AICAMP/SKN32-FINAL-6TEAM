import { expect, test, type Page } from "@playwright/test";
import { agree, agreeTerms, checkPlan, hydrated, mockServer, noHorizontalScroll, openPreferencesFromMenu, pickLanguage, registerStubTrip, useKorean, openPane } from "./helpers";

/** Write a plan and press 「계획 확인하기」: the app goes to the plan-check screen of the mock server's intake. */
async function sendPlan(page: Page) {
  await hydrated(page);
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await checkPlan(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
}

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

test("소개에서 약관을 끝까지 읽고 동의한 뒤 취향 6문항을 마치면 등록 화면에 취향이 이어진다", async ({ page, request }) => {
  await mockServer(request).scenario({ trips: "none" });           // 동의를 기록하면 서버가 게스트 세션을 만든다 - 그 세션에 여행은 아직 없다
  await useKorean(page);
  await page.goto("/");
  await expect(page.locator("#intro-title")).toHaveText("서울 여행 일정을함께 확인해요.");
  await page.getByRole("button", { name: "다음 화면" }).first().click();
  await expect(page.locator("#how-title")).toBeInViewport();
  await page.getByRole("button", { name: "3. 일정 시작" }).click();
  await page.getByRole("button", { name: "내 일정 시작하기" }).click();
  await expect(page).toHaveURL(/\/start\?terms=required&returnTo=%2Ftrips%2Fnew$/);

  // ★`[2026-10-16 사용자 결정 — ST4F-601]` 화면이 보내 온 약관 화면에는 약관 카드만 있다(디스코드 · 취향 카드는 없다).
  await expect(page.locator('[data-card="2"]')).toHaveCount(0);
  await expect(page.locator('[data-card="0"]')).toHaveCount(0);
  await expect(page.getByRole("button", { name: /약관 동의/ })).toHaveAttribute("aria-expanded", "true");
  // ★`[2026-10-05]` 동의는 항목별이다: 필수(서비스 이용약관 · 개인정보 수집·이용)도 선택(민감정보 · 위치 · 알림 채널)도 바로 체크할 수 있다(`[사용자 지시]` 끝까지 읽기 잠금을 뺐다). 전문은 카드 안 상자에서 내려 읽고, 「전문 보기」는 크게 보여 줄 뿐이다.
  const serviceCheck = page.locator("#consent-service_terms");
  const privacyCheck = page.locator("#consent-privacy");
  const proceed = page.getByRole("button", { name: "동의하고 다음으로" });
  for (const code of ["service_terms", "privacy", "sensitive", "location", "alert_channel"]) {
    await expect(page.locator(`#consent-${code}`)).toBeEnabled();                       // 필수도 선택도 읽지 않고 바로 고를 수 있다
    await expect(page.locator(`#consent-${code}`)).not.toBeChecked();                   // 그리고 처음에는 비어 있다(미리 체크해 두지 않는다)
  }
  await expect(proceed).toBeDisabled();
  // 전문이 카드 안 상자에 있고, 상자는 제 안에서 스크롤된다(내용이 상자보다 길다)
  const box = page.locator('li[data-doc="service_terms"]').getByRole("region", { name: /전문/ });
  await expect(box).toBeVisible();
  const scrollable = await box.evaluate((element) => ({ over: element.scrollHeight > element.clientHeight + 20, auto: getComputedStyle(element).overflowY }));
  expect(scrollable).toEqual({ over: true, auto: "auto" });
  await box.evaluate((element) => { element.scrollTop = element.scrollHeight; });
  expect(await box.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  await page.locator('li[data-doc="service_terms"] label').click();                      // 읽지 않아도 필수를 바로 체크
  await expect(serviceCheck).toBeChecked();
  await expect(proceed).toBeDisabled();                                                  // 필수 하나만으로는 아직
  // 「전문 보기」는 크게 보여 줄 뿐: 열어도 체크 상태가 바뀌지 않고, 창 안 상자에서 바로 체크할 수 있다
  await page.locator('[data-action="read-terms"][data-doc="privacy"]').click();
  const reader = page.getByRole("dialog");
  await expect(reader).toBeVisible();
  await expect(privacyCheck).not.toBeChecked();
  await expect(reader.getByRole("checkbox")).toBeEnabled();
  await expect(reader.getByRole("status")).toHaveText("필수 항목이에요. 동의 여부를 선택해 주세요.");
  await reader.getByText(/^\[필수\].*만 14세 이상/).click();                              // 개인정보 항목은 만 14세 이상 확인을 함께 담는다
  await expect(reader).toHaveCount(0);
  await expect(privacyCheck).toBeChecked();
  await expect(proceed).toBeEnabled();
  await proceed.click();
  // ★`[2026-10-06 사용자 지시]` 처음 동의하면 취향 설문 없이 바로 계획 올리는 화면으로 간다. 취향 설문은 메뉴의 「여행 취향 설문」에서 따로 연다.
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(page.locator("#plan-source")).toBeVisible();
  await openPreferencesFromMenu(page);

  const heading = (name: string) => page.getByRole("heading", { name, exact: true });
  // ★카드가 넘어가는 동안의 누름은 화면이 무시한다. 제목이 「보이는」 것은 넘김 중에도 참이라 신호가 못 된다 —
  //   넘김이 끝나 그 카드 제목으로 초점이 옮겨진 것을 보고 다음을 누른다(CI 에서 이 차이로 실패했다, 2026-09-28).
  const settled = (card: number | "intro") => expect(page.locator(`#question-title-${card}`)).toBeFocused();
  await expect(heading("여행 취향 설문을 시작할게요")).toBeVisible();
  await expect(page.getByText(/추천할 때 참고할 여행 취향 정보를 모아요/)).toBeVisible();
  await expect(page.getByText(/‘응답하지 않고 넘어가기’를 눌러 건너뛸 수 있어요/)).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "답변한 질문" })).toHaveAttribute("aria-valuenow", "0");
  await page.getByRole("button", { name: "시작하기" }).click();
  await expect(heading("누구와 함께 떠나나요?")).toBeVisible();
  await settled(0);
  await page.getByRole("button", { name: "이전", exact: true }).click();
  await expect(heading("여행 취향 설문을 시작할게요")).toBeVisible();
  await settled("intro");
  await page.getByRole("button", { name: "시작하기" }).click();
  await expect(heading("누구와 함께 떠나나요?")).toBeVisible();
  await settled(0);
  const next = page.getByRole("button", { name: "다음", exact: true });
  const progress = page.getByRole("progressbar", { name: "답변한 질문" });
  const skip = page.getByRole("button", { name: "응답하지 않고 넘어가기" });
  await expect(next).toBeDisabled();
  // No `optional` mark on the preference cards (the Discord alerts card above carries its own).
  await expect(page.locator("#card-2").getByText("선택", { exact: true })).toHaveCount(0);
  // `[2026-10-19 사용자 지시]` No theme question any more: companions come first. One choice only — a second choice replaces the first.
  await expect(page.getByRole("button", { name: /인원 늘리기/ })).toHaveCount(0);
  await page.getByRole("button", { name: "친구" }).click();
  await page.getByRole("button", { name: "가족" }).click();
  await expect(page.getByRole("button", { name: "친구" })).toHaveAttribute("aria-pressed", "false");
  await expect(progress).toHaveAttribute("aria-valuenow", "1");
  await page.getByRole("button", { name: "가족" }).press("ArrowRight");

  // No theme, transport or nationality question: the priorities card comes second.
  await expect(heading("어떤 것을 더 중요하게 생각하나요?")).toBeVisible();
  await settled(1);
  await page.getByRole("button", { name: /^활동/ }).click();
  await page.getByRole("button", { name: /^자연관광/ }).click();
  // Skipping clears the answer but still counts toward progress; going back shows it cleared.
  await skip.click();
  await expect(progress).toHaveAttribute("aria-valuenow", "2");
  await settled(2);
  await page.getByRole("button", { name: "이전", exact: true }).click();
  await expect(heading("어떤 것을 더 중요하게 생각하나요?")).toBeVisible();
  await settled(1);
  await expect(page.getByRole("button", { name: /^활동/ })).toHaveAttribute("aria-pressed", "false");
  await expect(next).toBeDisabled();
  await page.getByRole("button", { name: /^활동/ }).click();
  await expect(next).toBeDisabled();
  // Activities take exactly three of the seven tourism classes.
  for (const name of ["자연관광", "역사관광"]) {
    await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
    await expect(next).toBeDisabled();
  }
  await page.getByRole("button", { name: /^축제\/공연\/행사/ }).click();
  await next.click();
  await expect(heading("실내와 실외 중 어디가 좋으세요?")).toBeVisible();
  await settled(2);
  await page.getByRole("button", { name: "실내", exact: true }).first().click();
  await expect(next).toBeDisabled();
  await page.getByRole("button", { name: "상관없음", exact: true }).last().click();
  await next.click();
  // No plan-change question: the Course Keeper card decides that (`[2026-10-19 사용자 지시]`).
  await expect(heading("여행할 때 어느 정도 여유가 좋으세요?")).toBeVisible();
  await settled(3);
  await expect(page.getByRole("button", { name: "설문 마치기" })).toBeDisabled();
  await skip.click();

  await expect(heading("여행 취향 설문을 마쳤어요")).toBeVisible();
  await expect(page.getByText("가족", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "여행 계획 등록하기" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(page.getByText("여행 취향 설문", { exact: true })).toBeVisible();
  await expect(page.getByText("가족", { exact: true })).toBeVisible();

  await page.locator("form").getByRole("button", { name: "이전", exact: true }).click();
  // ★`[2026-10-16 ST4F-601]` 「이전」은 계획 담기를 연 화면으로 돌아간다 — 여기서는 설문의 「여행 계획 등록하기」(전에는 늘 소개 화면).
  await expect(page).toHaveURL(/\/start$/);
  await openPreferencesFromMenu(page);
  await expect(heading("여행 취향 설문을 마쳤어요")).toBeVisible();

  // The finished survey rides with the trip registration (`flow.spec.ts` checks what the server receives); here the plan goes on to its check.
  await page.getByRole("button", { name: "여행 계획 등록하기" }).click();
  await sendPlan(page);
});

test("설정에서 바꾼 언어는 새로고침 후에도 유지되고, 여행 화면도 그 언어로 열린다", async ({ page }) => {
  await agree(page);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  // `[2026-10-03 사용자 결정]` 기본은 한국어다. 영어로 바꾸면 새로고침 뒤에도 영어로 남고, 다시 한국어로 돌릴 수 있다.
  // `[2026-10-13 메뉴 = 마이페이지]` 언어 카드는 메뉴가 아니라 설정 화면(메뉴 › 설정)에 있다.
  await expect(page.locator("html")).toHaveAttribute("lang", "ko");
  await expect(page.locator("#intro-title")).toContainText("서울 여행 일정을");
  await noHorizontalScroll(page);

  await pickLanguage(page, "메뉴", "English");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator("#intro-title")).toContainText("Let’s check your");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("#intro-title")).toContainText("Let’s check your");

  await pickLanguage(page, "Menu", "한국어");
  await expect(page.locator("#intro-title")).toContainText("서울 여행 일정을");
  await expect(page).toHaveTitle("구구루트 · 당신다운 여행의 시작");

  await page.reload();
  await expect(page.locator("#intro-title")).toContainText("서울 여행 일정을");
  await registerStubTrip(page);
  // `[2026-10-07 사용자 결정 — 목업 C안]` 여행 화면은 시트의 「일정 | 채팅」으로 칸을 바꾼다(플로팅 버튼 스위치는 없다).
  await openPane(page, "채팅");
  await expect(page.locator("#trip-pane-chat")).not.toHaveAttribute("inert");
  await noHorizontalScroll(page);
});

test("설정 화면에서 언어를 고르면 카드가 접히고 첫 화면 문구가 바뀌며(첫 화면에는 언어 카드가 없다), 이용 방법 캡처를 마우스로 끌거나 버튼으로 넘겨 볼 수 있다", async ({ page }) => {
  // `[2026-10-13 메뉴 = 마이페이지]` 언어 카드는 설정 화면(`/mypage`)에만 있다(전에는 메뉴). 설정 화면은 필수 약관에 동의해야 열린다.
  await agree(page);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await expect(page.getByRole("button", { name: /LANGUAGE/ })).toHaveCount(0);
  // The page starts in Korean (`[2026-10-03 사용자 결정]`).
  await page.goto("/mypage");
  const card = page.getByRole("button", { name: /LANGUAGE/ });
  await expect(card).toHaveAttribute("aria-expanded", "false");
  await expect(card).toContainText("한국어");
  await card.click();
  await expect(card).toHaveAttribute("aria-expanded", "true");
  await page.getByRole("button", { name: "English", exact: true }).click();
  await expect(card).toHaveAttribute("aria-expanded", "false");
  await expect(card).toBeFocused();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await page.goto("/");
  await expect(page.locator("#intro-title")).toContainText("Let’s check your");
  await page.reload();
  await expect(page.locator("#intro-title")).toContainText("Let’s check your");
  // Back to Korean — the guide below is read in Korean.
  await pickLanguage(page, "Menu", "한국어");
  await expect(page.locator("#intro-title")).toContainText("서울 여행 일정을");

  await page.getByRole("button", { name: "다음 화면" }).first().click();
  const guide = page.getByRole("region", { name: "구구루트 이용 방법" });
  const firstShot = guide.getByRole("group", { name: "1 / 4" }).getByRole("img");
  await expect(firstShot).toHaveAccessibleName("앱 화면: 나의 여행 취향 알려주기");
  await expect.poll(() => firstShot.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);

  const track = guide.getByRole("group", { name: "1 / 4" }).locator("..");
  // Measure only after the page has finished snapping to the second screen.
  await expect.poll(() => page.locator("main").evaluate((main) => Math.abs(main.scrollTop - (main.children[1] as HTMLElement).offsetTop))).toBeLessThan(2);
  const dragBy = async (distance: number) => {
    const box = (await track.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + distance, box.y + box.height / 2, { steps: 8 });
    await page.mouse.up();
  };
  const offsetFromCard = (index: number) => track.evaluate((element, card) => {
    const cards = [...element.children] as HTMLElement[];
    return Math.abs(element.scrollLeft - (cards[card].offsetLeft - cards[0].offsetLeft));
  }, index);
  await dragBy(-150);
  await expect(guide.getByText("2 / 4", { exact: true })).toBeVisible();
  await expect.poll(() => offsetFromCard(1)).toBeLessThan(2);
  await dragBy(-20);
  await expect.poll(() => offsetFromCard(1)).toBeLessThan(2);
  await dragBy(200);
  await expect(guide.getByText("1 / 4", { exact: true })).toBeVisible();
  await expect.poll(() => offsetFromCard(0)).toBeLessThan(2);

  const next = guide.getByRole("button", { name: "다음 단계" });
  for (const step of [2, 3, 4]) {
    await next.click();
    await expect(guide.getByText(`${step} / 4`, { exact: true })).toBeVisible();
  }
  await expect(next).toHaveAttribute("aria-disabled", "true");
  await noHorizontalScroll(page);
});

test("시작 화면은 한 번만: 마친 뒤 새로고침해도 약관·취향이 남고, 소개 버튼은 바로 등록 화면으로 가며, 메뉴에서 고칠 수 있다", async ({ page }) => {
  await useKorean(page);
  await page.goto("/start");
  await agreeTerms(page);                                                                // `[2026-10-16 ST4F-601]` 약관 카드는 스스로 열리고, 동의하면 그 자리에서 취향 카드가 열린다
  await page.getByRole("button", { name: "시작하기" }).click();
  for (let at = 0; at < 4; at += 1) {
    await expect(page.locator(`#question-title-${at}`)).toBeFocused();
    await page.getByRole("button", { name: "응답하지 않고 넘어가기" }).click();
  }
  await expect(page.getByRole("heading", { name: "여행 취향 설문을 마쳤어요", exact: true })).toBeVisible();

  // A reload (or a later visit) does not start over.
  await page.reload();
  await expect(page.getByRole("button", { name: /약관 동의/ })).toContainText("필수 내용을 확인했어요.");
  await expect(page.getByRole("button", { name: /여행 취향 설문/ })).toContainText("4가지 질문을 모두 마쳤어요.");
  await expect(page.getByRole("button", { name: /여행 취향 설문/ })).toBeEnabled();

  // The intro button no longer sends the customer through it again.
  await page.goto("/");
  await page.getByRole("button", { name: "3. 일정 시작" }).click();
  await expect(page.getByText("약관에 동의했어요. 취향 설문은 메뉴에서 할 수 있어요.")).toBeVisible();   // `[2026-10-16 ST4F-601]` 문구
  await page.getByRole("button", { name: "내 일정 시작하기" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(page.getByText("여행 취향 설문", { exact: true })).toBeVisible();

  // The menu's 「여행 취향」 row opens the preferences for changes (`[2026-10-13]` the row left My page, which is the settings screen now).
  await openPreferencesFromMenu(page);
  await expect(page.getByRole("heading", { name: "여행 취향 설문을 마쳤어요", exact: true })).toBeVisible();
});

test("소개의 첫 단어는 「계획 담기」이고, 처음 동의하면 취향 설문 없이 바로 계획 올리는 화면으로 가며, 취향 설문은 메뉴에서 따로 연다 (2026-10-06 사용자 지시)", async ({ page, request }) => {
  await mockServer(request).scenario({ trips: "none" });
  await useKorean(page);
  await page.goto("/");
  await page.getByRole("button", { name: "3. 일정 시작" }).click();
  await expect(page.getByText("계획 담기", { exact: true })).toBeVisible();
  await expect(page.getByText("나의 취향", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "내 일정 시작하기" }).click();
  await expect(page).toHaveURL(/\/start\?terms=required&returnTo=%2Ftrips%2Fnew$/);   // 약관 미동의 진입은 필수 항목을 펼쳐 보여준다
  await expect(page.getByRole("button", { name: /약관 동의/ })).toHaveAttribute("aria-expanded", "true");
  for (const code of ["service_terms", "privacy"]) await page.locator(`li[data-doc="${code}"] label`).click();
  await page.getByRole("button", { name: "동의하고 다음으로" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);                              // 취향 설문이 아니라 계획 올리는 화면
  await expect(page.locator("#plan-source")).toBeVisible();
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await page.getByRole("dialog", { name: "메뉴" }).getByRole("button", { name: /^여행 취향 설문/ }).click();
  await expect(page).toHaveURL(/\/start$/);
  await expect(page.getByRole("heading", { name: "여행 취향 설문을 시작할게요", exact: true })).toBeVisible();
});

test("약관에 동의하지 않았으면 소개 버튼은 시작 화면으로 가고, 다른 화면은 열리지 않고 약관 화면으로 돌아가며, 동의한 뒤에는 메뉴의 여행 취향이 설정 전이라고 알린다", async ({ page }) => {
  await useKorean(page);
  await page.goto("/");
  await page.getByRole("button", { name: "3. 일정 시작" }).click();
  await expect(page.getByText("약관 확인부터 함께할게요.")).toBeVisible();
  await page.getByRole("button", { name: "내 일정 시작하기" }).click();
  await expect(page).toHaveURL(/\/start\?terms=required&returnTo=%2Ftrips%2Fnew$/);
  // ★`[2026-10-05 사용자 지시]` 필수 약관에 동의하지 않으면 앱을 쓸 수 없다: 마이페이지로 곧장 가도 약관 화면으로 돌아온다.
  await page.goto("/mypage");
  await expect(page).toHaveURL(/\/start\?terms=required&returnTo=%2Fmypage$/);
  await agree(page);
  await page.goto("/mypage");
  // `[2026-10-13 메뉴 = 마이페이지]` 여행 취향은 메뉴의 줄 하나(설정 화면에는 없다) — 누르면 시작 화면의 취향 카드.
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  const preferences = page.getByRole("dialog", { name: "메뉴" }).getByRole("button", { name: /^여행 취향 설문/ });
  await expect(preferences).toContainText("아직 설정하지 않았어요");
  await preferences.click();
  await expect(page).toHaveURL(/\/start$/);
});

test("저장된 값이 깨져 있어도 시작 화면은 처음 상태로 열린다", async ({ page }) => {
  await useKorean(page);
  await page.addInitScript(() => localStorage.setItem("tripilot.web.onboarding.v2", '{"agreed":"yes","answers":42}'));
  await page.goto("/start");
  await expect(page.getByRole("button", { name: /약관 동의/ })).toContainText("시작하기 전에 확인해 주세요.");
  await expect(page.getByRole("button", { name: /여행 취향 설문/ })).toBeDisabled();
});

test("계획 확인 전 화면(첫 화면 · 시작(약관) · 계획 담기)에는 메뉴 옆 지구본이 있어 약관 동의 전에도 언어를 바꾸고, 계획 담기의 항로 지킴이 아이콘은 없으며, 그 뒤 화면에는 지구본이 없다 (2026-10-13 사용자 결정)", async ({ page }) => {
  // `[2026-10-13 사용자 결정]` 언어는 설정 화면(필수 약관 동의 뒤에 열린다)과 계획 확인 전 화면의 지구본 두 곳에서 바꾼다 — 동의 전 방문자는 지구본으로 약관의 언어를 고른다.
  await useKorean(page);                                                                  // 세션도 동의도 없는 첫 방문
  await page.goto("/");
  const header = page.getByRole("banner");
  const globe = header.getByRole("button", { name: "언어 · 한국어", exact: true });
  const [g, m] = [(await globe.boundingBox())!, (await header.getByRole("button", { name: "메뉴", exact: true }).boundingBox())!];
  expect(g.x + g.width).toBeLessThanOrEqual(m.x);                                         // 메뉴 단추 바로 왼쪽, 같은 줄
  expect(Math.abs(g.y - m.y)).toBeLessThan(1);
  await globe.click();
  await expect(globe).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("button", { name: "한국어", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "English", exact: true })).toHaveCount(0);
  await expect(globe).toBeFocused();

  await page.getByRole("button", { name: "3. 일정 시작" }).click();
  await page.getByRole("button", { name: "내 일정 시작하기" }).click();
  await expect(page).toHaveURL(/\/start\?terms=required&returnTo=%2Ftrips%2Fnew$/);
  await header.getByRole("button", { name: "언어 · 한국어", exact: true }).click();
  await page.getByRole("button", { name: "English", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("button", { name: "English", exact: true })).toHaveCount(0);   // 고르면 목록이 닫히고
  await expect(header.getByRole("button", { name: "Language · English", exact: true })).toBeFocused();
  await expect(page.locator('li[data-doc="service_terms"]')).toContainText("GuguRoute Terms of Service");   // 약관을 영어로 읽는다

  // 계획 담기(계획 올리기)에도 지구본이 있고, 그 자리에 있던 항로 지킴이 아이콘은 없다. 그 뒤 화면(내 여행 목록)은 메뉴 › 설정에서만 바꾼다.
  await header.getByRole("button", { name: "Language · English", exact: true }).click();
  await page.getByRole("button", { name: "한국어", exact: true }).click();
  for (const code of ["service_terms", "privacy"]) await page.locator(`li[data-doc="${code}"] label`).click();
  await page.getByRole("button", { name: "동의하고 다음으로" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(header.getByRole("button", { name: "언어 · 한국어", exact: true })).toBeVisible();
  await expect(header.getByRole("button", { name: /^항로 지킴이/ })).toHaveCount(0);
  await page.goto("/trips");
  await expect(header.getByRole("button", { name: "메뉴", exact: true })).toBeVisible();
  await expect(header.getByRole("button", { name: /^언어 · / })).toHaveCount(0);
});

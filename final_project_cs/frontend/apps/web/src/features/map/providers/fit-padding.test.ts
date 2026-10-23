import { expect, it } from "vitest";
import { fitPadding, visibleLift } from "./fit-padding";

it("보이는 칸 가운데는 머리줄과 시트 차이의 절반만큼 지도 가운데보다 아래다", () => {
  expect(visibleLift(64, 24)).toBe(20);
  expect(visibleLift()).toBe(0);
  expect(visibleLift(0, 40)).toBe(-20);
});

it.each([150, 306, 600])("좁은 지도 높이 %s에서도 경로에 절반 이상을 남긴다", (height) => {
  const padding = fitPadding(375, height, 64, 20);
  expect(padding.top + padding.bottom).toBeLessThanOrEqual(height / 2);
  expect(padding.left + padding.right).toBeLessThanOrEqual(375 / 2);
});
it("공간이 있으면 머리·겹치는 시트와 원래 여백을 보존한다", () => {
  expect(fitPadding(402, 600, 64, 20)).toEqual({ top: 114, right: 50, bottom: 70, left: 50 });
});

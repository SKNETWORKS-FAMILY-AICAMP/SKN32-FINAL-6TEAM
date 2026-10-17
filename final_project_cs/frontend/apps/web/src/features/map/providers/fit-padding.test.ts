import { expect, it } from "vitest";
import { fitPadding } from "./fit-padding";

it.each([150, 306, 600])("좁은 지도 높이 %s에서도 경로에 절반 이상을 남긴다", (height) => {
  const padding = fitPadding(375, height, 64, 20);
  expect(padding.top + padding.bottom).toBeLessThanOrEqual(height / 2);
  expect(padding.left + padding.right).toBeLessThanOrEqual(375 / 2);
});
it("공간이 있으면 머리·겹치는 시트와 원래 여백을 보존한다", () => {
  expect(fitPadding(402, 600, 64, 20)).toEqual({ top: 114, right: 50, bottom: 70, left: 50 });
});

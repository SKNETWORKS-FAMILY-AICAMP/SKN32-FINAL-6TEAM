import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { EdgeChips } from "./map-controls";

function render(x: number, count: number, moving = false) {
  return renderToStaticMarkup(createElement(EdgeChips, { width: 375, moving, onGo: () => {}, chips: [{ ids: Array.from({ length: count }, (_, n) => `stop-${n}`), labels: Array.from({ length: count }, (_, n) => `${n + 1}`), x, y: 130, angle: 45, distanceM: 980 }] }));
}
it("방향 각도가 같아도 실제 지도 반쪽에 따라 좌우를 구분한다", () => {
  expect(render(70, 1)).toContain('data-side="left"');
  expect(render(300, 1)).toContain('data-side="right"');
});
it("중앙 경계는 오른쪽 순서로 처리한다", () => {
  expect(render(187.5, 1)).toContain('data-side="right"');
});
it("두 개는 번호, 세 개 이상은 여러 일정 아이콘으로 표시하고 전체 번호를 읽는다", () => {
  expect(render(300, 2)).toContain('>1 · 2</span>');
  const many = render(300, 4);
  expect(many).toContain('data-multiple="true"');
  expect(many).toContain('lucide-layers');
  expect(many).toContain('aria-label="1 · 2 · 3 · 4번 일정이 화면 밖에 있어요 · 980m');
});
it("이동 중에만 시각적 거리를 숨기며 읽어주는 거리와 동작은 유지한다", () => {
  expect(render(70, 1)).toContain('<small');
  const moving = render(70, 1, true);
  expect(moving).not.toContain('<small');
  expect(moving).toContain('980m · 누르면 그곳으로 가요');
});

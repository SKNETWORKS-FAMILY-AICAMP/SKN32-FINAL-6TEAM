import { describe, expect, it } from "vitest";
import { setMarkerHidden } from "./visibility";

function element() {
  const attrs = new Map<string, string>();
  return {
    style: { visibility: "visible" }, dataset: {} as Record<string, string>, inert: false,
    getAttribute: (key: string) => attrs.get(key) ?? null,
    setAttribute: (key: string, value: string) => { attrs.set(key, value); },
    removeAttribute: (key: string) => { attrs.delete(key); },
  } as unknown as HTMLElement;
}

describe("거리 칩으로 대체한 마커 가시성", () => {
  it("숨길 때 시각 표시·접근성·키보드 진입을 함께 막고 복구 때 원래 값을 돌린다", () => {
    const pin = element();
    setMarkerHidden(pin, true);
    expect(pin.style.visibility).toBe("hidden");
    expect(pin.inert).toBe(true);
    expect(pin.getAttribute("aria-hidden")).toBe("true");
    setMarkerHidden(pin, false);
    expect(pin.style.visibility).toBe("visible");
    expect(pin.inert).toBe(false);
    expect(pin.getAttribute("aria-hidden")).toBeNull();
  });

  it("이동 중 같은 숨김 신호를 되풀이해도 원래 상태를 덮어쓰지 않는다", () => {
    const pin = element();
    pin.inert = true;
    pin.setAttribute("aria-hidden", "false");
    setMarkerHidden(pin, true);
    setMarkerHidden(pin, true);
    setMarkerHidden(pin, false);
    expect(pin.style.visibility).toBe("visible");
    expect(pin.inert).toBe(true);
    expect(pin.getAttribute("aria-hidden")).toBe("false");
  });

  it("한 묶음의 본체와 분리 연결선을 모두 숨기고 원래 객체를 재사용한다", () => {
    const body = element(), leader = element();
    const nodes = [body, leader];
    nodes.forEach((node) => setMarkerHidden(node, true));
    expect(nodes.every((node) => node.style.visibility === "hidden")).toBe(true);
    nodes.forEach((node) => setMarkerHidden(node, false));
    expect(nodes[0]).toBe(body);
    expect(nodes[1]).toBe(leader);
    expect(nodes.every((node) => node.style.visibility === "visible")).toBe(true);
  });
});

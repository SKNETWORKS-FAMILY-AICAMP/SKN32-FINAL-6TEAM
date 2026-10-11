import { describe, expect, it } from "vitest";
import { silenceSnapshot } from "./silence-snapshot";

describe("무소식 알림 발생 시점", () => {
  it("늦게 진입해도 실제 시간으로 표시하고 같은 단계에서는 재알림하지 않는다", () => {
    const first = silenceSnapshot(null, 37);
    expect(first).toEqual({ stage: 30, seconds: 37 });
    expect(silenceSnapshot(first, 59)).toBe(first);
    const minute = silenceSnapshot(first, 64);
    expect(minute).toEqual({ stage: 60, seconds: 64 });
    expect(silenceSnapshot(minute, 127)).toBe(minute);
  });
  it("진행 소식이 오면 초기화하고 다음 정체의 진입 시간을 새로 잡는다", () => {
    const first = silenceSnapshot(null, 35);
    expect(silenceSnapshot(first, 0)).toBeNull();
    expect(silenceSnapshot(null, 29)).toBeNull();
    expect(silenceSnapshot(null, 32)).toEqual({ stage: 30, seconds: 32 });
  });
});

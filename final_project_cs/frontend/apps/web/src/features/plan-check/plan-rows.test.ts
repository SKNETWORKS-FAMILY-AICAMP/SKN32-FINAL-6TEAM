import { describe, expect, it } from "vitest";
import { legText } from "./plan-rows";

describe("the line under a move says only how long and how far", () => {
  it("cuts the server's sentence at the minutes: the mode is an icon, so the name of the line is not said twice", () => {
    expect(legText("지하철 3호선 10분 · 1.1km")).toBe("10분 · 1.1km");
    expect(legText("지하철 3호선→1호선 17분 · 2.1km")).toBe("17분 · 2.1km");
    expect(legText("도보 8분 · 0.4km")).toBe("8분 · 0.4km");
    expect(legText("버스 402번 1시간 5분 · 12.3km")).toBe("1시간 5분 · 12.3km");
  });

  it("leaves the sentence whole when it has no minutes — nothing is made up and nothing is lost", () => {
    expect(legText("택시 약 8,000원")).toBe("택시 약 8,000원");
    expect(legText("")).toBe("");
  });
});

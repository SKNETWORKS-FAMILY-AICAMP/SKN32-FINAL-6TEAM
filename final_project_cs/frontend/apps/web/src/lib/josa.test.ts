import { describe, expect, it } from "vitest";
import { eul, eun, gwa, ro } from "./josa";

describe("Korean particles after a word's last sound", () => {
  it("picks each particle by the final consonant", () => {
    expect([eul("경복궁"), eul("남산타워")]).toEqual(["경복궁을", "남산타워를"]);
    expect([ro("창덕궁"), ro("서울"), ro("남산타워")]).toEqual(["창덕궁으로", "서울로", "남산타워로"]);
    expect([gwa("경복궁"), gwa("남산타워")]).toEqual(["경복궁과", "남산타워와"]);
  });

  it("`[2026-10-20]` 은/는", () => {
    expect([eun("올리브영"), eun("남산타워"), eun("Tower")]).toEqual(["올리브영은", "남산타워는", "Tower는"]);
  });
});

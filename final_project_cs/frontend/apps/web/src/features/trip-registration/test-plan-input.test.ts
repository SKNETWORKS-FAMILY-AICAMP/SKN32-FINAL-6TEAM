import { describe, expect, it } from "vitest";
import { planOfInput, textToSend } from "./test-plan-input";

const plans = [
  { code: "test1", text: "서울 2일 여행 · 4명\n\n1일차 · 2026-10-18\n09:00~10:30 경복궁 관람" },
  { code: "test16", text: "서울 2일 여행 · 4명\n\n1일차 · 2026-10-18\n15:00 더 플라자 호텔 서울 체크인" },
];

describe("planOfInput — 입력칸 내용으로 선택된 시험 계획을 찾는다", () => {
  it("코드만 적어도(대소문자·앞뒤 공백 무시) 찾는다", () => {
    expect(planOfInput(plans, "  TEST16 ")?.code).toBe("test16");
  });
  it("목록에서 고른 뒤 입력칸에 채워진 원문이어도 찾는다", () => {
    expect(planOfInput(plans, plans[1].text)?.code).toBe("test16");
    expect(planOfInput(plans, `${plans[0].text}\n`)?.code).toBe("test1");
  });
  it("원문을 고치면 선택이 풀린다", () => {
    expect(planOfInput(plans, `${plans[1].text}\n19:00 저녁`)).toBeUndefined();
    expect(planOfInput(plans, "test1을 참고해서 서울을 여행할 거예요")).toBeUndefined();
  });
  it("목록을 아직 못 읽었으면 찾지 않는다", () => {
    expect(planOfInput(undefined, "test1")).toBeUndefined();
  });
});

describe("textToSend — 제출할 글", () => {
  it("고른 계획의 원문을 그대로 두면 코드를 보낸다", () => {
    expect(textToSend(plans[1].text, plans[1])).toBe("test16");
    expect(textToSend(`${plans[1].text}\n`, plans[1])).toBe("test16");
  });
  it("조금이라도 고쳤으면 고친 글을 보낸다", () => {
    const edited = `${plans[1].text}\n19:00~20:00 인사동 산책`;
    expect(textToSend(edited, plans[1])).toBe(edited);
  });
  it("고른 계획이 없으면 입력한 글 그대로(코드를 직접 적은 것 포함)", () => {
    expect(textToSend("  TEST1  ", null)).toBe("  TEST1  ");
    expect(textToSend("10/18 09:00 경복궁 관람", null)).toBe("10/18 09:00 경복궁 관람");
  });
});

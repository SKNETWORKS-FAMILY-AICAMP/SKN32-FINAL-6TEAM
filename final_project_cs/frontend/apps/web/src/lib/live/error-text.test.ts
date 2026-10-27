import { describe, expect, it } from "vitest";
import { REFUSAL_TEXT, refusalSentence } from "./error-text";

describe("the customer's sentence for a server refusal (ST4F-611 · 문구 대조표 113)", () => {
  it("keeps a server sentence that is already polite Korean on the Korean screen — it carries the case's own details", () => {
    expect(refusalSentence("agent_key_limit", "사용 중인 에이전트 키가 10개예요 — 쓰지 않는 키를 폐기해 주세요", undefined, "ko"))
      .toBe("사용 중인 에이전트 키가 10개예요 — 쓰지 않는 키를 폐기해 주세요");
    expect(refusalSentence("too_soon", "시험 발송은 잠시 뒤에 다시 할 수 있어요(30초 뒤)", undefined, "ko")).toBe("시험 발송은 잠시 뒤에 다시 할 수 있어요(30초 뒤)");
    expect(refusalSentence("intake_incomplete", "등록 전에 채워야 할 값이 있습니다", undefined, "ko")).toBe("등록 전에 채워야 할 값이 있습니다");
  });

  it("replaces a developer sentence (해라체) or an English one with the web's own", () => {
    expect(refusalSentence("too_many_auth", "로그인을 너무 자주 시도했다 — 잠시 뒤에 다시 한다", undefined, "ko")).toBe("로그인을 너무 자주 시도했어요. 잠시 뒤 다시 해 주세요.");
    expect(refusalSentence("not_found", "resource not found", undefined, "ko")).toBe("찾을 수 없어요. 지워졌거나 주소가 바뀌었을 수 있어요.");
  });

  it("speaks English on the English screen, whatever language the server wrote in", () => {
    expect(refusalSentence("stale_itinerary", "그 사이 일정이 바뀌었어요 — 새로 불러와 주세요", undefined, "en")).toBe("The plan changed in the meantime. Please reload it.");
    expect(refusalSentence("guest_trip_limit", "로그인하지 않으면 여행을 1개까지 만들 수 있어요", { cap: 1 }, "en")).toBe("Without signing in you can keep up to 1 trip.");
  });

  it("names an unknown code in a general sentence instead of showing the server's words", () => {
    expect(refusalSentence("reload_failed", "선언을 읽지 못했다", undefined, "ko")).toBe("요청을 처리하지 못했어요. 잠시 뒤 다시 해 주세요. (reload_failed)");
    expect(refusalSentence("HTTP_502", undefined, undefined, "en")).toBe("The request could not be completed. Please try again shortly. (HTTP_502)");
  });

  it("says the service is switching to a new version when Caddy answers for the server during a deploy (D-CS-019)", () => {
    const caddy = "서비스를 새 판으로 바꾸는 중이거나 잠시 연결이 끊겼습니다. 잠시 뒤 다시 시도해 주세요.";
    expect(refusalSentence("service_updating", caddy, undefined, "ko")).toBe(caddy);
    expect(refusalSentence("service_updating", caddy, undefined, "en")).toBe("The service is switching to a new version. Please try again shortly.");
  });

  it("says the plan was not saved and nothing changed when 「완료」 fails to write (503 save_failed, web-intakes /confirm 7)", () => {
    const server = "지금 일정을 저장하지 못했어요(저장 오류) — 일정은 바꾸지 않았어요. 잠시 뒤 「완료」를 다시 눌러 주세요.";
    expect(refusalSentence("save_failed", server, { version: 3 }, "ko")).toBe(server);
    expect(refusalSentence("save_failed", server, { version: 3 }, "en"))
      .toBe("We couldn't save the plan just now. Nothing was changed. Please try again shortly.");
  });

  it("has a Korean and an English sentence for every code, both ending politely", () => {
    for (const [code, text] of Object.entries(REFUSAL_TEXT)) {
      const [ko, en] = typeof text === "function" ? text({ cap: 2 }) : text;
      expect(ko, code).toMatch(/(요|니다)[.!?]?$/);
      expect(en.length, code).toBeGreaterThan(5);
    }
  });
});

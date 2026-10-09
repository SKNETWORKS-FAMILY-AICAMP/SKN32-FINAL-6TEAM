import { afterEach, expect, it } from "vitest";
import { LiveError } from "./client";
import { clearIntakeFailure, intakeFailure, rememberIntakeFailure, type IntakeStart } from "./intake-start";

afterEach(clearIntakeFailure);
const start = { files: [new Blob(["서울 여행"], { type: "text/plain" }) as File], plan: { start_date: "2026-10-15", days: 2, party_size: 2, wish: "서울 여행" } } as IntakeStart;

it("게스트 일정 상한 오류가 입력·첨부·계획 조건과 로그인 안내를 보존한다", () => {
  rememberIntakeFailure(start, new LiveError("guest_trip_limit", "로그인이 필요해요", { login_required: true }));
  expect(intakeFailure()).toEqual({ message: "로그인이 필요해요", files: start.files, plan: start.plan, loginRequired: true });
});

it("다른 오류를 게스트 한도로 오인하지 않는다", () => {
  rememberIntakeFailure(start, new LiveError("usage_limit", "잠시 뒤 다시 해 주세요"));
  expect(intakeFailure()?.loginRequired).toBe(false);
});

it("기존 문자열 호출도 계속 지원한다", () => {
  rememberIntakeFailure(start, "돌아왔어요");
  expect(intakeFailure()?.message).toBe("돌아왔어요");
});

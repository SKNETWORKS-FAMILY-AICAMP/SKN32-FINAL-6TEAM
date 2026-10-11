import { afterEach, expect, it } from "vitest";
import { clearIntakeArrival, clearIntakeFailure, forgetIntakeSubmission, intakeFailure, rememberEmptyIntake, rememberIntakeArrival } from "./intake-start";

afterEach(() => { clearIntakeArrival("empty"); forgetIntakeSubmission("empty"); clearIntakeFailure(); });

it("도착 표시를 지운 뒤에도 제출 글과 첨부 파일을 빈 결과에서 복원한다", () => {
  const file = new Blob(["서울 여행 메모"], { type: "text/plain" }) as File;
  rememberIntakeArrival("empty", "서울 여행을 가고 싶어요", [file]);
  clearIntakeArrival("empty");
  rememberEmptyIntake("empty", "일정을 찾지 못했어요", "읽힌 원문");
  expect(intakeFailure()).toEqual({ message: "일정을 찾지 못했어요", text: "서울 여행을 가고 싶어요", files: [file], plan: null });
});

it("직접 연 접수는 읽힌 원문을 복원하고 다른 접수의 파일을 가져오지 않는다", () => {
  const file = new Blob(["다른 계획"]) as File;
  rememberIntakeArrival("empty", "현재 입력", [file]);
  rememberEmptyIntake("another", "다시 입력해 주세요", "서울에서 여행하고 싶어요");
  expect(intakeFailure()).toEqual({ message: "다시 입력해 주세요", text: "서울에서 여행하고 싶어요", files: [], plan: null });
});

it("일정이 있는 결과에서 제출본을 잊으면 파일이 이후 빈 결과에 남지 않는다", () => {
  rememberIntakeArrival("empty", "서울 여행", [new Blob(["계획"]) as File]);
  forgetIntakeSubmission("empty");
  rememberEmptyIntake("empty", "일정을 찾지 못했어요", "복원 원문");
  expect(intakeFailure()?.files).toEqual([]);
  expect(intakeFailure()?.text).toBe("복원 원문");
});

it("파일 전용 제출의 빈 글은 기존 글 초안을 덮어쓸 값으로 만들지 않는다", () => {
  const file = new Blob(["메모"]) as File;
  rememberIntakeArrival("empty", "", [file]);
  rememberEmptyIntake("empty", "일정을 찾지 못했어요", "");
  expect(intakeFailure()).toEqual({ message: "일정을 찾지 못했어요", text: undefined, files: [file], plan: null });
});

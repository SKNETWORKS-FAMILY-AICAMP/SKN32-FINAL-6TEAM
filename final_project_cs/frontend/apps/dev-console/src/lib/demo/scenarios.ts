import type { FactRow, JsonObject, RunResult, RunStep, TestInput, TestRequest, TestTarget } from "../model";

const modes = { bus: "버스", walk: "도보", taxi: "택시" };
const routeMinutes = { bus: 40, walk: 55, taxi: 23 };
const venueRef = "fixture:venue-sample-01:v1";
const diningRef = "fixture:dining-sample-01:v1";
const routeRef = "fixture:route-sample-01:v1";

function minutes(time: string) {
  const [hours, mins] = time.split(":").map(Number);
  return hours * 60 + mins;
}

function formatTime(value: number) {
  const clock = `${String(Math.floor(value / 60) % 24).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
  return value >= 1440 ? `다음 날 ${clock}` : clock;
}

interface Scenario {
  input: JsonObject;
  response: JsonObject;
  observations: FactRow[];
  comparisons: FactRow[];
  evidenceRefs: string[];
  result: RunResult;
}

function activity(input: TestInput, version: TestRequest["version"], arrivalMinutes = minutes(input.time)): Scenario {
  const end = arrivalMinutes + input.durationMinutes;
  const entryConflict = arrivalMinutes > 990;
  const closingConflict = end > 1080;
  const expectedConflict = entryConflict || closingConflict;
  const actualConflict = (version === "B" && entryConflict) || closingConflict;
  const actual = actualConflict ? "마감 조건 초과" : "마감 조건 충족";
  const expected = expectedConflict ? "마감 조건 초과" : "마감 조건 충족";
  return {
    input: { place: "샘플 전시관 A", arrival: formatTime(arrivalMinutes), visit_minutes: input.durationMinutes, timezone: "Asia/Seoul" },
    response: { id: venueRef, name: "샘플 전시관 A", last_entry: "16:30", closes_at: "18:00", timezone: "Asia/Seoul" },
    observations: [
      { label: "입장 마감", value: "16:30", reference: venueRef },
      { label: "폐관 시각", value: "18:00", reference: venueRef },
    ],
    comparisons: [
      { label: "예상 도착 / 입장 마감", value: `${formatTime(arrivalMinutes)} / 16:30 → ${version === "A" ? "판정에서 누락" : entryConflict ? `${arrivalMinutes - 990}분 초과` : "충족"}`, reference: venueRef },
      { label: "예정 관람 종료 / 폐관", value: `${formatTime(end)} / 18:00 → ${closingConflict ? "초과" : "충족"}`, reference: venueRef },
    ],
    evidenceRefs: [venueRef],
    result: {
      actual, expected, matched: actual === expected,
      summary: version === "A" ? "샘플 A는 관람 종료와 폐관만 비교하며 입장 마감 조건을 누락합니다." : "샘플 B는 입장 마감과 폐관 시각을 각각 확인합니다. 실제 모델 평가 결과는 아닙니다.",
      output: { deadline_status: actualConflict ? "conflict" : "satisfied", arrival: formatTime(arrivalMinutes), visit_end: formatTime(end), last_entry: "16:30", closes_at: "18:00", evidence_refs: [venueRef] },
    },
  };
}

function dining(input: TestInput): Scenario {
  const start = minutes(input.time);
  const end = start + input.durationMinutes;
  const overlap = Math.max(0, Math.min(end, 1020) - Math.max(start, 900));
  const actual = overlap > 0 ? "휴게시간 이용 확인 필요" : "휴게시간 겹침 없음";
  return {
    input: { restaurant: "샘플 식당 B", reservation_time: input.time, meal_minutes: input.durationMinutes, reservation_fixed: true, timezone: "Asia/Seoul" },
    response: { id: diningRef, name: "샘플 식당 B", break_start: "15:00", break_end: "17:00", reservation_exception: null },
    observations: [
      { label: "휴게시간", value: "15:00–17:00", reference: diningRef },
      { label: "예약 손님 예외", value: "샘플 응답에 정보 없음", reference: diningRef },
    ],
    comparisons: [
      { label: "예정 식사", value: `${input.time}–${formatTime(end)} (${input.durationMinutes}분)` },
      { label: "휴게시간과 겹치는 구간", value: `${overlap}분`, reference: diningRef },
      { label: "예약 보존", value: `${input.time} 예약 유지` },
    ],
    evidenceRefs: [diningRef],
    result: { actual, expected: actual, matched: true,
      summary: overlap > 0 ? "예약은 유지합니다. 예약 손님에게 휴게시간이 적용되는지 샘플 응답에 없어 확인 필요 상태로 반환합니다." : "예정 식사와 샘플 휴게시간이 겹치지 않습니다. 예약 가능 여부를 보장하는 결과는 아닙니다.",
      output: { status: overlap > 0 ? "needs_confirmation" : "no_overlap", reservation_time: input.time, reservation_preserved: true, overlap_minutes: overlap, reservation_exception: null, evidence_refs: [diningRef] },
    },
  };
}

function mobility(input: TestInput): Scenario {
  const departure = minutes(input.time);
  const arrival = departure + routeMinutes[input.transport];
  const actual = `${modes[input.transport]} · ${formatTime(arrival)} 도착`;
  return {
    input: { origin: "샘플 식당 B", destination: "샘플 전시관 A", departure: input.time, preferred_mode: input.transport, timezone: "Asia/Seoul" },
    response: { id: routeRef, origin: "샘플 식당 B", destination: "샘플 전시관 A", routes: Object.entries(routeMinutes).map(([mode, duration]) => ({ mode, duration_minutes: duration })) },
    observations: Object.entries(routeMinutes).map(([mode, duration]) => ({ label: modes[mode as keyof typeof modes], value: `${duration}분`, reference: routeRef })),
    comparisons: Object.entries(routeMinutes).map(([mode, duration]) => ({ label: modes[mode as keyof typeof modes], value: `${formatTime(departure + duration)} 도착 · ${mode === input.transport ? "선호 조건 일치 · 선택" : "대안"}`, reference: routeRef })),
    evidenceRefs: [routeRef],
    result: { actual, expected: actual, matched: true,
      summary: "선호 이동수단의 경로를 반환합니다. 입장 가능 여부는 액티비티팀이 판정합니다.",
      output: { mode: input.transport, departure: input.time, duration_minutes: routeMinutes[input.transport], arrival: formatTime(arrival), evidence_refs: [routeRef] },
    },
  };
}

function step(id: string, label: string, owner: TestTarget, phase: number, props: Partial<RunStep> = {}): RunStep {
  return { id, label, owner, phase, status: "completed", input: {}, observations: [], comparisons: [], output: {}, evidenceRefs: [], summary: "샘플 단계 완료", ...props };
}

export function buildScenario(runId: string, request: TestRequest): { steps: RunStep[]; result: RunResult; failureStepId: string } {
  if (request.target !== "core") {
    const scenario = request.target === "activity" ? activity(request.input, request.version) : request.target === "dining" ? dining(request.input) : mobility(request.input);
    const id = (name: string) => `${runId}:${name}`;
    return {
      steps: [
        step(id("input"), "입력 전달", request.target, 0, { input: scenario.input, output: scenario.input, summary: "고정된 실행 입력을 팀에 전달했습니다." }),
        step(id("lookup"), "조회 응답", request.target, 1, { input: scenario.input, observations: scenario.observations, evidenceRefs: scenario.evidenceRefs, output: { source: "local_fixture", response: scenario.response, evidence_refs: scenario.evidenceRefs }, summary: "고정된 샘플 응답을 읽었습니다. 외부 API 호출은 없습니다." }),
        step(id("compare"), "비교·판정", request.target, 2, { input: scenario.input, comparisons: scenario.comparisons, evidenceRefs: scenario.evidenceRefs, output: scenario.result.output, summary: scenario.result.summary }),
        step(id("output"), "최종 출력", request.target, 3, { input: { step_ref: id("compare") }, output: scenario.result.output, evidenceRefs: scenario.evidenceRefs, summary: scenario.result.actual }),
      ],
      result: scenario.result, failureStepId: id("lookup"),
    };
  }

  const meal = dining({ ...request.input, time: "14:30" });
  const route = mobility(request.input);
  const visit = activity(request.input, request.version, minutes(request.input.time) + routeMinutes[request.input.transport]);
  const id = (name: string) => `${runId}:${name}`;
  const outputs = { dining: meal.result.output, mobility: route.result.output, activity: visit.result.output };
  const evidenceRefs = [diningRef, routeRef, venueRef];
  return {
    steps: [
      step(id("dispatch"), "요청 전달", "core", 0, { input: { reservation_time: "14:30", departure: request.input.time, duration_minutes: request.input.durationMinutes, preferred_mode: request.input.transport }, output: { team_tasks: [id("dining"), id("mobility")] }, summary: "독립적인 요식업 확인과 이동 조회를 같은 구간에 배정했습니다." }),
      step(id("dining"), "예약·휴게시간 확인", "dining", 1, { input: meal.input, observations: meal.observations, comparisons: meal.comparisons, output: meal.result.output, evidenceRefs: meal.evidenceRefs, summary: meal.result.summary }),
      step(id("mobility"), "경로·도착 시각 조회", "mobility", 1, { input: route.input, observations: route.observations, comparisons: route.comparisons, output: route.result.output, evidenceRefs: route.evidenceRefs, summary: route.result.summary }),
      step(id("activity"), "입장·관람 조건 판정", "activity", 2, { input: { ...visit.input, arrival_source_step: id("mobility") }, observations: visit.observations, comparisons: visit.comparisons, output: visit.result.output, evidenceRefs: [...visit.evidenceRefs, routeRef], summary: visit.result.summary }),
      step(id("collect"), "계약 검증·결과 취합", "core", 3, { input: { team_step_refs: [id("dining"), id("mobility"), id("activity")] }, comparisons: [{ label: "결과 연결", value: "같은 실행 ID의 세 팀 출력 취합" }, { label: "근거 참조", value: "세 샘플 응답 참조 확인" }], output: outputs, evidenceRefs, summary: "코어는 팀별 결과와 근거 참조를 취합합니다. 장소·식당의 업무 조건은 각 팀이 판정했습니다." }),
    ],
    result: { actual: `${visit.result.actual} · ${meal.result.actual}`, expected: `${visit.result.expected} · ${meal.result.expected}`, matched: visit.result.matched && meal.result.matched && route.result.matched, summary: "고정 예약은 유지하고 세 팀의 결과를 연결한 통합 샘플입니다. 실제 에이전트 호출은 없습니다.", output: outputs },
    failureStepId: id("mobility"),
  };
}

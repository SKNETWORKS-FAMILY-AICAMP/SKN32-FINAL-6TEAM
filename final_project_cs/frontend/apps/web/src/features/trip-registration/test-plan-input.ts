/** 테스트 계획을 고르면 입력칸에 원문이 채워진다. 어떤 계획이 선택된 것인지, 제출할 때 무엇을 보낼지를 정한다. */
export interface PlanText { code: string; text: string }

/** 입력칸에 코드(test1)만 적었거나, 준비된 계획의 원문이 그대로 들어 있으면 그 계획이 선택된 것이다. */
export function planOfInput<T extends PlanText>(plans: readonly T[] | undefined, value: string): T | undefined {
  const typed = value.trim();
  return plans?.find((plan) => plan.code === typed.toLowerCase() || plan.text.trim() === typed);
}

/**
 * 제출할 글. 목록에서 고른 계획의 원문을 고치지 않았으면 코드를 보낸다 — 서버가 코드를 원문으로 풀면서
 * 시험 계획으로 기록하기 때문이다. 조금이라도 고쳤으면 고친 글을 그대로 보낸다.
 */
export function textToSend(value: string, chosen: PlanText | null): string {
  return chosen && value.trim() === chosen.text.trim() ? chosen.code : value;
}

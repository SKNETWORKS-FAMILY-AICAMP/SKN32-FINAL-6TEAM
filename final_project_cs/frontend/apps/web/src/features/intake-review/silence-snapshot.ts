export type SilenceSnapshot = { stage: 30 | 60; seconds: number } | null;

/** 알림 단계에 처음 진입한 실제 경과시간이다. 현재 시간을 흉내 내거나 매초 재알림하지 않는다. */
export function silenceSnapshot(previous: SilenceSnapshot, quiet: number): SilenceSnapshot {
  const stage = quiet >= 60 ? 60 : quiet >= 30 ? 30 : null;
  if (stage === null) return null;
  return previous?.stage === stage ? previous : { stage, seconds: quiet };
}

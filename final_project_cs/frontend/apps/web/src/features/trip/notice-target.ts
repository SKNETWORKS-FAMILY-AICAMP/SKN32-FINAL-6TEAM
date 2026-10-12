import type { Notice, Proposal } from "@/lib/live/extras";

/** 알림이 제안 조회보다 먼저 도착해도 대상 정보를 한 번 다시 읽은 뒤 표시한다. */
export async function resolveNoticeTarget(notice: Notice, proposals: Proposal[], reload: () => Promise<Proposal[]>): Promise<Proposal[]> {
  if (notice.type !== "proposal_request" || proposals.some((entry) => entry.id === notice.proposalId)) return proposals;
  return reload();
}

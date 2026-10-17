import { JourneyShell } from "@/components/layout/journey-shell";
import { NoticePage } from "@/features/support/notice-board";

export default async function Page({ params }: { params: Promise<{ noticeId: string }> }) {
  const { noticeId } = await params;
  return <JourneyShell view="other" title={["공지", "Notice"]}><NoticePage id={noticeId} /></JourneyShell>;
}

import { JourneyShell } from "@/components/layout/journey-shell";
import { NoticeBoard } from "@/features/support/notice-board";

export default function Page() {
  return <JourneyShell view="other" title={["공지사항", "Notices"]}><NoticeBoard /></JourneyShell>;
}

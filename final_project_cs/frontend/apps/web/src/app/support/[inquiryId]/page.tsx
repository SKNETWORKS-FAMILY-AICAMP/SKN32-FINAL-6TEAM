import { JourneyShell } from "@/components/layout/journey-shell";
import { InquiryPage } from "@/features/support/support";

export default async function Page({ params }: { params: Promise<{ inquiryId: string }> }) {
  const { inquiryId } = await params;
  return <JourneyShell view="other" title={["문의 내역", "Inquiry"]}><InquiryPage id={inquiryId} /></JourneyShell>;
}

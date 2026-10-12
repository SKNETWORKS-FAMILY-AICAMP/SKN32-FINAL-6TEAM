import { Onboarding } from "@/features/onboarding/onboarding";

export default async function StartPage({ searchParams }: { searchParams: Promise<{ terms?: string }> }) {
  const params = await searchParams;
  return <Onboarding termsRequired={params.terms === "required"} />;
}

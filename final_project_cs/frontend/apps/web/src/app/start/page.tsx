import { Onboarding } from "@/features/onboarding/onboarding";

export default async function StartPage({ searchParams }: { searchParams: Promise<{ terms?: string; returnTo?: string; signup?: string }> }) {
  const params = await searchParams;
  return <Onboarding signupRequired={params.signup === "1"} termsRequired={params.terms === "required" || params.signup === "1"} returnTo={params.returnTo ?? null} />;
}

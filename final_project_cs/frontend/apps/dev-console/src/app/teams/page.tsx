import { Suspense } from "react";
import { TeamTestsScreen } from "@/features/team-tests/team-tests-screen";

export default function TeamsPage() {
  return <Suspense fallback={<p role="status">팀별 테스트를 불러오고 있습니다.</p>}><TeamTestsScreen /></Suspense>;
}

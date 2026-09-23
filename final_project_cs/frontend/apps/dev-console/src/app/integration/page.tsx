import { Suspense } from "react";
import { TeamTestsScreen } from "@/features/team-tests/team-tests-screen";
export default function Page() { return <Suspense fallback={<p role="status">코어 통합 테스트를 불러오고 있습니다.</p>}><TeamTestsScreen integration /></Suspense>; }

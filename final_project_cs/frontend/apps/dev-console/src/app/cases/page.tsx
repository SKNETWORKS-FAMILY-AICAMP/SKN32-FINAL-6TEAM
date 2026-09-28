import { Suspense } from "react";
import { CasesWorkbench } from "@/features/cases/cases-workbench";

export default function CasesPage() {
  return <Suspense fallback={<p role="status">테스트 사례 화면을 준비하고 있어요.</p>}><CasesWorkbench /></Suspense>;
}

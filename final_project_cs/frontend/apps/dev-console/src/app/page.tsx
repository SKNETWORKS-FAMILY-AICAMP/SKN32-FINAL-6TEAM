import { Suspense } from "react";
import { ManagementWorkspace } from "@/components/management-workspace";

export default function Page() {
  return <Suspense fallback={<p role="status">관리 화면을 불러오고 있습니다.</p>}><ManagementWorkspace /></Suspense>;
}

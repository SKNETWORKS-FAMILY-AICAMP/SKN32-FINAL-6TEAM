import { RunPage } from "@/features/runs/run-page";
export default async function Page({ params }: { params: Promise<{ runId: string }> }) { const { runId } = await params; return <RunPage id={runId} />; }

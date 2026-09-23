"use client";

import { useRouter } from "next/navigation";
import { ButtonLink, Notice, PageHeading, QueryState } from "@/components/ui";
import { useCreateRun, useRun } from "@/lib/queries";
import { RunInspector } from "./run-inspector";

export function RunPage({ id }: { id: string }) {
  const router = useRouter();
  const query = useRun(id);
  const create = useCreateRun();
  return <><PageHeading eyebrow="개발 작업공간 / 실행 기록" title="실행 상세" description="테스트의 입력, 수집된 값과 반환 결과를 확인합니다." action={<ButtonLink href="/teams">팀별 테스트</ButtonLink>} /><QueryState loading={query.isPending} error={query.error} retry={() => void query.refetch()} />{create.error && <Notice tone="error">{create.error.message}</Notice>}{query.data && <RunInspector run={query.data} onRetry={create.isPending ? undefined : run => create.mutate({ request: run.request, retryOf: run.id }, { onSuccess: next => router.push(`/runs/${next.id}`) })} />}</>;
}

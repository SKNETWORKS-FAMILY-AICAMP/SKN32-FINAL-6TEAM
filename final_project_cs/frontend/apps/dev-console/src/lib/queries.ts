"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { gateway } from "./gateway";
import type { Run, TestRequest } from "./model";

export const queryKeys = { run: (id?: string) => ["run", id] as const, cases: ["cases"] as const, case: (id?: string) => ["case", id] as const, comparison: (id?: string) => ["comparison", id] as const };

export function useRun(id?: string) {
  return useQuery({ queryKey: queryKeys.run(id), queryFn: () => gateway.getRun(id!), enabled: !!id, refetchInterval: query => query.state.data?.status === "running" ? 350 : false });
}

export function useCreateRun() {
  const client = useQueryClient();
  return useMutation({ mutationFn: ({ request, retryOf }: { request: TestRequest; retryOf?: string }) => gateway.createRun(request, retryOf), onSuccess: (run: Run) => client.setQueryData(queryKeys.run(run.id), run) });
}

export function useCases() { return useQuery({ queryKey: queryKeys.cases, queryFn: () => gateway.listCases() }); }
export function useTestCase(id?: string) { return useQuery({ queryKey: queryKeys.case(id), queryFn: () => gateway.getCase(id!), enabled: !!id }); }
export function useComparison(id?: string) { return useQuery({ queryKey: queryKeys.comparison(id), queryFn: () => gateway.getComparison(id!), enabled: !!id }); }

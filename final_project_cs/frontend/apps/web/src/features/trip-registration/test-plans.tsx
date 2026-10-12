"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/live/client";
import { useSettings, useT } from "@/lib/settings";
import styles from "./test-plans.module.css";

interface PreparedPlan { code: string; name: string; description: string; expected: string; text: string }
interface Catalog { enabled: boolean; scenarios: PreparedPlan[] }

/** 목록은 부가 기능이다. 읽기를 기다리거나 실패해도 일반 계획 입력을 막지 않는다. */
export function TestPlans({ value, onChoose, disabled }: { value: string; onChoose: (code: string) => void; disabled: boolean }) {
  const { language } = useSettings();
  const t = useT();
  const query = useQuery({ queryKey: ["test-plans", language], queryFn: () => api<Catalog>("/v1/web/test-scenarios", language), retry: false });
  const entry = query.data?.scenarios.find((plan) => plan.code === value.trim().toLowerCase());
  if (query.data && !query.data.enabled) return <p className={styles.help}>{t("시험 일정 입력이 꺼져 있어요.", "Test plan shortcuts are turned off.")}</p>;
  return <div className={styles.box}>
    <label htmlFor="test-plan-code">{t("테스트 계획", "Test plan")}</label>
    <select id="test-plan-code" value={entry?.code ?? ""} disabled={disabled || !query.data} onChange={(event) => { if (event.target.value) onChoose(event.target.value); }}>
      <option value="">{query.isPending ? t("준비된 계획 불러오는 중…", "Loading prepared plans…") : t("test1~test12 중에서 선택", "Choose test1–test12")}</option>
      {query.data?.scenarios.map((plan) => <option key={plan.code} value={plan.code}>{plan.code} · {plan.name}</option>)}
    </select>
    {query.error ? <p className={styles.help}>{t("시험 목록을 불러오지 못했어요.", "Could not load test plans.")} <button type="button" onClick={() => void query.refetch()}>{t("다시 불러오기", "Try again")}</button></p>
      : entry ? <><p className={styles.help} role="status">{entry.description} {entry.expected}</p>
        <details><summary>{t("준비된 계획 원문 보기", "View prepared plan")}</summary><pre>{entry.text}</pre></details></>
        : <p className={styles.help}>{t("위 입력란에 test1처럼 적어도 준비된 계획으로 확인해요.", "You can also type test1 in the plan box above.")}</p>}
  </div>;
}

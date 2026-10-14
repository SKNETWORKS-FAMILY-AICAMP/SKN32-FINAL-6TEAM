"use client";

import { useQuery } from "@tanstack/react-query";
import { useRef, type KeyboardEvent } from "react";
import { Check, ChevronDown } from "lucide-react";
import { openApi } from "@/lib/live/client";
import { useSettings, useT } from "@/lib/settings";
import styles from "./test-plans.module.css";
import { planOfInput } from "./test-plan-input";

interface PreparedPlan { code: string; name: string; description: string; expected: string; text: string; category?: string }
interface Catalog { enabled: boolean; scenarios: PreparedPlan[] }
const categories = [
  ["normal", "문제 없는 기본안", "No intentional issues"],
  ["time", "시간 겹침", "Overlapping times"],
  ["hours", "운영시간·휴무", "Opening hours / closures"],
  ["place", "장소 미정", "Unspecified place"],
  ["mobility", "이동 여유", "Travel time"],
  ["input", "입력 확인", "Input checks"],
  ["general", "일반 흐름", "General flow"],
] as const;
function categoryOf(plan: PreparedPlan) { return categories.find(([code]) => code === plan.category) ?? categories[categories.length - 1]; }

/** 목록은 부가 기능이다. 읽기를 기다리거나 실패해도 일반 계획 입력을 막지 않는다. */
export function TestPlans({ value, onChoose, disabled }: { value: string; onChoose: (code: string, text: string) => void; disabled: boolean }) {
  const { language } = useSettings();
  const t = useT();
  const picker = useRef<HTMLDetailsElement>(null);
  const trigger = useRef<HTMLElement>(null);
  const query = useQuery({ queryKey: ["test-plans", language], queryFn: () => openApi<Catalog>("/v1/web/test-scenarios", language), retry: false });
  const entry = planOfInput(query.data?.scenarios, value);
  const selectedCategory = entry && categoryOf(entry);
  const close = () => { if (picker.current) picker.current.open = false; trigger.current?.focus(); };
  function navigate(event: KeyboardEvent<HTMLDetailsElement>) {
    if (event.key === "Escape" && picker.current?.open) { event.preventDefault(); event.stopPropagation(); close(); return; }
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key) || !picker.current?.open) return;
    const options = [...event.currentTarget.querySelectorAll<HTMLButtonElement>("button[data-plan-code]")];
    const index = options.indexOf(document.activeElement as HTMLButtonElement);
    const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1 : index < 0 ? (event.key === "ArrowUp" ? options.length - 1 : 0) : (index + (event.key === "ArrowUp" ? -1 : 1) + options.length) % options.length;
    event.preventDefault(); options[next]?.focus();
  }
  if (query.data && !query.data.enabled) return <p className={styles.help}>{t("시험 일정 입력이 꺼져 있어요.", "Test plan shortcuts are turned off.")}</p>;
  return <div className={styles.box}>
    <span className={styles.label}>{t("테스트 계획", "Test plan")}</span>
    <details ref={picker} className={styles.picker} onKeyDown={navigate} onToggle={event => { if (event.currentTarget.open) event.currentTarget.scrollIntoView({ block: "nearest" }); }} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false; }}>
      <summary ref={trigger} id="test-plan-code" aria-label={t("테스트 계획", "Test plan")} aria-disabled={disabled || !query.data} onClick={event => { if (disabled || !query.data) event.preventDefault(); }}>
        <span className={styles.selection}>
          {selectedCategory && <span className={styles.badge} data-category={selectedCategory[0]}>{t(selectedCategory[1], selectedCategory[2])}</span>}
          <span>{entry ? `${entry.code} · ${entry.name}` : query.isPending ? t("준비된 계획 불러오는 중…", "Loading prepared plans…") : t("분류별 테스트 계획 선택", "Choose a test plan by category")}</span>
        </span><ChevronDown size={18} aria-hidden="true" />
      </summary>
      {!disabled && query.data && <div className={styles.options} aria-label={t("분류별 테스트 계획", "Test plans by category")}>
        {categories.map(category => {
          const plans = query.data.scenarios.filter(plan => categoryOf(plan)[0] === category[0]);
          return plans.length > 0 && <fieldset key={category[0]} className={styles.group}>
            <legend><span className={styles.badge} data-category={category[0]}>{t(category[1], category[2])}</span><span className={styles.count}>{plans.length}</span></legend>
            {plans.map(plan => <button key={plan.code} type="button" data-plan-code={plan.code} data-category={category[0]} aria-pressed={entry?.code === plan.code} onClick={() => { onChoose(plan.code, plan.text); close(); }}>
              <span className={styles.code}>{plan.code}</span><span>{plan.name}</span><Check size={16} aria-hidden="true" className={entry?.code === plan.code ? styles.checked : styles.unchecked} />
            </button>)}
          </fieldset>;
        })}
      </div>}
    </details>
    {query.error ? <p className={styles.help}>{t("시험 목록을 불러오지 못했어요.", "Could not load test plans.")} <button type="button" onClick={() => void query.refetch()}>{t("다시 불러오기", "Try again")}</button></p>
      : entry ? <><p className={styles.help} role="status">{entry.description} {entry.expected}</p>
        <details><summary>{t("준비된 계획 원문 보기", "View prepared plan")}</summary><pre>{entry.text}</pre></details></>
        : <p className={styles.help}>{t("위 입력란에 test1처럼 적어도 준비된 계획으로 확인해요.", "You can also type test1 in the plan box above.")}</p>}
  </div>;
}

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
// 두 묶음: 검사 항목별(test1~16, 시각+장소 목록) · 입력 형식별(test17~, 계획 이해 시험지의 형식 이름 그대로 — 2026-10-16)
const sections = [
  ["check", "검사 항목별 · 시각+장소 목록", "By check · time + place lists"],
  ["form", "입력 형식별 · 계획 이해 시험지 분류", "By input form · plan reading test categories"],
] as const;
const categories = [
  ["normal", "문제 없는 기본안", "No intentional issues", "check"],
  ["time", "시간 겹침", "Overlapping times", "check"],
  ["hours", "운영시간·휴무", "Opening hours / closures", "check"],
  ["place", "장소 미정", "Unspecified place", "check"],
  ["mobility", "이동 여유", "Travel time", "check"],
  ["input", "입력 확인", "Input checks", "check"],
  ["general", "일반 흐름", "General flow", "check"],
  ["mixed_list", "정형 목록+자유 문장", "List with free sentences", "form"],
  ["typo_line", "말투·오타 한 줄", "Casual one-liner with typos", "form"],
  ["paragraph", "문단 자유문", "Free paragraph", "form"],
  ["csv", "CSV·TSV", "CSV / TSV", "form"],
  ["json", "JSON", "JSON", "form"],
  ["excel_memo", "메모식 엑셀", "Spreadsheet memo", "form"],
  ["pasted_table", "붙여 넣은 표", "Pasted table", "form"],
  ["multi_message", "나눠 보낸 메시지", "Split messages", "form"],
  ["mixed_request", "계획+질문+짜기", "Plan + question + planning ask", "form"],
  ["correction", "중간 정정", "Mid-message correction", "form"],
  ["real", "실제 접수", "Real-intake style", "form"],
] as const;
const fallback = categories.find(([code]) => code === "general")!;
function categoryOf(plan: PreparedPlan) { return categories.find(([code]) => code === plan.category) ?? fallback; }

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
        {sections.map(section => {
          const groups = categories.filter(category => category[3] === section[0]).map(category => {
            const plans = query.data.scenarios.filter(plan => categoryOf(plan)[0] === category[0]);
            return plans.length > 0 && <fieldset key={category[0]} className={styles.group}>
              <legend><span className={styles.badge} data-category={category[0]}>{t(category[1], category[2])}</span><span className={styles.count}>{plans.length}</span></legend>
              {plans.map(plan => <button key={plan.code} type="button" data-plan-code={plan.code} data-category={category[0]} aria-pressed={entry?.code === plan.code} onClick={() => { onChoose(plan.code, plan.text); close(); }}>
                <span className={styles.code}>{plan.code}</span><span>{plan.name}</span><Check size={16} aria-hidden="true" className={entry?.code === plan.code ? styles.checked : styles.unchecked} />
              </button>)}
            </fieldset>;
          }).filter(Boolean);
          return groups.length > 0 && <section key={section[0]} className={styles.section} data-section={section[0]} aria-label={t(section[1], section[2])}>
            <p className={styles.sectionTitle}>{t(section[1], section[2])}</p>
            {groups}
          </section>;
        })}
      </div>}
    </details>
    {query.error ? <p className={styles.help}>{t("시험 목록을 불러오지 못했어요.", "Could not load test plans.")} <button type="button" onClick={() => void query.refetch()}>{t("다시 불러오기", "Try again")}</button></p>
      : entry ? <><p className={styles.help} role="status">{entry.description} {entry.expected}</p>
        <details><summary>{t("준비된 계획 원문 보기", "View prepared plan")}</summary><pre>{entry.text}</pre></details></>
        : <p className={styles.help}>{t("위 입력란에 test1처럼 적어도 준비된 계획으로 확인해요.", "You can also type test1 in the plan box above.")}</p>}
  </div>;
}

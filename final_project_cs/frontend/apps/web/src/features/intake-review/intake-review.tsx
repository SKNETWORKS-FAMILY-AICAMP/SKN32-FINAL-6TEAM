"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, CalendarDays, RefreshCw } from "lucide-react";
import { JourneyShell } from "@/components/layout/journey-shell";
import { Button, ButtonLink, Eyebrow, PageHeading, Panel, QueryState } from "@/components/ui";
import { useOnboarding } from "@/features/onboarding/onboarding-state";
import { toSurvey } from "@/features/onboarding/payload";
import { KeyNotice } from "@/features/account/key-notice";
import { candidatesOf, readingOf, resultOf, tripIssuesOf } from "@/features/plan-check/from-intake";
import type { ItemDraft } from "@/features/plan-check/model";
import { PlanCheck } from "@/features/plan-check/plan-check";
import { tripsKey } from "@/lib/gateway";
import { LiveError } from "@/lib/live/client";
import { confirmIntake, editIntake, getIntake, planIntake, type IntakeEdit, type IntakePlanBasis, type IntakePlanInput, type IntakeView } from "@/lib/live/intake";
import { progressText, type OpProgress } from "@/lib/live/stream";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import { rows, draftOf, editsFor, statusOf } from "./model";
import { ItemCard } from "./item-card";
import { useIntakeEvents } from "./use-intake-events";
import styles from "./intake-review.module.css";

/** 한국관광공사 이용조건 — 관광정보를 화면에 올리면 출처와 저작권 정책 링크를 같이 준다(설계서 §4-6). */
const TOUR_API_POLICY_URL = "https://api.visitkorea.or.kr/#/useServiceGuide/2";
const icon = { size: 16, strokeWidth: 1.6, "aria-hidden": true } as const;

export function IntakeReview({ intakeId }: { intakeId: string }) {
  const t = useT();
  const { language } = useSettings();
  const router = useRouter();
  const [day, setDay] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [notice, setNotice] = useState("");
  const queryClient = useQueryClient();
  // The onboarding answers go to the server with the registration — only when the customer finished them.
  const [onboarding] = useOnboarding();
  const survey = onboarding.complete ? toSurvey(onboarding.answers) : undefined;
  const key = ["intake", intakeId, language] as const;
  // ★`[2026-10-02]` While the server reads, its progress stream says when to read the intake again (`useIntakeEvents`).
  //   Only where there is no stream (an older server, or the stream limit) is the intake asked for every 1.5 s, as before.
  const [polling, setPolling] = useState(false);
  const query = useQuery({
    queryKey: key,
    queryFn: () => getIntake(intakeId, language),
    retry: false,
    refetchOnWindowFocus: false,
    refetchInterval: (state) => polling && !state.state.error && state.state.data?.status === "reading" ? 1500 : false,
  });
  const reread = useCallback(() => void queryClient.invalidateQueries({ queryKey: ["intake", intakeId, language] }), [queryClient, intakeId, language]);
  const follow = useIntakeEvents(intakeId, query.data?.status === "reading", language, reread);
  if (follow.follow === "polling" && !polling) setPolling(true);
  const edit = useMutation({
    mutationFn: ({ revision, edits }: { revision: number; edits: IntakeEdit[] }) => editIntake(intakeId, revision, edits, language),
    onSuccess: (view) => {
      queryClient.setQueryData(key, view);
      setOpen(null); setDirty(false);
      setNotice(t("수정 내용을 저장하고 등록 조건을 다시 확인했어요.", "Saved your changes and checked the registration requirements."));
    },
    onError: (error) => { if (error instanceof LiveError && error.code === "stale_revision") void query.refetch(); },
  });
  // A registered trip makes the cached trip list stale; drop it so the home card and "My trips" read it again.
  const registered = (tripId: string) => { queryClient.removeQueries({ queryKey: tripsKey }); router.push(routes.trip(tripId)); };
  // What the server says it is doing with 「plan it for me」 (planning → checking → registering); null until it says.
  const [planProgress, setPlanProgress] = useState<OpProgress | null>(null);
  const plan = useMutation({
    mutationFn: ({ revision, input }: { revision: number; input: IntakePlanInput }) => { setPlanProgress(null); return planIntake(intakeId, revision, { ...input, ...(survey && { survey }) }, language, setPlanProgress); },
    onSuccess: (result) => registered(result.trip.trip_id),
    onError: (error) => { if (error instanceof LiveError && error.code === "stale_revision") void query.refetch(); },
  });
  const confirm = useMutation({
    mutationFn: (revision: number) => confirmIntake(intakeId, revision, language, survey),
    onSuccess: (result) => registered(result.trip.trip_id),
    onError: (error) => { if (error instanceof LiveError && error.code === "stale_revision") void query.refetch(); },
  });

  // ★`[2026-10-03]` The new plan-check screen (mockup `tripilot-plan-check-streaming.html`) shows the server's intake:
  //   while it reads (`readingOf` — it first draws the lines it has not drawn yet when reading ends), then the result
  //   (`resultOf` — map and list; edit, delete, trip details and register through the same server calls as this review).
  //   This review stays for planning a trip the server could not read stops from, and behind 「이전 확인 화면 열기」.
  //   An intake opened after reading goes straight to the result.
  const reading = useMemo(() => query.data ? readingOf(query.data) : null, [query.data]);
  const result = useMemo(() => query.data && query.data.status !== "reading" && query.data.status !== "fatal" ? resultOf(query.data) : null, [query.data]);
  const [readingSeen, setReadingSeen] = useState(false);
  const [readingDrawn, setReadingDrawn] = useState(false);
  const [editing, setEditing] = useState(false);
  if (query.data?.status === "reading" && !readingSeen) setReadingSeen(true);
  const readingCaughtUp = useCallback(() => setReadingDrawn(true), []);
  const shell = (children: ReactNode) => <JourneyShell view="checking" title={["계획 확인", "Check your plan"]}>{children}</JourneyShell>;

  if (query.isPending || !query.data) return shell(<QueryState loading={query.isPending} error={query.error} retry={() => void query.refetch()} />);
  const view = query.data;

  if (view.status === "reading" && follow.follow === "stalled") {
    return shell(<Panel className={styles.waiting}>
      <Eyebrow>{t("읽기가 멈췄어요", "READING STOPPED")}</Eyebrow>
      <h1>{t("서버가 이 계획을 끝까지 읽지 못했어요", "The server stopped reading this plan")}</h1>
      <p role="alert">{t("읽던 서버가 다시 시작됐을 수 있어요. 계획을 다시 올려 주세요.", "The server may have restarted while reading. Please upload the plan again.")}</p>
      <ButtonLink href={routes.newTrip} variant="primary">{t("다시 올리기", "Upload again")}</ButtonLink>
    </Panel>);
  }
  if (reading && (view.status === "reading" || (view.status === "review" && readingSeen && !readingDrawn))) {
    const streamNote = view.status !== "reading" ? null
      : follow.follow === "lost" ? <p className={styles.streamNote} role="status" data-lost>{t("서버와 연결이 끊겼어요 — 다시 연결하는 중이에요…", "Lost the connection to the server — reconnecting…")}</p>
      : follow.slow ? <p className={styles.streamNote} role="status">{t("읽는 데 시간이 걸리고 있어요. 서버는 계속 읽고 있어요.", "Reading is taking a while. The server is still at it.")}</p>
      : null;
    return <PlanCheck key="reading" view={reading} notice={<><KeyNotice />{streamNote}</>} onBack={() => router.push(routes.newTrip)} onCaughtUp={view.status === "review" ? readingCaughtUp : undefined} />;
  }
  if (view.status === "fatal") {
    return shell(<Panel className={styles.waiting}>
      <Eyebrow>{t("읽지 못했어요", "COULD NOT READ")}</Eyebrow>
      <h1>{t("이 계획을 읽지 못했어요", "We could not read this plan")}</h1>
      <p role="alert">{view.fatal?.detail ?? view.fatal?.code}</p>
      <ButtonLink href={routes.newTrip} variant="primary">{t("다시 올리기", "Try again")}</ButtonLink>
    </Panel>);
  }
  if (result && !editing && result.items.length > 0 && !view.check?.plan.requested) {
    // Every change goes through this review's edit call, so the server checks the plan again and answers with the new one.
    const send = async (edits: IntakeEdit[]) => { if (edits.length) await edit.mutateAsync({ revision: view.revision, edits }); };
    const rowOf = (id: string) => rows(view).find((row) => row.key === id);
    const refusal = confirm.error instanceof LiveError ? (confirm.error.detail as { problems?: { field: string; message?: string; reason?: string }[] } | undefined) : undefined;
    return <PlanCheck key="result" view={result} notice={<KeyNotice />} onBack={() => router.push(routes.newTrip)}
      tripIssues={tripIssuesOf(view)} onOpenPrevious={() => setEditing(true)}
      actions={{
        edit: async (id: string, draft: ItemDraft) => { const row = rowOf(id); if (row) await send(editsFor(row, draft)); },
        remove: async (id: string) => { const row = rowOf(id); if (row) await send([{ source_id: row.source.source_id, field: `items[${row.item.index}].removed`, value: true }]); },
        // A place by name: the server looks it up again and checks the plan (an alternative it weighed, or a typed name).
        replace: async (id, choice) => {
          const row = rowOf(id);
          if (row) await send([{ source_id: row.source.source_id, field: `items[${row.item.index}].place`, value: { name: "candidate" in choice ? choice.candidate.name : choice.name } }]);
        },
        candidates: async (id) => candidatesOf(view, id),
        editTrip: (field, value) => send([{ field: `trip.${field}`, value }]),
      }}
      registration={{
        ready: Boolean(view.check?.ready), busy: confirm.isPending, onRegister: () => confirm.mutate(view.revision),
        error: confirm.error?.message ?? null, problems: refusal?.problems?.map((problem) => problem.message ?? `${problem.field}: ${problem.reason}`) ?? [],
        registeredHref: view.status === "confirmed" && view.trip_id ? routes.trip(view.trip_id) : null,
      }} />;
  }

  const list = rows(view);
  const problems = view.check?.problems ?? [];
  const tripProblems = problems.filter((problem) => !list.some((row) => row.problems.includes(problem)));
  const dates = [...new Set(list.map((row) => draftOf(row).date))].sort((a, b) => (a || "9999").localeCompare(b || "9999"));
  const selectedDay = day !== null && dates.includes(day) ? day : dates[0];
  const visible = list.filter((row) => draftOf(row).date === selectedDay);
  const count = (status: "ready" | "edited" | "review") => list.filter((row) => statusOf(row) === status).length;
  const closeEditor = () => { setOpen(null); setDirty(false); edit.reset(); };
  const changeSelection = (action: () => void) => {
    if (dirty) { setNotice(t("고치는 일정의 저장 또는 취소를 먼저 눌러 주세요.", "Save or cancel your current edit first.")); return; }
    action(); setNotice("");
  };
  const needsFirstDay = problems.some((problem) => problem.code === "no_date");
  const needsParty = problems.some((problem) => problem.code === "party_size_out_of_range");
  const yearFilled = view.sources.flatMap((source) => source.items).map((item) => item.fields.date)
    .find((field) => field?.method !== "customer" && field?.evidence.how === "year_filled");
  const busy = edit.isPending || confirm.isPending || plan.isPending;
  const send = (edits: IntakeEdit[]) => edit.mutate({ revision: view.revision, edits });
  const confirmed = view.status === "confirmed";
  const error = (open ? null : edit.error) ?? confirm.error ?? plan.error;
  const refusal = error instanceof LiveError ? (error.detail as { problems?: { field: string; message?: string; reason?: string }[]; violations?: { reason: string }[] } | undefined) : undefined;

  return shell(<div className={styles.review}>
    <PageHeading eyebrow="LET’S CHECK IT TOGETHER" title={view.check?.title ?? t("읽은 계획", "Your plan")}
      description={t("읽은 그대로 보여 드려요. 고칠 곳만 고치고 등록하면, 여행이 끝날 때까지 지켜볼게요.", "Here is what we read. Fix only what needs fixing, then we’ll watch over your trip until it ends.")} />
    {query.error && <div className={styles.error} role="alert">
      <p>{t("최신 결과를 불러오지 못했어요. 마지막으로 읽은 내용과 고치던 입력을 보관하고 있어요.", "Could not refresh the plan. Your last loaded plan and unsaved edits are kept here.")}</p>
      <p>{query.error.message}</p><Button disabled={query.isFetching} onClick={() => void query.refetch()}>{t("다시 불러오기", "Try again")}</Button>
    </div>}
    {list.length > 0 && <section className={styles.stats} aria-label={t("일정 확인 요약", "Review summary")}>
      <div><strong>{count("edited")}<small>{t("개", "")}</small></strong><p>{t("수정한 일정", "Edited stops")}</p></div>
      <div><strong>{count("ready")}<small>{t("개", "")}</small></strong><p>{t("입력 확인", "Read back")}</p></div>
      <div><strong>{count("review")}<small>{t("개", "")}</small></strong><p>{t("확인이 필요한 일정", "Needs review")}</p></div>
    </section>}
    {list.length > 0 && <p className={styles.summaryNote}>{t("읽은 입력과 수정 상태를 보여 드려요. 최종 등록 가능 여부는 등록할 때 다시 확인해요.", "These counts describe the input and edits. Final eligibility is checked when registering.")}</p>}
    {notice && <p className={styles.notice} role="status">{notice}</p>}
    {(tripProblems.length > 0 || needsFirstDay || needsParty) && <Panel className={styles.problems} aria-labelledby="intake-problems">
      <h2 id="intake-problems">{tripProblems.length > 0 ? t(`여행 전체에서 확인할 것 ${tripProblems.length}개`, `${tripProblems.length} trip details to check`) : t("여행 기본정보 확인", "Check your trip details")}</h2>
      <ul>{tripProblems.map((problem) => <li key={`${problem.source_id}:${problem.field}:${problem.code}`}>{problem.message}</li>)}</ul>
      {needsFirstDay && <FirstDay disabled={busy || dirty} onSave={(value) => send([{ field: "trip.first_day", value }])} />}
      {needsParty && <Party disabled={busy || dirty} onSave={(value) => send([{ field: "trip.party_size", value }])} />}
    </Panel>}
    {yearFilled && <p className={styles.notice} role="note">{t(`해가 적혀 있지 않아 ${String(yearFilled.value).slice(0, 4)}년으로 두었어요. 다르면 항목의 날짜를 고쳐 주세요.`, `No year was written, so we assumed ${String(yearFilled.value).slice(0, 4)}. Fix a stop’s date if that is wrong.`)}</p>}
    {view.check && !confirmed && (view.check.plan.requested || list.length === 0) &&
      <PlanPanel basis={view.check.plan} readItems={list.length} disabled={busy || dirty} pending={plan.isPending} progress={planProgress}
        onPlan={(input) => plan.mutate({ revision: view.revision, input })} />}
    {list.length > 0 && <section className={styles.planList} aria-labelledby="plan-title">
      <div className={styles.planHead}><h2 id="plan-title">{t("여행 계획 살펴보기", "Review your itinerary")}</h2><span>{t(`${list.length}개 일정`, `${list.length} stops`)}</span></div>
      <div className={styles.days} role="group" aria-label={t("일차", "Travel days")}>
        {dates.map((date, index) => <button key={date} type="button" aria-pressed={selectedDay === date} disabled={busy}
          onClick={() => changeSelection(() => { setDay(date); closeEditor(); })}>{date ? <>{t(`${index + 1}일차`, `Day ${index + 1}`)}<small>{date.slice(5).replace("-", ".")}</small></> : t("날짜 확인 필요", "Date needed")}</button>)}
      </div>
      <div className={styles.list}>{visible.map((row) => <ItemCard key={row.key} row={row} all={list} open={open === row.key}
        revision={view.revision} disabled={busy || confirmed} onDirty={setDirty} onCancel={closeEditor}
        onToggle={() => changeSelection(() => setOpen(open === row.key ? null : row.key))}
        onEdit={async (edits, revision) => { await edit.mutateAsync({ revision, edits }); }} />)}</div>
    </section>}
    {list.length === 0 && !view.check?.plan.requested && <Panel><p>{t("읽은 일정이 없어요. 원문을 보고 다시 올리거나, 위에서 일정을 짜 달라고 해 주세요.", "No stops were read. Check the original and upload again, or ask us above to plan it.")}</p></Panel>}
    <Evidence view={view} />
    {error && <ErrorNotice error={error}>
      <p>{error.message}</p>
      {refusal?.problems && <ul>{refusal.problems.map((problem, index) => <li key={`${problem.field}-${index}`}>{problem.message ?? `${problem.field}: ${problem.reason}`}</li>)}</ul>}
      {refusal?.violations && <ul>{refusal.violations.map((violation) => <li key={violation.reason}>{violation.reason}</li>)}</ul>}
    </ErrorNotice>}
    <p className={styles.credit}>{t("장소 정보 출처 : ⓒ한국관광공사 · ", "Place data: ⓒKorea Tourism Organization · ")}<a href={TOUR_API_POLICY_URL} target="_blank" rel="noreferrer">{t("저작권 정책", "Copyright policy")}</a></p>
    <div className={styles.refresh}><Button variant="quiet" disabled={busy || dirty || query.isFetching} onClick={() => { setNotice(""); void query.refetch(); }}><RefreshCw {...icon} />{query.isFetching ? t("확인하는 중…", "Refreshing…") : t("확인 결과 새로고침", "Refresh check")}</Button></div>
    <div className={styles.actions}>
      <ButtonLink href={routes.newTrip}><ArrowLeft {...icon} />{t("다시 올리기", "Upload again")}</ButtonLink>
      <span className={styles.actionNote}>{confirmed ? t("이미 등록했어요.", "Already registered.") : view.check?.ready ? t("등록하면 바로 지켜보기 시작해요.", "We start watching as soon as you register.") : list.length === 0 ? t("위에서 조건을 고르고 「짜서 등록」을 눌러 주세요.", "Choose the conditions above and press “Plan and register”.") : t("위의 확인할 것을 먼저 채워 주세요.", "Fill in the items above first.")}</span>
      {confirmed && view.trip_id
        ? <ButtonLink href={routes.trip(view.trip_id)} variant="primary">{t("여행 보기", "Open trip")}<ArrowRight {...icon} /></ButtonLink>
        : <Button variant="primary" disabled={busy || dirty || Boolean(query.error) || !view.check?.ready} onClick={() => confirm.mutate(view.revision)}>{confirm.isPending ? t("등록하는 중…", "Registering…") : t("여행 등록", "Register trip")}<ArrowRight {...icon} /></Button>}
    </div>
  </div>);
}

/**
 * The failure of the last action. ★It sits under the item list while the buttons stay in the bar at the bottom, so a
 * long plan hid it — pressing 「등록하고 관리 시작」 then looked like nothing happened (found 2026-09-28 on the real
 * server). Each new failure is brought into view.
 */
function ErrorNotice({ error, children }: { error: Error; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => { box.current?.scrollIntoView({ block: "center", behavior: "smooth" }); }, [error]);
  return <div ref={box} className={styles.error} role="alert">{children}</div>;
}

function FirstDay({ disabled, onSave }: { disabled: boolean; onSave: (value: string) => void }) {
  const t = useT();
  const [value, setValue] = useState("");
  return <form className={styles.inline} onSubmit={(event) => { event.preventDefault(); if (value) onSave(value); }}>
    <label htmlFor="intake-first-day"><CalendarDays {...icon} />{t("여행 첫날", "First day")}</label>
    <input id="intake-first-day" type="date" value={value} onChange={(event) => setValue(event.target.value)} disabled={disabled} required />
    <Button type="submit" disabled={disabled || !value}>{t("저장", "Save")}</Button>
  </form>;
}

/** 「일정 짜 줘」 — 조건을 확인하고 누르면 일정 생성기가 짠 초안을 판정 뒤 등록한다. 누르는 것이 곧 등록이다. */
function PlanPanel({ basis, readItems, disabled, pending, progress, onPlan }: { basis: IntakePlanBasis; readItems: number; disabled: boolean; pending: boolean; progress: OpProgress | null; onPlan: (input: IntakePlanInput) => void }) {
  const t = useT();
  const [start, setStart] = useState(basis.start_date ?? "");
  const [days, setDays] = useState(basis.days ?? 0);
  const [party, setParty] = useState(basis.party_size ?? 0);
  const [keep, setKeep] = useState(readItems > 0);
  const ready = Boolean(start) && days >= 1 && party >= 1;
  return <Panel className={styles.plan} aria-labelledby="intake-plan">
    <h2 id="intake-plan">{basis.requested ? t("일정을 짜 달라고 하셨어요", "You asked us to plan the trip") : t("읽은 일정이 없어요 — 대신 짜 드릴까요?", "No stops were read — shall we plan one?")}</h2>
    <p>{t("서울 안에서, 올려 주신 글을 선호로 읽어 하루하루를 짜요. 짠 일정은 판정을 통과해야 등록돼요.", "We plan each day in Seoul, reading your text as preferences. The plan is registered only if it passes our checks.")}
      {readItems > 0 && !keep && <strong> {t(`새로 짜면 위에 읽은 일정 ${readItems}개는 쓰지 않아요.`, `A new plan does not use the ${readItems} stops read above.`)}</strong>}</p>
    {readItems > 0 && <label className={styles.keep}><input type="checkbox" checked={keep} onChange={(event) => setKeep(event.target.checked)} disabled={disabled} />
      {t(`읽은 일정 ${readItems}개는 그대로 두고 빈 시간만 채우기`, `Keep the ${readItems} stops read above and fill only the gaps`)}</label>}
    <form className={styles.inline} onSubmit={(event) => { event.preventDefault(); if (ready) onPlan({ start_date: start, days, party_size: party, keep_read_items: keep }); }}>
      <label htmlFor="plan-start">{t("첫날", "First day")}</label>
      <input id="plan-start" type="date" value={start} onChange={(event) => setStart(event.target.value)} disabled={disabled} required />
      <label htmlFor="plan-days">{t("일수", "Days")}</label>
      <select id="plan-days" value={days} onChange={(event) => setDays(Number(event.target.value))} disabled={disabled}>
        <option value={0}>{t("고르기", "Choose")}</option>{[1, 2, 3, 4, 5, 6, 7].map((n) => <option key={n} value={n}>{t(`${n}일`, `${n}`)}</option>)}
      </select>
      <label htmlFor="plan-party">{t("인원", "Travelers")}</label>
      <select id="plan-party" value={party} onChange={(event) => setParty(Number(event.target.value))} disabled={disabled}>
        <option value={0}>{t("고르기", "Choose")}</option>{[1, 2, 3, 4].map((n) => <option key={n} value={n}>{t(`${n}명`, `${n}`)}</option>)}
      </select>
      <Button type="submit" variant="primary" disabled={disabled || !ready}>{pending ? t("짜는 중… (1분쯤)", "Planning… (about a minute)") : t("이 조건으로 짜서 등록", "Plan and register")}</Button>
    </form>
    {pending && <p className={styles.streamNote} role="status" data-lost={progress?.lost || undefined}>{progressText(progress, t, ["일정을 짜 달라고 보냈어요…", "Sent your planning request…"])}</p>}
  </Panel>;
}

function Party({ disabled, onSave }: { disabled: boolean; onSave: (value: number) => void }) {
  const t = useT();
  const [value, setValue] = useState(2);
  return <form className={styles.inline} onSubmit={(event) => { event.preventDefault(); onSave(value); }}>
    <label htmlFor="intake-party">{t("인원", "Travelers")}</label>
    <select id="intake-party" value={value} onChange={(event) => setValue(Number(event.target.value))} disabled={disabled}>
      {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{t(`${n}명`, `${n}`)}</option>)}
    </select>
    <Button type="submit" disabled={disabled}>{t("저장", "Save")}</Button>
  </form>;
}

function Evidence({ view }: { view: IntakeView }) {
  const t = useT();
  return <details className={styles.evidence}>
    <summary>{t("읽은 원문 전체 보기", "Show the full original")}</summary>
    {view.sources.map((source) => <div key={source.source_id}>
      <p className={styles.note}>{source.filename ?? t("입력한 글", "Your text")}{source.transcribed ? t(" · 사진에서 받아 적은 글", " · transcribed from a photo") : ""}
        {source.reading?.rejected?.length ? t(` · 원문에 없는 인용 ${source.reading.rejected.length}개는 버렸어요`, ` · ${source.reading.rejected.length} quotes not in the original were dropped`) : ""}
        {source.reading?.error ? t(" · 남은 줄 읽기 모델이 응답하지 않았어요", " · the model for unread lines did not respond") : ""}</p>
      <ol className={styles.lines}>{source.lines.map((line) => <li key={line.no} data-read={line.read}><span>{line.no}</span>{line.text}</li>)}</ol>
    </div>)}
  </details>;
}


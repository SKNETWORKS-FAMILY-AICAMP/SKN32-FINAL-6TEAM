"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, CalendarDays, MapPin, Trash2 } from "lucide-react";
import { Badge, Button, ButtonLink, Eyebrow, PageHeading, Panel, QueryState } from "@/components/ui";
import { useOnboarding } from "@/features/onboarding/onboarding-state";
import { toSurvey } from "@/features/onboarding/payload";
import type { Translate } from "@/lib/i18n";
import { tripsKey } from "@/lib/gateway";
import { LiveError } from "@/lib/live/client";
import { confirmIntake, editIntake, getIntake, planIntake, type IntakeEdit, type IntakeItem, type IntakePlanBasis, type IntakePlanInput, type IntakeProblem, type IntakeSource, type IntakeView } from "@/lib/live/intake";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import styles from "./intake-review.module.css";

/** 한국관광공사 이용조건 — 관광정보를 화면에 올리면 출처와 저작권 정책 링크를 같이 준다(설계서 §4-6). */
const TOUR_API_POLICY_URL = "https://api.visitkorea.or.kr/#/useServiceGuide/2";
const icon = { size: 16, strokeWidth: 1.6, "aria-hidden": true } as const;

interface Row {
  source: IntakeSource;
  item: IntakeItem;
  key: string;
  problems: IntakeProblem[];
  filledStart?: string;
  filledEnd?: string;
}

function rows(view: IntakeView): Row[] {
  const problems = view.check?.problems ?? [];
  const filled = view.check?.filled ?? [];
  const out: Row[] = [];
  for (const source of view.sources) {
    for (const item of source.items) {
      if (item.fields.removed?.value === true) continue;
      const where = `items[${item.index}]`;
      const mine = (field: string) => filled.find((entry) => entry.source_id === source.source_id && entry.field === `${where}.${field}`)?.value;
      out.push({
        source, item, key: `${source.source_id}:${item.index}`,
        problems: problems.filter((problem) => problem.source_id === source.source_id && problem.field.startsWith(`${where}.`)),
        filledStart: mine("starts_at"), filledEnd: mine("ends_at"),
      });
    }
  }
  const dateOf = (row: Row) => String(row.item.fields.date?.value ?? row.item.date ?? "9999");
  const timeOf = (row: Row) => String(row.item.fields.starts_at?.value ?? row.filledStart ?? "99:99");
  return out.sort((a, b) => (b.problems.length ? 1 : 0) - (a.problems.length ? 1 : 0) || dateOf(a).localeCompare(dateOf(b)) || timeOf(a).localeCompare(timeOf(b)));
}

function badges(row: Row, t: Translate, yearNote: boolean) {
  const out: { label: string; warn?: boolean }[] = [];
  const title = row.item.fields.title;
  if (title?.method === "rule" || title?.method === "llm_span") out.push({ label: t("원문 그대로", "As written") });
  if (row.filledStart) out.push({ label: t("규칙으로 배치", "Placed by rule") });
  const place = row.item.fields.place;
  if (place?.method === "lookup" && place.value) out.push({ label: t("조회로 확인", "Checked by lookup") });
  if (place?.method === "customer") out.push({ label: t("직접 고침", "Fixed by you") });
  // ★해를 채운 날짜(「10월 15일」 → 올해·내년)는 항목마다 달지 않고 화면 위에서 한 번 알린다 — 전부에 붙으면
  //   정작 확인할 곳이 묻힌다(2026-09-27 실제 화면)
  const review = Object.entries(row.item.fields).some(([name, field]) => field?.needs_review && field.method !== "customer"
    && !(name === "date" && yearNote && ["year_filled", "day_offset"].includes(String(field.evidence.how))));
  if (row.problems.length || review) out.push({ label: t("확인 필요", "Needs review"), warn: true });
  return out;
}

export function IntakeReview({ intakeId }: { intakeId: string }) {
  const t = useT();
  const { language } = useSettings();
  const router = useRouter();
  const queryClient = useQueryClient();
  // The onboarding answers go to the server with the registration — only when the customer finished them.
  const [onboarding] = useOnboarding();
  const survey = onboarding.complete ? toSurvey(onboarding.answers) : undefined;
  const key = ["intake", intakeId, language] as const;
  const query = useQuery({
    queryKey: key,
    queryFn: () => getIntake(intakeId, language),
    retry: false,
    refetchOnWindowFocus: false,
    refetchInterval: (state) => !state.state.error && state.state.data?.status === "reading" ? 1500 : false,
  });
  const edit = useMutation({
    mutationFn: ({ revision, edits }: { revision: number; edits: IntakeEdit[] }) => editIntake(intakeId, revision, edits, language),
    onSuccess: (view) => queryClient.setQueryData(key, view),
    onError: (error) => { if (error instanceof LiveError && error.code === "stale_revision") void query.refetch(); },
  });
  // A registered trip makes the cached trip list stale; drop it so the home card and "My trips" read it again.
  const registered = (tripId: string) => { queryClient.removeQueries({ queryKey: tripsKey }); router.push(routes.trip(tripId)); };
  const plan = useMutation({
    mutationFn: ({ revision, input }: { revision: number; input: IntakePlanInput }) => planIntake(intakeId, revision, { ...input, ...(survey && { survey }) }, language),
    onSuccess: (result) => registered(result.trip.trip_id),
    onError: (error) => { if (error instanceof LiveError && error.code === "stale_revision") void query.refetch(); },
  });
  const confirm = useMutation({
    mutationFn: (revision: number) => confirmIntake(intakeId, revision, language, survey),
    onSuccess: (result) => registered(result.trip.trip_id),
    onError: (error) => { if (error instanceof LiveError && error.code === "stale_revision") void query.refetch(); },
  });

  if (query.isPending || query.error || !query.data) return <QueryState loading={query.isPending} error={query.error} retry={() => void query.refetch()} />;
  const view = query.data;

  if (view.status === "reading") {
    return <Panel className={styles.waiting} role="status">
      <Eyebrow>{t("계획을 읽고 있어요", "READING YOUR PLAN")}</Eyebrow>
      <h1>{view.stage_label}</h1>
      <p>{t("사진은 한 장에 1분쯤 걸려요. 이 화면을 열어 두면 끝나는 대로 보여 드려요.", "A photo takes about a minute. Keep this page open and the result will appear.")}</p>
    </Panel>;
  }
  if (view.status === "fatal") {
    return <Panel className={styles.waiting}>
      <Eyebrow>{t("읽지 못했어요", "COULD NOT READ")}</Eyebrow>
      <h1>{t("이 계획을 읽지 못했어요", "We could not read this plan")}</h1>
      <p role="alert">{view.fatal?.detail ?? view.fatal?.code}</p>
      <ButtonLink href={routes.newTrip} variant="primary">{t("다시 올리기", "Try again")}</ButtonLink>
    </Panel>;
  }

  const list = rows(view);
  const problems = view.check?.problems ?? [];
  const needsFirstDay = problems.some((problem) => problem.code === "no_date");
  const needsParty = problems.some((problem) => problem.code === "party_size_out_of_range");
  const yearFilled = view.sources.flatMap((source) => source.items).map((item) => item.fields.date)
    .find((field) => field?.method !== "customer" && field?.evidence.how === "year_filled");
  const busy = edit.isPending || confirm.isPending || plan.isPending;
  const send = (edits: IntakeEdit[]) => edit.mutateAsync({ revision: view.revision, edits }).then(() => true, () => false);
  const confirmed = view.status === "confirmed";
  const error = edit.error ?? confirm.error ?? plan.error;
  const refusal = error instanceof LiveError ? (error.detail as { problems?: { field: string; message?: string; reason?: string }[]; violations?: { reason: string }[] } | undefined) : undefined;

  return <>
    <PageHeading eyebrow="LET’S CHECK IT TOGETHER" title={view.check?.title ?? t("읽은 계획", "Your plan")}
      description={t("읽은 그대로 보여 드려요. 고칠 곳만 고치고 등록하면, 여행이 끝날 때까지 지켜볼게요.", "Here is what we read. Fix only what needs fixing, then we’ll watch over your trip until it ends.")} />
    {problems.length > 0 && <Panel className={styles.problems} aria-labelledby="intake-problems">
      <h2 id="intake-problems">{t(`등록 전에 확인할 것 ${problems.length}개`, `${problems.length} things to check before registering`)}</h2>
      <ul>{problems.map((problem) => <li key={`${problem.source_id}:${problem.field}:${problem.code}`}>{problem.message}</li>)}</ul>
      {needsFirstDay && <FirstDay disabled={busy} onSave={(value) => send([{ field: "trip.first_day", value }])} />}
      {needsParty && <Party disabled={busy} onSave={(value) => send([{ field: "trip.party_size", value }])} />}
    </Panel>}
    {yearFilled && <p className={styles.notice} role="note">{t(`해가 적혀 있지 않아 ${String(yearFilled.value).slice(0, 4)}년으로 두었어요. 다르면 항목의 날짜를 고쳐 주세요.`, `No year was written, so we assumed ${String(yearFilled.value).slice(0, 4)}. Fix a stop’s date if that is wrong.`)}</p>}
    {view.check && !confirmed && (view.check.plan.requested || list.length === 0) &&
      <PlanPanel basis={view.check.plan} readItems={list.length} disabled={busy} pending={plan.isPending}
        onPlan={(input) => plan.mutate({ revision: view.revision, input })} />}
    <div className={styles.list}>{list.map((row) => <ItemCard key={row.key} row={row} yearNote={Boolean(yearFilled)} disabled={busy || confirmed} onEdit={send} />)}</div>
    {list.length === 0 && !view.check?.plan.requested && <Panel><p>{t("읽은 일정이 없어요. 원문을 보고 다시 올리거나, 위에서 일정을 짜 달라고 해 주세요.", "No stops were read. Check the original and upload again, or ask us above to plan it.")}</p></Panel>}
    <Evidence view={view} />
    {error && <ErrorNotice error={error}>
      <p>{error.message}</p>
      {refusal?.problems && <ul>{refusal.problems.map((problem, index) => <li key={`${problem.field}-${index}`}>{problem.message ?? `${problem.field}: ${problem.reason}`}</li>)}</ul>}
      {refusal?.violations && <ul>{refusal.violations.map((violation) => <li key={violation.reason}>{violation.reason}</li>)}</ul>}
    </ErrorNotice>}
    <p className={styles.credit}>{t("장소 정보 출처 : ⓒ한국관광공사 · ", "Place data: ⓒKorea Tourism Organization · ")}<a href={TOUR_API_POLICY_URL} target="_blank" rel="noreferrer">{t("저작권 정책", "Copyright policy")}</a></p>
    <div className={styles.actions}>
      <ButtonLink href={routes.newTrip}><ArrowLeft {...icon} />{t("다시 올리기", "Upload again")}</ButtonLink>
      <span className={styles.actionNote}>{confirmed ? t("이미 등록했어요.", "Already registered.") : view.check?.ready ? t("등록하면 바로 지켜보기 시작해요.", "We start watching as soon as you register.") : list.length === 0 ? t("위에서 조건을 고르고 「짜서 등록」을 눌러 주세요.", "Choose the conditions above and press “Plan and register”.") : t("위의 확인할 것을 먼저 채워 주세요.", "Fill in the items above first.")}</span>
      {confirmed && view.trip_id
        ? <ButtonLink href={routes.trip(view.trip_id)} variant="primary">{t("여행 보기", "Open trip")}<ArrowRight {...icon} /></ButtonLink>
        : <Button variant="primary" disabled={busy || !view.check?.ready} onClick={() => confirm.mutate(view.revision)}>{confirm.isPending ? t("등록하는 중…", "Registering…") : t("등록하고 관리 시작", "Register and start")}<ArrowRight {...icon} /></Button>}
    </div>
  </>;
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
function PlanPanel({ basis, readItems, disabled, pending, onPlan }: { basis: IntakePlanBasis; readItems: number; disabled: boolean; pending: boolean; onPlan: (input: IntakePlanInput) => void }) {
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

function ItemCard({ row, yearNote, disabled, onEdit }: { row: Row; yearNote: boolean; disabled: boolean; onEdit: (edits: IntakeEdit[]) => Promise<boolean> }) {
  const t = useT();
  const { item, source } = row;
  const where = `items[${item.index}]`;
  const field = (name: string) => `${where}.${name}`;
  const title = String(item.fields.title?.value ?? "");
  const start = String(item.fields.starts_at?.value ?? row.filledStart ?? "");
  const end = String(item.fields.ends_at?.value ?? row.filledEnd ?? "");
  const date = String(item.fields.date?.value ?? item.date ?? "");
  const place = item.fields.place;
  const placeName = place?.value && typeof place.value === "object" ? String((place.value as { name?: string }).name ?? "") : "";
  const [placeDraft, setPlaceDraft] = useState("");
  // 편집한 칸만 초안으로 보관해, 나머지 칸은 최신 서버 값을 따라가게 한다.
  const [timeDraft, setTimeDraft] = useState<Partial<{ start: string; end: string; date: string }>>({});
  const times = { start, end, date, ...timeDraft };
  const booking = item.fields.booking_no?.value;
  const line = item.line ? source.lines[item.line - 1]?.text : undefined;
  const t2 = (edits: IntakeEdit[]) => onEdit(edits.map((edit) => ({ source_id: source.source_id, ...edit })));

  async function saveTimes(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const edits: IntakeEdit[] = [];
    if (times.start && times.start !== start) edits.push({ field: field("starts_at"), value: times.start });
    if (times.end && times.end !== end) edits.push({ field: field("ends_at"), value: times.end });
    if (times.date && times.date !== date) edits.push({ field: field("date"), value: times.date });
    if (edits.length && await t2(edits)) setTimeDraft({});
  }

  return <Panel className={styles.item} data-problem={row.problems.length > 0}>
    <header className={styles.itemHead}>
      <div>
        <p className={styles.when}>{date || t("날짜 모름", "Date unknown")} · {start || "--:--"}{end ? ` – ${end}` : ""}</p>
        <h2>{title || t("(이름 없음)", "(no name)")}</h2>
      </div>
      <div className={styles.badges}>{badges(row, t, yearNote).map((badge) => <Badge key={badge.label} tone={badge.warn ? "warning" : "success"}>{badge.label}</Badge>)}</div>
    </header>
    {row.problems.map((problem) => <p key={problem.code} className={styles.problem}>{problem.message}</p>)}
    <dl className={styles.facts}>
      <dt><MapPin {...icon} />{t("장소", "Place")}</dt>
      <dd>{placeName || (place?.method === "customer" ? t("장소 없음", "No place") : t("정하지 못했어요", "Not decided"))}
        {place?.note && <span className={styles.note}>{place.note}</span>}</dd>
      {booking != null && <><dt>{t("예약번호", "Booking")}</dt><dd>{String(booking)} <span className={styles.note}>{t("바꾸기 전에 꼭 물어볼게요", "We will always ask before changing it")}</span></dd></>}
      {line && <><dt>{t("원문", "Original")}</dt><dd className={styles.quote}>{item.line}: {line}</dd></>}
    </dl>
    <div className={styles.editRow}>
      <form className={styles.inline} onSubmit={(event) => { event.preventDefault(); if (placeDraft.trim()) { t2([{ field: field("place"), value: { name: placeDraft.trim() } }]); setPlaceDraft(""); } }}>
        <label className="sr-only" htmlFor={`place-${row.key}`}>{t("다른 장소로 고치기", "Change place")}</label>
        <input id={`place-${row.key}`} value={placeDraft} onChange={(event) => setPlaceDraft(event.target.value)} placeholder={t("다른 장소로 고치기", "Change place")} disabled={disabled} maxLength={80} />
        <Button type="submit" disabled={disabled || !placeDraft.trim()}>{t("찾기", "Find")}</Button>
        <Button variant="quiet" disabled={disabled} onClick={() => t2([{ field: field("place"), value: { none: true } }])}>{t("장소 없음", "No place")}</Button>
      </form>
      <form className={styles.inline} onSubmit={saveTimes}>
        <label className="sr-only" htmlFor={`date-${row.key}`}>{t("날짜", "Date")}</label>
        <input id={`date-${row.key}`} type="date" value={times.date} onChange={(event) => setTimeDraft({ ...timeDraft, date: event.target.value })} disabled={disabled} />
        <label className="sr-only" htmlFor={`start-${row.key}`}>{t("시작", "Start")}</label>
        <input id={`start-${row.key}`} type="time" value={times.start} onChange={(event) => setTimeDraft({ ...timeDraft, start: event.target.value })} disabled={disabled} />
        <label className="sr-only" htmlFor={`end-${row.key}`}>{t("끝", "End")}</label>
        <input id={`end-${row.key}`} type="time" value={times.end} onChange={(event) => setTimeDraft({ ...timeDraft, end: event.target.value })} disabled={disabled} />
        <Button type="submit" disabled={disabled}>{t("날짜·시각 저장", "Save date & time")}</Button>
      </form>
      <Button variant="quiet" disabled={disabled} onClick={() => t2([{ field: field("removed"), value: true }])}><Trash2 {...icon} />{t("빼기", "Remove")}</Button>
    </div>
  </Panel>;
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

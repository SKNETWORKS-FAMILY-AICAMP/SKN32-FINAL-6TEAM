"use client";

import { silenceSnapshot, type SilenceSnapshot } from "./silence-snapshot";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { JourneyShell } from "@/components/layout/journey-shell";
import { ButtonLink, Eyebrow, Panel, QueryState } from "@/components/ui";
import { useOnboarding } from "@/features/onboarding/onboarding-state";
import { toSurvey } from "@/features/onboarding/payload";
import { useCriteria, withCriteria } from "@/features/guardian/criteria-store";
import { questionsOf, startAnswers } from "@/features/survey-questions/model";
import { preloadAnswers } from "@/features/survey-questions/preload";
import { IdleWarning, ReadingFooter } from "@/features/survey-questions/reading-footer";
import { ReadingQuestions } from "@/features/survey-questions/reading-questions";
import { useQuestionFlow } from "@/features/survey-questions/use-question-flow";
import { assumedYear, candidatesOf, readingOf, resultOf, sendingOf, tripIssuesOf } from "@/features/plan-check/from-intake";
import { reviewResultOf, streamingViewOf } from "@/features/plan-check/from-review";
import { useServerReview } from "@/features/plan-check/use-server-review";
import type { ItemDraft } from "@/features/plan-check/model";
import { PlanCheck } from "@/features/plan-check/plan-check";
import { clearRegistrationDraft } from "@/features/trip-registration/trip-registration";
import { tripGateway, tripKey, tripsKey } from "@/lib/gateway";
import { LiveError, loginRequired } from "@/lib/live/client";
import { emptyStream, reduceStream, toIntakeEvent, type StreamState } from "@/lib/live/intake-events";
import { confirmIntake, editIntake, getIntake, type IntakeEdit } from "@/lib/live/intake";
import { clearIntakeArrival, entryReturnOf, forgetIntakeSubmission, intakeArrival, rememberEmptyIntake } from "@/lib/live/intake-start";
import type { ReviewedIntakeView } from "@/lib/live/intake-review";
import { getIntakeRouteShapes } from "@/lib/live/route-shapes";
import { useIntakeRoutes } from "@/features/map/use-intake-routes";
import { useRouteDetail } from "@/features/map/use-route-detail";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import { draftOf, editsFor, rows } from "./model";
import type { BusToast } from "@/lib/toast-bus";
import { useQuiet } from "@/lib/use-quiet";
import { useIntakeEvents } from "./use-intake-events";
import styles from "./intake-review.module.css";

/**
 * The screen of a plan the server has taken (`/intakes/[intakeId]`): the plan check (`features/plan-check/`) while the server reads and
 * once it has — and, for the two ways it can end without a result, a short panel of its own.
 *
 * ★`[2026-10-03 사용자 결정]` The earlier list-style review screen is gone (it sat behind 「이전 확인 화면 열기」), and with it its
 *   「읽은 일정이 없어요 — 대신 짜 드릴까요?」 panel: asking the server to plan moved to the registration page's third panel,
 *   「계획 짜 주기」 (`features/trip-registration/`). An intake read without stops returns to registration automatically,
 *   keeping the submitted input for correction and showing the reason there.
 */
export function IntakeReview({ intakeId }: { intakeId: string }) {
  const t = useT();
  const { language } = useSettings();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [arrival] = useState(() => intakeArrival(intakeId));
  const arriving = arrival !== undefined;
  const firstView = useMemo(() => sendingOf(arrival ?? ""), [arrival]);
  useEffect(() => { clearIntakeArrival(intakeId); }, [intakeId]);
  // The onboarding answers go to the server with the registration — only when the customer finished them.
  const [onboarding] = useOnboarding();
  // `[2026-10-06]` What the plan screen decided (a day's fullness, the Course Keeper on or off) is laid over it - the latest choice wins, and 「끄고 진행」 says `ask_first` out loud.
  const criteria = useCriteria();
  const survey = withCriteria(onboarding.complete ? toSurvey(onboarding.answers) : undefined, criteria);
  // ★`[2026-10-20 ST4F-665]` A plan this page watched arrive: what that survey already answers (the start survey with the plan screen's choices — who and how many,
  //   priorities, indoors or out, pace) goes to the intake BEFORE its first read, so the loading questions do not ask it again (`survey-questions/preload.ts`).
  //   Every read waits for it (not a disabled query: a progress event that comes meanwhile must still lead to a read). Arriving means the app, and the answers it keeps, is loaded.
  const [preloaded] = useState(() => arriving ? preloadAnswers(intakeId, startAnswers(survey), language) : null);
  const key = ["intake", intakeId, language] as const;
  // ★`[2026-10-02]` While the server reads, its progress stream says when to read the intake again (`useIntakeEvents`).
  //   Only where there is no stream (an older server, or the stream limit) is the intake asked for every 1.5 s, as before.
  const [polling, setPolling] = useState(false);
  const query = useQuery({
    queryKey: key,
    queryFn: async () => { await preloaded; return getIntake(intakeId, language); },
    retry: false,
    refetchOnWindowFocus: false,
    // Keep recently read data when reopening; a new submission opens its progress screen before this first GET finishes.
    staleTime: 2_000,
    refetchInterval: (state) => state.state.data?.status === "review" ? 180_000
      : polling && !state.state.error && state.state.data?.status === "reading" ? 1500 : false,
  });
  const refresh = useRef({ running: false, queued: false });
  const reread = useCallback(() => {
    refresh.current.queued = true;
    if (refresh.current.running) return;
    refresh.current.running = true;
    void (async () => {
      try {
        do {
          refresh.current.queued = false;
          // Wait for an active GET instead of cancelling it on every SSE packet. If another packet arrived meanwhile,
          // read once more afterwards: a completion signal must not be swallowed by the first, older GET.
          await queryClient.refetchQueries({ queryKey: ["intake", intakeId, language] }, { cancelRefetch: false });
        } while (refresh.current.queued);
      } finally { refresh.current.running = false; }
    })();
  }, [queryClient, intakeId, language]);
  // ★`[2026-10-03]` What the server has checked so far arrives as content events while it reads (the GET holds the check only
  //   once it is done): `line` · `item` · `check` · `move` · `done`, copies of state that `reduceStream` folds in.
  const [stream, setStream] = useState<StreamState>(emptyStream);
  const onContent = useCallback((name: string, data: string) => {
    const event = toIntakeEvent(name, data);
    if (event) setStream((current) => reduceStream(current, event));
    if (event?.type === "done") reread();
  }, [reread]);
  const follow = useIntakeEvents(intakeId, query.data?.status === "reading" || (arriving && !query.data && !query.error), language, reread, onContent);
  // ★`[2026-10-03]` A stream that goes silent (`lost`) is not waited for alone: the intake is asked for every 1.5 s as well, until the read ends —
  //   the server keeps no pace for a dead line, and the customer must not sit on a screen that never moves. (The stream still reconnects.)
  if ((follow.follow === "polling" || follow.follow === "lost") && !polling) setPolling(true);
  // ★`[2026-10-06 사용자 지적 — 서버가 1분 넘게 답이 없는데 아무 알림이 없다]` The stream stays open and says nothing of its own when the server is slow: how long NOTHING changed in the reading
  //   (no new line read, no new stage, no new check) is counted here, and the screen says so from 30 s on.
  const linesRead = query.data?.sources.reduce((count, source) => count + source.lines.filter((line) => line.read).length, 0) ?? 0;
  const quiet = useQuiet([query.data?.stage, linesRead, stream.stage, stream.order.length, stream.done ? 1 : 0, stream.progress?.phase, stream.progress?.done].join("|"),
    query.data?.status === "reading" && follow.follow !== "stalled");
  const silenceRef = useRef<SilenceSnapshot>(null);
  const [silence, setSilence] = useState<SilenceSnapshot>(null);
  useEffect(() => {
    const next = silenceSnapshot(silenceRef.current, quiet);
    if (next !== silenceRef.current) {
      silenceRef.current = next;
      setSilence(next);
    }
  }, [quiet]);
  // Without the server's own check (`view.review`) a change goes through the intake's edit call, which answers with the new plan.
  const edit = useMutation({
    mutationFn: ({ revision, edits }: { revision: number; edits: IntakeEdit[] }) => editIntake(intakeId, revision, edits, language),
    onSuccess: (view) => queryClient.setQueryData(key, view),
    onError: (error) => { if (error instanceof LiveError && error.code === "stale_revision") void query.refetch(); },
  });
  // A registered trip makes the cached trip list stale; drop it so the home card and "My trips" read it again.
  // `[2026-10-21 사용자 지시]` The trip is read before going there: the trip screen then opens on it, not on its 「여행 정보를 불러오고 있어요」 page. Until then this screen stays,
  //   still 「서버로 전송중입니다.」 (`leaving` keeps the button busy). A failed read only means the trip screen reads it itself, as before.
  const [leaving, setLeaving] = useState(false);
  const registered = async (tripId: string) => {
    setLeaving(true);
    clearRegistrationDraft();
    queryClient.removeQueries({ queryKey: tripsKey });
    await queryClient.prefetchQuery({ queryKey: tripKey(tripId, language), queryFn: () => tripGateway.getTrip(tripId, language), retry: false });
    router.push(routes.trip(tripId));
  };
  const confirm = useMutation({
    mutationFn: (revision: number) => confirmIntake(intakeId, revision, language, survey),
    onSuccess: (result) => registered(result.trip.trip_id),
    onError: (error) => { if (error instanceof LiveError && error.code === "stale_revision") void query.refetch(); },
  });

  // ★`[2026-10-03]` The plan-check screen (mockup `tripilot-plan-check-streaming.html`) shows the server's intake:
  //   while it reads (`readingOf` — it first draws the lines it has not drawn yet when reading ends), then the result
  //   (`resultOf` — map and list; edit, delete, trip details and register through the same server calls as the edit call above).
  //   An intake opened after reading goes straight to the result.
  //   ★`[2026-10-03]` With the server's own check (`review`, and while reading the events), the places, legs and every check line
  //   come from it and the changes (lock, recommend, search, photos, re-check) go through its calls (`useServerReview`).
  //   Without one (`review: null` — the check failed — or an older server), it says only what the read values say.
  const apply = useCallback((next: ReviewedIntakeView) => { queryClient.setQueryData(["intake", intakeId, language], next); }, [queryClient, intakeId, language]);
  const server = useServerReview({ intakeId, view: query.data, language, apply, reread });
  // ★`[2026-10-03]` While 「전체 자동 추천」 is only previewed (`server.preview`, nothing saved) the screen also draws that plan; every call still goes with the real one.
  // ★`[2026-10-04 사용자 지시]` The two are held side by side — the plan as it is (`reviewed`) and the one the server proposed (`previewed`) — so the list can scroll from one into the other.
  const shown = query.data;
  const reviewed = useMemo(() => shown && shown.status !== "reading" ? reviewResultOf(shown, readingOf(shown), server.infos) : null, [shown, server.infos]);
  const previewed = useMemo(() => server.preview && server.preview.status !== "reading" ? reviewResultOf(server.preview, readingOf(server.preview), server.infos) : null, [server.preview, server.infos]);
  // ★`[2026-10-03]` While the screen still draws what the server did (the intake is already `review` but the rows are being caught up), the last
  //   count the server sent stays on the bar — it would otherwise vanish the moment the server finishes, however many rows are left to draw.
  const reading = useMemo(() => {
    if (!query.data) return null;
    if (query.data.status === "reading") return streamingViewOf(query.data, stream, server.infos);
    const base = reviewed ?? readingOf(query.data);
    const last = stream.progress;
    return last ? { ...base, serverProgress: { phase: last.phase, done: last.done, total: last.total, title: last.current?.title ?? null } } : base;
  }, [query.data, stream, reviewed, server.infos]);
  const result = useMemo(() => {
    if (!query.data || query.data.status === "reading" || query.data.status === "fatal") return null;
    return reviewed ? { ...reviewed, dirty: server.dirty, rechecking: server.rechecking } : resultOf(query.data);
  }, [query.data, reviewed, server.dirty, server.rechecking]);
  // ★`[2026-10-04 사용자 지시]` The lines to draw between the stops on the map (`trip-intakes/{id}/route-shapes`): asked once the check is on screen and again when the plan moves on
  //   (`revision`). Failures are shown with a retry; an older API (404) means route lines are unsupported.
  const routeShapes = useIntakeRoutes(intakeId, query.data?.revision ?? 0, language, Boolean(reviewed));
  // `[2026-10-05 사용자 지시]` Zoomed in, the detailed lines (`?detail=true`) replace these short ones - they follow the streets.
  const routeDetail = useRouteDetail(routeShapes.data, ["intake", intakeId, query.data?.revision ?? 0, language], () => getIntakeRouteShapes(intakeId, language, { detail: true }));
  // ★`[2026-10-06 사용자 지시 — 설문 화면 구현 인계 2단계]` Questions asked while the server reads (`questions[]` of the intake; none from an older server). The screen goes on to the plan check
  //   when the reading is done unless the customer is in the middle of answering - then it is held (`flow.hold`) until they are done, press the button, or the warning runs out.
  const questions = useMemo(() => questionsOf(query.data?.questions, language), [query.data?.questions, language]);
  const flow = useQuestionFlow({ intakeId, language, questions, loadingDone: Boolean(query.data) && query.data?.status !== "reading", fresh: arriving });
  const readingExtras = flow.shown ? { top: <><ReadingQuestions flow={flow} />{flow.phase === "idle" && <IdleWarning flow={flow} />}</>, footer: <ReadingFooter flow={flow} />, onActivity: flow.touch } : undefined;
  const [readingSeen, setReadingSeen] = useState(arriving);
  const [readingDrawn, setReadingDrawn] = useState(false);
  if (query.data?.status === "reading" && !readingSeen) setReadingSeen(true);
  const readingCaughtUp = useCallback(() => setReadingDrawn(true), []);
  // A temporary zero while reading is not an empty result. Removed stops stay in sources and do not trigger this return.
  // ★`[2026-10-26 사용자 지시]` Back to 「계획 담기」 with its sentence instead of the plan check: no stops read, or every stop before today
  //   (server `fatal` · `all_dates_in_past` — the plan never reaches the cards to pick from). `entryReturnOf` says which.
  const entryReturn = entryReturnOf(query.data, t);
  const emptyIntake = entryReturn !== null;
  const emptyReturned = useRef(false);
  useEffect(() => {
    const view = query.data;
    if (!view || view.status === "reading") return;
    if (!emptyIntake) { forgetIntakeSubmission(intakeId); return; }
    if (emptyReturned.current) return;
    emptyReturned.current = true;
    const text = view.sources.filter((source) => source.kind === "text").flatMap((source) => source.lines.map((line) => line.text)).join("\n");
    rememberEmptyIntake(intakeId, entryReturn ?? "", text);
    // A corrected intake must be read again instead of reusing the completed empty snapshot.
    queryClient.removeQueries({ queryKey: ["intake", intakeId, language], exact: true });
    router.replace(routes.newTrip);
  }, [emptyIntake, entryReturn, intakeId, language, query.data, queryClient, router]);
  const shell = (children: ReactNode) => <JourneyShell view="checking" title={["계획 확인", "Check your plan"]}>{children}</JourneyShell>;

  // Returning takes priority over survey holds and replay of the completed read.
  if (emptyIntake) return null;
  if (query.isPending && arriving) return <PlanCheck key="plan" view={firstView} sending onBack={() => router.push(routes.newTrip)} />;
  if (query.isPending || !query.data) return shell(<QueryState loading={query.isPending} error={query.error} retry={() => void query.refetch()} />);
  const view = query.data;
  const testNote: BusToast | null = view.test_scenario ? { text: t(`시험 계획 ${view.test_scenario.code} · ${view.test_scenario.name}`, `Test plan ${view.test_scenario.code} · ${view.test_scenario.name}`), sub: t("검증 결과는 실제 조회에 따라 달라져요.", "Results depend on live checks.") } : null;

  if (view.status === "reading" && follow.follow === "stalled") {
    return shell(<Panel className={styles.waiting}>
      <Eyebrow>{t("읽기가 멈췄어요", "READING STOPPED")}</Eyebrow>
      <h1>{t("서버가 이 계획을 끝까지 읽지 못했어요", "The server stopped reading this plan")}</h1>
      <p role="alert">{t("읽던 서버가 다시 시작됐을 수 있어요. 계획을 다시 올려 주세요.", "The server may have restarted while reading. Please upload the plan again.")}</p>
      <ButtonLink href={routes.newTrip} variant="primary">{t("다시 올리기", "Upload again")}</ButtonLink>
    </Panel>);
  }
  if (flow.hold) {
    // Keep the same PlanCheck instance through the survey: its paused replay must not remount at the completed target.
    return <PlanCheck key="plan" view={reading ?? readingOf(view)} notice={testNote} readingExtras={readingExtras} onBack={() => router.push(routes.newTrip)} />;
  }
  if (reading && (view.status === "reading" || (view.status === "review" && readingSeen && !readingDrawn))) {
    const lostNote: BusToast | null = view.status === "reading" && follow.follow === "lost" ? { text: t("서버와 연결이 끊겼어요", "Lost the connection to the server"), sub: t("다시 연결하는 중이에요…", "Reconnecting…") } : null;
    // `[2026-10-21 사용자 지적]` Slow and quiet are not said while the check is stopped at a question (`slowNotice`); a lost connection still is.
    const slowNote: BusToast | null = view.status !== "reading" || lostNote ? null
      : follow.slow ? { text: t("서버 응답이 늦어지고 있어요", "The server is slow to answer"), sub: stream.progress?.current?.title
        // ★`[2026-10-03]` The server's `progress` packet says what it is at: name it instead of a general "taking a while".
        ? t(`「${stream.progress.current.title}」 확인이 오래 걸리고 있어요. 서버는 계속 확인하고 있어요.`, `Checking “${stream.progress.current.title}” is taking a while. The server is still at it.`)
        : t("읽는 데 시간이 걸리고 있어요. 서버는 계속 읽고 있어요.", "Reading is taking a while. The server is still at it.") }
      : silence?.stage === 60 ? { text: t("1분이 넘게 서버 소식이 없어요", "No news from the server for over a minute"), sub: t("이 화면에서 더 기다리거나, 뒤로 가서 잠시 뒤에 다시 보내 주세요.", "Keep waiting here, or go back and send it again shortly."), note: t("60초 이상 새 진행 소식이 없어요.", "No new progress for at least 60 seconds.") }
      : silence?.stage === 30 ? { text: t("서버 소식이 한동안 없어요", "No news from the server for a while"), sub: t("조금 더 기다리거나, 뒤로 가서 다시 보낼 수 있어요.", "Wait a little longer, or go back and send it again."), note: t("30초 이상 새 진행 소식이 없어요.", "No new progress for at least 30 seconds.") }
      : null;
    // `[2026-10-20 사용자 결정 — 계획 확인 C안]` Once the server's check is final the replay can stop at a card that needs a look and ask inside it: the changes are wired here too.
    return <PlanCheck key="plan" view={reading} notice={lostNote ?? testNote} slowNotice={slowNote} readingExtras={readingExtras} onBack={() => router.push(routes.newTrip)} onCaughtUp={view.status === "review" ? readingCaughtUp : undefined}
      actions={view.status === "review" && view.review ? server.actions : undefined} />;
  }
  if (view.status === "fatal") {
    return shell(<Panel className={styles.waiting}>
      <Eyebrow>{t("읽지 못했어요", "COULD NOT READ")}</Eyebrow>
      <h1>{t("이 계획을 읽지 못했어요", "We could not read this plan")}</h1>
      <p role="alert">{view.fatal?.detail ?? view.fatal?.code}</p>
      <ButtonLink href={routes.newTrip} variant="primary">{t("다시 올리기", "Try again")}</ButtonLink>
    </Panel>);
  }

  // ★The server read it and found no stops at all (the text was not a schedule, or was empty). Stops the customer took out afterwards do not
  //   count: those leave the plan check's own 「남은 일정이 없어요」. A trip already registered from this intake (a planned one) links to the trip.
  const stopsRead = view.sources.reduce((count, source) => count + source.items.length, 0);
  if (stopsRead === 0 && view.status === "confirmed") {
    const tripId = view.trip_id;
    return shell(<Panel className={styles.waiting}>
      <Eyebrow>{t("이미 등록했어요", "ALREADY REGISTERED")}</Eyebrow>
      <h1>{t("이 접수는 여행으로 등록했어요", "This plan is already a trip")}</h1>
      <p>{t("등록한 여행은 여행 화면에서 볼 수 있어요.", "You can see the trip on its own page.")}</p>
      {tripId && <ButtonLink href={routes.trip(tripId)} variant="primary">{t("여행 보기", "Open trip")}</ButtonLink>}
    </Panel>);
  }
  if (!result) return shell(<QueryState loading error={null} />);

  // Every change goes through the intake's edit call, so the server checks the plan again and answers with the new one.
  const send = async (edits: IntakeEdit[]) => { if (edits.length) await edit.mutateAsync({ revision: view.revision, edits }); };
  const rowOf = (id: string) => rows(view).find((row) => row.key === id);
  const refusal = confirm.error instanceof LiveError ? (confirm.error.detail as { problems?: { field: string; message?: string; reason?: string }[] } | undefined) : undefined;
  // The server tried to check places, hours and legs and could not (`review: null` + `review_error`): say so — nothing it did not check is shown as fine.
  const unchecked = view.review_error ? t("서버가 장소·운영시간·이동 확인 결과를 만들지 못했어요. 등록할 때 다시 확인해요.", "The server could not build the place, hours and route check. It checks again when you register.") : null;
  // The text also asked us to plan, but stops were read too: only the stops are shown, so say where the planning is.
  const asked = view.check?.plan.requested ? t("글에 일정을 짜 달라는 말도 있었어요. 대신 짜 받으려면 등록 화면의 「계획 짜 주기」를 써 주세요.", "The text also asked us to plan. Use “Plan it for me” on the registration page.") : null;
  // `[2026-10-05]` A date written without a year: the server took one (and says so in its own note) - the screen says which, so the customer can correct it.
  const year = assumedYear(view);
  const yearNote = year ? t(`날짜에 해가 적혀 있지 않아 ${year}년으로 두었어요. 다르면 일정의 날짜를 고쳐 주세요.`, `Some dates had no year, so ${year} was assumed. Change the date of a stop if that is wrong.`) : null;
  const details = [unchecked, asked, yearNote].filter(Boolean).join("\n");
  const finalNotice: BusToast | null = details ? { text: t("계획 확인 안내", "Plan check notice"), sub: [details, testNote?.text, testNote?.sub].filter(Boolean).join("\n"), stay: Boolean(unchecked) } : testNote;
  return <PlanCheck key="plan" view={result} previewView={previewed ? { ...previewed, dirty: false, rechecking: null } : null} routes={routeDetail.routes} onMapZoom={routeDetail.onZoom} routeState={{ loading: routeShapes.isFetching, error: routeShapes.isError, retry: () => { void routeShapes.refetch(); } }} notice={finalNotice} onBack={() => router.push(routes.newTrip)}
    tripIssues={tripIssuesOf(view)}
    actions={view.review ? server.actions : {
      edit: async (id: string, draft: ItemDraft) => { const row = rowOf(id); if (row) await send(editsFor(row, draft)); },
      // `[2026-10-04]` Several stops' new times in ONE request (title · date · place stay as they are; an empty start leaves the start alone).
      retime: async (changes) => {
        const edits = changes.flatMap((change) => {
          const row = rowOf(change.id);
          return row ? editsFor(row, { ...draftOf(row), start: change.start || draftOf(row).start, end: change.end }) : [];
        });
        await send(edits);
      },
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
      ready: view.review ? view.review.ready : Boolean(view.check?.ready), previewReady: server.preview?.review ? server.preview.review.ready : undefined, busy: confirm.isPending || leaving,
      // The plan the server holds when it is pressed — a plan saved a moment before (the proposed one, registered from) has a newer revision than this render's.
      onRegister: () => confirm.mutate(queryClient.getQueryData<ReviewedIntakeView>(key)?.revision ?? view.revision),
      error: confirm.error?.message ?? null, problems: refusal?.problems?.map((problem) => problem.message ?? `${problem.field}: ${problem.reason}`) ?? [],
      loginRequired: loginRequired(confirm.error),
      loginHref: `${routes.myPageAccount}?returnTo=${encodeURIComponent(routes.intake(intakeId))}`,
      registeredHref: view.status === "confirmed" && view.trip_id ? routes.trip(view.trip_id) : null,
    }} />;
}

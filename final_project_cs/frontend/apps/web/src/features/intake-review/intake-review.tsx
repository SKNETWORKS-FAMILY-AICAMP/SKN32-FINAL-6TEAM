"use client";

import { useCallback, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { JourneyShell } from "@/components/layout/journey-shell";
import { ButtonLink, Eyebrow, Panel, QueryState } from "@/components/ui";
import { useOnboarding } from "@/features/onboarding/onboarding-state";
import { toSurvey } from "@/features/onboarding/payload";
import { candidatesOf, readingOf, resultOf, tripIssuesOf } from "@/features/plan-check/from-intake";
import { reviewResultOf, streamingViewOf } from "@/features/plan-check/from-review";
import { useServerReview } from "@/features/plan-check/use-server-review";
import type { ItemDraft } from "@/features/plan-check/model";
import { PlanCheck } from "@/features/plan-check/plan-check";
import { tripsKey } from "@/lib/gateway";
import { LiveError } from "@/lib/live/client";
import { emptyStream, reduceStream, toIntakeEvent, type StreamState } from "@/lib/live/intake-events";
import { confirmIntake, editIntake, getIntake, type IntakeEdit } from "@/lib/live/intake";
import type { ReviewedIntakeView } from "@/lib/live/intake-review";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import { rows, editsFor } from "./model";
import { useIntakeEvents } from "./use-intake-events";
import styles from "./intake-review.module.css";

/**
 * The screen of a plan the server has taken (`/intakes/[intakeId]`): the plan check (`features/plan-check/`) while the server reads and
 * once it has — and, for the two ways it can end without a result, a short panel of its own.
 *
 * ★`[2026-10-03 사용자 결정]` The earlier list-style review screen is gone (it sat behind 「이전 확인 화면 열기」), and with it its
 *   「읽은 일정이 없어요 — 대신 짜 드릴까요?」 panel: asking the server to plan moved to the registration page's third panel,
 *   「계획 짜 주기」 (`features/trip-registration/`). Here, an intake the server read but found no stops in gets a short note and a link back
 *   to that page.
 */
export function IntakeReview({ intakeId }: { intakeId: string }) {
  const t = useT();
  const { language } = useSettings();
  const router = useRouter();
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
    // ★`[2026-10-03]` The page opens on the intake the progress screen just read (`intake-starting.tsx`): do not read it again at once.
    //   (`invalidateQueries` / `refetch` below still read it whenever the stream or an edit asks.)
    staleTime: 2_000,
    refetchInterval: (state) => polling && !state.state.error && state.state.data?.status === "reading" ? 1500 : false,
  });
  const reread = useCallback(() => void queryClient.invalidateQueries({ queryKey: ["intake", intakeId, language] }), [queryClient, intakeId, language]);
  // ★`[2026-10-03]` What the server has checked so far arrives as content events while it reads (the GET holds the check only
  //   once it is done): `line` · `item` · `check` · `move` · `done`, copies of state that `reduceStream` folds in.
  const [stream, setStream] = useState<StreamState>(emptyStream);
  const onContent = useCallback((name: string, data: string) => {
    const event = toIntakeEvent(name, data);
    if (event) setStream((current) => reduceStream(current, event));
  }, []);
  const follow = useIntakeEvents(intakeId, query.data?.status === "reading", language, reread, onContent);
  // ★`[2026-10-03]` A stream that goes silent (`lost`) is not waited for alone: the intake is asked for every 1.5 s as well, until the read ends —
  //   the server keeps no pace for a dead line, and the customer must not sit on a screen that never moves. (The stream still reconnects.)
  if ((follow.follow === "polling" || follow.follow === "lost") && !polling) setPolling(true);
  // Without the server's own check (`view.review`) a change goes through the intake's edit call, which answers with the new plan.
  const edit = useMutation({
    mutationFn: ({ revision, edits }: { revision: number; edits: IntakeEdit[] }) => editIntake(intakeId, revision, edits, language),
    onSuccess: (view) => queryClient.setQueryData(key, view),
    onError: (error) => { if (error instanceof LiveError && error.code === "stale_revision") void query.refetch(); },
  });
  // A registered trip makes the cached trip list stale; drop it so the home card and "My trips" read it again.
  const registered = (tripId: string) => { queryClient.removeQueries({ queryKey: tripsKey }); router.push(routes.trip(tripId)); };
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
  // ★`[2026-10-03]` While 「전체 자동 추천」 is only previewed (`server.preview`, nothing saved) the screen draws that plan; every call still goes with the real one.
  const shown = server.preview ?? query.data;
  const reviewed = useMemo(() => shown && shown.status !== "reading" ? reviewResultOf(shown, readingOf(shown), server.infos) : null, [shown, server.infos]);
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
  const [readingSeen, setReadingSeen] = useState(false);
  const [readingDrawn, setReadingDrawn] = useState(false);
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
      : follow.slow ? <p className={styles.streamNote} role="status">{stream.progress?.current?.title
        // ★`[2026-10-03]` The server's `progress` packet says what it is at: name it instead of a general "taking a while".
        ? t(`「${stream.progress.current.title}」 확인이 오래 걸리고 있어요. 서버는 계속 확인하고 있어요.`, `Checking “${stream.progress.current.title}” is taking a while. The server is still at it.`)
        : t("읽는 데 시간이 걸리고 있어요. 서버는 계속 읽고 있어요.", "Reading is taking a while. The server is still at it.")}</p>
      : null;
    return <PlanCheck key="plan" view={reading} notice={streamNote} onBack={() => router.push(routes.newTrip)} onCaughtUp={view.status === "review" ? readingCaughtUp : undefined} />;
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
  if (stopsRead === 0) {
    const tripId = view.status === "confirmed" ? view.trip_id : null;
    const asked = Boolean(view.check?.plan.requested);
    return shell(<Panel className={styles.waiting}>
      <Eyebrow>{tripId ? t("이미 등록했어요", "ALREADY REGISTERED") : t("읽은 일정이 없어요", "NO STOPS READ")}</Eyebrow>
      <h1>{tripId ? t("이 접수는 여행으로 등록했어요", "This plan is already a trip") : t("이 글에서는 일정을 찾지 못했어요", "We found no stops in this")}</h1>
      <p>{tripId ? t("등록한 여행은 여행 화면에서 볼 수 있어요.", "You can see the trip on its own page.")
        : asked ? t("읽은 일정이 없어요. 글에서 일정을 짜 달라는 요청은 읽었어요 — 등록 화면의 「계획 짜 주기」에서 첫날 · 일수 · 인원을 골라 짜 보세요.", "No stops were read. We did read that you asked us to plan — use “Plan it for me” on the registration page and choose the first day, days and travelers.")
          : t("읽은 일정이 없어요. 원문을 확인해 다시 올리거나, 등록 화면의 「계획 짜 주기」를 써 보세요.", "No stops were read. Check the original and upload it again, or use “Plan it for me” on the registration page.")}</p>
      {tripId ? <ButtonLink href={routes.trip(tripId)} variant="primary">{t("여행 보기", "Open trip")}</ButtonLink>
        : <ButtonLink href={routes.newTrip} variant="primary">{t("등록 화면으로", "Back to the registration page")}</ButtonLink>}
    </Panel>);
  }
  if (!result) return shell(<QueryState loading error={null} />);

  // Every change goes through the intake's edit call, so the server checks the plan again and answers with the new one.
  const send = async (edits: IntakeEdit[]) => { if (edits.length) await edit.mutateAsync({ revision: view.revision, edits }); };
  const rowOf = (id: string) => rows(view).find((row) => row.key === id);
  const refusal = confirm.error instanceof LiveError ? (confirm.error.detail as { problems?: { field: string; message?: string; reason?: string }[] } | undefined) : undefined;
  // The server tried to check places, hours and legs and could not (`review: null` + `review_error`): say so — nothing it did not check is shown as fine.
  const unchecked = view.review_error ? <p className={styles.streamNote} role="status">{t("서버가 장소·운영시간·이동 확인 결과를 만들지 못했어요. 읽은 값만 보여 드려요 — 등록할 때 서버가 다시 확인해요.", "The server could not build the place, hours and route check. Only what it read is shown — it checks again when you register.")}</p> : null;
  // The text also asked us to plan, but stops were read too: only the stops are shown, so say where the planning is.
  const asked = view.check?.plan.requested ? <p className={styles.streamNote} role="status">{t("글에 일정을 짜 달라는 말도 있었어요. 읽은 일정만 보여 드려요 — 대신 짜 받으려면 등록 화면의 「계획 짜 주기」를 써 주세요.", "The text also asked us to plan. Only the stops it lists are shown — to have a trip planned, use “Plan it for me” on the registration page.")}</p> : null;
  return <PlanCheck key="plan" view={result} notice={<>{unchecked}{asked}</>} onBack={() => router.push(routes.newTrip)}
    tripIssues={tripIssuesOf(view)}
    actions={view.review ? server.actions : {
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
      ready: view.review ? view.review.ready : Boolean(view.check?.ready), busy: confirm.isPending, onRegister: () => confirm.mutate(view.revision),
      error: confirm.error?.message ?? null, problems: refusal?.problems?.map((problem) => problem.message ?? `${problem.field}: ${problem.reason}`) ?? [],
      registeredHref: view.status === "confirmed" && view.trip_id ? routes.trip(view.trip_id) : null,
    }} />;
}

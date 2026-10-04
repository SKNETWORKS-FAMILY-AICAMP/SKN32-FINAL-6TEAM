"use client";

import { useEffect, useRef, useState, useSyncExternalStore, type FormEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, FileText, Paperclip, X } from "lucide-react";
import { Button, ButtonLink, Eyebrow, PageHeading, Panel, QueryState } from "@/components/ui";
import { HumanCheck, TURNSTILE_SITE_KEY } from "@/features/human-check/human-check";
import { partyLabel } from "@/features/onboarding/model";
import { useOnboarding } from "@/features/onboarding/onboarding-state";
import { toSurvey } from "@/features/onboarding/payload";
import { LiveError, probeSession, startSession } from "@/lib/live/client";
import { beginIntake, clearIntakeFailure, intakeFailure, type PlanRequest } from "@/lib/live/intake-start";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import { examplePlan } from "./example-plan";
import { emptyAsk, paneOfSending, paneReason, seoulToday, type PlanAsk, type RegistrationPane } from "./model";
import { PlanAskFields } from "./plan-ask-fields";
import styles from "./trip-registration.module.css";

const draftKey = "tripilot.web.registration-draft.v1";

function Preferences() {
  const t = useT();
  const [{ complete, answers }] = useOnboarding();
  // ★Without finished answers the registration goes without a survey — say so instead of registering without them in
  //   silence (found 2026-09-28: registered trips had no survey after a reload). `[2026-10-01]` Answers are now kept in
  //   this browser, so this shows only when the questions were never finished.
  if (!complete) return <><div className={styles.preferences}>
    <Eyebrow>{t("여행 취향", "YOUR TRAVEL PREFERENCES")}</Eyebrow>
    <p>{t("취향 설문을 마치지 않아서 이번 등록에는 취향이 반영되지 않아요. 마이페이지에서도 설정할 수 있어요.", "The preference questions are not finished, so this registration goes without them. You can also set them on My page.")}</p>
    <p><ButtonLink href={routes.start}>{t("취향 설정하기", "Set my preferences")}</ButtonLink></p>
  </div><hr /></>;
  const labels: Record<string, string> = { food: t("맛집 탐방", "Food"), nature: t("자연과 힐링", "Nature"), culture: t("문화와 역사", "Culture"), activity: t("액티비티", "Activities"), shopping: t("쇼핑", "Shopping"), local: t("로컬 일상", "Local life") };
  return <><div className={styles.preferences}>
    <Eyebrow>{t("함께 고른 여행 취향", "YOUR TRAVEL PREFERENCES")}</Eyebrow>
    <div className={styles.tags}>{answers.theme && <span className={styles.pill}>{labels[answers.theme]}</span>}{answers.party && <span className={styles.pill}>{partyLabel(answers, t)}</span>}</div>
    <p>{t("홈에서 고른 취향을 이 여행과 함께 이어가요.", "The preferences you chose stay with this journey.")}</p>
  </div><hr /></>;
}

/** One of the three ways to give a plan: a bordered panel that is marked while it is the one that will be sent. */
function Pane({ id, title, active, onActivate, children }: { id: RegistrationPane; title: string; active: boolean; onActivate: () => void; children: ReactNode }) {
  const t = useT();
  // Pressing it, writing in it, choosing in it, or moving the keyboard focus into it makes it the chosen one.
  return <Panel className={styles.pane} data-pane={id} data-active={active || undefined} aria-current={active ? "true" : undefined} aria-labelledby={`pane-${id}-title`}
    onClick={onActivate} onFocus={onActivate}>
    <div className={styles.paneHead}>
      <h2 id={`pane-${id}-title`} className={styles.paneTitle}>{title}</h2>
      {active && <span className={styles.paneBadge}>{t("보낼 칸", "Will be sent")}</span>}
    </div>
    {children}
  </Panel>;
}

// Today in Seoul is known only in the browser: the server render (and the first paint) has none, so no date check is shown before it.
const never = () => () => undefined;

export function TripRegistration() {
  const t = useT();
  const { language } = useSettings();
  const [onboarding] = useOnboarding();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [source, setSource] = useState<string>();
  const [validation, setValidation] = useState("");
  const [draftWarning, setDraftWarning] = useState("");
  // ★A sending the server refused comes back here (`intake-starting.tsx`): its sentence is shown, the attached files and the planning
  //   conditions are given back, and the panel it came from is the chosen one again.
  const [returned] = useState(intakeFailure);
  const [files, setFiles] = useState<File[]>(() => returned?.files ?? []);
  const [restored, setRestored] = useState(() => returned?.message ?? "");
  const [ask, setAsk] = useState<PlanAsk>(() => returned?.plan ? { start: returned.plan.start_date, days: returned.plan.days, party: returned.plan.party_size, wish: returned.plan.wish } : emptyAsk);
  // ★`[2026-10-03 사용자 결정]` The panel touched last is the one that is sent — and only that one .
  const [active, setActive] = useState<RegistrationPane>(() => returned ? paneOfSending(returned) : "text");
  const today = useSyncExternalStore(never, seoulToday, () => "");
  useEffect(() => { clearIntakeFailure(); }, []);
  // ★Human check (Turnstile) — only when a site key is set. A token is good for one send.
  const checking = Boolean(TURNSTILE_SITE_KEY);
  const [humanToken, setHumanToken] = useState<string | null>(null);
  const [humanReset, setHumanReset] = useState(0);
  // Waiting for the next token (a new customer needs two: one to start the session, one for the plan).
  const nextToken = useRef<((token: string) => void) | null>(null);
  function takeToken(token: string | null) {
    setHumanToken(token);
    if (token) { setValidation(""); nextToken.current?.(token); nextToken.current = null; }
  }
  /** Spend the current token and wait for a fresh one — a token is checked once only. */
  function freshToken(): Promise<string> {
    return new Promise((resolve, reject) => {
      const timer = window.setTimeout(() => { nextToken.current = null; reject(new LiveError("human_check_timeout", t("사람 확인이 끝나지 않았어요. 다시 눌러 주세요.", "The human check did not finish. Please press again."))); }, 60_000);
      nextToken.current = (token) => { window.clearTimeout(timer); resolve(token); };
      setHumanToken(null);
      setHumanReset((count) => count + 1);
    });
  }
  // The text box keeps what was typed while the customer moves around the app (this tab's session storage).
  const draft = useQuery({
    queryKey: ["registration-draft"],
    queryFn: async () => {
      try { return sessionStorage.getItem(draftKey) ?? ""; }
      catch { return ""; }
    },
    retry: false,
    staleTime: Infinity,
  });
  const value = source ?? draft.data ?? "";
  // ★글·파일·짜 달라는 조건을 — 글·파일을 계획 읽기로 보내고 확인 화면으로 간다. 등록은 확인 화면의 「등록하고 관리 시작」이 한다.
  //   `[2026-10-03 사용자 지시]` 누르면 곧바로 진행 화면으로 넘어간다: 보내기는 여기서 시작하고(`beginIntake`) 서버의 답은 그 화면이
  //   기다린다. 사람 확인 뒤의 새 고객만 여기서 기다린다 — 세션 시작에 쓴 확인이 한 번 소비되고, 계획은 새 확인으로 간다(두 확인 모두 이 화면에 있다).
  //   `[2026-10-04]` 이미 세션이 있으면(쿠키 · 옛 키 이전) 확인을 쓰지 않고 그대로 보낸다.
  //   ★`[2026-10-03 사용자 결정]` 마지막에 고른 칸만 보낸다: 직접 입력이면 글만, 파일이면 파일만, 계획 짜 주기면 그 조건만(고른 칸이 비어 있으면 단추가 꺼져 있다).
  const [sent, setSent] = useState(false);
  function send(token: string | null) {
    setSent(true);
    const base = { language, humanToken: token };
    if (active === "plan") {
      // The short text rides as the intake's text (the server reads it as the preferences); the survey only when it was finished.
      const plan: PlanRequest = { start_date: ask.start, days: ask.days, party_size: ask.party, wish: ask.wish, ...(onboarding.complete && { survey: toSurvey(onboarding.answers) }) };
      beginIntake({ ...base, text: ask.wish.trim(), files: [], plan });
    } else if (active === "files") beginIntake({ ...base, text: "", files });
    else beginIntake({ ...base, text: value, files: [] });
    router.push(routes.intakeStarting);
  }
  const signUp = useMutation({
    mutationFn: async () => {
      if (await probeSession(language)) return humanToken;       // someone is already here: the check is still unspent, send with it
      await startSession(language, humanToken);                  // the server checks (and spends) the token when it starts the guest session
      return freshToken();
    },
    onSuccess: send,
    // The token was spent on this attempt; ask for a fresh one before the next.
    onError: () => setHumanReset((count) => count + 1),
  });
  const pending = signUp.isPending || sent;
  // Why 「계획 확인하기」 is off: the chosen panel has nothing to send yet.
  const reason = paneReason(active, { text: value, files: files.length, ask }, today);

  /** The panel the customer touched becomes the chosen one; anything said about the last sending goes with it. */
  function choose(pane: RegistrationPane) {
    if (pending) return;                                         // the sending has begun with this panel (review 2026-10-03: a click while the session was starting changed what was sent)
    if (pane !== active) setActive(pane);
  }
  function changeAsk(next: PlanAsk) {
    setAsk(next);
    setActive("plan");
    setValidation("");
    signUp.reset();
    setRestored("");
  }

  function updateSource(next: string) {
    setActive("text");
    setSource(next);
    queryClient.setQueryData(["registration-draft"], next);
    setValidation("");
    signUp.reset();
    setRestored("");
    try { sessionStorage.setItem(draftKey, next); setDraftWarning(""); }
    catch { setDraftWarning(t("임시 저장을 사용할 수 없어요. 이 화면을 닫으면 입력 내용이 사라질 수 있어요.", "Drafts cannot be saved here. Closing this page may lose your input.")); }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    // ★`[2026-10-03 사용자 결정]` The chosen panel must have something in it — 「계획 확인하기」 is off until it has, and says why
    //   (the earlier rule, `[2026-09-30]`, let an empty plan through to a screen that offered to plan; that screen is gone and its
    //   planning is the third panel). Pressing Enter in a field cannot get around the off button.
    if (reason) return;
    if (checking && !humanToken) { setValidation(t("사람 확인이 끝나면 보낼 수 있어요. 잠시만 기다려 주세요.", "You can send once the human check finishes. One moment, please.")); return; }
    setValidation("");
    setRestored("");
    if (checking) signUp.mutate();
    else send(humanToken);
  }

  if (draft.isPending || draft.error) return <QueryState loading={draft.isPending} error={draft.error} retry={() => void draft.refetch()} />;
  const error = validation || signUp.error?.message || restored;

  // The text box, the file picker and the planning conditions each sit in their own panel (`Pane`).
  const textBox = <>
    <div className={styles.labelRow}>
      <label htmlFor="plan-source">{t("나의 여행 계획", "Your travel plan")}</label>
      <Button variant="quiet" className={styles.sample} onClick={() => updateSource(examplePlan(language))} disabled={pending}>{t("예시 불러오기", "Load example")}</Button>
    </div>
    <textarea id="plan-source" name="planSource" className={styles.input} value={value} onChange={(event) => updateSource(event.target.value)} disabled={pending} maxLength={12000} required aria-invalid={Boolean(error)} aria-describedby={`plan-format${error ? " plan-error" : ""}`}
      placeholder={t("1일차 · 2026-09-15\n09:00 호텔 조식\n13:00 점심 식당 · 예약 있음\n\n2일차 · 2026-09-16\n10:00 박물관 관람", "DAY 1 · 2026-09-15\n09:00 Hotel breakfast\n13:00 Lunch restaurant · reserved\n\nDAY 2 · 2026-09-16\n10:00 Museum visit")} />
    <div className={styles.inputMeta}><span id="plan-format">{t("날짜 · 시간 · 장소를 함께 적어 주세요.", "Include dates, times, and places.")}</span><span>{value.length.toLocaleString()} / 12,000</span></div>
  </>;
  // 2026-09-30: file picker designed by Codex astra — the native input stays (hidden) for keyboard and screen readers.
  const filePicker = (
    <div className={`${styles.files} ${styles.filePanel}`}>
      <div className={styles.filePicker}>
        <input
          className={styles.fileInput}
          id="plan-files"
          type="file"
          multiple
          accept="image/*,.pdf,.docx,.xlsx,.txt"
          disabled={pending}
          aria-describedby="plan-files-help plan-files-status"
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              if (!event.repeat) event.currentTarget.click();
            }
          }}
          onChange={(event) => {
            const selected = Array.from(event.currentTarget.files ?? []);
            if (selected.length === 0) return;

            setFiles(selected.slice(0, 5));
            setActive("files");
            setValidation("");
            signUp.reset();
            setRestored("");

            // 같은 파일도 다시 선택할 수 있도록 초기화합니다.
            // 제출할 파일은 기존 files state에 보관됩니다.
            event.currentTarget.value = "";
          }}
        />
        <label className={styles.fileTrigger} htmlFor="plan-files">
          <Paperclip size={18} aria-hidden="true" />
          <span>
            {pending
              ? t("처리 중…", "Processing…")
              : t("파일 선택", "Choose files")}
          </span>
        </label>
      </div>

      <p id="plan-files-help" className={styles.fileHelp}>
        {t(
          "사진 · PDF · 워드 · 엑셀로 된 계획도 올릴 수 있어요 (최대 5개, 한 개 10MB)",
          "You can also upload a photo, PDF, Word or Excel plan (up to 5 files, 10MB each)",
        )}
      </p>

      <p
        id="plan-files-status"
        className={styles.fileStatus}
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {t(`${files.length} / 5개 선택됨`, `${files.length} / 5 files selected`)}
      </p>

      {files.length > 0 && (
        <ul
          className={`${styles.fileList}${pending ? ` ${styles.fileListBusy}` : ""}`}
          aria-label={t("선택한 파일", "Selected files")}
        >
          {files.map((file, index) => (
            <li
              className={styles.fileChip}
              key={`${file.name}-${file.size}-${file.lastModified}-${index}`}
            >
              <FileText
                className={styles.fileIcon}
                size={18}
                aria-hidden="true"
              />

              <div className={styles.fileDetails}>
                <span className={styles.fileName}>{file.name}</span>
                <span className={styles.fileSize}>
                  {file.size < 1024
                    ? `${file.size} B`
                    : file.size < 1024 * 1024
                      ? `${Math.ceil(file.size / 1024)} KB`
                      : `${(file.size / (1024 * 1024)).toFixed(1)} MB`}
                </span>
              </div>

              <button
                className={styles.fileRemove}
                type="button"
                disabled={pending}
                aria-label={t(`${file.name} 빼기`, `Remove ${file.name}`)}
                onClick={() => {
                  setFiles((current) =>
                    current.filter((_, fileIndex) => fileIndex !== index),
                  );
                  setValidation("");
                  signUp.reset();
                  setRestored("");
                }}
              >
                <X size={16} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );

  return <>
    <PageHeading eyebrow="A PLAN THAT FEELS LIKE YOU" title={t("이제, 여행을 담아볼까요?", "Let’s put your trip together.")}
      description={t("준비한 계획을 그대로 붙여 넣어 주세요.\n하나씩 살펴보고, 편안한 여행으로 이어갈게요.", "Paste the plan you have prepared.\nWe’ll walk through it, one step at a time.")} />
    <form onSubmit={submit} noValidate>
      <div className={styles.layout}>
        <div className={styles.editor}>
          <div className={styles.panes}>
            <Pane id="text" title={t("직접 입력", "Type it in")} active={active === "text"} onActivate={() => choose("text")}>{textBox}</Pane>
            <Pane id="files" title={t("파일 선택", "Choose files")} active={active === "files"} onActivate={() => choose("files")}>{filePicker}</Pane>
            <Pane id="plan" title={t("계획 짜 주기 (테스트)", "Plan it for me (test)")} active={active === "plan"} onActivate={() => choose("plan")}>
              <PlanAskFields ask={ask} today={today} disabled={pending} onChange={changeAsk} />
            </Pane>
          </div>
          {checking && <HumanCheck onToken={takeToken} resetKey={humanReset} />}
          {error && <p id="plan-error" className={styles.error} role="alert">{error}</p>}
          {draftWarning && <p className={styles.warning} role="status">{draftWarning}</p>}
        </div>
        <aside className={styles.tips}>
          <Panel>
            <Preferences />
            <h2>{t("작은 준비, 더 편한 여행", "A little preparation goes a long way")}</h2>
            <ol className={styles.tipList}>
              <li>{t("일차 제목에 날짜를 적어요.", "Start each day with a date.")}</li>
              <li>{t("시작 시간과 장소를 한 줄씩 적어요.", "Write each start time and place on a new line.")}</li>
              <li>{t("예약한 일정은 ‘예약 있음’으로 표시해요.", "Mark reserved plans with “reserved”.")}</li>
            </ol>
          </Panel>
        </aside>
      </div>
      <div className={styles.actions}>
        <ButtonLink href={onboarding.agreed ? routes.home : routes.start}><ArrowLeft size={18} strokeWidth={1.6} aria-hidden="true" />{t("이전", "Back")}</ButtonLink>
        {reason
          ? <span id="submit-reason" className={styles.reason} role="status">{t(...reason)}</span>
          : <span className={styles.actionNote}>{t("입력한 계획은 화면을 오가도 유지돼요.", "Your draft stays while you explore.")}</span>}
        <Button variant="primary" type="submit" disabled={pending || Boolean(reason)} aria-describedby={reason ? "submit-reason" : undefined}>{pending ? t("확인을 시작하는 중…", "Starting the check…") : t("계획 확인하기", "Check my plan")}<ArrowRight size={18} strokeWidth={1.6} aria-hidden="true" /></Button>
      </div>
    </form>
  </>;
}

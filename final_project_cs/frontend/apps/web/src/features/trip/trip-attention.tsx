"use client";

import { useEffect, useState, useSyncExternalStore, type KeyboardEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui";
import { MaintenanceItem, NoticeItems, useServiceStatus } from "@/features/support/service-notices";
import { seoul } from "@/lib/live/gateway";
import { LiveError } from "@/lib/live/client";
import { chooseProposal, undoChange, type Notice } from "@/lib/live/extras";
import { useSettings, useT } from "@/lib/settings";
import { openChoices, recentNotices, undoableChange } from "./attention";
import { LinkedText } from "./linked-text";
import type { Trip } from "./model";
import { markNoticesSeen, useSeenNotices } from "./notice-reads";
import { tripKey } from "./use-trip";
import { noticesKey, proposalsKey, recoveryKey, useNotices, useProposals, useRecovery } from "./use-trip-extras";
import { SafetyPanel } from "./trip-safety";
import { RecoveryPanel } from "./trip-recovery";
import type { Recovery } from "@/lib/live/recovery";
import styles from "./trip-attention.module.css";
import { askBrowserNotify, browserNotifyState, type BrowserNotifyState } from "@/lib/browser-notify";

export const NOTICE_LABEL: Record<string, [string, string]> = {
  guidance: ["안내", "Guidance"], proposal_request: ["선택 요청", "Your choice"],
  safety_alert: ["안전 알림", "Safety alert"], change_notice: ["변경 알림", "Change"],
};

export const noticeWhen = (iso: string) => { const at = seoul(iso); return `${at.date} ${at.time}`; };

/** The three lists of the notice center (`[2026-10-07 목업 C안]`): what the server found, what it sent, what it changed. */
export type CenterTab = "warnings" | "notices" | "history";
const TABS: readonly [CenterTab, string, string][] = [["warnings", "살펴볼 점", "Worth a look"], ["notices", "받은 알림", "Notices"], ["history", "변경 이력", "History"]];

/** Server contract (2026-09-29): a proposal with this reason and no options asks "change it?"; answering with this key makes
 *  the server compute options and fill the same proposal (reason becomes `indoor_unknown_options`). */
const CONSENT_REASON = "indoor_unknown";
const FORECAST_REASON = "forecast_advisory";
const CONSENT_KEY = "change";

/**
 * `[2026-10-14 실서버 확인]` The words for the reason the server wrote a version (`append_version(reason=…)`) — 「처음 등록」 was the only one; the others showed the code itself
 * (`customer_request` …) to the customer. A reason not listed here still shows the server's code (the rule above: the screen does not write a line of its own about what it does not know).
 */
const VERSION_REASON: Record<string, [string, string]> = {
  created: ["처음 등록", "Registered"],
  customer_request: ["직접 고침", "Changed by you"],
  customer_choice: ["고른 안 적용", "Your pick applied"],
  auto_adjusted: ["자동으로 바꿈", "Changed automatically"],
  rollback: ["되돌림", "Undone"],
};

/**
 * Live only: what the server is waiting for, found and sent about this trip — the body of the notice center the bell opens.
 * `[2026-10-07 사용자 결정 — 목업 C안 ① 알림 센터]` 「할 일」 first (the disaster pause → going on after it → a choice the server waits for → an automatic change that can be undone), then three tabs:
 * 「살펴볼 점」 (`warnings`) · 「받은 알림」 (`/notices`, a dot on those first seen now) · 「변경 이력」 (`history`).
 * ★Every sentence here is the server's — its notice text, its warning reason, its history. Where it sent none, the screen shows the server's own code instead of writing a line of its own.
 * Read state is this browser's (`notice-reads.ts`): the server keeps none yet.
 */
/**
 * `[2026-10-17 사용자 결정 — ST4F-604]` 알림 센터 맨 위 「서비스 공지」 — 운영 앱의 공지(여행과 상관없는 전체 공지)를 맨 위 배너와 같은 모양으로(종류 딱지 · 장애 먼저).
 *   배너를 닫아도 여기서 다시 본다. 게시 중인 공지도 점검도 없으면 칸이 없다.
 */
function ServiceNoticeSection() {
  const t = useT();
  const status = useServiceStatus();
  const notices = status.data?.notices ?? [];
  const maintenance = status.data?.maintenance.enabled ? status.data.maintenance : null;
  if (notices.length === 0 && !maintenance) return null;
  return <section className={styles.tasks} aria-labelledby="trip-service-title" data-service-notices>
    <h3 id="trip-service-title" className={styles.secTitle}>{t("서비스 공지", "Service notices")} {notices.length + (maintenance ? 1 : 0)}</h3>
    {maintenance && <MaintenanceItem maintenance={maintenance} />}
    <NoticeItems notices={notices} />
  </section>;
}

export function TripAttention({ trip, tab, onTab, onGoto, onResumed }: {
  trip: Trip; tab: CenterTab; onTab: (tab: CenterTab) => void;
  /** 「일정에서 보기」: close the center and show that stop in the list. */
  onGoto: (stopId: string) => void;
  /** 「일정 다시 시작」 answered with the brief of the disaster just lifted (null when there was nothing to lift). */
  onResumed: (recovery: Recovery | null) => void;
}) {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  // `[2026-10-07]` The server's "this trip changed" bell is kept by the trip screen (`trip-screen.tsx`) — it listens while the trip is open, not only while this list is shown.
  const proposals = useProposals(trip.id);
  const notices = useNotices(trip.id);
  const recovery = useRecovery(trip.id);
  const choices = openChoices(proposals.data ?? [], notices.data ?? [], trip.stops);
  const { shown, total, hidden } = recentNotices(notices.data ?? []);
  const undoable = undoableChange(notices.data ?? [], trip.version);

  // A dot stays on the notices first seen in this opening (until the center closes — it is drawn only while open); the tab marks them read.
  const seen = useSeenNotices(trip.id);
  const [seenAtOpen] = useState(() => new Set(seen));
  const keys = (notices.data ?? []).map((notice) => notice.key).join("\n");
  const unread = (notices.data ?? []).filter((notice) => !seen.includes(notice.key)).length;
  useEffect(() => {
    if (tab === "notices" && keys) markNoticesSeen(trip.id, keys.split("\n"));
  }, [tab, keys, trip.id]);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: tripKey(trip.id, language) });
    void queryClient.invalidateQueries({ queryKey: proposalsKey(trip.id, language) });
    void queryClient.invalidateQueries({ queryKey: noticesKey(trip.id, language) });
  };
  const chosen = () => { refresh(); void queryClient.invalidateQueries({ queryKey: recoveryKey(trip.id, language) }); };
  const choose = useMutation({
    mutationFn: ({ proposalId, key }: { proposalId: string; key: string | null }) => chooseProposal(trip.id, proposalId, key, language),
    // Refused because it was already decided or the trip moved on: nothing changed, so re-read what is true now.
    onSettled: refresh,
  });

  // ★Undo an automatic change (only customers who chose "change it automatically" get those). 409 = the plan moved on.
  const undo = useMutation({
    mutationFn: (notice: Notice) => undoChange(trip.id, notice.rollback!, language),
    onSettled: refresh,
  });

  const readError = proposals.error ?? notices.error;
  const warnings = trip.warnings ?? [];
  const history = trip.history ?? [];
  const paused = Boolean(trip.safety?.paused);
  const goingOn = !paused && recovery.data ? recovery.data : null;
  const tasks = (paused ? 1 : 0) + (goingOn && !goingOn.chosen ? 1 : 0) + choices.length + (undoable ? 1 : 0);
  const counts: Record<CenterTab, number> = { warnings: warnings.length, notices: total, history: history.length };

  function tabKeys(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const at = TABS.findIndex(([key]) => key === tab);
    const next = TABS[(at + (event.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length][0];
    event.preventDefault();
    onTab(next);
    requestAnimationFrame(() => document.getElementById(`trip-center-tab-${next}`)?.focus());
  }

  return <div className={styles.wrap}>
    <ServiceNoticeSection />
    {readError && <div className={styles.error} role="alert">{t("선택과 알림을 읽지 못했어요 — ", "Could not read your choices and notices — ")}{readError instanceof Error ? readError.message : String(readError)}</div>}

    <section className={styles.tasks} aria-labelledby="trip-tasks-title">
      <h3 id="trip-tasks-title" className={styles.secTitle}>{t("할 일", "To do")}{tasks > 0 ? ` ${tasks}` : ""}</h3>
      {/* `[2026-10-06]` 재난으로 일정이 멈췄으면 맨 위에: 정지 · 안전 안내 · 다시 시작(일정 칸 맨 윗줄에도 같은 패널이 있다). 정지가 없으면 아무것도 그리지 않는다. */}
      <SafetyPanel trip={trip} notices={notices.data ?? []} onChanged={refresh} onResumed={onResumed} where="center" />
      {/* `[2026-10-06]` 다시 시작한 뒤(72시간 안): 아는 것 · 모르는 것 · 남은 일정의 영향 · 이어가는 세 가지 길. 다시 정지 중이면(새 사건) 그 정지 패널이 먼저다. */}
      {goingOn && <RecoveryPanel key={goingOn.pauseId} trip={trip} recovery={goingOn} onChosen={chosen} />}

      {choices.length > 0 && <section className={styles.act} aria-labelledby="trip-choices">
        <h4 id="trip-choices">{t("선택이 필요해요", "Your choice is needed")}{choices.length > 1 ? ` ${choices.length}` : ""}</h4>
        {choices.map(({ proposal, stop, text }) => <div key={proposal.id} className={styles.choice}>
          <p className={styles.what}>{stop ? `${stop.time} · ${stop.title}` : t("이 여행의 일정", "A stop on this trip")}</p>
          <p>{text ?? t(`서버가 이 일정에 대한 선택을 기다려요 (이유: ${proposal.reason}).`, `The server is waiting for your choice on this stop (reason: ${proposal.reason}).`)}</p>
          <div className={styles.options}>
            {/* 2026-09-29: "should we change it?" first (indoor/outdoor unknown). The server computes options only after "change". */}
            {[CONSENT_REASON, FORECAST_REASON].includes(proposal.reason) && proposal.options.length === 0 && <Button variant="primary" disabled={choose.isPending}
              onClick={() => choose.mutate({ proposalId: proposal.id, key: CONSENT_KEY })}>{proposal.reason === FORECAST_REASON
                ? t("예보에 맞게 일정 변경", "Adjust the plan for the forecast")
                : t("바꿔 줘 — 다른 곳 보기", "Change it — show other places")}</Button>}
            {proposal.options.map((option) => <Button key={option.key} variant="primary" disabled={choose.isPending}
              onClick={() => choose.mutate({ proposalId: proposal.id, key: option.key })}>{option.note ? `${option.note} · ` : ""}{option.startsAt ? `${seoul(option.startsAt).time} ` : ""}{option.name}
              {option.warnings.length > 0 && <small className={styles.optionWarning}>{option.warnings.join(" · ")}</small>}</Button>)}
            <Button disabled={choose.isPending} onClick={() => choose.mutate({ proposalId: proposal.id, key: null })}>{t("지금 일정 그대로 두기", "Keep the plan as it is")}</Button>
          </div>
          {(proposal.expiresAt || proposal.safety || stop) && <p className={styles.meta}>
            {proposal.safety ? t("안전과 관련된 선택이에요. ", "This one is about safety. ") : ""}{proposal.expiresAt ? t(`${noticeWhen(proposal.expiresAt)} 까지`, `Until ${noticeWhen(proposal.expiresAt)}`) : ""}
            {stop && <>{proposal.expiresAt || proposal.safety ? " · " : ""}<button type="button" className={styles.link} onClick={() => onGoto(stop.id)}>{t("일정에서 보기", "Show in the plan")}</button></>}</p>}
        </div>)}
      </section>}
      {/* ★Outside the choices card: after a decision the server closes the proposal and the card goes away,
           but what happened (no other place / already decided) must still be said. */}
      {choose.error && <div className={styles.error} role="alert">{choose.error instanceof LiveError && (choose.error.code === "already_decided" || choose.error.code === "stale")
          ? t("이미 정해졌거나 그 사이 일정이 바뀌었어요. 아무것도 바뀌지 않았고, 지금 상태를 다시 불러왔어요.", "It was already decided or the trip changed meanwhile. Nothing was changed; we reloaded the current state.")
          : choose.error.message}</div>}
      {choose.data?.status && !choose.error && <p className={styles.said}>{
          choose.data.status === "options" ? t("다른 곳을 찾았어요 — 위에서 골라 주세요.", "Found other places — pick one above.")
            : choose.data.status === "no_alternate" ? t("바꿀 수 있는 다른 곳을 찾지 못했어요 — 원래 일정을 그대로 둡니다.", "No other place was found — the plan stays as it is.")
            : choose.data.status === "adjusted" ? t("고르신 곳으로 일정을 바꿨어요.", "Your plan now uses the place you picked.")
            : choose.data.status === "kept" ? t("지금 일정을 그대로 두었어요.", "Your plan stays as it is.")
              : t(`처리 결과: ${choose.data.status}`, `Result: ${choose.data.status}`)}</p>}

      {undoable && <section className={styles.act} data-tone="info" aria-labelledby="trip-undo">
        <h4 id="trip-undo">{t("자동으로 바꾼 일정", "Changed automatically")}</h4>
        <p>{undoable.text ?? t("서버가 문장을 보내지 않았어요.", "The server sent no text.")}</p>
        <div className={styles.options}>
          <Button disabled={undo.isPending} onClick={() => undo.mutate(undoable)}>{undo.isPending ? t("되돌리는 중…", "Undoing…") : t("되돌리기", "Undo")}</Button>
        </div>
      </section>}
      {undo.error && <div className={styles.error} role="alert">{undo.error instanceof LiveError && ["stale_itinerary", "stale", "invalid_version"].includes(undo.error.code)
        ? t("그 사이 일정이 다시 바뀌어 되돌리지 않았어요. 지금 상태를 다시 불러왔어요.", "The plan changed again meanwhile, so nothing was undone. We reloaded the current state.")
        : undo.error.message}</div>}
      {undo.data && !undo.error && <p className={styles.said}>{undo.data.answer ?? t("바꾸기 전 일정으로 되돌렸어요.", "Your plan is back to how it was.")}</p>}

      {tasks === 0 && !goingOn && <p className={styles.empty}>{t("지금 처리할 일은 없어요.", "Nothing to do right now.")}</p>}
    </section>

    <div className={styles.tabs} role="tablist" aria-label={t("알림 종류", "Kinds of notices")} onKeyDown={tabKeys}>
      {TABS.map(([key, ko, en]) => <button key={key} type="button" role="tab" id={`trip-center-tab-${key}`} aria-selected={tab === key} aria-controls="trip-center-panel" tabIndex={tab === key ? 0 : -1}
        onClick={() => onTab(key)}>{t(ko, en)} {counts[key]}{key === "notices" && unread > 0 && <span className={styles.unread} role="img" aria-label={t("읽지 않은 알림", "Unread notices")} />}</button>)}
    </div>
    <div id="trip-center-panel" role="tabpanel" aria-labelledby={`trip-center-tab-${tab}`}>
      {tab === "warnings" && (warnings.length === 0 ? <p className={styles.empty}>{t("살펴볼 점이 없어요.", "Nothing to look at.")}</p>
        : <ul className={styles.list}>{warnings.map((warning, index) => <li key={`${warning.code}-${warning.date ?? ""}-${index}`}>
          {warning.date && <span className={styles.tag}>{warning.date}</span>}
          <p>{warning.reason}</p>
          {warning.remedy && <p className={styles.remedy}>{warning.remedy}</p>}
        </li>)}</ul>)}
      {tab === "notices" && <BrowserNotifyOffer />}
      {tab === "notices" && (total === 0 ? <p className={styles.empty}>{t("받은 알림이 없어요.", "No notices yet.")}</p> : <>
        <ul className={styles.list}>{shown.map((notice) => {
          const label = NOTICE_LABEL[notice.type];
          return <li key={notice.key}>
            <span className={styles.tag} data-type={notice.type}>{label ? t(label[0], label[1]) : notice.type}</span><time>{noticeWhen(notice.at)}</time>
            {!seenAtOpen.has(notice.key) && <span className={styles.unread} role="img" aria-label={t("새 알림", "New")} />}
            {/* A link the server wrote into the notice (the plan's address) is pressable, by the chat's rule: https only. */}
            <p>{notice.text ? <LinkedText text={notice.text} mapLabel={t("지도 앱으로 열기", "Open in maps app")} /> : t("서버가 문장을 보내지 않았어요.", "The server sent no text.")}</p>
          </li>;
        })}</ul>
        {hidden > 0 && <p className={styles.cut}>{t(`최근 ${shown.length}개만 보여요. 전체 ${total}개 중 ${hidden}개는 화면에 없어요.`, `Showing the latest ${shown.length}. ${hidden} of ${total} are not on screen.`)}</p>}
      </>)}
      {tab === "history" && (history.length === 0 ? <p className={styles.empty}>{t("변경 이력이 없어요.", "No changes yet.")}</p>
        : <ul className={styles.list}>{[...history].reverse().map((entry) => <li key={entry.version}>
          <span className={styles.tag} data-type="version">v{entry.version}</span><time>{entry.at} · {VERSION_REASON[entry.reason] ? t(...VERSION_REASON[entry.reason]) : entry.reason}</time>
          {entry.causes.map((cause) => <p key={cause} className={styles.remedy}>{cause}</p>)}
        </li>)}</ul>)}
    </div>

  </div>;
}


/**
 * 「받은 알림」 위 한 줄 — 브라우저(운영체제) 알림 켜기. `[2026-10-16 사용자 지시]`
 * 권한은 단추를 눌렀을 때만 묻는다. 켜면 여행 화면이 뒤에 있을 때도 새 알림이 운영체제 알림으로 뜬다(탭을 닫으면 오지 않는다).
 */
const noSubscribe = () => () => undefined;

function BrowserNotifyOffer() {
  const t = useT();
  // 서버에서 그릴 때는 「없음」 — 브라우저에서만 실제 권한을 읽는다(그리기 불일치를 막는다). 단추로 바꾼 값이 있으면 그것.
  const current = useSyncExternalStore(noSubscribe, browserNotifyState, () => "unsupported" as BrowserNotifyState);
  const [asked, setState] = useState<BrowserNotifyState | null>(null);
  const state = asked ?? current;
  if (state === "unsupported") return null;
  if (state === "granted") return <p className={styles.empty}>{t("브라우저 알림이 켜져 있어요. 이 창을 내려 둬도 새 알림이 떠요.", "Browser notifications are on. New notices pop up even when this window is in the background.")}</p>;
  if (state === "denied") return <p className={styles.empty}>{t("브라우저에서 이 사이트 알림이 막혀 있어요. 주소창 왼쪽 자물쇠 → 알림 → 허용으로 바꿀 수 있어요.", "This site's notifications are blocked in your browser. Allow them from the lock icon left of the address bar.")}</p>;
  return <p className={styles.empty}>{t("창을 내려 둬도 알림을 받으려면", "To get notices while this window is in the background,")}{" "}
    <Button onClick={() => void askBrowserNotify().then(setState)}>{t("브라우저 알림 켜기", "Turn on browser notifications")}</Button></p>;
}

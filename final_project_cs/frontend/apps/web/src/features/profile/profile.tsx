"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ChevronRight } from "lucide-react";
import { Avatar, Button, ButtonLink, Panel } from "@/components/ui";
import { AgentKeys, keysKey } from "@/features/account/agent-keys";
import { ConsentManager } from "@/features/consent/consent-manager";
import { OPTIONAL_CONSENTS, serverPending } from "@/features/consent/consent-model";
import { useAgreedCount, useConsent, useRequiredConsents } from "@/features/consent/consent-store";
import { SessionCard } from "@/features/account/session-card";
import { linksKey, SocialAccounts } from "@/features/account/social-accounts";
import { answerLines, questions } from "@/features/onboarding/model";
import { discordWebhookProblem } from "@/features/onboarding/model";
import { useOnboarding, useOnboardingReady } from "@/features/onboarding/onboarding-state";
import { DATA_MODE } from "@/lib/data-mode";
import type { Translate } from "@/lib/i18n";
import { isAgentKeysUnsupported, listAgentKeys } from "@/lib/live/agent-keys";
import { getLinks, providerName } from "@/lib/live/auth";
import { LiveError } from "@/lib/live/client";
import { readDiscordReturn } from "@/lib/live/discord-connect";
import { isUnsupported } from "@/lib/live/profile";
import { nicknameLabel, useProfile, type Profile } from "@/lib/profile";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import { saveDiscordWebhook, webhookWaiting } from "@/lib/webhook";
import { checkDraft, type ProfileDraft } from "./model";
import { TelegramRow } from "./telegram";
import { serverProfileKey, useServerProfile, WebhookField, WebhookView } from "./webhook";
import styles from "./profile.module.css";

/** The default image with the name line under it: text on My page, the nickname field on the edit screen. */
function Identity({ children }: { children: ReactNode }) {
  return <div className={styles.identity}><Avatar size={88} />{children}</div>;
}

const DISCORD_STATE: Record<"untested" | "ok" | "invalid", [string, string]> = {
  untested: ["시험 전", "not tested"],
  ok: ["시험 통과", "test passed"],
  invalid: ["다시 연결해야 해요", "needs reconnecting"],
};

/** One line of My page: what something is now, and the screen (or the start screen's card) where it is changed. */
function StatusRow({ title, state, href, onClick, disabled }: { title: string; state: string; href?: string; onClick?: () => void; disabled?: boolean }) {
  const inner = <><span className={styles.rowText}><strong>{title}</strong><small>{state}</small></span><ChevronRight size={18} aria-hidden="true" /></>;
  return href
    ? <Link href={href} className={styles.row}>{inner}</Link>
    : <button type="button" className={styles.row} disabled={disabled} onClick={onClick}>{inner}</button>;
}

/**
 * `[2026-10-13 사용자 결정 — 마이페이지 A안]` My page says only how things stand, one line each; nothing is changed here. A line opens its own screen
 * (sign-in & accounts · where alerts go · consents · agent keys), and the travel preferences open the start screen's card as before
 * (`[2026-10-01 user decision]` — asked once there, changed afterwards from here). Each line reads what that screen reads.
 */
function StatusRows({ profile }: { profile: Profile | undefined }) {
  const t = useT();
  const router = useRouter();
  const { language } = useSettings();
  const live = DATA_MODE === "live";
  const session = profile?.session ?? null;
  const member = session?.kind === "member";
  const links = useQuery({ queryKey: linksKey(language), queryFn: () => getLinks(language), enabled: live && member, retry: false });
  const server = useServerProfile(Boolean(session));
  const keys = useQuery({ queryKey: keysKey(language), queryFn: () => listAgentKeys(language), enabled: live && member, retry: false });
  const [{ complete, answers, agreed }, setOnboarding] = useOnboarding();
  const ready = useOnboardingReady();
  // The optional items the server can record; one still waiting for the server (`serverPending`) is not counted.
  const optional = OPTIONAL_CONSENTS.filter((code) => !serverPending(code));
  const optionalAgreed = useAgreedCount(optional);
  const required = useRequiredConsents();
  const loading = t("불러오고 있어요", "Loading");

  function editPreferences() {
    setOnboarding((current) => ({ ...current, open: agreed ? 2 : null }));      // ★`agreed` comes from the consent store (derived), not from this raw state
    router.push(routes.start);
  }

  const account = profile === undefined ? loading
    : profile.unreachable ? t("서버에 연결하지 못해 확인하지 못했어요", "Could not reach the server to check")
      : !session ? t("아직 시작하지 않았어요 · 첫 계획을 올리면 게스트로 시작해요", "Not started yet · your first plan starts you as a guest")
        : !member ? t("게스트 · 이 기기에서만 쓸 수 있어요", "Guest · only on this device")
          : links.data?.length
            ? t(`로그인됨 · ${links.data.map((link) => providerName(link.provider)[0]).join(" · ")}`, `Signed in · ${links.data.map((link) => providerName(link.provider)[1]).join(" · ")}`)
            : t("로그인됨", "Signed in");

  function alerts(): string {
    if (!live) return t("실제 서버에 연결됐을 때만 등록할 수 있어요", "Only when connected to the real server");
    if (!session) return webhookWaiting() ? t("입력한 웹훅은 첫 여행을 등록하면 저장돼요", "The webhook you entered is saved with your first trip") : t("연결한 곳이 없어요", "Nothing connected");
    if (server.isPending) return loading;
    if (server.isError) return isUnsupported(server.error) ? t("이 서버는 알림 채널을 받지 않아요", "This server takes no alert channel") : t("불러오지 못했어요", "Could not load");
    const data = server.data;
    const where = data.noticeChannel ?? (data.webhook.set ? "discord" : data.telegram.connected ? "telegram" : null);
    const guestNote = member ? "" : t(" · 게스트는 알림을 받지 않아요", " · guests get no alerts");
    if (where === "telegram") return t("텔레그램", "Telegram") + guestNote;
    if (where === "discord") return t("디스코드", "Discord") + (data.webhook.status ? ` · ${t(...DISCORD_STATE[data.webhook.status])}` : "") + guestNote;
    return t("연결한 곳이 없어요", "Nothing connected") + guestNote;
  }

  const preferences = !ready ? loading
    : complete ? questions.slice(0, 3).map((question) => answerLines(question.id, answers, t)[0]).join(" · ")
      : t("아직 설정하지 않았어요", "Not set yet");

  const consents = required
    ? t(`필수 동의함 · 선택 ${optionalAgreed}/${optional.length} 동의`, `Required agreed · optional ${optionalAgreed}/${optional.length}`)
    : t("필수 약관에 아직 동의하지 않았어요", "The required terms are not agreed yet");

  function agents(): string {
    if (!member) return t("로그인한 사용자만 쓸 수 있어요", "Signed-in users only");
    if (keys.isPending) return loading;
    if (keys.isError) return isAgentKeysUnsupported(keys.error) ? t("서버가 준비 중이에요", "Being prepared on the server") : t("불러오지 못했어요", "Could not load");
    const active = keys.data.filter((key) => key.status === "active").length;
    return active ? t(`사용 중인 키 ${active}개`, `${active} active key${active === 1 ? "" : "s"}`) : t("아직 만든 키가 없어요", "No keys yet");
  }

  return <nav className={styles.rows} aria-label={t("내 상태", "My status")}>
    {live && <StatusRow href={routes.myPageAccount} title={t("로그인 · 계정", "Sign-in & accounts")} state={account} />}
    <StatusRow href={routes.myPageAlerts} title={t("알림 받는 곳", "Where alerts go")} state={alerts()} />
    <StatusRow title={t("여행 취향", "Travel preferences")} state={preferences} onClick={editPreferences} disabled={!ready} />
    {live && <StatusRow href={routes.myPageConsents} title={t("약관 · 동의", "Terms & consents")} state={consents} />}
    {live && <StatusRow href={routes.myPageAgents} title={t("에이전트 연결", "Connect an agent")} state={agents()} />}
  </nav>;
}

/** My page — read only: the profile, then how things stand. The nickname and image are changed on the edit screen, the rest on each line's screen. */
export function MyPage() {
  const t = useT();
  const router = useRouter();
  const profile = useProfile();
  // `[2026-10-13]` The server's Discord callback comes back to `/mypage?discord=…` (its setting): the alerts screen reads that answer now, so it is passed on there.
  useEffect(() => {
    if (readDiscordReturn(window.location.search) !== null) router.replace(`${routes.myPageAlerts}${window.location.search}`);
  }, [router]);
  return <>
    <div className={styles.bar}>
      <button type="button" className={styles.back} aria-label={t("뒤로", "Back")}
        onClick={() => { if (window.history.length > 1) router.back(); else router.push(routes.home); }}><ArrowLeft size={20} strokeWidth={1.8} aria-hidden="true" /></button>
      <h1>{t("마이페이지", "My page")}</h1>
      <ButtonLink href={routes.myPageEdit} variant="quiet">{t("프로필 수정", "Edit profile")}</ButtonLink>
    </div>
    <Panel className={styles.card}>
      {/* The name line under the image is the nickname; there is no second nickname row. */}
      <Identity><p className={styles.name}>{nicknameLabel(profile, t)}</p>
        {/* `[2026-10-13 사용자 결정]` 메뉴의 게스트 입구와 같은 단추 — 로그인 · 계정 화면에서 로그인한다. */}
        {DATA_MODE === "live" && profile !== undefined && profile.session?.kind !== "member" && <ButtonLink href={routes.myPageAccount} variant="primary">{t("계정으로 계속하기", "Continue with an account")}</ButtonLink>}
      </Identity>
    </Panel>
    <StatusRows profile={profile} />
  </>;
}

/** The head of a My page screen: back to My page, then the screen's name. */
function SubBar({ title }: { title: string }) {
  const t = useT();
  return <div className={styles.bar}>
    <Link href={routes.myPage} className={styles.back} aria-label={t("마이페이지로", "Back to My page")}><ArrowLeft size={20} strokeWidth={1.8} aria-hidden="true" /></Link>
    <h1>{title}</h1>
  </div>;
}

const liveOnly = (t: Translate) => <Panel className={styles.card}><p className={styles.muted}>{t("실제 서버에 연결됐을 때만 쓸 수 있어요.", "Available only when connected to the real server.")}</p></Panel>;

/**
 * `[2026-10-13]` Sign-in & accounts: the cards My page had — whether this browser is a guest or signed in (sign out), and the social accounts
 * (`[2026-10-04 사용자 결정]` no token, a cookie session · `[2026-10-03 사용자 지시]` sign in with or link a social account). A guest signs in here.
 */
export function AccountPage() {
  const t = useT();
  const profile = useProfile();
  return <>
    <SubBar title={t("로그인 · 계정", "Sign-in & accounts")} />
    {DATA_MODE !== "live" ? liveOnly(t) : <>
      {profile !== undefined && <Panel className={styles.card}><SessionCard profile={profile} /></Panel>}
      <Panel className={styles.card}><SocialAccounts /></Panel>
    </>}
  </>;
}

/** `[2026-10-13]` Where alerts go: the Discord webhook and Telegram rows My page had, and the webhook address typed by hand (from the edit screen). */
export function AlertsPage() {
  const t = useT();
  const profile = useProfile();
  const hasSession = Boolean(profile?.session), guest = profile?.session?.kind === "guest";
  // The address field asks for the alert-channel consent too; until it is given, the webhook row above asks once (with a session it is the same question).
  const alertConsent = useConsent("alert_channel");
  return <>
    <SubBar title={t("알림 받는 곳", "Where alerts go")} />
    <Panel className={styles.card}>
      {profile === undefined
        ? <p className={styles.muted} role="status">{t("사용자 정보를 불러오고 있어요.", "Loading your details.")}</p>
        : <dl className={styles.fields}>
          <div><dt>{t("디스코드 웹훅", "Discord webhook")}</dt><dd><WebhookView hasSession={hasSession} guest={guest} /></dd></div>
          {/* ★`[2026-10-05 사용자 지시]` 「텔레그램으로 연결」(알림만) - 서버가 연결할 수 있다고 말할 때만 이 줄이 있다(없으면 줄째 없음). */}
          <TelegramRow hasSession={hasSession} guest={guest} />
        </dl>}
    </Panel>
    {profile !== undefined && (alertConsent || !hasSession) && <Panel className={styles.card} id="webhook-address"><WebhookForm hasSession={hasSession} /></Panel>}
  </>;
}

/** `[2026-10-13]` Consents: `[2026-10-09 사용자 지시]` the required terms are read in full, only the optional items are turned on and off. */
export function ConsentsPage() {
  const t = useT();
  return <>
    <SubBar title={t("약관 · 동의", "Terms & consents")} />
    {DATA_MODE !== "live" ? liveOnly(t) : <Panel className={styles.card}><ConsentManager /></Panel>}
  </>;
}

/** `[2026-10-13]` Agent keys: `[2026-10-04 사용자 지시]` signed-in users (members) only; a guest is told to sign in. */
export function AgentsPage() {
  const t = useT();
  return <>
    <SubBar title={t("에이전트 연결", "Connect an agent")} />
    {DATA_MODE !== "live" ? liveOnly(t) : <Panel className={styles.card}><AgentKeys /></Panel>}
  </>;
}

/**
 * The webhook address typed by hand (since `[2026-10-03]` it can be saved, `lib/webhook.ts`). Blank keeps the saved one — its address is never shown
 * again; the box removes it. With no session yet it waits in page memory for the first trip, as before.
 */
function WebhookForm({ hasSession }: { hasSession: boolean }) {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const [webhook, setWebhook] = useState("");
  const [remove, setRemove] = useState(false);
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const changed = remove || Boolean(webhook.trim());
  const bad = !remove && Boolean(discordWebhookProblem(webhook));
  async function save(event: FormEvent) {
    event.preventDefault();
    if (saving || !changed || bad) return;
    const key = serverProfileKey(language);
    const query = queryClient.getQueryCache().find({ queryKey: key, exact: true });
    setSaving(true);
    setMessage(null);
    try {
      const saved = await saveDiscordWebhook(remove ? null : webhook, language);
      // Another sign-in meanwhile replaced the profile query: the answer belongs to the old one and is not written over it.
      if (saved.where === "server" && query && queryClient.getQueryCache().find({ queryKey: key, exact: true }) === query) queryClient.setQueryData(key, saved.profile);
      setWebhook(""); setRemove(false); setTouched(false);
      setMessage({ ok: true, text: saved.where === "server" ? t("저장했어요.", "Saved.") : t("입력한 웹훅은 첫 여행을 등록하면 서버에 저장돼요. 그 전에 새로고침하면 다시 넣어 주세요.", "The webhook you entered is saved when you register your first trip. Enter it again if you reload before then.") });
    } catch (error) {
      setMessage({ ok: false, text: error instanceof LiveError ? error.message : t("저장하지 못했어요. 잠시 뒤 다시 시도해 주세요.", "Could not save. Please try again shortly.") });
    } finally { setSaving(false); }
  }
  return <form className={styles.card} onSubmit={(event) => void save(event)}>
    <WebhookField hasSession={hasSession} value={webhook} remove={remove} touched={touched}
      onValue={(value) => { setWebhook(value); setMessage(null); }} onRemove={(value) => { setRemove(value); setMessage(null); }} onBlur={() => setTouched(true)} />
    <div className={styles.actions}><Button type="submit" variant="primary" disabled={saving || !changed || bad}>{saving ? t("저장 중…", "Saving…") : t("저장", "Save")}</Button></div>
    {message && <p className={message.ok ? styles.note : styles.failed} role={message.ok ? "status" : "alert"}>{message.text}</p>}
  </form>;
}

/** Profile edit. The draft starts as a copy of the profile and stays on this screen; nothing else sees it. */
export function ProfileEdit() {
  const t = useT();
  const profile = useProfile();
  return profile === undefined
    ? <>
      <EditBar />
      <Panel className={styles.card}><p className={styles.muted} role="status">{t("사용자 정보를 불러오고 있어요.", "Loading your details.")}</p></Panel>
    </>
    : <ProfileForm profile={profile} />;
}

/**
 * The top bar of the edit screen. The nickname and the image have no server call yet, so saving stays off rather than pretending;
 * `[2026-10-13]` the Discord webhook moved to My page 「알림 받는 곳」.
 */
function EditBar() {
  const t = useT();
  return <>
    <div className={styles.bar}>
      <ButtonLink href={routes.myPage} variant="quiet">{t("취소", "Cancel")}</ButtonLink>
      <h1>{t("프로필 수정", "Edit profile")}</h1>
      <Button variant="primary" disabled aria-describedby="profile-save-note">{t("저장", "Save")}</Button>
    </div>
    <p id="profile-save-note" className={styles.notice}>{t("닉네임 · 이미지 저장은 준비 중이에요. 디스코드 웹훅은 마이페이지 「알림 받는 곳」에서 바꿔요.", "Saving the nickname and image is not available yet. The Discord webhook is changed in My page → “Where alerts go”.")}</p>
  </>;
}

function ProfileForm({ profile }: { profile: Profile }) {
  const t = useT();
  const [draft, setDraft] = useState<ProfileDraft>({ nickname: profile.nickname ?? "" });
  const [touched, setTouched] = useState(false);
  const nicknameError = touched && checkDraft(draft).nickname;
  return <><EditBar />
  <Panel className={styles.card}>
    {/* The name line itself becomes the nickname field; its placeholder is what My page shows. */}
    <Identity>
      <label htmlFor="profile-nickname" className="sr-only">{t("닉네임", "Nickname")}</label>
      <input id="profile-nickname" className={styles.nameInput} value={draft.nickname} placeholder={nicknameLabel(profile, t)}
        onChange={(event) => { setDraft({ nickname: event.target.value }); setTouched(true); }} onBlur={() => setTouched(true)}
        autoComplete="nickname" aria-invalid={Boolean(nicknameError)} aria-describedby={nicknameError ? "profile-nickname-error" : undefined} />
      {nicknameError && <p id="profile-nickname-error" className={styles.failed}>{t("닉네임을 입력해 주세요.", "Enter a nickname.")}</p>}
      <Button disabled aria-describedby="profile-image-note">{t("이미지 변경", "Change image")}</Button>
      <p id="profile-image-note" className={styles.note}>{t("이미지 변경은 준비 중이에요.", "Changing the image is not available yet.")}</p>
    </Identity>
  </Panel></>;
}

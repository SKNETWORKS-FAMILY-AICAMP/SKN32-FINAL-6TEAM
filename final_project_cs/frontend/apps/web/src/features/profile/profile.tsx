"use client";

import { useState, type ChangeEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Avatar, Button, ButtonLink, Panel } from "@/components/ui";
import { AgentKeys } from "@/features/account/agent-keys";
import { ConsentManager } from "@/features/consent/consent-manager";
import { SessionCard } from "@/features/account/session-card";
import { SocialAccounts } from "@/features/account/social-accounts";
import { answerLines, questions } from "@/features/onboarding/model";
import { discordWebhookProblem } from "@/features/onboarding/model";
import { useOnboarding, useOnboardingReady } from "@/features/onboarding/onboarding-state";
import { LiveError } from "@/lib/live/client";
import { DATA_MODE } from "@/lib/data-mode";
import { nicknameLabel, useProfile, type Profile } from "@/lib/profile";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import { saveDiscordWebhook } from "@/lib/webhook";
import { checkDraft, type ProfileDraft } from "./model";
import { TelegramRow } from "./telegram";
import { serverProfileKey, WebhookField, WebhookView } from "./webhook";
import styles from "./profile.module.css";

/** The default image with the name line under it: text on My page, the nickname field on the edit screen. */
function Identity({ children }: { children: ReactNode }) {
  return <div className={styles.identity}><Avatar size={88} />{children}</div>;
}

/**
 * `[2026-10-01 user decision]` The start screen (terms, preferences, email) is asked once; the preference answers are
 * looked at and changed here afterwards. The button opens the start screen on its preferences card.
 */
function PreferencesCard() {
  const t = useT();
  const router = useRouter();
  const [{ complete, answers, agreed }, setOnboarding] = useOnboarding();
  const ready = useOnboardingReady();
  function edit() {
    setOnboarding((current) => ({ ...current, open: agreed ? 2 : null }));      // ★`agreed` comes from the consent store (derived), not from this raw state
    router.push(routes.start);
  }
  return <Panel className={styles.card}>
    <div className={styles.sectionHead}>
      <h2 className={styles.sectionTitle}>{t("여행 취향", "Travel preferences")}</h2>
      <Button variant="quiet" disabled={!ready} onClick={edit}>{complete ? t("수정", "Edit") : t("설정하기", "Set up")}</Button>
    </div>
    {!ready
      ? <p className={styles.muted} role="status">{t("저장된 취향을 불러오고 있어요.", "Loading your saved preferences.")}</p>
      : complete
        ? <dl className={styles.fields}>{questions.map((question) => <div key={question.id}>
          <dt>{t(...question.name)}</dt>
          <dd>{answerLines(question.id, answers, t).map((line) => <span key={line} className={styles.line}>{line}</span>)}</dd>
        </div>)}</dl>
        : <p className={styles.muted}>{t("아직 설정하지 않았어요. 설정하면 일정을 확인할 때 반영돼요.", "Not set yet. Once set, it is used when your plan is checked.")}</p>}
    <p className={styles.note}>{t("이 브라우저에 저장돼요. 서버에는 일정을 등록할 때만 함께 보내요.", "Kept in this browser. It goes to the server only when you register a plan.")}</p>
  </Panel>;
}

/** My page — read only. The nickname and the Discord webhook are changed on the edit screen. */
export function MyPage() {
  const t = useT();
  const router = useRouter();
  const profile = useProfile();
  return <>
    <div className={styles.bar}>
      <button type="button" className={styles.back} aria-label={t("뒤로", "Back")}
        onClick={() => { if (window.history.length > 1) router.back(); else router.push(routes.home); }}><ArrowLeft size={20} strokeWidth={1.8} aria-hidden="true" /></button>
      <h1>{t("마이페이지", "My page")}</h1>
      <ButtonLink href={routes.myPageEdit} variant="quiet">{t("수정", "Edit")}</ButtonLink>
    </div>
    <Panel className={styles.card}>
      {/* The name line under the image is the nickname; there is no second nickname row. */}
      <Identity><p className={styles.name}>{nicknameLabel(profile, t)}</p></Identity>
      {profile === undefined
        ? <p className={styles.muted} role="status">{t("사용자 정보를 불러오고 있어요.", "Loading your details.")}</p>
        : <dl className={styles.fields}>
          <div><dt>{t("디스코드 웹훅", "Discord webhook")}</dt><dd><WebhookView hasSession={Boolean(profile.session)} guest={profile.session?.kind === "guest"} /></dd></div>
          {/* ★`[2026-10-05 사용자 지시]` 「텔레그램으로 연결」(알림만) - 서버가 연결할 수 있다고 말할 때만 이 줄이 있다(없으면 줄째 없음). */}
          <TelegramRow hasSession={Boolean(profile.session)} guest={profile.session?.kind === "guest"} />
        </dl>}
    </Panel>
    <PreferencesCard />
    <Panel className={styles.card}><ButtonLink href="/support">{t("문의하기 · 내 문의와 답변", "Contact support · My inquiries")}</ButtonLink></Panel>
    {/* ★`[2026-10-04 사용자 결정]` 토큰은 없다 — 서버가 쿠키 세션을 준다. 여기서는 게스트인지·로그인했는지와 게스트의 제한을 말한다. */}
    {DATA_MODE === "live" && profile !== undefined && <Panel className={styles.card}><SessionCard profile={profile} /></Panel>}
    {/* ★`[2026-10-03 사용자 지시]` 소셜 계정으로 로그인·연결. 서버가 준비한 업체만 단추가 생기고, 아니면 「서버 준비 중」이라고만 말한다. */}
    {DATA_MODE === "live" && <Panel className={styles.card}><SocialAccounts /></Panel>}
    {/* ★`[2026-10-09 사용자 지시]` 필수 약관은 전문으로 읽고, 선택 동의만 켜고 끈다. */}
    {DATA_MODE === "live" && <Panel className={styles.card}><ConsentManager /></Panel>}
    {/* ★`[2026-10-04 사용자 지시]` 에이전트 연결 — 로그인한 사용자(회원)만. 게스트에게는 「로그인하면 쓸 수 있어요」. */}
    {DATA_MODE === "live" && <Panel className={styles.card}><AgentKeys /></Panel>}
  </>;
}

/** Profile edit. The draft starts as a copy of the profile and stays on this screen; nothing else sees it. */
export function ProfileEdit() {
  const t = useT();
  const profile = useProfile();
  return profile === undefined
    ? <>
      <EditBar canSave={false} onSave={() => {}} />
      <Panel className={styles.card}><p className={styles.muted} role="status">{t("사용자 정보를 불러오고 있어요.", "Loading your details.")}</p></Panel>
    </>
    : <ProfileForm profile={profile} />;
}

/**
 * The top bar of the edit screen. Since `[2026-10-03]` the Discord webhook can be saved (`lib/webhook.ts`); the nickname and
 * the image have no server call yet, so saving them stays off rather than pretending.
 */
function EditBar({ canSave, saving = false, onSave }: { canSave: boolean; saving?: boolean; onSave: () => void }) {
  const t = useT();
  return <>
    <div className={styles.bar}>
      <ButtonLink href={routes.myPage} variant="quiet">{t("취소", "Cancel")}</ButtonLink>
      <h1>{t("프로필 수정", "Edit profile")}</h1>
      <Button variant="primary" disabled={!canSave} onClick={onSave} aria-describedby="profile-save-note">{saving ? t("저장 중…", "Saving…") : t("저장", "Save")}</Button>
    </div>
    <p id="profile-save-note" className={styles.notice}>{t("디스코드 웹훅은 저장할 수 있어요. 닉네임·이미지 저장은 준비 중이에요.", "You can save the Discord webhook. Saving the nickname and image is not available yet.")}</p>
  </>;
}

function ProfileForm({ profile }: { profile: Profile }) {
  const t = useT();
  const router = useRouter();
  const { language } = useSettings();
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [draft, setDraft] = useState<ProfileDraft>({ nickname: profile.nickname ?? "" });
  const [touched, setTouched] = useState({ nickname: false, webhook: false });
  // The webhook is typed fresh: the saved address is never shown again. Blank keeps it; `removeWebhook` deletes it.
  const [webhook, setWebhook] = useState("");
  const [removeWebhook, setRemoveWebhook] = useState(false);
  const queryClient = useQueryClient();
  const problems = checkDraft(draft);
  const nicknameError = touched.nickname && problems.nickname;
  const edit = (field: keyof ProfileDraft) => (event: ChangeEvent<HTMLInputElement>) => {
    setDraft({ ...draft, [field]: event.target.value });
    setTouched({ ...touched, [field]: true });
  };
  // Only the webhook is saved: when a well-formed address is typed or removing it is ticked.
  const webhookChanged = removeWebhook || Boolean(webhook.trim());
  const webhookBad = !removeWebhook && Boolean(discordWebhookProblem(webhook));
  const canSave = !saving && !webhookBad && webhookChanged;
  async function save() {
    if (!canSave) return;
    setSaving(true);
    setSaveError("");
    try {
      if (webhookChanged) {
        const saved = await saveDiscordWebhook(removeWebhook ? null : webhook, language);
        if (saved.where === "server") queryClient.setQueryData(serverProfileKey(language), saved.profile);
      }
      router.push(routes.myPage);
    } catch (error) {
      setSaveError(error instanceof LiveError ? error.message : t("저장하지 못했어요. 잠시 뒤 다시 시도해 주세요.", "Could not save. Please try again shortly."));
      setSaving(false);
    }
  }

  return <><EditBar canSave={canSave} saving={saving} onSave={() => void save()} />
  {saveError && <p className={styles.failed} role="alert">{saveError}</p>}
  <Panel className={styles.card}>
    {/* The name line itself becomes the nickname field; its placeholder is what My page shows. */}
    <Identity>
      <label htmlFor="profile-nickname" className="sr-only">{t("닉네임", "Nickname")}</label>
      <input id="profile-nickname" className={styles.nameInput} value={draft.nickname} placeholder={nicknameLabel(profile, t)}
        onChange={edit("nickname")} onBlur={() => setTouched({ ...touched, nickname: true })}
        autoComplete="nickname" aria-invalid={Boolean(nicknameError)} aria-describedby={nicknameError ? "profile-nickname-error" : undefined} />
      {nicknameError && <p id="profile-nickname-error" className={styles.failed}>{t("닉네임을 입력해 주세요.", "Enter a nickname.")}</p>}
      <Button disabled aria-describedby="profile-image-note">{t("이미지 변경", "Change image")}</Button>
      <p id="profile-image-note" className={styles.note}>{t("이미지 변경은 준비 중이에요.", "Changing the image is not available yet.")}</p>
    </Identity>
    <WebhookField hasSession={Boolean(profile.session)} value={webhook} remove={removeWebhook} touched={touched.webhook}
      onValue={(value) => { setWebhook(value); setSaveError(""); }} onRemove={(value) => { setRemoveWebhook(value); setSaveError(""); }}
      onBlur={() => setTouched({ ...touched, webhook: true })} />
  </Panel></>;
}

"use client";

import { useState, type ChangeEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Avatar, Button, ButtonLink, Panel } from "@/components/ui";
import { KeySettings } from "@/features/account/key-settings";
import { answerLines, questions } from "@/features/onboarding/model";
import { useOnboarding, useOnboardingReady } from "@/features/onboarding/onboarding-state";
import { saveRecoveryEmail, useRecoveryEmailOnServer } from "@/lib/contact";
import { LiveError } from "@/lib/live/client";
import { DATA_MODE } from "@/lib/data-mode";
import { nicknameLabel, useProfile, type Profile } from "@/lib/profile";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import { checkDraft, type ProfileDraft } from "./model";
import styles from "./profile.module.css";

const MASK = "••••••••••••••••";

/** The issued token: hidden until asked, never editable. Copy always copies the whole token and says what really happened. */
function TokenField({ token }: { token: string | null }) {
  const t = useT();
  const [shown, setShown] = useState(false);
  const [copied, setCopied] = useState<"done" | "failed" | null>(null);

  async function copy() {
    if (!token) return;
    try {
      await navigator.clipboard.writeText(token);
      setCopied("done");
    } catch {
      setCopied("failed");
    }
  }

  return <div className={styles.token}>
    <p className={styles.tokenValue}>{!token
      ? <span className={styles.muted}>{t("발급된 토큰이 없어요.", "No token has been issued.")}</span>
      : shown ? <code>{token}</code> : <><span aria-hidden="true">{MASK}</span><span className="sr-only">{t("가려진 토큰", "Hidden token")}</span></>}</p>
    <div className={styles.tokenActions}>
      <Button variant="quiet" disabled={!token} onClick={() => setShown((value) => !value)}>{shown ? t("숨기기", "Hide") : t("보기", "Show")}</Button>
      <Button variant="quiet" disabled={!token} onClick={() => void copy()}>{t("복사", "Copy")}</Button>
    </div>
    <p className={copied === "failed" ? styles.failed : styles.note} role="status">{copied === "done"
      ? t("토큰을 복사했어요.", "Token copied.")
      : copied === "failed" ? t("복사하지 못했어요. 보기로 토큰을 연 뒤 직접 복사해 주세요.", "Could not copy. Show the token and copy it yourself.") : ""}</p>
  </div>;
}

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
  const [{ complete, answers }, setOnboarding] = useOnboarding();
  const ready = useOnboardingReady();
  function edit() {
    setOnboarding((current) => ({ ...current, open: current.agreed ? 2 : null }));
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

/** My page — read only. The nickname and the email are changed on the edit screen. */
export function MyPage() {
  const t = useT();
  const router = useRouter();
  const profile = useProfile();
  const emailOnServer = useRecoveryEmailOnServer();
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
          <div><dt>{t("발급된 토큰", "Issued token")}</dt><dd><TokenField token={profile.token} /></dd></div>
          <div><dt>{t("토큰 복구용 이메일", "Recovery email")}</dt><dd>
            {profile.email ? <span className={styles.line}>{profile.email}</span> : <span className={styles.muted}>{t("등록된 이메일이 없습니다.", "No email registered.")}</span>}
            {!profile.email && <ButtonLink href={routes.myPageEdit} variant="quiet">{t("이메일 등록하기", "Add an email")}</ButtonLink>}
            <span className={styles.note}>{!profile.email
              ? t("등록해 두면 보관해요. 복구 메일은 아직 보내지 않아요(준비 중).", "It is kept once you add it. Recovery by email is still being prepared, so no email is sent yet.")
              : emailOnServer
                ? t("서버에 저장돼 있어요. 복구 메일은 아직 보내지 않아요(준비 중).", "Saved on the server. Recovery by email is still being prepared, so no email is sent yet.")
                : t("이 브라우저에만 있어요. 첫 여행을 등록하면 서버에 저장돼요. 복구 메일은 아직 보내지 않아요.", "Only in this browser for now; it is saved to the server when you register your first trip. No recovery email is sent yet.")}</span>
          </dd></div>
        </dl>}
    </Panel>
    <PreferencesCard />
    {/* ★Everything about the token lives on this page (2026-09-28 user): see it here, open another device's token, or replace a leaked one. */}
    {DATA_MODE === "live" && <Panel className={styles.card}><KeySettings /></Panel>}
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
 * The top bar of the edit screen. ★`[2026-10-01]` The recovery email can be saved (in this browser, `lib/contact.ts`);
 * the nickname and the image have no server call yet, so saving them stays off rather than pretending.
 */
function EditBar({ canSave, saving = false, onSave }: { canSave: boolean; saving?: boolean; onSave: () => void }) {
  const t = useT();
  return <>
    <div className={styles.bar}>
      <ButtonLink href={routes.myPage} variant="quiet">{t("취소", "Cancel")}</ButtonLink>
      <h1>{t("프로필 수정", "Edit profile")}</h1>
      <Button variant="primary" disabled={!canSave} onClick={onSave} aria-describedby="profile-save-note">{saving ? t("저장 중…", "Saving…") : t("저장", "Save")}</Button>
    </div>
    <p id="profile-save-note" className={styles.notice}>{t("이메일은 저장할 수 있어요. 닉네임·이미지 저장은 준비 중이에요.", "You can save the email. Saving the nickname and image is not available yet.")}</p>
  </>;
}

function ProfileForm({ profile }: { profile: Profile }) {
  const t = useT();
  const router = useRouter();
  const { language } = useSettings();
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [draft, setDraft] = useState<ProfileDraft>({ nickname: profile.nickname ?? "", email: profile.email ?? "" });
  const [touched, setTouched] = useState({ nickname: false, email: false });
  // The email can change under an open form (the app brings it in step with the server when it opens): a field the
  // customer has not touched follows it, so the form never shows a value that is no longer the saved one.
  const [shownEmail, setShownEmail] = useState(profile.email ?? "");
  if ((profile.email ?? "") !== shownEmail) {
    setShownEmail(profile.email ?? "");
    if (!touched.email) setDraft({ ...draft, email: profile.email ?? "" });
  }
  const problems = checkDraft(draft);
  const nicknameError = touched.nickname && problems.nickname;
  const emailError = touched.email && problems.email;
  const edit = (field: keyof ProfileDraft) => (event: ChangeEvent<HTMLInputElement>) => {
    setDraft({ ...draft, [field]: event.target.value });
    setTouched({ ...touched, [field]: true });
    if (field === "email") setSaveError("");
  };
  // Only the email is saved. It can be saved when it is a well-formed address (or blank, which removes it) and has changed.
  const canSave = !saving && !problems.email && draft.email.trim() !== (profile.email ?? "");
  async function save() {
    if (!canSave) return;
    setSaving(true);
    setSaveError("");
    try {
      await saveRecoveryEmail(draft.email.trim() || null, language);
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
    <div className={styles.field}>
      <p className={styles.label}>{t("발급된 토큰", "Issued token")}</p>
      <TokenField token={profile.token} />
      <p className={styles.note}>{t("토큰은 수정할 수 없어요.", "The token cannot be changed.")}</p>
    </div>
    <div className={styles.field}>
      <label htmlFor="profile-email">{t("토큰 복구용 이메일", "Recovery email")} <small>{t("(선택)", "(optional)")}</small></label>
      <input id="profile-email" type="email" inputMode="email" autoComplete="email" placeholder="example@email.com" value={draft.email}
        onChange={edit("email")} onBlur={() => setTouched({ ...touched, email: true })}
        aria-invalid={Boolean(emailError)} aria-describedby={emailError ? "profile-email-hint profile-email-error" : "profile-email-hint"} />
      <p id="profile-email-hint" className={styles.note}>{t("토큰을 잃어버렸을 때 찾는 데 사용할 이메일이에요.", "The email for finding your token if you lose it.")}</p>
      {emailError && <p id="profile-email-error" className={styles.failed}>{t("이메일 형식이 올바르지 않아요.", "Enter a valid email address.")}</p>}
      <p className={styles.note}>{t("비우고 저장하면 등록한 이메일이 지워져요.", "Save it blank to remove the email.")}</p>
    </div>
  </Panel></>;
}

"use client";

import { useState, type ChangeEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Avatar, Button, ButtonLink, Panel } from "@/components/ui";
import { nicknameLabel, useProfile, type Profile } from "@/lib/profile";
import { routes } from "@/lib/routes";
import { useT } from "@/lib/settings";
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

function Identity({ profile, children }: { profile: Profile | undefined; children?: ReactNode }) {
  const t = useT();
  return <div className={styles.identity}><Avatar size={88} /><p className={styles.name}>{nicknameLabel(profile, t)}</p>{children}</div>;
}

/** My page — read only. The nickname and the email are changed on the edit screen. */
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
      <Identity profile={profile} />
      {profile === undefined
        ? <p className={styles.muted} role="status">{t("사용자 정보를 불러오고 있어요.", "Loading your details.")}</p>
        : <dl className={styles.fields}>
          <div><dt>{t("닉네임", "Nickname")}</dt><dd>{profile.nickname ?? <span className={styles.muted}>{t("아직 발급된 닉네임이 없어요.", "No nickname has been issued yet.")}</span>}</dd></div>
          <div><dt>{t("발급된 토큰", "Issued token")}</dt><dd><TokenField token={profile.token} /></dd></div>
          <div><dt>{t("토큰 복구용 이메일", "Recovery email")}</dt><dd>{profile.email ?? <span className={styles.muted}>{t("등록된 이메일이 없습니다.", "No email registered.")}</span>}</dd></div>
        </dl>}
    </Panel>
  </>;
}

/** Profile edit. The draft starts as a copy of the profile and stays on this screen; nothing else sees it. */
export function ProfileEdit() {
  const t = useT();
  const profile = useProfile();
  return <>
    <div className={styles.bar}>
      <ButtonLink href={routes.myPage} variant="quiet">{t("취소", "Cancel")}</ButtonLink>
      <h1>{t("프로필 수정", "Edit profile")}</h1>
      {/* ★No server call saves a profile yet (see `lib/profile.ts`): saving stays off rather than pretending. */}
      <Button variant="primary" disabled aria-describedby="profile-save-note">{t("저장", "Save")}</Button>
    </div>
    <p id="profile-save-note" className={styles.notice}>{t("프로필 저장 기능은 준비 중이에요.", "Saving your profile is not available yet.")}</p>
    {profile === undefined
      ? <Panel className={styles.card}><p className={styles.muted} role="status">{t("사용자 정보를 불러오고 있어요.", "Loading your details.")}</p></Panel>
      : <ProfileForm profile={profile} />}
  </>;
}

function ProfileForm({ profile }: { profile: Profile }) {
  const t = useT();
  const [draft, setDraft] = useState<ProfileDraft>({ nickname: profile.nickname ?? "", email: profile.email ?? "" });
  const [touched, setTouched] = useState({ nickname: false, email: false });
  const problems = checkDraft(draft);
  const nicknameError = touched.nickname && problems.nickname;
  const emailError = touched.email && problems.email;
  const edit = (field: keyof ProfileDraft) => (event: ChangeEvent<HTMLInputElement>) => {
    setDraft({ ...draft, [field]: event.target.value });
    setTouched({ ...touched, [field]: true });
  };

  return <Panel className={styles.card}>
    <Identity profile={profile}>
      <Button disabled aria-describedby="profile-image-note">{t("이미지 변경", "Change image")}</Button>
      <p id="profile-image-note" className={styles.note}>{t("이미지 변경은 준비 중이에요.", "Changing the image is not available yet.")}</p>
    </Identity>
    <div className={styles.field}>
      <label htmlFor="profile-nickname">{t("닉네임", "Nickname")}</label>
      <input id="profile-nickname" value={draft.nickname} onChange={edit("nickname")} onBlur={() => setTouched({ ...touched, nickname: true })}
        autoComplete="nickname" aria-invalid={Boolean(nicknameError)} aria-describedby={nicknameError ? "profile-nickname-error" : undefined} />
      {nicknameError && <p id="profile-nickname-error" className={styles.failed}>{t("닉네임을 입력해 주세요.", "Enter a nickname.")}</p>}
    </div>
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
    </div>
  </Panel>;
}

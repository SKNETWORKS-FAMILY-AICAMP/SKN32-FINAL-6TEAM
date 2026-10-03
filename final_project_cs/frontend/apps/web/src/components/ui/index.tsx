"use client";

import Link from "next/link";
import { Check } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import { useT } from "@/lib/settings";
import { routes } from "@/lib/routes";
import styles from "./ui.module.css";

type Variant = "primary" | "secondary" | "quiet" | "danger";

export function Button({ variant = "secondary", className = "", type = "button", ...props }: ComponentProps<"button"> & { variant?: Variant }) {
  return <button type={type} className={`${styles.button} ${styles[variant]} ${className}`} {...props} />;
}

export function ButtonLink({ variant = "secondary", className = "", ...props }: ComponentProps<typeof Link> & { variant?: Variant }) {
  return <Link className={`${styles.button} ${styles[variant]} ${className}`} {...props} />;
}

export function Panel({ children, className = "", ...props }: ComponentProps<"section">) {
  return <section className={`${styles.panel} ${className}`} {...props}>{children}</section>;
}

export function Badge({ children, tone = "success", className = "" }: { children: ReactNode; tone?: "success" | "warning"; className?: string }) {
  return <span className={`${styles.badge} ${styles[tone]} ${className}`}>{children}</span>;
}

/**
 * The one default profile image, shared by the menu and My page. Changing it is not offered yet.
 * Drawn inline (the shape of `public/images/tripilot-avatar-default.svg`) so it takes the chosen theme's soft and primary roles.
 */
export function Avatar({ size, className = "" }: { size: number; className?: string }) {
  return <svg viewBox="0 0 96 96" width={size} height={size} aria-hidden="true" className={`${styles.avatar} ${className}`}>
    <rect width="96" height="96" style={{ fill: "var(--color-soft)" }} />
    <circle cx="48" cy="38" r="17" style={{ fill: "var(--color-primary)" }} />
    <path d="M14 96c2-20 16-32 34-32s32 12 34 32z" style={{ fill: "var(--color-primary)" }} />
  </svg>;
}

export function Eyebrow({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <p className={`${styles.eyebrow} ${className}`}>{children}</p>;
}

/** `action` sits at the right end of the title's row. */
export function PageHeading({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: ReactNode; action?: ReactNode }) {
  return <header className={styles.heading}>{eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}{action ? <div className={styles.titleRow}><h1>{title}</h1>{action}</div> : <h1>{title}</h1>}{description && <p>{description}</p>}</header>;
}

export function RegistrationSteps({ current }: { current: 0 | 1 | 2 }) {
  const t = useT();
  const labels = [t("계획 담기", "Your plan"), t("함께 확인", "Check together"), t("여행 시작", "Your journey")];
  return <ol className={styles.steps} aria-label={t("여행 등록 단계", "Trip steps")}>{labels.map((label, index) => (
    <li key={label} aria-current={index === current ? "step" : undefined}>
      <span aria-hidden="true">{index < current ? <Check size={13} /> : `0${index + 1}`}</span>{label}
    </li>
  ))}</ol>;
}

export function QueryState({ loading, error, retry }: { loading: boolean; error: Error | null; retry?: () => void }) {
  const t = useT();
  if (loading) return <div className={styles.queryState} role="status"><h1>{t("여행 정보를 불러오고 있어요", "Loading your trip")}</h1><p>{t("잠시만 기다려 주세요.", "Just a moment.")}</p></div>;
  if (!error) return null;
  return <div className={styles.queryState}><h1>{t("여행 정보를 불러오지 못했어요", "We couldn’t load your trip")}</h1><p role="alert">{error.message}</p><div className={styles.actions}>{retry && <Button onClick={retry}>{t("다시 불러오기", "Try again")}</Button>}<ButtonLink href={routes.newTrip} variant="primary">{t("여행 계획 등록", "Add a travel plan")}</ButtonLink></div></div>;
}

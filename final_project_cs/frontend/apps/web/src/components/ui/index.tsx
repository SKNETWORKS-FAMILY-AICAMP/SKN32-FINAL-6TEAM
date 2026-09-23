import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import styles from "./ui.module.css";

type Variant = "primary" | "secondary" | "quiet";

export function Button({ variant = "secondary", className = "", type = "button", ...props }: ComponentProps<"button"> & { variant?: Variant }) {
  return <button type={type} className={`${styles.button} ${styles[variant]} ${className}`} {...props} />;
}

export function ButtonLink({ variant = "secondary", className = "", ...props }: ComponentProps<typeof Link> & { variant?: Variant }) {
  return <Link className={`${styles.button} ${styles[variant]} ${className}`} {...props} />;
}

export function Panel({ children, className = "", ...props }: ComponentProps<"section">) {
  return <section className={`${styles.panel} ${className}`} {...props}>{children}</section>;
}

export function Badge({ children, tone = "neutral", className = "" }: { children: ReactNode; tone?: "neutral" | "success" | "warning"; className?: string }) {
  return <span className={`${styles.badge} ${styles[tone]} ${className}`}>{children}</span>;
}

export function PageHeading({ eyebrow, title, description }: { eyebrow?: string; title: string; description?: ReactNode }) {
  return <div className={styles.heading}>{eyebrow && <div className={styles.eyebrow}>{eyebrow}</div>}<h1>{title}</h1>{description && <p>{description}</p>}</div>;
}

export function RegistrationSteps({ current }: { current: 0 | 1 | 2 }) {
  return <nav className={styles.steps} aria-label="여행 등록 단계">{["계획 입력", "검증", "관리 시작"].map((label, index) => <span key={label} className={index === current ? styles.current : index < current ? styles.done : ""} aria-current={index === current ? "step" : undefined}><b aria-hidden="true">{index < current ? "✓" : index + 1}</b>{label}</span>)}</nav>;
}

export function QueryState({ loading, error, retry }: { loading: boolean; error: Error | null; retry?: () => void }) {
  if (loading) return <div className={styles.queryState} role="status"><h1>여행 정보를 불러오고 있어요</h1><p>잠시만 기다려 주세요.</p></div>;
  if (!error) return null;
  return <div className={styles.queryState}><h1>여행 정보를 불러오지 못했어요</h1><p role="alert">{error.message}</p><div className={styles.actions}>{retry && <Button onClick={retry}>다시 불러오기</Button>}<ButtonLink href="/trips/new" variant="primary">여행 계획 등록</ButtonLink></div></div>;
}

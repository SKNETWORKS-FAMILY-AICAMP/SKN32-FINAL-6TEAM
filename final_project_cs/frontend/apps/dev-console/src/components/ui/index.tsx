import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./ui.module.css";

export function Button({ variant = "secondary", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" }) {
  return <button type="button" {...props} className={`${styles.button} ${variant === "primary" ? styles.primary : ""} ${className}`} />;
}

export function ButtonLink({ href, children, variant = "secondary" }: { href: string; children: ReactNode; variant?: "primary" | "secondary" }) {
  return <Link href={href} data-button className={`${styles.button} ${variant === "primary" ? styles.primary : ""}`}>{children}</Link>;
}

export function Panel({ children, title, aside, className = "" }: { children: ReactNode; title?: string; aside?: ReactNode; className?: string }) {
  return <section className={`${styles.panel} ${className}`}>{(title || aside) && <header className={styles.panelHead}>{title && <h2>{title}</h2>}{aside}</header>}<div className={styles.panelBody}>{children}</div></section>;
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "success" | "warning" | "danger" }) {
  return <span className={`${styles.badge} ${styles[tone]}`}>{children}</span>;
}

export function PageHeading({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) {
  return <header className={styles.heading}><div>{eyebrow && <p className={styles.eyebrow}>{eyebrow}</p>}<h1>{title}</h1>{description && <p className={styles.description}>{description}</p>}</div>{action}</header>;
}

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warning" | "error" }) {
  return <div className={`${styles.notice} ${styles[tone]}`} role={tone === "error" ? "alert" : undefined}>{children}</div>;
}

export function QueryState({ loading, error, retry }: { loading?: boolean; error?: Error | null; retry?: () => void }) {
  if (loading) return <Notice><p role="status">기록을 불러오고 있습니다.</p></Notice>;
  if (error) return <Notice tone="error"><p>{error.message}</p>{retry && <Button onClick={retry}>다시 불러오기</Button>}</Notice>;
  return null;
}

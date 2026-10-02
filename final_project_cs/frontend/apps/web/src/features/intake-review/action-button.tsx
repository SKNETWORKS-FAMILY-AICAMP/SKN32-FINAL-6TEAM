"use client";

import Link from "next/link";
import type { ComponentProps, MouseEvent, ReactNode } from "react";
import { cx } from "./cx";
import styles from "./action-button.module.css";

type Variant = "default" | "primary" | "ok" | "danger";
const variantClass: Record<Variant, string | false> = { default: false, primary: styles.pri, ok: styles.ok, danger: styles.del };

/**
 * A button of the check screen. `unavailable` greys it but keeps it pressable: the press is answered by `onBlocked`
 * (the screen says why in a toast) instead of nothing — a dead button that never says why looks broken.
 */
export function ActionButton({ variant = "default", big = false, unavailable = false, onBlocked, onClick, className, children, ...rest }: Omit<ComponentProps<"button">, "disabled"> & {
  variant?: Variant; big?: boolean; unavailable?: boolean; onBlocked?: () => void; children: ReactNode;
}) {
  return <button type="button" {...rest} className={cx(styles.btn, variantClass[variant], big && styles.big, className)} aria-disabled={unavailable || undefined}
    onClick={(event: MouseEvent<HTMLButtonElement>) => { if (unavailable) { onBlocked?.(); return; } onClick?.(event); }}>{children}</button>;
}

export function ActionLink({ variant = "default", big = false, className, ...rest }: ComponentProps<typeof Link> & { variant?: Variant; big?: boolean }) {
  return <Link {...rest} className={cx(styles.btn, variantClass[variant], big && styles.big, className)} />;
}

export const ButtonSpinner = () => <i className={styles.spinner} aria-hidden="true" />;
export const ButtonCount = ({ children }: { children: ReactNode }) => <span className={styles.count}>{children}</span>;

/**
 * 브라우저(운영체제) 알림 — 여행 화면이 뒤에 있거나 다른 창을 보고 있을 때도 새 알림을 알린다. `[2026-10-16 사용자 지시]`
 *
 * ★전에는 화면 안 알림 막대만 있어서, 관리자 재난 시험이나 실제 감시 알림이 와도 탭을 보고 있지 않으면 알 길이 없었다
 *   (사용자 보고: 「실제 브라우저 알림으로 안 간다」).
 * ★여행 화면이 열려 있는 동안만 뜬다(서비스 워커 · 웹 푸시는 없다 — 탭을 닫으면 오지 않는다).
 * ★권한은 사용자가 단추를 눌렀을 때만 묻는다(브라우저는 누르지 않은 권한 요청을 막거나 조용히 거절한다).
 */

export type BrowserNotifyState = "unsupported" | "default" | "granted" | "denied";

type NotificationLike = { onclick: ((this: unknown, ev: Event) => unknown) | null; close(): void };
type NotificationCtor = {
  new (title: string, options?: { body?: string; tag?: string; lang?: string }): NotificationLike;
  permission: "default" | "granted" | "denied";
  requestPermission(): Promise<"default" | "granted" | "denied">;
};

function api(): NotificationCtor | null {
  if (typeof window === "undefined" || !("Notification" in window)) return null;
  return (window as unknown as { Notification: NotificationCtor }).Notification;
}

export function browserNotifyState(): BrowserNotifyState {
  const N = api();
  return N ? N.permission : "unsupported";
}

/** 단추를 눌렀을 때만 부른다. 돌려주는 값은 그 뒤의 상태. */
export async function askBrowserNotify(): Promise<BrowserNotifyState> {
  const N = api();
  if (!N) return "unsupported";
  try {
    return await N.requestPermission();
  } catch {
    return N.permission;
  }
}

/** 지금 이 탭을 보고 있나 — 보고 있으면 화면 안 알림 막대로 충분하다(같은 알림을 두 번 띄우지 않는다). */
export function pageInView(): boolean {
  if (typeof document === "undefined") return true;
  return document.visibilityState === "visible" && document.hasFocus();
}

/**
 * 권한이 있고 이 탭을 보고 있지 않을 때만 운영체제 알림을 띄운다. 띄웠으면 true.
 * `tag` 가 같으면 브라우저가 앞 알림을 바꿔 끼운다(같은 알림이 쌓이지 않는다). 누르면 이 탭으로 돌아와 `onOpen` 을 부른다.
 */
export function browserNotify(title: string, body: string | undefined, tag: string, onOpen?: () => void,
  inView: () => boolean = pageInView): boolean {
  const N = api();
  if (!N || N.permission !== "granted" || inView()) return false;
  try {
    const shown = new N(title, { body, tag, lang: typeof document === "undefined" ? undefined : document.documentElement.lang || undefined });
    shown.onclick = () => {
      window.focus();
      onOpen?.();
      shown.close();
    };
    return true;
  } catch {
    return false;                                   // 일부 모바일 브라우저는 생성자를 막는다(서비스 워커로만 허용) — 화면 안 막대는 그대로 뜬다
  }
}

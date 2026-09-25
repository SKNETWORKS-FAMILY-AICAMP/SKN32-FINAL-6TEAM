type Provider = "naver" | "google";
type SdkGlobals = Window & Record<string, unknown>;

interface LoaderOptions<T> {
  provider: Provider;
  label: string;
  authCallback: "navermap_authFailure" | "gm_authFailure";
  read: () => T | undefined;
  url: (key: string, callback: string) => string;
  timeoutMs?: number;
}

/** One script per provider. Network failures are retryable; changing SDK credentials needs a reload. */
export function createSdkLoader<T>(options: LoaderOptions<T>) {
  let attempt = 0;
  let entry: { key: string; promise: Promise<T> } | undefined;
  let authError: Error | undefined;
  let authInstalled = false;
  let rejectPending: ((error: Error) => void) | undefined;
  const authSubscribers = new Set<(error: Error) => void>();

  function installAuthHandler() {
    if (authInstalled) return;
    const globals = window as unknown as SdkGlobals;
    const previous = globals[options.authCallback];
    globals[options.authCallback] = () => {
      authError = new Error(`${options.label} 인증에 실패했습니다. 웹용 키·허용 주소·서비스 활성화 설정을 확인한 뒤 페이지를 새로고침해 주세요.`);
      rejectPending?.(authError);
      authSubscribers.forEach((subscriber) => subscriber(authError!));
      if (typeof previous === "function") previous();
    };
    authInstalled = true;
  }

  function load(key: string): Promise<T> {
    if (typeof window === "undefined" || typeof document === "undefined") {
      return Promise.reject(new Error("지도는 브라우저에서만 불러올 수 있습니다."));
    }
    if (!key.trim()) return Promise.reject(new Error(`${options.label} 웹용 키가 설정되지 않았습니다.`));
    if (authError) return Promise.reject(authError);
    if (entry) {
      if (entry.key !== key) {
        return Promise.reject(new Error(`${options.label} 키가 변경되었습니다. 페이지를 새로고침해 주세요.`));
      }
      return entry.promise;
    }
    installAuthHandler();
    const globals = window as unknown as SdkGlobals;
    const callback = `__tripilot_${options.provider}_ready_${++attempt}`;
    const script = document.createElement("script");
    script.async = true;
    script.dataset.tripilotMapSdk = options.provider;
    script.src = options.url(key, callback);

    // Register the entry before appending; a cached script may resolve immediately.
    let resolveLoad!: (sdk: T) => void;
    let rejectLoad!: (error: Error) => void;
    const promise = new Promise<T>((resolve, reject) => {
      resolveLoad = resolve;
      rejectLoad = reject;
    });
    entry = { key, promise };
    let settled = false;
    const finish = () => {
      settled = true;
      clearTimeout(timeout);
      script.onerror = null;
      rejectPending = undefined;
      // A timed-out response may still execute; its obsolete callback must be harmless.
      globals[callback] = () => {};
    };
    const fail = (error: Error) => {
      if (settled) return;
      finish();
      script.remove();
      entry = undefined;
      rejectLoad(error);
    };
    const timeout = setTimeout(() => {
      fail(new Error(`${options.label}을 불러오는 시간이 초과됐습니다. 네트워크를 확인하고 다시 시도해 주세요.`));
    }, options.timeoutMs ?? 15_000);
    rejectPending = fail;
    globals[callback] = () => {
      if (settled) return;
      const sdk = options.read();
      if (!sdk) {
        fail(new Error(`${options.label} 라이브러리가 준비되지 않았습니다. 다시 시도해 주세요.`));
        return;
      }
      finish();
      resolveLoad(sdk);
    };
    script.onerror = () => fail(new Error(`${options.label}을 불러오지 못했습니다. 네트워크를 확인하고 다시 시도해 주세요.`));
    document.head.append(script);
    return promise;
  }

  function watchAuthFailure(subscriber: (error: Error) => void) {
    installAuthHandler();
    authSubscribers.add(subscriber);
    if (authError) subscriber(authError);
    return () => { authSubscribers.delete(subscriber); };
  }

  return { load, watchAuthFailure };
}

import type { PlanAsk, RegistrationPane } from "./model";

export interface LoginDraft { text: string; files: File[]; ask: PlanAsk; active: RegistrationPane }
const DATABASE = "tripilot-registration-login";
const STORE = "draft";
const KEY = "pending";

async function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/** 외부 소셜 화면으로 이동해도 파일까지 이 브라우저에 보존한다. */
export async function keepLoginDraft(draft: LoginDraft): Promise<void> {
  const db = await database();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE, "readwrite");
      transaction.objectStore(STORE).put(draft, KEY);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
  } finally { db.close(); }
}

export async function takeLoginDraft(): Promise<LoginDraft | null> {
  const db = await database();
  try {
    return await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE, "readonly");
      const store = transaction.objectStore(STORE);
      const request = store.get(KEY);
      let draft: LoginDraft | null = null;
      request.onsuccess = () => { draft = request.result ?? null; };
      transaction.oncomplete = () => resolve(draft);
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
  } finally { db.close(); }
}

export async function clearLoginDraft(): Promise<void> {
  const db = await database();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE, "readwrite");
      transaction.objectStore(STORE).delete(KEY);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
  } finally { db.close(); }
}

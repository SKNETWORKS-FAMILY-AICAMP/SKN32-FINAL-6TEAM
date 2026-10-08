import type { TermsDoc } from "./terms-content";

/**
 * `[2026-10-05 사용자 지시]` 동의 증빙: 고객이 동의할 때 본 **한국어 약관 전문**의 지문(sha256)을 서버에 함께 보낸다. 서버는 동의 기록에 이 값을 남기고,
 * 나중에 「그때 어떤 글에 동의했나」는 그 약관 버전의 정본 글을 같은 방식으로 계산해 맞춰 본다.
 * 글은 제목과 모든 절의 제목·본문(한국어)을 빈 줄 하나로 이은 것이다 - 이 모양을 바꾸면 옛 기록과 맞춰 볼 수 없으니 바꾸지 않는다.
 */
export function docText(doc: Pick<TermsDoc, "title" | "sections">): string {
  return [doc.title[0], ...doc.sections.flatMap((section) => [section.heading[0], section.body[0]])].join("\n\n");
}

/** The title without its trailing 「(필수)」/「(선택)」 - the box already says which it is (`[필수]`/`[선택]`), so the label does not say it twice. */
export const plainTitle = (title: readonly [ko: string, en: string]): readonly [string, string] => [title[0].replace(/\s*\((필수|선택)\)\s*$/, ""), title[1].replace(/\s*\((required|optional)\)\s*$/i, "")];

const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

const rotr = (value: number, bits: number) => (value >>> bits) | (value << (32 - bits));

/**
 * SHA-256 in plain code. The browser's own (`crypto.subtle`) exists only on a secure page (https, localhost); a phone reaching the development server over plain
 * http has none, and a consent proof must not depend on how the page was reached. `sha256Hex` uses the browser's when it is there.
 */
export function sha256Bytes(data: Uint8Array): Uint8Array {
  const bitLength = data.length * 8;
  const padded = new Uint8Array(Math.ceil((data.length + 9) / 64) * 64);
  padded.set(data);
  padded[data.length] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(padded.length - 8, Math.floor(bitLength / 2 ** 32));
  view.setUint32(padded.length - 4, bitLength >>> 0);
  const h = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
  const w = new Uint32Array(64);
  for (let offset = 0; offset < padded.length; offset += 64) {
    for (let i = 0; i < 16; i += 1) w[i] = view.getUint32(offset + i * 4);
    for (let i = 16; i < 64; i += 1) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0;
    }
    let [a, b, c, d, e, f, g, hh] = h;
    for (let i = 0; i < 64; i += 1) {
      const t1 = (hh + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i]) >>> 0;
      const t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0;
      hh = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0;
    }
    h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
  }
  const out = new Uint8Array(32);
  const outView = new DataView(out.buffer);
  h.forEach((word, index) => outView.setUint32(index * 4, word >>> 0));
  return out;
}

const hex = (bytes: Uint8Array) => Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");

/** sha256 of a text (UTF-8), as 64 lowercase hex digits. */
export async function sha256Hex(text: string): Promise<string> {
  const bytes = new TextEncoder().encode(text);
  const subtle = typeof crypto !== "undefined" ? crypto.subtle : undefined;
  if (subtle) {
    try { return hex(new Uint8Array(await subtle.digest("SHA-256", bytes as BufferSource))); } catch { /* fall through to the plain code */ }
  }
  return hex(sha256Bytes(bytes));
}

/** The proof of what a customer was shown for one document. */
export const docHash = (doc: Pick<TermsDoc, "title" | "sections">) => sha256Hex(docText(doc));

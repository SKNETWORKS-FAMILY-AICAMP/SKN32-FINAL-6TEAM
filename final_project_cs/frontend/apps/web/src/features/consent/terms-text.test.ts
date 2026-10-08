import { describe, expect, it } from "vitest";
import { docText, sha256Bytes, sha256Hex } from "./terms-text";

const hexOf = (bytes: Uint8Array) => Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
const bytes = (text: string) => new TextEncoder().encode(text);

describe("sha256 in plain code (for a page without crypto.subtle)", () => {
  it("matches the published test vectors", () => {
    expect(hexOf(sha256Bytes(bytes("")))).toBe("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    expect(hexOf(sha256Bytes(bytes("abc")))).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    expect(hexOf(sha256Bytes(bytes("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq")))).toBe("248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1");
  });

  it("handles text that is longer than one block and Korean text", async () => {
    const long = "가나다라마바사".repeat(100);
    expect(hexOf(sha256Bytes(bytes(long)))).toBe(await sha256Hex(long));                     // the browser's own and the plain code agree
    expect(await sha256Hex("약관")).toMatch(/^[0-9a-f]{64}$/);
  });
});

describe("the text a consent proof is made from", () => {
  it("is the Korean title and every Korean heading and body, in order, one blank line apart - and nothing English", () => {
    const text = docText({ title: ["서비스 이용약관", "Terms"], sections: [{ heading: ["제1조", "Article 1"], body: ["본문 하나", "Body one"] }, { heading: ["제2조", "Article 2"], body: ["본문 둘", "Body two"] }] });
    expect(text).toBe("서비스 이용약관\n\n제1조\n\n본문 하나\n\n제2조\n\n본문 둘");
  });
});

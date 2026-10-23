import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  // _backup/ 아래 옛 사본은 시험이 아니다 — 지워진 모듈을 불러 「실패 파일」로 잡히던 것을 뺀다(2026-10-12)
  test: { include: ["src/**/*.test.ts"], exclude: ["**/node_modules/**", "**/_backup/**"], environment: "node" },
});

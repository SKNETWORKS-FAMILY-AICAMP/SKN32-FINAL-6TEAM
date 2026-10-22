import { defineConfig } from "../../../../../frontend/apps/web/node_modules/vitest/dist/config.js";
import { fileURLToPath } from "node:url";

export default defineConfig({
  root: fileURLToPath(new URL("../../../../../../", import.meta.url)),
  resolve: { alias: {
    "@": fileURLToPath(new URL("../../../../../frontend/apps/web/src", import.meta.url)),
    "vitest": fileURLToPath(new URL("../../../../../frontend/apps/web/node_modules/vitest/dist/index.js", import.meta.url)),
  } },
  test: { include: ["final_project_cs/wiki/records/evidence/2026-10-23_frontend-audit/web-security/*.test.ts"], environment: "node", fileParallelism: false },
});

import type { DevConsoleGateway } from "./model";
import { createDemoGateway } from "./demo/gateway";

export const dataMode = process.env.NEXT_PUBLIC_CONSOLE_DATA_MODE === "demo" ? "demo" : "unconfigured";

async function unavailable(): Promise<never> {
  throw new Error("개발팀 콘솔의 데이터 연결이 설정되지 않았습니다. 샘플 실행은 NEXT_PUBLIC_CONSOLE_DATA_MODE=demo로 명시해야 합니다. 실제 코어 API 어댑터는 아직 구현되지 않았습니다.");
}

export const gateway: DevConsoleGateway = dataMode === "demo"
  ? createDemoGateway({ storage: () => window.sessionStorage })
  : { createRun: unavailable, getRun: unavailable, listCases: unavailable, getCase: unavailable, saveCase: unavailable, createComparison: unavailable, getComparison: unavailable };

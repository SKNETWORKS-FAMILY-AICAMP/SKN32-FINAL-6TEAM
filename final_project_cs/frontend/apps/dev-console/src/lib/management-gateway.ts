import { dataMode } from "./gateway";
import type { ManagementGateway } from "./management";
import { createDemoManagementGateway } from "./demo/management";

export const managementGateway: ManagementGateway = dataMode === "demo"
  ? createDemoManagementGateway()
  : { async getSnapshot() { throw new Error("관리 앱의 데이터 연결이 설정되지 않았습니다. NEXT_PUBLIC_CONSOLE_DATA_MODE=demo를 명시해야 가상 오류 예시를 볼 수 있습니다. 실제 오류 수집 API는 아직 연결되지 않았습니다."); } };

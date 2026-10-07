import type { ManagementGateway, ManagementSnapshot } from "../management";

// Source: this app's mockups/management-scenario.html (2026-09-30).
// These are fictional examples, never a substitute for failed live requests.
const snapshot: ManagementSnapshot = {
  source: "demo",
  asOf: "2026-10-14 14:35 KST",
  incidents: [
    {
      id: "fp_llm", code: "LLM_TIMEOUT", title: "채팅 분류 LLM 응답 시간 초과", module: "코어 · 분류 실행",
      status: "new", severity: "high", source: "server", affectedUsers: 12, firstSeen: "13:05", lastSeen: "14:32",
      hourlyCounts: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 11, 26],
      hint: "모델 적재 대기(콜드 스타트)가 제한 시간을 넘었을 수 있습니다. 원인 후보를 설명하는 가상 예시이며, 실제 진단 결과가 아닙니다.",
      maskedStack: "OllamaError: Ollama 호출 시간 초과 (가상 예시)\n  app/infrastructure/ollama_chat.py\n  app/modules/travel_ops/feedback.py\n  app/application/classification.py\n  app/modules/travel_ops/trip_messages.py",
      occurrences: [
        { reference: "ERR-7F3A2C", occurredAt: "14:32:05", userHash: "uk#9f2c", traceId: "tr_01JA9Q7M3K2X", tripId: "trp_5d2e", caseId: "cs_8c41", source: "server" },
        { reference: "ERR-7F1D20", occurredAt: "14:30:01", userHash: null, traceId: "tr_job_classifying_1430", tripId: null, caseId: "cs_8a02", source: "job" },
        { reference: "ERR-7F2B91", occurredAt: "14:28:40", userHash: "uk#41ad", traceId: "tr_01JA9Q2B7T0E", tripId: "trp_a910", caseId: "cs_8b77", source: "server" },
        { reference: "ERR-7F0E55", occurredAt: "14:21:17", userHash: "uk#9f2c", traceId: "tr_01JA9PX4QW1C", tripId: "trp_5d2e", caseId: "cs_8a90", source: "server" },
        { reference: "ERR-7E9C04", occurredAt: "14:11:12", userHash: "uk#c3d0", traceId: "tr_01JA9P93HD6M", tripId: "trp_1c33", caseId: "cs_89f1", source: "server" },
        { reference: "ERR-7E1A77", occurredAt: "13:05:33", userHash: "uk#77be", traceId: "tr_01JA9K0Z5R8N", tripId: "trp_77b0", caseId: "cs_8811", source: "server" },
      ],
    },
    {
      id: "fp_notice", code: "INTERNAL_ERROR", title: "알림 목록 조회 중 KeyError", module: "코어 · 여행 API",
      status: "new", severity: "high", source: "server", affectedUsers: 2, firstSeen: "11:48", lastSeen: "12:10",
      hourlyCounts: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 1, 0, 0], occurrences: [],
    },
    {
      id: "fp_kma", code: "EXTERNAL_SOURCE_FAILED", title: "기상청 단기예보 — 외부 소스 확인 실패", module: "활동 · 감시",
      status: "investigating", severity: "medium", source: "job", affectedUsers: 0, firstSeen: "13:10", lastSeen: "13:40",
      hourlyCounts: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6, 0], occurrences: [],
    },
    {
      id: "fp_map", code: "CLIENT_RENDER_ERROR", title: "여행 화면 지도 로딩 실패", module: "웹 · 지도",
      status: "new", severity: "low", source: "web", affectedUsers: 4, firstSeen: "09:12", lastSeen: "14:05",
      hourlyCounts: [0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 1, 0, 1, 0, 1], occurrences: [],
    },
  ],
};

export function createDemoManagementGateway(): ManagementGateway {
  return { async getSnapshot() { return structuredClone(snapshot); } };
}

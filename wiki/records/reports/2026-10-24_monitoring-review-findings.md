---
type: report
title: 감시 응대 독립 검토 결함과 후속 작업
status: draft
domain: travel
---

# 독립 검토에서 확인한 결함

[순수 probe·정적 검토] 73개 지정시험 통과 이후 독립child가 두 결함을 재현했습니다. 현재모니터링전체안전완료상태를선언하지않습니다.

1. monitoring.case_payload가asked/retry만확인해 no_alternate/recheck_failed가있는혼합batch를applied/complete로표시할수있습니다. 실제trip_watch_batch/itinerary_actions의저장summary에미해결항목이빠져항목결과보존이필요합니다.
2. proposal참조는정확한trip prefix를검사하지않아 trip:other:proposal:x도awaiting_choice로인정했습니다. 실제타고객자료유출재현은아닙니다.

부모는새구현child에재현시험RED→항목별저장요약보존/정확tripref검증→GREEN과기본Case성공outbox의동일키/트랜잭션안내연결을인계했습니다. tick에서outbox재발행금지,Core업무판정/거래/DBschema변경금지입니다.

별도child에는기존의미해석/읽기경로로‘왜바꿨어?’를실제저장원인/판에연결하는읽기전용후속을인계했습니다. 복수/만료/판변경/타trip이면추정하지않고재질문하며변경/승인/알림재실행하지않습니다. 두절은현재미완료입니다.

웹notice기존허용필드는내부scope/evidence/token을그대로내보내지않지만monitoring종결상태연결도필요합니다. 실DBcommit/배달·모델·운영은미검증입니다. 현재추가사용자운영승인요청은없고운영변경도없습니다.

## 관계

- [모니터링 부모 체크포인트](2026-10-24_monitoring-parent-checkpoint.md)
- [구현 인계](../../handoff/2026-10-24_travel-writing-implementation.md)

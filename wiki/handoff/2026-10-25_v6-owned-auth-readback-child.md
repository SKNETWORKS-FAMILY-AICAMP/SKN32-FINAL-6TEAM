# v6 owned guest readback — 부모 인계

[결과·안전·미해결](../records/reports/2026-10-25_v6-owned-auth-readback-child.md)

- live PID24140/PPID23792, localhost+LAN8042 재확인. 정상 인증 GET 정확8회 모두200, CORS credentials8/8.
- auth·consents·trip shared-live 기존SHA/양쪽SHA 동일. trip ownership/version/items 일치.
- intake 전체 정제SHA는 양쪽부터 다릅니다. diff 경로를 메모리에만 유지하지 못하여 원인 미확정, 추가 GET 없이 strict acceptance FAIL 보존. intake core 동등성은 닫지 마십시오.
- 업무11표 SHA동일, session 변경은 승인 fixture last_used_at 1행뿐. v6 policy counters 전후 모두0. 모델/유료/remote/restart/fixture copy/제품 소스변경0.
- startup public14/14·loaded341/341은 기존 부모 검증이며 전환 짧은 gap 기록 유지. 전체 고객 기능 PASS 금지.

추가 증거는 runtime-v6-serving/auth-readback-owned-20261025/acceptance.json. 역사적 증거/공유 인덱스를 덮지 않고 고유 문서만 추가했습니다.

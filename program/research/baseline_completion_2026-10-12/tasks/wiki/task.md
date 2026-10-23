# wiki 작성 기준·상태 표시·정합성 — W16·W20·W22·W23·W25

OpenWiki/OKF를 참고해 이미 정한 프로젝트 표준을 지킵니다. 새 표준을 임의로 도입하지 않습니다. `wiki/governance/document-standard.md`, front-matter·evidence-grades·review-policy·implementation-state, `program/research/_prompts/문서병합_지침.md`를 전문으로 읽고 기존 모순과 현재 사실을 대조하세요.

## 소유 범위

- `wiki/governance/`, `wiki/delivery/roles.md`, `final_project_cs/wiki/teams/code-layout.md`, `program/scripts/check_wiki.py`, `program/scripts/build_wiki_catalogs.py` 및 관련 검사 시험. 다른 세션이 수정하는 feature 계약은 직접 덮어쓰지 말고 적용 목록·필요한 수정안을 결과로 전달합니다.
- W16 실제 README 담당을 유지하고 임의로 팀원을 배정하지 않습니다. 인증·DB 상시 전담 미확정 등은 기존 설계 범위를 보존하며 디렉토리 책임과 기능 책임을 구분합니다. 외부 근거는 기존 공식 자료를 확인하고 최초 발명자를 지어내지 않습니다.
- W20 머리말의 문서 검토/결정/구현/검증 상태와 본문의 환경별 배포 상태·시각·증거를 연결합니다. 현재 주요 결정·계약 전체의 적용 대상 목록을 만들고 확인하지 않은 구현·배포는 unverified로 적습니다. 무조건 draft→stable/implemented/verified로 올리지 않습니다.
- 특히 `wiki/governance/implementation-state.md`의 “양쪽 DB에 옛 표가 남음 / x600 제외 규칙 없음” 예시는 2026-10-12 정리 후 현재 사실과 다릅니다. 기존 증거 날짜를 보존하고 현재 SQL 실측 링크로 정정하세요. findings-v2.json의 일부 completion_evidence·updated_at에도 과거 시점이 남아 있어 현재 상태와 혼동됩니다. 원본을 백업한 뒤 과거 기록과 현재 확인 결과를 구분하는 구조로 고치되 사용자 선택은 바꾸지 않습니다. parent가 관리하는 review_status/coordination 파일은 수정하지 않습니다.
- 검사기는 현재/생성/기록/백업 범위를 명시하고 자동 목록은 생성기로 갱신합니다. wiki 검사기 집계와 cs 불변식 목록 수는 범위가 다를 수 있으므로 84/70 등 서로 다른 집계를 같은 숫자로 덮어쓰지 말고 집계 대상·출처를 표시합니다. 오류 없음과 의미상 사양 일치/시험 통과를 구분합니다.
- 현재 본문 먼저·과거 records 링크 원칙을 현재 정본 페이지에 적용하고 과거 자료 자체는 수정하지 않습니다. 기여·계약 의미가 불명확한 모순은 근거와 미결정으로 남기되 이미 승인된 현재 결정을 재승인 질문으로 되돌리지 않습니다.

위키 기본 검사·관련 새 필드 검증·생성물 재현 검사를 실행하고 대상 수와 미적용 목록을 남기세요. 최종 feature 구현 결과가 아직 없으면 영향 문서는 기다리는 대상으로 명시합니다. v12·베이스라인의 최종 작성은 integration 담당이 소유합니다. 자기 status.json과 report.md에 결과를 저장하세요.

# 잔여 비DB 누적 릴리스 준비 — 2026-10-25

판정: **정확 누적 후보 재구성 완료 / 릴리스 HOLD**. 확인 시각 2026-10-25T06:07:11.709959+09:00.

## 누적 입력과 이력

- 기준 commit `635cb3424c75f6621bf75430766f27083dfaa00e`, tree `b5bfeeaf30426f9183bfba12f800434287d339b7`.
- 1단계 remaining-non-db.patch → tree `e94caecf05c9af750b45bef4bdc4e64395caaf8b`, commit `c32348d42d241553f6c344d03c312d0af3c14d34`.
- 2단계 combined-acceptance.patch → 제품 수락 tree `f0288f75fdc32c955201d440da9620ec46dd869d`, commit `eff496edc23d4b9f0b85b14132dfa345c3e600e3`.
- 2단계 SHA256 `bbac2d6d1b45d8ab5626241e625c7647d606681046a34691ab8a61fc88f35f34`. **이전 diagnostic 뒤 적용 금지**. followup-acceptance.patch는 diagnostic 입력에 대한 별도 비교물이며 combined와 순차 적용하지 않습니다.
- 새 후보는 profile scratch `remaining_non_db_release_preparation/repo`; 기존 원본·수락 후보를 변경하지 않았습니다. 날짜/고객시간 실제 commit과 조상 이력을 부모로 유지하며 synthetic snapshot을 부모로 쓰지 않았습니다.
- 본 기록은 제품 코드를 바꾸지 않는 후속 문서 commit입니다. 최종 문서 포함 tree/commit과 정역 검사 정본은 패키지 `FINAL.json`입니다. 기존 검증물은 전부 불변 보존합니다.

## F3 계약 검토

F3는 검증된 성공 publication과 provider 각 시도의 claim을 요청별 동일 lock으로 순서화합니다. publication이 먼저이면 미claim 첫 시도/재시도를 막습니다. claim이 먼저이면 publication 뒤에 실제 provider 함수 진입/전송이 시작할 수 있습니다. 전역 lock·I/O 구간 lock·실행 중 HTTP 물리 취소 보장은 아닙니다.

**사용자 요구나 기존 strict-budget 계약의 완화 승인이 아닙니다.** 일반 failover의 기존 admission/fail-open 관측은 더 엄격한 reader/per-attempt fail-closed 정책에 대한 예외가 아닙니다. 저장소 reserve·원자적 월/일 상한·명시된 strict gate·외부전송 금지 정책은 그대로 필수이며 미충족 요구를 scoped acceptance로 닫지 않습니다. F3 diff는 _hedged/_attempt의 lock·claim뿐이고 CallBudget, Ollama adapter, D-CS-016 blob은 기준과 동일합니다. bool 예약에는 commit/refund가 없어 유료0이어도 예약이 남으며 기존 재시도당 엄격 과금/물리 zero-send를 새로 증명하지 않습니다. 엄격 예산/전송 요구가 릴리스 조건이면 별도 미완료 관문으로 남습니다. 이 문서는 기존 fail-open을 모든 API에 확대하지 않습니다.

원문 probe는 fresh paid_called Event의 유일 set이 paid.append 뒤인데 wait 성공과 최종 paid==[]를 동시에 요구합니다. 직접 소스와 실패 줄을 재검토했고 원문3건의 모순 분류는 정당합니다. 원문 시험을 삭제/xfail/완화하거나 예외를 삼키지 않았습니다. 별도 동등 스케줄은 caller 소비를 worker 완료까지 지연해 동일 enqueue-before-start·paid-zero를 보존합니다. 동일 시험 SHA256 `7261772b1ceaf90a72c288c1f7aa2a26616a00a7965e3fa95cf57f5fab17581c`: 보존된 독립 old RED3/3, new GREEN3/3의 XML·rc·실패 위치를 확인했습니다. 원문은 여전히 wait 줄에서3실패입니다. 이전 원문 실패는 새 pass로 바꾸지 않습니다.

## 실제 누적 시험

- 첫 실행 rc2의 실제 원인은 복사된 UUID 시험의 보조파일 uuid/codex_percall.py 누락입니다. 로그/JSON/XML 보존. 제품 assertion이나 patch 실패가 아닙니다. historical evidence 의존자료도 함께 새 scratch에만 복사했습니다. 가드·assertion·원본은 바꾸지 않았습니다.
- fresh release-single-02: **958/965 = 99.27% pass**, 원문모순3 fail + bind정책차단4 fail, error0/skip0, deselected29, rc1. 기존 단일 실행과 exact JUnit965 집합·7개 실패 ID 동일, 누락0/추가0입니다. 전체 GREEN 아님.
- 누적 제품 tracked19012/19012 = 100% byte manifest 일치, 실행 전후 변화0. 보안 scan text9480/9480, missing0/omitted0. 별도 후속 문서 보안 관문은 FINAL.json에 기록하고965분모에 합산하지 않습니다.
- 추가 제품 결함은 이 실행/검토 범위에서 발견하지 않았습니다. 전체 DoD·실 DB/실모델/실전송/서비스/운영 화면 수락을 의미하지 않습니다.

## local_admin_3300_v2 / 예약 OFF 읽기전용 대조

- 검토된 combined patch의 입력은 같은 b5bfeeaf tree, 결과 `fc35fb10321789fdd720f3740eb13595a97183f2`. 현재 live worktree/비밀 환경/DB 갱신분은 수집·통합하지 않았습니다.
- 양측 겹침은 **문서3경로**: final_project_cs/wiki/index.md, wiki/handoff/index.md, wiki/index.md. 제품 코드 겹침0. admin 단독33경로이며 정확 목록은 admin-overlap.json입니다.
- 새 저장소의 객체 수준 merge-tree는 rc0, 제안 tree `feea96a74f22ac9e689f96d018666e9b1833f797`입니다. 충돌 marker0, 세 문서 모두 양쪽 기록을 보존하는 최소 union이 기계적으로 가능합니다. 제품33경로 전체를 이 F3 릴리스에 몰래 넣지 않았습니다.
- 최소 병합 가능 범위는 위 wiki3의 양쪽 기록/링크 보존뿐입니다. 이후 admin/예약OFF를 실제 포함하면 그33경로와 merged wiki에 별도 수락/최신 환경 조정이 필요합니다. mechanical clean은 admin build/launcher/설정 OFF 저장 수락이 아닙니다. 실제 통합은 미실행입니다.

## 유지되는 HOLD

기준 날짜 commit의 검토된 CRLF 기본 whitespace 실패, 기존 브라우저 부산물/배포 제외 검토, 원문모순3·bind4의 raw 실패, strict accounting/실전송 보장 미수락, 전체 DoD/환경 검증, admin/OFF 실제 통합은 남습니다. 이번은 오프라인 pin 기준이며 원격 최신/CI를 재확인하지 않았습니다. 원본 적용·push·배포·서비스 시작/중지·DB·실모델·외부API 호출은 모두 금지/미실행입니다. DB는 별도 라이팅 세션 소유입니다.

새 승인 요청 없이 이번 좁은 준비 단계만 종료합니다. scratch prune 전 승인된 영속 저장소에 패키지를 보관해야 합니다.

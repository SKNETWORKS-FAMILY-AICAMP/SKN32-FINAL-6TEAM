# 2026-10-25 호텔 조식 예시 3100 실제 교체 완료

확인 시각: 2026-10-25T14:16:09.577565+09:00

기존 3100은 캐시 문제가 아니라 호텔 없는 test1 artifact를 실제 serving하고 있었습니다. exact command/parent/listener/start identity와 기존 provenance를 확인한 두 tracked handle만 종료했고 기존 artifact는 rollback용으로 보존했습니다.

새 서비스는 재빌드 없이 final immutable build를 그대로 재사용합니다. old pin+검증 delta이며 최신12커밋 전체 통합이 아닙니다. 새 incoming candidate/8042 API/DB/Dining 프로세스는 변경하지 않았습니다. 필수동의만 하는 fresh guest 두 개에서 예시 버튼을 눌러 전체 textarea exact equality·서울 일주일 뒤 날짜·첫날09호텔조식→10경복궁·19N서울타워예약·둘째날09호텔조식을 실제 확인했습니다. 선택동의4개는 모두 false, 제출/등록0이며 기존 고객 저장계획 자동업데이트나 수정은 하지 않았습니다.

- http://127.0.0.1:3100/trips/new: build `93tSFrxar_RqgguLjsbwY`, handle `proc_8ddc440853a5` handed_off, listener PID2720, cwd `C:\Users\kcxsz\AppData\Local\hermes\profiles\guguroute\cache\scratch\candidate-review-fix-20261025-134532\localhost-final\web`.
- http://192.168.0.15:3100/trips/new: build `p4N2ThMaXaAI8RY4eWrbC`, handle `proc_3ea4aa66fa7a` handed_off, listener PID4612, cwd `C:\Users\kcxsz\AppData\Local\hermes\profiles\guguroute\cache\scratch\candidate-review-fix-20261025-134532\lan-final\web`.

수락 2/2=100%. 양쪽 HTML 정적 JS 전수 disk/HTTP 동일은 `compiled-http-final.json`, 원문1876byte SHA256·7개 scoped product/test file 해시는 HANDOFF.json. 호텔 chunk `5270-2588f3cc93a3bf0f.js` SHA256 `9bda635530080b0cd53a94ec2a408cb95ca5a95162099338d9d5c246b7e75e27`. compiled API localhost127.0.0.1:8042 / LAN192.168.0.15:8042 일치. UI 사진·textarea·safe traffic·PID/start/command·rollback은 active profile scratch/deploy-hotel-3100-20261025/ 아래 보존했습니다. 3129 final validation listener는 기존 소유 상태 그대로이며 production은3100입니다.

문제: 초기 PowerShell 조회의 bash 달러 확장/디코딩 문제는 외부 파일 기반 조회로 정정; 서비스 및 UI 수락 실패는 없습니다. latest 전체 통합과 real candidate timeout/retry 수락은 별도 owner 범위로 남습니다.

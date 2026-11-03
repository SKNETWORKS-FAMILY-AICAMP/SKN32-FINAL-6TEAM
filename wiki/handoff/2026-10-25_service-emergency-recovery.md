# 2026-10-25 긴급 DB·API·웹 연결 복구

## 결론
**DB·API·UI 연결 복구 완료. test1 질문·대안선택·등록은 별도 다음 절입니다.**

- 정확 target ID7700321712607772424, PostgreSQL16.15, datadir `C:/_proj/postgresql/data/guguroute-16`, `127.0.0.1:5433/acop_cs`.
- 새 DB handle `proc_a722e0c9781f` **handed_off**, terminalPID15288 → 정본launcherPID2912 → postmasterPID6536. cwd `C:/_proj/postgresql/run`.
- 새 API handle `proc_34d42d0ecdbb` **handed_off**, terminalPID2552 → venvPID10936 → listenerPID22260. cwd `C:\Users\kcxsz\AppData\Local\hermes\profiles\guguroute\cache\scratch\skn-develop-step1-20261025-014848\candidate\final_project_cs`. launcher `C:\Users\kcxsz\AppData\Local\hermes\profiles\guguroute\cache\scratch\normal-intake-e2e-20261025\runtime3\launch-final.py`. localhost·LAN8042.
- 기존 웹 handle `proc_efa2a4fe7502`(parent15384/listener27124), `proc_c122bdc3c08b`(parent26404/listener16432) 모두 현재 running. 기존 handed_off 기록 보존, 재시작·kill·빌드변경0. cwd·buildID는 HANDOFF와 frontend-provenance.json.

## 데이터 보존·복구 근거
PID22972는 재사용 프로세스조차 없었습니다. Windows CIM postgres0,5433listener0, 정확 port bind 성공을 직전 재검사했습니다. owner pid/datadir/executable/start epoch와 PID파일 일치·offline control ID 일치 확인. PID 원문·SHA256/mtime·owner/opts/control/정본starter/full log를 고유 **private backup**에 보존한 뒤 원파일을 고유 `postmaster.pid.stale-*`로 원자적 rename했습니다. 삭제0. 정본 server.py 그대로 start했고 직접postgres 우회·resetwal·promotion·restore/initdb/DROP0입니다. source는 기동/변경0입니다. private 백업 경로는 로컬 stale-recovery.json만 참조하며 공개첨부하지 않습니다.

12:53:44 정상start → interrupted 감지 →12:53:49 automatic recovery/redo done/end-of-recovery checkpoint →12:53:49.846 ready. 이번 시작에 공유메모리 충돌/FATAL/PANIC 없음. 과거 error487은11:20/12:16 기록이며 그 뒤 checkpoint가 이어졌으므로 이번 소실 원인으로 확정하지 않습니다. Windows PID파일 shared-memory key 줄은 빈 값이며 stale Windows named object 자체를 열거한 검사는 하지 않았습니다. 새 정본 start/SQL 성공이 현재 collision 없음의 실행증거입니다.

독립 read-only SQL: trips=142, intakes=68, claims=610, sources=58, base tables=110. 필요한 archives/alternatives/dining links/judge 및 reopen 열 존재. 확정시험여행79ffe6f2… latest_version1/itinerary_version1/items2 독립DB·정상 authenticated GET200·same-context reload 확인. 원고객7a7a0e55… fatal/revision1/updated_at `2026-10-25 11:57:01.731006+09` 그대로이며 원문/쿠키 접근·자동쓰기0.

## API·실제 브라우저
- 기존 runtime3 integrity16/16=100%, manifest SHA256 `94f64418d4c4d4f6bb8ffd516d7fb01ee9bf80550c39fe6c6e0ef4577c05cbda`. V10+confirmed reload/envguard bytes 그대로.
- E4B digest `ef0a580aca375aa9bf4547558b9b41910e5f85769b5ad3e9e99ee13af71a1025`, ctx8192/concurrency1, native tokenizer/offline cl100k 로딩, 모델 inference0. tokenizer manifest `977b9500b210baff760dfa4c380bc4d3bc59281eedc312156dd2ac70841360c7`.
- local/LAN health/legal/features/notices200, guest auth401(정상), OPTIONS200 및 credentialed CORS **12/12=100%**.
- fresh GET-only 실제 Edge **2/2=100%**: 법적문서200·guest401·notices200, 동의폼 표시, 연결실패 배너 없음. 새guest발급/동의/접수POST0. 기존 owned registered guest GET/reload 별도 성공.
- 웹2/2 buildID 일치, 각각 served script21개 전부 disk/HTTP byte일치, 기존 pinned chunk SHA256 일치. 다른기기 LAN 수락과 전체업무완료를 뜻하지 않습니다.

## 동시 소실 원인: 확인된 것과 미확정
OS boot는 이번 소실보다 오래됐으며 최근4시간 System41/1074/6005/6006/6008/42 조회결과0. Application1001은12:32:37.984 HermesBundled `MoAppHang`을 기록합니다. DB 마지막 checkpoint12:27, 새start interrupted, 정상이전 shutdown 로그 없음. DB/API 과거 handle 부재와 새웹 handoff후 생존을 확인했습니다. 기존handoff는 실제 transfer 기록이지 앱종료 뒤 생존보장이 아닙니다. active profile logs에서12:30대 shutdown/cleanup/termination 해당기록은 찾지 못했습니다. **Hermes hang이 전부를 죽였다는 직접 종료감사/exit-code 증거가 없어 인과관계는 미확정**이며 호스트재부팅으로 설명하지 않습니다. 자동서비스/스케줄러 등록은 하지 않았습니다.

## 변경·다음 checkpoint
제품/공유starter patch0, schema변경0, 외부paid/raw/실알림0. 무분별 stale 자동삭제를 추가하지 않았습니다. 수동 증명+privatebackup+rename+정본start 절차만 실행했습니다. 현재 test1 DB metadata는 review/revision2, 이전 dining running/deadline 기록의 fresh normal GET은 다음 owner가 본인시험guest에서 수행해야 합니다(이 GET은 deadline 상태저장을 일으킬 수 있음). worker 자동재생·사용자원고 재접수 금지. 기존 test1 REPORT_KO.md의 DB복구뒤 큐대로 질문/명시 시험답변 →월요일창덕궁 실제대안/시나리오선택 →revalidate →UI확정/등록가능성 →DB/reload를 진행하십시오. 무료 외부조회도 현 egress거부 유지, 추가 승인 없이 넓히지 않습니다.

요청된 REPORT_KO.json은 원래 부재했습니다. REPORT_KO.md와 HANDOFF.json은 정확히 읽었고, 기존HANDOFF backup후 recovery 상태만 보충했습니다. JSON 신규 파일과 이 보고서는 현재 실행증거이며 이전test1 완료를 소급 주장하지 않습니다.

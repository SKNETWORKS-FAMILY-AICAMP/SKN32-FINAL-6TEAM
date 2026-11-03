# 축제 통제 알림 누락·실행 환경 복구

2026-10-18 11:35~11:43 KST 실제 축제로 이동 중인데 통제 알림이 없다는 사용자 요청으로 우선순위를 변경했다. 구청 공식 공지(2026-10-06)에는 선사초교사거리~서원마을로터리 전면 통제, 서원마을→올림픽로108길 부분 통제와 강동02 우회가 있다. 홈 배너는 종료22:30, 상세 공지는22:00으로 달라 종료를 하나로 합치지 않는다. https://www.gangdong.go.kr/web/newportal/bbs/b_068/157782

첫 x600 관리 경로는 connection reset. 보조 경로의 Windows 관리 접속은 성공했으나 Ubuntu와 utility VM 진입이 Wsl/Service/0x80072746으로 실패했다. Windows 쪽 API8043/웹3300 읽기 검사도 실패했다. 오라클 같은 최근 고객 Case 검색은 해당 기록을 찾지 못했다. 이는 해당 검색 범위의 결과이며 다른 여행 존재 여부를 판정하지 않는다.

11:41 Windows 메모리 사용92%, 가용1777MiB. 정확한 채팅 모델만 ollama stop으로 정상 언로드했고 다른 모델·학습 프로세스를 종료하지 않았다. 직후에도 WSL 오류가 남았다. 메모리 압박은 관찰값이며 오류 원인 확정이 아니다.

11:43 Ubuntu 정상 terminate 성공, 정상 start는 같은 CreateInstance 오류로 실패. WSL 관리 서비스 정상 중지를 요청했고 STOP_PENDING이 이어져 강제 종료하지 않았다. 자료·볼륨·컨테이너 삭제/교체·Windows 재부팅은 하지 않았다. 지키미4개는 앞선 승인대로 꺼진 상태를 유지해야 한다.

코드 추가 결함: TripStore.due가 시작 시각이 현재보다 지난 일반 항목을 제외했다. 사용자 축제 항목은11:15 조회 당시10:55~12:35였으므로 실제 감시 당시의 동일 버전 여부를 재확인해야 한다. 감시 두 실행기는 원래 시작시각으로 사건을 조회했다. 현재 일정도 감시하고 현재시각으로 확인하도록 별도 격리 후보에 공유 계약을 먼저 적고3파일을 보완했다. 실제 고객 원인 확정·운영 반영·실제 알림 생성은 아직 미완료다.

## 12:23 KST 추가 확인 — Windows 재시작 금지·메모리 회수

- 사용자가 x600 컴퓨터가 꺼지면 다시 켜지지 않는 버그를 명시했다. Windows 종료·재시작은 금지한다. 정상 Windows 재시작 도우미의 도구 호출은 사용자 중단으로 실행되지 않았고 결과 로그가 생성되지 않았다. 도우미 원문을 백업한 뒤 실행 즉시 중단하도록 비활성화했다. 다른 도구/작업으로 재부팅을 대신 시도하지 않는다.
- E→F 보존 이동5/5·크기/SHA256대조21,643/21,643·E 추가4,388,061,184바이트 확보 완료. [실측·이동 범위](2026-10-18_x600-e-to-f-preserved-move.md).
- Windows Resource-Exhaustion-Detector2004를 직전1시간 범위에서 필터로 조회해6건 확보했다. 11:11~11:35 KST 두 모델 실행 프로세스가 각각 최대13,351,563,264/12,451,160,064바이트와 WSL가상환경 최대6,245,023,744바이트의 가상메모리를 사용한 기록이다. 다른 사용자 작업이 원인이라고 단정하지 않는다. [원문 증거](../../../scratch/chat-model-20261018/x600-recovery-blocker-20261018-120750.jsonl).
- 12:14 Windows 자체 Ollama의 기존 학습 모델 `tripilot-pointer:e4b-ft`, 문맥8192, 30분 유지로 실제 생성 HTTP200·done·응답 `서울`을 확인했다. 이는 모델 단독 생성이며 구구루트 고객 요청 성공을 뜻하지 않는다. 당시 가상메모리 여유가 약0.75GB까지 줄어 추가 누적 원인을 확인했다.
- 12:20 기존 모델 실행 프로세스2개가 3일 전 종료된 이전 부모에서 남았고 TCP연결은 LISTEN만,3초간CPU사용변화0인 것을 확인했다. 현재 모델 실행 프로세스는 새 Ollama의 자식이며 별도 신원이다. 이전2개만 정확한PID·생성시각·모델지문·부모부재·연결/CPU재확인 후 종료했다. 이후 가상메모리 여유814,641,152→13,236,477,952바이트, 현재모델생성 HTTP200·`서울` 유지. 파일/학습자료/다른실행부모는 변경하지 않았다. [소유·연결 확인](../../../scratch/chat-model-20261018/x600-runner-ownership-20261018-122025.jsonl) · [실제 회수·현재모델 검증](../../../scratch/chat-model-20261018/x600-orphan-model-reclaim-20261018-122054.jsonl).
- 가상 환경 정상 terminate·서비스 정상stop은 완료/시작대기에서 멈췄다. 정확한 WslService/vmcompute 제어 프로세스만 종료 후 WslService는RUNNING, vmcompute는START_PENDING이다. 기존 단일 vmwp 정확PID 종료 요청은 'no running instance'로 실패했다. GetExitCodeProcess1067이나 WaitForSingleObject(0)는258이므로 종료 완료를 확정하지 않는다. HCSdiag exactGUID종료도20초시간초과. VMMS재시작 도우미는 이 종료완료검사에서 중단되어 실제서비스변경을 안 했다. 컴퓨터재부팅·VHD삭제/수리/축소·컨테이너/볼륨교체는 미실행이다. 가상메모리회수 뒤에도 cs앱복구는 미완료다.
- 진행 중 일정 감시 보완은 별도 격리 후보의 계약·3소스·새11단위시험과 기존9시험 합계20/20통과다. 아직 x600 운영 반영/실제 고객 알림 전달은 하지 못했다. [단위시험 원문](../../../scratch/traffic-alert-20261018/ongoing-watch-unit-v3.xml).
- 사용자가 AWS개선배포와 x600복구의 병렬 진행을 명시 승인했다. AWS담당은 기존 EKS앱6/6가용·health200, 현재고객여행0건·해당축제Case0건을 확인했다. AWS를 x600와 같은 고객DB로 취급하지 않으며 고객주소를 임의전환하지 않는다. 미완성 시간/근처검색의미 후보는 배포에서 제외한다.

남은 일: Windows를 유지한 가상환경 복구, AWS 기존소스에 검증패치 보존배포, 실제 고객여행 연속성/통제알림 확인. 지키미전용4개는 새기동 시에도 중단 상태를 유지하고 공용접속프로그램은 보존한다.

## 12:52 KST — UTIC에서 축제 도로통제 실제 원문 확인

- AWS 복구용 경유 조회에서 12:52:48 KST 새 응답134건을 받았다. 기존12:43의129건 수신 결과를 최신 건수로 덮어쓰지 않는다. 조회7.77초, misses는 빈 객체였다. 이는 API 제공처 할당량 초과를 나타내는 응답이 아니다.
- 사건 `L93174333790`의 원문에는 제31회 강동선사문화축제가 정확히 포함돼 있다. 올림픽로 선사초교사거리~서원마을입구, 양방향 전체차로 전면통제다. 원문 오늘 통제시각은09:00~23:00, 사건 전체기간은10/16 13:00~10/18 23:00이다. 구청 상세 공지22:00·홈 배너22:30과 UTIC23:00의 차이는 보존하고 임의로 하나로 합치지 않는다.
- 축제장 기준 약517.2m이고 반경1,000m의 현재 유효한 전체차로 통제1건으로 어댑터가 반환했다. 가까운 사건이라는 이유만으로 축제라고 단정한 것이 아니라 원문의 정확한 축제명·유효기간·구간까지 대조했다. 다른 강동 사고/공사·타지역 선사/서원 검색결과는 분리했다.
- [실제 원문·분류·조회시각](../../../scratch/aws-app-recovery-20261018/festival-utic-now-20261018-125237.json). 복구용 조회 성공은 운영 설정 반영·고객 감시·외부 알림 도착의 증거가 아니다. AWS 운영 앱의 경유 설정/시간 제한·새 API/웹 반영과 합성 고객 경로를 검증 중이며, 기존 x600 고객 여행 DB에는 아직 접근하지 못했다.

## 12:56 KST — 가상환경 후속 확인과 확인 범위 정정

- 12:23 이후 VMMS 서비스 정상 중지·시작을 실제1회 완료했으나 가상환경 진입은 복구되지 않았다. 새 compute 제어 프로세스가 시작 대기 상태이며, 대기 체인은 기존 VM 실행 프로세스와의 ALPC 통신을 가리켰다. Windows 전체는 종료·재시작하지 않았다.
- 기존 VM 프로세스의 종료 코드1067과 WaitForSingleObject(0)=258이 함께 관찰돼 종료 정리가 끝났다고 단정하지 않는다. HCS 직접 열기 작업은10초 내 반환하지 않아 종료 요청 단계까지 도달하지 못했다. VMMS의 정확한 VM 식별자 조회 두 경로에서도 WSL VM을 관리 가능한 객체로 찾지 못했다. 이것이 다른 미확인 복구 방법의 부재를 증명하지는 않는다.
- [HCS·대기 체인](../../../scratch/chat-model-20261018/x600-wct-hcs-20261018-122743.jsonl) · [정확한 VM 스레드 상태](../../../scratch/chat-model-20261018/x600-vm-worker-waits-v2-20261018-123311.jsonl) · [VMMS 조회](../../../scratch/chat-model-20261018/x600-vmms-exact-registration-20261018-123454.jsonl).
- 이전 기록의 웹3300·/qa-account 확인은 관리자 화면이며 고객 웹 화면 확인으로 확대하지 않는다. 고객 웹과 관리자 웹, 모델 단독 생성과 고객 요청 성공을 구분한다.

남은 일: AWS 새 API/worker/웹 실제 반영·교통 감시에서 고객 알림까지 확인, 기존 고객 여행의 연속성 확보, Windows를 유지한 x600 가상환경 복구. 오라클 서버는 별도 작업 담당이 새 API 병행 기동 방식을 구현 중이므로 Caddy·배포 제어를 동시에 덮어쓰지 않는다.

## 13:06 KST — 현재 상태 재조회·명령 완료 표현 정정

- 12:56의 VMMS 정상 중지·시작 ‘완료’는 명령이 오류 없이 접수됐다는 범위였다. 12:23 원문 시작 결과도 START_PENDING이며, RUNNING 상태 완료가 확인됐다는 의미로 확대하지 않는다. [명령·상태 원문](../../../scratch/chat-model-20261018/x600-vmms-v2-no-windows-restart-20261018-122335.jsonl).
- 12:58 재조회에서 WslService는RUNNING, compute는START_PENDING, VMMS는STOPPED였다. 기존 VM의 WaitForSingleObject(0)=258도 유지됐다. Windows 부팅 시각은 이전과 동일하고 고객 API8043·고객웹13000은2/2 응답하지 않았다. Windows 종료·재시작은 하지 않았다.
- 같은 조회에서 학습 모델 `tripilot-pointer:e4b-ft`의 2토큰 상한 시험은 HTTP200/done이나 본문이 비었다. 이전 성공 조건과 같은16토큰 상한으로 재검사한 실제 응답은 HTTP200/done·서울·생성2토큰이었다. 실패·불충분 시험을 숨기지 않으며 모델 단독 생성과 고객 앱 복구를 구분한다. [2토큰 시험](../../../scratch/chat-model-20261018/x600-current-model-guest-20261018-125813.jsonl) · [실제 본문 재확인](../../../scratch/chat-model-20261018/x600-current-model-guest-20261018-125832.jsonl).
- 사용자 직접 지시로 오라클 작업 「오라클 서버 우천 알림 점검」에 UTIC 실제 원문·진행중 감시3파일·의미후보17파일/351시험·접속유지 계약을 전달했고 전달 도구 성공을 확인했다. 후속 읽기에서 해당 담당이 최종 manifest·검증보고·접속유지 계약을 읽는 것도 확인했다. Caddy2.6.2 지원·인증/DB 동일성·이전 정적파일·worker단독 인계·연결유지 시간 차이 검토9항목도 추가 전달했다. 오라클 운영 설정은 이 작업에서 동시에 바꾸지 않았다.
- AWS 새이미지는 실제 canary에서17/17해시·jsonschema4.26.0·새공지판/인증제공처/생존3응답을 확인했고, 같은4.26런타임 의미343/343을 통과했다. 첫 원격 수집은 시험 보조파일3개 누락으로 실패했고 보조파일 보완 뒤 통과했다. 전체 통합425/425·실제합성해석2/2도 통과했다. canary는 복원DB만 사용했으며 운영DB·고객여행변경으로 확대하지 않는다.
- 추가 잠재 누락: 일반 감시의 자료일부실패 분기에서 이미 확인된 disruptions가 사실안내에 포함되지 않는다. 실제6종 보고서를 대조 중이고, 별도 격리 후보에서 기존 일정변경 보류를 유지하며 알려진 사실만 중복 없이 안내하는 최소수정·회귀를 검토하도록 분담했다. 오라클 담당에게도 전달했다. 아직 운영환경 실제 조건 재현·수정반영 완료로 보고하지 않는다.

## 13:23 KST — AWS 공개 앱 v2 반영·자료 연결·접속 유지

- API와 worker2/2는 새 이미지로 실제 교체했고 통합17파일을각각확인해34/34해시가일치했다. jsonschema4.26실제설치·공공키·Google소유키·UTIC경유/20초·모델API대체와기존상한이실기동에존재한다. worker는기존Recreate전략으로동시실행을피했다. [교체 증거](../../../scratch/aws-app-recovery-20261018/api-v2-rollout-result.json).
- 운영DB추가SQL10파일을1트랜잭션으로적용했다. 적용전후고객1·여행0·문의0·장소카탈로그6138·고객지문동일,기존이력SQL바이트덮어쓰기0이다. 실제백업을별도DB에복원한뒤적용/재적용·신판실제DB8/8을먼저검증했다. [운영DB 적용·지문](../../../scratch/aws-app-recovery-20261018/operational-sql-v2-20261018-130657.json).
- 영구키/경유설정반영뒤13:10실제외부점검은8.42초,6분류응답모두ok·failed/not_connected빈목록이었다. 기상특보·지진·실측대기를포함하고서울강풍주의보와축제전면통제1건을함께보존했다. 교통소스중ITS는여전히부분실패이며UTIC확인과모든교통소스완료를동일시하지않는다. [실제6분류 자료](../../../scratch/aws-app-recovery-20261018/operational-disruption-20261018-131026.json).
- 새고객웹도실제반영했다. 최초공개6경로중2건502,준비/종료보호도입중84요청중1건502를기록했다. edge의연결거부와보호없는이전Pod종료시각을대조했고HTTP준비검사·최소준비대기·종료전5초대기를추가했다. 보호가이미있는Pod를다시교체하는필요검증은31/31성공,최종직접6/6·공개18/18·추가edge오류0·재시작/OOM0이다. root독립13:12공개8/8도별도기록이다. 최초실패는성공으로다시쓰지않는다. [웹 인계](../../../scratch/aws-web-recovery-20261018/WEB_HANDOFF.md) · [최종 증거](../../../scratch/aws-web-recovery-20261018/web-final-health-proof.json).
- 복원DB사전검증뒤사실자료만운영에1트랜잭션추가했다. 식당1228곳·영업규칙8540·구간11546,활동1484곳이다. 활동원본1507중필수분류미확정23은원본을보존하고적재보류했다. 첫복원시험은필수분류누락으로전체롤백됐고출처ID로기존카탈로그와대조해보완후재검증했다. 사진/소개글/Oracle고객자료·문의/알림로그이전0,기존AWS고객1·여행0·카탈로그6138지문은유지했다.
- 실제근처검색검증에서식당1228곳만으로는축제장기준3km안후보가0이었다. 식당수신/적재만으로사용자요청이해결됐다고하지않는다. 최신정본자료/기존공공근처조회경로의증분보완을별도읽기조사중이다. 특정축제식당목록을제품코드에넣지않는다.

## 13:23 KST — 추가 통지 결함 검증 완료·독립 검토 승인

다른자료실패시에확인한통제사실이누락되는분기는운영기본CaseWatch의3구현파일로최소보완했다. 단위93/93(신규22포함)·실제분리Postgres6/6·ruffF/E9통과,기존의미후보17/17해시유지다. fatal자동변경보류와게스트/고정/예약·동의경계는보존하면서확인사건·출처·확인시각/일부조회실패/기존일정유지를함께안내한다. 조회시각·거리·목록순서만바뀐경우중복0,새사건·유효기간/실패상태변경은새안내를허용한다. 식당추가조회예외에도유효6종보고를유지하고계약실패/항목간사건혼입/실패정보안전사건승격을막았다.

루트는3파일전체diff·계약·manifest를독립검토한뒤AWS추가반영을승인하고Oracle담당에도최종검증본을전달했다. 이시각추가패치운영반영은진행중이다. [최종후보·해시](../../../scratch/partial-traffic-notice-20261018/source/final_project_cs/_local_checks/partial-notice-manifest-v2.json) · [검증/한계](../../../scratch/partial-traffic-notice-20261018/source/final_project_cs/wiki/records/reports/2026-10-18_partial-source-notice-repair.md). 수동 --only trip/replay의별도TripWatcher는같은fatal사실안내보완이남아있으며기본운영완료와구분한다.

남은고객경로: Google실제인증응답은주소불일치오류이며정상로그인완료가아니다. 기존Google클라이언트에공개로그인콜백주소1개추가가필요해사용자에게정확한값과공식설정경로를안내하고응답을기다린다. 응답없음을등록/승인으로간주하지않는다. QA계정은게스트감시제외경계를유지한다. 원래x600고객여행/알림프로필은AWS로이전하지않았고실제개인고객통제알림수신은미확인이다. x600 Windows는유지·모델단독생성성공·WSL/고객API복구미완료다.

## 13:40 KST — 사용자 범위 변경: x600 가상환경·고객 앱 복구에 집중

사용자가 AWS 추가 작업은 하지 말고 x600 복구에 집중하라고 명시했다. AWS 담당을 즉시 중단시키고 추가 이미지 게시·자료층 게시·시험·배포·자원 변경 취소를 전달했다. 이미 운영 중인 AWS 앱은 그대로 보존하며 종료하거나 되돌리지 않는다. 가상환경 담당은 x600 진단으로 복귀했고 다른 담당은 Microsoft 공식 제어 경로만 읽기 검토한다. Windows 종료·재시작, 원본 가상 디스크 수정·분리·수리·축소는 하지 않는다.

- 새 직접 증거: Hyper-V Worker 관리 로그18590의 원래 VM 식별자가 기존 정지 VM과 일치한다. 11:38:42 KST에 기록된 게스트 출력에는 가상 저장장치 읽기 실패, journald 중단, CPU Machine Check/Processor Context Corrupt와 `Kernel panic - not syncing: Fatal local machine check`, 이어 VMBus 종료 대기가 남아 있다. 이 게스트 중단은 확인했지만 물리 부품 고장이나 특정 세션이 원인이라고 단정하지 않는다.
- VHDMP 운영 로그11은 11:16:11 KST에 가상 디스크 Flush가 `0xC000009A`로 실패해 surface가 invalidated/unsurfaced 된 사실을 기록한다. 이전 자원 부족 기록과 시간대가 겹친다. 자원 부족→디스크 실패→패닉의 인과관계 전체를 검증한 것은 아니다. 기존 메모리 회수 이후에도 종료 정리가 끝나지 않는 이유를 이 사건 중심으로 좁힌다.
- 최근3시간의 선택한 로그를 모두 수집해 System 필터 결과12,431건 중 교정된 PCIe WHEA17은12,425건, 자원 부족2004는6건이었다. 교정된 오류 건수만으로 영구 부품 고장이나 중단 원인을 확정하지 않는다. VID 로그는 해당 시간·수준 필터에서 일치 이벤트를 찾지 못한 범위다. [수집 원문](../../../scratch/chat-model-20261018/x600-storage-worker-events-20261018-133900.jsonl).
- x600 Windows 부팅 시각은 이전과 동일하다. 모델은 유휴 언로드 후 25초 제한을 넘겼으나 별도 실제 요청에서 37.34초(적재37.00초)에 정상 생성했고, 후속 동일 질문은0.95초 HTTP200·서울이었다. 현재 세션의 모델 유지값은 `keep_alive=-1`이며 예약·자동화 생성이 아니다. [재적재](../../../scratch/chat-model-20261018/x600-idle-model-recovery-20261018-133153.jsonl) · [후속 생성](../../../scratch/chat-model-20261018/x600-warm-model-confirm-20261018-133321.jsonl). 모델 성공을 고객 앱 복구로 확대하지 않는다.

## 13:40 KST — 앞선 AWS 검증 범위 정정·중단 시점 인계

- 13:23의 축제3km 후보0건은 `record_status=active`만 조회한 진단 필터 결과였다. 실제 추천은 closed만 제외하므로 같은 원본에서3km13곳 중 폐업1곳을 제외한12곳이 있었다. 미확정 상태는 오늘 영업 확인을 뜻하지 않는다. 이 오진을 이유로 추가 자료를 적재하지 않았다.
- 실제 추가 결함은 첫 근처 조회가700m, 최종 후보 단계가 최대3km라서805m 식당이 초기 조회에서 빠지는 범위 불일치였다. 별도1구현파일 후보의 관련 단위96·분리DB2=98/98을 통과했고 기존 단계별 거리·영업·이동·동시변경 검증을 유지했다. Oracle 담당에 최종 파일·해시를 전달했다. AWS 추가 배포는 최신 사용자 지시로 중단하며 완료라고 쓰지 않는다.
- 일부 자료 실패 시 확인한 통제 사실을 보존하는3파일 보완은 AWS v3 API/worker에 반영된 상태다. 합계506/506 시험·실행파일40/40 해시 일치. 실제 UTIC 통제+기상특보와 예보 실패 조건을 복원DB 합성 여행에 적용한 시험에서 안내1회/다음 회차0회, Case0·일정/버전 불변이었다. 운영 고객 쓰기·외부 발송0이다. [합성 실제 어댑터 증거](../../../scratch/aws-app-recovery-20261018/adapter-watch-fault-20261018-133443.jsonl).

남은 최우선은 Windows를 유지한 x600 가상환경 복구, 기존 고객 DB·컨테이너 재기동, 실제 고객 앱과 모델/API 대체·통제 알림 확인이다. 지키미 전용4개는 재기동하지 않는다. 실제 개인 고객 알림 수신은 아직 미확인이다.

## 13:53 KST — x600 추가 복구 실행 결과와 미완료 범위

최신 사용자 지시대로 AWS 추가 게시·시험·배포는 중단했다. 마지막 원격 시험은 이미 종료됐고 신규 실행 중 작업은 없다는 담당 인계를 받았다. 기존 AWS 운영 앱은 종료/롤백하지 않았다. 이 기록은 AWS 재개 승인이나 예약 신호가 아니다.

### 직접 확인·실제 복구 시도

- 원래 VM의 마지막 실제 TID7676 하나를 native 조회와 psutil로 대조했다. 정확한 PID·생성시각·GUID, 프로세스 종료코드1067/Wait258, 유일 TID·GetExitCodeThread259/Wait258·I/O pending을 확인했다. GetThreadIOPendingFlag TRUE는 입출력 존재만 뜻하며 디스크·동기·취소 가능 여부까지 증명하지 않는다. 앞선 중간 보고의 ‘디스크 작업’은 범위를 넓힌 표현이어서 입출력 대기로 정정한다.
- 공식 CancelSynchronousIo를 그 TID에 정확1회 실행했다. FALSE/ERROR_NOT_FOUND1168, 후속10개 표본 모두 thread/process Wait258·pending TRUE로 종료 정리 미완료였다. 이 결과는 현재 취소할 수 있는 동기 I/O 요청을 찾지 못한 범위이며 모든 비동기/커널 복구 수단의 부재를 증명하지 않는다. 반복 호출0, 다른 스레드 취소0, 대상 핸들 강제 닫기0이다. 실제 로그는 [single-cancel-20261018-134200.jsonl](../../../scratch/x600-wsl-io-recovery-20261018/single-cancel-20261018-134200.jsonl) 하나다. 담당 회신의134534는 파일명 오기이며 파일 존재·추가 호출을 뜻하지 않는다.
- 마지막 기록된 사용자 시스템 호출은 NtClose(0xc9c)였다. 현재 커널 스택을 읽지 않았으므로 NtClose 내부와 이후 프로세스 종료 정리 중 어디서 기다리는지는 구분하지 못한다. 현재685핸들표에서0xc9c를 찾지 못했다. PSS685/685와 native 타입분류73종/685개 대조를 했으나 사라진 핸들의 객체 유형은 복원하지 못했다. 남은 File36·ALPC9·I/O completion8 등의 분포로 VHD/VID/GPU 원인을 단정하지 않는다. [추가 진단·실행 범위](../../../scratch/x600-wsl-io-recovery-20261018/WORK_REPORT.md).
- 일반 파일 읽기 전용으로 원본 가상 디스크의 식별8바이트와 두 헤더4,096바이트씩만 읽었다(8,200바이트). 가상 디스크 열기/attach/분리/수리 API는 호출하지 않았다. 두 헤더의 CRC32C2/2가 유효하고 sequence605가 선택되며 active LogGUID가 남아 있다. 크기249,636,585,472바이트·mtime은 읽기 전후 동일했다. 전체 디스크 해시·ext4·PostgreSQL·고객 여행 무결성을 확인한 것은 아니다. [헤더 읽기 결과](../../../scratch/chat-model-20261018/x600-readonly-vhdx-headers-20261018-135129.jsonl).
- 13:52:38 KST 재확인에서 Windows 부팅 시각 동일, WslService RUNNING·vmcompute START_PENDING·VMMS STOPPED·기존 VM Wait258이었다. 고객 API8043/고객 웹13000은2/2 응답하지 않았다. 학습 모델은 keep_alive=-1로 실제 HTTP200/done·서울·0.95초를 다시 확인했다. [최신 상태](../../../scratch/chat-model-20261018/x600-recovery-checkpoint-20261018-135235.jsonl).

### 실행하지 않은 수단·제외 이유

- Windows 종료/재시작·가상화 기능 해제/재설치·커널/그래픽/저장장치 드라이버 리셋: 사용자 Windows 유지 조건과 위험 범위 때문에 실행하지 않는다. 재시작 승인을 다시 요청하거나 우회 명령으로 대신하지 않는다.
- HCS 추가 취소는 문서상 E_NOTIMPL, 외부 프로세스 CancelIoEx는 대상 VM 발행 I/O 취소를 보장하지 않으며 ALPC용 RPC/COM 취소도 적용 조건을 충족하지 못해 실행하지 않았다. HCS Crash는 이미 중단된 게스트에 NMI를 보내는 기능이고 기존 핸들 열기부터 멈췄으므로 새 안전 제거 경로로 채택하지 않았다.
- VSS 시점 고정+VHDX 컨테이너 바이트 아래 새 qcow2+QEMU TCG 임시 기동은 공개 코드상 구조 가능성을 확인했으나 채택 조건이 미검증이다. E 기존 snapshot/association 조회는 각각0건이었고 새 snapshot·다운로드·QEMU 기동은0회다. VSS 자체가 원본 볼륨 flush/freeze를 수행하므로 현재 I/O 정리 상태와 무관하다고 보장할 수 없다. Crash-consistent snapshot은 게스트 DB 무결성을 보장하지 않으며 dirty 로그 재생/확장·원래 worker 재개 차단·사용자 로그인/알림 경로도 검증해야 한다. 가용 물리 약4.1GB에서 guest RAM3GB 외 QEMU/TCG/호스트 여유까지 안전하다는 실측도 없다. [독립 검토·채택 조건](../../../scratch/x600-wsl-io-recovery-20261018/VSS_COW_REVIEW.md). 임시 기동이 성공해도 원 WSL 복구와 구분해야 한다.
- 네이티브 PostgreSQL 프로세스 존재는 확인했으나 암호 없는 읽기 연결은 실패했다. 기존 제한된 백업 폴더 깊이3 검색에서 구구루트 고객 DB 덤프를 찾지 못했다. 이 범위가 전체 기계의 백업 부재를 뜻하지 않는다. 다른 프로젝트 자료로 고객 DB를 교체하거나 접근 우회하지 않았다.

현재 결론: 원래 x600 가상환경과 고객 앱은 미복구다. 확인한 공개 사용자모드 제어 방법들로는 Windows 유지 조건에서 종료 정리를 해제하는 검증된 수단을 아직 확보하지 못했다. 원본 가상 디스크 수정/삭제·고객 DB 교체·Windows 재시작은 하지 않았다. 다음 복구 담당은 위 실패·경계·원문을 보존해 새로운 안전 경로를 검증해야 하며, 이 기록을 실행 승인·완료·자동 재시도 신호로 쓰지 않는다.

## 14:05 KST — 원본 미사용 기동 예비검증으로 계속 진행

13:53 체크포인트는 복구 완료나 작업 취소가 아니다. Windows 유지 조건에서 별도 기동 가능성을 작은 새 시험 디스크로 먼저 검증하도록 이어갔다. [단계별 보호 계약](../../delivery/x600-preserved-boot-recovery.md)을 실제 시험 전에 작성했다. 실제 고객 디스크의 로그 재생·snapshot·VM 기동은 아직0이다.

- 원본 로그1MiB의 읽기 검사에서 현재 헤더와 GUID가 맞고 CRC가 유효한 entry103개를 찾았다. sequence는 연속이며 descriptor153개의 sequence도 일치했고 쓰기 대상 offset은 파일 범위 안이었다. 이것은 구조 검사이며 실제 재생·파일시스템·DB 복구 성공이 아니다. 헤더·크기·mtime은 읽기 전후 동일, 원본 쓰기0. [읽기 결과](../../../scratch/chat-model-20261018/x600-readonly-log-metadata-20261018-135502.jsonl).
- 원본 형식 metadata는 두 region table CRC가 유효하고 동일했다. dynamic/no-parent·virtual1TiB·block1MiB·logical512/physical4096이다. QEMU 형식 제약 대조용 읽기이며 전체 디스크 정상 판정이 아니다. [형식 읽기](../../../scratch/chat-model-20261018/x600-readonly-format-metadata-20261018-135602.jsonl).
- 설치된 커널 자체의 내장 설정을 추출해 virtio-SCSI·PCI·SCSI disk·ext4·devtmpfs·serial·ELF 등의 필수10항목이 built-in임을 확인했다. virtio-blk는 모듈이므로 직접기동 대상으로 쓰지 않는다. 커널 SHA를 보존했다. [커널 검증·한계](../../../scratch/x600-wsl-io-recovery-20261018/KERNEL_BOOT_GATE.md).
- 공식 공개 Alpine3.24.2 최소 Linux의 SHA512와 설치 커널 SHA를 대조하고, 새 initramfs3.7MB·새 synthetic16MiB 디스크를 격리 폴더에 만들었다. 네트워크·Docker·systemd를 시작하지 않고 장치/크기/시험값 해시를 출력한 뒤 게스트만 종료하는 초기 셸이다. 첫 스크립트는 로컬 구문 오류로 실행 전 실패했고 원문 백업 후 고쳤다. 실제 새 VM 실행0이며 고객 자료를 이 준비물에 넣지 않았다. [준비 증거](../../../scratch/chat-model-20261018/x600-synthetic-boot-bundle-20261018-140146.jsonl).
- 기존 AMD 제공 압축 도구의 서명과 현재 보안 기능 활성 상태를 확인했다. QEMU 공식 연결 배포 파일은 원격 직접 다운로드가 구간 제한으로 실패해 partial을 보존했다. 이 PC 메모리 중계 다운로드·도착 SHA 대조로 전환 중이다. 로컬 C: 디스크에 대형 설치 파일을 저장하지 않고 새 x600 F: 폴더만 사용한다. 아직 QEMU 실행·설치 프로그램 실행0.
- VSS 관련 CIM 클래스와 Create 메서드는 실제 조회했으나 실행 지원/생성 성공은 미확인이다. 첫 메서드 열거는 컬렉션 Keys 조회 오류로 null이어서 올바른 열거로 재확인했다. E/F 파일시스템은 NTFS, E여유5.89GB/F여유10.95GB이며 기존 shadow/association은 앞선 해당 볼륨 명령 범위에서0건이다. 새 snapshot·저장소 연결 생성0, VSS 서비스 기동0.

다음: 소형 중첩 COW 쓰기/확장 및 합성 dirty 로그 격리 시험, 고객 디스크 없는 최소 TCG Linux 부팅을 실제 검증한다. 이를 통과해도 실제 데이터 사본·원래 worker 재개 차단·고객 앱 공개는 별도 단계다.


## 14:24 KST — x600 실제 소형 기동·변경 분리 시험 통과

- 공식 QEMU Windows 배포 전체 SHA512 일치, 실제 서명 만료와 공식 유지관리자 알려진 문제·현재 보안 검사 결과를 기록했다. 설치 프로그램은 실행하지 않고 필요한 파일만 새 폴더에 추출했다. 시스템 시각/인증서/보안 정책 변경0이다. [검토 경계](../../delivery/x600-preserved-boot-recovery.md).
- 새 시험 디스크의 정상 중첩 읽기/쓰기/확장6/6, 단일 유효 CRC 합성 dirty 로그 재생10/10을 통과했다. 원본 시험 파일의 전체 SHA·크기·mtime은 불변이다. 처음 fixture 형변환 오류는 QEMU 호출 전 실패이며 보존했다. 이 결과로 실제 원본의103개 로그·ext4·DB 복구를 확정하지 않는다.
- x600 Windows에서 설치 커널·공개 최소 Linux·새16MiB 시험 디스크만으로 QEMU TCG Linux 기동8/8 통과,11.603초·최대 RSS239,304,704바이트였다. 네트워크 없음·Docker/systemd 미시작·Windows 재시작0이며 기존 WSL 복구와 구분한다. [실제 기동 증거](../../../scratch/chat-model-20261018/x600-synthetic-linux-boot-20261018-141705.jsonl).
- 14:22 실제 관리자·NTFS·현재 자료 볼륨 기존 snapshot/연결0·보관 볼륨 여유10.58GB·물리 가용4.70GB를 확인했다. 다른 볼륨의 기존 snapshot1개/연결1개는 보존한다. 원본 크기/mtime은 동일, Windows 부팅 시각과 잔여 vmwp도 동일했다. [사전 조회 원문](../../../scratch/chat-model-20261018/x600-fixed-snapshot-preflight-20261018-142216.jsonl). 새 snapshot 생성은 아직0이며 다음은 계약의2GiB 제한 연결/단일 생성 시도다.

고객 자료 연결·DB 복구·고객 앱 공개는 아직0이다. AWS 추가 작업 중단, x600 Windows 유지·지키미 재기동 금지는 유지한다.


### 14:25 저장소 생성 첫 실패와 인자 정정

새 연결 Create1회는 반환10(Unknown error), 해당 볼륨 연결/snapshot 모두0이었다. 실행 인자의 볼륨 끝 구분자가 PowerShell에서 두 개로 전달되는 작성 실수를 확인했다. 첫 실패·스크립트·증거를 보존하고, 재조회한 실제 볼륨 DeviceID 문자열을 그대로 전달하는 새 단일 시도만 허용한다. 기존 연결 변경/삭제·상한 확대·snapshot 반복 생성은 허용하지 않는다. 저장소 연결0과 여유를 다시 확인한 뒤 진행한다. 직접 원본 VHD 쓰기0이다. [첫 시도](../../../scratch/chat-model-20261018/x600-limited-shadow-storage-20261018-142345.jsonl).


### 14:26 인자 의심 정정·같은 호출 재시도 보류

직전14:25 기록의 구분자 두 개 주장은 JSON 표시를 실제 문자열로 오독한 것이다. 독립 AST 계수에서 실제 Volume=[69,58,92]/DiffVolume=[70,58,92], 각각 길이3으로 정상 인자였다. 인자 실수라고 확정할 근거가 없으며 GUID로 같은 호출을 다시 하지 않았다. 반환10의 원인은 아직 미확정이다. Microsoft 문서의 해당 WMI 메서드 클라이언트 지원 표기는 None supported이며, 실제 Windows에서 지원되는 관리 명령·하위 오류를 별도로 검토한다. 원본 VHD 직접 쓰기/새 snapshot/다른 기존 연결 변경은0이다.


### 14:26:53 KST — 실측 저장소 위치·단일 사본 생성 조건

vssadmin 제한 명령은 exit2/지정 연결을 찾지 못했다고 답했다. 다만 바로 뒤 실제 조회에 자료 볼륨 자신을 보관 위치로 하는 최대2GiB 연결1개가 새로 나타났다(allocated/used0). 앞선 WMI 호출과 이 명령 중 어느 것이 생성했는지는 확정하지 않는다. 이 연결을 삭제하거나 보관 위치를 바꾸지 않고 보존한다. 다른 볼륨의 기존 snapshot ID/연결은 유지됐고 새 snapshot은0이다. 자료 볼륨 여유5.89GB에서 최대2GiB 차등영역을 사용하면 약3.74GB가 남는다. 해당 연결/상한/기존 source snapshot0·자료 볼륨 여유5GiB 이상·물리3GiB 이상·새 파일 보관 볼륨9GiB 이상을 직전 검증한 뒤 ClientAccessible snapshot Create1회만 진행한다. 실패/결과 불명 때 재호출하지 않는다. 모든 자료 원본 직접 쓰기 금지와 다른 snapshot 보존 경계는 유지한다. 앞 문단14:28 표기는 작성 중 시각 오기이며 실제 명령 증거14:25:56이 정본이다.


## 14:29:15 KST — 실제 고정 사본1회 생성·읽기 전용 검증

ClientAccessible Create1회가 반환0이었고 새 고유 snapshot1개가 State12/NoWriters/ClientAccessible/Persistent/NoAutoRelease로 확인됐다. 실제 volume API의 FILE_READ_ONLY_VOLUME도 확인했다. 차등 저장 위치는 자료 볼륨 자신·최대2GiB이며 실제 초기할당335,544,320바이트/사용2,293,760바이트였다. 자료 볼륨 여유5,557,977,088바이트·새 파일 보관 볼륨10,585,407,488바이트·물리 가용4,645,724,160바이트를 기록했다. 이 값은 해당 시각 실측이고 미래 잔량 보장이 아니다.

사본 파일249,636,585,472바이트의 식별/두 헤더8,200바이트를 읽었다. CRC2/2·sequence604/605·active 로그가 확인되고 크기/mtime은 읽기 전후 같았다. 원본 direct write/attach/분리/수리0, 고객 DB 검사0이다. snapshot은 crash-consistent로서 DB 일관성이나 전체 독립 백업을 보장하지 않는다. [생성 증거](../../../scratch/chat-model-20261018/x600-fixed-snapshot-create-20261018-142654.jsonl) · [고정 사본 읽기 검증](../../../scratch/chat-model-20261018/x600-fixed-source-verification-20261018-142805.jsonl).

Windows QEMU 기본 파일 읽기에서 일부 실패가0 채움으로 숨을 가능성을 발견해 직접 snapshot 파일 driver 연결은 채택하지 않았다. 고정 사본1개만 읽는 loopback 읽기 전용 NBD(디스크 읽기 전달) bridge의 명시 EIO/shortread 거절을 새 합성 자료로 먼저 검증 중이다. 별도 initramfs는 고객 코드 실행 없이 readonly block→ext4→ro,noload,nosuid,nodev,noexec 마운트만 하도록 새로 만들었다. 아직 실제 사본 QEMU 연결·로그 재생·DB 복구·고객 앱 공개0이다. 원래 WSL은 미복구이며 AWS 추가 작업 중단·Windows 유지·지키미 미기동 경계는 유지한다.


### 14:37:40 KST — 최초 연결 실패 보존·수정 검사 조건

첫 실제 사본 검사에서 새qcow2 생성만 성공했으며 VHDX를 열기 전 저장된 backing URI와 명시 server 옵션 충돌로 중단했다. bridge 실제 payload read0·원본 쓰기0·VM기동0이다. 실패 COW/로그를 보존했다. backing URI를 저장하지 않는 새 blankqcow2에 runtime 읽기 전용 backing만 지정하는 합성 회귀까지 포함해 bridge v2는11/11 통과했다. 최종 SHA2177b9c2225e8f4f6d00924f62a7d1edc1fbf4711a06e9995ea9dfbb64ae485b만 사용한다. 원문 경로의 사전 reparse 거절도 포함한다.

독립 코드 검토에서 수명 예산·bridge 종료 판정·ThreadPool 대기·비동기 디스크 열거 경합을 발견했다. 새 manager는 NBD 잔여 수명에서 guest timeout을 계산하고, 결과 누락/bridge 실패는 전체 실패, source 오류는 export 전체 종료로 처리한다. manager 자체도 새 전용 Job에 제한(자식 포함4개·프로세스별512MiB·145초)하며 그 안의 NBD/guest별 제한도 유지한다. 초기 셸의 디스크 대기는10초 상한으로 새 파일을 만들었다. COW는 read-only guest 전후 전체SHA를 대조한다. Windows 커널 상태 때문에 모든 종료가 즉시 완료된다고 보장하지는 않는다. 새로운 시도는 이전 COW를 덮어쓰지 않는 새 경로에서만 진행한다.


## 14:40:31 KST — 실제 사본 파일시스템 검사7/7 통과

고정 VSS를 읽기 전용 NBDv2로 전달하고, backing URI를 저장하지 않는 새qcow2에만 VHDX 로그를 재생했다. 두 COW 헤더CRC와 선택 헤더 activeLogGUID0을 확인했다. 원본 direct write/attach/분리/수리0이다. 새 COW실제 파일은1,441,792바이트이며 독립 전체 백업이 아니다.

네트워크 없는 실제 QEMU guest에서 readonly block·1TiB 가상 크기·ext4·ro,noload,nosuid,nodev,noexec 마운트·배포폴더 존재 등7/7 통과했다. 실제 guest4.668초·최대 RSS238,133,248바이트, manager7.256초·최대43,687,936바이트였다. bridge4접속/1,877읽기/오류0/원본쓰기핸들0으로 정상 종료했고 COW 전체SHA가 읽기 전용 부팅 전후 동일했다. 기존 고객 OS 코드/systemd/Docker는 실행하지 않았다.

Ubuntu26.04·고객 앱 배포폴더와Docker자료폴더 존재를 확인했으나 내부 고객 DB/WAL 일관성·여행 데이터·실제 앱은 미검증이다. 원래 WSL은 여전히 종료 정리 대기이며 이 성공은 그 VM 복구 완료가 아니다. [실제 실행 로그](../../../scratch/chat-model-20261018/x600-fixed-copy-inspection-20261018-143741.jsonl) · [원격 proof의 로컬 보존 사본](../../../scratch/chat-model-20261018/x600-actual-readonly-copy-proof-143744.json).

다음은 비밀값을 출력하지 않는 bounded metadata 수집으로 고객DB/컨테이너 저장위치를 확인하고 새 사본에서만 crash recovery를 검토한다. 실서비스를 사본에 연결하기 전 원래 WSL 외부 통신과 공개 대상 단일화, 고정 snapshot 수명 의존 해소 또는 명시적인 제한/실패중단 설계가 남아 있다.


## 15:00:52 KST — 사용자 승인 옛 이미지1개 삭제·고객 메타데이터 확보

사용자가 F의100GB넘는옛E복구백업이미지삭제를새로지시했다. 오래된정리메모와실제위치/크기/mtime/FileID/할당량을대조한정확1파일을독립검토뒤삭제했다. 기술적으로9/28이전WSL사본이며전체E볼륨이미지와는다르다. 현재E원본은noParent이고오늘고정사본과의연결도없음을구분했다. 전체옛이미지는다시백업하지않았으며262,144바이트헤더·메타데이터·삭제감사만보존했다.

정확한단독DELETE핸들에서최종경로/FileID/크기/mtime/link1/일반파일속성을재검증해1개파일만삭제했다. 재귀작업0, 실제회수125,125,525,504바이트·F여유10,557,603,840→135,683,129,344바이트다. 현재E원본249,636,585,472바이트와오늘읽기전용사본은이후에도존재했다. [원문감사](../../../scratch/chat-model-20261018/x600-user-approved-old-backup-deletion-20261018-145537.jsonl) · [독립범위검토](../../../scratch/x600-wsl-io-recovery-20261018/OLD_BACKUP_SCOPE_REVIEW.md).

고객메타데이터는새선별묶음으로실제8/8통과했다. 원격private archive11파일47,258바이트,Windows표준JSON으로정확고객4개/hostconfig4개·중복/누락0을확인했다. 고객DB는PostgreSQL17.11이며기존고객자료볼륨과API/web현재이미지3종을확인했다. Driver는overlayfs/OCI이미지스토어다. Env원문값/.env/base64본문은공유출력하지않았고tar파일시스템추출/고객코드실행0이다. [비밀값제외요약](../../../scratch/chat-model-20261018/x600-customer-metadata-summary-20261018-145557.jsonl).

새공간으로전체oldDockerdaemon을기동하는대신공개Alpine·Docker실행OS를새독립디스크에만준비하고,선택OCI이미지3종/고객DB/필수마운트를옮기는방향으로좁혔다. 기존Swarm/plugin/AutoRemove가동하는복구경로는채택하지않는다. 실제고객DBcrash recovery·고객앱기동·새독립환경성공은아직미확인이다. Windows재시작0·AWS추가작업중단·지키미기동0은유지한다.


## 15:08:10 KST — 독립 환경 설치·선택 자료 실측

- x600공개AlpineOS설치1/1완료(정상서명apk,29.4초,peakRSS580,173,824B). 최초독립부팅은기존devtmpfs중복마운트검사로실패했으며실패v1/로그를보존하고새v2에서검사코드만수정중이다. 고객기동성공으로보고하지않는다.
- 실제readonlyguest8/8,NBD2438읽기/오류0,COW불변. 선택이미지manifest3/index3SHA검증,44layer압축합725,470,887B. 실제고객자료du PG514,400KiB/이동224,216KiB/diagnostics24KiB/ops76KiB. configblob3/layer44전체검증과DBrecovery는아직안했다.
- 최초parser는DockerImage를configID로해석해KeyError였다. 실제파일종류가OCIindex임을확인해새parser로index→linuxamd64manifest연결을검증했다. 실패를보존했다. 읽기수집완료를이미지전체복구로간주하지않는다.
- Windows재시작0,AWS추가작업0,지키미기동0. 다음은독립OS완료→새target선택자료복사→source없는부팅→DB/API/web복구다. 고객app8043/web13000은직전실측2/2무응답,모델단독HTTP200/0.8초와구분한다.

근거: [추가사본검사](../../../scratch/chat-model-20261018/x600-fixed-copy-inspection-20261018-150533.jsonl), [선택자료실측](../../../scratch/chat-model-20261018/x600-image-data-private-summary-20261018-150702.jsonl). privatearchive/환경값은공유기록에전개하지않는다.


## 15:14:00 KST — 독립 OS 부팅 완료·복사 실행안 준비

- 새공개OSv2의기존source/NBD/NIC없는부팅8/8 통과.9.362초/peakRSS394,584,064B. 원래OS와다른새OS자료만으로부팅했다. Docker/고객자료기동은0.
- 공개Python은검증된새target사본에서RAM복사해JSON/SHA검사에사용한다. 원래고객Ubuntu코드실행은0. 새longNBD13/13 합성시험과새메모리/시간/용량guard자기검사1/1 통과. 고객자료실제복사는아직0.
- 원래WSL의중복고객통신을막기위한가역설정안을준비했으나아직적용0. 네트워크차단을로컬DB쓰기정지라고간주하지않는다. 실제DB복구·고객API/web·모델API대체·통제안내확인은남았다.

근거: [독립OS부팅](../../../scratch/x600-wsl-io-recovery-20261018/independent-os-v2-run-20261018-150731.private.jsonl), [준비실행안](../../../scratch/chat-model-20261018/run_x600_selected_copy_v1.py).


## 15:14:50 KST — 원래 WSL 고객 통신 차단 정책 반영

WSL creator 범위에 새 inbound/outbound AnyBlock priority1 규칙2개와 LoopbackEnabled=False 설정1개, 총3/3을 반영했다. PersistentStore/ActiveStore 두 곳의 정확 필드와 EnforcementStatus1을 확인했다. 기존 설정·규칙·프로필은 비공개 XML/JSON으로 직전 보존했고 일반 Windows 방화벽/기존 규칙/서비스/Windows 부팅 시각은 바꾸지 않았다.

WSL 포트가0개이므로 실제 패킷 차단은 확인하지 못했다. 로컬 DB 쓰기·AF_HYPERV/interop 차단도 아니며 기존 가상환경 완전 종료라고 보고하지 않는다. 기존 vmwp Wait258·vmcompute start_pending이 계속된다. 새 SSH 연결은 성공했고 Windows 모델 직접 HTTP200/done/서울,0.86초,keep_alive=-1을 확인했다. 고객 API/웹은2/2 무응답으로 남았다.

근거: [정책 반영](../../../scratch/chat-model-20261018/x600-wsl-fence-apply-20261018-151423.jsonl), [새 연결·모델·앱 재확인](../../../scratch/chat-model-20261018/x600-recovery-checkpoint-20261018-151430.jsonl). 복사 bundle 준비 중이며 실제 고객 자료 복사·독립 고객 DB 기동·공개 경로는 아직 확인하지 않았다.


## 15:21:01 KST — 실제 선택 복사 실행 전 검토 완료

부모가 공개RAM helper/init 전체를 읽었다. 최종 helper SHA7ad048b8b2debb4756712fc40e17f95032caf9f65b78438d6b93faff55b6e1a6, private bundle SHA f62af9096aa3d1e6da457496ed1dc4a3901909da1410a6f4a375772150983521이다. 합성 blob/경계시험12/12 통과했으나 Windows 토큰의 symlink 생성 권한 제한으로 실제 symlink 거절 시험은 하지 않았다. 실제 Linux cp-a의 UID/GID/mode 보존은 복사 결과에서 대조한다.

builder 첫 시도는 Compose service를 api/web/db라고 가정해 사전 AssertionError로 멈췄다. 실제 exactName과tripilot-api/web/db 라벨 두 조건으로 새 builder에서 정정했고 helper/init은 바꾸지 않았다. 원본/VSS/VM/새bundle쓰기 전 실패였으며 실패 로그를 보존했다.

실행안v3는 복사 전 stale abort flag가 있으면 새 디스크도 만들지 않고 거절하며, NBD 조기 종료는 새 guest 중단으로 전파한다. 독립 코드 검토4/4, 부모의 최종 실행안 SHA d1a353d15fc716ead09f7156cfa60c69349465f80a92394724ca906da1bc9da0를 확인했다. 상태·중단 소유 flag를 삭제해서 재시도하지 않는다. 다음은 검증된 새target 전체사본에만 실제 복사를1회 실행하는 단계이며 고객 Docker/DB/API/web 기동 성공으로 보고하지 않는다.


### 15:22:16 KST — 복사 첫 실행의 QEMU 인자 실패·새 실행안

첫 실행은 새target전체사본/새COW/VHDX로그재생까지만 성공했고 Linux를 부팅하기 전 QEMU가 source serial25자의 기본device_id겸용20자상한으로 exit1했다. stdout0·0.273초·원본쓰기0·NBD1194읽기/오류0이며 실패COW/target/proof를 보존했다. 실제고객자료복사 성공이 아니다.

현재 실행파일의 scsi-hd 도움말에서 device_id/serial 두 독립 인자 지원을 실제 확인했다. 새v4 실행안은 source serial을 그대로 유지하고 짧은 명시device_id를 추가한다. source VPD0x80을 읽는 bundle/helper는 동일 해시이며 source데이터경로/권한은 바꾸지 않는다. 이전 중단 flag가 있으면 재시도하지 않으며 새 세션/새target/COW에서만 다시 진행한다.

근거: [첫 실행](../../../scratch/chat-model-20261018/x600-selected-copy-20261018-152103.jsonl).


## 15:26:40 KST — 실제 고객 자료 선택 복사 성공

새 독립 target 사본으로 이미지3종의manifest/config/layer50blob과고객DB·이동자료·diagnostics·ops 정확4트리를 옮겼다. source/target SHA·size·mode/uid/gid·자료목록 전후 대조, 공개RAM runtime 출처 대조와privatemetadata복사를 통과했다. 부모 실행 proof10/10,150.224초,guestpeakRSS663,101,440B,NBD49,544읽기/오류0·fatal0·원본쓰기핸들false다. 새작업전체할당2,726,910,671B로8GiB예산안이다. 30초 snapshot감시와회차정상종료를확인했고guest/NBD는종료됐다.

이target을보존본으로두고다음runtime주입은별도새fullcopy/noBacking/전체streamingSHA대조후그새디스크에만쓴다. 원본/E/snapshot/기존OS/보존target은수정하지않는다. copy성공은PG WALrecovery·고객DB/앱기동·공개고객경로확인과다르다. 그부분은아직미확인이다.

근거: [실제복사10/10](../../../scratch/chat-model-20261018/x600-selected-copy-20261018-152217.jsonl).


## 15:43:03 KST — 실행 설정 주입 성공·종료 연동의 기동 전 수정

첫 독립 실행용디스크에 주입8/8·19.044초/peakRSS360,255,488B를 실제 통과했다. 원본/NBD/VSS/NIC 연결0·Docker기동0, 기존공개init/환경원문보존 및 새init/선택10파일대조를 확인했다. 이후 기동 전 독립검토에서 PID1의작업중stop요청거절·감독기의8초고정뒤QMP종료·관리콘솔로그계약불일치3건을찾았다. 이디스크/코드를보존하고아직지속실행QEMU는시작하지않았다.

새실행용v2디스크를다시고객자료보존본에서fullcopy했고1,783,365,632B/전체SHA6240686088c8d6b74133ff818dafc3a00e83051725313c4fbb82140ec9faa678가전후일치했다. 새fullcopyproof SHA d92e40cdbf9a7674e11213100e4da9a9cd030f66419a0d04d2fcc889f255af75→selected-copyproof2ced236c6d906103a3023aaf32dec97a5018c606d7812eff3f96de54e0cf5ea7 연결도확인했다.

수정감독기는소유중단때240초/자원비상때10초까지실제정상종료ACK를읽는다. ACK없음은정상종료완료로보고하지않고새guest강제중단·DBcrashrecovery필요가능성을private결과에남긴다. 원래Windows/WSL/모델을종료하지않는다. 관리자직렬출력은기록하지않는다. 새PID1은작업중중단을우선수락하고자기stage그룹만TERM/회수,소유DB/daemon종료확인뒤에만ACK를낸다. Python대역계약10/10은실제VM/DB종료검증과구분한다.

이변경은새boot파일/새bundle과새v2실행디스크에서만진행하며이미만든고객자료보존본과기존주입디스크는덮지않는다. 고객DB/API/web은아직기동전이다. 근거: [첫주입8/8](../../../scratch/chat-model-20261018/x600-runtime-injection-20261018-153407.jsonl), [새실행사본](../../../scratch/chat-model-20261018/x600-runtime-fullcopy-20261018-153801.jsonl).


## 15:56 KST — 새 독립 가상환경과 Docker 실제 기동

새 고객 실행용 사본에 주입 8/8을 통과한 뒤 원본/NBD/VSS 연결 없이 지속 실행을 시작했다. 새 가상환경의 Docker 29.8.2/cgroup2/독립 자료 경로와 Windows에 이미 실행 중인 모델의 HTTP 200 연결을 실제 확인했다. Windows 부팅 시각은 바뀌지 않았다. SSH 기동 제어 호출은 시간초과됐으나 새 감독기·가상환경 프로세스가 살아 있고 새 연결에서 소유한 loopback 5곳을 확인했다. 제어 호출 시간초과를 가상환경 기동 실패로 간주해 다시 실행하지 않았다.

앱 이미지 3종의 태그가 보이며 압축 해제/최종 검증 작업은 계속 진행 중이다. 이미지 적재 성공 proof는 아직 없고 고객 DB/API/웹 기동은 0/3이다. 고객 자료 보존본은 별도로 유지하며 현재 공개 고객 경로 전환과 고객 요청 성공을 확인한 상태가 아니다. 다음은 이미지 최종 검증 → 복사 DB 제어정보/설정 확인 → 새 사본 DB의 정상 WAL 재생 → API/웹 기동이다. 지키미 전용 앱 및 AWS 추가 변경은 0이다.


## 16:06 KST — 이미지 검증 완료·DB 기동 차단의 권한 원인

선택 이미지3종/50blob 최종 import proof를 실제 통과했다. DB 제어정보 helper는 첫 PATH 해석 실패, 두 번째 절대경로도 비관리자에게 접근 거부됐다. 정확한 실행 파일 자체는 root:root0755이며 실제 컨테이너 `/`만 root:root0700, `/usr`부터 실행파일 부모까지0755임을 root helper로 실측했다. 새 daemon의 umask077 상속과 빈 active snapshot root 생성이 원인에 부합하며, 고객 PGDATA 소유권 변경 대상으로 해석하지 않는다. root+DAC_READ_SEARCH의 읽기 전용 helper로 PostgreSQL17 제어정보를 읽었고 상태 in production, Timeline1이었다. 이는 복구 성공의 증명이 아니다.

고객 복사본 UID/GID999,0700을 보존했다. WAL 정규 segment5개, 외부 tablespace0·standby/recovery/backup metadata0·검토 대상 활성 외부 config 키0을 확인했다. 새 guest postgres 프로세스0·5432미사용을 검증하고 marker와 복사된 stale PID를 새 비공개 증거 경로에 백업/이름보존한 뒤, 새 사본의 표준 WAL 재생 검토 flag를 기록했다. 원래 E/VSS/보존 target에는 접근하지 않았다. resetwal0이다.

단일 dot tar rootmode 교정 probe는 실제 모드 assertion을 통과하지 못해 적용 성공으로 보고하지 않는다. 설치 Docker 의존 압축해제에서 dot/slash root entry를 건너뛰는 근거를 별도 담당자가 확인했다. 실제 DB 기동은 새 컨테이너 root shell이 `/` 한 디렉터리만0755로 바꾸고 즉시 원래 entrypoint/argv를 exec하도록 제한한다. 원본 이미지 변경·재귀 chmod/chown·고객 파일 권한 변경은0이다. wrapper 첫 준비는 health flags 사이의 image 위치 가정 assertion으로 create 전에 멈췄고, 고정 tag 위치를 찾아 원래 flags를 보존하는 새 실행안을 썼다. 고객 DB/API/웹 기동 성공은 아직 기록하지 않는다.

이미지 파일 진단의 첫 directory cp는 부모가 너무 넓게 지정해30초 CLI timeout으로 끝났다. 원문은 추출·보관하지 않았으며 이후 정확한 실행 파일 한 곳의 tar metadata만 읽었다. 후속 guest 가용메모리1,289,928KiB를 확인했다. 전체 디렉터리 진단은 재시도하지 않는다. 개선사항 ZIP2개는 임시 loopback 전달을 통해 새 guest에 받아 SHA2/2·ZIP 항목9/92를 확인했으며, 코드 적용은 아직이다.


## 16:34 KST — WHPX 실부팅 검증·불완전 종료를 숨기지 않는 가속 전환

현재 Windows 기능 변경 없이 같은 QEMU/공개 kernel/q35/WHPX/qemu64/1vCPU로 공개 read-only Linux 부팅·셸 응답·종료를 10/10,2.939초에 통과했다. HypervisorPlatform 기능 표시는 Disabled였으나 실제 Hypervisor API와 WHPX 실부팅이 가능했으므로 기능 표시만으로 불가능하다고 판단하지 않는다. 기존 TCG에서는 API 프로세스가 실행 중이면서 준비 제한 시간을 넘었고, CPU가 실제 실행 상태이며 메모리 초과 종료는 확인되지 않았다. Docker의5초 healthcheck도 실행 지연으로 실패해 DB의 health 상태만으로 DB 자체 정지를 판단할 수 없었다.

새 API의2CPU 상한은1vCPU guest에서 create 전에 거절돼 임시1CPU로 제한했다. API 기동 전 원본 health/config/설정을 확인하는 범위가 부족했던 실패를 보존한다. API 정상 stop60초 요청은 exit137로 끝났다. 이어 새 TCG guest에 DB/daemon 정상 중지를 요청했으나 GUGU_STOP_INCOMPLETE를 받았고240초 내 정상 ACK가 없어 감독기가 새 QEMU만 QMP로 종료했다. QEMU exit0은 정상 DB 종료의 증거가 아니다. outcome ACK=false/forced=true를 그대로 보존했다. 원래 Windows/WSL/모델은 종료하지 않았다.

가속 실행은 같은 독립 복구 사본의 OS/Docker만 먼저 켠다. 초기 주입 SHA와 지금 disk가 같다고 요구하지 않고, 종료된 현재 파일 SHA를 별도로 고정한다. release 계약은 이전 DB 정상종료 미확인·표준 사본 crash recovery만 허용·fresh read-only pg_controldata/stalePID 검토 전 DB 기동 금지를 명시한다. 공개 probe의1CPU와 고객2CPU 선택을 구분하며, 원본/NBD/VSS 연결0·TCG fallback0·자동 DB/API/웹 기동0을 지킨다. pg_resetwal·고객 자료 삭제는 허용하지 않는다.

기존 고객 URL은 별도 AWS URL과 다르며, x600의 기존80/443 전달이 옛 WSL 공유 Caddy로 향하는 것을 읽기 확인했다. 경유 기계의 고객 route는 .off이며 live에도 없어 살아 있는 역방향 통로를 현재 고객 공개 경로라고 단정한 초기 가설을 정정했다. 원래 공개 고객 경로 복구에는 고객 인증서/전용 TLS 접점의 선택 복사가 추가로 필요하다. AWS/경유/DNS/Windows portproxy는 아직 변경하지 않았다.


## 16:43 KST — 가속 환경에서 DB/API/웹 실제 정상·고객 TLS 선택 복사 계약

새 가속 guest의 Docker29.8.2/cgroup2와 native 모델 적재 조회 HTTP200을 실제 확인했다. 새 연결의 명령 응답이1~3초로 돌아왔으며 오래 걸렸던 TCG 제어 호출과 구분한다. 기동 제어 SSH는100초 시간초과됐지만 새 QEMU의 동일신원·소유listener·guest응답을 새 연결에서 확인했고 중복 launch는 하지 않았다.

fresh 읽기 전용 pg_controldata의 상태는 shut down이었다. 따라서 앞선 ACK 미확인이 DB 불완전 종료 자체를 의미하지 않았고, 실제 제어정보 검토 후에만 기존 복사 DB를 명시 기동했다. 현재 PostgreSQL17.11·healthy·pg_is_in_recovery=false·실제SQL1회 통과, resetwal0이다. 웹도 healthy로기동됐다.

실제 이미지824참조를 비교해795원문일치/22내용차이/7부재/미확인0을 확인했다. 선택22앱파일은 기대된20차이+2새모듈 범위였고 명시SHA/3.12compile검증한 별도readonly파일mount로 API에 적용했다. 실제x600기존base.py의 UTIC 생성 호출에 timeout키워드 하나만 추가한 별도파일과, 실제x600설정YAML에 없는 UTIC20초 키만 추가한 별도설정도 사용했다. 검토한 다른7설정키는이미존재해그대로보존했다. 원본이미지/기존YAML전체덮기/SQL적용0,readonly mount24개다. 새API healthy와별도WindowsGET에서API200/0.0049초·웹200/0.0475초를확인했다. 모델적재200은생성/자동대체시험성공으로세지않는다. 첫추가모델probe는메모리여유검문에서실행전멈춰진단범위를보존했다.

기존 공개 고객 주소는 여전히시간초과여서전체복구완료로보고하지않는다. 고객HTTPS복구용으로기존고정VSS+이미재생된같은COW를RO NBD→raw→qcow2RO→VHDXRO로다시읽고,별도공개OS fullcopy target에정확고객cert/key와전용설정조각만선택복사한다. 기존고객runtime은이복사guest에연결하지않고,source ext4는ro,noload,noexec이며journal재생을하지않는다. 공개OS와COW는잠금읽기/전후전체SHA불변을요구한다. 고객도메인은private계약에서만읽고키/도메인stdout0·다른도메인cert/ACMEaccountkey복사0이다. 새target반영만허용하며Windowsportproxy/DNS/경유기계설정은대기TLS검증전바꾸지않는다.


## 2026-10-18 16:57 KST — 기존 고객 주소·모델 호출 복구

- 실제 기동/배포: 독립 복구 가상환경의 고객 API·웹이 정상이며, 기존 공개 고객 주소 GET `/health`와 `/`에서 각각 HTTP 200을 확인했다. 전용 응답 헤더로 두 응답 모두 이번 독립 복구 환경에서 왔음을 확인했다(2/2). DNS·경유 경로·다른 배포 환경 변경은 하지 않았다. 기존 Windows의 HTTP/HTTPS 전달 대상 두 행만 백업 후 새 고객 앱으로 연결했고, 다른 세 행은 그대로임을 비교했다.
- 보안 접속: 기존 고객 도메인의 유효 인증서·키·해당 인증서 메타데이터만 추가 선택 복사했다. 읽기 전용 원본 접근, 원본 COW·공개 OS 기준 사본 불변, 별도 대상 기록을 검증했다(새 복사 검사 9/9). 다른 도메인 인증서와 ACME 계정 키는 복사하지 않았다. 전용 Caddy를 켜고 동일 발급처의 세 파일을 관리 저장소에 넣은 뒤 무중단 설정 교체와 실제 공개 TLS 검증을 통과했다. 현재 인증서 잔여 기간은 약74일이며, 미래 CA 갱신 성공은 시험하지 않았다.
- 실제 모델 경로: 고객 API 컨테이너의 설정을 사용해 로컬 모델에서 비어 있지 않은 답을 받았다(1.141초). 숫자7만 요구한 좁은 지시에는 그대로 답하지 않았으므로 의미 해석 정확도 확인으로 세지 않는다. 별도 시험 프로세스의 로컬 연결만 실패시킨 뒤, 기존 일·월 호출 상한을 적용한 실제 외부 API 전환에서 숫자7 응답을 확인했다(3.153초, 1/1). 고객 일정은 쓰지 않았다.
- 자원 보완: 추가 모델 시험 전에 독립 복구 가상환경의 여유 메모리가 약143MiB임을 확인했다. 독립 런타임 파일시스템에만 1536MiB swap을 만들고 활성화했다. 고객 앱 종료·원본 WSL/Windows 설정 변경은 하지 않았다. 앞선 모델 시험은 실제로 메모리 사전 조건에서 중단된 것이며, 비공개 오류 원문으로 확인했다.
- 남은 일: cs 감시·알림 worker 복구, 실제 UTIC 조회/경유 연결 및 고객 알림 처리 경로, 실제 고객 로그인·여행 의미 해석의 종단 확인. 원래 멈춘 WSL 자체는 계속 격리되어 있으며, 이번 고객 서비스는 별도 독립 복구 가상환경에서 실행 중이다. Windows 재시작은 하지 않았다.
- 로컬 작업 PC의 C: 여유0으로 기록 생성이 한 번 실패했다. 이번 세션이 만든 큰 로그 한 개를 NTFS 압축해 바이트 내용과 경로를 보존했고 약5MiB의 쓰기 여유를 확보했다. 자료 삭제·이동은 하지 않았다.

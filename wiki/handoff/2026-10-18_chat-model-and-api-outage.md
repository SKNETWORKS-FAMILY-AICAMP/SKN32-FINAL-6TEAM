# 채팅 해석 모델·앱 중단 진단 인계

## 한 일

- 광화문 일정의 야외 여부 질문 중 해석 오류와, 이어진 선택/알림 502 제보를 조사했다.
- 운영 앱 개별 상태를 조회했다. 09:57 KST API·고객 웹앱·알림 작업은 종료, DB는 실행·healthy였다. 기존 「알림 모니터링 흐름 점검」 세션의 배포 중단 보고와 일치했다.
- 운영 설정의 같은 학습 모델 `tripilot-pointer:e4b-ft`로 1토큰 생성 시험을 1회 했다. HTTP 500과 5,637,144,576바이트 CUDA_Host 버퍼 할당 실패를 직접 확인했다. 상태·모델 목록 조회는 2/2 HTTP 200이며 생성 성공과 구분한다.
- 원본 코드·Git 색인·자료·설정·서비스·예약을 변경하지 않았다. 다른 채팅에 메시지를 보내지 않았다. 이 인계는 추가 재시작·중단 승인이나 자동 작업 신호가 아니다.

## 남은 일

1. 기존 운영 배포 담당의 API·고객 웹앱·알림 작업 교체와 기동을 완료한다. 진단 세션이 중복 조작하지 않는다.
2. 실제 모델의 호스트 메모리·커밋 한도·고정 메모리 조건을 확인하고 생성 성공을 확인한다. 할당 오류만으로 GPU 메모리 부족이나 특정 다른 작업의 책임으로 단정하지 않는다.
3. 앱 복구 뒤 원래 고객 질문과 선택/알림 조회를 확인한다. 최초 제보의 정확한 원문·저장된 실패 상세는 아직 미확보다.

[확인 시각·범위·근거](../records/reports/2026-10-18_chat-model-500-and-api-502.md). 운영 복구·고객 경로 최종 검증은 미완료다.

## 후속 완료·남은 통합 — 2026-10-18

- 사용자 지시로 지키미 고객·관리자·전용 DB를 정상 종료했다. 전달 작업은 이미 중단이었다. 지키미 전용4/4 종료·PID0이며 사용자 새 요청 없이 재기동하지 않는다. 구구루트에도 쓰는 공용 Caddy는 유지한다.
- 대체 API는 작동하고 있었다. 정상적인 outdoor 단일 장소 응답의 null조회 범위를 목록 조회로 잘못 검사하던 결함을 실제 API로2회 재현했다. 단일 장소·문맥·답변 처리3파일을 격리 수정하고 고유 관련226시험 통과, F/E9통과, 실제 수정본 대체 API1/1 성공을 확인했다.
- 운영3파일 원문 백업·해시 대조 후 임시 수정했다. 정상 재시작이 연결 대기로 지연돼 DB 활성 질의0개·대상 API 신원 재대조 후 SIGINT1회로 연결을 취소했다. API /health200으로 복구했고, 운영 파일 그대로의 실제 대체 API도1/1 성공했다. 이 과정의10:36~10:39 수신 중단을 원래 기록에 보존한다.
- 최신 개별 상태는 구구루트 API·웹앱·알림 작업·DB 실행, 로컬 /qa-account HTTP200이다. 직접 공개 주소 조회403·브라우저 도구 실행 실패는 별도로 기록했다. 실제 고객의 원래 질문·버튼·알림 전체를 확인한 것은 아니다.
- **다음 배포에서 보존할 수정**: [검토 묶음6파일](../../scratch/chat-model-20261018/review-v1/). 런타임만 수정했고 이미지·정식 Git 소스에는 아직 통합하지 않았다. 코드3개·계약1개·회귀1개·실제 합성 응답fixture1개를 최신 이력에 보존 통합·검증해야 한다. 원본으로 통째 역복사하지 않는다.
- 자체 모델 메모리 부족은 미해결이지만 대체 API가 질문에 답하는 것을 확인했다. 이 문서는 추가 서비스 중단·예약 변경·지키미 재기동 승인 신호가 아니다.

## 강동선사문화축제 변경 거절의 별도 진단

- 10:46:04 실제 기록은 국립고궁박물관→강동선사문화축제의 replace_named 정상 해석, decision_failed 비어 있음이다. 다음 일정 도착 시각 계산에서 거절됐으며 model_path가 비어 있어 이 건의 모델 제공처를 확정하지 않는다.
- 다른 알림 점검 세션의210시험 통과는 날씨 후속 질문·변경 완료 안내2건이고, 이번 이동 시각 문제를 고쳤다는 근거가 아니다. 실제 경로 불가능/탐색 수렴/계산 예산 중 무엇인지 추가 계측이 필요하다. 고객 일정·운영 코드는 이 후속 진단에서 바꾸지 않았다.

## 12:23 KST 우선 인계 — Windows 종료 금지

- 사용자 명시: x600컴퓨터가 꺼지면 다시 안 켜지는 버그가 있어 Windows종료·재시작금지. 기존 재시작 도구 호출은 실행 전 사용자중단, 도우미는백업후비활성화. 이 기록은 재부팅 승인신호가 아니다.
- E→F5그룹21,643파일보존이동·전체크기/SHA256일치. E여유1.505→5.894GB, 추가4.388GB. 원래E경로연결유지. [결과](../records/reports/2026-10-18_x600-e-to-f-preserved-move.md).
- Windows현재학습모델 실제HTTP200·서울응답. 이전부모가 사라진3일전 모델프로세스2개정확신원/유휴확인후종료, 가상메모리여유0.815→13.236GB로증가했고 현재모델응답유지. 특정다른세션책임은확정하지않음.
- x600 WSL/가상환경관리서비스는여전히진입불가. 정상종료·관리프로세스종료·exactVM종료요청을구분해기록. vmwp exit1067/Wait258로종료완료확정불가. HCS종료20초timeout. VMMS도우미는사전조건에서멈춰서비스변경미실행. 새단계는기존컴퓨터부팅을건드리지않고진행.
- 시작된일정 감시후보3소스/계약/11신규+9기존단위20/20통과, x600반영/실제고객통제알림미완. 시간/근처식당 의미수정후보는220고유단위통과했지만실제모델2요청새필드누락검증실패로배포금지.
- 사용자 AWS업로드와x600복구 병렬요청. AWS별도담당기존앱6/6가용, 고객여행0건으로DB분리확인. 검증된야외질문3+진행중감시3을기존AWS소스에보존패치/검증중이며주소강제전환하지않음. AWS배포완료는담당실제롤아웃/HTTP/검증증거로후속기록.

[상세시각·실패·남은일](../records/reports/2026-10-18_festival-traffic-alert-recovery.md). 지키미전용4개는꺼둔상태유지, 공용접속프로그램보존.

## 12:56 KST 추가 인계 — 축제 UTIC 원문·의미 후보 검증

- 12:52:48 실제 UTIC134건 중 강동선사문화축제 정확한 원문1건을 확인했다. 올림픽로 선사초교사거리~서원마을입구 양방향 전면통제이며 현재 유효, 축제장 약517m다. UTIC 종료23시와 구청22시/배너22:30 차이는 보존한다. 복구용 조회 성공과 운영 알림 수신을 구분한다.
- 의미 후보17파일은 단위343+분리 실제DB8=351/351, 실제모델/API5/5로 완성해 AWS 보존 통합을 승인했다. 기존 모델 필드누락 실패 기록은 당시 사실로 남긴다. [최종 후보](../../scratch/chat-semantics-20261018/source/final_project_cs/_local_checks/semantic-contract-manifest.json).
- AWS API·웹 새 이미지 게시와 별도 DB 복원/확장 적용·재적용 검증은 완료했으나 운영 DB 확장·최종 API/worker/웹 반영·고객 알림 전달은 이 시각 미완료다. 웹 단위835/835·Linux빌드·컨테이너6경로 응답은 운영 공개 화면 검증과 구분한다. 고객 DB는 x600와 별개다.
- x600 Windows 재시작 금지는 유지한다. VMMS 정상 중지/시작은1회 실제 완료했지만 HCS가 기존 VM 대기 상태여서 WSL 진입 미복구다. 정확한 VM을 VMMS 두 경로로 조회하지 못했고 HCS열기는10초 대기 후 종료 요청 전 멈췄다. 이 결과로 Windows 재부팅을 대신 승인하지 않는다.
- [오라클 서버 접속 유지 계약](../delivery/oracle-service-continuity.md)을 구현 전에 기록했다. 별도 작업 담당이 같은 사용자 무중단 지시로 새 API 병행 기동을 구현 중이므로 소스·Caddy·배포 제어를 동시에 바꾸지 않는다. 반영 뒤 실제 접속 유지와 worker중복·스트림·인증·DB호환·정적파일을 검증한다.

남은 일: AWS 최종운영반영과 합성/실제고객 경로 구분 검증, x600 기존여행 연속성 확보·WSL복구, 오라클 담당 반영 후 접속유지 독립확인. 원래 고객에게 실제 통제알림이 도착했다고 아직 보고하지 않는다.

## 13:06 KST — 담당 전달 완료·현재 복구 한계

- 사용자가 해당 세션으로 추가 수정 전달을 직접 지시해 오라클 담당에2회 전달했다. 실제UTIC축제원문·진행중감시·최종의미17파일·접속유지9항목을 포함했고 담당의 manifest/보고서/계약 읽기까지 확인했다. 오라클 소스·Caddy·compose는 중복 변경하지 않는다.
- 12:58 실제 Windows모델은16토큰상한 시험에서HTTP200·서울, 고객API/web은2/2미응답이다. VMMS시작 명령 접수는 RUNNING 완료가 아니다(현STOPPED, computeSTART_PENDING). Windows재시작금지는유지한다.
- AWS 통합425/425, 실기동343/343, 의미/대체API2/2·최종17해시 일치. 운영최종반영은담당의후속실행으로확인한다. 자료일부실패 때 실제통제원인이사실안내에서빠지는 잠재분기는별도격리후보로검증하며 자동변경안전장치를우회하지 않는다.

## 13:23 KST — AWS 새판 실제 기동·최종 통지 보완

- AWS API/worker/web3개새판기동완료. API/worker34/34해시·실제6분류응답·축제UTIC/서울강풍확인,ITS부분실패별도. 운영DB확장10파일및사실자료적재의기존고객/장소지문보존확인.
- 웹최초교체502세건은보존했다. 준비/종료보호뒤실제교체31/31·최종직접6/공개18·추가오류0. [웹인계](../../scratch/aws-web-recovery-20261018/WEB_HANDOFF.md).
- 통지누락추가3파일후보99/99·전체diff부모검토완료, AWS추가배포승인·Oracle담당최종전달완료. 기존의미17파일은불변. 수동TripWatcher는동일안내잔여.
- Google주소불일치는외부클라이언트등록1건필요하여정확한주소를사용자에게안내·응답대기. 실제OAuth/개인수신미확인. 식당1228등록만으로는축제3km후보0이라증분사실보완/실행검색검증중. x600고객여행은미이전·Windows종료금지·WSL미복구.

[시간별근거·실패·미확인](../records/reports/2026-10-18_festival-traffic-alert-recovery.md).

## 13:40 KST — x600 복구 집중·새 중단 증거

사용자 명시로 AWS 추가 작업을 취소했다. 기존 운영 앱 보존, 신규 게시/배포/자료층/자원 변경은 중단이다. x600 가상환경·고객 앱 복구가 우선이며 Windows 종료·재시작은 금지한다.

확인: 원VM Worker18590의 게스트 Kernel panic/Processor Context Corrupt와 VMBus 종료 대기, 그 이전 VHDMP11 Flush0xC000009A로 가상 디스크 surface invalidated 기록을 새로 확보했다. 물리 부품 고장·특정 세션 책임은 미확정이다. 모델은 재적재37.34초 후 후속0.95초 생성 성공·유휴 언로드 방지값 적용, 고객 앱은 여전히 미복구다.

이전 식당3km0건은 active만 조회한 필터 오류였다. 실제 closed 제외12곳이며 원본 보존·추가 적재0. 초기700m/최종3km 불일치1파일 후보98/98은 Oracle 전달, AWS 추가 반영 중단. 이미 반영한 사실 안내3파일은506/506·실행 해시40/40, 합성 실제 어댑터 안내1회/중복0이나 개인 고객 수신 미확인이다.

[상세 시간·원문·남은 일](../records/reports/2026-10-18_festival-traffic-alert-recovery.md).

## 13:53 KST — 복구 미완료 체크포인트

- 최신13:52:38 실측: Windows 유지·모델 실제0.95초 생성 성공, WSL START_PENDING/원VM Wait258 유지, 고객 API/web2/2 미응답이다.
- 정확 마지막 TID의 pending I/O에 공식 취소1회→1168,10초 종료 미완료. 마지막 기록 NtClose는 현재 커널 대기 위치를 확정하지 않는다.685핸들 읽기 검증은 장치 원인 확정이 아니다.
- 원본 raw 헤더8,200바이트 읽기만 수행: CRC2/2·active LogGUID 존재·크기/mtime 동일. 원본 쓰기/attach/수리0이며 내부 DB 건전성 미확인이다.
- AWS 추가 작업 중단 완료, 기존 운영 앱 보존. Windows 재시작 금지·지키미 재기동 금지 유지. VSS/COW/TCG 대안은 안전·자원·데이터·중복 실행 조건 미검증이라 snapshot/설치/기동0이다.

실제 완료는 모델 단독 응답이며 가상환경·고객 앱 복구 완료가 아니다. [현재 근거·안 해본 수단과 제외 이유](../records/reports/2026-10-18_festival-traffic-alert-recovery.md).


## 14:24 KST — x600 별도 기동 및 COW 예비시험 완료

한 일: 정상6/6·합성 dirty 로그10/10·고객 자료 없는 실제 Linux 기동8/8,11.603초/최대 RSS239MB. 원본 WSL은 아직 멈춰 있다. 원본 VHD 직접 쓰기0·고객 자료 연결0·새 snapshot0·Windows 재시작0이다. 알려진 공식 배포 인증서 만료는 유효로 보고하지 않고 제한 검토 근거를 보존했다.

남은 일: 계약의2GiB 제한 고정 snapshot 생성/검증 → 명시적 읽기 오류 전파 → 새 COW에서 자료/DB 검사 → 원래 WSL의 중복 쓰기·알림 차단 → 고객 앱 실제 경로 확인. 다른 볼륨의 기존 snapshot/연결은 보존하고 timeout 생성은 재시도하지 않는다. AWS 추가 작업은 중단한다.

[실행 경계](../delivery/x600-preserved-boot-recovery.md) · [시간별 근거](../records/reports/2026-10-18_festival-traffic-alert-recovery.md).


## 14:29:15 KST — 실제 고정 사본 확보

한 일: snapshot1회 생성 성공, 고유ID/State12/NoWriters 및 volume readonly·동일크기249.6GB·헤더CRC2/2 확인. 초기차등영역335.5MB·최대2GiB, 원본 직접 쓰기0·Windows 재시작0. 고객 자료 없는 TCG8/8·합성 COW16/16은 이전대로 보존했다.

남은 일: readonly NBD bridge의 실패 주입 검증 → 새 COW에만 VHDX 로그 재생 → 네트워크 없는 ext4 ro,noload 확인 → 사본 DB crash recovery/고객 앱 → 원래 WSL 통신 차단과 공개단일경로 검증. 기존 WSL·고객 앱 미복구·AWS 추가 작업 중단. [정본 실행 경계](../delivery/x600-preserved-boot-recovery.md).


## 14:40:31 KST — 실제 사본 내부 읽기 성공

한 일: 실제 VHDX 로그를 새COW에만 재생, 네트워크 없는 ext4 읽기 전용 검사7/7·COW 전체SHA 불변·NBD1877읽기/오류0. Ubuntu26.04·배포폴더·Docker자료 존재 확인. 기존 게스트 코드/Docker 실행0·원본 직접 쓰기0·Windows 재시작0이다.

남은 일: 메타데이터로 고객DB 위치 확인 → 새COW에서만 DB crash recovery → 선택고객앱 기동 → 원래WSL 통신 차단/공개경로 검증 → snapshot 의존을 줄인 독립 자료 확보. AWS 추가 작업 중단·지키미 미기동 유지. [실행 근거](../records/reports/2026-10-18_festival-traffic-alert-recovery.md).


## 15:00:52 KST — 125GB 확보·실제 운영대상 메타데이터4/4

사용자승인옛백업정확1개삭제,실제125,125,525,504바이트회수/F여유135,683,129,344바이트. 현재E원본과오늘RO사본보존,전체옛이미지재백업0·헤더/감사보존. 원문은상세기록링크를본다.

readonly메타수집실제8/8→WindowsJSON4/4·hostconfig4/4확인. PG17.11·OCI이미지3개·기존고객볼륨확인,Env값출력0. oldDocker자동복원경로는제외하고새공개Alpine실행OS·freshDocker영역에필수이미지/자료만옮기는중이다. 새OS준비담당은고객디스크/NBD접근0,부모는source접속을독점한다. DB/WAL검사·고객앱기동·통제알림수신미확인,Windows유지/AWS중단/지키미OFF계속.

[실행근거·남은일](../records/reports/2026-10-18_festival-traffic-alert-recovery.md).


## 15:08:10 KST — 독립 환경 설치·선택 자료 실측

- x600공개AlpineOS설치1/1완료(정상서명apk,29.4초,peakRSS580,173,824B). 최초독립부팅은기존devtmpfs중복마운트검사로실패했으며실패v1/로그를보존하고새v2에서검사코드만수정중이다. 고객기동성공으로보고하지않는다.
- 실제readonlyguest8/8,NBD2438읽기/오류0,COW불변. 선택이미지manifest3/index3SHA검증,44layer압축합725,470,887B. 실제고객자료du PG514,400KiB/이동224,216KiB/diagnostics24KiB/ops76KiB. configblob3/layer44전체검증과DBrecovery는아직안했다.
- 최초parser는DockerImage를configID로해석해KeyError였다. 실제파일종류가OCIindex임을확인해새parser로index→linuxamd64manifest연결을검증했다. 실패를보존했다. 읽기수집완료를이미지전체복구로간주하지않는다.
- Windows재시작0,AWS추가작업0,지키미기동0. 다음은독립OS완료→새target선택자료복사→source없는부팅→DB/API/web복구다. 고객app8043/web13000은직전실측2/2무응답,모델단독HTTP200/0.8초와구분한다.

근거: [추가사본검사](../../scratch/chat-model-20261018/x600-fixed-copy-inspection-20261018-150533.jsonl), [선택자료실측](../../scratch/chat-model-20261018/x600-image-data-private-summary-20261018-150702.jsonl). privatearchive/환경값은공유기록에전개하지않는다.


## 15:14:00 KST — 독립 OS 부팅 완료·복사 실행안 준비

- 새공개OSv2의기존source/NBD/NIC없는부팅8/8 통과.9.362초/peakRSS394,584,064B. 원래OS와다른새OS자료만으로부팅했다. Docker/고객자료기동은0.
- 공개Python은검증된새target사본에서RAM복사해JSON/SHA검사에사용한다. 원래고객Ubuntu코드실행은0. 새longNBD13/13 합성시험과새메모리/시간/용량guard자기검사1/1 통과. 고객자료실제복사는아직0.
- 원래WSL의중복고객통신을막기위한가역설정안을준비했으나아직적용0. 네트워크차단을로컬DB쓰기정지라고간주하지않는다. 실제DB복구·고객API/web·모델API대체·통제안내확인은남았다.

근거: [독립OS부팅](../../scratch/x600-wsl-io-recovery-20261018/independent-os-v2-run-20261018-150731.private.jsonl), [준비실행안](../../scratch/chat-model-20261018/run_x600_selected_copy_v1.py).


## 15:14:50 KST — 원래 WSL 고객 통신 차단 정책 반영

WSL creator 범위에 새 inbound/outbound AnyBlock priority1 규칙2개와 LoopbackEnabled=False 설정1개, 총3/3을 반영했다. PersistentStore/ActiveStore 두 곳의 정확 필드와 EnforcementStatus1을 확인했다. 기존 설정·규칙·프로필은 비공개 XML/JSON으로 직전 보존했고 일반 Windows 방화벽/기존 규칙/서비스/Windows 부팅 시각은 바꾸지 않았다.

WSL 포트가0개이므로 실제 패킷 차단은 확인하지 못했다. 로컬 DB 쓰기·AF_HYPERV/interop 차단도 아니며 기존 가상환경 완전 종료라고 보고하지 않는다. 기존 vmwp Wait258·vmcompute start_pending이 계속된다. 새 SSH 연결은 성공했고 Windows 모델 직접 HTTP200/done/서울,0.86초,keep_alive=-1을 확인했다. 고객 API/웹은2/2 무응답으로 남았다.

근거: [정책 반영](../../scratch/chat-model-20261018/x600-wsl-fence-apply-20261018-151423.jsonl), [새 연결·모델·앱 재확인](../../scratch/chat-model-20261018/x600-recovery-checkpoint-20261018-151430.jsonl). 복사 bundle 준비 중이며 실제 고객 자료 복사·독립 고객 DB 기동·공개 경로는 아직 확인하지 않았다.


## 15:21:01 KST — 실제 선택 복사 실행 전 검토 완료

부모가 공개RAM helper/init 전체를 읽었다. 최종 helper SHA7ad048b8b2debb4756712fc40e17f95032caf9f65b78438d6b93faff55b6e1a6, private bundle SHA f62af9096aa3d1e6da457496ed1dc4a3901909da1410a6f4a375772150983521이다. 합성 blob/경계시험12/12 통과했으나 Windows 토큰의 symlink 생성 권한 제한으로 실제 symlink 거절 시험은 하지 않았다. 실제 Linux cp-a의 UID/GID/mode 보존은 복사 결과에서 대조한다.

builder 첫 시도는 Compose service를 api/web/db라고 가정해 사전 AssertionError로 멈췄다. 실제 exactName과tripilot-api/web/db 라벨 두 조건으로 새 builder에서 정정했고 helper/init은 바꾸지 않았다. 원본/VSS/VM/새bundle쓰기 전 실패였으며 실패 로그를 보존했다.

실행안v3는 복사 전 stale abort flag가 있으면 새 디스크도 만들지 않고 거절하며, NBD 조기 종료는 새 guest 중단으로 전파한다. 독립 코드 검토4/4, 부모의 최종 실행안 SHA d1a353d15fc716ead09f7156cfa60c69349465f80a92394724ca906da1bc9da0를 확인했다. 상태·중단 소유 flag를 삭제해서 재시도하지 않는다. 다음은 검증된 새target 전체사본에만 실제 복사를1회 실행하는 단계이며 고객 Docker/DB/API/web 기동 성공으로 보고하지 않는다.


### 15:22:16 KST — 복사 첫 실행의 QEMU 인자 실패·새 실행안

첫 실행은 새target전체사본/새COW/VHDX로그재생까지만 성공했고 Linux를 부팅하기 전 QEMU가 source serial25자의 기본device_id겸용20자상한으로 exit1했다. stdout0·0.273초·원본쓰기0·NBD1194읽기/오류0이며 실패COW/target/proof를 보존했다. 실제고객자료복사 성공이 아니다.

현재 실행파일의 scsi-hd 도움말에서 device_id/serial 두 독립 인자 지원을 실제 확인했다. 새v4 실행안은 source serial을 그대로 유지하고 짧은 명시device_id를 추가한다. source VPD0x80을 읽는 bundle/helper는 동일 해시이며 source데이터경로/권한은 바꾸지 않는다. 이전 중단 flag가 있으면 재시도하지 않으며 새 세션/새target/COW에서만 다시 진행한다.

근거: [첫 실행](../../scratch/chat-model-20261018/x600-selected-copy-20261018-152103.jsonl).


## 15:26:40 KST — 실제 고객 자료 선택 복사 성공

새 독립 target 사본으로 이미지3종의manifest/config/layer50blob과고객DB·이동자료·diagnostics·ops 정확4트리를 옮겼다. source/target SHA·size·mode/uid/gid·자료목록 전후 대조, 공개RAM runtime 출처 대조와privatemetadata복사를 통과했다. 부모 실행 proof10/10,150.224초,guestpeakRSS663,101,440B,NBD49,544읽기/오류0·fatal0·원본쓰기핸들false다. 새작업전체할당2,726,910,671B로8GiB예산안이다. 30초 snapshot감시와회차정상종료를확인했고guest/NBD는종료됐다.

이target을보존본으로두고다음runtime주입은별도새fullcopy/noBacking/전체streamingSHA대조후그새디스크에만쓴다. 원본/E/snapshot/기존OS/보존target은수정하지않는다. copy성공은PG WALrecovery·고객DB/앱기동·공개고객경로확인과다르다. 그부분은아직미확인이다.

근거: [실제복사10/10](../../scratch/chat-model-20261018/x600-selected-copy-20261018-152217.jsonl).


## 15:43:03 KST — 실행 설정 주입 성공·종료 연동의 기동 전 수정

첫 독립 실행용디스크에 주입8/8·19.044초/peakRSS360,255,488B를 실제 통과했다. 원본/NBD/VSS/NIC 연결0·Docker기동0, 기존공개init/환경원문보존 및 새init/선택10파일대조를 확인했다. 이후 기동 전 독립검토에서 PID1의작업중stop요청거절·감독기의8초고정뒤QMP종료·관리콘솔로그계약불일치3건을찾았다. 이디스크/코드를보존하고아직지속실행QEMU는시작하지않았다.

새실행용v2디스크를다시고객자료보존본에서fullcopy했고1,783,365,632B/전체SHA6240686088c8d6b74133ff818dafc3a00e83051725313c4fbb82140ec9faa678가전후일치했다. 새fullcopyproof SHA d92e40cdbf9a7674e11213100e4da9a9cd030f66419a0d04d2fcc889f255af75→selected-copyproof2ced236c6d906103a3023aaf32dec97a5018c606d7812eff3f96de54e0cf5ea7 연결도확인했다.

수정감독기는소유중단때240초/자원비상때10초까지실제정상종료ACK를읽는다. ACK없음은정상종료완료로보고하지않고새guest강제중단·DBcrashrecovery필요가능성을private결과에남긴다. 원래Windows/WSL/모델을종료하지않는다. 관리자직렬출력은기록하지않는다. 새PID1은작업중중단을우선수락하고자기stage그룹만TERM/회수,소유DB/daemon종료확인뒤에만ACK를낸다. Python대역계약10/10은실제VM/DB종료검증과구분한다.

이변경은새boot파일/새bundle과새v2실행디스크에서만진행하며이미만든고객자료보존본과기존주입디스크는덮지않는다. 고객DB/API/web은아직기동전이다. 근거: [첫주입8/8](../../scratch/chat-model-20261018/x600-runtime-injection-20261018-153407.jsonl), [새실행사본](../../scratch/chat-model-20261018/x600-runtime-fullcopy-20261018-153801.jsonl).


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

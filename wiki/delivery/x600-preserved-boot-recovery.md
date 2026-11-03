# x600 Windows 유지·격리 기동 복구 계약

2026-10-18 사용자 지시: AWS 추가 작업은 중단하고 x600 가상환경·고객 앱 복구에 집중한다. Windows 종료·재시작은 하지 않는다.

## 현재 상태와 경계

기존 가상환경은 게스트 커널 패닉 이후 종료 정리가 끝나지 않았다. 모델 단독 응답과 고객 앱 복구를 구분한다. 원본 가상 디스크의 헤더·로그·형식은 일반 파일 읽기로만 확인했다. 정상 CRC는 파일시스템이나 고객 DB의 정상 판정이 아니다.

원본 디스크 쓰기·로그 재생·마운트·분리·수리·축소, 기존 자료 삭제·덮어쓰기, Windows 기능 해제·재설치·드라이버 리셋을 이 절차에서 수행하지 않는다. 이미 실행한 정확한 잔여 스레드의 취소1회는 실패했으며 반복하지 않는다.

## 단계별 검증

1. 공식 배포처·게시 해시·실제 서명 상태를 기록하고, 기존 압축 도구로 새 격리 폴더에만 필요한 파일을 추출한다. 설치 프로그램 실행·서비스·레지스트리·시스템 PATH 변경은 하지 않는다. 서명 오류·해시 불일치·보안 도구 차단을 우회하지 않는다.
2. 새 소형 시험 디스크에서 원본 파일 전체 바이트를 읽기 전용 backing으로 둔 새 COW 파일과 VHDX 형식의 중첩 읽기·쓰기·확장을 확인한다. 정상 읽기/쓰기는 dirty 로그 재생 성공과 별도 항목이다. 시험 원본의 전후 전체 SHA를 대조한다.
3. 공개 최소 Linux와 설치된 커널의 해시를 확인해 별도 초기 파일시스템을 만든다. 새 시험 디스크만 붙여 TCG·단일 CPU·guest RAM256MiB부터 기동한다. 네트워크·Docker·systemd 자동 시작 없이 디스크 존재·크기·시험값 해시를 확인하고 게스트만 종료한다. 실제 고객 디스크를 이 단계에 붙이지 않는다.
4. 실제 데이터 사본은 시점 고정·읽기 전용 backing의 증거가 필요하다. VSS 생성은 원본 볼륨 flush/freeze를 수행하므로 단순 조회와 구분한다. 생성 전 저장소·권한·용량·기존 snapshot·수명 및 실패 동작을 검증하고, 새 snapshot의 ID·원본 볼륨·시각·DeviceObject·속성을 확인하기 전 사용하지 않는다. 현재 단계에서 snapshot 생성은 아직 승인된 실행으로 간주하지 않는다.
5. 실제 데이터 사본을 쓰는 단계가 성립해도 먼저 격리 셸·네트워크 차단·파일시스템 읽기 전용으로 확인한다. ext4의 읽기 전용만으로 journal 쓰기를 막는다고 가정하지 않는다. 사본의 로그 재생/DB crash recovery는 별도 새 COW에만 허용할지 검토하고 원본에는 수행하지 않는다. 강제 WAL 초기화나 임의 데이터 손실 수용은 하지 않는다.
6. 고객 앱 공개 전 원래 가상환경의 고객 쓰기·알림 작업 재개와 중복 실행을 차단하고, DB·로그인·공개 경로·모델/API 대체·통제 사실 안내를 확인한다. Docker를 시작하면 기존 컨테이너가 자동 재시작할 수 있으므로 기존 자료 폴더에 그대로 daemon을 띄우지 않는다. 지키미 전용 앱은 재기동하지 않는다.

## 자원·실행 보호

- 예비 도구·시험 자료는 새 작업 폴더1GiB 이내를 목표로 실제 크기를 센다. 기존 자료를 정리해 예산을 확보하지 않는다.
- 첫 TCG 시험은 프로세스 식별자·생성시각·실행 경로·인자를 확인한 새 자식만 감시하고 제한을 넘으면 그 자식만 종료한다. 예비 시험 RSS512MiB, 호스트 가용 물리 메모리2GiB 이상, 새 파일 저장 공간8GiB 이상을 시작 조건으로 한다. 이 조건은 실제 고객 앱 전체 실행 용량의 검증을 대신하지 않는다.
- `-m`은 guest RAM이며 QEMU/TCG/호스트 전체 메모리 상한이 아니다. 실제 관찰값을 별도로 기록한다. 시험을 위한 예약·상주 감시·새 자동화는 만들지 않는다.
- 기존 모델의 유지값과 현재 Windows 부팅 시각을 보존한다. Windows나 다른 프로세스를 종료하는 포괄 명령을 쓰지 않는다.
- 원본 여행 데이터·키·토큰·접속 정보는 공개 로그/기록에 넣지 않는다. 백업·증거·실패한 시험 파일은 삭제하지 않는다.

## 보고 범위

시험 디스크 성공은 고객 DB 복구가 아니다. 별도 임시 기동 성공은 원래 WSL 복구 완료가 아니다. 로컬 준비·x600 시험·고객 앱 공개·실제 알림 수신을 각각 기록한다.

[실행 기록·실패·미확인](../records/reports/2026-10-18_festival-traffic-alert-recovery.md).

## 공식 도구 인증서 만료의 검토 범위 — 2026-10-18

공식 QEMU 다운로드 페이지가 연결한 Windows 배포 파일의 전체 SHA512가 게시값과 일치했다. 실제 검증 HRESULT는 CERT_E_EXPIRED(0x800B0101), 서명자 Universität Mannheim의 유효기간은2022-12-09~2023-12-09, 파일 timestamp는2026-08-11이다. 유효 서명이라고 보고하지 않는다. [공식 QEMU 이슈2602](https://gitlab.com/qemu-project/qemu/-/issues/2602)에서 해당 배포 유지관리자가 같은 만료 인증서 문제를 알려진 문제로 설명했다.

이 원인·공식 HTTPS 출처·전체 게시 해시 일치·현재 보안 도구 검사·추출 파일별 해시를 확인한 경우에만 원본 미사용의 소형 시험 디스크 검증에 한정해 도구 실행을 검토한다. 이는 모든 서명 오류를 허용하는 규칙이 아니다. 변조·해시 불일치·뜻밖의 서명자·폐기 또는 Windows 보안 정책 차단은 우회하지 않는다. 시스템 시각·인증서 저장소·보안 정책은 바꾸지 않으며 설치 프로그램도 실행하지 않는다. 실제 고객 디스크 연결·공개 앱 기동 승인을 포함하지 않는다.

프로세스 Job 제한은 자원·실행 수 제한이며 파일·네트워크 권한을 완전히 차단하는 보안 sandbox라고 보고하지 않는다. 게스트 네트워크 없음·시험 디스크 한정·원본 접근0을 별도 검증한다.


## 14:24 KST — 합성 검증 통과 뒤 실제 고정 사본 단계의 실행 경계

정상 중첩 COW6/6·단일 합성 dirty 로그10/10·고객 자료 없는 Linux 기동8/8을 실제 통과했다. 공식 배포 전체 게시 해시 일치·추출 파일 해시·보안 검사와 알려진 만료 원인을 재검토했다. 만료 서명은 유효로 바꾸지 않는다. 이 확인에 한정해 같은 해시 도구를 아래 고정 사본 검사에도 사용할 수 있다. Windows 보안 정책 차단은 우회하지 않는다.

사용자의 x600 복구 지시 범위에서 다음 단일 고정 사본 생성 시도를 진행한다. 관리자 권한·NTFS 두 볼륨·현재 자료 볼륨의 기존 snapshot/저장소 연결0·물리 가용4.70GB·자료 볼륨 여유5.89GB·보관 볼륨 여유10.58GB를 실제 확인했다. 다른 볼륨의 기존 snapshot1개/연결1개는 보존한다. 보관 볼륨에 자료 볼륨용 최대2GiB의 새 차등 저장소 연결1건을 먼저 시도하고, 반환0 및 재조회한 정확 연결/상한을 확인한 때에만 ClientAccessible snapshot1건을 생성한다. CIM 클래스는 설치되어 있으나 Microsoft 문서의 클라이언트 지원 표기가 없으므로 실제 성공을 가정하지 않는다. 실패하면 다른 기존 연결 변경·삭제·상한 확대를 자동 시도하지 않는다. 호출 결과 불명/timeout이면 같은 생성 명령을 재시도하지 않고 실제 생성 여부부터 조회한다.

VSS는 볼륨 flush/commit을 수반할 수 있어 원본 모든 바이트 불변이라고 약속하지 않는다. 직접 원본 VHD 쓰기·로그 재생·attach·분리·수리는 계속 금지한다. Snapshot은 전체 독립 백업이 아니며 수명/차등 공간 소진 때 소멸할 수 있다. 실제 ID·시각·원본 볼륨·읽기 전용 device·크기·헤더를 검증한 뒤 읽기 전용으로만 사용한다. 원본 guest DB와 일관된 상태라고 간주하지 않는다.

현재 Windows QEMU의 파일 읽기 오류가 short-read/0값으로 숨을 가능성을 추가 검토 중이다. Snapshot 존재 감시만으로 모든 읽기 오류를 감지한다고 가정하지 않는다. 실제 사본을 QEMU에 연결하기 전에 명시적 읽기 오류 전파 경로와 고정 backing 증거를 확정한다. 고객 쓰기/알림/원래 WSL 재개 차단 검증 전에는 고객 앱을 공개하지 않는다.

공식 계약 근거: [저장소 연결 생성](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/vsswmi/create-method-in-class-win32-shadowstorage), [snapshot 생성](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/vsswmi/create-method-in-class-win32-shadowcopy).


### 14:25 저장소 생성 첫 실패와 인자 정정

새 연결 Create1회는 반환10(Unknown error), 해당 볼륨 연결/snapshot 모두0이었다. 실행 인자의 볼륨 끝 구분자가 PowerShell에서 두 개로 전달되는 작성 실수를 확인했다. 첫 실패·스크립트·증거를 보존하고, 재조회한 실제 볼륨 DeviceID 문자열을 그대로 전달하는 새 단일 시도만 허용한다. 기존 연결 변경/삭제·상한 확대·snapshot 반복 생성은 허용하지 않는다. 저장소 연결0과 여유를 다시 확인한 뒤 진행한다. 직접 원본 VHD 쓰기0이다. [첫 시도](../../scratch/chat-model-20261018/x600-limited-shadow-storage-20261018-142345.jsonl).


### 14:26 인자 의심 정정·같은 호출 재시도 보류

직전14:25 기록의 구분자 두 개 주장은 JSON 표시를 실제 문자열로 오독한 것이다. 독립 AST 계수에서 실제 Volume=[69,58,92]/DiffVolume=[70,58,92], 각각 길이3으로 정상 인자였다. 인자 실수라고 확정할 근거가 없으며 GUID로 같은 호출을 다시 하지 않았다. 반환10의 원인은 아직 미확정이다. Microsoft 문서의 해당 WMI 메서드 클라이언트 지원 표기는 None supported이며, 실제 Windows에서 지원되는 관리 명령·하위 오류를 별도로 검토한다. 원본 VHD 직접 쓰기/새 snapshot/다른 기존 연결 변경은0이다.


### 14:28 Windows11 관리 명령의 제한된 별도 시도

WMI 동일 호출은 반복하지 않는다. Windows11 지원이 명시된 vssadmin resize shadowstorage를 자료 볼륨의 snapshot/association 모두0인 조건에서 최대2GiB·지정 보관 볼륨으로1회만 시도한다. 새 연결 생성은 문서 보장이 아니므로 성공을 가정하지 않는다. 기존 source 사본이 없음을 직전 재조회하므로 축소로 기존 사본을 소멸시키지 않는다. 다른 볼륨의 기존 ID/연결은 전후 대조한다. 실패/timeout이면 반복·삭제·임의 확대를 하지 않는다. [공식 명령·제약](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/vssadmin-resize-shadowstorage).


### 14:26:53 KST — 실측 저장소 위치·단일 사본 생성 조건

vssadmin 제한 명령은 exit2/지정 연결을 찾지 못했다고 답했다. 다만 바로 뒤 실제 조회에 자료 볼륨 자신을 보관 위치로 하는 최대2GiB 연결1개가 새로 나타났다(allocated/used0). 앞선 WMI 호출과 이 명령 중 어느 것이 생성했는지는 확정하지 않는다. 이 연결을 삭제하거나 보관 위치를 바꾸지 않고 보존한다. 다른 볼륨의 기존 snapshot ID/연결은 유지됐고 새 snapshot은0이다. 자료 볼륨 여유5.89GB에서 최대2GiB 차등영역을 사용하면 약3.74GB가 남는다. 해당 연결/상한/기존 source snapshot0·자료 볼륨 여유5GiB 이상·물리3GiB 이상·새 파일 보관 볼륨9GiB 이상을 직전 검증한 뒤 ClientAccessible snapshot Create1회만 진행한다. 실패/결과 불명 때 재호출하지 않는다. 모든 자료 원본 직접 쓰기 금지와 다른 snapshot 보존 경계는 유지한다. 앞 문단14:28 표기는 작성 중 시각 오기이며 실제 명령 증거14:25:56이 정본이다.


## 14:29:15 KST — 고정 사본 생성 이후 읽기 단계

실제 snapshot1회 성공·고유ID/원본볼륨/시각/State12/속성과 volume 읽기 전용을 검증했다. 두 headerCRC2/2는 정상이나 active 로그가 남아 있다. 다음은 읽기 전용 전달 bridge의 새 합성 실패 시험 후, 실제 고정 사본 파일만 아래 raw backing으로 쓰는 새 qcow2를 만들고 guest 없이 VHDX 로그를 새 COW에만 재생하는 단계다. 원본 path fallback·원본 쓰기·snapshot 삭제/다른 사본 변경은 금지한다.

bridge는 정확 snapshot의 read-only 핸들1개·고정 file length·loopback 전용·read-only export·요청 상한·범위 및 전체 길이 읽기 검사·OS 오류/short read 시 명시 EIO와 연결 종료를 요구한다. 실패를0으로 채우거나 reconnect로 다른 source를 열지 않는다. snapshot 소멸/여유 감소 때 새 QEMU만 중지한다. 차등 저장영역/원본볼륨 여유는 실행 전후 다시 확인한다.

첫 실제 guest 검사는 새 COW chain을 다시 readonly로 열어 네트워크 없음·공개 initramfs PID1·block readonly/예상크기 assert·ext4 ro,noload,nosuid,nodev,noexec만 사용한다. 기존 OS 실행파일·systemd·Docker·fsck·원본 WAL 수리 코드를 실행하지 않는다. noload 뷰는 불일치할 수 있어 DB 복구 성공이라고 보고하지 않는다.


### 14:34:06 KST — 읽기 전달 실패 시험 통과·실제 사본 검사 진행

읽기 전용 NBD bridge의 실패 주입6/6·실제 QEMU 연결/패턴 읽기2/2, 합계8/8을 통과했다. 실제 새 합성 파일의 LockFileEx로 발생시킨 ReadFile 오류33과 주입 short read가 명시 EIO·접속 종료·fatal source latch로 이어짐을 확인했다. 범위 밖/쓰기 거절과 source 치명 오류를 구분하고 원본 fallback0이다. 부모가 최종 코드를 읽고 로컬/원격 실행 스크립트 구문2/2를 확인했다. SHA256 878c8af5a36bf8ded33a440968780dc4459595e857e9d1924d47ac94363d1776의 bridge만 사용한다. 고정 사본·새 COW 한정으로 로그 재생/readonly Linux 검사를 실행하며 고객 앱 공개/네트워크/기존 게스트 코드 실행은0으로 유지한다.


### 14:37:40 KST — 최초 연결 실패 보존·수정 검사 조건

첫 실제 사본 검사에서 새qcow2 생성만 성공했으며 VHDX를 열기 전 저장된 backing URI와 명시 server 옵션 충돌로 중단했다. bridge 실제 payload read0·원본 쓰기0·VM기동0이다. 실패 COW/로그를 보존했다. backing URI를 저장하지 않는 새 blankqcow2에 runtime 읽기 전용 backing만 지정하는 합성 회귀까지 포함해 bridge v2는11/11 통과했다. 최종 SHA2177b9c2225e8f4f6d00924f62a7d1edc1fbf4711a06e9995ea9dfbb64ae485b만 사용한다. 원문 경로의 사전 reparse 거절도 포함한다.

독립 코드 검토에서 수명 예산·bridge 종료 판정·ThreadPool 대기·비동기 디스크 열거 경합을 발견했다. 새 manager는 NBD 잔여 수명에서 guest timeout을 계산하고, 결과 누락/bridge 실패는 전체 실패, source 오류는 export 전체 종료로 처리한다. manager 자체도 새 전용 Job에 제한(자식 포함4개·프로세스별512MiB·145초)하며 그 안의 NBD/guest별 제한도 유지한다. 초기 셸의 디스크 대기는10초 상한으로 새 파일을 만들었다. COW는 read-only guest 전후 전체SHA를 대조한다. Windows 커널 상태 때문에 모든 종료가 즉시 완료된다고 보장하지는 않는다. 새로운 시도는 이전 COW를 덮어쓰지 않는 새 경로에서만 진행한다.


### 14:45:10 KST — 고객 앱 메타데이터 읽기 범위

같은 읽기 전용 사본 단계에서 Docker컨테이너의 config.v2.json/hostconfig.json과 배포폴더 깊이2의 지정 compose/Caddyfile/Dockerfile만 최대200파일/원문4MiB로 RAM에 모아 private stdout으로 전달한다. .env는 선택하지 않는다. DockerEnv에는 비밀값이 있을 수 있어 base64본문과 원문환경값은 도구 출력/공유문서에 넣지 않는다. 수집 코드·경로·symlink/용량 경계를 부모가 읽었고 준비 측 sh구문/8개 정적경계 검증을 확인했다. 부모는 원격private파일을 Windows 표준 tar.extractfile/JSON으로만 읽고 파일실행/파일시스템전개를 하지 않는다. 기존 guest코드/Docker/network 실행0을 유지한다.


### 14:52:39 KST — 수집 상한 실패·운영 대상 선별

첫메타수집은 META_FILE_COUNT_LIMIT로아카이브출력전중단했다. 이전실제DockerList기록에는208개컨테이너가있어전체두JSON을모으면200파일을넘는다. 원본쓰기0·readonlyNBD2362읽기/오류0·COW읽기불변이며실패를보존했다. 상한을늘리는대신이전실제운영기록의고객API/worker/web/DB 정확Name4개만조용한선별로수집하고Windows정식JSON파싱에서exactName4개·중복/누락0·hostconfig쌍일치를확인한다. 후보스캔은최대1000config/각1MiB미만이며수집archive200파일/원문4MiB와구분한다. .env원문출력·고객코드실행·네트워크는0을유지한다.


## 15:00:52 KST — 새 독립 실행 OS·선택 자료 복사 단계

사용자승인125GB옛이미지1개삭제뒤F여유135.68GB를확보했다. 앞으로새상위작업폴더는해당기계F지침에따라기존작업영역하위에만만들고기존시험폴더는이동/삭제하지않는다. 앞선시험폴더작성때F루트지침을뒤늦게읽은한계도기록한다.

실제고객4컨테이너메타데이터와OCI이미지3종·고객PG17볼륨을확인했다. oldDockerdaemon을시작하면다른컨테이너/Swarm/plugin/AutoRemove를폭넓게다루므로이경로는선택하지않는다. 새공개Alpine실행OS와새Docker자료영역에선택이미지만가져온다.

공개OS준비는고객디스크0/원본VHD0/NBD0인새VM에서만한다. 검증된공개rootfs·설치커널/QEMU동일해시를쓰고virtio-net+userNAT로공식Alpine서명검증apk경로만사용한다. allow-untrusted/TLS/Windows보안우회금지,host포트전달0·모델/SSH/Windows서비스/레지스트리/PATH/예약변경0이다. Guest512MiB/1CPU부터·프로세스메모리상한1GiB/RSS768MiB·호스트가용3GiB이상·보관볼륨여유32GiB이상·OS용물리4GiB·회차600초상한을검증한다. 새blank64GiB qcow2의serial/크기/blank표식만확인하고그새장치에만파일시스템을만든다. 기존디스크attach/format명령은실행인자단계에서금지한다.

새OS에공개rootfs와최소Docker/containerd/runc/Python/e2fsprogs/인증서·네트워크도구만설치하고기존app/systemd/compose/Docker자동기동은없다. 공개서명패키지확인·새디스크전체기동/종료를확인한뒤고객자료복사를검토한다. 이미지manifest/configsha·compressedlayer합집합크기와DB/이동자료실측을먼저확보하고,8GB또는64GB가충분하다고미리확정하지않는다. 최종고객앱은source/NBD/VSS가없는실제기동으로독립성을검증한다.


## 15:08:10 KST — 선택 자료 실측·복사 계약

추가 읽기 전용 guest8/8·NBD2438회/오류0·COW전체SHA불변을 실제 확인했다. 선택한 OCI manifest3개는 모두정식containerd 저장소에있고해시/descriptor를확인했다. Docker의Image필드는이번환경에서OCIindex였으며configID라는초기해석을정정한다. index3→선택linuxamd64manifest3연결을검증했고실제configblob3은다음복사때별도SHA검증한다. 앞선parserKeyError실패파일을보존했다.

합집합44개compressedlayer는725,470,887B, 실제du는PG514,400KiB/이동자료224,216KiB/diagnostics24KiB/ops76KiB다. DB는PG17·control8192B다. 이는사본noload뷰의실측이며DBcrash recovery/자료누락없음/복사성공을뜻하지않는다.

다음복사는새독립OS디스크의새완전사본에만쓴다. source는같은고정VSS아래raw읽기전용bridge와새VHDXcontainerCOW다. 기존snapshot/원본에직접쓰지않는다. 공개코드로sourceCOW의ext4를ro,noexec로한번열어journal을새COW에만재생하고unmount후blockreadonly설정/ro,noload재마운트한다. 실패하면fsck/강제WAL초기화/원본fallback없이중단한다. 기존OS의실행파일/Docker/systemd는실행하지않는다.

새target장치는serial/크기/독립qcow2/noBacking으로확인한다. 선택blob의모든SHA/크기·자료복사전후목록/크기를검증하고DBtablespace/symlink와외부대상을확인한다. 고객secret은새private파일로만옮기고stdout/공유문서에쓰지않는다. 복사guestNIC0,목표512MiB/1CPU,전용Job1GiB/RSS768MiB·호스트가용3GiB·보관볼륨32GiB·새target물리8GiB부터보호한다. 회차1800초이내새bridge/helper를검증하고원문버전은보존한다. 작업자기존프로세스/모델은종료하지않는다.

복사종료뒤source/NBD/VSS/기존COW가없는새target부팅을통과해야독립자료복사로인정한다. 고객기동/공개는아직0이며원래WSL접속차단과중복worker방지후DB/API/web순으로검증한다.


### 15:14:00 KST — 공개 도구 실행 범위·원래 WSL 고객 통신 차단

새 독립 OS v2의 source 없는 부팅은 실제8/8 통과했다. Alpine3.24.2/Docker29.8.2/containerd2.3.7/runc1.4.3/Python3.14.8, guest512MiB/1CPU,9.362초/peakRSS394,584,064B다. 기존devtmpfs를중복마운트한검사실패v1/원문은보존했고,새v2에서만검사코드를고쳤다. 고객자료/Docker기동0이다.

복사 initramfs의JSON/hash검증을위해해시확인된이새공개OS v2의완전사본target에서공개Python/필수lib를RAM으로복사하고RAM에서만실행하는것을허용한다. target noexec마운트는유지한다. 원래고객Ubuntu/source의실행파일·스크립트·systemd·Docker실행은계속0이다. 공개runtime의출처/파일목록/SHA를private증거에남긴다.

고객앱기동전원래WSL에한정한네트워크차단을적용할수있다. 해당Windows의모든WSLcreator범위에새고유Outbound/Inbound AnyBlock priority1규칙2개와LoopbackEnabledFalse설정1개로제한한다. 현재Persistent/Active설정·전체WSL규칙/프로필을직전백업하고,원래로컬NotConfigured/유효True·localrule허용·이름충돌0·먼저평가되는TCP/AnyAllow0을확인한뒤적용한다. 적용중결과불명때재실행하지않고현재상태를조회한다. 기존규칙/일반Windows방화벽/서비스/모델/Windows재시작은변경하지않는다.

차단전후정확새2규칙필드와Persistent/Active Loopback을검증하고새SSH연결/WindowsOllama읽기응답을따로확인한다. 현재WSL포트0이면실제트래픽차단은미검증이다. 이방법은원래WSL로컬DB쓰기나AF_HYPERV/interop를막지못하며그렇다고보고하지않는다. 원복은새규칙2개만소유필드비교후제거하고Loopback을원래NotConfigured로복귀한다. 공용고객proxy는후속별도단일대상검증이필요하다.


## 15:14:50 KST — 원래 WSL 고객 통신 차단 정책 반영

WSL creator 범위에 새 inbound/outbound AnyBlock priority1 규칙2개와 LoopbackEnabled=False 설정1개, 총3/3을 반영했다. PersistentStore/ActiveStore 두 곳의 정확 필드와 EnforcementStatus1을 확인했다. 기존 설정·규칙·프로필은 비공개 XML/JSON으로 직전 보존했고 일반 Windows 방화벽/기존 규칙/서비스/Windows 부팅 시각은 바꾸지 않았다.

WSL 포트가0개이므로 실제 패킷 차단은 확인하지 못했다. 로컬 DB 쓰기·AF_HYPERV/interop 차단도 아니며 기존 가상환경 완전 종료라고 보고하지 않는다. 기존 vmwp Wait258·vmcompute start_pending이 계속된다. 새 SSH 연결은 성공했고 Windows 모델 직접 HTTP200/done/서울,0.86초,keep_alive=-1을 확인했다. 고객 API/웹은2/2 무응답으로 남았다.

근거: [정책 반영](../../scratch/chat-model-20261018/x600-wsl-fence-apply-20261018-151423.jsonl), [새 연결·모델·앱 재확인](../../scratch/chat-model-20261018/x600-recovery-checkpoint-20261018-151430.jsonl). 복사 bundle 준비 중이며 실제 고객 자료 복사·독립 고객 DB 기동·공개 경로는 아직 확인하지 않았다.


### 15:17:05 KST — 독립 검토 반영·긴 복사 감시 한계

긴 복사 실행안의 baseline/target 전체파일 RAM 적재를1MiB streaming SHA로 교정했다. manager/NBD/guest는 각각의 PID에 RSS768MiB/자기 Job commit 상한을 적용한다. 전체 Job 합산 RSS768MiB를 보장하지 않는다. 조회용 PowerShell은 outer Job의 프로세스별 commit1GiB와20초 timeout을 받으며 개별 RSS 감시는 하지 않는다.

복사 중30초마다 고정사본ID/State12/차등저장2GiB상한·사용1.5GiB미만·원본볼륨3GiB이상 여유를 다시 조회한다. 조회 실패/여유 위반 때 새 복사 guest와 읽기전달 bridge의 전용 Job만 종료하는 소유 flag를 쓰며 원래 Windows 프로세스를 종료하지 않는다. 그 중단 경로의 합성시험1/1,0.315초를 확인했다. 감시 사이 급격한 소멸을 방지한다고 보장하지 않으며, 실제 읽기오류는 bridge가 EIO로 전파해 전체복사 실패로 처리한다. snapshot 자동 재생성·원본 fallback은0이다. 성공 marker는 정확한 줄로 비교한다. marker만으로 내용무결성을 대체하지 않고 bundle에서 모든 선택 blob과 자료목록의 실제검증을 요구한다.


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


## 15:31:54 KST — source 없는 고객 실행 부팅·진단 콘솔 계약

선택복사 target 전체사본1,783,365,632B를 새실행용디스크에만 복제했고 원본/대상 streaming SHA 전후일치6240686088c8d6b74133ff818dafc3a00e83051725313c4fbb82140ec9faa678를 확인했다. 원래선택복사proof→새fullcopyproof의해시연결을기동직전다시확인한다. 이추이검증이성립하면주입helper는기존50blob/4트리SHA증거·합계와실제파일size/mode/uid/gid를대조하며큰자료전체SHA를TCG에서중복재계산하지않는다. 복사이후새고객자료변경은0이며증거SHA/작은주입파일SHA는계산한다.

주입회차는512MiB/1CPU·NIC0·새독립실행디스크1개/17자serial·기존init덮기0·guest종료로제한한다. 운영회차는source/NBD/VSS/initramfs 없이이디스크와공개커널로만부팅한다. 최초RAM1536MiB/CPU1,새QEMU단독Jobcommit3GiB/RSS2304MiB·호스트가용2GiB·보관볼륨여유32GiB·새작업전체물리16GiB를한계로한다. 이는동시다른작업의전체메모리사용을보장하는수치가아니며실제boot/DB/API/web RSS를확인한다.

복구중새guest만진단하기위해둘째직렬장치에관리자셸1개를추가한다. 이콘솔과주제어직렬/QMP는Windows loopback에만연결하며guest TCProot셸/외부공개관리포트는만들지않는다. 새guestRoot임의명령은복구운영진단에사용하며Windows/원래Ubuntu코드를실행하지않는다. PID1은직접자식을추적/회수하며콘솔종료후자동재시작하지않는다. 고객API8043/웹13000전달도처음에는Windowsloopback만사용하고DB5432전달은0이다.

고객앱이계속실행되도록Windows숨김백그라운드의새QEMU감독프로세스를사용할수있다. 이것은요청된제품앱실행이며에이전트예약/자동화등록이아니다. Windows서비스/레지스트리/시작프로그램/예약작업을만들지않고실제프로세스신원/시작시각/명령해시/loopback소유권을비공개기록한다. 자동재기동은0이다. 자원위반/소유중단요청때새guestDB/daemon의정상중지를먼저요청하고동일신원새QEMU만종료한다. 원래Windows프로세스/모델은종료하지않는다.

기존WSL고객통신차단3/3반영은유지한다. 공개ingress/DNS/Cloudflare/AWS/경유기계proxy는이부팅으로변경하지않는다. 기록상13:18공개경로는AWS였고현재외부설정은미확인이므로데이터연속성확인없이x600으로공개경로를전환하지않는다. 새guest이미지/DB검증후API/웹/모델API대체/통제안내를확인한다. 지키미전용앱은기동하지않는다.


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

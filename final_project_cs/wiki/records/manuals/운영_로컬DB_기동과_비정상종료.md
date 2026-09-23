# 운영 절차 — 로컬 PostgreSQL 기동과 비정상 종료

로컬 PostgreSQL 16.14(`127.0.0.1:5433`, conda env `pgv`, **Windows 서비스가 아니다**)가
정상 종료 기록 없이 여러 번 꺼졌다. 이 문서는 **무엇이 실제로 있었는지**(조사 결과)와
**되살리는 절차**, 그리고 **재발을 줄이는 제안**을 적는다.

기동 명령 자체와 환경 값은 [`wiki/operations/local-setup.md`](../../operations/local-setup.md)가 정본이다.
이 문서는 그 위에 **「안 떠 있을 때 무엇을 보고 어떤 순서로 손대나」**를 더한다.

---

## 0. 이 문서의 조사 범위 — 무엇을 보고 썼나

`[실측 2026-09-22]`

| 본 것 | 범위 |
|---|---|
| `…/data/pgdata/server_5433.log` | **13,912줄 전부.** 자르지 않고 `Select-String` 로 셌다 |
| `…/data/pgdata/server.log` | **9,201줄 전부.** 같은 데이터 디렉터리의 **다른 로그 파일**이다(§1) |
| Windows System·Application 이벤트 로그 | `Get-WinEvent`. **보존 범위 2026-09-10 01:18 ~ 2026-09-22 07:42** (순환 로그 20MB) |
| 살아 있는 `postgres.exe` 의 부모 사슬 | `Win32_Process` · `IsProcessInJob` 실측 |
| 예외 코드 뜻 | 이 기계의 Windows SDK 헤더 `…\Windows Kits\10\Include\10.0.26100.0\shared\ntstatus.h` 와 `um\winnt.h` 대조 |

### ★ 확인 못 한 것 (먼저 적는다)

- **2026-09-10 이전의 Windows 이벤트는 남아 있지 않다.** 이벤트 로그가 순환(Circular, 20MB)이라
  덮어써졌다. 그래서 8월과 9월 초의 재부팅·로그오프 여부는 **확인 못 했다.**
  「그때 재부팅이 없었다」고 말할 수 없다.
- **각 인스턴스가 정확히 몇 시에 죽었는지 모른다.** 소리 없이 사라진 경우 로그에 아무것도 안
  남는다. 다음 기동이 적는 `last known up at` 은 **마지막 체크포인트 시각**이라 **죽은 시각의
  하한선**일 뿐이다(놀고 있으면 체크포인트를 안 찍으므로 실제 사망은 훨씬 뒤일 수 있다).
- **Job object 의 `KILL_ON_JOB_CLOSE` 플래그는 확인 못 했다**(Job 핸들이 없으면 못 읽는다).
  §5-① 의 판정이 「유력」에서 멈추는 이유다.
- 프로세스 생성·종료 감사(Security 4688/4689)는 켜져 있지 않아 **누가 죽였는지는 어디에도 없다.**

---

## 1. 먼저 — 로그 파일이 **둘**이다

같은 데이터 디렉터리를 두 파일이 나눠 기록한다. **한쪽만 보면 역사가 끊긴다.**

```
…/_unified_mall_3/data/pgdata/server.log        2026-08-02 12:27 ~ 2026-09-10 15:47
…/_unified_mall_3/data/pgdata/server_5433.log   2026-08-13 12:13 ~ 현재
```

`pg_ctl … -l <파일>` 의 `-l` 에 무엇을 줬느냐로 갈린다. 2026-09-10 02:17 기동분은
`server.log` 에만 있어서 `server_5433.log` 만 보면 **09-09 ~ 09-14 가 통째로 빈 것처럼
보인다.** 실제로는 그 사이 09-10 02:17~15:47 에 인스턴스 하나가 더 돌았다.

→ **조사할 때는 두 파일을 같이 본다.**

---

## 2. 기동과 종료 — 전부

### 2-A. `server_5433.log` 의 인스턴스 13개 (자르지 않고 센 것)

`last known up at` = 다음 기동이 pg_control 에서 읽어 적은 **마지막 체크포인트 시각**.

| # | postmaster PID | 기동 | 마지막으로 남긴 줄 | 종료가 로그에 남았나 | 다음 기동이 말한 `last known up at` |
|---|---|---|---|---|---|
| 1 | 15024 | 08-13 12:13:21 | 08-15 04:12:38 `is shut down` | **남음** — 백엔드 `0xC000026B` → 재초기화 실패 | — |
| 2 | 27128 | 08-17 22:33:46 | 08-17 22:34:29 `ready` | **없음** | 08-18 22:31:13 |
| 3 | 23852 | 08-19 11:28:38 | 08-19 23:53:09 `is shut down` | **남음** — `0xC0000142` | 08-19 17:39:35 |
| 4 | 10992 | 08-20 01:04:51 | 08-22 00:14:42 `is shut down` | **남음** — `0xC0000142` | 08-20 13:59:18 |
| 5 | 30576 | 08-24 10:40:38 | 08-25 10:45:21 `is shut down` | **남음** — `0xC000012D` 뒤 `0xC0000142` | 08-25 10:44:43 |
| 6 | 27520 | 08-28 15:44:39 | 09-05 20:03:24 `is shut down` | **남음** — `0xC0000142` | 09-05 16:19:38 |
| 7 | 5892 | 09-06 00:38:30 | 09-08 20:14:48 `is shut down` | **남음** — `0xC000012D` 4회 | 09-08 20:14:35 |
| 8 | 26416 | 09-09 03:28:30 | 09-10 00:09:39 `ready` | **없음** | 09-10 00:09:39 (`server.log` 의 09-10 02:17 기동이 적음) |
| — | 5656 | 09-10 02:17:56 (`server.log`) | 09-10 15:47:41 체크포인트 | **없음** | 09-10 15:47:41 |
| 9 | 2480 | 09-14 09:50:44 | 09-15 06:47:33 `is shut down` | **남음** — WAL writer `0x40010004` | 09-15 06:32:35 |
| 10 | 4328 | 09-17 04:07:05 | 09-17 04:08:02 `ready` | **없음** | 09-17 05:38:44 |
| 11 | 13620 | 09-17 14:48:13 | 09-17 14:48:58 `ready` | **없음** | 09-17 15:19:03 |
| 12 | 8932 | 09-18 13:57:34 | 09-18 13:58:21 `ready` | **없음** | 09-18 14:53:27 |
| 13 | 20028 | 09-21 00:07:04 | **지금 실행 중** | — | — |

★ **질문에 적힌 네 시각(09-15 06:47 · 09-17 05:38 · 09-17 15:19 · 09-18 14:53)은
「기동 시각」이 아니라 이 표의 `last known up at` 이다.** 그래서 로그의 `starting PostgreSQL`
시각과 45분~1시간쯤 어긋나 보인다. 어긋난 게 아니라 **다른 값**이다.

### 2-B. 센 것 (두 파일 합산, 자르지 않음)

| 항목 | 건수 |
|---|---|
| `starting PostgreSQL` | **26** |
| `database system was not properly shut down` | **28** (`server_5433.log` 19 + `server.log` 9) |
| `terminated by exception` | **18** |
| `received fast/smart/immediate shutdown request` (= 정상 종료) | **3** — 전부 2026-08-02·08-10·08-13. **08-13 12:13:17 이후 0건** |
| `could not reserve shared memory region … error code 487` | **52** |
| `could not fork …` | **231** (연결용 157 · autovacuum 71 · 기타 3) |
| `sharing violation` + `You might have antivirus…` HINT | **각 19** |

---

## 3. 예외 코드가 무엇을 뜻하나 — 추측이 아니라 헤더 대조

`[실측]` 이 기계의 `ntstatus.h` · `winnt.h` 에서 그대로 옮긴 것이다.

| 코드 | 헤더의 이름 | 뜻 | 두 파일 합산 |
|---|---|---|---|
| `0xC000012D` | `STATUS_COMMITMENT_LIMIT` | **커밋 한도 고갈** — 메모리+페이지파일이 동났다 | 8 |
| `0xC0000142` | `STATUS_DLL_INIT_FAILED` | 프로세스가 DLL 초기화에 실패해 못 떴다 | 6 |
| `0xC000026B` | `STATUS_DLL_INIT_FAILED_LOGOFF` | 같은 실패인데 **원인이 「윈도 스테이션이 내려가는 중」** | 2 |
| `0xC000013A` | `STATUS_CONTROL_C_EXIT` | **Ctrl+C / 콘솔 닫힘**으로 끝났다 | 1 |
| `0x40010004` | `DBG_TERMINATE_PROCESS` | **바깥에서 강제 종료**됐다 | 1 |

★ 이 18건은 **전부 자식 프로세스**(백엔드·checkpointer·WAL writer)다. postmaster 는 살아서
crash recovery 를 돌렸고, 그 재초기화가 실패했을 때만 postmaster 까지 내려갔다
(`server_5433.log` 에서 7번: 08-15 · 08-19 · 08-22 · 08-25 · 09-05 · 09-08 · 09-15).

---

## 4. 가설별 판정

### ① 「DB 를 띄운 셸 세션이 끝날 때 자식이 함께 죽는다」 → **가장 유력. 확정 못 함**

**지지**

- 지금 도는 postmaster 의 부모 사슬이 **정확히 그 위험한 모양**이다 `[실측 2026-09-22]`:

  ```
  bash.exe (3656)          ← Claude Code 의 Bash 도구가 띄운 셸. 31시간째 살아 있다
    └ conhost.exe (17568)  ← 콘솔이 여기 붙어 있다
    └ pg_ctl.exe (9524)    ← 이미 종료됨
        └ cmd.exe (19492)  ← pg_ctl 이 만든 래퍼. `… < nul >> server_5433.log 2>&1`
            └ postgres.exe (20028)   ← 지금 5433 을 듣고 있는 그 프로세스
  ```

  DB 가 **한 번의 도구 호출이 만든 콘솔에 매달려 있다.**
- `postgres.exe(20028)` · `cmd.exe(19492)` · `bash.exe(3656)` **전부 Job object 안에 있다**
  (`IsProcessInJob` 실측).
- 로그가 **콘솔·세션 파괴를 직접 지목한 적이 있다** — `STATUS_DLL_INIT_FAILED_LOGOFF` 2건,
  `STATUS_CONTROL_C_EXIT` 1건. 둘 다 「창/세션이 내려가는 중」에만 나오는 코드다.
- **인스턴스 #11(09-17 14:48 기동)은 재부팅도 절전도 크래시도 없이 사라졌다.**
  그 구간(09-17 05:47:24 부팅 ~ 09-20 23:12:44 재부팅) 내내 OS 는 계속 떠 있었고,
  09-17 14:40~09-18 14:10 의 System 오류·경고는 **6건뿐이며 전부 무관**하다
  (Wi-Fi 드라이버 정보 3 · 시간 동기화 DNS 실패 1 · Windows Update 설치 실패 1 등).
  → **바깥에서 무언가 죽였다는 뜻인데, 그게 무엇인지 기록이 없다.**

**반박 · 한계**

- Job 에 속해 있다는 사실만으로 「Job 이 닫히면 죽는다」가 되지 않는다.
  `KILL_ON_JOB_CLOSE` 플래그는 **확인 못 했다.** Windows 11 은 많은 프로세스를 기본적으로 Job 에 넣는다.
- `pg_ctl.exe(9524)` 가 빠졌는데도 postgres 는 살아남았다.
  → **직계 부모가 죽는 것만으로는 안 죽는다.**

**판정 — 지지 증거가 가장 많지만 확정할 수 없다. 죽는 순간을 기록한 것이 하나도 없기 때문이다.**

### ② 「사용자가 껐다」 → **`pg_ctl stop` 형태로는 반박. 재부팅 형태로는 지지**

- **반박** — 정상 종료(`received fast/smart/immediate shutdown request`)는
  **2026-08-13 12:13:17 이후 0건**이다(두 파일 전체를 자르지 않고 셌다).
  전체 역사에서 3건뿐이고 전부 8월 초다. → **`pg_ctl stop` 으로 껐을 가능성은 없다.**
- **지지(다른 형태)** — 조사 범위 안의 재부팅 7건 중 **3건은 사용자가 직접 걸었다.**
  이벤트 1074 가 `Explorer.EXE` 가 `playdata\playdata2` 를 대신해 요청했다고 적는다 —
  **09-11 09:54:49 · 09-15 06:47:31 · 09-20 23:12:21.**
- **확인 못 함** — 창을 닫았거나 Ctrl+C 를 눌렀거나 작업 관리자로 죽인 경우.
  어느 로그에도 안 남는다. `STATUS_CONTROL_C_EXIT` 1건(08-02)이 유일한 흔적인데
  이건 이벤트 로그 보존 범위 밖이라 대조할 수 없다.

### ③ 「크래시」 → **지지. 단 층이 다르다 — 이 사건들은 로그에 또렷이 남았다**

예외 종료 18건은 **postmaster 가 아니라 자식**이 죽은 것이고, 기록이 **또렷이 남아 있다.**
질문이 말한 「정상 종료 기록 없이 꺼졌다」와는 **다른 사건**이다. 섞어 보면 안 된다.

뒷받침하는 실측:

- **메모리 고갈** — Windows `Resource-Exhaustion-Detector`(이벤트 2004)가 조사 범위 안에서
  **52건** 울렸다. 특히 **09-14 12:54:26 의 2004 는 같은 초의 `0xC000012D` 크래시와 초 단위로 일치**한다.
  기계 값: 물리 메모리 **15.7GB** · 커밋 한도 **21.8GB** · 페이지파일 **고정 6,184MB
  (자동 관리 꺼짐)**. 2004 이벤트가 이름을 댄 상위 소비자는 `claude.exe` · `msedge.exe` ·
  `ChatGPT.exe` · `python.exe` · `mysqld.exe` 다.
- **fork 실패 231건** — `could not fork new process for connection` 157 ·
  `could not fork autovacuum worker` 71 · 기타 3.
- **안티바이러스 간섭** — PostgreSQL 자신이 19번 이렇게 적었다:
  `could not open file "./server_5433.log": sharing violation` +
  `HINT: You might have antivirus, backup, or similar software interfering with the database system.`
  그리고 `could not reserve shared memory region … error code 487` 이 **52건**이다.
  이 기계에는 실시간 검사기가 **둘** 등록돼 있다 — **Windows Defender · McAfee VirusScan**
  (`root\SecurityCenter2` 조회).

### ④ 「절전·재부팅」 → **재부팅은 강하게 지지(네 시각 중 둘을 설명). 절전은 반박**

| 시각 | 판정 | 근거 |
|---|---|---|
| **09-15 06:47** | **확정 — 사용자 재부팅** | 1074 재부팅 요청이 **06:47:31**(Explorer.EXE, playdata2) → **2초 뒤** 06:47:33 WAL writer `0x40010004`(DBG_TERMINATE_PROCESS) |
| **09-17 05:38** | **거의 확정 — Windows Update 재부팅** | `last known up` 05:38:44 뒤 **5분 31초** 만에 재부팅 3연속: 05:44:15 `MoUsoCoreWorker.exe`(Windows Update) · 05:46:21 · 05:47:00 `TrustedInstaller.exe` |
| **09-17 15:19** | **④ 로 설명 안 됨** | 그 구간에 **재부팅 0건.** OS 는 09-17 05:47:24 부팅 후 09-20 23:12 까지 계속 떠 있었다 → §5-① 로 간다 |
| **09-18 14:53** | **구분 못 했다** | 재부팅은 09-20 23:12:21 하나뿐인데 **2일 뒤**다. 그때 죽었는지 그 전에 죽었는지 **확인 못 했다** |

- **절전은 반박** — `Kernel-Power 42`(절전 진입) · `107`·`Power-Troubleshooter 1`(복귀) ·
  `Kernel-Power 41`(더티 셧다운) · `6008`(예기치 않은 종료)이 **전부 0건**이다.
  조사 범위는 **2026-09-10 01:20 ~ 2026-09-22 07:42**. **그 이전은 확인 못 했다.**

### 요약

| 가설 | 판정 |
|---|---|
| ① 세션 종료와 함께 죽는다 | **유력 — 09-17 15:19 건은 이것 말고 설명이 없다. 다만 확정 못 했다** |
| ② 사용자가 껐다 | `pg_ctl stop` 은 **반박(0건)** · 재부팅으로는 **지지(3건)** · 창 닫기/Ctrl+C 는 **확인 못 함** |
| ③ 크래시 | **지지 — 단 이건 로그에 남은 다른 사건이다.** 원인은 커밋 한도 고갈과 AV 간섭 |
| ④ 절전·재부팅 | 재부팅 **지지(09-15·09-17 05:38 확정)** · 절전 **반박(0건, 09-10 이후 범위)** |

---

## 5. 되살리는 절차

★ **끄지 않는다.** 이 클러스터는 A-COP 만의 것이 아니다 — 같은 데이터 디렉터리에
옆 프로젝트 DB 가 함께 있다([`local-setup.md`](../../operations/local-setup.md) §「알아야 할 것」).

### 5-1. 먼저 본다 — 정말 안 떠 있나

```powershell
Get-NetTCPConnection -State Listen -LocalPort 5433 -ErrorAction SilentlyContinue |
  Select-Object LocalAddress, LocalPort, OwningProcess
```

나오면 **떠 있는 것이다. 아무것도 하지 마라.** 안 나오면 다음으로.

### 5-2. ★ 낡은 `postmaster.pid` 가 남았나 — 여기서 조용히 막힌다

`[실측 2026-09-21]` **실제로 겪었다.** 죽은 PID **8932**(09-18 13:57 기동분)의
`postmaster.pid` 가 남아 있어 `pg_ctl` 이 **조용히 실패했다.**

★ **그때 `server_5433.log` 에는 `lock file` · `another postmaster` 계열 줄이 한 줄도
안 남았다**(두 파일 전체를 자르지 않고 센 결과 **0건**). 즉 **로그만 보면 왜 실패했는지
알 수 없다.** 거절 메시지가 `pg_ctl` 자신의 표준출력으로 나가는데, 그걸 파이프로
받아 버리면(`… | tail -10`) 눈에 안 보인다 `[해석 — 확인 못 함]`.

**확인**

```powershell
$data = "C:\Users\playdata2\Documents\llm_workspace\_unified_mall_3\data\pgdata"
Get-Content "$data\postmaster.pid"            # 첫 줄이 PID
$pidInFile = (Get-Content "$data\postmaster.pid")[0]
Get-CimInstance Win32_Process -Filter "ProcessId=$pidInFile" |
  Select-Object ProcessId, Name, CreationDate
```

| 결과 | 뜻 | 할 것 |
|---|---|---|
| 프로세스가 **없다** | 낡은 파일이다 | 5-3 의 **비켜 두기** |
| `postgres.exe` 로 **있다** | **DB 가 떠 있다** | 손대지 마라. 5-1 을 다시 본다 |
| **다른 이름**으로 있다 (`chrome.exe` 등) | 재부팅 뒤 **PID 가 재사용**된 것이다. 낡은 파일이다 | 5-3 의 **비켜 두기** |

★ 셋째 줄이 함정이다. 재부팅하면 PID 는 얼마든지 재사용된다.
**PID 숫자만 보고 「돌고 있네」라고 판단하지 않는다 — 프로세스 이름까지 본다.**

### 5-3. 낡은 `postmaster.pid` 는 **지우지 말고 비켜 둔다**

```powershell
$data = "C:\Users\playdata2\Documents\llm_workspace\_unified_mall_3\data\pgdata"
$stamp = Get-Date -Format 'yyyyMMdd_HHmm'
Rename-Item "$data\postmaster.pid" "postmaster.pid.stale_$stamp"
```

**지우지 않는 이유** — 그 안의 PID·기동 시각이 **다음 조사의 유일한 단서**다.
2026-09-21 에 남긴 `postmaster.pid.stale_20260921`(PID 8932) 덕분에 이 문서의 §2-A 표
12번 줄을 확정할 수 있었다.

★ **5-2 에서 「`postgres.exe` 로 살아 있다」가 나오면 절대 이 단계로 오지 않는다.**
살아 있는 서버의 `postmaster.pid` 를 치우면 그 서버가 다음 재기동 때 망가진다.

### 5-4. 기동

```powershell
$bin  = "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin"
$data = "C:\Users\playdata2\Documents\llm_workspace\_unified_mall_3\data\pgdata"
& "$bin\pg_ctl.exe" -D $data -o "-p 5433" -l "$data\server_5433.log" -w start
```

| 주의 | |
|---|---|
| **`-o "-p 5433"` 를 빠뜨리면 5432 로 뜬다** | `postgresql.conf` 에 `port` 가 없다. 2026-08-13 에 실제로 당했다 |
| **`-l` 은 늘 `server_5433.log` 로 준다** | 파일을 바꾸면 §1 처럼 역사가 두 곳으로 쪼개진다 |
| **느려도 기다린다** | 기동 때 `syncing data directory (fsync)` 가 돈다. 실측 **46.67초**(09-18) 걸린 적이 있다 |
| **출력을 파이프로 먹지 않는다** | `\| tail` 로 받으면 5-2 의 거절 메시지가 사라진다 |

### 5-5. 기동 후 확인 — 로그에서 이 네 줄을 본다

```powershell
Get-Content "$data\server_5433.log" -Tail 30
```

| 보이는 줄 | 뜻 |
|---|---|
| `database system was interrupted; last known up at <시각>` | **그 시각이 지난번에 살아 있던 마지막 순간**이다. 적어 둔다 — 원인 추적의 출발점 |
| `database system was not properly shut down; automatic recovery in progress` | 정상이다. crash recovery 가 도는 중 |
| `redo starts at … / redo done at …` | 복구 완료 |
| **`database system is ready to accept connections`** | **여기까지 나와야 끝난 것이다** |

★ `ready` 가 안 나왔는데 `shutting down due to startup process failure` 가 보이면
**재초기화가 실패한 것이다**(§2-A 에서 7번 있었다). 이때는 다시 `start` 를 걸기 전에
**메모리 여유부터 본다**(§6-1) — 커밋 한도가 동난 상태에서 재시도하면 같은 자리에서 또 죽는다.

### 5-6. 데이터 확인

건수를 대조하고 작업을 재개한다. 정본은 [`local-setup.md`](../../operations/local-setup.md) §「기동 후」.
★ **`pg_ctl` 이 200 을 냈다는 것만으로 「됐다」고 하지 않는다.** §5-5 의 `ready` 줄과 건수를 본다.

---

## 6. 재발을 줄이는 방법

★ **아래는 전부 제안이다. 이 조사에서는 시스템 설정을 하나도 바꾸지 않았다**
(서비스 등록·작업 스케줄러 생성·레지스트리 수정 없음, DB 재기동 없음).
고칠지 말지는 사람이 정한다.

### 6-1. 지금 당장 할 수 있는 것 — 띄우는 방법을 바꾼다

**문제의 뿌리는 「어디에서 띄우느냐」다.** §4-① 이 보여주듯 지금 DB 는
**에이전트 도구 호출이 만든 콘솔**에 매달려 있다. 그 콘솔이 사라지면 DB 도 사라지고,
**사라지는 순간을 아무도 기록하지 않는다.**

| 제안 | 무엇이 나아지나 | 대가 |
|---|---|---|
| **A. 사람이 연 터미널에서 직접 띄운다** | 에이전트 세션·도구 호출 수명과 끊어진다. 오늘 바로 할 수 있다 | 그 터미널을 닫으면 똑같이 죽는다. **재부팅 뒤 수동 기동은 그대로** |
| **B. Windows 서비스로 등록한다** (`pg_ctl register`) | 세션·콘솔과 완전히 끊긴다. **재부팅 뒤 자동 기동**되고, 정상 종료 경로가 생겨 「기록 없는 죽음」이 사라진다 | 관리자 권한 필요. 계정·권한·데이터 디렉터리 ACL 을 정해야 한다. **옆 프로젝트와 공유하는 클러스터**라 영향 범위를 먼저 합의해야 한다 |
| **C. 작업 스케줄러에 「시작할 때」 트리거로 등록** | 재부팅 뒤 자동 기동. B 보다 가볍다 | 서비스가 아니라 **정상 종료 보장이 없다.** 죽어도 알려 주지 않는다 |

★ **B 를 권한다.** ②·④ 에서 확정된 원인(재부팅)과 ① 에서 유력한 원인(세션 종료)을
**한 번에** 없앤다. 다만 **지금 바꾸지 않았다** — 공유 클러스터라 팀 합의가 먼저다.

### 6-2. 메모리 — `0xC000012D` 8건의 원인

- 페이지파일이 **고정 6,184MB**이고 자동 관리가 **꺼져 있다.** 물리 15.7GB + 페이지파일로
  커밋 한도가 **21.8GB** 인데, 2004 이벤트가 **52건** 울렸다.
- **제안** — 페이지파일을 시스템 관리로 돌리거나 상한을 올린다. `[설정 안 바꿨다]`
- **제안** — DB 를 띄워 둔 채로 LLM·브라우저·빌드를 같이 돌리지 않는다.
  2004 이벤트가 이름을 댄 상위 소비자가 매번 그것들이었다.

### 6-3. 안티바이러스 — `error code 487` 52건 · `sharing violation` 19건

- 실시간 검사기가 **둘**(Windows Defender · McAfee VirusScan) 걸려 있다.
  PostgreSQL 이 직접 「안티바이러스가 간섭하고 있을 수 있다」고 19번 적었다.
- **제안** — 데이터 디렉터리와 `pgv` 환경의 `bin` 을 실시간 검사 **제외**에 넣는다.
  `[설정 안 바꿨다 — 보안 정책이라 사람이 정한다]`
- **제안** — 검사기 둘을 함께 쓰는 게 의도한 것인지 확인한다.

### 6-4. 죽는 순간을 기록하게 만든다

지금은 **죽으면 아무것도 안 남는다.** 그게 이 조사가 ① 을 확정하지 못한 이유다.
비용 없이 할 수 있는 것:

- **`postmaster.pid` 를 지우지 말고 비켜 둔다**(§5-3). 이미 한 번 효과를 봤다.
- **기동할 때마다 `last known up at` 을 적어 둔다.** 죽은 시각의 하한선이 그것뿐이다.
- `logging_collector` 와 `log_line_prefix` 를 손보면 로그 회전·추적이 쉬워진다.
  `[제안 — `postgresql.conf` 는 손대지 않았다. 공유 클러스터다]`

---

## 7. 이 문서가 말하지 않는 것

- **인스턴스 #11(09-17 15:19)과 #12(09-18 14:53)를 무엇이 죽였는지 모른다.**
  재부팅·절전·크래시는 배제했지만(#11), **무엇이 죽였는지는 확인 못 했다.**
- **2026-09-10 이전은 Windows 쪽 증거가 없다.** 이벤트 로그가 덮어써졌다.
- **`pg_ctl register`(서비스 등록)를 해 본 적이 없다.** §6-1 B 는 **제안이지 검증된 절차가 아니다.**

---

## 관계

- [`wiki/operations/local-setup.md`](../../operations/local-setup.md) — 기동 명령·환경 값의 정본
- [`wiki/operations/troubleshooting.md`](../../operations/troubleshooting.md) §1 — 「DB 연결이 안 된다」 진입점
- [`2026-08-12_1520_환경_기동절차.md`](2026-08-12_1520_환경_기동절차.md) — 최초 기동 절차(2026-08-13 실측)

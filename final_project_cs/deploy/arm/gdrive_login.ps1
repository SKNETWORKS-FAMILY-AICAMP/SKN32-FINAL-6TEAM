# 구글 드라이브 읽기 전용 로그인을 한 번 만들어 오라클 ARM 서버로 보낸다(사람이 이 PC 에서 직접 실행한다).
#   사용: powershell -ExecutionPolicy Bypass -File deploy\arm\gdrive_login.ps1
#   하는 일: rclone 준비 → 브라우저에서 구글 로그인(읽기 전용 권한) → 로그인 정보를 서버 control 폴더로 복사 → 이 PC 사본 삭제 → 첫 동기화 시작
#   로그인 정보는 화면에 찍지 않는다. 저장소에도 넣지 않는다.
param(
    [string]$SshHost = "dr-a2",
    [string]$ServerConf = "/home/ubuntu/tripilot-serving/control/rclone-gdrive.conf"
)
$ErrorActionPreference = "Stop"

if (-not (Get-Command rclone -ErrorAction SilentlyContinue)) {
    Write-Host "rclone 이 없어 winget 으로 설치합니다..."
    winget install --id Rclone.Rclone -e --accept-source-agreements --accept-package-agreements
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not (Get-Command rclone -ErrorAction SilentlyContinue)) {
        throw "rclone 설치 뒤에도 명령을 못 찾았습니다. PowerShell 창을 새로 열고 다시 실행하세요."
    }
}

$tmp = Join-Path $env:TEMP ("tripilot-gdrive-" + [guid]::NewGuid().ToString("N") + ".conf")
try {
    Write-Host "브라우저가 열리면 dataset 폴더를 볼 수 있는 구글 계정으로 로그인하고 '허용'을 누르세요."
    # 읽기 전용(drive.readonly). 폴더 ID 는 서버 설정(/etc/tripilot-arm-dataset-sync.env)에 있으므로 여기서는 로그인만 만든다.
    rclone config create tripilot_gdrive drive scope=drive.readonly --config $tmp | Out-Null
    if (-not (Select-String -Path $tmp -Pattern '^token\s*=' -Quiet)) {
        throw "로그인이 끝나지 않았습니다(설정에 token 이 없음). 다시 실행하세요."
    }
    scp -q $tmp "${SshHost}:$ServerConf"
    ssh $SshHost "chmod 600 '$ServerConf' && sudo systemctl start --no-block tripilot-arm-dataset-sync.service"
    Write-Host "완료: 오라클 서버로 로그인 정보를 보냈고 첫 동기화를 시작했습니다."
    Write-Host "확인: ssh $SshHost cat /home/ubuntu/tripilot-serving/dataset-sync.json"
}
finally {
    if (Test-Path $tmp) { Remove-Item $tmp -Force }
}

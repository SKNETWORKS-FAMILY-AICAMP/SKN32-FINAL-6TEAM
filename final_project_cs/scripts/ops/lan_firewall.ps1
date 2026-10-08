# triPilot — 같은 공유기의 다른 기기가 이 PC 의 웹앱 · API 에 들어올 수 있게 윈도 방화벽에 **들어오는 연결 허락 규칙 하나**를 더한다.
#
# ★관리자 PowerShell 에서 직접 실행한다(보안 설정이라 자동으로 하지 않는다):
#     powershell -ExecutionPolicy Bypass -File scripts\ops\lan_firewall.ps1            # 규칙 더하기
#     powershell -ExecutionPolicy Bypass -File scripts\ops\lan_firewall.ps1 -Remove    # 규칙 지우기(다 쓴 뒤)
# ★범위를 좁혔다: TCP 두 포트만 · 같은 서브넷(같은 공유기에 붙은 기기)에서 온 연결만. 공유기 밖(인터넷)에서는 안 닿는다.
#   다만 같은 공유기에 붙은 **모든** 기기가 대상이다 — 남이 같이 쓰는 공유기(학원 · 공용 Wi-Fi)에서는 쓰는 동안만 열고 다 쓰면 -Remove 로 지운다.
# ★「공용 네트워크(Public)」로 잡힌 Wi-Fi 에서도 열리게 프로필을 Any 로 뒀다 — 집·내 방 공유기가 아니면 켜 두지 않는다.
#Requires -RunAsAdministrator
param(
  [int[]]$Port = @(3110, 8043),
  [switch]$Remove
)
$name = 'triPilot LAN (web+api)'
if ($Remove) {
  Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue | Remove-NetFirewallRule
  Write-Host "규칙 '$name' 을 지웠다"
  return
}
if (Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue) { Get-NetFirewallRule -DisplayName $name | Remove-NetFirewallRule }
New-NetFirewallRule -DisplayName $name -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -RemoteAddress LocalSubnet -Profile Any | Out-Null
Write-Host "규칙 '$name' 을 더했다 — TCP $($Port -join ', ') · 같은 서브넷에서 온 연결만"

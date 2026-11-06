"""Offline launcher regression; no app import, socket, DB or service launch.

Run directly: python tools/tests/test_local_launcher.py
Temporary files stay beneath HERMES_LAUNCHER_TEST_DIR (required).
"""
from pathlib import Path
import json
import os
import subprocess
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]
BATCH = ROOT / "triPilot-실행.bat"


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(os.environ["HERMES_LAUNCHER_TEST_DIR"]) / uuid.uuid4().hex
        self.root.mkdir(parents=True)
        for name in ("app/ops_entrypoint.py", "frontend/apps/web/node_modules/next/dist/bin/next",
                     "frontend/apps/admin/node_modules/next/dist/bin/next"):
            path = self.root / "final_project_cs" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        self.env = {**os.environ, "TRIPILOT_ROOT": str(self.root), "TRIPILOT_ACTION": "check",
                    "USERPROFILE": str(self.root / "empty-profile")}

    def run_body(self, *, legacy=False, missing_admin=False):
        if legacy:
            starter = Path(self.env["USERPROFILE"]) / ".acop-ops/start-acop.ps1"
            starter.parent.mkdir(parents=True)
            starter.write_text("throw 'MUST NOT RUN'", encoding="utf-8")
        if missing_admin:
            self.root.joinpath("final_project_cs/frontend/apps/admin/node_modules/next/dist/bin/next").unlink()
        body = BATCH.read_text(encoding="utf-8").split("\n#==POWERSHELL==", 1)[1]
        # Refuse every side effect; check must not call even a readiness socket.
        guards = """function Start-Process { throw 'SIDE_EFFECT_START' }
function Get-Process { throw 'SIDE_EFFECT_PROCESS_QUERY' }
function New-Item { throw 'SIDE_EFFECT_WRITE' }
function taskkill.exe { throw 'SIDE_EFFECT_KILL' }
function Get-Command { param($Name) return @{Source=$Name} }
"""
        harness = self.root / "check.ps1"
        harness.write_text(guards + body, encoding="utf-8-sig")
        result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness)],
                                env=self.env, capture_output=True, timeout=20)
        return result, (result.stdout + result.stderr).decode("utf-8", errors="replace")

    def test_clean_profile_plans_all_four_services_without_private_starter(self):
        result, output = self.run_body()
        self.assertEqual(result.returncode, 0, output)
        for port in (8042, 8070, 3100, 3300):
            self.assertIn(str(port), output)
        self.assertFalse((self.root / ".tmp").exists())

    def test_existing_legacy_starter_is_preserved_but_never_run_by_check(self):
        result, output = self.run_body(legacy=True)
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn("MUST NOT RUN", output)

    def test_missing_admin_dependencies_fail_before_any_launch(self):
        result, output = self.run_body(legacy=True, missing_admin=True)
        self.assertEqual(result.returncode, 1, output)
        self.assertNotIn("SIDE_EFFECT", output)

    def test_batch_bootstrap_handles_git_lf_and_windows_crlf(self):
        text = BATCH.read_text(encoding="utf-8")
        command = text.split('-Command "', 1)[1].split('" && exit /b', 1)[0]
        for newline in ("\n", "\r\n"):
            batch = self.root / ("lf.bat" if newline == "\n" else "crlf.bat")
            batch.write_bytes(text.replace("\n", newline).encode("utf-8"))
            result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                     "-Command", command],
                                    env={**self.env, "TRIPILOT_BATCH": str(batch)},
                                    capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, (newline, result.stdout, result.stderr))
            self.assertIn(b"3300", result.stdout)
            self.assertFalse((self.root / ".tmp").exists())

    def test_launch_path_uses_real_plans_and_does_not_own_existing_listener(self):
        body = BATCH.read_text(encoding="utf-8").split("\n#==POWERSHELL==", 1)[1]
        begin = body.index("function Open-Port")
        end = body.index("function Save-State", begin)
        body = body[:begin] + """function Open-Port([int]$port) {
    if ($port -eq 3100) { return $true }
    return $script:startedPorts.Contains($port)
}
""" + body[end:]
        harness = self.root / "launch-mocked.ps1"
        guards = """$script:startedPorts = [Collections.Generic.HashSet[int]]::new()
$script:launches = @()
function Get-Command { param($Name) return @{Source=$Name} }
function Start-Process {
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle, [switch]$PassThru,
          $RedirectStandardOutput, $RedirectStandardError)
    $port = [int]([IO.Path]::GetFileName($RedirectStandardOutput).Split('-')[-1].Split('.')[0])
    $script:startedPorts.Add($port) | Out-Null
    $script:launches += @{Port=$port; Exe=$FilePath; Args=$ArgumentList; Dir=$WorkingDirectory}
    ConvertTo-Json -InputObject @($script:launches) | Set-Content -LiteralPath $env:LAUNCH_CAPTURE
    return [pscustomobject]@{Id=(900000+$port); StartTime=[datetime]::UtcNow; HasExited=$false}
}
function taskkill.exe { throw 'MUST_NOT_KILL' }
"""
        harness.write_text(guards + body, encoding="utf-8-sig")
        capture = self.root / "captured.json"
        result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                 "-File", str(harness)],
                                env={**self.env, "TRIPILOT_ACTION": "", "LAUNCH_CAPTURE": str(capture)},
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 1, (result.stdout, result.stderr))
        self.assertFalse(capture.exists())
        self.assertFalse((self.root / '.tmp/local-services/processes.json').exists())

    def test_stop_only_kills_matching_owned_pid_and_start_time(self):
        state = self.root / ".tmp/local-services/processes.json"
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps([
            {"Name": "owned", "Id": 900001, "StartTicks": "638000000000000000", "Order": 1},
            {"Name": "reused", "Id": 900002, "StartTicks": "1", "Order": 2},
            {"Name": "gone", "Id": 900003, "StartTicks": "1", "Order": 3},
        ]), encoding="utf-8")
        capture = self.root / "killed.txt"
        guards = """function Get-Process {
    param($Id)
    if ($Id -eq 900003) { return $null }
    return [pscustomobject]@{StartTime=[datetime]::new(638000000000000000, [DateTimeKind]::Utc)}
}
function taskkill.exe {
    $args[1] | Add-Content -LiteralPath $env:KILL_CAPTURE
    $global:LASTEXITCODE = 0
}
function Start-Process { throw 'MUST_NOT_START' }
"""
        body = BATCH.read_text(encoding="utf-8").split("\n#==POWERSHELL==", 1)[1]
        harness = self.root / "stop-mocked.ps1"
        harness.write_text(guards + body, encoding="utf-8-sig")
        result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness)],
                                env={**self.env, "TRIPILOT_ACTION": "stop", "KILL_CAPTURE": str(capture)},
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
        self.assertTrue(capture.exists(), (result.stdout, result.stderr, state.read_text(encoding="utf-8-sig")))
        self.assertEqual(capture.read_text().strip(), "900001")
        self.assertEqual(json.loads(state.read_text(encoding="utf-8-sig")), [])

    def run_boundary(self, case):
        body = BATCH.read_text(encoding='utf-8').split('\n#==POWERSHELL==', 1)[1]
        begin = body.index('function Open-Port')
        end = body.index('function Save-State', begin)
        body = body[:begin] + body[end:]
        guards = r'''
$script:started = [Collections.Generic.HashSet[int]]::new()
$script:processes = @{}
$script:launches = @()
function Get-Command { param($Name) return @{Source=$Name} }
function Open-Port([int]$port) {
    if ($env:BOUNDARY_CASE -eq 'unrelated') { return $true }
    if ($env:BOUNDARY_CASE -eq 'late_collision' -and $script:started.Count -gt 0 -and $port -eq 8070) { return $true }
    if ($env:BOUNDARY_CASE -eq 'final_port_loss' -and $script:started.Count -eq 4 -and $port -eq 8042) { return $false }
    return $script:started.Contains($port)
}
function Start-Sleep {}
function taskkill.exe { throw 'FORBIDDEN_KILL' }
function New-Object { throw 'FORBIDDEN_SOCKET' }
function Invoke-WebRequest { throw 'FORBIDDEN_HTTP' }
function Get-NetTCPConnection { throw 'FORBIDDEN_TCP_QUERY' }
function Get-CimInstance { throw 'FORBIDDEN_CIM' }
function Start-Process {
    param($FilePath,$ArgumentList,$WorkingDirectory,$WindowStyle,[switch]$PassThru,$RedirectStandardOutput,$RedirectStandardError)
    $port=[int]([IO.Path]::GetFileName($RedirectStandardOutput).Split('-')[-1].Split('.')[0])
    if ($env:BOUNDARY_CASE -eq 'start_failure' -and $port -eq 8070) { throw 'injected process start failure' }
    $script:started.Add($port) | Out-Null
    $p=[pscustomobject]@{Id=(900000+$port);StartTime=[datetime]::UtcNow;Port=$port}
    $p | Add-Member -MemberType ScriptProperty -Name HasExited -Value {
        return ($env:BOUNDARY_CASE -eq 'early_death' -and $this.Port -eq 8042 -and $script:started.Count -gt 1) -or ($env:BOUNDARY_CASE -eq 'immediate_death')
    }
    $p | Add-Member -MemberType ScriptMethod -Name Refresh -Value {}
    $script:processes[$p.Id]=$p
    $script:started.Count | Set-Content -LiteralPath $env:START_CAPTURE
    $script:launches += @{Port=$port; Exe=$FilePath; Args=$ArgumentList; Dir=$WorkingDirectory}
    ConvertTo-Json -InputObject @($script:launches) | Set-Content -LiteralPath ($env:START_CAPTURE + '.json')
    return $p
}
'''
        overrides = r'''
function Test-ListenerOwned($plan,$process) {
    return ($env:BOUNDARY_CASE -ne 'foreign_listener') -and -not ($env:BOUNDARY_CASE -eq 'final_listener_loss' -and $script:started.Count -eq 4 -and $plan.Port -eq 8042)
}
function Test-AppResponse($plan) {
    return ($env:BOUNDARY_CASE -ne 'not_ready') -and -not ($env:BOUNDARY_CASE -eq 'final_http_loss' -and $script:started.Count -eq 4 -and $plan.Port -eq 8042)
}
'''
        marker = '\ntry {\n    if ($action'
        body = body.replace(marker, '\n' + overrides + marker, 1)
        harness = self.root / 'boundary.ps1'
        harness.write_text(guards + body, encoding='utf-8-sig')
        capture = self.root / 'starts.txt'
        result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(harness)],
                                env={**self.env, 'TRIPILOT_ACTION':'', 'BOUNDARY_CASE':case, 'START_CAPTURE':str(capture)},
                                capture_output=True, timeout=30)
        output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
        self.assertNotIn('FORBIDDEN_', output)
        return result, output, int(capture.read_text().strip()) if capture.exists() else 0

    def test_unrelated_listener_is_conflict_not_success(self):
        result, output, starts = self.run_boundary('unrelated')
        self.assertEqual(result.returncode, 1, output)
        self.assertEqual(starts, 0)

    def test_earlier_api_death_during_later_startup_fails_bundle(self):
        result, output, starts = self.run_boundary('early_death')
        self.assertEqual(result.returncode, 1, output)
        self.assertGreater(starts, 1)

    def test_startup_boundaries_fail_and_keep_only_owned_state(self):
        for case in ('late_collision', 'foreign_listener', 'not_ready', 'immediate_death'):
            with self.subTest(case=case):
                self.setUp()  # independent owned state for each injected boundary
                result, output, starts = self.run_boundary(case)
                self.assertEqual(result.returncode, 1, output)
                self.assertEqual(starts, 1)
                state = json.loads((self.root / '.tmp/local-services/processes.json').read_text(encoding='utf-8-sig'))
                self.assertTrue(state)
                self.assertTrue(all(p['Id'] == 908042 for p in state))
                self.assertNotIn('http://127.0.0.1:3300', output)

    def test_healthy_owned_bundle_preserves_all_launch_arguments(self):
        result, output, starts = self.run_boundary('healthy')
        self.assertEqual(result.returncode, 0, output)
        self.assertEqual(starts, 4)
        launches = json.loads((self.root / 'starts.txt.json').read_text(encoding='utf-8-sig'))
        self.assertEqual([p['Port'] for p in launches], [8042, 8070, 3100, 3300])
        self.assertIn('app.presentation.api.app:app', launches[0]['Args'])
        self.assertEqual(launches[1]['Args'], '-m app.ops_entrypoint --host 127.0.0.1 --port 8070')
        self.assertIn('--port 3300', launches[3]['Args'])
        state = json.loads((self.root / '.tmp/local-services/processes.json').read_text(encoding='utf-8-sig'))
        self.assertEqual([p['Id'] for p in state], [908042, 908070, 903100, 903300])

    def test_final_readiness_loss_or_later_start_failure_never_reports_success(self):
        for case in ('final_port_loss','final_listener_loss','final_http_loss','start_failure'):
            with self.subTest(case=case):
                self.setUp()
                result, output, starts = self.run_boundary(case)
                self.assertEqual(result.returncode, 1, output)
                self.assertEqual(starts, 1 if case == 'start_failure' else 4)
                self.assertNotIn('http://127.0.0.1:3300', output)
                state = json.loads((self.root / '.tmp/local-services/processes.json').read_text(encoding='utf-8-sig'))
                self.assertEqual(len(state), starts)

    def test_prior_owned_state_survives_new_launch_without_nested_array(self):
        path = self.root / '.tmp/local-services/processes.json'
        path.parent.mkdir(parents=True)
        previous = {'Name':'earlier owned', 'Id':900001, 'StartTicks':'1', 'Order':1}
        path.write_text(json.dumps([previous]), encoding='utf-8')
        result, output, starts = self.run_boundary('healthy')
        self.assertEqual(result.returncode, 0, output)
        state = json.loads(path.read_text(encoding='utf-8-sig'))
        self.assertEqual(len(state), 5)
        self.assertEqual(state[0], previous)
        self.assertTrue(all('Id' in p for p in state))

    def test_listener_ownership_checks_direct_descendant_foreign_reused_and_cycle(self):
        text = BATCH.read_text(encoding='utf-8').split('\n#==POWERSHELL==', 1)[1]
        func = text[text.index('function Test-ListenerOwned'):text.index('function Test-AppResponse')]
        script = r'''
$ErrorActionPreference='Stop'
$root=[pscustomobject]@{Id=900001;StartTime=[datetime]::new(638000000000000000)}
$plan=@{Port=8042}
function Get-NetTCPConnection { return @([pscustomobject]@{OwningProcess=$script:listener}) }
function Get-Process { return [pscustomobject]@{StartTime=$script:birth} }
function Get-CimInstance { return [pscustomobject]@{ParentProcessId=$script:parent} }
'''+func+r'''
foreach ($case in @('direct','descendant','foreign','reused','cycle')) {
 $script:listener=900002; $script:parent=900001; $script:birth=$root.StartTime.AddSeconds(1)
 if ($case -eq 'direct') { $script:listener=900001 }
 if ($case -eq 'foreign') { $script:parent=0 }
 if ($case -eq 'reused') { $script:birth=$root.StartTime.AddSeconds(-1) }
 if ($case -eq 'cycle') { $script:parent=900002 }
 $actual=Test-ListenerOwned $plan $root
 $expected=$case -in @('direct','descendant')
 if ($actual -ne $expected) { throw "ownership $case mismatch" }
 Write-Host "OWNERSHIP_PASS=$case"
}
'''
        harness = self.root / 'ownership.ps1'
        harness.write_text(script, encoding='utf-8-sig')
        result = subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(harness)],capture_output=True,timeout=20)
        self.assertEqual(result.returncode, 0, (result.stdout,result.stderr))
        self.assertEqual(result.stdout.count(b'OWNERSHIP_PASS='), 5)

    def test_http_readiness_uses_existing_app_contract_and_disposes_response(self):
        text = BATCH.read_text(encoding='utf-8').split('\n#==POWERSHELL==', 1)[1]
        func = text[text.index('function Test-AppResponse'):text.index('function Save-State')]
        # Replace only the transport factory; run the complete production predicate.
        self.assertIn('[Net.HttpWebRequest]::Create(', func)
        func = func.replace('[Net.HttpWebRequest]::Create(', 'New-TestRequest(')
        script = r'''
$ErrorActionPreference='Stop'
$pollMilliseconds=500
function New-TestRequest($uri) {
 if ($uri -notmatch '^http://127.0.0.1:8042/health$') { throw 'unexpected URI' }
 $request=[pscustomobject]@{Proxy='must-clear';AllowAutoRedirect=$true;Timeout=0;ReadWriteTimeout=0}
 $request | Add-Member ScriptMethod GetResponse {
  if ($this.Proxy -ne $null -or $this.AllowAutoRedirect -or $this.Timeout -ne 500 -or $this.ReadWriteTimeout -ne 500) { throw 'unsafe transport' }
  $response=[pscustomobject]@{StatusCode=$script:status}
  $response | Add-Member ScriptMethod GetResponseStream { return [IO.MemoryStream]::new([Text.Encoding]::UTF8.GetBytes($script:payload)) }
  $response | Add-Member ScriptMethod Dispose { $script:disposed=$true }
  return $response
 }
 return $request
}
'''+func+r'''
foreach ($case in @('ok','wrong-app','bad-status','invalid-json','redirect','error','web-ok')) {
 $script:status=200; $script:payload='{"status":"ok","app":"ops"}'; $script:disposed=$false
 $plan=@{Port=8042;HealthPath='/health';HealthApp='ops'}
 if ($case -eq 'wrong-app') { $script:payload='{"status":"ok","app":"other"}' }
 if ($case -eq 'bad-status') { $script:payload='{"status":"failed","app":"ops"}' }
 if ($case -eq 'invalid-json') { $script:payload='not-json' }
 if ($case -eq 'redirect') { $script:status=302 }
 if ($case -eq 'error') { $script:status=503 }
 if ($case -eq 'web-ok') { $plan.HealthApp=$null }
 $actual=Test-AppResponse $plan
 if ($actual -ne ($case -in @('ok','web-ok'))) { throw "HTTP $case mismatch" }
 if (-not $script:disposed) { throw "HTTP $case leaked response" }
 Write-Host "HTTP_PASS=$case"
}
'''
        harness=self.root / 'http-contract.ps1'
        harness.write_text(script,encoding='utf-8-sig')
        result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(harness)],capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0,(result.stdout,result.stderr))
        self.assertEqual(result.stdout.count(b'HTTP_PASS='),7)

    def test_stop_failure_retains_owned_record_and_never_kills_unowned_pid(self):
        path = self.root / '.tmp/local-services/processes.json'
        path.parent.mkdir(parents=True)
        entries = [{'Name':'owned','Id':900001,'StartTicks':'638000000000000000','Order':1},
                   {'Name':'reused','Id':900002,'StartTicks':'1','Order':2}]
        path.write_text(json.dumps(entries), encoding='utf-8')
        guards = r'''
function Get-Process { param($Id) return [pscustomobject]@{StartTime=[datetime]::new(638000000000000000,[DateTimeKind]::Utc)} }
function taskkill.exe {
 if ($args[1] -ne 900001) { throw 'UNOWNED_KILL' }
 $args[1] | Add-Content -LiteralPath $env:KILL_CAPTURE
 $global:LASTEXITCODE=1
}
function Start-Process { throw 'UNEXPECTED_START' }
'''
        body = BATCH.read_text(encoding='utf-8').split('\n#==POWERSHELL==',1)[1]
        harness=self.root / 'stop-failure.ps1'
        harness.write_text(guards+body,encoding='utf-8-sig')
        capture=self.root / 'kills.txt'
        result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(harness)],
                              env={**self.env,'TRIPILOT_ACTION':'stop','KILL_CAPTURE':str(capture)},capture_output=True,timeout=20)
        self.assertEqual(result.returncode,1,(result.stdout,result.stderr))
        self.assertEqual(capture.read_text().strip(),'900001')
        self.assertEqual(json.loads(path.read_text(encoding='utf-8-sig')),[entries[0]])

    def test_complete_stop_wrapper_lf_crlf_never_stops_foreign_process(self):
        text = (ROOT / 'triPilot-종료.bat').read_text(encoding='utf-8')
        for label, newline in [('lf','\n'),('crlf','\r\n')]:
            with self.subTest(label=label):
                self.setUp()
                (self.root / 'triPilot-실행.bat').write_bytes(BATCH.read_bytes())
                wrapper = self.root / ('stop-' + label + '.bat')
                wrapper.write_bytes(text.replace('\n', newline).encode('utf-8'))
                result = subprocess.run(['cmd.exe','/d','/c',str(wrapper)],env=self.env,capture_output=True,timeout=20)
                self.assertEqual(result.returncode, 0, (result.stdout,result.stderr))
                self.assertTrue(result.stdout)
                self.assertFalse((self.root / '.tmp').exists())

    def test_complete_cmd_check_lf_crlf_and_delivered_bytes(self):
        delivered = BATCH.read_bytes()
        text = delivered.decode('utf-8').replace('\r\n', '\n')
        cases = [('delivered', delivered), ('lf', text.encode('utf-8')),
                 ('crlf', text.replace('\n', '\r\n').encode('utf-8'))]
        for label, data in cases:
            with self.subTest(label=label):
                batch = self.root / (label + '.bat')
                batch.write_bytes(data)
                result = subprocess.run(['cmd.exe', '/d', '/c', str(batch), 'check'],
                                        env=self.env, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, (label, result.stdout, result.stderr))
                self.assertIn(b'3300', result.stdout)
                self.assertFalse((self.root / '.tmp').exists())
                missing = self.root / ('missing-' + label)
                missing.mkdir()
                absent_batch = missing / 'start.bat'
                absent_batch.write_bytes(data)
                failed = subprocess.run(['cmd.exe','/d','/c',str(absent_batch),'check'],
                                        env=self.env,capture_output=True,timeout=30)
                self.assertEqual(failed.returncode, 1, (label,failed.stdout,failed.stderr))
                self.assertFalse((missing / '.tmp').exists())

    def test_ops_bind_and_port_cannot_drift_from_admin_gateway(self):
        text = BATCH.read_text(encoding="utf-8")
        self.assertIn("Args='-m app.ops_entrypoint --host 127.0.0.1 --port 8070'", text)
        self.assertIn("$env:ADMIN_OPS_API_URL = 'http://127.0.0.1:8070'", text)
        package = json.loads((ROOT / "final_project_cs/frontend/apps/admin/package.json").read_text())
        self.assertIn("--port 3300", package["scripts"]["dev"])
        self.assertIn("--port 3300", package["scripts"]["start"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

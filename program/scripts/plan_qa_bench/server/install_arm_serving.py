"""기존 ARM 작업 폴더에 전용 systemd 서비스를 등록한다. 접속 정보는 받지 않는다."""
import argparse
import getpass
from pathlib import Path
import shutil
import subprocess
import time

ap = argparse.ArgumentParser()
ap.add_argument('--root', required=True)
args = ap.parse_args()
root = Path(args.root).resolve()
unit = 'tripilot-arm-serving.service'
target = Path('/etc/systemd/system') / unit
active = subprocess.run(['systemctl', 'is-active', '--quiet', unit]).returncode == 0
if active:
    print('ALREADY_ACTIVE')
    raise SystemExit(0)
for name in ('manifest.json', 'arm_serving_queue.py'):
    if not (root/name).is_file():
        raise FileNotFoundError(name)
content = f'''[Unit]
Description=guguroute ARM travel inference validation queue
After=network.target
StartLimitIntervalSec=600
StartLimitBurst=3

[Service]
Type=simple
User={getpass.getuser()}
WorkingDirectory={root}
ExecStart=/usr/bin/python3 -u {root}/arm_serving_queue.py --root {root}
Restart=on-failure
RestartSec=15
KillMode=control-group
TimeoutStopSec=45
CPUAccounting=yes
CPUQuota=180%
AllowedCPUs=0-1
MemoryAccounting=yes
MemoryHigh=9G
MemoryMax=10G
MemorySwapMax=0
Nice=5
NoNewPrivileges=yes
PrivateTmp=yes
UMask=0077

[Install]
WantedBy=multi-user.target
'''
candidate = root/'tripilot-arm-serving.service'
if candidate.exists():
    backup = root/'_backup'/str(time.time_ns())
    backup.mkdir(parents=True)
    shutil.copy2(candidate, backup/candidate.name)
candidate.write_text(content)
if target.exists():
    old = target.read_text()
    if f'WorkingDirectory={root}\n' not in old:
        raise RuntimeError('같은 서비스 이름이 다른 작업을 가리킵니다')
    subprocess.run(['sudo', '-n', 'cp', str(target), str(root/f'unit_before_{time.time_ns()}')], check=True)
subprocess.run(['sudo', '-n', 'install', '-m', '644', str(candidate), str(target)], check=True)
subprocess.run(['sudo', '-n', 'systemctl', 'daemon-reload'], check=True)
subprocess.run(['sudo', '-n', 'systemctl', 'enable', '--now', unit], check=True)
subprocess.run(['systemctl', 'show', unit, '-p', 'ActiveState', '-p', 'MainPID', '-p', 'CPUQuotaPerSecUSec', '-p', 'MemoryMax', '-p', 'AllowedCPUs'], check=True)

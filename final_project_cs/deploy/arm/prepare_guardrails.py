"""ARM 전용 외부 호출 예산을 해당 이미지의 최신 가드레일에 덧씌운다."""
from datetime import datetime, timezone
from pathlib import Path
import os
import shutil

import yaml


def prepare(source: Path, target: Path) -> None:
    config = yaml.safe_load(source.read_text(encoding="utf-8"))
    travel = config["travel"]
    travel["source_budget_shared"] = True
    travel["source_budget_on_db_error"] = "refuse"
    travel["kakao_budget"]["kakao_local_keyword"] = {"day": 100, "month": 3000}
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S_%f")
        backup = target.parent / "_backup" / (stamp + "_guardrails")
        backup.mkdir(parents=True)
        shutil.copy2(target, backup / target.name)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    os.replace(temporary, target)


if __name__ == "__main__":
    prepare(Path("/srv/config/guardrails.yaml"), Path("/srv/var/ops/arm-guardrails.yaml"))
    print("ARM_SOURCE_BUDGET_GUARDRAILS_READY")

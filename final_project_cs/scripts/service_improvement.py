"""서비스 개선 합성 자료 운영 도구. 자동 승인·실사용자 자료 추출은 하지 않는다."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.domains.travel_ops.components.customer import service_improvement as improvement
from app.infrastructure.db.session import get_connection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare", help="현재 버전 선택 동의자만 처리; 누적 생성 예산 1회 소비")
    commands.add_parser("prune", help="기한 지난 합성 후보/승인본 정리; 원본은 건드리지 않음")
    review = commands.add_parser("approve", help="실제 심의 증빙을 확인한 검토자만 실행")
    review.add_argument("batch_id")
    review.add_argument("--sha256", required=True)
    review.add_argument("--reviewer", required=True)
    for field in improvement.REVIEW_FIELDS:
        review.add_argument("--" + field.removesuffix("_sha256").replace("_", "-"), type=Path, required=True,
                            help="실제 검토 결과 파일; 내용의 SHA-256을 기록")
    export = commands.add_parser("export", help="승인되고 연례 검토가 유효한 합성 자료만 새 파일에 저장")
    export.add_argument("batch_id")
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with get_connection() as conn:
        conn.autocommit = True
        if args.command == "prepare":
            result = improvement.prepare(conn, args.tenant)
        elif args.command == "prune":
            result = {"expired_synthetic_batches": improvement.prune_expired(conn, args.tenant)}
        elif args.command == "approve":
            evidence = {"reviewer": args.reviewer}
            for field in improvement.REVIEW_FIELDS:
                content = getattr(args, field.removesuffix("_sha256")).read_bytes()
                if not content.strip():
                    parser.error("빈 검토 증빙은 사용할 수 없습니다")
                evidence[field] = hashlib.sha256(content).hexdigest()
            improvement.approve(conn, args.tenant, args.batch_id, expected_sha256=args.sha256, review=evidence)
            result = {"status": "approved"}
        else:
            payload = improvement.export(conn, args.tenant, args.batch_id)
            with args.output.open("x", encoding="utf-8") as output:
                json.dump(payload, output, ensure_ascii=False, separators=(",", ":"))
            result = {"status": "exported", "payload_sha256": improvement.digest(payload)}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

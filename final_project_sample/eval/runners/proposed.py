from .common import execute, parser

if __name__ == "__main__":
    args = parser("Proposed: lifecycle, Context Broker, two Teams, approval and REST").parse_args()
    try:
        raise SystemExit(execute(args, "Proposed", require_teams=True))
    except RuntimeError as exc:
        raise SystemExit(f"ERROR: {exc}")

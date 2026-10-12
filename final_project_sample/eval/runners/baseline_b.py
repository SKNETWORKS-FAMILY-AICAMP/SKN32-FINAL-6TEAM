from .common import execute, parser

if __name__ == "__main__":
    args = parser("Baseline B: fixed workflow/rules with policy retrieval and no Team").parse_args()
    raise SystemExit(execute(args, "B"))

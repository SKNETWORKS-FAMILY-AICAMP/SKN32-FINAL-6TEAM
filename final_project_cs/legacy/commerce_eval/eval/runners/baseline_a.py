from .common import execute, parser

if __name__ == "__main__":
    args = parser("Baseline A: single LLM with original prompt and minimal DB lookup").parse_args()
    raise SystemExit(execute(args, "A"))

"""Compile trusted migration sources without rewriting their SQL bodies."""
from pglast import ast, enums, parse_sql, scan


def atomic_sql(source: str, filename: str) -> str:
    """Remove only a plain file-level transaction pair; reject other controls.

    PostgreSQL's parser classifies statements and its scanner supplies character
    spans. Comments, quoted text and function bodies are never regex-rewritten.
    All sources are compiled before the first database statement is executed.
    """
    statements = parse_sql(source)
    for raw in statements:
        if isinstance(raw.stmt, ast.VariableSetStmt) and raw.stmt.name in (
                "TRANSACTION", "SESSION CHARACTERISTICS", "transaction_isolation",
                "transaction_read_only", "transaction_deferrable"):
            raise ValueError(f"{filename}: migration cannot change transaction options")
    controls = [i for i, raw in enumerate(statements)
                if isinstance(raw.stmt, ast.TransactionStmt)]
    if not controls:
        return source
    kind = enums.TransactionStmtKind
    first, last = statements[0].stmt, statements[-1].stmt
    if (len(statements) < 3 or controls != [0, len(statements) - 1]
            or first.kind not in (kind.TRANS_STMT_BEGIN, kind.TRANS_STMT_START)
            or last.kind != kind.TRANS_STMT_COMMIT
            or first.options or first.chain or last.chain):
        raise ValueError(f"{filename}: only a plain outer BEGIN/COMMIT pair is supported")
    chars = list(source)
    tokens = scan(source)
    for raw in (statements[0], statements[-1]):
        start = raw.stmt_location
        end = start + raw.stmt_len if raw.stmt_len else len(source)
        for token in tokens:
            if start <= token.start < end and token.name not in ("C_COMMENT", "SQL_COMMENT"):
                for index in range(token.start, token.end + 1):
                    if chars[index] not in "\r\n":
                        chars[index] = " "
    return "".join(chars)

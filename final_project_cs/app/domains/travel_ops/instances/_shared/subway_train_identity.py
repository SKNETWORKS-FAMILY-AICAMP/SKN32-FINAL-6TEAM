"""도착 소스와 출발 대조가 공유하는 열차번호 입력 계약. I/O를 하지 않는다."""
from __future__ import annotations


def valid_train_number(value: object) -> bool:
    """원문 ASCII 영숫자 번호. 접두사로 운영사·열차 종류를 추정하지 않는다.

    숫자 역ID 검사와 구분해 문자 포함 열차번호도 그대로 보존한다.
    선행0·대소문자를 바꾸지 않으며 기존 전부0 번호는 계속 거부한다.
    """
    return (isinstance(value, str) and value.isascii() and value.isalnum()
            and any(c.isdigit() for c in value) and any(c != '0' for c in value))

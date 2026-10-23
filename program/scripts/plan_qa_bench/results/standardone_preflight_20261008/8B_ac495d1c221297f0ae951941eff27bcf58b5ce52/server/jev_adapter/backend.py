"""The small contract between response formatting and inference transport."""

from dataclasses import dataclass
from typing import Protocol


class AdapterError(Exception):
    def __init__(self, code: str, message: str, field: str = "", status: int = 422):
        super().__init__(message)
        self.code, self.field, self.status = code, field, status


@dataclass(frozen=True)
class ScoringResult:
    logprobs: tuple[float, ...]
    input_tokens: int


class ScoringBackend(Protocol):
    model: str

    async def start(self) -> None: ...

    async def close(self) -> None: ...

    def labels(self, count: int) -> tuple[tuple[str, ...], tuple[int, ...]]: ...

    async def evaluate(
        self,
        prompt: str,
        images: list[str],
        labels: tuple[str, ...],
        token_ids: tuple[int, ...],
        assistant_prefix: str | None,
    ) -> ScoringResult: ...

"""Build questions and construct responses independently of the inference engine."""

import asyncio
import math
import time
from collections.abc import Mapping
from numbers import Real

from .backend import AdapterError, ScoringBackend
from .protocol import (
    SystemOneRequest,
    build_prompt,
    plan_question,
    reduce_probabilities,
    rotation_order,
)


QUESTION_TYPES = ("choice", "noul", "score")


def validate_temperature_by_type(values: Mapping[str, float] | None) -> dict[str, float]:
    """Check a {answer type: temperature} map; returns a plain dict (empty if None)."""
    if values is None:
        return {}
    result = {}
    for key, value in values.items():
        if key not in QUESTION_TYPES:
            raise ValueError(f"unknown answer type for temperature_by_type: {key!r}")
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError("temperature_by_type values must be finite and greater than zero")
        result[key] = float(value)
    return result


class SystemOneService:
    def __init__(
        self,
        backend: ScoringBackend,
        *,
        max_concurrency: int = 32,
        alias: str = "jev-latest",
        default_temperature: float = 1.0,
        temperature_by_type: Mapping[str, float] | None = None,
        prompt_wording: str = "served",
    ):
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        if (
            isinstance(default_temperature, bool)
            or not isinstance(default_temperature, Real)
            or not math.isfinite(default_temperature)
            or default_temperature <= 0
        ):
            raise ValueError("default_temperature must be finite and greater than zero")
        if prompt_wording not in ("served", "native"):
            raise ValueError('prompt_wording must be "served" or "native"')
        self.backend, self.alias = backend, alias
        # Applied only when a request omits options.temperature; an explicit
        # request value always wins, and temperature_scaling=false still
        # disables scaling. Without this setting the request default (1.0) holds.
        self.default_temperature = float(default_temperature)
        # Optional per-answer-type defaults (choice / noul / score); a type not
        # listed falls back to default_temperature. Also applied only when the
        # request omits options.temperature.
        self.temperature_by_type = validate_temperature_by_type(temperature_by_type)
        # Server-wide, not per-request: which text build_prompt() renders.
        # "native" additionally requires the backend's labels to be canonical
        # A-Z (build_prompt raises otherwise) and relies on the backend to
        # prepend a matching system message where feasible (see sglang.py).
        self.prompt_wording = prompt_wording
        self.capacity = asyncio.Semaphore(max_concurrency)

    def effective_options(self, request: SystemOneRequest):
        """Request options with the server default filled into an omitted temperature."""
        options = request.options
        if "temperature" in options.model_fields_set:
            return options
        return options.model_copy(update={"temperature": self.default_temperature})

    def question_options(self, request: SystemOneRequest, options, question_type: str):
        """Options for one question: the per-type default when the request left
        temperature unset and a default exists for this answer type."""
        if (
            "temperature" in request.options.model_fields_set
            or question_type not in self.temperature_by_type
        ):
            return options
        return options.model_copy(
            update={"temperature": self.temperature_by_type[question_type]}
        )

    async def score(self, request: SystemOneRequest) -> dict:
        if request.model not in {self.backend.model, self.alias}:
            raise AdapterError(
                "model_not_found",
                "Requested model is not configured.",
                "model",
                404,
            )
        started = time.perf_counter()
        options = self.effective_options(request)
        jobs, plans = [], {}
        # Validate and prepare all questions before scheduling any inference.
        for key, question in request.questions.items():
            plan = plans[key] = plan_question(question)
            labels, token_ids = self.backend.labels(len(plan.option_names))
            for rotation in range(options.permutations):
                order = rotation_order(len(labels), rotation)
                prompt = build_prompt(
                    request.state, plan, labels, order, wording=self.prompt_wording
                )
                jobs.append((key, order, prompt, labels, token_ids))

        async def evaluate(job):
            key, order, prompt, labels, token_ids = job
            async with self.capacity:
                result = await self.backend.evaluate(
                    prompt,
                    request.images,
                    labels,
                    token_ids,
                    options.assistant_prefix,
                )
            return key, order, result

        tasks = [asyncio.create_task(evaluate(job)) for job in jobs]
        try:
            results = await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        grouped = {key: ([], []) for key in plans}
        input_tokens = 0
        for key, order, result in results:
            vectors, orders = grouped[key]
            vectors.append(result.logprobs)
            orders.append(order)
            input_tokens += result.input_tokens
        return {
            "model": self.backend.model,
            "answers": {
                key: reduce_probabilities(
                    plan, *grouped[key], self.question_options(request, options, plan.type)
                )
                for key, plan in plans.items()
            },
            "usage": {"input_tokens": input_tokens, "output_tokens": 0},
            "metadata": {
                "confidence_method": "1 - normalized_entropy",
                "temperature": (
                    options.temperature if options.temperature_scaling else 1.0
                ),
                **(
                    {"temperature_by_type": dict(self.temperature_by_type)}
                    if self.temperature_by_type
                    and "temperature" not in request.options.model_fields_set
                    and options.temperature_scaling
                    else {}
                ),
                "evaluations": len(jobs),
                **(
                    {"label_scheme": self.backend.label_scheme}
                    if getattr(self.backend, "label_scheme", None)
                    else {}
                ),
                "adapter_elapsed_ms": (time.perf_counter() - started) * 1000,
            },
        }

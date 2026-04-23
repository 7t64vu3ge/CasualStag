from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

try:
    from langfuse import Langfuse
except ImportError:  # pragma: no cover - optional dependency
    Langfuse = None  # type: ignore[assignment]

from financial_agent.config import Settings


LOGGER = logging.getLogger(__name__)


@dataclass
class TraceRun:
    trace_id: str | None
    started_at: float
    trace_url: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)


class ObservabilityService:
    def __init__(self, settings: Settings) -> None:
        self._client: Any | None = None
        if Langfuse and settings.langfuse_public_key and settings.langfuse_secret_key:
            self._client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )

    def start_trace(self, name: str, request_input: dict[str, Any]) -> TraceRun:
        trace_id: str | None = None
        trace_url: str | None = None
        if self._client:
            trace_id = self._client.create_trace_id()
            trace_url = self._client.get_trace_url(trace_id=trace_id)
            self._client.create_event(
                trace_context={"trace_id": trace_id},
                name=f"{name}.start",
                input=request_input,
                metadata={"component": "financial-agent"},
            )
        return TraceRun(trace_id=trace_id, trace_url=trace_url, started_at=time.perf_counter())

    def record_phase(
        self,
        trace: TraceRun,
        name: str,
        *,
        input_data: Any | None = None,
        output_data: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        elapsed_ms = round((time.perf_counter() - trace.started_at) * 1000, 2)
        event = {
            "name": name,
            "elapsed_ms": elapsed_ms,
            "input": input_data,
            "output": output_data,
            "metadata": metadata or {},
        }
        trace.events.append(event)
        LOGGER.info("trace_phase=%s elapsed_ms=%s", name, elapsed_ms)
        if self._client and trace.trace_id:
            self._client.create_event(
                trace_context={"trace_id": trace.trace_id},
                name=name,
                input=input_data,
                output=output_data,
                metadata={"elapsed_ms": elapsed_ms, **(metadata or {})},
            )

    def finish_trace(self, trace: TraceRun, response: dict[str, Any]) -> None:
        total_elapsed_ms = round((time.perf_counter() - trace.started_at) * 1000, 2)
        if self._client and trace.trace_id:
            self._client.create_event(
                trace_context={"trace_id": trace.trace_id},
                name="analyze.finish",
                output=response,
                metadata={"latency_ms": total_elapsed_ms, "event_count": len(trace.events)},
            )
            self._client.flush()

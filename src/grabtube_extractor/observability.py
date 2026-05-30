"""Structured logging + a tiny in-memory metrics registry (Constitution V).

Metrics are intentionally simple (single-instance, no external system): counters and a
gauge for queue depth, plus job durations. No sensitive data is logged.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.time(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger("grabtube")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root.propagate = False


@dataclass
class Metrics:
    jobs_created: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0
    jobs_canceled: int = 0
    queue_depth: int = 0
    durations: list[float] = field(default_factory=list)

    def record_duration(self, seconds: float) -> None:
        self.durations.append(seconds)

    @property
    def failure_rate(self) -> float:
        total = self.jobs_completed + self.jobs_failed
        return (self.jobs_failed / total) if total else 0.0

    def snapshot(self) -> dict:
        return {
            "jobs_created": self.jobs_created,
            "jobs_completed": self.jobs_completed,
            "jobs_failed": self.jobs_failed,
            "jobs_canceled": self.jobs_canceled,
            "queue_depth": self.queue_depth,
            "failure_rate": round(self.failure_rate, 4),
            "avg_duration_s": round(sum(self.durations) / len(self.durations), 3) if self.durations else 0.0,
        }

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AnalysisContext:
    timeline: list[dict[str, Any]]
    diarization: dict[str, Any]
    events: list[dict[str, Any]]
    metadata: dict[str, Any]
    summary: dict[str, Any]


@dataclass
class ScoreResult:
    name: str
    value: float
    grade: str
    positives: list[str] = field(default_factory=list)
    negatives: list[str] = field(default_factory=list)
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "grade": self.grade,
            "positives": self.positives,
            "negatives": self.negatives,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

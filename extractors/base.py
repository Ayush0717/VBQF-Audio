from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class BaseExtractor(ABC):
    name: str

    @abstractmethod
    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, Any]:
        """Return feature values for one audio window."""

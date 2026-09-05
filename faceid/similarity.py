# Small numeric helpers shared by the face engine and the subject registry.
from __future__ import annotations

import numpy as np


def cosine_similarity(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
    a = np.asarray(vector_a, dtype=np.float32).flatten()
    b = np.asarray(vector_b, dtype=np.float32).flatten()
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator == 0.0:
        return 0.0
    return float(np.dot(a, b) / denominator)

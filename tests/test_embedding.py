import math

import pytest

from oncallagent.embedding import average_embeddings, normalize_embedding


def test_average_embeddings_returns_arithmetic_mean() -> None:
    assert average_embeddings([[1.0, 3.0], [3.0, 5.0]]) == [2.0, 4.0]


def test_average_embeddings_rejects_empty_or_mismatched_vectors() -> None:
    with pytest.raises(ValueError, match="no embeddings provided"):
        average_embeddings([])

    with pytest.raises(ValueError, match="embedding 1 has different length"):
        average_embeddings([[1.0], [1.0, 2.0]])


def test_normalize_embedding_uses_l2_norm_and_keeps_zero_vector() -> None:
    normalized = normalize_embedding([3.0, 4.0])

    assert normalized == [0.6, 0.8]
    assert math.isclose(sum(value * value for value in normalized), 1.0)
    assert normalize_embedding([0.0, 0.0]) == [0.0, 0.0]

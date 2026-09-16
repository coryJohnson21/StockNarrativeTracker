import math

import pytest

from app.services.narratives import cluster_greedy, cosine_similarity, novelty_from_max_similarity


def _unit(*coords):
    n = math.sqrt(sum(c * c for c in coords))
    return [c / n for c in coords]


def test_cosine_similarity_basics():
    assert cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)
    assert cosine_similarity([3, 0], [1, 0]) == pytest.approx(1.0)  # scale invariant
    assert cosine_similarity([0, 0], [1, 0]) == 0.0


@pytest.mark.parametrize(
    "max_sim, expected",
    [
        (None, None),
        (1.0, 0.0),
        (0.9, 0.1),
        (0.4, 0.6),
        (-0.2, 1.0),   # anti-similar still caps at fully novel
        (1.3, 0.0),    # float noise above 1 clamps
    ],
)
def test_novelty_from_max_similarity(max_sim, expected):
    result = novelty_from_max_similarity(max_sim)
    assert result == expected if expected is None else result == pytest.approx(expected)


def test_cluster_greedy_groups_near_duplicates():
    a, a2, b = _unit(1, 0, 0), _unit(1, 0.05, 0), _unit(0, 1, 0)
    assert cluster_greedy([a, a2, b]) == [[0, 1], [2]]


def test_cluster_greedy_preserves_first_appearance_order():
    a, b = _unit(1, 0), _unit(0, 1)
    assert cluster_greedy([b, a, b, a]) == [[0, 2], [1, 3]]


def test_cluster_greedy_threshold_controls_granularity():
    a, mid = _unit(1, 0), _unit(1, 0.6)   # cosine ~0.86
    assert cluster_greedy([a, mid], threshold=0.85) == [[0, 1]]
    assert cluster_greedy([a, mid], threshold=0.9) == [[0], [1]]


def test_cluster_greedy_uses_running_centroid():
    # Each step is within threshold of the running centroid, so a slow drift stays one story...
    drift = [_unit(1, 0.0), _unit(1, 0.15), _unit(1, 0.3)]
    assert cluster_greedy(drift, threshold=0.95) == [[0, 1, 2]]
    # ...but a jump far from the centroid starts a new one.
    assert cluster_greedy(drift + [_unit(0, 1)], threshold=0.95) == [[0, 1, 2], [3]]


def test_cluster_greedy_empty():
    assert cluster_greedy([]) == []

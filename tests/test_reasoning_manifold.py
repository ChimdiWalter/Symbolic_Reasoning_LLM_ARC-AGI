import numpy as np

from reasoning_project.diagnostics.reasoning_manifold import (
    divergence_step,
    latent_separability_score,
    nearest_success_distance,
    summarize_reasoning_manifold,
)


def test_reasoning_manifold_metrics_are_bounded_and_interpretable():
    success = np.asarray([[0.0, 0.0], [0.1, 0.0], [0.0, 0.1]], dtype=float)
    failure = np.asarray([[2.0, 2.0], [2.1, 1.9]], dtype=float)
    trajectory = np.asarray([[0.0, 0.0], [0.1, 0.0], [1.2, 1.1], [2.0, 2.0]], dtype=float)

    distances = nearest_success_distance(success, failure, k=2)
    separability = latent_separability_score(success, failure)
    step = divergence_step(trajectory, success, k=1, threshold=0.5)
    summary = summarize_reasoning_manifold(success, failure, trajectory_vectors=trajectory, k=1)

    assert distances.shape == (2,)
    assert float(distances.mean()) > 1.0
    assert separability > 1.0
    assert step == 2
    assert summary["divergence_step"] == 2
    assert summary["failure_count"] == 2

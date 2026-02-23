"""Ensemble parameter sampling."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _latin_hypercube(n: int, d: int, seed: int) -> np.ndarray:
    """Generate a Latin-hypercube sample matrix.

    Parameters
    ----------
    n : int
        Number of samples.
    d : int
        Number of dimensions.
    seed : int
        Random seed.

    Returns
    -------
    numpy.ndarray
        Matrix of shape ``(n, d)`` with values in ``[0, 1]``.
    """

    try:
        from scipy.stats import qmc

        sampler = qmc.LatinHypercube(d=d, seed=seed)
        return sampler.random(n=n)
    except Exception:
        rng = np.random.default_rng(seed)
        return rng.random((n, d))


def sample_ensemble_parameters(ensemble_size: int, seed: int) -> pd.DataFrame:
    """Sample CivicMorph ensemble dimensions using Latin hypercube strategy.

    Parameters
    ----------
    ensemble_size : int
        Number of ensemble members to sample.
    seed : int
        Deterministic seed value.

    Returns
    -------
    pandas.DataFrame
        Table of sampled member parameters.
    """

    raw = _latin_hypercube(ensemble_size, d=8, seed=seed)
    mixes = np.array(["balanced", "brt_bias", "tram_bias", "metro_bias"])

    rows: list[dict[str, object]] = []
    for idx, vals in enumerate(raw):
        rows.append(
            {
                "member_id": idx,
                "corridor_candidate": int(np.floor(vals[0] * 5)),
                "transit_type_mix": mixes[min(3, int(np.floor(vals[1] * 4)))],
                "stop_spacing_jitter": float(np.interp(vals[2], [0, 1], [-0.15, 0.15])),
                "intensity_budget_scalar": float(np.interp(vals[3], [0, 1], [0.8, 1.25])),
                "green_budget_scalar": float(np.interp(vals[4], [0, 1], [0.8, 1.3])),
                "street_conversion_budget": float(np.interp(vals[5], [0, 1], [0.75, 1.35])),
                "block_subdivision_aggressiveness": float(np.interp(vals[6], [0, 1], [0.7, 1.4])),
                "terrain_sensitivity_scalar": float(np.interp(vals[7], [0, 1], [0.7, 1.5])),
            }
        )

    return pd.DataFrame(rows)

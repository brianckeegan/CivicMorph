"""Terrain derivation helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd


def derive_slope_classes(score: pd.Series) -> pd.Series:
    """Map normalized slope scores into slope-class labels.

    Parameters
    ----------
    score : pandas.Series
        Normalized slope score in ``[0, 1]``.

    Returns
    -------
    pandas.Series
        Categorical slope classes: ``0-5``, ``5-10``, ``10-20``, ``>20``.
    """

    bins = [0.0, 0.2, 0.4, 0.7, 1.01]
    labels = ["0-5", "5-10", "10-20", ">20"]
    return pd.cut(np.clip(score, 0, 1), bins=bins, labels=labels, include_lowest=True)

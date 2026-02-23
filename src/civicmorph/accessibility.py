"""Accessibility computations for 15-minute evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd


def classify_access(minutes: pd.Series) -> pd.Series:
    """Classify travel-time accessibility into threshold bands.

    Parameters
    ----------
    minutes : pandas.Series
        Travel time in minutes.

    Returns
    -------
    pandas.Series
        Categorical labels: ``primary`` (<=15), ``secondary`` (<=30), or ``outside``.
    """

    bands = np.where(minutes <= 15, "primary", np.where(minutes <= 30, "secondary", "outside"))
    return pd.Series(bands, index=minutes.index)

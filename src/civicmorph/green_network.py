"""Green-network utility wrappers."""

from __future__ import annotations

import pandas as pd


def public_green_only(df: pd.DataFrame) -> pd.DataFrame:
    """Filter a green-area table to public-access features.

    Parameters
    ----------
    df : pandas.DataFrame
        Green-area table. If ``is_public`` is present, ``1`` indicates public access.

    Returns
    -------
    pandas.DataFrame
        Filtered dataframe. If ``is_public`` is missing, a copy of input data.
    """

    if "is_public" not in df.columns:
        return df.copy()
    return df[df["is_public"] == 1].copy()

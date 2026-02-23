"""Grid helpers for cell overlays."""

from __future__ import annotations

import pandas as pd


def make_square_grid(side: int, cell_size_m: int = 100) -> pd.DataFrame:
    """Create square grid metadata table.

    Parameters
    ----------
    side : int
        Number of cells per side.
    cell_size_m : int, default=100
        Cell width and height in meters.

    Returns
    -------
    pandas.DataFrame
        Grid metadata table with ``cell_id``, ``x``, ``y``, and ``cell_size_m``.
    """

    rows = []
    for x in range(side):
        for y in range(side):
            rows.append(
                {
                    "cell_id": f"c_{x:03d}_{y:03d}",
                    "x": x,
                    "y": y,
                    "cell_size_m": cell_size_m,
                }
            )
    return pd.DataFrame(rows)

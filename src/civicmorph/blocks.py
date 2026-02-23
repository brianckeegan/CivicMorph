"""Synthetic block generation from cell overlays."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


TYPOLOGIES = [
    "courtyard",
    "perimeter_mixed_use",
    "rowhouse",
    "small_apartment_court",
]


def _typology_for_row(row: pd.Series) -> str:
    """Select a synthetic block typology from aggregated cell attributes.

    Parameters
    ----------
    row : pandas.Series
        Aggregated block-level metrics.

    Returns
    -------
    str
        Typology label.
    """

    if row["slope_constraint_score"] > 0.65:
        return "rowhouse"
    if row["flood_risk_score"] > 0.65:
        return "perimeter_mixed_use"
    if row["proposed_intensity_far"] > 2.6:
        return "perimeter_mixed_use"
    if row["proposed_intensity_far"] > 1.5:
        return "courtyard"
    return "small_apartment_court"


def generate_blocks(cells: pd.DataFrame, member_id: int, params: dict[str, Any]) -> pd.DataFrame:
    """Generate synthetic blocks with terrain-aware envelope parameters.

    Parameters
    ----------
    cells : pandas.DataFrame
        Cell-level proposed overlays for one ensemble member.
    member_id : int
        Ensemble member identifier.
    params : dict of str to Any
        Sampled parameters used to configure generation behavior.

    Returns
    -------
    pandas.DataFrame
        Synthetic block layer with typology and envelope columns.
    """

    work = cells.copy()
    work["block_x"] = work["x"] // 2
    work["block_y"] = work["y"] // 2

    grouped = work.groupby(["block_x", "block_y"], as_index=False).agg(
        {
            "proposed_intensity_far": "mean",
            "proposed_height_cap_ft": "max",
            "slope_constraint_score": "mean",
            "flood_risk_score": "mean",
            "view_shed_value_score": "mean",
        }
    )

    rows: list[dict[str, Any]] = []
    for _, row in grouped.iterrows():
        typology = _typology_for_row(row)
        courtyard_ratio = float(
            np.clip(
                0.25 + 0.12 * row["view_shed_value_score"] - 0.15 * row["slope_constraint_score"],
                0.12,
                0.45,
            )
        )
        block_id = f"b_{int(row['block_x']):03d}_{int(row['block_y']):03d}"
        rows.append(
            {
                "block_id": block_id,
                "member_id": member_id,
                "typology": typology,
                "far_target": float(np.clip(row["proposed_intensity_far"], 0.5, 5.0)),
                "height_cap_ft": float(np.clip(row["proposed_height_cap_ft"], 25, 60)),
                "courtyard_ratio": courtyard_ratio,
                "terrain_steep_slope_adapt": bool(row["slope_constraint_score"] > 0.55),
                "terrain_flood_resilient_form": bool(row["flood_risk_score"] > 0.55),
                "geometry_wkt": (
                    f"POLYGON(({int(row['block_x'])*200} {int(row['block_y'])*200}, "
                    f"{int(row['block_x']+1)*200} {int(row['block_y'])*200}, "
                    f"{int(row['block_x']+1)*200} {int(row['block_y']+1)*200}, "
                    f"{int(row['block_x'])*200} {int(row['block_y']+1)*200}, "
                    f"{int(row['block_x'])*200} {int(row['block_y'])*200}))"
                ),
            }
        )

    return pd.DataFrame(rows)

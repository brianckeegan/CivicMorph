"""One-shot regime-shift synthesis for CivicMorph ensemble members."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _far_to_height(far: float) -> float:
    """Map FAR value to a capped height in feet.

    Parameters
    ----------
    far : float
        Proposed floor area ratio.

    Returns
    -------
    float
        Height cap in feet before global clipping.
    """

    if far < 1.2:
        return 25 + (far - 0.5) / 0.7 * 10
    if far < 2.5:
        return 35 + (far - 1.2) / 1.3 * 25
    return 45 + min(15, (far - 2.0) * 6)


def _street_priority(car_deemphasis: float, access_score: float) -> str:
    """Select street priority class from mobility signals.

    Parameters
    ----------
    car_deemphasis : float
        Cell-level car deemphasis score.
    access_score : float
        Cell-level transit access proxy.

    Returns
    -------
    str
        Street priority class label.
    """

    if car_deemphasis > 0.8:
        return "ped_priority"
    if access_score > 0.75:
        return "transit_priority"
    if car_deemphasis > 0.6:
        return "bike_priority"
    if car_deemphasis > 0.45:
        return "mixed_local"
    return "vehicle_limited"


def generate_member_cells(
    baseline_cells: pd.DataFrame,
    params: dict[str, Any],
    member_id: int,
    seed: int,
) -> pd.DataFrame:
    """Generate cell-level overlays for one ensemble member.

    Parameters
    ----------
    baseline_cells : pandas.DataFrame
        Baseline cell table.
    params : dict of str to Any
        Sampled member parameters.
    member_id : int
        Ensemble member identifier.
    seed : int
        Deterministic run seed.

    Returns
    -------
    pandas.DataFrame
        Proposed overlay table for one member with required output columns.
    """

    rng = np.random.default_rng(seed + member_id)
    work = baseline_cells.copy()

    corridor_signal = np.sin((work["x"] + int(params["corridor_candidate"])) / 3.0)
    transit_access = np.clip(0.5 + 0.35 * corridor_signal + rng.normal(0, 0.08, size=len(work)), 0, 1)
    base_access = np.clip(1 - (work["baseline_daily_needs_min"] / 40.0), 0, 1)
    green_gap = 1 - work["baseline_green_access_score"]

    terrain_penalty = (
        work["flood_risk_score"] * 0.55 * params["terrain_sensitivity_scalar"]
        + work["slope_constraint_score"] * 0.45 * params["terrain_sensitivity_scalar"]
    )

    opportunity = (
        0.45 * transit_access
        + 0.35 * base_access
        + 0.2 * green_gap * params["green_budget_scalar"]
        - terrain_penalty
    )

    viewshed_moderation = work["view_shed_value_score"] * 0.18
    far_raw = (
        0.8
        + opportunity * 3.0 * params["intensity_budget_scalar"]
        - viewshed_moderation
        + rng.normal(0, 0.18, size=len(work))
    )
    far = np.clip(far_raw, 0.5, 5.0)

    height = np.array([_far_to_height(v) for v in far])
    height = np.clip(height, 25, 60)

    car_deemphasis = np.clip(
        0.35
        + 0.4 * params["street_conversion_budget"] * transit_access
        + 0.15 * params["green_budget_scalar"]
        - 0.25 * work["flood_risk_score"],
        0,
        1,
    )

    green_access = np.clip(
        work["baseline_green_access_score"]
        + 0.18 * params["green_budget_scalar"]
        + 0.12 * work["flood_risk_score"]
        + rng.normal(0, 0.04, size=len(work)),
        0,
        1,
    )

    work["member_id"] = member_id
    work["proposed_intensity_far"] = far
    work["proposed_height_cap_ft"] = height
    work["car_deemphasis_score"] = car_deemphasis
    work["green_access_score"] = green_access
    work["street_priority_class"] = [
        _street_priority(c, a) for c, a in zip(car_deemphasis, transit_access, strict=True)
    ]

    # Required output columns are emitted in stable order.
    return work[
        [
            "cell_id",
            "member_id",
            "x",
            "y",
            "geometry_wkt",
            "proposed_intensity_far",
            "proposed_height_cap_ft",
            "street_priority_class",
            "car_deemphasis_score",
            "green_access_score",
            "flood_risk_score",
            "slope_constraint_score",
            "view_shed_value_score",
            "inhabited",
            "baseline_daily_needs_min",
            "baseline_non_auto_score",
        ]
    ].copy()


def generate_street_layer(cells: pd.DataFrame, member_id: int) -> pd.DataFrame:
    """Create street-priority layer for one member.

    Parameters
    ----------
    cells : pandas.DataFrame
        Proposed cell overlays for one member.
    member_id : int
        Ensemble member identifier.

    Returns
    -------
    pandas.DataFrame
        Street-priority layer with segment geometry proxies.
    """

    grouped = cells.groupby("x", as_index=False).agg(
        {
            "car_deemphasis_score": "mean",
            "street_priority_class": lambda s: s.value_counts().index[0],
        }
    )

    grouped["member_id"] = member_id
    grouped.rename(columns={"x": "segment_id"}, inplace=True)
    grouped["geometry_wkt"] = grouped["segment_id"].apply(
        lambda s: f"LINESTRING({int(s)*100} 0, {int(s)*100} 2500)"
    )
    return grouped[
        ["segment_id", "member_id", "street_priority_class", "car_deemphasis_score", "geometry_wkt"]
    ]


def generate_green_network(cells: pd.DataFrame, member_id: int, green_budget_scalar: float) -> pd.DataFrame:
    """Generate terrain-aware green-network additions.

    Parameters
    ----------
    cells : pandas.DataFrame
        Proposed cell overlays for one member.
    member_id : int
        Ensemble member identifier.
    green_budget_scalar : float
        Member-level green investment scalar.

    Returns
    -------
    pandas.DataFrame
        Green network layer with priority scores and point geometry proxies.
    """

    work = cells.copy()
    score = (
        0.45 * work["flood_risk_score"]
        + 0.25 * work["slope_constraint_score"]
        + 0.30 * work["view_shed_value_score"]
    )
    threshold = np.quantile(score, max(0.3, 0.6 - 0.1 * green_budget_scalar))
    selected = work[score >= threshold][["cell_id", "x", "y", "green_access_score"]].copy()
    selected["member_id"] = member_id
    selected.rename(columns={"green_access_score": "priority_score"}, inplace=True)
    selected["geometry_wkt"] = selected.apply(
        lambda r: f"POINT({int(r['x'])*100 + 50} {int(r['y'])*100 + 50})", axis=1
    )
    return selected[["cell_id", "member_id", "priority_score", "geometry_wkt"]]

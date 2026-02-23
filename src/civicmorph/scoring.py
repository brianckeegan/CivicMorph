"""Scoring and ranking utilities for CivicMorph ensemble plans."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_quantile(series: pd.Series, q: float) -> float:
    """Compute quantile with empty-series guard.

    Parameters
    ----------
    series : pandas.Series
        Input series.
    q : float
        Quantile in the closed interval ``[0, 1]``.

    Returns
    -------
    float
        Quantile value or ``0.0`` when ``series`` is empty.
    """

    if series.empty:
        return 0.0
    return float(np.quantile(series.to_numpy(), q))


def compute_static_scores(cells: pd.DataFrame, scoring_cfg: object) -> dict[str, float]:
    """Compute static objective and penalty scores for one member.

    Parameters
    ----------
    cells : pandas.DataFrame
        Proposed cell overlays for one member.
    scoring_cfg : object
        Scoring configuration object with penalty weights.

    Returns
    -------
    dict of str to float
        Aggregated objective, penalty, and component metrics.
    """

    compactness = float(np.clip(cells["proposed_intensity_far"].mean() / 5.0, 0, 1))
    green_access = float(np.clip(cells["green_access_score"].mean(), 0, 1))
    non_auto_access = float(np.clip(cells["car_deemphasis_score"].mean(), 0, 1))

    utility = 0.35 * compactness + 0.35 * green_access + 0.30 * non_auto_access

    permeability_decline = float(max(0.0, 0.45 - cells["car_deemphasis_score"].mean()))
    auto_centrality_increase = float(max(0.0, 0.5 - non_auto_access))
    excessive_tower_morphology = float((cells["proposed_intensity_far"] > 4.4).mean())
    green_inequity = float(
        np.clip(_safe_quantile(cells["green_access_score"], 0.9) - _safe_quantile(cells["green_access_score"], 0.1), 0, 1)
    )

    baseline_median = float(np.median(cells["baseline_daily_needs_min"]))
    proposed_proxy = float(np.median(cells["baseline_daily_needs_min"] * (1.0 - 0.35 * cells["car_deemphasis_score"])))
    access_regression = float(max(0.0, (proposed_proxy - baseline_median) / 45.0))

    flood_exposure = float(
        np.clip((cells["proposed_intensity_far"] * cells["flood_risk_score"]).mean() / 5.0, 0, 1)
    )
    slope_overbuild = float(
        np.clip((cells["proposed_intensity_far"] * cells["slope_constraint_score"]).mean() / 5.0, 0, 1)
    )

    penalty = (
        float(scoring_cfg.permeability_penalty_weight) * permeability_decline
        + float(scoring_cfg.auto_centrality_penalty_weight) * auto_centrality_increase
        + float(scoring_cfg.tower_morphology_penalty_weight) * excessive_tower_morphology
        + float(scoring_cfg.green_inequity_penalty_weight) * green_inequity
        + float(scoring_cfg.access_regression_penalty_weight) * access_regression
        + float(scoring_cfg.flood_exposure_penalty_weight) * flood_exposure
        + float(scoring_cfg.slope_overbuild_penalty_weight) * slope_overbuild
    )

    final_static = utility - penalty
    return {
        "compactness_score": compactness,
        "green_access_score": green_access,
        "non_auto_access_score": non_auto_access,
        "utility_score": utility,
        "penalty_score": penalty,
        "static_final": final_static,
        "permeability_decline": permeability_decline,
        "auto_centrality_increase": auto_centrality_increase,
        "excessive_tower_morphology": excessive_tower_morphology,
        "green_inequity": green_inequity,
        "access_regression": access_regression,
        "flood_exposure_increase": flood_exposure,
        "slope_overbuild": slope_overbuild,
    }


def pareto_frontier(df: pd.DataFrame, objective_cols: list[str]) -> pd.DataFrame:
    """Return non-dominated rows for maximizing objective columns.

    Parameters
    ----------
    df : pandas.DataFrame
        Candidate score table.
    objective_cols : list of str
        Column names to maximize jointly.

    Returns
    -------
    pandas.DataFrame
        Subset of Pareto-efficient rows.
    """

    values = df[objective_cols].to_numpy()
    keep = np.ones(len(df), dtype=bool)

    for i in range(len(df)):
        if not keep[i]:
            continue
        dominates = np.all(values >= values[i], axis=1) & np.any(values > values[i], axis=1)
        if np.any(dominates):
            keep[i] = False

    return df.loc[keep].copy()


def member_signature(cells: pd.DataFrame) -> set[str]:
    """Build a corridor signature for diversity filtering.

    Parameters
    ----------
    cells : pandas.DataFrame
        Member cell overlays.

    Returns
    -------
    set of str
        Set of high-intensity cell identifiers.
    """

    high = cells[cells["proposed_intensity_far"] >= 2.2]
    return set(high["cell_id"].astype(str).tolist())


def jaccard(a: set[str], b: set[str]) -> float:
    """Compute Jaccard similarity between two sets.

    Parameters
    ----------
    a : set of str
        First set.
    b : set of str
        Second set.

    Returns
    -------
    float
        Jaccard similarity in ``[0, 1]``.
    """

    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def select_diverse_top(
    scores: pd.DataFrame,
    signatures: dict[int, set[str]],
    top_n: int,
    score_col: str,
    max_jaccard: float = 0.8,
) -> pd.DataFrame:
    """Greedy diverse top-k selection by score and overlap threshold.

    Parameters
    ----------
    scores : pandas.DataFrame
        Scored member table.
    signatures : dict of int to set of str
        Member signatures used for overlap filtering.
    top_n : int
        Number of members to select.
    score_col : str
        Ranking column name.
    max_jaccard : float, default=0.8
        Maximum allowed pairwise Jaccard similarity.

    Returns
    -------
    pandas.DataFrame
        Selected top members with diversity constraint.
    """

    ordered = scores.sort_values(score_col, ascending=False)
    selected_rows: list[pd.Series] = []
    selected_ids: list[int] = []

    for _, row in ordered.iterrows():
        member_id = int(row["member_id"])
        sig = signatures.get(member_id, set())
        if all(jaccard(sig, signatures.get(existing, set())) <= max_jaccard for existing in selected_ids):
            selected_rows.append(row)
            selected_ids.append(member_id)
        if len(selected_rows) >= top_n:
            break

    if not selected_rows:
        return ordered.head(top_n).copy()

    return pd.DataFrame(selected_rows)

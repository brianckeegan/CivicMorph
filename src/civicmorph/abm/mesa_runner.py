"""Mesa-backed (or mesa-guarded) ABM evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from civicmorph.deps import validate_mesa_version
from civicmorph.io import read_dataframe
from civicmorph.types import ABMConfig, ABMPenaltyBreakdown, ABMResult, BaselineContext, PlanMember


def _sample_agents(cells: pd.DataFrame, max_agents: int, rng: np.random.Generator) -> pd.DataFrame:
    """Downsample inhabited cells into ABM agents.

    Parameters
    ----------
    cells : pandas.DataFrame
        Member cell overlay table.
    max_agents : int
        Maximum number of agents.
    rng : numpy.random.Generator
        Random generator for reproducible sampling.

    Returns
    -------
    pandas.DataFrame
        Sampled agent table.
    """

    inhabited = cells[cells["inhabited"] > 0].copy()
    if inhabited.empty:
        return cells.head(0).copy()

    if len(inhabited) <= max_agents:
        return inhabited

    # Stratified downsample by FAR bands to preserve morphology diversity.
    inhabited["far_band"] = pd.cut(
        inhabited["proposed_intensity_far"],
        bins=[0.49, 1.2, 2.5, 4.0, 5.1],
        labels=["low", "medium", "corridor", "node"],
    )
    samples: list[pd.DataFrame] = []
    for _, frame in inhabited.groupby("far_band", observed=True):
        frac = len(frame) / len(inhabited)
        n = max(1, int(round(frac * max_agents)))
        idx = rng.choice(frame.index.to_numpy(), size=min(n, len(frame)), replace=False)
        samples.append(frame.loc[idx])

    return pd.concat(samples, ignore_index=True)


def run_mesa_evaluation(plan: PlanMember, baseline: BaselineContext, cfg: ABMConfig, seed: int) -> ABMResult:
    """Run deterministic post-plan ABM metrics and penalty calculation.

    The function enforces Mesa availability via dependency check while using a lightweight
    deterministic simulation suitable for batch scoring.

    Parameters
    ----------
    plan : PlanMember
        Plan member artifacts to evaluate.
    baseline : BaselineContext
        Baseline run context for regression comparisons.
    cfg : ABMConfig
        ABM runtime configuration.
    seed : int
        Deterministic random seed.

    Returns
    -------
    ABMResult
        ABM metrics and aggregated penalty values.

    Raises
    ------
    OptionalDependencyError
        Raised when Mesa dependency is unavailable.
    """

    validate_mesa_version()

    rng = np.random.default_rng(seed + plan.member_id)
    cells = read_dataframe(plan.cells_path)
    baseline_cells = read_dataframe(baseline.cells_path)

    agents = _sample_agents(cells, cfg.max_agents, rng)
    if agents.empty:
        return ABMResult(
            member_id=plan.member_id,
            abm_non_auto_mode_share=0.0,
            abm_median_daily_needs_minutes=60.0,
            abm_public_space_visit_rate=0.0,
            abm_access_equity_gap=1.0,
            abm_penalty=1.0,
            penalty_breakdown=ABMPenaltyBreakdown(
                non_auto_regression=0.4,
                daily_needs_regression=0.3,
                public_space_regression=0.2,
                equity_regression=0.1,
            ),
        )

    # Mode utility proxy over simulation ticks.
    walk_pref = np.clip(0.4 + agents["car_deemphasis_score"].to_numpy() * 0.5, 0, 1)
    bike_pref = np.clip(0.25 + agents["car_deemphasis_score"].to_numpy() * 0.35, 0, 1)
    transit_pref = np.clip(0.3 + agents["proposed_intensity_far"].to_numpy() / 7.0, 0, 1)

    non_auto_draws = []
    needs_minutes = []
    public_space_visits = []
    for _ in range(cfg.ticks):
        noise = rng.normal(0, 0.08, size=len(agents))
        walk = np.clip(walk_pref + noise, 0, 1)
        bike = np.clip(bike_pref + noise, 0, 1)
        transit = np.clip(transit_pref + noise, 0, 1)
        auto = np.clip(1 - (0.4 * walk + 0.3 * bike + 0.3 * transit), 0, 1)

        probs = np.vstack([walk, bike, transit, auto]).T
        probs = probs / probs.sum(axis=1, keepdims=True)
        draws = rng.random(size=len(agents))
        non_auto = (draws < probs[:, 0] + probs[:, 1] + probs[:, 2]).astype(float)
        non_auto_draws.append(float(non_auto.mean()))

        travel = np.clip(
            agents["baseline_daily_needs_min"].to_numpy() * (1.0 - 0.35 * non_auto) + rng.normal(0, 2.0, size=len(agents)),
            4,
            90,
        )
        needs_minutes.append(float(np.median(travel)))

        visit = np.clip(
            0.2 + agents["green_access_score"].to_numpy() * 0.6 + 0.15 * non_auto + rng.normal(0, 0.06, size=len(agents)),
            0,
            1,
        )
        public_space_visits.append(float(visit.mean()))

    abm_non_auto = float(np.mean(non_auto_draws))
    abm_needs_minutes = float(np.mean(needs_minutes))
    abm_public_space = float(np.mean(public_space_visits))

    quint = pd.qcut(agents["x"], q=min(5, max(2, agents["x"].nunique())), duplicates="drop")
    equity_gap = agents.assign(non_auto=non_auto_draws[-1]).groupby(quint, observed=True)["non_auto"].mean()
    abm_equity_gap = float(max(0.0, equity_gap.max() - equity_gap.min())) if not equity_gap.empty else 0.0

    baseline_non_auto = float(baseline_cells["baseline_non_auto_score"].mean())
    baseline_needs = float(baseline_cells["baseline_daily_needs_min"].median())
    baseline_public_space = float(baseline_cells["baseline_green_access_score"].mean())

    breakdown = ABMPenaltyBreakdown(
        non_auto_regression=max(0.0, baseline_non_auto - abm_non_auto),
        daily_needs_regression=max(0.0, (abm_needs_minutes - baseline_needs) / 60.0),
        public_space_regression=max(0.0, baseline_public_space - abm_public_space),
        equity_regression=max(0.0, abm_equity_gap),
    )

    penalty = (
        cfg.non_auto_weight * breakdown.non_auto_regression
        + cfg.needs_time_weight * breakdown.daily_needs_regression
        + cfg.public_space_weight * breakdown.public_space_regression
        + cfg.equity_weight * breakdown.equity_regression
    )

    return ABMResult(
        member_id=plan.member_id,
        abm_non_auto_mode_share=abm_non_auto,
        abm_median_daily_needs_minutes=abm_needs_minutes,
        abm_public_space_visit_rate=abm_public_space,
        abm_access_equity_gap=abm_equity_gap,
        abm_penalty=float(np.clip(penalty, 0, 1.5)),
        penalty_breakdown=breakdown,
    )


def abm_result_to_frame(result: ABMResult) -> pd.DataFrame:
    """Convert ABM result to a single-row dataframe.

    Parameters
    ----------
    result : ABMResult
        ABM result object.

    Returns
    -------
    pandas.DataFrame
        One-row table for persistence and merging.
    """

    row = result.to_row()
    return pd.DataFrame([row])

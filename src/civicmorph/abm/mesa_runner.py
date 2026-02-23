"""Mesa-backed (or mesa-guarded) simulation evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from civicmorph.deps import validate_mesa_version
from civicmorph.io import read_dataframe
from civicmorph.types import ABMConfig, ABMPenaltyBreakdown, ABMResult, BaselineContext, PlanMember

SUPPORTED_MESA_SIMULATION_OPTIONS = {
    "abm",
    "dla",
    "ca",
    "network",
    "multi_scale",
}


@dataclass
class _SimulationSignals:
    """Intermediate simulation signals before regression penalties are applied."""

    non_auto_mode_share: float
    median_daily_needs_minutes: float
    public_space_visit_rate: float
    access_equity_gap: float
    growth_focus_index: float
    capacity_utilization: float
    network_access_gain: float


def _sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    """Compute logistic transform with clipping for numeric stability.

    Parameters
    ----------
    x : numpy.ndarray or float
        Input values.

    Returns
    -------
    numpy.ndarray or float
        Logistic transformed values.
    """

    arr = np.clip(x, -20.0, 20.0)
    return 1.0 / (1.0 + np.exp(-arr))


def _series(df: pd.DataFrame, col: str, default: float) -> np.ndarray:
    """Read a dataframe column with scalar fallback.

    Parameters
    ----------
    df : pandas.DataFrame
        Source table.
    col : str
        Column name.
    default : float
        Fill value when column is absent.

    Returns
    -------
    numpy.ndarray
        Numeric vector.
    """

    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(default).to_numpy(dtype=float)
    return np.full(len(df), default, dtype=float)


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

    inhabited = cells[cells.get("inhabited", 1) > 0].copy()
    if inhabited.empty:
        return cells.head(0).copy()

    if len(inhabited) <= max_agents:
        return inhabited

    inhabited["far_band"] = pd.cut(
        pd.to_numeric(inhabited.get("proposed_intensity_far", 1.0), errors="coerce").fillna(1.0),
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


def _equity_gap(x: np.ndarray, value: np.ndarray) -> float:
    """Compute intra-city equity gap as max-min quintile mean.

    Parameters
    ----------
    x : numpy.ndarray
        Positional axis used for grouping.
    value : numpy.ndarray
        Metric values to compare.

    Returns
    -------
    float
        Equity gap in the closed interval ``[0, 1]``.
    """

    if len(value) == 0:
        return 1.0

    temp = pd.DataFrame({"x": x, "value": value})
    if temp["x"].nunique() < 2:
        return 0.0
    try:
        bins = pd.qcut(temp["x"], q=min(5, max(2, temp["x"].nunique())), duplicates="drop")
    except ValueError:
        return 0.0
    grouped = temp.groupby(bins, observed=True)["value"].mean()
    if grouped.empty:
        return 0.0
    return float(np.clip(grouped.max() - grouped.min(), 0.0, 1.0))


def _base_fields(cells: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Extract normalized simulation vectors from member cells.

    Parameters
    ----------
    cells : pandas.DataFrame
        Member overlay table.

    Returns
    -------
    tuple of numpy.ndarray
        Arrays for ``x``, ``access``, ``green``, ``constraints``, ``intensity``, and ``needs``.
    """

    x = _series(cells, "x", 0.0)
    base_needs = np.clip(_series(cells, "baseline_daily_needs_min", 24.0), 4.0, 90.0)
    access = np.clip(
        0.55 * _series(cells, "car_deemphasis_score", 0.5)
        + 0.45 * (1.0 - np.clip(base_needs / 40.0, 0.0, 1.0)),
        0.0,
        1.0,
    )
    green = np.clip(_series(cells, "green_access_score", 0.4), 0.0, 1.0)
    constraints = np.clip(
        0.5 * _series(cells, "flood_risk_score", 0.25)
        + 0.5 * _series(cells, "slope_constraint_score", 0.25),
        0.0,
        1.0,
    )
    intensity = np.clip(_series(cells, "proposed_intensity_far", 1.3), 0.5, 5.0)
    return x, access, green, constraints, intensity, base_needs


def _simulate_dla_growth(cells: pd.DataFrame, cfg: ABMConfig, rng: np.random.Generator) -> _SimulationSignals:
    """Run DLA-inspired growth where development particles attach to seed clusters.

    Parameters
    ----------
    cells : pandas.DataFrame
        Member overlay table.
    cfg : ABMConfig
        Simulation configuration.
    rng : numpy.random.Generator
        Deterministic random generator.

    Returns
    -------
    _SimulationSignals
        Mode-specific metrics before penalty translation.
    """

    if cells.empty:
        return _SimulationSignals(0.0, 60.0, 0.0, 1.0, 0.0, 0.0, 0.0)

    x, access, green, constraints, intensity, base_needs = _base_fields(cells)
    y = _series(cells, "y", 0.0)

    center_x = float(np.mean(x))
    center_y = float(np.mean(y))
    centrality = 1.0 / (1.0 + np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2))
    activity = np.clip(1.0 - base_needs / 45.0, 0.0, 1.0)

    seed_score = 0.4 * access + 0.35 * centrality + 0.25 * activity
    seed_count = int(np.clip(cfg.dla_seed_count, 3, max(3, len(cells))))
    seed_idx = np.argsort(seed_score)[-seed_count:]

    cluster_mass = np.zeros(len(cells), dtype=float)
    cluster_mass[seed_idx] = 1.0
    growth_events = np.zeros(len(cells), dtype=float)

    particle_events = int(np.clip(cfg.dla_particle_events, 10, 2000))
    for _ in range(particle_events):
        i = int(rng.integers(0, len(cells)))
        active = np.where(cluster_mass > 0)[0]
        if active.size == 0:
            active = seed_idx

        d = np.sqrt((x[i] - x[active]) ** 2 + (y[i] - y[active]) ** 2)
        nearest = float(np.min(d))
        attraction = (
            cfg.dla_attachment_strength / (1.0 + nearest)
            + 0.55 * access[i]
            - cfg.dla_constraint_weight * constraints[i]
        )
        p_attach = float(_sigmoid(attraction))
        if float(rng.random()) < p_attach:
            cluster_mass[i] += 1.0
            growth_events[i] += 1.0

    attached = growth_events > 0
    attached_share = float(attached.mean())
    growth_focus = float(
        np.clip(
            (np.quantile(growth_events, 0.9) - np.quantile(growth_events, 0.5))
            / max(1.0, np.quantile(growth_events, 0.9)),
            0.0,
            1.0,
        )
    )
    network_gain = float(np.clip(access[attached].mean() - access.mean(), 0.0, 1.0)) if attached.any() else 0.0
    capacity_utilization = float(np.clip(attached_share * 0.7 + cluster_mass.mean() / 4.0, 0.0, 1.0))

    non_auto = float(
        np.clip(
            access.mean()
            + 0.10 * attached_share
            + 0.06 * network_gain
            + 0.04 * cfg.policy_parking_reduction
            - 0.05 * constraints.mean(),
            0.0,
            1.0,
        )
    )
    needs = float(np.clip(np.median(base_needs * (1.0 - 0.30 * non_auto) - 5.0 * growth_focus), 4.0, 90.0))
    public_space = float(np.clip(green.mean() + 0.06 * cfg.policy_green_protection, 0.0, 1.0))
    equity = _equity_gap(x, np.clip(access + 0.15 * attached.astype(float), 0.0, 1.0))

    return _SimulationSignals(
        non_auto_mode_share=non_auto,
        median_daily_needs_minutes=needs,
        public_space_visit_rate=public_space,
        access_equity_gap=equity,
        growth_focus_index=growth_focus,
        capacity_utilization=capacity_utilization,
        network_access_gain=network_gain,
    )


def _simulate_agent_based(cells: pd.DataFrame, cfg: ABMConfig, rng: np.random.Generator) -> _SimulationSignals:
    """Run heterogenous-budget ABM with policy feedback loops.

    Parameters
    ----------
    cells : pandas.DataFrame
        Member overlay table.
    cfg : ABMConfig
        Simulation configuration.
    rng : numpy.random.Generator
        Deterministic random generator.

    Returns
    -------
    _SimulationSignals
        Mode-specific metrics before penalty translation.
    """

    if cells.empty:
        return _SimulationSignals(0.0, 60.0, 0.0, 1.0, 0.0, 0.0, 0.0)

    x, access, green, constraints, intensity, base_needs = _base_fields(cells)
    access0 = access.copy()
    intensity0 = intensity.copy()

    n = len(cells)
    household_budget = rng.lognormal(
        mean=np.log(max(cfg.household_budget_mean, 1e-3)),
        sigma=max(cfg.household_budget_sigma, 1e-3),
        size=n,
    )
    developer_budget = rng.lognormal(
        mean=np.log(max(cfg.developer_budget_mean, 1e-3)),
        sigma=max(cfg.developer_budget_sigma, 1e-3),
        size=max(5, n // 8),
    )
    employer_budget = rng.lognormal(
        mean=np.log(max(cfg.employer_budget_mean, 1e-3)),
        sigma=max(cfg.employer_budget_sigma, 1e-3),
        size=max(5, n // 10),
    )

    planner_budget = float(cfg.city_planner_budget)
    transit_budget = float(cfg.transit_operator_budget)

    price = np.clip(0.75 + 0.22 * intensity + 0.12 * constraints, 0.35, 3.5)
    transit_service_trace: list[float] = []

    for _ in range(int(max(1, cfg.ticks))):
        affordability = household_budget.mean() / max(1e-6, price.mean())
        relocate_signal = (
            access.mean()
            + 0.18 * cfg.policy_affordable_housing
            + 0.10 * cfg.policy_parking_reduction
            - cfg.price_response_weight * price.mean()
            + 0.06 * np.log1p(affordability)
        )
        relocate_rate = float(_sigmoid(relocate_signal - 1.0))

        build_signal = (
            np.log1p(developer_budget.mean())
            + 0.30 * cfg.policy_upzone
            + 0.20 * cfg.policy_transit_investment
            - 0.55 * price.mean()
            + 0.08 * np.log1p(employer_budget.mean())
        )
        build_rate = float(_sigmoid(build_signal))

        planner_upzone = float(
            np.clip(0.02 * planner_budget + 0.24 * cfg.policy_upzone - 0.10 * constraints.mean(), 0.0, 1.0)
        )
        transit_invest = float(
            np.clip(
                0.02 * transit_budget + 0.30 * cfg.policy_transit_investment + 0.10 * cfg.corridor_frequency_scalar,
                0.0,
                1.0,
            )
        )
        transit_service_trace.append(transit_invest)

        access = np.clip(
            access
            + 0.030 * transit_invest
            + 0.015 * planner_upzone
            - 0.010 * price
            - 0.007 * constraints
            + rng.normal(0.0, 0.01, size=n),
            0.0,
            1.0,
        )
        intensity = np.clip(
            intensity + 0.05 * build_rate + 0.03 * planner_upzone - 0.04 * constraints,
            0.5,
            5.0,
        )
        price = np.clip(
            price
            + cfg.price_response_weight * (0.08 * relocate_rate + 0.12 * build_rate)
            - 0.03 * cfg.policy_affordable_housing,
            0.35,
            3.8,
        )

        planner_budget = max(0.0, planner_budget - 0.02 * n * planner_upzone)
        transit_budget = max(0.0, transit_budget - 0.015 * n * transit_invest)

    network_gain = float(np.clip(access.mean() - access0.mean(), 0.0, 1.0))
    capacity_utilization = float(
        np.clip((intensity.mean() - intensity0.mean()) / max(0.1, 5.0 - intensity0.mean()), 0.0, 1.0)
    )
    growth_focus = float(np.clip(np.std(intensity) / max(1e-6, intensity.mean()), 0.0, 1.0))

    transit_service = float(np.mean(transit_service_trace)) if transit_service_trace else 0.0
    non_auto = float(
        np.clip(
            0.75 * access.mean()
            + 0.12 * transit_service
            + 0.08 * cfg.policy_parking_reduction
            - 0.04 * constraints.mean(),
            0.0,
            1.0,
        )
    )
    needs = float(np.clip(np.median(base_needs * (1.0 - 0.35 * non_auto) - 6.0 * network_gain), 4.0, 90.0))
    public_space = float(
        np.clip(green.mean() + 0.05 * cfg.policy_green_protection + 0.02 * (1.0 - price.mean() / 3.8), 0.0, 1.0)
    )
    equity = _equity_gap(x, np.clip(access - 0.10 * (price / 3.8), 0.0, 1.0))

    return _SimulationSignals(
        non_auto_mode_share=non_auto,
        median_daily_needs_minutes=needs,
        public_space_visit_rate=public_space,
        access_equity_gap=equity,
        growth_focus_index=growth_focus,
        capacity_utilization=capacity_utilization,
        network_access_gain=network_gain,
    )


def _neighbor_map(x: np.ndarray, y: np.ndarray, tessellation: str) -> list[list[int]]:
    """Build neighborhood index map for CA updates.

    Parameters
    ----------
    x : numpy.ndarray
        X coordinates.
    y : numpy.ndarray
        Y coordinates.
    tessellation : str
        Neighborhood topology: ``grid`` or ``hex``.

    Returns
    -------
    list of list of int
        Neighbor index lists aligned to input order.
    """

    coord_to_idx = {(int(xx), int(yy)): i for i, (xx, yy) in enumerate(zip(x, y, strict=True))}
    neighbors: list[list[int]] = []
    for xx, yy in zip(x, y, strict=True):
        xi = int(xx)
        yi = int(yy)
        if tessellation == "hex":
            if yi % 2 == 0:
                offsets = [(-1, 0), (1, 0), (0, -1), (-1, -1), (0, 1), (-1, 1)]
            else:
                offsets = [(-1, 0), (1, 0), (1, -1), (0, -1), (1, 1), (0, 1)]
        else:
            offsets = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1)]

        current = []
        for dx, dy in offsets:
            idx = coord_to_idx.get((xi + dx, yi + dy))
            if idx is not None:
                current.append(idx)
        neighbors.append(current)
    return neighbors


def _simulate_cellular_automata(cells: pd.DataFrame, cfg: ABMConfig, rng: np.random.Generator) -> _SimulationSignals:
    """Run stochastic CA land-use transition dynamics.

    Parameters
    ----------
    cells : pandas.DataFrame
        Member overlay table.
    cfg : ABMConfig
        Simulation configuration.
    rng : numpy.random.Generator
        Deterministic random generator.

    Returns
    -------
    _SimulationSignals
        Mode-specific metrics before penalty translation.
    """

    if cells.empty:
        return _SimulationSignals(0.0, 60.0, 0.0, 1.0, 0.0, 0.0, 0.0)

    x, access, green, constraints, intensity, base_needs = _base_fields(cells)
    y = _series(cells, "y", 0.0)

    states = np.digitize(intensity, bins=[1.2, 2.5, 4.0]).astype(float)
    neighbors = _neighbor_map(x, y, cfg.ca_tessellation)

    for _ in range(int(max(1, cfg.ticks))):
        updated = states.copy()
        for i in range(len(states)):
            neigh = neighbors[i]
            neigh_state = float(np.mean(states[neigh])) if neigh else float(states[i])
            score = (
                cfg.ca_neighborhood_weight * (neigh_state / 3.0)
                + cfg.ca_accessibility_weight * access[i]
                + cfg.ca_zoning_weight * cfg.policy_upzone
                - cfg.ca_constraint_weight * constraints[i]
            )
            p_up = float(_sigmoid(2.0 * score)) * cfg.ca_stochastic_weight
            if float(rng.random()) < p_up:
                updated[i] = min(3.0, states[i] + 1.0)

            p_down = float(_sigmoid(3.0 * (constraints[i] - 0.70))) * 0.10
            if float(rng.random()) < p_down:
                updated[i] = max(0.0, updated[i] - 1.0)

        states = updated

    capacity_utilization = float(np.clip(states.mean() / 3.0, 0.0, 1.0))
    growth_focus = float(np.clip((np.quantile(states, 0.9) - np.quantile(states, 0.5)) / 3.0, 0.0, 1.0))
    network_gain = float(np.clip((access + 0.05 * states / 3.0).mean() - access.mean(), 0.0, 1.0))

    non_auto = float(
        np.clip(
            access.mean()
            + 0.10 * capacity_utilization
            + 0.04 * cfg.policy_parking_reduction
            - 0.05 * constraints.mean(),
            0.0,
            1.0,
        )
    )
    needs = float(np.clip(np.median(base_needs * (1.0 - 0.25 * non_auto) + (1.0 - capacity_utilization) * 3.0), 4.0, 90.0))
    public_space = float(np.clip(green.mean() + 0.04 * cfg.policy_green_protection, 0.0, 1.0))
    equity = _equity_gap(x, np.clip(access + 0.10 * (states / 3.0), 0.0, 1.0))

    return _SimulationSignals(
        non_auto_mode_share=non_auto,
        median_daily_needs_minutes=needs,
        public_space_visit_rate=public_space,
        access_equity_gap=equity,
        growth_focus_index=growth_focus,
        capacity_utilization=capacity_utilization,
        network_access_gain=network_gain,
    )


def _simulate_network_growth(cells: pd.DataFrame, cfg: ABMConfig, rng: np.random.Generator) -> _SimulationSignals:
    """Run network-intervention accessibility growth simulation.

    Parameters
    ----------
    cells : pandas.DataFrame
        Member overlay table.
    cfg : ABMConfig
        Simulation configuration.
    rng : numpy.random.Generator
        Deterministic random generator.

    Returns
    -------
    _SimulationSignals
        Mode-specific metrics before penalty translation.
    """

    if cells.empty:
        return _SimulationSignals(0.0, 60.0, 0.0, 1.0, 0.0, 0.0, 0.0)

    x, access, green, constraints, intensity, base_needs = _base_fields(cells)

    intervention_strength = (
        0.025 * cfg.network_new_links
        + 0.004 * cfg.network_bus_lane_km
        + 0.045 * cfg.network_station_infill
        + 0.050 * cfg.policy_transit_investment
    )
    centrality_gain = np.clip(intervention_strength * (0.6 + 0.4 * access), 0.0, 0.65)

    generalized_access = np.clip(
        access
        + cfg.objective_15min_weight * centrality_gain
        + 0.06 * cfg.policy_parking_reduction
        - 0.10 * constraints,
        0.0,
        1.0,
    )
    network_gain = float(np.clip(np.mean(generalized_access - access), 0.0, 1.0))

    intensity_new = np.clip(intensity + 0.9 * generalized_access * cfg.corridor_frequency_scalar, 0.5, 5.0)
    capacity_utilization = float(
        np.clip(np.mean((intensity_new - intensity) / np.maximum(0.1, 5.0 - intensity)), 0.0, 1.0)
    )
    growth_focus = float(
        np.clip(
            (np.quantile(intensity_new - intensity, 0.9) - np.quantile(intensity_new - intensity, 0.5)) / 2.0,
            0.0,
            1.0,
        )
    )

    non_auto = float(np.clip(generalized_access.mean(), 0.0, 1.0))
    needs = float(np.clip(np.median(base_needs * (1.0 - 0.45 * generalized_access)), 4.0, 90.0))
    public_space = float(np.clip(green.mean() + 0.03 * cfg.policy_green_protection + 0.03 * network_gain, 0.0, 1.0))
    equity = _equity_gap(x, generalized_access)

    return _SimulationSignals(
        non_auto_mode_share=non_auto,
        median_daily_needs_minutes=needs,
        public_space_visit_rate=public_space,
        access_equity_gap=equity,
        growth_focus_index=growth_focus,
        capacity_utilization=capacity_utilization,
        network_access_gain=network_gain,
    )


def _simulate_multi_scale(cells: pd.DataFrame, cfg: ABMConfig, rng: np.random.Generator) -> _SimulationSignals:
    """Run a coupled multi-scale simulation across cell, corridor, and regional scales.

    Parameters
    ----------
    cells : pandas.DataFrame
        Member overlay table.
    cfg : ABMConfig
        Simulation configuration.
    rng : numpy.random.Generator
        Deterministic random generator.

    Returns
    -------
    _SimulationSignals
        Coupled multi-scale metrics before penalty translation.
    """

    ca_signals = _simulate_cellular_automata(cells, cfg, rng)
    network_signals = _simulate_network_growth(cells, cfg, rng)

    coupling = float(np.clip(cfg.parcel_to_corridor_coupling, 0.0, 1.0))
    regional_factor = float(
        np.clip(cfg.regional_growth_boundary_factor * (1.0 - 0.8 * cfg.regional_conservation_share), 0.25, 1.5)
    )

    non_auto = float(
        np.clip(
            coupling * ca_signals.non_auto_mode_share + (1.0 - coupling) * network_signals.non_auto_mode_share,
            0.0,
            1.0,
        )
    )
    needs = float(
        np.clip(
            coupling * ca_signals.median_daily_needs_minutes
            + (1.0 - coupling) * network_signals.median_daily_needs_minutes
            + (1.0 - regional_factor) * 7.0,
            4.0,
            90.0,
        )
    )
    public_space = float(
        np.clip(
            coupling * ca_signals.public_space_visit_rate
            + (1.0 - coupling) * network_signals.public_space_visit_rate
            + 0.05 * cfg.policy_green_protection * cfg.regional_conservation_share,
            0.0,
            1.0,
        )
    )
    equity = float(
        np.clip(
            coupling * ca_signals.access_equity_gap + (1.0 - coupling) * network_signals.access_equity_gap,
            0.0,
            1.0,
        )
    )

    growth_focus = float(
        np.clip(
            coupling * ca_signals.growth_focus_index + (1.0 - coupling) * network_signals.growth_focus_index,
            0.0,
            1.0,
        )
    )
    capacity = float(
        np.clip(
            regional_factor
            * (coupling * ca_signals.capacity_utilization + (1.0 - coupling) * network_signals.capacity_utilization),
            0.0,
            1.0,
        )
    )
    network_gain = float(
        np.clip(regional_factor * network_signals.network_access_gain * cfg.corridor_frequency_scalar, 0.0, 1.0)
    )

    return _SimulationSignals(
        non_auto_mode_share=non_auto,
        median_daily_needs_minutes=needs,
        public_space_visit_rate=public_space,
        access_equity_gap=equity,
        growth_focus_index=growth_focus,
        capacity_utilization=capacity,
        network_access_gain=network_gain,
    )


def _simulate_mode(cells: pd.DataFrame, cfg: ABMConfig, rng: np.random.Generator) -> _SimulationSignals:
    """Dispatch to selected Mesa simulation option.

    Parameters
    ----------
    cells : pandas.DataFrame
        Member overlay table.
    cfg : ABMConfig
        Simulation configuration.
    rng : numpy.random.Generator
        Deterministic random generator.

    Returns
    -------
    _SimulationSignals
        Mode-specific simulation outputs.

    Raises
    ------
    ValueError
        Raised when simulation mode is unsupported.
    """

    mode = cfg.simulation_mode.strip().lower()
    if mode not in SUPPORTED_MESA_SIMULATION_OPTIONS:
        raise ValueError(
            f"Unsupported ABM simulation mode '{cfg.simulation_mode}'. "
            f"Supported modes: {sorted(SUPPORTED_MESA_SIMULATION_OPTIONS)}"
        )

    if mode == "dla":
        return _simulate_dla_growth(cells, cfg, rng)
    if mode == "ca":
        return _simulate_cellular_automata(cells, cfg, rng)
    if mode == "network":
        return _simulate_network_growth(cells, cfg, rng)
    if mode == "multi_scale":
        return _simulate_multi_scale(cells, cfg, rng)
    return _simulate_agent_based(cells, cfg, rng)


def run_mesa_evaluation(plan: PlanMember, baseline: BaselineContext, cfg: ABMConfig, seed: int) -> ABMResult:
    """Run Mesa-configured simulation metrics and penalty calculation.

    Parameters
    ----------
    plan : PlanMember
        Plan member artifacts to evaluate.
    baseline : BaselineContext
        Baseline run context for regression comparisons.
    cfg : ABMConfig
        Simulation configuration with mode and policy levers.
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
    ValueError
        Raised when an unsupported simulation mode is requested.
    """

    validate_mesa_version()

    # Import is optional so tests can patch dependency checks in lightweight environments.
    try:  # pragma: no cover - optional runtime branch
        import mesa as _mesa  # noqa: F401
    except Exception:
        pass

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
            abm_mode=cfg.simulation_mode,
        )

    signals = _simulate_mode(agents, cfg, rng)

    baseline_non_auto = float(
        pd.to_numeric(baseline_cells.get("baseline_non_auto_score", pd.Series([0.4])), errors="coerce")
        .fillna(0.4)
        .mean()
    )
    baseline_needs = float(
        pd.to_numeric(baseline_cells.get("baseline_daily_needs_min", pd.Series([24.0])), errors="coerce")
        .fillna(24.0)
        .median()
    )
    baseline_public_space = float(
        pd.to_numeric(baseline_cells.get("baseline_green_access_score", pd.Series([0.4])), errors="coerce")
        .fillna(0.4)
        .mean()
    )

    breakdown = ABMPenaltyBreakdown(
        non_auto_regression=max(0.0, baseline_non_auto - signals.non_auto_mode_share),
        daily_needs_regression=max(0.0, (signals.median_daily_needs_minutes - baseline_needs) / 60.0),
        public_space_regression=max(0.0, baseline_public_space - signals.public_space_visit_rate),
        equity_regression=max(0.0, signals.access_equity_gap),
    )

    penalty = (
        cfg.non_auto_weight * breakdown.non_auto_regression
        + cfg.needs_time_weight * breakdown.daily_needs_regression
        + cfg.public_space_weight * breakdown.public_space_regression
        + cfg.equity_weight * breakdown.equity_regression
    )

    return ABMResult(
        member_id=plan.member_id,
        abm_non_auto_mode_share=signals.non_auto_mode_share,
        abm_median_daily_needs_minutes=signals.median_daily_needs_minutes,
        abm_public_space_visit_rate=signals.public_space_visit_rate,
        abm_access_equity_gap=signals.access_equity_gap,
        abm_penalty=float(np.clip(penalty, 0.0, 1.5)),
        penalty_breakdown=breakdown,
        abm_mode=cfg.simulation_mode,
        abm_growth_focus_index=signals.growth_focus_index,
        abm_capacity_utilization=signals.capacity_utilization,
        abm_network_access_gain=signals.network_access_gain,
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

"""Typed data models for CivicMorph runtime artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class BaselineContext:
    """Baseline artifact locations and metadata for a run."""

    project_dir: Path
    baseline_dir: Path
    crs: str
    cells_path: Path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanMember:
    """A generated ensemble member and artifact references."""

    member_id: int
    project_dir: Path
    member_dir: Path
    cells_path: Path
    blocks_path: Path
    transit_path: Path
    streets_path: Path
    green_path: Path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Graph2CitySeed:
    """Graph2City inbound seed structures mapped into CivicMorph."""

    source_path: Path
    crs: str
    graph2city_version: str
    nodes: pd.DataFrame = field(default_factory=pd.DataFrame)
    edges: pd.DataFrame = field(default_factory=pd.DataFrame)
    blocks: pd.DataFrame = field(default_factory=pd.DataFrame)
    activities: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass
class Graph2CityExportResult:
    """Graph2City outbound export metadata."""

    out_dir: Path
    manifest_path: Path
    graph2city_version: str
    layer_paths: dict[str, Path]


@dataclass
class ABMConfig:
    """Configuration for Mesa-backed agent-based evaluation."""

    max_agents: int = 5000
    ticks: int = 60
    simulation_mode: str = "abm"
    ca_tessellation: str = "grid"

    # Agent heterogeneity and budgets.
    household_budget_mean: float = 1.0
    household_budget_sigma: float = 0.35
    developer_budget_mean: float = 2.0
    developer_budget_sigma: float = 0.45
    employer_budget_mean: float = 1.5
    employer_budget_sigma: float = 0.30
    city_planner_budget: float = 2.5
    transit_operator_budget: float = 2.0

    # Policy levers and feedback controls.
    policy_upzone: float = 1.0
    policy_transit_investment: float = 1.0
    policy_affordable_housing: float = 1.0
    policy_parking_reduction: float = 1.0
    policy_green_protection: float = 1.0
    price_response_weight: float = 0.30

    # DLA-inspired growth controls.
    dla_particle_events: int = 350
    dla_attachment_strength: float = 1.6
    dla_constraint_weight: float = 1.0
    dla_seed_count: int = 12

    # Cellular automata controls.
    ca_neighborhood_weight: float = 0.35
    ca_accessibility_weight: float = 0.30
    ca_zoning_weight: float = 0.20
    ca_constraint_weight: float = 0.35
    ca_stochastic_weight: float = 0.75

    # Network intervention controls.
    network_new_links: int = 3
    network_bus_lane_km: float = 12.0
    network_station_infill: int = 2
    objective_15min_weight: float = 1.0

    # Multi-scale coupling controls.
    corridor_frequency_scalar: float = 1.0
    parcel_to_corridor_coupling: float = 0.55
    regional_growth_boundary_factor: float = 1.0
    regional_conservation_share: float = 0.20

    # Transit assumptions used when GTFS is absent.
    headway_assumptions: dict[str, float] = field(
        default_factory=lambda: {"bus": 12.0, "tram": 10.0, "rail": 8.0}
    )

    non_auto_weight: float = 0.4
    needs_time_weight: float = 0.3
    public_space_weight: float = 0.2
    equity_weight: float = 0.1


@dataclass
class ABMPenaltyBreakdown:
    """Penalty components from ABM-based post-plan evaluation."""

    non_auto_regression: float = 0.0
    daily_needs_regression: float = 0.0
    public_space_regression: float = 0.0
    equity_regression: float = 0.0


@dataclass
class ABMResult:
    """ABM metrics and aggregated penalties for one plan member."""

    member_id: int
    abm_non_auto_mode_share: float
    abm_median_daily_needs_minutes: float
    abm_public_space_visit_rate: float
    abm_access_equity_gap: float
    abm_penalty: float
    penalty_breakdown: ABMPenaltyBreakdown
    abm_mode: str = "abm"
    abm_growth_focus_index: float = 0.0
    abm_capacity_utilization: float = 0.0
    abm_network_access_gain: float = 0.0

    def to_row(self) -> dict[str, float | int]:
        """Convert ABM result to a flat row mapping.

        Returns
        -------
        dict of str to float or int
            Flattened metrics and penalty components.
        """

        row = {
            "member_id": self.member_id,
            "abm_non_auto_mode_share": self.abm_non_auto_mode_share,
            "abm_median_daily_needs_minutes": self.abm_median_daily_needs_minutes,
            "abm_public_space_visit_rate": self.abm_public_space_visit_rate,
            "abm_access_equity_gap": self.abm_access_equity_gap,
            "abm_penalty": self.abm_penalty,
            "abm_mode": self.abm_mode,
            "abm_growth_focus_index": self.abm_growth_focus_index,
            "abm_capacity_utilization": self.abm_capacity_utilization,
            "abm_network_access_gain": self.abm_network_access_gain,
            "abm_penalty_non_auto_regression": self.penalty_breakdown.non_auto_regression,
            "abm_penalty_daily_needs_regression": self.penalty_breakdown.daily_needs_regression,
            "abm_penalty_public_space_regression": self.penalty_breakdown.public_space_regression,
            "abm_penalty_equity_regression": self.penalty_breakdown.equity_regression,
        }
        return row


def dataclass_to_dict(instance: Any) -> dict[str, Any]:
    """Serialize dataclass instances recursively for storage and logging.

    Parameters
    ----------
    instance : Any
        Dataclass instance.

    Returns
    -------
    dict of str to Any
        Serialized dictionary with ``Path`` values converted to strings.
    """

    data = asdict(instance)
    for key, value in list(data.items()):
        if isinstance(value, Path):
            data[key] = str(value)
    return data

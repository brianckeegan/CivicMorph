"""Configuration models and loading utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover - fallback only used without pydantic
    BaseModel = None
    Field = None


if BaseModel:

    class SamplingConfig(BaseModel):
        ensemble_size: int = 50
        seed: int = 1
        method: str = "latin_hypercube"


    class ScoringConfig(BaseModel):
        permeability_penalty_weight: float = 0.15
        auto_centrality_penalty_weight: float = 0.15
        tower_morphology_penalty_weight: float = 0.10
        green_inequity_penalty_weight: float = 0.20
        access_regression_penalty_weight: float = 0.20
        flood_exposure_penalty_weight: float = 0.10
        slope_overbuild_penalty_weight: float = 0.10


    class ProfileConfig(BaseModel):
        name: str
        transit_investment_intensity: float = 1.0
        green_budget: float = 1.0
        street_conversion_budget: float = 1.0
        intensity_budget: float = 1.0
        terrain_sensitivity: float = 1.0


    class ExportConfig(BaseModel):
        top_n: int = 5
        include_graph2city: bool = False


    class RunConfig(BaseModel):
        profile: ProfileConfig
        sampling: SamplingConfig = Field(default_factory=SamplingConfig)
        scoring: ScoringConfig = Field(default_factory=ScoringConfig)
        export: ExportConfig = Field(default_factory=ExportConfig)

else:

    @dataclass
    class SamplingConfig:
        ensemble_size: int = 50
        seed: int = 1
        method: str = "latin_hypercube"


    @dataclass
    class ScoringConfig:
        permeability_penalty_weight: float = 0.15
        auto_centrality_penalty_weight: float = 0.15
        tower_morphology_penalty_weight: float = 0.10
        green_inequity_penalty_weight: float = 0.20
        access_regression_penalty_weight: float = 0.20
        flood_exposure_penalty_weight: float = 0.10
        slope_overbuild_penalty_weight: float = 0.10


    @dataclass
    class ProfileConfig:
        name: str
        transit_investment_intensity: float = 1.0
        green_budget: float = 1.0
        street_conversion_budget: float = 1.0
        intensity_budget: float = 1.0
        terrain_sensitivity: float = 1.0


    @dataclass
    class ExportConfig:
        top_n: int = 5
        include_graph2city: bool = False


    @dataclass
    class RunConfig:
        profile: ProfileConfig
        sampling: SamplingConfig = field(default_factory=SamplingConfig)
        scoring: ScoringConfig = field(default_factory=ScoringConfig)
        export: ExportConfig = field(default_factory=ExportConfig)


def _to_profile_config(data: dict[str, Any]) -> ProfileConfig:
    """Convert plain mapping data into a profile model.

    Parameters
    ----------
    data : dict of str to Any
        Parsed profile mapping.

    Returns
    -------
    ProfileConfig
        Validated profile configuration object.
    """

    if hasattr(ProfileConfig, "model_validate"):
        return ProfileConfig.model_validate(data)
    return ProfileConfig(**data)


def load_profile(profile_name: str, profiles_dir: Path | None = None) -> ProfileConfig:
    """Load a profile by name from YAML files.

    Parameters
    ----------
    profile_name : str
        Profile filename stem (without ``.yaml``).
    profiles_dir : Path or None, default=None
        Optional directory override for profile files.

    Returns
    -------
    ProfileConfig
        Loaded profile model.

    Raises
    ------
    FileNotFoundError
        Raised when profile file does not exist.
    """
    if profiles_dir is None:
        profiles_dir = Path(__file__).resolve().parents[2] / "config" / "profiles"
    path = profiles_dir / f"{profile_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Profile '{profile_name}' not found at {path}")

    data = yaml.safe_load(path.read_text()) or {}
    data.setdefault("name", profile_name)
    return _to_profile_config(data)

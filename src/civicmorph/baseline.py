"""Baseline build pipeline (OSM + terrain placeholders for v1)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from .io import ensure_dir, write_dataframe
from .types import BaselineContext


def _stable_seed(*parts: str) -> int:
    """Derive a deterministic integer seed from string parts.

    Parameters
    ----------
    *parts : str
        Stable input tokens such as file paths.

    Returns
    -------
    int
        Deterministic non-negative seed.
    """

    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _build_baseline_cells(seed: int, side: int = 25) -> pd.DataFrame:
    """Create deterministic synthetic baseline cells.

    Parameters
    ----------
    seed : int
        Random seed used for deterministic generation.
    side : int, default=25
        Number of grid cells along each side.

    Returns
    -------
    pandas.DataFrame
        Baseline cell table with terrain and access proxy attributes.
    """

    rng = np.random.default_rng(seed)
    rows: list[dict[str, float | int | str]] = []
    for ix in range(side):
        for iy in range(side):
            flood = float(np.clip(rng.normal(0.25 + (iy / side) * 0.25, 0.1), 0.0, 1.0))
            slope = float(np.clip(rng.normal(0.2 + (ix / side) * 0.35, 0.12), 0.0, 1.0))
            view = float(np.clip(rng.normal(0.35 + (ix / side) * 0.25, 0.15), 0.0, 1.0))
            base_access = float(np.clip(rng.normal(22 - (ix + iy) / side * 8, 4), 8, 40))
            green_access = float(np.clip(rng.normal(0.5 - flood * 0.2, 0.12), 0.0, 1.0))
            rows.append(
                {
                    "cell_id": f"c_{ix:03d}_{iy:03d}",
                    "x": ix,
                    "y": iy,
                    "inhabited": int(rng.random() > 0.2),
                    "baseline_daily_needs_min": base_access,
                    "baseline_non_auto_score": float(np.clip(1 - base_access / 40, 0, 1)),
                    "baseline_green_access_score": green_access,
                    "flood_risk_score": flood,
                    "slope_constraint_score": slope,
                    "view_shed_value_score": view,
                    "geometry_wkt": (
                        f"POLYGON(({ix*100} {iy*100}, {(ix+1)*100} {iy*100}, "
                        f"{(ix+1)*100} {(iy+1)*100}, {ix*100} {(iy+1)*100}, {ix*100} {iy*100}))"
                    ),
                }
            )
    return pd.DataFrame(rows)


def build_baseline(
    project_dir: Path,
    osm_pbf: Path,
    dem: Path | None = None,
    flood: Path | None = None,
    crs: str = "EPSG:3857",
) -> BaselineContext:
    """Build baseline artifacts from local inputs.

    This v1 implementation creates deterministic synthetic baseline layers while validating
    local input presence and artifact contracts.

    Parameters
    ----------
    project_dir : Path
        Run directory where baseline artifacts are written.
    osm_pbf : Path
        Local OSM extract path (required).
    dem : Path or None, default=None
        Optional local DEM raster path.
    flood : Path or None, default=None
        Optional local flood layer path.
    crs : str, default="EPSG:3857"
        Working coordinate reference system identifier.

    Returns
    -------
    BaselineContext
        Baseline context with artifact locations and metadata.

    Raises
    ------
    FileNotFoundError
        Raised when required input files do not exist.
    """

    if not osm_pbf.exists():
        raise FileNotFoundError(f"OSM file not found: {osm_pbf}")
    if dem is not None and not dem.exists():
        raise FileNotFoundError(f"DEM file not found: {dem}")
    if flood is not None and not flood.exists():
        raise FileNotFoundError(f"Flood file not found: {flood}")

    baseline_dir = ensure_dir(project_dir / "baseline")
    seed = _stable_seed(str(osm_pbf.resolve()), str(dem) if dem else "", str(flood) if flood else "")

    cells = _build_baseline_cells(seed)
    cells_path = baseline_dir / "cells_baseline.parquet"
    write_dataframe(cells, cells_path)

    # Graph placeholders (walk/bike/drive) for consistent downstream contracts.
    graph_rows = pd.DataFrame(
        [
            {"u": "n1", "v": "n2", "mode": "walk", "weight": 1.0},
            {"u": "n2", "v": "n3", "mode": "bike", "weight": 0.8},
            {"u": "n1", "v": "n3", "mode": "drive", "weight": 0.5},
        ]
    )
    write_dataframe(graph_rows[graph_rows["mode"] == "walk"], baseline_dir / "graphs_walk.graphml")
    write_dataframe(graph_rows[graph_rows["mode"] == "bike"], baseline_dir / "graphs_bike.graphml")
    write_dataframe(graph_rows[graph_rows["mode"] == "drive"], baseline_dir / "graphs_drive.graphml")

    # Terrain placeholders.
    slope = cells[["cell_id", "slope_constraint_score", "x", "y"]].copy()
    flood_df = cells[["cell_id", "flood_risk_score", "x", "y"]].copy()
    viewshed = cells[["cell_id", "view_shed_value_score", "x", "y"]].copy()
    write_dataframe(slope, baseline_dir / "terrain_slope.tif")
    write_dataframe(flood_df, baseline_dir / "terrain_flood.tif")
    write_dataframe(viewshed, baseline_dir / "terrain_viewshed.tif")

    public_green = cells[cells["baseline_green_access_score"] > 0.55][
        ["cell_id", "x", "y", "baseline_green_access_score"]
    ].copy()
    public_green.rename(columns={"baseline_green_access_score": "green_score"}, inplace=True)
    write_dataframe(public_green, baseline_dir / "public_green.gpkg")

    metadata = {
        "crs": crs,
        "cell_count": int(cells.shape[0]),
        "dem_used": bool(dem),
        "flood_layer_used": bool(flood),
    }

    return BaselineContext(
        project_dir=project_dir,
        baseline_dir=baseline_dir,
        crs=crs,
        cells_path=cells_path,
        metadata=metadata,
    )

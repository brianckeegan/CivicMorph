"""Baseline build pipeline (OSM + terrain placeholders for v1)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from .data_sources import (
    retrieve_constraint_masks,
    retrieve_dem_data,
    retrieve_flood_data,
    retrieve_osm_data,
)
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
    osm_pbf: Path | None = None,
    place_name: str | None = None,
    study_area: Path | None = None,
    dem: Path | None = None,
    flood: Path | None = None,
    constraint_masks: list[Path] | None = None,
    transit_headway_assumptions: dict[str, float] | None = None,
    crs: str = "EPSG:3857",
) -> BaselineContext:
    """Build baseline artifacts from local inputs.

    This v1 implementation creates deterministic synthetic baseline layers while validating
    local input presence and artifact contracts.

    Parameters
    ----------
    project_dir : Path
        Run directory where baseline artifacts are written.
    osm_pbf : Path or None, default=None
        Local OSM extract path when available.
    place_name : str or None, default=None
        Optional place name selector for OSM-driven setup.
    study_area : Path or None, default=None
        Optional polygon selector path for OSM-driven setup.
    dem : Path or None, default=None
        Optional local DEM raster path.
    flood : Path or None, default=None
        Optional local flood layer path.
    constraint_masks : list of Path or None, default=None
        Optional user-supplied constraint mask layers.
    transit_headway_assumptions : dict of str to float or None, default=None
        Optional transit headway assumptions used when GTFS is absent.
    crs : str, default="EPSG:3857"
        Working coordinate reference system identifier.

    Returns
    -------
    BaselineContext
        Baseline context with artifact locations and metadata.

    Raises
    ------
    ValueError
        Raised when no OSM selector is provided.
    FileNotFoundError
        Raised when required input files do not exist.
    """

    if osm_pbf is None and not place_name and study_area is None:
        raise ValueError("Provide one OSM selector: osm_pbf, place_name, or study_area")
    if osm_pbf is not None and not osm_pbf.exists():
        raise FileNotFoundError(f"OSM file not found: {osm_pbf}")
    if study_area is not None and not study_area.exists():
        raise FileNotFoundError(f"Study-area polygon not found: {study_area}")
    if dem is not None and not dem.exists():
        raise FileNotFoundError(f"DEM file not found: {dem}")
    if flood is not None and not flood.exists():
        raise FileNotFoundError(f"Flood file not found: {flood}")
    for mask in constraint_masks or []:
        if not mask.exists():
            raise FileNotFoundError(f"Constraint mask file not found: {mask}")

    baseline_dir = ensure_dir(project_dir / "baseline")
    source_token = (
        str(osm_pbf.resolve())
        if osm_pbf is not None
        else place_name
        if place_name
        else study_area.read_text()
        if study_area is not None and study_area.exists()
        else "study_area"
    )
    seed = _stable_seed(source_token, str(dem) if dem else "", str(flood) if flood else "")

    osm_layers, osm_meta = retrieve_osm_data(
        osm_pbf=str(osm_pbf) if osm_pbf else None,
        place_name=place_name,
        study_area=str(study_area) if study_area else None,
        headway_assumptions=transit_headway_assumptions,
        constraint_masks=[str(mask) for mask in (constraint_masks or [])],
    )
    for layer_name, layer_df in osm_layers.items():
        write_dataframe(layer_df, baseline_dir / f"osm_{layer_name}.parquet")

    dem_table, dem_meta = retrieve_dem_data(
        dem_source=str(dem) if dem else None,
        seed_token=source_token,
        side=25,
    )
    write_dataframe(dem_table, baseline_dir / "dem_source.parquet")

    flood_table, flood_meta = retrieve_flood_data(
        flood_source=str(flood) if flood else None,
        dem_table=dem_table,
        seed_token=source_token,
        side=25,
    )
    write_dataframe(flood_table, baseline_dir / "flood_source.parquet")

    mask_table, mask_meta = retrieve_constraint_masks([str(mask) for mask in (constraint_masks or [])])
    write_dataframe(mask_table, baseline_dir / "constraint_masks.parquet")

    cells = _build_baseline_cells(seed)
    cells_path = baseline_dir / "cells_baseline.parquet"
    write_dataframe(cells, cells_path)

    # Graph approximations built from OSM extraction layers.
    streets = osm_layers.get("streets", pd.DataFrame())
    walk_paths = osm_layers.get("walk_paths", pd.DataFrame())
    drive_paths = osm_layers.get("drive_paths", streets)

    walk_graph = (
        walk_paths[[c for c in ["u", "v", "length_m"] if c in walk_paths.columns]].copy()
        if not walk_paths.empty
        else pd.DataFrame([{"u": "n1", "v": "n2", "length_m": 100.0}])
    )
    bike_graph = (
        walk_graph.copy().assign(length_m=lambda d: pd.to_numeric(d["length_m"], errors="coerce").fillna(100.0) * 0.9)
        if "length_m" in walk_graph.columns
        else walk_graph.copy()
    )
    drive_graph = (
        drive_paths[[c for c in ["u", "v", "length_m"] if c in drive_paths.columns]].copy()
        if not drive_paths.empty and {"u", "v"}.issubset(drive_paths.columns)
        else pd.DataFrame([{"u": "n1", "v": "n3", "length_m": 150.0}])
    )

    write_dataframe(walk_graph, baseline_dir / "graphs_walk.graphml")
    write_dataframe(bike_graph, baseline_dir / "graphs_bike.graphml")
    write_dataframe(drive_graph, baseline_dir / "graphs_drive.graphml")

    # Terrain placeholders.
    slope = cells[["cell_id", "slope_constraint_score", "x", "y"]].copy()
    flood_df = cells[["cell_id", "flood_risk_score", "x", "y"]].copy()
    viewshed = cells[["cell_id", "view_shed_value_score", "x", "y"]].copy()
    write_dataframe(slope, baseline_dir / "terrain_slope.tif")
    write_dataframe(flood_df, baseline_dir / "terrain_flood.tif")
    write_dataframe(viewshed, baseline_dir / "terrain_viewshed.tif")

    public_green = osm_layers.get("public_green", pd.DataFrame()).copy()
    if public_green.empty:
        public_green = cells[cells["baseline_green_access_score"] > 0.55][
            ["cell_id", "x", "y", "baseline_green_access_score"]
        ].copy()
        public_green.rename(columns={"baseline_green_access_score": "green_score"}, inplace=True)
    else:
        if "green_score" not in public_green.columns:
            public_green["green_score"] = 1.0
    write_dataframe(public_green, baseline_dir / "public_green.gpkg")

    metadata = {
        "crs": crs,
        "cell_count": int(cells.shape[0]),
        "dem_used": bool(dem),
        "flood_layer_used": bool(flood),
        "dem_source": dem_meta,
        "flood_source": flood_meta,
        "constraint_masks": mask_meta,
        "osm": osm_meta,
        "transit_routes_count": int(osm_layers.get("transit_routes", pd.DataFrame()).shape[0]),
        "transit_stops_count": int(osm_layers.get("transit_stops", pd.DataFrame()).shape[0]),
        "constraint_masks_count": len(constraint_masks or []),
    }

    return BaselineContext(
        project_dir=project_dir,
        baseline_dir=baseline_dir,
        crs=crs,
        cells_path=cells_path,
        metadata=metadata,
    )

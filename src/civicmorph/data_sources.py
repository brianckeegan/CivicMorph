"""Data retrieval helpers for OSM and auxiliary sources."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
import pandas as pd

from .osm import extract_osm_layers


def _is_http_source(source: str) -> bool:
    """Return whether a source string is an HTTP(S) URL.

    Parameters
    ----------
    source : str
        Source string.

    Returns
    -------
    bool
        ``True`` when source is HTTP or HTTPS.
    """

    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"}


def _ensure_existing_file(path: Path, label: str) -> Path:
    """Validate a local path exists.

    Parameters
    ----------
    path : Path
        Candidate path.
    label : str
        Source label used in error messages.

    Returns
    -------
    Path
        Normalized existing path.

    Raises
    ------
    FileNotFoundError
        Raised when path does not exist.
    """

    if not path.exists():
        raise FileNotFoundError(f"{label} file not found: {path}")
    return path


def _read_table_file(path: Path) -> pd.DataFrame:
    """Read a table-like file from disk.

    Parameters
    ----------
    path : Path
        Input file path.

    Returns
    -------
    pandas.DataFrame
        Loaded table.
    """

    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".json":
        return pd.read_json(path)
    if suffix in {".geojson", ".gpkg"}:
        # Keep retrieval lightweight without hard geopandas requirement.
        # If geopandas is available, use it; otherwise return a row-level placeholder.
        try:
            import geopandas as gpd  # pragma: no cover - optional runtime branch

            gdf = gpd.read_file(path)
            df = pd.DataFrame(gdf)
            if "geometry" in df.columns:
                df["geometry_wkt"] = df["geometry"].astype(str)
                df = df.drop(columns=["geometry"])
            return df
        except Exception:
            return pd.DataFrame([{"source_path": str(path), "source_format": suffix}])

    # Generic fallback to CSV reader semantics.
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame([{"source_path": str(path), "source_format": suffix or "unknown"}])


def retrieve_tabular_source(
    source: str | Path,
    *,
    allow_http: bool = False,
    timeout_s: float = 20.0,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Retrieve a tabular source from local path or optional HTTP URL.

    Parameters
    ----------
    source : str or Path
        Source location.
    allow_http : bool, default=False
        Whether HTTP(S) sources are allowed.
    timeout_s : float, default=20.0
        Timeout for HTTP requests in seconds.

    Returns
    -------
    tuple of pandas.DataFrame and dict
        Retrieved table and metadata.

    Raises
    ------
    ValueError
        Raised when HTTP sources are blocked by configuration.
    RuntimeError
        Raised when HTTP retrieval is requested but dependencies are unavailable.
    FileNotFoundError
        Raised when local file source is missing.
    """

    source_str = str(source)
    if _is_http_source(source_str):
        if not allow_http:
            raise ValueError("HTTP source retrieval is disabled; set allow_http=True to enable")
        try:
            import requests
        except Exception as exc:  # pragma: no cover - optional dependency branch
            raise RuntimeError("requests package is required for HTTP retrieval") from exc

        response = requests.get(source_str, timeout=timeout_s)
        response.raise_for_status()
        text = response.text

        if source_str.lower().endswith(".json"):
            payload = pd.read_json(text)
        else:
            from io import StringIO

            payload = pd.read_csv(StringIO(text))
        meta = {
            "source": source_str,
            "source_mode": "http",
            "row_count": int(payload.shape[0]),
        }
        return payload, meta

    path = _ensure_existing_file(Path(source_str), label="Data source")
    table = _read_table_file(path)
    meta = {
        "source": str(path),
        "source_mode": "local_file",
        "row_count": int(table.shape[0]),
    }
    return table, meta


def retrieve_constraint_masks(mask_paths: list[str | Path] | None) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Retrieve user-supplied constraint masks.

    Parameters
    ----------
    mask_paths : list of str or Path or None
        Optional paths to mask layers.

    Returns
    -------
    tuple of pandas.DataFrame and dict
        Constraint mask table and metadata summary.

    Raises
    ------
    FileNotFoundError
        Raised when a specified mask path is missing.
    """

    rows: list[dict[str, Any]] = []
    for mask in mask_paths or []:
        path = _ensure_existing_file(Path(mask), label="Constraint mask")
        rows.append(
            {
                "constraint_type": "user_mask",
                "source_path": str(path),
                "source_format": path.suffix.lower() or "unknown",
            }
        )

    table = pd.DataFrame(rows)
    meta = {
        "mask_count": int(table.shape[0]),
        "mask_paths": [str(v) for v in table.get("source_path", pd.Series(dtype=str)).tolist()],
    }
    return table, meta


def retrieve_dem_data(
    dem_source: str | Path | None,
    *,
    seed_token: str,
    side: int = 25,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Retrieve DEM-derived table from local source or synthetic fallback.

    Parameters
    ----------
    dem_source : str or Path or None
        DEM source file path.
    seed_token : str
        Deterministic token for fallback generation.
    side : int, default=25
        Grid side size for fallback surfaces.

    Returns
    -------
    tuple of pandas.DataFrame and dict
        DEM table and metadata.

    Raises
    ------
    FileNotFoundError
        Raised when a provided DEM path does not exist.
    """

    if dem_source is not None:
        path = _ensure_existing_file(Path(dem_source), label="DEM")
        try:
            table = _read_table_file(path)
            if table.empty:
                raise ValueError("empty DEM table")
            if "elevation_m" not in table.columns:
                table["elevation_m"] = 0.0
            meta = {
                "source": str(path),
                "source_mode": "local_file",
                "row_count": int(table.shape[0]),
                "synthetic": False,
            }
            return table, meta
        except Exception:
            # For raster-like sources we do not parse directly in lightweight mode.
            table = pd.DataFrame([{"source_path": str(path), "source_format": path.suffix.lower()}])
            table["elevation_m"] = 0.0
            meta = {
                "source": str(path),
                "source_mode": "local_file_placeholder",
                "row_count": int(table.shape[0]),
                "synthetic": False,
            }
            return table, meta

    seed = int(np.frombuffer(seed_token.encode("utf-8"), dtype=np.uint8).sum())
    rng = np.random.default_rng(seed)
    rows = []
    for x in range(side):
        for y in range(side):
            rows.append(
                {
                    "x": x,
                    "y": y,
                    "elevation_m": float(1600 + 20 * np.sin(x / 4) + 15 * np.cos(y / 5) + rng.normal(0, 2)),
                }
            )
    table = pd.DataFrame(rows)
    meta = {
        "source": None,
        "source_mode": "synthetic",
        "row_count": int(table.shape[0]),
        "synthetic": True,
    }
    return table, meta


def retrieve_flood_data(
    flood_source: str | Path | None,
    *,
    dem_table: pd.DataFrame | None,
    seed_token: str,
    side: int = 25,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Retrieve flood-risk table from source or derived fallback.

    Parameters
    ----------
    flood_source : str or Path or None
        Flood source path.
    dem_table : pandas.DataFrame or None
        DEM-like table used for derived flood fallback.
    seed_token : str
        Deterministic token for fallback generation.
    side : int, default=25
        Grid side size for synthetic fallback.

    Returns
    -------
    tuple of pandas.DataFrame and dict
        Flood table and metadata.

    Raises
    ------
    FileNotFoundError
        Raised when a provided flood path does not exist.
    """

    if flood_source is not None:
        path = _ensure_existing_file(Path(flood_source), label="Flood")
        table = _read_table_file(path)
        if "flood_risk_score" not in table.columns:
            table["flood_risk_score"] = 0.5
        meta = {
            "source": str(path),
            "source_mode": "local_file",
            "row_count": int(table.shape[0]),
            "derived": False,
        }
        return table, meta

    if dem_table is not None and not dem_table.empty and {"x", "y", "elevation_m"}.issubset(dem_table.columns):
        work = dem_table[["x", "y", "elevation_m"]].copy()
        elev = pd.to_numeric(work["elevation_m"], errors="coerce").fillna(work["elevation_m"].median())
        rank = elev.rank(pct=True)
        work["flood_risk_score"] = np.clip(1.0 - rank + 0.15 * np.sin(work["x"] / 3.0), 0.0, 1.0)
        meta = {
            "source": None,
            "source_mode": "derived_from_dem",
            "row_count": int(work.shape[0]),
            "derived": True,
        }
        return work[["x", "y", "flood_risk_score"]], meta

    seed = int(np.frombuffer(seed_token.encode("utf-8"), dtype=np.uint8).sum()) + 17
    rng = np.random.default_rng(seed)
    rows = []
    for x in range(side):
        for y in range(side):
            rows.append(
                {
                    "x": x,
                    "y": y,
                    "flood_risk_score": float(np.clip(0.2 + (y / side) * 0.4 + rng.normal(0, 0.08), 0.0, 1.0)),
                }
            )
    table = pd.DataFrame(rows)
    meta = {
        "source": None,
        "source_mode": "synthetic",
        "row_count": int(table.shape[0]),
        "derived": True,
    }
    return table, meta


def retrieve_osm_data(
    *,
    osm_pbf: str | Path | None,
    place_name: str | None,
    study_area: str | Path | None,
    headway_assumptions: dict[str, float] | None = None,
    constraint_masks: list[str | Path] | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Retrieve OSM layers from file/place/polygon selectors.

    Parameters
    ----------
    osm_pbf : str or Path or None
        Local OSM PBF source path.
    place_name : str or None
        Place-name selector.
    study_area : str or Path or None
        Study-area polygon selector path.
    headway_assumptions : dict of str to float or None, default=None
        Transit headway assumptions used when GTFS is absent.
    constraint_masks : list of str or Path or None, default=None
        Optional user-supplied mask paths.

    Returns
    -------
    tuple of dict and dict
        OSM layers mapping and extraction metadata.

    Raises
    ------
    ValueError
        Raised when no OSM selector is provided.
    """

    osm_path = Path(osm_pbf) if osm_pbf is not None else None
    area_path = Path(study_area) if study_area is not None else None
    mask_paths = [Path(p) for p in (constraint_masks or [])]

    layers, meta = extract_osm_layers(
        osm_pbf=osm_path,
        place_name=place_name,
        study_area=area_path,
        headway_assumptions=headway_assumptions,
        constraint_masks=mask_paths,
    )

    # Add explicit retrieval metadata for downstream consumers.
    meta = {
        **meta,
        "selector": {
            "osm_pbf": str(osm_path) if osm_path else None,
            "place_name": place_name,
            "study_area": str(area_path) if area_path else None,
        },
    }
    return layers, meta

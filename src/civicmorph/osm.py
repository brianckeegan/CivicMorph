"""OSM extraction helpers with deterministic fallback behavior."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _seed_from_token(token: str) -> int:
    """Build deterministic seed from source token.

    Parameters
    ----------
    token : str
        Input source token.

    Returns
    -------
    int
        Deterministic integer seed.
    """

    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _to_table(data: Any) -> pd.DataFrame:
    """Normalize extracted tabular or geospatial structures into plain dataframes.

    Parameters
    ----------
    data : Any
        Candidate table-like object.

    Returns
    -------
    pandas.DataFrame
        Plain dataframe with optional ``geometry_wkt`` projection.
    """

    if data is None:
        return pd.DataFrame()

    table = pd.DataFrame(data).copy()
    if "geometry" in table.columns:
        table["geometry_wkt"] = table["geometry"].astype(str)
        table = table.drop(columns=["geometry"])
    return table


def _transit_headway_defaults(headway_assumptions: dict[str, float] | None) -> dict[str, float]:
    """Resolve transit headway assumptions.

    Parameters
    ----------
    headway_assumptions : dict of str to float or None
        Optional overrides.

    Returns
    -------
    dict of str to float
        Headway assumptions by transit type.
    """

    base = {"bus": 12.0, "tram": 10.0, "rail": 8.0}
    if not headway_assumptions:
        return base
    for key, value in headway_assumptions.items():
        base[str(key).lower()] = float(value)
    return base


def _extract_with_pyrosm(
    osm_pbf: Path,
    headway_assumptions: dict[str, float],
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Attempt extracting OSM layers using pyrosm.

    Parameters
    ----------
    osm_pbf : Path
        Local OSM PBF file.
    headway_assumptions : dict of str to float
        Headway defaults when service frequency is unavailable.

    Returns
    -------
    tuple of dict and dict
        Layer tables and extraction metadata.

    Raises
    ------
    RuntimeError
        Raised when pyrosm extraction cannot be completed.
    """

    try:
        from pyrosm import OSM
    except Exception as exc:  # pragma: no cover - optional dependency branch
        raise RuntimeError("pyrosm is unavailable") from exc

    try:  # pragma: no cover - heavy branch not run in tests
        osm = OSM(str(osm_pbf))

        streets = _to_table(osm.get_network(network_type="driving"))
        walk_paths = _to_table(osm.get_network(network_type="walking"))
        buildings = _to_table(osm.get_buildings())
        landuse = _to_table(osm.get_landuse())
        amenities = _to_table(osm.get_pois())
        water = _to_table(osm.get_water())

        transit_routes = _to_table(
            osm.get_data_by_custom_criteria(
                custom_filter={"route": ["bus", "tram", "subway", "train", "light_rail"]},
                filter_type="keep",
                keep_nodes=False,
                keep_ways=True,
                keep_relations=True,
            )
        )
        transit_stops = _to_table(
            osm.get_pois(
                custom_filter={
                    "public_transport": ["platform", "stop_position"],
                    "highway": ["bus_stop"],
                    "railway": ["station", "halt"],
                }
            )
        )

        if "route" in transit_routes.columns:
            route_type = transit_routes["route"].astype(str).str.lower()
        else:
            route_type = pd.Series(["bus"] * len(transit_routes), index=transit_routes.index)

        transit_routes["route_type"] = route_type
        transit_routes["headway_min"] = (
            route_type.map(
                lambda r: headway_assumptions.get("rail")
                if r in {"subway", "train", "light_rail"}
                else headway_assumptions.get("tram")
                if r == "tram"
                else headway_assumptions.get("bus")
            )
            .astype(float)
        )
        transit_routes["service_source"] = "assumed_headway"

        public_green = landuse.copy()
        if "landuse" in public_green.columns:
            keep = public_green["landuse"].astype(str).str.lower().isin(
                {"park", "grass", "recreation_ground", "village_green", "allotments"}
            )
            public_green = public_green[keep].copy()

        constraints = pd.concat(
            [
                water.assign(constraint_type="water"),
                public_green.assign(constraint_type="park_or_green"),
            ],
            ignore_index=True,
            sort=False,
        )

        layers = {
            "streets": streets,
            "walk_paths": walk_paths,
            "drive_paths": streets.copy(),
            "transit_routes": transit_routes,
            "transit_stops": transit_stops,
            "buildings": buildings,
            "landuse": landuse,
            "amenities": amenities,
            "water": water,
            "public_green": public_green,
            "constraints": constraints,
        }
        meta = {
            "extractor": "pyrosm",
            "empirical_osm": True,
        }
        return layers, meta
    except Exception as exc:  # pragma: no cover - optional dependency branch
        raise RuntimeError(f"pyrosm extraction failed: {exc}") from exc


def _synthetic_osm_layers(
    source_token: str,
    headway_assumptions: dict[str, float],
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Create deterministic synthetic layers when OSM extraction is unavailable.

    Parameters
    ----------
    source_token : str
        OSM source token (place name, polygon hash, or file path).
    headway_assumptions : dict of str to float
        Headway defaults for synthetic transit routes.

    Returns
    -------
    tuple of dict and dict
        Layer tables and extraction metadata.
    """

    rng = np.random.default_rng(_seed_from_token(source_token))

    n_nodes = 180
    node_x = rng.integers(0, 40, size=n_nodes)
    node_y = rng.integers(0, 40, size=n_nodes)

    edge_rows = []
    walk_rows = []
    for i in range(n_nodes - 1):
        j = int((i + rng.integers(1, 8)) % n_nodes)
        length = float(np.hypot(node_x[i] - node_x[j], node_y[i] - node_y[j]) * 80 + 35)
        edge_rows.append({"edge_id": f"e_{i:04d}", "u": i, "v": j, "length_m": length, "mode": "drive"})
        walk_rows.append(
            {
                "edge_id": f"w_{i:04d}",
                "u": i,
                "v": j,
                "length_m": length * float(rng.uniform(0.8, 1.2)),
                "mode": "walk",
            }
        )

    streets = pd.DataFrame(edge_rows)
    walk_paths = pd.DataFrame(walk_rows)

    transit_types = ["bus", "tram", "rail"]
    transit_routes = pd.DataFrame(
        {
            "route_id": [f"r_{k:03d}" for k in range(9)],
            "route_type": [transit_types[k % 3] for k in range(9)],
            "headway_min": [headway_assumptions[transit_types[k % 3]] for k in range(9)],
            "service_source": ["assumed_headway"] * 9,
        }
    )
    transit_stops = pd.DataFrame(
        {
            "stop_id": [f"s_{k:03d}" for k in range(48)],
            "route_id": [f"r_{k % 9:03d}" for k in range(48)],
            "x": rng.integers(0, 40, size=48),
            "y": rng.integers(0, 40, size=48),
        }
    )

    buildings = pd.DataFrame(
        {
            "building_id": [f"b_{k:05d}" for k in range(480)],
            "levels": rng.integers(1, 8, size=480),
            "use": rng.choice(["residential", "mixed_use", "commercial", "civic"], size=480),
            "x": rng.integers(0, 40, size=480),
            "y": rng.integers(0, 40, size=480),
        }
    )

    landuse = pd.DataFrame(
        {
            "landuse_id": [f"l_{k:04d}" for k in range(140)],
            "landuse": rng.choice(
                ["residential", "commercial", "industrial", "park", "recreation_ground"],
                size=140,
                p=[0.45, 0.18, 0.10, 0.18, 0.09],
            ),
            "x": rng.integers(0, 40, size=140),
            "y": rng.integers(0, 40, size=140),
        }
    )

    amenities = pd.DataFrame(
        {
            "amenity_id": [f"a_{k:04d}" for k in range(220)],
            "amenity": rng.choice(
                ["school", "clinic", "pharmacy", "grocery", "cafe", "childcare", "park"],
                size=220,
            ),
            "x": rng.integers(0, 40, size=220),
            "y": rng.integers(0, 40, size=220),
        }
    )

    water = pd.DataFrame(
        {
            "water_id": [f"w_{k:03d}" for k in range(16)],
            "x": rng.integers(0, 40, size=16),
            "y": rng.integers(0, 40, size=16),
            "constraint_type": ["water"] * 16,
        }
    )

    public_green = landuse[landuse["landuse"].isin(["park", "recreation_ground"])].copy()
    public_green["is_public"] = 1

    constraints = pd.concat(
        [
            water[["x", "y", "constraint_type"]],
            public_green[["x", "y"]].assign(constraint_type="park_or_green"),
        ],
        ignore_index=True,
        sort=False,
    )

    layers = {
        "streets": streets,
        "walk_paths": walk_paths,
        "drive_paths": streets.copy(),
        "transit_routes": transit_routes,
        "transit_stops": transit_stops,
        "buildings": buildings,
        "landuse": landuse,
        "amenities": amenities,
        "water": water,
        "public_green": public_green,
        "constraints": constraints,
    }
    meta = {
        "extractor": "synthetic",
        "empirical_osm": False,
    }
    return layers, meta


def extract_osm_layers(
    osm_pbf: Path | None,
    place_name: str | None,
    study_area: Path | None,
    headway_assumptions: dict[str, float] | None = None,
    constraint_masks: list[Path] | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Extract OSM-driven layers from file, place, or polygon selectors.

    Parameters
    ----------
    osm_pbf : Path or None
        Local OSM PBF source when available.
    place_name : str or None
        Place name selector (for metadata and deterministic fallback behavior).
    study_area : Path or None
        Polygon selector path (GeoJSON/GPKG) for metadata and deterministic fallback behavior.
    headway_assumptions : dict of str to float or None, default=None
        Transit headway assumptions used when GTFS is not present.
    constraint_masks : list of Path or None, default=None
        Optional user-supplied mask layers.

    Returns
    -------
    tuple of dict and dict
        Mapping of extracted layer tables and extraction metadata.

    Raises
    ------
    ValueError
        Raised when no source selector is provided.
    """

    if osm_pbf is None and not place_name and study_area is None:
        raise ValueError("Provide at least one source selector: osm_pbf, place_name, or study_area")

    if osm_pbf is not None:
        source_mode = "osm_pbf"
        source_token = str(osm_pbf.resolve())
    elif place_name:
        source_mode = "place_name"
        source_token = place_name
    else:
        source_mode = "study_area"
        source_token = study_area.read_text() if study_area is not None and study_area.exists() else "study_area"

    headways = _transit_headway_defaults(headway_assumptions)

    layers: dict[str, pd.DataFrame]
    meta: dict[str, Any]
    if osm_pbf is not None:
        try:
            layers, meta = _extract_with_pyrosm(osm_pbf=osm_pbf, headway_assumptions=headways)
        except RuntimeError:
            layers, meta = _synthetic_osm_layers(source_token, headways)
            meta["extractor_fallback_reason"] = "pyrosm_unavailable_or_failed"
    else:
        layers, meta = _synthetic_osm_layers(source_token, headways)
        meta["extractor_fallback_reason"] = "offline_place_or_polygon_mode"

    mask_entries = []
    for mask in constraint_masks or []:
        mask_entries.append(
            {
                "constraint_type": "user_mask",
                "source_path": str(mask),
            }
        )

    if mask_entries:
        existing = layers.get("constraints", pd.DataFrame())
        layers["constraints"] = pd.concat([existing, pd.DataFrame(mask_entries)], ignore_index=True, sort=False)

    meta.update(
        {
            "source_mode": source_mode,
            "source_token_hash": hashlib.sha256(source_token.encode("utf-8")).hexdigest()[:16],
            "source_place_name": place_name,
            "source_polygon": str(study_area) if study_area else None,
            "headway_assumptions": headways,
            "constraint_masks": [str(p) for p in (constraint_masks or [])],
            "layer_counts": {name: int(df.shape[0]) for name, df in layers.items()},
        }
    )

    # Ensure transit route headways are populated.
    routes = layers.get("transit_routes", pd.DataFrame()).copy()
    if not routes.empty:
        if "route_type" not in routes.columns:
            routes["route_type"] = "bus"
        if "headway_min" not in routes.columns:
            routes["headway_min"] = routes["route_type"].map(headways).fillna(headways.get("bus", 12.0))
        if "service_source" not in routes.columns:
            routes["service_source"] = "assumed_headway"
        layers["transit_routes"] = routes

    return layers, meta

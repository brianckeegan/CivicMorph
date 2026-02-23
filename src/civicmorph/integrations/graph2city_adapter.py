"""Graph2City adapter boundary for CivicMorph."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from civicmorph.deps import validate_graph2city_version
from civicmorph.io import ensure_dir, read_dataframe, write_dataframe, write_json
from civicmorph.types import BaselineContext, Graph2CityExportResult, Graph2CitySeed, PlanMember


def _load_optional_table(base: Path, stem: str) -> pd.DataFrame:
    """Load a table from a Graph2City package directory if present.

    Parameters
    ----------
    base : Path
        Graph2City seed package directory.
    stem : str
        Filename stem to probe (without extension).

    Returns
    -------
    pandas.DataFrame
        Loaded table or empty dataframe if no matching file exists.
    """

    candidates = [
        base / f"{stem}.parquet",
        base / f"{stem}.csv",
        base / f"{stem}.gpkg",
        base / f"{stem}.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            if candidate.suffix in {".csv", ".json"}:
                if candidate.suffix == ".csv":
                    return pd.read_csv(candidate)
                return pd.read_json(candidate)
            return read_dataframe(candidate)
    return pd.DataFrame()


def import_graph2city(path: str, crs: str) -> Graph2CitySeed:
    """Import Graph2City seed layers from a local directory.

    Parameters
    ----------
    path : str
        Path to Graph2City seed package directory.
    crs : str
        Target CRS string for downstream processing metadata.

    Returns
    -------
    Graph2CitySeed
        Imported Graph2City seed object.

    Raises
    ------
    FileNotFoundError
        Raised when ``path`` is not an existing directory.
    OptionalDependencyError
        Raised when Graph2City dependency is unavailable.
    UnsupportedIntegrationVersionError
        Raised when Graph2City version is unsupported.
    """

    version = validate_graph2city_version()
    base = Path(path)
    if not base.exists() or not base.is_dir():
        raise FileNotFoundError(f"Graph2City input directory not found: {base}")

    return Graph2CitySeed(
        source_path=base,
        crs=crs,
        graph2city_version=version,
        nodes=_load_optional_table(base, "nodes"),
        edges=_load_optional_table(base, "edges"),
        blocks=_load_optional_table(base, "blocks"),
        activities=_load_optional_table(base, "activities"),
    )


def merge_seed_with_baseline(seed: Graph2CitySeed, baseline: BaselineContext) -> BaselineContext:
    """Merge Graph2City priors into baseline cells for downstream synthesis.

    Parameters
    ----------
    seed : Graph2CitySeed
        Graph2City seed tables.
    baseline : BaselineContext
        Baseline context to augment.

    Returns
    -------
    BaselineContext
        Updated baseline context with merged priors and metadata annotations.
    """

    cells = read_dataframe(baseline.cells_path)

    # Make merge idempotent if graph2city merge is called multiple times for the same run.
    drop_existing = [col for col in ["g2c_block_prior", "g2c_activity_prior"] if col in cells.columns]
    if drop_existing:
        cells = cells.drop(columns=drop_existing)

    if "cell_id" in seed.blocks.columns:
        block_prior = seed.blocks.groupby("cell_id", as_index=False).size().rename(columns={"size": "g2c_block_prior"})
        cells = cells.merge(block_prior, on="cell_id", how="left")
    else:
        cells["g2c_block_prior"] = 0

    if "cell_id" in seed.activities.columns:
        activity_prior = (
            seed.activities.groupby("cell_id", as_index=False).size().rename(columns={"size": "g2c_activity_prior"})
        )
        cells = cells.merge(activity_prior, on="cell_id", how="left")
    else:
        cells["g2c_activity_prior"] = 0

    cells["g2c_block_prior"] = cells["g2c_block_prior"].fillna(0)
    cells["g2c_activity_prior"] = cells["g2c_activity_prior"].fillna(0)

    write_dataframe(cells, baseline.cells_path)
    baseline.metadata["graph2city_seed_path"] = str(seed.source_path)
    baseline.metadata["graph2city_version"] = seed.graph2city_version
    baseline.metadata["graph2city_nodes"] = int(seed.nodes.shape[0])
    baseline.metadata["graph2city_edges"] = int(seed.edges.shape[0])
    return baseline


def export_plan_to_graph2city(plan: PlanMember, out_dir: str) -> Graph2CityExportResult:
    """Export CivicMorph plan member outputs into Graph2City package files.

    Parameters
    ----------
    plan : PlanMember
        Plan member artifact references.
    out_dir : str
        Destination directory for Graph2City export package.

    Returns
    -------
    Graph2CityExportResult
        Export metadata with manifest and layer paths.

    Raises
    ------
    OptionalDependencyError
        Raised when Graph2City dependency is unavailable.
    UnsupportedIntegrationVersionError
        Raised when Graph2City version is unsupported.
    """

    version = validate_graph2city_version()
    base = ensure_dir(Path(out_dir))

    cells = read_dataframe(plan.cells_path)
    blocks = read_dataframe(plan.blocks_path)
    transit = read_dataframe(plan.transit_path)
    streets = read_dataframe(plan.streets_path)

    layer_paths = {
        "cells": base / "cells.parquet",
        "blocks": base / "blocks.parquet",
        "transit": base / "transit.parquet",
        "streets": base / "streets.parquet",
    }
    write_dataframe(cells, layer_paths["cells"])
    write_dataframe(blocks, layer_paths["blocks"])
    write_dataframe(transit, layer_paths["transit"])
    write_dataframe(streets, layer_paths["streets"])

    manifest_path = base / "manifest.json"
    manifest = {
        "schema": "civicmorph.graph2city.v1",
        "graph2city_version": version,
        "member_id": plan.member_id,
        "layers": {k: str(v.name) for k, v in layer_paths.items()},
    }
    write_json(manifest, manifest_path)

    return Graph2CityExportResult(
        out_dir=base,
        manifest_path=manifest_path,
        graph2city_version=version,
        layer_paths=layer_paths,
    )

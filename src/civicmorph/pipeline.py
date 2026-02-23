"""Top-level pipeline orchestration for CivicMorph."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .abm.mesa_runner import abm_result_to_frame, run_mesa_evaluation
from .baseline import build_baseline as build_baseline_impl
from .blocks import generate_blocks
from .config import ScoringConfig, load_profile
from .integrations.graph2city_adapter import (
    export_plan_to_graph2city,
    import_graph2city,
    merge_seed_with_baseline,
)
from .io import (
    ensure_dir,
    read_dataframe,
    read_json,
    resolve_project_dir,
    write_dataframe,
    write_json,
)
from .render import render_composite_png, render_interactive_html
from .sampling import sample_ensemble_parameters
from .scoring import compute_static_scores, member_signature, pareto_frontier, select_diverse_top
from .synthesis import generate_green_network, generate_member_cells, generate_street_layer
from .transit import generate_transit
from .types import ABMConfig, BaselineContext, PlanMember


def _baseline_context(project_dir: Path) -> BaselineContext:
    """Build baseline context from an existing run directory.

    Parameters
    ----------
    project_dir : Path
        Run directory.

    Returns
    -------
    BaselineContext
        Baseline context object for downstream operations.

    Raises
    ------
    FileNotFoundError
        Raised when baseline artifacts are not present.
    """

    baseline_dir = project_dir / "baseline"
    cells_path = baseline_dir / "cells_baseline.parquet"
    if not cells_path.exists() and not (cells_path.with_name(cells_path.name + ".csv")).exists():
        raise FileNotFoundError("Baseline not found. Run build-baseline first.")
    return BaselineContext(
        project_dir=project_dir,
        baseline_dir=baseline_dir,
        crs="EPSG:3857",
        cells_path=cells_path,
        metadata={},
    )


def _member_paths(project_dir: Path, member_id: int) -> PlanMember:
    """Build canonical artifact paths for an ensemble member.

    Parameters
    ----------
    project_dir : Path
        Run directory.
    member_id : int
        Ensemble member identifier.

    Returns
    -------
    PlanMember
        Plan member object with standardized artifact paths.
    """

    member_dir = project_dir / "ensemble" / f"member_{member_id:03d}"
    return PlanMember(
        member_id=member_id,
        project_dir=project_dir,
        member_dir=member_dir,
        cells_path=member_dir / "cells_proposed.parquet",
        blocks_path=member_dir / "blocks.gpkg",
        transit_path=member_dir / "transit.gpkg",
        streets_path=member_dir / "streets_priority.gpkg",
        green_path=member_dir / "green_network.gpkg",
    )


def build_baseline(
    osm_pbf: str,
    dem: str | None = None,
    flood: str | None = None,
    project_dir: str | Path | None = None,
    graph2city_in: str | None = None,
) -> BaselineContext:
    """Execute baseline command workflow.

    Parameters
    ----------
    osm_pbf : str
        OSM PBF input file path.
    dem : str or None, default=None
        Optional DEM file path.
    flood : str or None, default=None
        Optional flood layer file path.
    project_dir : str or Path or None, default=None
        Optional run directory.
    graph2city_in : str or None, default=None
        Optional Graph2City seed package directory.

    Returns
    -------
    BaselineContext
        Baseline context and metadata.
    """

    resolved = resolve_project_dir(project_dir, create_if_missing=True)
    ctx = build_baseline_impl(
        project_dir=resolved,
        osm_pbf=Path(osm_pbf),
        dem=Path(dem) if dem else None,
        flood=Path(flood) if flood else None,
    )

    if graph2city_in:
        seed = import_graph2city(graph2city_in, ctx.crs)
        ctx = merge_seed_with_baseline(seed, ctx)

    write_json(
        {
            "project_dir": str(resolved),
            "baseline": ctx.metadata,
            "graph2city_enabled": bool(graph2city_in),
        },
        resolved / "run_manifest.json",
    )
    return ctx


def generate_ensemble(
    profile_name: str,
    ensemble_size: int = 50,
    seed: int = 1,
    project_dir: str | Path | None = None,
    seed_source: str = "osm",
    graph2city_in: str | None = None,
) -> pd.DataFrame:
    """Generate ensemble members and required plan artifacts.

    Parameters
    ----------
    profile_name : str
        Profile identifier.
    ensemble_size : int, default=50
        Number of members to generate.
    seed : int, default=1
        Deterministic seed.
    project_dir : str or Path or None, default=None
        Existing run directory.
    seed_source : {"osm", "graph2city", "hybrid"}, default="osm"
        Seed strategy for generation.
    graph2city_in : str or None, default=None
        Graph2City seed directory for graph2city/hybrid modes.

    Returns
    -------
    pandas.DataFrame
        Member artifact index table.

    Raises
    ------
    ValueError
        Raised when seed mode arguments are inconsistent.
    """

    project = resolve_project_dir(project_dir, create_if_missing=False)
    baseline = _baseline_context(project)

    if seed_source not in {"osm", "graph2city", "hybrid"}:
        raise ValueError("seed_source must be one of: osm, graph2city, hybrid")
    if seed_source in {"graph2city", "hybrid"} and not graph2city_in:
        raise ValueError("graph2city_in is required when seed_source is graph2city or hybrid")

    if graph2city_in:
        seed_data = import_graph2city(graph2city_in, baseline.crs)
        baseline = merge_seed_with_baseline(seed_data, baseline)

    profile = load_profile(profile_name)
    params = sample_ensemble_parameters(ensemble_size=ensemble_size, seed=seed)

    # Apply profile-level scalars.
    params["intensity_budget_scalar"] *= float(profile.intensity_budget)
    params["green_budget_scalar"] *= float(profile.green_budget)
    params["street_conversion_budget"] *= float(profile.street_conversion_budget)
    params["terrain_sensitivity_scalar"] *= float(profile.terrain_sensitivity)

    ensemble_dir = ensure_dir(project / "ensemble")
    write_dataframe(params, ensemble_dir / "samples.parquet")

    baseline_cells = read_dataframe(baseline.cells_path)
    if seed_source in {"graph2city", "hybrid"}:
        g2c_boost = 0.15 if seed_source == "graph2city" else 0.08
        baseline_cells["baseline_non_auto_score"] = np.clip(
            baseline_cells["baseline_non_auto_score"] + g2c_boost, 0, 1
        )

    records: list[dict[str, Any]] = []
    for _, row in params.iterrows():
        member_id = int(row["member_id"])
        member = _member_paths(project, member_id)
        ensure_dir(member.member_dir)

        param_dict = row.to_dict()
        cells = generate_member_cells(
            baseline_cells=baseline_cells,
            params=param_dict,
            member_id=member_id,
            seed=seed,
        )

        blocks = generate_blocks(cells, member_id=member_id, params=param_dict)
        lines, stops = generate_transit(cells, member_id=member_id, params=param_dict)
        transit = pd.concat(
            [
                lines.assign(feature_type="line"),
                stops.assign(feature_type="stop", type="Stop", headway_min=np.nan, speed_kmh=np.nan, stop_spacing_m=np.nan),
            ],
            ignore_index=True,
            sort=False,
        )
        streets = generate_street_layer(cells, member_id=member_id)
        green = generate_green_network(
            cells, member_id=member_id, green_budget_scalar=float(row["green_budget_scalar"])
        )

        write_dataframe(cells, member.cells_path)
        write_dataframe(blocks, member.blocks_path)
        write_dataframe(transit, member.transit_path)
        write_dataframe(streets, member.streets_path)
        write_dataframe(green, member.green_path)

        # Keep split transit files for rendering convenience.
        write_dataframe(lines, member.member_dir / "transit_lines.parquet")
        write_dataframe(stops, member.member_dir / "transit_stops.parquet")

        write_json(
            {
                "member_id": member_id,
                "seed": seed,
                "profile": profile_name,
                "seed_source": seed_source,
                "params": {k: (float(v) if isinstance(v, (int, float, np.number)) else str(v)) for k, v in param_dict.items()},
            },
            member.member_dir / "member_manifest.json",
        )

        records.append(
            {
                "member_id": member_id,
                "cells_path": str(member.cells_path),
                "blocks_path": str(member.blocks_path),
                "transit_path": str(member.transit_path),
                "streets_path": str(member.streets_path),
                "green_path": str(member.green_path),
            }
        )

    index_df = pd.DataFrame(records).sort_values("member_id")
    write_dataframe(index_df, ensemble_dir / "members.parquet")
    return index_df


def _iter_members(project: Path) -> list[PlanMember]:
    """Enumerate generated ensemble members in a run directory.

    Parameters
    ----------
    project : Path
        Run directory.

    Returns
    -------
    list of PlanMember
        Plan members in sorted order.

    Raises
    ------
    FileNotFoundError
        Raised when no generated members are found.
    """

    ensemble_dir = project / "ensemble"
    if not ensemble_dir.exists():
        raise FileNotFoundError("Ensemble directory not found. Run generate first.")

    members: list[PlanMember] = []
    for path in sorted(ensemble_dir.glob("member_*")):
        member_id = int(path.name.split("_")[-1])
        members.append(_member_paths(project, member_id))
    if not members:
        raise FileNotFoundError("No members found. Run generate first.")
    return members


def score_ensemble(
    project_dir: str | Path | None = None,
    with_abm: bool = False,
    abm_top: int = 10,
    seed: int = 1,
) -> pd.DataFrame:
    """Compute static scores and optional ABM-adjusted scores.

    Parameters
    ----------
    project_dir : str or Path or None, default=None
        Existing run directory.
    with_abm : bool, default=False
        Whether to run ABM post-evaluation.
    abm_top : int, default=10
        Number of top static members to evaluate with ABM.
    seed : int, default=1
        Deterministic seed for ABM simulation.

    Returns
    -------
    pandas.DataFrame
        Member score table including static and ABM-adjusted outputs.
    """

    project = resolve_project_dir(project_dir, create_if_missing=False)
    scoring_dir = ensure_dir(project / "scoring")
    abm_dir = ensure_dir(project / "abm")

    members = _iter_members(project)
    scoring_cfg = ScoringConfig()

    rows: list[dict[str, Any]] = []
    signatures: dict[int, set[str]] = {}
    for member in members:
        cells = read_dataframe(member.cells_path)
        metrics = compute_static_scores(cells, scoring_cfg=scoring_cfg)
        metrics["member_id"] = member.member_id
        rows.append(metrics)
        signatures[member.member_id] = member_signature(cells)

    scores = pd.DataFrame(rows).sort_values("member_id").reset_index(drop=True)
    scores["abm_non_auto_mode_share"] = np.nan
    scores["abm_median_daily_needs_minutes"] = np.nan
    scores["abm_public_space_visit_rate"] = np.nan
    scores["abm_access_equity_gap"] = np.nan
    scores["abm_penalty"] = 0.0

    baseline = _baseline_context(project)
    if with_abm:
        abm_cfg = ABMConfig()
        to_eval = scores.sort_values("static_final", ascending=False).head(max(1, abm_top))

        abm_rows: list[pd.DataFrame] = []
        for member_id in to_eval["member_id"].astype(int):
            member = _member_paths(project, member_id)
            result = run_mesa_evaluation(plan=member, baseline=baseline, cfg=abm_cfg, seed=seed)
            frame = abm_result_to_frame(result)
            abm_rows.append(frame)
            write_dataframe(frame, abm_dir / f"member_{member_id:03d}_abm_metrics.parquet")

        if abm_rows:
            abm_summary = pd.concat(abm_rows, ignore_index=True)
            write_dataframe(abm_summary, abm_dir / "abm_summary.parquet")
            scores = scores.merge(abm_summary, on="member_id", how="left", suffixes=("", "_abm"))
            scores["abm_non_auto_mode_share"] = scores["abm_non_auto_mode_share_abm"].combine_first(
                scores["abm_non_auto_mode_share"]
            )
            scores["abm_median_daily_needs_minutes"] = scores[
                "abm_median_daily_needs_minutes_abm"
            ].combine_first(scores["abm_median_daily_needs_minutes"])
            scores["abm_public_space_visit_rate"] = scores["abm_public_space_visit_rate_abm"].combine_first(
                scores["abm_public_space_visit_rate"]
            )
            scores["abm_access_equity_gap"] = scores["abm_access_equity_gap_abm"].combine_first(
                scores["abm_access_equity_gap"]
            )
            scores["abm_penalty"] = scores["abm_penalty_abm"].fillna(scores["abm_penalty"])

            drop_cols = [c for c in scores.columns if c.endswith("_abm")]
            scores.drop(columns=drop_cols, inplace=True)

    scores["final_with_abm"] = scores["static_final"] - scores["abm_penalty"].fillna(0.0)

    objective_cols = ["compactness_score", "green_access_score", "non_auto_access_score"]
    frontier = pareto_frontier(scores, objective_cols)

    medians = scores[objective_cols].median()
    eligible = scores[
        (scores["compactness_score"] >= medians["compactness_score"])
        & (scores["green_access_score"] >= medians["green_access_score"])
        & (scores["non_auto_access_score"] >= medians["non_auto_access_score"])
    ]
    balanced = (
        eligible.sort_values("final_with_abm", ascending=False).head(1)
        if not eligible.empty
        else scores.sort_values("final_with_abm", ascending=False).head(1)
    )

    top5 = select_diverse_top(
        scores=scores,
        signatures=signatures,
        top_n=5,
        score_col="final_with_abm",
        max_jaccard=0.8,
    )

    write_dataframe(scores, scoring_dir / "member_scores.parquet")
    write_dataframe(frontier, scoring_dir / "pareto_frontier.parquet")
    write_json(balanced.iloc[0].to_dict(), scoring_dir / "balanced_exemplar.json")
    write_json(top5.to_dict(orient="records"), scoring_dir / "top5.json")

    return scores


def export_top_plans(
    top_n: int = 5,
    project_dir: str | Path | None = None,
    graph2city_out: bool = False,
) -> list[dict[str, Any]]:
    """Export selected plans to map products and optional Graph2City packages.

    Parameters
    ----------
    top_n : int, default=5
        Number of ranked plans to export.
    project_dir : str or Path or None, default=None
        Existing run directory.
    graph2city_out : bool, default=False
        Whether to export Graph2City packages for selected members.

    Returns
    -------
    list of dict of str to Any
        Export records for each ranked plan.
    """

    project = resolve_project_dir(project_dir, create_if_missing=False)
    scores_path = project / "scoring" / "member_scores.parquet"
    scores = read_dataframe(scores_path)

    top_candidates_path = project / "scoring" / "top5.json"
    if top_candidates_path.exists() and top_n == 5:
        top_candidates = pd.DataFrame(read_json(top_candidates_path))
    else:
        top_candidates = scores.sort_values("final_with_abm", ascending=False).head(top_n)

    exports_dir = ensure_dir(project / "exports")
    g2c_exports_root = ensure_dir(exports_dir / "graph2city") if graph2city_out else None

    exported: list[dict[str, Any]] = []
    summary_lines = ["# CivicMorph Ensemble Summary", "", f"Top plans exported: {len(top_candidates)}", ""]

    for rank, (_, row) in enumerate(top_candidates.head(top_n).iterrows(), start=1):
        member_id = int(row["member_id"])
        member = _member_paths(project, member_id)

        lines_path = member.member_dir / "transit_lines.parquet"
        stops_path = member.member_dir / "transit_stops.parquet"

        png_path = exports_dir / f"top_{rank}_composite.png"
        html_path = exports_dir / f"top_{rank}_interactive.html"
        layers_path = exports_dir / f"top_{rank}_layers.gpkg"

        render_composite_png(
            cells_path=member.cells_path,
            blocks_path=member.blocks_path,
            transit_lines_path=lines_path,
            transit_stops_path=stops_path,
            green_path=member.green_path,
            streets_path=member.streets_path,
            out_png=png_path,
        )
        render_interactive_html(
            cells_path=member.cells_path,
            lines_path=lines_path,
            stops_path=stops_path,
            green_path=member.green_path,
            out_html=html_path,
        )

        cells = read_dataframe(member.cells_path)
        blocks = read_dataframe(member.blocks_path)
        transit = read_dataframe(member.transit_path)
        streets = read_dataframe(member.streets_path)
        green = read_dataframe(member.green_path)

        combined = pd.concat(
            [
                cells.assign(layer="cells"),
                blocks.assign(layer="blocks"),
                transit.assign(layer="transit"),
                streets.assign(layer="streets"),
                green.assign(layer="green"),
            ],
            ignore_index=True,
            sort=False,
        )
        write_dataframe(combined, layers_path)

        export_record: dict[str, Any] = {
            "rank": rank,
            "member_id": member_id,
            "final_with_abm": float(row["final_with_abm"]),
            "png": str(png_path),
            "html": str(html_path),
            "layers": str(layers_path),
        }

        if graph2city_out and g2c_exports_root is not None:
            g2c_member_dir = ensure_dir(g2c_exports_root / f"member_{member_id:03d}")
            result = export_plan_to_graph2city(member, str(g2c_member_dir))
            export_record["graph2city_manifest"] = str(result.manifest_path)

        exported.append(export_record)
        summary_lines.append(
            f"- Rank {rank}: member {member_id}, final_with_abm={float(row['final_with_abm']):.4f}"
        )

    summary_path = exports_dir / "ensemble_summary.md"
    summary_path.write_text("\n".join(summary_lines) + "\n")

    return exported

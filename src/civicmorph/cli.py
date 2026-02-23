"""Command-line interface for CivicMorph."""

from __future__ import annotations

import argparse
import json
from typing import Any

from .pipeline import build_baseline, export_top_plans, generate_ensemble, score_ensemble

try:
    import typer
except ImportError:  # pragma: no cover - fallback path
    typer = None


def _print_json(payload: Any) -> None:
    """Print JSON to stdout with pretty formatting.

    Parameters
    ----------
    payload : Any
        JSON-serializable payload.
    """

    print(json.dumps(payload, indent=2, default=str))


def _build_baseline_cmd(
    osm_pbf: str | None,
    place: str | None,
    study_area: str | None,
    dem: str | None,
    flood: str | None,
    constraint_masks: list[str] | None,
    transit_headway_bus: float,
    transit_headway_tram: float,
    transit_headway_rail: float,
    project_dir: str | None,
    graph2city_in: str | None,
) -> None:
    """Execute baseline subcommand implementation.

    Parameters
    ----------
    osm_pbf : str or None
        OSM PBF path.
    place : str or None
        Optional place name selector.
    study_area : str or None
        Optional study-area polygon path.
    dem : str or None
        Optional DEM path.
    flood : str or None
        Optional flood-layer path.
    constraint_masks : list of str or None
        Optional user-supplied mask paths.
    transit_headway_bus : float
        Bus headway assumption (minutes).
    transit_headway_tram : float
        Tram headway assumption (minutes).
    transit_headway_rail : float
        Rail headway assumption (minutes).
    project_dir : str or None
        Optional run directory.
    graph2city_in : str or None
        Optional Graph2City seed package directory.
    """

    ctx = build_baseline(
        osm_pbf=osm_pbf,
        place_name=place,
        study_area=study_area,
        dem=dem,
        flood=flood,
        constraint_masks=constraint_masks or [],
        transit_headway_bus=transit_headway_bus,
        transit_headway_tram=transit_headway_tram,
        transit_headway_rail=transit_headway_rail,
        project_dir=project_dir,
        graph2city_in=graph2city_in,
    )
    _print_json({"project_dir": str(ctx.project_dir), "baseline": ctx.metadata})


def _generate_cmd(
    profile: str,
    ensemble: int,
    seed: int,
    project_dir: str | None,
    seed_source: str,
    graph2city_in: str | None,
) -> None:
    """Execute ensemble generation subcommand implementation.

    Parameters
    ----------
    profile : str
        Profile name.
    ensemble : int
        Ensemble size.
    seed : int
        Deterministic seed.
    project_dir : str or None
        Existing run directory.
    seed_source : str
        Seed strategy name.
    graph2city_in : str or None
        Optional Graph2City seed package path.
    """

    members = generate_ensemble(
        profile_name=profile,
        ensemble_size=ensemble,
        seed=seed,
        project_dir=project_dir,
        seed_source=seed_source,
        graph2city_in=graph2city_in,
    )
    _print_json({"members_generated": int(members.shape[0])})


def _score_cmd(
    project_dir: str | None,
    with_abm: bool,
    abm_top: int,
    seed: int,
    abm_mode: str,
    ca_tessellation: str,
    policy_upzone: float,
    policy_transit_investment: float,
    policy_affordable_housing: float,
    policy_parking_reduction: float,
    policy_green_protection: float,
    network_new_links: int,
    network_bus_lane_km: float,
    network_station_infill: int,
    regional_growth_boundary: float,
    regional_conservation_share: float,
) -> None:
    """Execute scoring subcommand implementation.

    Parameters
    ----------
    project_dir : str or None
        Existing run directory.
    with_abm : bool
        Whether to run ABM post-evaluation.
    abm_top : int
        Number of top static members to evaluate with ABM.
    seed : int
        Deterministic seed.
    abm_mode : str
        Mesa simulation option.
    ca_tessellation : str
        Cellular automata tessellation type.
    policy_upzone : float
        Upzoning policy lever.
    policy_transit_investment : float
        Transit investment policy lever.
    policy_affordable_housing : float
        Affordability policy lever.
    policy_parking_reduction : float
        Parking reduction policy lever.
    policy_green_protection : float
        Green-space protection policy lever.
    network_new_links : int
        Network-link intervention count.
    network_bus_lane_km : float
        Added bus-lane kilometers.
    network_station_infill : int
        Station infill intervention count.
    regional_growth_boundary : float
        Regional growth-boundary scalar.
    regional_conservation_share : float
        Regional conservation share.
    """

    scores = score_ensemble(
        project_dir=project_dir,
        with_abm=with_abm,
        abm_top=abm_top,
        seed=seed,
        abm_mode=abm_mode,
        ca_tessellation=ca_tessellation,
        policy_upzone=policy_upzone,
        policy_transit_investment=policy_transit_investment,
        policy_affordable_housing=policy_affordable_housing,
        policy_parking_reduction=policy_parking_reduction,
        policy_green_protection=policy_green_protection,
        network_new_links=network_new_links,
        network_bus_lane_km=network_bus_lane_km,
        network_station_infill=network_station_infill,
        regional_growth_boundary=regional_growth_boundary,
        regional_conservation_share=regional_conservation_share,
    )
    _print_json(
        {
            "members_scored": int(scores.shape[0]),
            "best_member": int(scores.sort_values("final_with_abm", ascending=False).iloc[0]["member_id"]),
        }
    )


def _export_cmd(project_dir: str | None, top: int, graph2city_out: bool) -> None:
    """Execute export subcommand implementation.

    Parameters
    ----------
    project_dir : str or None
        Existing run directory.
    top : int
        Number of plans to export.
    graph2city_out : bool
        Whether to emit Graph2City packages.
    """

    artifacts = export_top_plans(top_n=top, project_dir=project_dir, graph2city_out=graph2city_out)
    _print_json({"exported": artifacts})


if typer:
    app = typer.Typer(help="CivicMorph speculative urban plan generator")

    @app.command("build-baseline")
    def build_baseline_cli(
        osm_pbf: str | None = typer.Option(None, "--osm-pbf", help="Path to input OSM PBF file"),
        place: str | None = typer.Option(
            None,
            "--place",
            help="Place name selector (e.g., 'Boulder, Colorado') when OSM PBF is not provided",
        ),
        study_area: str | None = typer.Option(
            None,
            "--study-area",
            help="Polygon selector path (GeoJSON/GPKG) when OSM PBF is not provided",
        ),
        dem: str | None = typer.Option(None, "--dem", help="Optional DEM raster path"),
        flood: str | None = typer.Option(None, "--flood", help="Optional flood layer path"),
        constraint_masks: list[str] = typer.Option(
            [],
            "--constraint-mask",
            help="Optional user-supplied constraint masks (repeatable)",
        ),
        transit_headway_bus: float = typer.Option(
            12.0, "--transit-headway-bus", help="Bus headway assumption (minutes)"
        ),
        transit_headway_tram: float = typer.Option(
            10.0, "--transit-headway-tram", help="Tram headway assumption (minutes)"
        ),
        transit_headway_rail: float = typer.Option(
            8.0, "--transit-headway-rail", help="Rail headway assumption (minutes)"
        ),
        project_dir: str | None = typer.Option(
            None,
            "--project-dir",
            help="Run directory. Default creates runs/<run_id>",
        ),
        graph2city_in: str | None = typer.Option(
            None,
            "--graph2city-in",
            help="Optional Graph2City seed directory",
        ),
    ) -> None:
        """Run baseline artifact build from CLI options."""

        _build_baseline_cmd(
            osm_pbf=osm_pbf,
            place=place,
            study_area=study_area,
            dem=dem,
            flood=flood,
            constraint_masks=constraint_masks,
            transit_headway_bus=transit_headway_bus,
            transit_headway_tram=transit_headway_tram,
            transit_headway_rail=transit_headway_rail,
            project_dir=project_dir,
            graph2city_in=graph2city_in,
        )

    @app.command("generate")
    def generate_cli(
        profile: str = typer.Option(..., "--profile", help="Profile name"),
        ensemble: int = typer.Option(50, "--ensemble", help="Ensemble size"),
        seed: int = typer.Option(1, "--seed", help="Deterministic run seed"),
        project_dir: str | None = typer.Option(None, "--project-dir", help="Existing run directory"),
        seed_source: str = typer.Option(
            "osm",
            "--seed-source",
            help="Seed source: osm|graph2city|hybrid",
        ),
        graph2city_in: str | None = typer.Option(
            None,
            "--graph2city-in",
            help="Graph2City input directory (required for graph2city/hybrid)",
        ),
    ) -> None:
        """Run ensemble generation from CLI options."""

        _generate_cmd(
            profile=profile,
            ensemble=ensemble,
            seed=seed,
            project_dir=project_dir,
            seed_source=seed_source,
            graph2city_in=graph2city_in,
        )

    @app.command("score")
    def score_cli(
        project_dir: str | None = typer.Option(None, "--project-dir", help="Existing run directory"),
        with_abm: bool = typer.Option(False, "--with-abm", help="Enable Mesa ABM post-evaluation"),
        abm_top: int = typer.Option(10, "--abm-top", help="Evaluate top N static members in ABM"),
        seed: int = typer.Option(1, "--seed", help="ABM deterministic seed"),
        abm_mode: str = typer.Option(
            "abm",
            "--abm-mode",
            help="Mesa simulation mode: abm|dla|ca|network|multi_scale",
        ),
        ca_tessellation: str = typer.Option("grid", "--ca-tessellation", help="CA tessellation: grid|hex"),
        policy_upzone: float = typer.Option(1.0, "--policy-upzone", help="Upzoning policy lever"),
        policy_transit_investment: float = typer.Option(
            1.0, "--policy-transit-investment", help="Transit investment policy lever"
        ),
        policy_affordable_housing: float = typer.Option(
            1.0, "--policy-affordable-housing", help="Affordability policy lever"
        ),
        policy_parking_reduction: float = typer.Option(
            1.0, "--policy-parking-reduction", help="Parking reduction policy lever"
        ),
        policy_green_protection: float = typer.Option(
            1.0, "--policy-green-protection", help="Green protection policy lever"
        ),
        network_new_links: int = typer.Option(
            3, "--network-new-links", help="Network growth: number of new links"
        ),
        network_bus_lane_km: float = typer.Option(
            12.0, "--network-bus-lane-km", help="Network growth: added bus lane kilometers"
        ),
        network_station_infill: int = typer.Option(
            2, "--network-station-infill", help="Network growth: station infill count"
        ),
        regional_growth_boundary: float = typer.Option(
            1.0, "--regional-growth-boundary", help="Multi-scale regional growth-boundary scalar"
        ),
        regional_conservation_share: float = typer.Option(
            0.2, "--regional-conservation-share", help="Multi-scale conservation share"
        ),
    ) -> None:
        """Run score computation from CLI options."""

        _score_cmd(
            project_dir=project_dir,
            with_abm=with_abm,
            abm_top=abm_top,
            seed=seed,
            abm_mode=abm_mode,
            ca_tessellation=ca_tessellation,
            policy_upzone=policy_upzone,
            policy_transit_investment=policy_transit_investment,
            policy_affordable_housing=policy_affordable_housing,
            policy_parking_reduction=policy_parking_reduction,
            policy_green_protection=policy_green_protection,
            network_new_links=network_new_links,
            network_bus_lane_km=network_bus_lane_km,
            network_station_infill=network_station_infill,
            regional_growth_boundary=regional_growth_boundary,
            regional_conservation_share=regional_conservation_share,
        )

    @app.command("export")
    def export_cli(
        top: int = typer.Option(5, "--top", help="Number of top plans to export"),
        project_dir: str | None = typer.Option(None, "--project-dir", help="Existing run directory"),
        graph2city_out: bool = typer.Option(
            False,
            "--graph2city-out",
            help="Also export selected plans in Graph2City format",
        ),
    ) -> None:
        """Run export workflow from CLI options."""

        _export_cmd(project_dir=project_dir, top=top, graph2city_out=graph2city_out)


else:  # pragma: no cover

    app = None

    def _argparse_parser() -> argparse.ArgumentParser:
        """Create argparse parser for no-Typer fallback mode."""

        parser = argparse.ArgumentParser(prog="civicmorph")
        subparsers = parser.add_subparsers(dest="command", required=True)

        b = subparsers.add_parser("build-baseline")
        b.add_argument("--osm-pbf")
        b.add_argument("--place")
        b.add_argument("--study-area")
        b.add_argument("--dem")
        b.add_argument("--flood")
        b.add_argument("--constraint-mask", action="append", default=[])
        b.add_argument("--transit-headway-bus", type=float, default=12.0)
        b.add_argument("--transit-headway-tram", type=float, default=10.0)
        b.add_argument("--transit-headway-rail", type=float, default=8.0)
        b.add_argument("--project-dir")
        b.add_argument("--graph2city-in")

        g = subparsers.add_parser("generate")
        g.add_argument("--profile", required=True)
        g.add_argument("--ensemble", type=int, default=50)
        g.add_argument("--seed", type=int, default=1)
        g.add_argument("--project-dir")
        g.add_argument("--seed-source", default="osm")
        g.add_argument("--graph2city-in")

        s = subparsers.add_parser("score")
        s.add_argument("--project-dir")
        s.add_argument("--with-abm", action="store_true")
        s.add_argument("--abm-top", type=int, default=10)
        s.add_argument("--seed", type=int, default=1)
        s.add_argument("--abm-mode", default="abm")
        s.add_argument("--ca-tessellation", default="grid")
        s.add_argument("--policy-upzone", type=float, default=1.0)
        s.add_argument("--policy-transit-investment", type=float, default=1.0)
        s.add_argument("--policy-affordable-housing", type=float, default=1.0)
        s.add_argument("--policy-parking-reduction", type=float, default=1.0)
        s.add_argument("--policy-green-protection", type=float, default=1.0)
        s.add_argument("--network-new-links", type=int, default=3)
        s.add_argument("--network-bus-lane-km", type=float, default=12.0)
        s.add_argument("--network-station-infill", type=int, default=2)
        s.add_argument("--regional-growth-boundary", type=float, default=1.0)
        s.add_argument("--regional-conservation-share", type=float, default=0.2)

        e = subparsers.add_parser("export")
        e.add_argument("--top", type=int, default=5)
        e.add_argument("--project-dir")
        e.add_argument("--graph2city-out", action="store_true")

        return parser


def run() -> None:
    """Run the CivicMorph command-line application.

    This function dispatches to the Typer app when available and falls back to
    argparse otherwise.

    Parameters
    ----------
    None

    Returns
    -------
    None
    """

    if typer and app is not None:
        app()
        return

    parser = _argparse_parser()
    args = parser.parse_args()
    cmd = args.command

    if cmd == "build-baseline":
        _build_baseline_cmd(
            args.osm_pbf,
            args.place,
            args.study_area,
            args.dem,
            args.flood,
            args.constraint_mask,
            args.transit_headway_bus,
            args.transit_headway_tram,
            args.transit_headway_rail,
            args.project_dir,
            args.graph2city_in,
        )
    elif cmd == "generate":
        _generate_cmd(
            args.profile,
            args.ensemble,
            args.seed,
            args.project_dir,
            args.seed_source,
            args.graph2city_in,
        )
    elif cmd == "score":
        _score_cmd(
            args.project_dir,
            args.with_abm,
            args.abm_top,
            args.seed,
            args.abm_mode,
            args.ca_tessellation,
            args.policy_upzone,
            args.policy_transit_investment,
            args.policy_affordable_housing,
            args.policy_parking_reduction,
            args.policy_green_protection,
            args.network_new_links,
            args.network_bus_lane_km,
            args.network_station_infill,
            args.regional_growth_boundary,
            args.regional_conservation_share,
        )
    elif cmd == "export":
        _export_cmd(args.project_dir, args.top, args.graph2city_out)
    else:  # pragma: no cover
        raise RuntimeError(f"Unknown command: {cmd}")


if __name__ == "__main__":  # pragma: no cover
    run()

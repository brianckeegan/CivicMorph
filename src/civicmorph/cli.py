"""Command-line interface for CivicMorph."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
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
    osm_pbf: str,
    dem: str | None,
    flood: str | None,
    project_dir: str | None,
    graph2city_in: str | None,
) -> None:
    """Execute baseline subcommand implementation.

    Parameters
    ----------
    osm_pbf : str
        OSM PBF path.
    dem : str or None
        Optional DEM path.
    flood : str or None
        Optional flood-layer path.
    project_dir : str or None
        Optional run directory.
    graph2city_in : str or None
        Optional Graph2City seed package directory.
    """

    ctx = build_baseline(
        osm_pbf=osm_pbf,
        dem=dem,
        flood=flood,
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


def _score_cmd(project_dir: str | None, with_abm: bool, abm_top: int, seed: int) -> None:
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
    """

    scores = score_ensemble(project_dir=project_dir, with_abm=with_abm, abm_top=abm_top, seed=seed)
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
        osm_pbf: str = typer.Option(..., "--osm-pbf", help="Path to input OSM PBF file"),
        dem: str | None = typer.Option(None, "--dem", help="Optional DEM raster path"),
        flood: str | None = typer.Option(None, "--flood", help="Optional flood layer path"),
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
            dem=dem,
            flood=flood,
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
    ) -> None:
        """Run score computation from CLI options."""

        _score_cmd(project_dir=project_dir, with_abm=with_abm, abm_top=abm_top, seed=seed)

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
        b.add_argument("--osm-pbf", required=True)
        b.add_argument("--dem")
        b.add_argument("--flood")
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
        _build_baseline_cmd(args.osm_pbf, args.dem, args.flood, args.project_dir, args.graph2city_in)
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
        _score_cmd(args.project_dir, args.with_abm, args.abm_top, args.seed)
    elif cmd == "export":
        _export_cmd(args.project_dir, args.top, args.graph2city_out)
    else:  # pragma: no cover
        raise RuntimeError(f"Unknown command: {cmd}")


if __name__ == "__main__":  # pragma: no cover
    run()

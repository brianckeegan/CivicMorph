from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from civicmorph.pipeline import build_baseline, export_top_plans, generate_ensemble, score_ensemble
from civicmorph.io import read_dataframe


def test_core_pipeline_without_extras(tmp_path: Path, dummy_inputs: dict[str, Path]) -> None:
    run_dir = tmp_path / "run_core"
    build_baseline(
        osm_pbf=str(dummy_inputs["osm"]),
        dem=str(dummy_inputs["dem"]),
        flood=str(dummy_inputs["flood"]),
        project_dir=run_dir,
    )
    generate_ensemble(
        profile_name="optimistic_courtyard_city",
        ensemble_size=6,
        seed=1,
        project_dir=run_dir,
    )
    scores = score_ensemble(project_dir=run_dir)
    exports = export_top_plans(project_dir=run_dir, top_n=3)

    assert len(scores) == 6
    assert len(exports) == 3
    assert (run_dir / "exports" / "top_1_composite.png").exists()
    assert (run_dir / "exports" / "top_1_interactive.html").exists()


def test_graph2city_seed_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, dummy_inputs: dict[str, Path]) -> None:
    monkeypatch.setattr("civicmorph.integrations.graph2city_adapter.validate_graph2city_version", lambda: "1.2.3")

    run_dir = tmp_path / "run_g2c"
    build_baseline(
        osm_pbf=str(dummy_inputs["osm"]),
        project_dir=run_dir,
        graph2city_in=str(dummy_inputs["g2c"]),
    )
    members = generate_ensemble(
        profile_name="transit_corridor_city",
        ensemble_size=4,
        seed=2,
        project_dir=run_dir,
        seed_source="graph2city",
        graph2city_in=str(dummy_inputs["g2c"]),
    )

    assert len(members) == 4
    one = read_dataframe(run_dir / "ensemble" / "member_000" / "cells_proposed.parquet")
    assert "proposed_intensity_far" in one.columns
    assert float(one["proposed_height_cap_ft"].max()) <= 60.0


def test_score_with_abm_writes_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, dummy_inputs: dict[str, Path]
) -> None:
    monkeypatch.setattr("civicmorph.abm.mesa_runner.validate_mesa_version", lambda: "2.1.1")

    run_dir = tmp_path / "run_abm"
    build_baseline(osm_pbf=str(dummy_inputs["osm"]), project_dir=run_dir)
    generate_ensemble(
        profile_name="bike_supergrid_city",
        ensemble_size=8,
        seed=5,
        project_dir=run_dir,
    )

    scores = score_ensemble(project_dir=run_dir, with_abm=True, abm_top=3, seed=5)
    assert "abm_penalty" in scores.columns
    assert (run_dir / "abm" / "abm_summary.parquet").exists() or (
        run_dir / "abm" / "abm_summary.parquet.csv"
    ).exists()


def test_export_graph2city_out(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, dummy_inputs: dict[str, Path]
) -> None:
    monkeypatch.setattr("civicmorph.integrations.graph2city_adapter.validate_graph2city_version", lambda: "1.2.3")

    run_dir = tmp_path / "run_export_g2c"
    build_baseline(osm_pbf=str(dummy_inputs["osm"]), project_dir=run_dir)
    generate_ensemble(
        profile_name="green_weave_first",
        ensemble_size=5,
        seed=7,
        project_dir=run_dir,
    )
    score_ensemble(project_dir=run_dir)

    exported = export_top_plans(project_dir=run_dir, top_n=2, graph2city_out=True)
    assert len(exported) == 2
    assert (run_dir / "exports" / "graph2city").exists()


def test_hybrid_seed_respects_human_scale_caps(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, dummy_inputs: dict[str, Path]
) -> None:
    monkeypatch.setattr("civicmorph.integrations.graph2city_adapter.validate_graph2city_version", lambda: "1.2.3")

    run_dir = tmp_path / "run_hybrid"
    build_baseline(
        osm_pbf=str(dummy_inputs["osm"]),
        project_dir=run_dir,
    )
    generate_ensemble(
        profile_name="optimistic_courtyard_city",
        ensemble_size=3,
        seed=11,
        project_dir=run_dir,
        seed_source="hybrid",
        graph2city_in=str(dummy_inputs["g2c"]),
    )

    sample = read_dataframe(run_dir / "ensemble" / "member_001" / "cells_proposed.parquet")
    assert float(sample["proposed_height_cap_ft"].max()) <= 60.0
    required = {
        "proposed_intensity_far",
        "street_priority_class",
        "car_deemphasis_score",
        "green_access_score",
        "flood_risk_score",
        "slope_constraint_score",
        "view_shed_value_score",
    }
    assert required.issubset(sample.columns)

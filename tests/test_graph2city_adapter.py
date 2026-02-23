from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from civicmorph import pipeline
from civicmorph.exceptions import OptionalDependencyError
from civicmorph.integrations.graph2city_adapter import (
    export_plan_to_graph2city,
    import_graph2city,
)
from civicmorph.io import write_dataframe
from civicmorph.types import PlanMember


def test_import_graph2city_topology_and_crs(monkeypatch: pytest.MonkeyPatch, dummy_inputs: dict[str, Path]) -> None:
    monkeypatch.setattr(
        "civicmorph.integrations.graph2city_adapter.validate_graph2city_version",
        lambda: "1.2.3",
    )

    seed = import_graph2city(str(dummy_inputs["g2c"]), crs="EPSG:32613")
    assert seed.crs == "EPSG:32613"
    assert seed.graph2city_version == "1.2.3"
    assert len(seed.nodes) == 3
    assert len(seed.edges) == 2


def test_export_graph2city_layers_and_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "civicmorph.integrations.graph2city_adapter.validate_graph2city_version",
        lambda: "1.2.3",
    )

    member_dir = tmp_path / "member_000"
    member_dir.mkdir(parents=True)

    cells_path = member_dir / "cells_proposed.parquet"
    blocks_path = member_dir / "blocks.gpkg"
    transit_path = member_dir / "transit.gpkg"
    streets_path = member_dir / "streets_priority.gpkg"
    green_path = member_dir / "green_network.gpkg"

    write_dataframe(pd.DataFrame({"cell_id": ["c1"], "proposed_intensity_far": [2.0]}), cells_path)
    write_dataframe(pd.DataFrame({"block_id": ["b1"]}), blocks_path)
    write_dataframe(pd.DataFrame({"line_id": ["l1"]}), transit_path)
    write_dataframe(pd.DataFrame({"segment_id": [1]}), streets_path)
    write_dataframe(pd.DataFrame({"cell_id": ["c1"]}), green_path)

    member = PlanMember(
        member_id=0,
        project_dir=tmp_path,
        member_dir=member_dir,
        cells_path=cells_path,
        blocks_path=blocks_path,
        transit_path=transit_path,
        streets_path=streets_path,
        green_path=green_path,
    )

    out_dir = tmp_path / "g2c_export"
    result = export_plan_to_graph2city(member, str(out_dir))
    assert result.manifest_path.exists()
    for path in result.layer_paths.values():
        assert path.exists() or path.with_name(path.name + ".csv").exists()


def test_optional_dependency_guard_only_for_framework_paths(
    tmp_path: Path, dummy_inputs: dict[str, Path]
) -> None:
    # Core baseline generation should work without graph2city/mesa extras.
    ctx = pipeline.build_baseline(
        osm_pbf=str(dummy_inputs["osm"]),
        dem=str(dummy_inputs["dem"]),
        flood=str(dummy_inputs["flood"]),
        project_dir=tmp_path / "run_core",
    )
    assert ctx.cells_path.exists() or ctx.cells_path.with_name(ctx.cells_path.name + ".csv").exists()

    # Graph2City path should fail fast when dependency is missing.
    with pytest.raises(OptionalDependencyError):
        import_graph2city(str(dummy_inputs["g2c"]), crs="EPSG:3857")

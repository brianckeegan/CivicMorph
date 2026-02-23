from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from civicmorph.abm.mesa_runner import run_mesa_evaluation
from civicmorph.io import write_dataframe
from civicmorph.types import ABMConfig, BaselineContext, PlanMember


def _build_plan(tmp_path: Path, member_id: int, factor: float) -> tuple[PlanMember, BaselineContext]:
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    cells_baseline = baseline_dir / "cells_baseline.parquet"

    baseline_df = pd.DataFrame(
        {
            "cell_id": [f"c_{i:03d}" for i in range(50)],
            "baseline_non_auto_score": [0.45] * 50,
            "baseline_daily_needs_min": [20.0] * 50,
            "baseline_green_access_score": [0.5] * 50,
        }
    )
    write_dataframe(baseline_df, cells_baseline)

    member_dir = tmp_path / f"member_{member_id:03d}"
    member_dir.mkdir(parents=True, exist_ok=True)
    cells_path = member_dir / "cells_proposed.parquet"
    df = pd.DataFrame(
        {
            "cell_id": [f"c_{i:03d}" for i in range(50)],
            "x": list(range(50)),
            "inhabited": [1] * 50,
            "car_deemphasis_score": [min(1.0, 0.3 + factor)] * 50,
            "proposed_intensity_far": [min(5.0, 1.0 + factor * 2)] * 50,
            "baseline_daily_needs_min": [max(6.0, 22.0 - factor * 5)] * 50,
            "green_access_score": [min(1.0, 0.35 + factor)] * 50,
        }
    )
    write_dataframe(df, cells_path)

    member = PlanMember(
        member_id=member_id,
        project_dir=tmp_path,
        member_dir=member_dir,
        cells_path=cells_path,
        blocks_path=member_dir / "blocks.gpkg",
        transit_path=member_dir / "transit.gpkg",
        streets_path=member_dir / "streets_priority.gpkg",
        green_path=member_dir / "green_network.gpkg",
    )
    baseline = BaselineContext(
        project_dir=tmp_path,
        baseline_dir=baseline_dir,
        crs="EPSG:3857",
        cells_path=cells_baseline,
    )
    return member, baseline


def test_mesa_runner_determinism(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("civicmorph.abm.mesa_runner.validate_mesa_version", lambda: "2.1.1")
    member, baseline = _build_plan(tmp_path, member_id=1, factor=0.4)

    cfg = ABMConfig(max_agents=200, ticks=20)
    r1 = run_mesa_evaluation(member, baseline, cfg, seed=9)
    r2 = run_mesa_evaluation(member, baseline, cfg, seed=9)

    assert r1.abm_penalty == pytest.approx(r2.abm_penalty)
    assert r1.abm_non_auto_mode_share == pytest.approx(r2.abm_non_auto_mode_share)


def test_abm_penalty_monotonic_for_worse_access(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("civicmorph.abm.mesa_runner.validate_mesa_version", lambda: "2.1.1")
    good_member, baseline = _build_plan(tmp_path / "good", member_id=1, factor=0.6)
    bad_member, _ = _build_plan(tmp_path / "bad", member_id=2, factor=0.1)

    cfg = ABMConfig(max_agents=250, ticks=25)
    good = run_mesa_evaluation(good_member, baseline, cfg, seed=3)
    bad = run_mesa_evaluation(bad_member, baseline, cfg, seed=3)

    assert bad.abm_penalty >= good.abm_penalty

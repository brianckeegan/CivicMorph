from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture()
def dummy_inputs(tmp_path: Path) -> dict[str, Path]:
    osm = tmp_path / "input.osm.pbf"
    osm.write_text("placeholder")

    dem = tmp_path / "terrain.tif"
    dem.write_text("placeholder")

    flood = tmp_path / "flood.tif"
    flood.write_text("placeholder")

    g2c = tmp_path / "graph2city"
    g2c.mkdir()
    pd.DataFrame(
        {
            "node_id": [1, 2, 3],
            "x": [0, 1, 2],
            "y": [0, 1, 1],
        }
    ).to_csv(g2c / "nodes.csv", index=False)
    pd.DataFrame(
        {
            "edge_id": [1, 2],
            "u": [1, 2],
            "v": [2, 3],
        }
    ).to_csv(g2c / "edges.csv", index=False)
    pd.DataFrame(
        {
            "cell_id": ["c_000_000", "c_000_001", "c_001_001"],
            "block_id": ["b1", "b2", "b3"],
        }
    ).to_csv(g2c / "blocks.csv", index=False)
    pd.DataFrame(
        {
            "cell_id": ["c_000_000", "c_001_001"],
            "activity": ["clinic", "grocery"],
        }
    ).to_csv(g2c / "activities.csv", index=False)

    return {"osm": osm, "dem": dem, "flood": flood, "g2c": g2c}

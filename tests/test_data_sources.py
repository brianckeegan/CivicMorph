from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from civicmorph.data_sources import (
    retrieve_constraint_masks,
    retrieve_dem_data,
    retrieve_flood_data,
    retrieve_osm_data,
    retrieve_tabular_source,
)


def test_retrieve_tabular_source_local_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "table.csv"
    pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_csv(csv_path, index=False)

    table, meta = retrieve_tabular_source(csv_path)
    assert table.shape == (2, 2)
    assert meta["source_mode"] == "local_file"


def test_retrieve_constraint_masks(tmp_path: Path) -> None:
    mask1 = tmp_path / "mask1.geojson"
    mask2 = tmp_path / "mask2.geojson"
    mask1.write_text('{"type":"FeatureCollection","features":[]}')
    mask2.write_text('{"type":"FeatureCollection","features":[]}')

    table, meta = retrieve_constraint_masks([mask1, mask2])
    assert len(table) == 2
    assert meta["mask_count"] == 2


def test_retrieve_dem_data_fallback_and_flood_derivation() -> None:
    dem_table, dem_meta = retrieve_dem_data(None, seed_token="boulder", side=8)
    flood_table, flood_meta = retrieve_flood_data(None, dem_table=dem_table, seed_token="boulder", side=8)

    assert dem_meta["synthetic"] is True
    assert flood_meta["source_mode"] in {"derived_from_dem", "synthetic"}
    assert "flood_risk_score" in flood_table.columns


def test_retrieve_osm_data_place_mode() -> None:
    layers, meta = retrieve_osm_data(
        osm_pbf=None,
        place_name="Boulder, Colorado",
        study_area=None,
        headway_assumptions={"bus": 10.0, "tram": 9.0, "rail": 7.0},
        constraint_masks=None,
    )

    assert "streets" in layers
    assert "transit_routes" in layers
    assert meta["source_mode"] in {"place_name", "osm_pbf", "study_area"}
    assert meta["selector"]["place_name"] == "Boulder, Colorado"


def test_retrieve_osm_data_polygon_mode(tmp_path: Path) -> None:
    polygon_path = tmp_path / "polygon.geojson"
    polygon_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [-105.35, 39.95],
                                    [-105.17, 39.95],
                                    [-105.17, 40.08],
                                    [-105.35, 40.08],
                                    [-105.35, 39.95],
                                ]
                            ],
                        },
                    }
                ],
            }
        )
    )

    layers, meta = retrieve_osm_data(
        osm_pbf=None,
        place_name=None,
        study_area=polygon_path,
    )
    assert "landuse" in layers
    assert meta["source_mode"] in {"study_area", "osm_pbf", "place_name"}
    assert meta["selector"]["study_area"] is not None


def test_retrieve_tabular_source_http_rejected() -> None:
    with pytest.raises(ValueError):
        retrieve_tabular_source("https://example.com/data.csv", allow_http=False)

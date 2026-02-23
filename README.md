# CivicMorph

CivicMorph is a speculative, ensemble-based urban planning toolkit that transforms OSM + terrain inputs into optimistic, human-scale post-suburban plans focused on transit, biking, and walking.

## Features

- Cell-based plan overlays (FAR, height cap, street priority, green/risk scores)
- Synthetic block and transit generation per ensemble member
- One-shot regime-shift synthesis with deterministic sampling
- Penalty-based scoring with Pareto frontier and balanced exemplar
- Composite exports (PNG, interactive HTML, GIS-style layer files)
- Optional Graph2City import/export adapters
- Optional Mesa post-plan ABM scoring

## Installation

```bash
pip install -e .
```

Optional frameworks:

```bash
pip install -e .[graph2city]
pip install -e .[abm]
pip install -e .[frameworks]
```

## CLI

```bash
civicmorph build-baseline --osm-pbf data/boulder/boulder.osm.pbf --dem data/boulder/boulder_dem.tif --project-dir runs/boulder_demo
civicmorph generate --project-dir runs/boulder_demo --profile optimistic_courtyard_city --ensemble 50 --seed 1
civicmorph score --project-dir runs/boulder_demo --with-abm --abm-top 10
civicmorph export --project-dir runs/boulder_demo --top 5 --graph2city-out
```

Alternative OSM selectors (when local PBF is not passed):

```bash
civicmorph build-baseline --place "Boulder, Colorado" --project-dir runs/boulder_place
civicmorph build-baseline --study-area data/boulder/boulder_polygon.geojson --constraint-mask data/boulder/flood_mask.geojson
```

Mesa simulation options for scoring:

- `abm`: heterogeneous household/developer/employer + planner/operator feedback
- `dla`: DLA-inspired growth around seeded clusters
- `ca`: stochastic cellular automata (`--ca-tessellation grid|hex`)
- `network`: network intervention growth (`--network-*` levers)
- `multi_scale`: coupled cell/corridor/regional simulation (`--regional-*` levers)

```bash
civicmorph score \
  --project-dir runs/boulder_demo \
  --with-abm \
  --abm-mode multi_scale \
  --ca-tessellation hex \
  --policy-upzone 1.2 \
  --policy-transit-investment 1.3 \
  --network-new-links 6 \
  --network-bus-lane-km 24 \
  --network-station-infill 4 \
  --regional-growth-boundary 0.95 \
  --regional-conservation-share 0.3
```

ABM-enhanced scoring outputs include:

- `abm_mode`
- `abm_penalty`
- `abm_growth_focus_index`
- `abm_capacity_utilization`
- `abm_network_access_gain`

Python support functions for data retrieval:

- `retrieve_osm_data(...)` for OSM layers from PBF, place-name, or polygon selector.
- `retrieve_dem_data(...)` for DEM source/fallback retrieval.
- `retrieve_flood_data(...)` for flood layer retrieval or DEM-derived fallback.
- `retrieve_constraint_masks(...)` for user mask ingestion.
- `retrieve_tabular_source(...)` for local (and optional HTTP) tabular sources.

Example:

```python
from civicmorph import retrieve_osm_data, retrieve_dem_data, retrieve_flood_data

layers, osm_meta = retrieve_osm_data(
    osm_pbf=None,
    place_name="Boulder, Colorado",
    study_area=None,
)
dem_table, dem_meta = retrieve_dem_data(None, seed_token="boulder")
flood_table, flood_meta = retrieve_flood_data(None, dem_table=dem_table, seed_token="boulder")
```

### Graph2City seed modes

- `--seed-source osm` (default)
- `--seed-source graph2city --graph2city-in path/to/seed`
- `--seed-source hybrid --graph2city-in path/to/seed`

## Output layout

Artifacts are created under `runs/<run_id>/`:

- `baseline/` baseline cells, graph placeholders, terrain/public-green layers
- `ensemble/member_<id>/` generated cells, blocks, transit, streets, green network
- `scoring/` member scores, Pareto frontier, balanced exemplar, top5 list
- `abm/` per-member ABM metrics and summary (when `--with-abm` is used)
- `exports/` composite PNG/HTML/layer packages and optional Graph2City exports

## Development

```bash
pytest
```

## Documentation

- Sphinx docs root: `docs/source/index.rst`
- Boulder tutorial notebook: `output/jupyter-notebook/civicmorph-boulder-colorado-tutorial.ipynb`

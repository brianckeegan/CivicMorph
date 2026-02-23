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

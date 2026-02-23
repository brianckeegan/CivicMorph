Getting Started (Boulder, Colorado)
===================================

This quick start walks through the full CivicMorph flow for Boulder, Colorado.

Prerequisites
-------------

- Python 3.11+ environment
- Optional extras for integrations:
  - ``pip install -e .[graph2city]``
  - ``pip install -e .[abm]``
- Local Boulder data files:
  - ``data/boulder/boulder.osm.pbf``
  - ``data/boulder/boulder_dem.tif``
  - optional flood layer: ``data/boulder/boulder_flood.tif``

Install
-------

.. code-block:: bash

   pip install -e .

Run the Boulder Pipeline
------------------------

.. code-block:: bash

   civicmorph build-baseline \
     --osm-pbf data/boulder/boulder.osm.pbf \
     --dem data/boulder/boulder_dem.tif \
     --flood data/boulder/boulder_flood.tif \
     --project-dir runs/boulder_demo

   civicmorph generate \
     --project-dir runs/boulder_demo \
     --profile optimistic_courtyard_city \
     --ensemble 50 \
     --seed 1

   civicmorph score \
     --project-dir runs/boulder_demo \
     --with-abm \
     --abm-top 10

   civicmorph export \
     --project-dir runs/boulder_demo \
     --top 5

What to Inspect
---------------

- ``runs/boulder_demo/scoring/member_scores.parquet`` for score distributions.
- ``runs/boulder_demo/scoring/pareto_frontier.parquet`` for efficient tradeoffs.
- ``runs/boulder_demo/exports/top_1_interactive.html`` for the composite map.

Optional Graph2City Integration
-------------------------------

If you have a Boulder Graph2City seed package:

.. code-block:: bash

   civicmorph build-baseline \
     --osm-pbf data/boulder/boulder.osm.pbf \
     --project-dir runs/boulder_graph2city \
     --graph2city-in data/boulder/graph2city_seed

   civicmorph generate \
     --project-dir runs/boulder_graph2city \
     --profile transit_corridor_city \
     --seed-source hybrid \
     --graph2city-in data/boulder/graph2city_seed

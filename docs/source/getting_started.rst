Getting Started (Boulder, Colorado)
===================================

This quick start walks through the full CivicMorph flow for Boulder, Colorado, including
revised Mesa simulation options.

Prerequisites
-------------

- Python 3.11+ environment
- Optional extras for integrations:
  - ``pip install -e .[graph2city]``
  - ``pip install -e .[abm]``
  - ``pip install -e .[osm]``
- Local Boulder data files (if using local PBF mode):
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
     --abm-top 10 \
     --abm-mode abm

   civicmorph export \
     --project-dir runs/boulder_demo \
     --top 5

Alternative OSM Selectors
-------------------------

You can start from place name or polygon selectors instead of a local PBF:

.. code-block:: bash

   civicmorph build-baseline \
     --place "Boulder, Colorado" \
     --project-dir runs/boulder_place

   civicmorph build-baseline \
     --study-area data/boulder/boulder_polygon.geojson \
     --constraint-mask data/boulder/water_mask.geojson \
     --constraint-mask data/boulder/conservation_mask.geojson \
     --project-dir runs/boulder_polygon

Mesa Simulation Options
-----------------------

`score` supports five Mesa simulation options:

- ``abm``: heterogeneous households/developers/employers + planner/transit operator feedback loop.
- ``dla``: DLA-inspired development event attachment around seed nodes and attraction gradients.
- ``ca``: stochastic cellular automata transitions on ``grid`` or ``hex`` tessellation.
- ``network``: street/transit intervention simulation (new links, bus lanes, station infill).
- ``multi_scale``: coupled parcel/cell + corridor + regional-growth/conservation behavior.

Key runtime levers:

- Policy: ``--policy-upzone``, ``--policy-transit-investment``, ``--policy-affordable-housing``, ``--policy-parking-reduction``, ``--policy-green-protection``
- CA-specific: ``--ca-tessellation``
- Network-specific: ``--network-new-links``, ``--network-bus-lane-km``, ``--network-station-infill``
- Multi-scale regional controls: ``--regional-growth-boundary``, ``--regional-conservation-share``

Mode-Specific Scoring Examples
------------------------------

DLA-inspired growth:

.. code-block:: bash

   civicmorph score \
     --project-dir runs/boulder_demo \
     --with-abm \
     --abm-mode dla \
     --policy-upzone 1.1 \
     --policy-parking-reduction 1.2

Cellular automata on hex tessellation:

.. code-block:: bash

   civicmorph score \
     --project-dir runs/boulder_demo \
     --with-abm \
     --abm-mode ca \
     --ca-tessellation hex \
     --policy-green-protection 1.2

Network + multi-scale objective bundle:

.. code-block:: bash

   civicmorph score \
     --project-dir runs/boulder_demo \
     --with-abm \
     --abm-mode multi_scale \
     --policy-upzone 1.2 \
     --policy-transit-investment 1.3 \
     --network-new-links 6 \
     --network-bus-lane-km 24 \
     --network-station-infill 4 \
     --regional-growth-boundary 0.95 \
     --regional-conservation-share 0.3

What to Inspect
---------------

- ``runs/boulder_demo/scoring/member_scores.parquet`` for score distributions and ABM mode outputs.
- ``runs/boulder_demo/scoring/pareto_frontier.parquet`` for efficient tradeoffs.
- ``runs/boulder_demo/abm/abm_summary.parquet`` for per-member simulation metrics.
- ``runs/boulder_demo/exports/top_1_interactive.html`` for the composite map.

New ABM summary fields include:

- ``abm_mode``
- ``abm_growth_focus_index``
- ``abm_capacity_utilization``
- ``abm_network_access_gain``

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

Further Framework Introductions
-------------------------------

For additional conceptual onboarding and framework context, continue with:

- :doc:`user_guide/framework_introduction`
- :doc:`user_guide/framework_workflow`
- :doc:`user_guide/framework_interoperability`

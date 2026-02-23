Framework Interoperability (Graph2City + Mesa)
===============================================

This guide introduces how CivicMorph interoperates with Graph2City and Mesa while keeping
the CivicMorph generator as the primary planning engine.

Design Principle
----------------

Integration is adapter-based and optional:

- Graph2City is used for seed import/export interoperability.
- Mesa is used for post-plan evaluation, not generation.
- Core CivicMorph commands remain usable without either framework installed.

Dependency Setup
----------------

.. code-block:: bash

   pip install -e .[graph2city]
   pip install -e .[abm]
   # or:
   pip install -e .[frameworks]

If extras are missing, only framework-specific paths fail with actionable install hints.

Graph2City Integration Modes
----------------------------

Generation seed source controls how Graph2City participates:

- ``--seed-source osm``:
  CivicMorph uses baseline OSM-derived context only.
- ``--seed-source graph2city --graph2city-in <path>``:
  Graph2City seed priors drive member initialization.
- ``--seed-source hybrid --graph2city-in <path>``:
  OSM baseline remains primary; Graph2City contributes structured priors.

Boulder example:

.. code-block:: bash

   civicmorph build-baseline \
     --osm-pbf data/boulder/boulder.osm.pbf \
     --graph2city-in data/boulder/graph2city_seed \
     --project-dir runs/boulder_g2c

   civicmorph generate \
     --project-dir runs/boulder_g2c \
     --profile transit_corridor_city \
     --seed-source hybrid \
     --graph2city-in data/boulder/graph2city_seed

Mesa Integration Modes
----------------------

Enable Mesa via scoring:

.. code-block:: bash

   civicmorph score \
     --project-dir runs/boulder_g2c \
     --with-abm \
     --abm-top 10 \
     --abm-mode multi_scale

Supported modes:

- ``abm``:
  heterogeneous households/developers/employers + planner/operator feedback.
- ``dla``:
  DLA-inspired growth events attaching around seeded centers.
- ``ca``:
  stochastic cellular automata transitions on ``grid`` or ``hex`` tessellation.
- ``network``:
  accessibility-driven growth under street/transit interventions.
- ``multi_scale``:
  coupled cell/corridor/regional dynamic evaluation.

ABM columns added to ``member_scores.parquet`` include:

- ``abm_non_auto_mode_share``
- ``abm_median_daily_needs_minutes``
- ``abm_public_space_visit_rate``
- ``abm_access_equity_gap``
- ``abm_penalty``
- ``final_with_abm``

Python API Entry Points
-----------------------

Graph2City adapter functions:

- ``civicmorph.integrations.graph2city_adapter.import_graph2city``
- ``civicmorph.integrations.graph2city_adapter.merge_seed_with_baseline``
- ``civicmorph.integrations.graph2city_adapter.export_plan_to_graph2city``

Mesa runner:

- ``civicmorph.abm.mesa_runner.run_mesa_evaluation``

Data retrieval support functions:

- ``civicmorph.data_sources.retrieve_osm_data``
- ``civicmorph.data_sources.retrieve_dem_data``
- ``civicmorph.data_sources.retrieve_flood_data``
- ``civicmorph.data_sources.retrieve_constraint_masks``
- ``civicmorph.data_sources.retrieve_tabular_source``

Interoperability Guardrails
---------------------------

When using Graph2City + Mesa together in Boulder scenarios:

1. Keep human-scale caps and terrain constraints active in profile settings.
2. Treat Graph2City exports as interchange packages, not canonical plan truth.
3. Compare static and ABM-adjusted ranking to explain sensitivity of top members.
4. Keep fixed seeds for repeatable workshop narratives.

Read Next
---------

- :doc:`intermediate_applications` for applied Boulder scenario patterns.
- :doc:`../api/integrations` and :doc:`../api/abm` for function-level API details.

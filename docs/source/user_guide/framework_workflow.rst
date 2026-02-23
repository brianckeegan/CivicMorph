Framework Workflow (Boulder, Colorado)
======================================

This guide explains the end-to-end lifecycle of a CivicMorph run and what each stage contributes.

Lifecycle Overview
------------------

1. ``build-baseline``:
   ingest OSM + terrain and create baseline context artifacts.
2. ``generate``:
   synthesize one-shot ensemble members with stratified parameter sampling.
3. ``score``:
   compute static objective/penalty scores, optionally with Mesa post-plan evaluation.
4. ``export``:
   generate presentation-ready map outputs and GIS-style layer packages.

Boulder CLI Walkthrough
-----------------------

.. code-block:: bash

   civicmorph build-baseline \
     --place "Boulder, Colorado" \
     --project-dir runs/boulder_framework_intro

   civicmorph generate \
     --project-dir runs/boulder_framework_intro \
     --profile optimistic_courtyard_city \
     --ensemble 50 \
     --seed 1

   civicmorph score \
     --project-dir runs/boulder_framework_intro \
     --with-abm \
     --abm-top 10 \
     --abm-mode abm

   civicmorph export \
     --project-dir runs/boulder_framework_intro \
     --top 5

Key Artifacts by Stage
----------------------

Baseline stage (``runs/.../baseline/``):

- ``cells_baseline.parquet``
- ``osm_*.parquet`` (streets, paths, buildings, land use, amenities, transit where available)
- ``terrain_slope.tif`` / ``terrain_flood.tif`` / ``terrain_viewshed.tif`` (artifact placeholders)

Generation stage (``runs/.../ensemble/member_<id>/``):

- ``cells_proposed.parquet``
- ``blocks.gpkg``
- ``transit.gpkg`` plus ``transit_lines.parquet`` and ``transit_stops.parquet``
- ``streets_priority.gpkg``
- ``green_network.gpkg``

Scoring stage (``runs/.../scoring/`` and optional ``runs/.../abm/``):

- ``member_scores.parquet``
- ``pareto_frontier.parquet``
- ``balanced_exemplar.json``
- ``top5.json``
- ``abm/abm_summary.parquet`` when ``--with-abm`` is enabled

Export stage (``runs/.../exports/``):

- ``top_<rank>_composite.png``
- ``top_<rank>_thematic_panels.png``
- ``top_<rank>_interactive.html``
- ``top_<rank>_layers.gpkg``

How to Read Results
-------------------

Use the following sequence for Boulder reviews:

1. Start with ``member_scores.parquet`` to identify high-performing candidates.
2. Check penalty columns to understand tradeoffs (flood, slope, green inequity, etc.).
3. Open ``top_1_thematic_panels.png`` and ``top_1_interactive.html`` to inspect spatial pattern logic.
4. Use ``pareto_frontier.parquet`` to build shortlist options for design discussion.

Reproducibility Notes
---------------------

- Keep ``--seed`` fixed when comparing policy packages.
- Keep profile fixed when isolating only Mesa mode behavior.
- Use dedicated run directories for each Boulder experiment batch.

Read Next
---------

- :doc:`framework_interoperability` for framework integrations.
- :doc:`intermediate_application_scaffolding` to turn a run into reusable analysis apps.

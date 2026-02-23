Intermediate Applications (Boulder)
===================================

This section outlines three intermediate applications built on CivicMorph outputs.

1. Transit Corridor Retrofit for Boulder Arterials
---------------------------------------------------

Goal
^^^^

Compare corridor-forward ensemble members to identify which synthetic transit alignments best improve
15-minute access while keeping height caps under 60 ft.

Inputs
^^^^^^

- ``runs/boulder_demo/ensemble/member_*/cells_proposed.parquet``
- ``runs/boulder_demo/ensemble/member_*/transit.gpkg``
- ``runs/boulder_demo/scoring/member_scores.parquet``

Suggested Mesa mode
^^^^^^^^^^^^^^^^^^^

- Start with ``--abm-mode network`` to stress-test corridor/link interventions.
- Use ``--network-new-links``, ``--network-bus-lane-km``, and ``--network-station-infill`` for alternative retrofit packages.

Outputs
^^^^^^^

- Ranked candidate corridors for design discussion.
- Tradeoff matrix between compactness, green access, and non-auto access.

2. Flood-Adaptive Green Weave Scenario
--------------------------------------

Goal
^^^^

Use terrain and flood risk overlays to identify green-network-first plans that improve resilience and public-space continuity.

Inputs
^^^^^^

- ``runs/boulder_demo/baseline/terrain_flood.tif``
- ``runs/boulder_demo/ensemble/member_*/green_network.gpkg``
- ``runs/boulder_demo/scoring/member_scores.parquet``

Suggested Mesa mode
^^^^^^^^^^^^^^^^^^^

- Start with ``--abm-mode ca`` to model stochastic land-use transition under constraints.
- Test both ``--ca-tessellation grid`` and ``--ca-tessellation hex``.
- Increase ``--policy-green-protection`` to evaluate conservation-oriented policy packages.

Outputs
^^^^^^^

- Priority corridors for flood-adaptive public green expansion.
- Candidate plans with low flood-exposure penalties.

3. Neighborhood 15-Minute Retrofit Comparison
---------------------------------------------

Goal
^^^^

Evaluate access improvements around selected Boulder neighborhoods by comparing baseline vs. post-plan
ABM-adjusted outcomes.

Inputs
^^^^^^

- ``runs/boulder_demo/baseline/cells_baseline.parquet``
- ``runs/boulder_demo/abm/abm_summary.parquet``
- ``runs/boulder_demo/scoring/member_scores.parquet``

Suggested Mesa mode
^^^^^^^^^^^^^^^^^^^

- ``--abm-mode abm`` for behavioral feedback under heterogeneity and budgets.
- ``--abm-mode multi_scale`` for coupled parcel/corridor/regional policy tests.
- Use regional controls ``--regional-growth-boundary`` and ``--regional-conservation-share`` for scenario envelopes.

Outputs
^^^^^^^

- Neighborhood-level summaries for workshop discussion.
- Candidate policy narratives tied to score signals and penalties.

Mesa Mode Selection Heuristic
-----------------------------

Use this shortcut when choosing mode for Boulder applications:

- Growth pattern exploration near existing centers: ``dla``
- Parcel/cell transition dynamics and zoning sensitivity: ``ca``
- Corridor and link intervention packages: ``network``
- Full behavior and budget response: ``abm``
- Combined local-corridor-regional policy envelopes: ``multi_scale``

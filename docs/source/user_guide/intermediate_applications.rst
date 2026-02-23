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

Outputs
^^^^^^^

- Neighborhood-level summaries for workshop discussion.
- Candidate policy narratives tied to score signals and penalties.

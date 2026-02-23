Scaffolding Intermediate Applications
=====================================

This template helps teams create reusable analysis applications from Boulder run artifacts.

Recommended Project Layout
--------------------------

.. code-block:: text

   apps/
     boulder_transit_retrofit/
       app.py
       config.yaml
       README.md
     boulder_green_weave/
       app.py
       config.yaml
       README.md
     boulder_access_equity/
       app.py
       config.yaml
       README.md

Scaffold Checklist
------------------

1. Define a single question and one decision output.
2. Pin the CivicMorph run directory and profile in ``config.yaml``.
3. Pin a Mesa simulation mode and its key levers for repeatability.
4. Load only required layers for speed and reproducibility.
5. Log objective, penalty, and ABM diagnostic columns, not only final ranks.
6. Export one graphic and one tabular summary per app run.

Minimal ``config.yaml`` Pattern
--------------------------------

.. code-block:: yaml

   city: boulder_co
   run_dir: runs/boulder_demo
   baseline_cells: baseline/cells_baseline.parquet
   scores: scoring/member_scores.parquet
   abm_summary: abm/abm_summary.parquet
   objective_columns:
     - compactness_score
     - green_access_score
     - non_auto_access_score
   mesa:
     mode: multi_scale
     ca_tessellation: hex
     policy_upzone: 1.2
     policy_transit_investment: 1.3
     policy_affordable_housing: 1.0
     policy_parking_reduction: 1.1
     policy_green_protection: 1.2
     network_new_links: 6
     network_bus_lane_km: 24
     network_station_infill: 4
     regional_growth_boundary: 0.95
     regional_conservation_share: 0.30

Reusable Analysis Function Pattern
----------------------------------

.. code-block:: python

   from pathlib import Path
   import pandas as pd

   ABM_COLUMNS = [
       "abm_mode",
       "abm_penalty",
       "abm_growth_focus_index",
       "abm_capacity_utilization",
       "abm_network_access_gain",
   ]

   def load_boulder_scores(run_dir: Path) -> pd.DataFrame:
       """Load and sort Boulder member scores with ABM diagnostics.

       Parameters
       ----------
       run_dir : Path
           CivicMorph run directory for Boulder.

       Returns
       -------
       pandas.DataFrame
           Score table sorted by final_with_abm descending.
       """
       scores = pd.read_parquet(run_dir / "scoring" / "member_scores.parquet")
       cols = [c for c in ABM_COLUMNS if c in scores.columns]
       return scores[["member_id", "final_with_abm", *cols]].sort_values(
           "final_with_abm", ascending=False
       )

Integration Tips
----------------

- Use a fixed ``--seed`` when comparing policy bundles.
- Keep each app profile-specific, then compare profiles at summary level.
- For mode comparisons, keep levers fixed and vary only ``--abm-mode``.
- If using Graph2City exports, treat them as interchange artifacts, not authoritative source-of-truth.

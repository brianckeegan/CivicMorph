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
3. Load only required layers for speed and reproducibility.
4. Log score + penalty terms, not only final ranks.
5. Export one graphic and one tabular summary per app run.

Minimal ``config.yaml`` Pattern
--------------------------------

.. code-block:: yaml

   city: boulder_co
   run_dir: runs/boulder_demo
   baseline_cells: baseline/cells_baseline.parquet
   scores: scoring/member_scores.parquet
   objective_columns:
     - compactness_score
     - green_access_score
     - non_auto_access_score

Reusable Analysis Function Pattern
----------------------------------

.. code-block:: python

   from pathlib import Path
   import pandas as pd

   def load_boulder_scores(run_dir: Path) -> pd.DataFrame:
       """Load and sort Boulder member scores.

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
       return scores.sort_values("final_with_abm", ascending=False)

Integration Tips
----------------

- Use ``--seed`` to make scenario outputs deterministic in stakeholder reviews.
- Keep each app profile-specific, then compare across profiles at summary level.
- If using Graph2City exports, treat them as interchange artifacts, not authoritative source-of-truth.

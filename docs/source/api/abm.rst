ABM API
=======

Mesa Simulation Options
-----------------------

CivicMorph supports these Mesa simulation options in ``score --abm-mode``:

- ``abm``: heterogeneous household/developer/employer behaviors with policy and budget feedback loops.
- ``dla``: diffusion-limited attachment-inspired growth around seed nodes.
- ``ca``: cellular automata land-use transitions (``grid`` or ``hex`` tessellation).
- ``network``: network intervention growth based on accessibility and centrality shifts.
- ``multi_scale``: coupled cell/corridor/regional simulation with growth-boundary and conservation controls.

Each mode writes core ABM metrics plus mode-agnostic diagnostics:

- ``abm_non_auto_mode_share``
- ``abm_median_daily_needs_minutes``
- ``abm_public_space_visit_rate``
- ``abm_access_equity_gap``
- ``abm_growth_focus_index``
- ``abm_capacity_utilization``
- ``abm_network_access_gain``

.. currentmodule:: civicmorph.abm.mesa_runner

.. autosummary::
   :toctree: generated
   :nosignatures:

   run_mesa_evaluation
   abm_result_to_frame

.. automodule:: civicmorph.abm.mesa_runner
   :members: run_mesa_evaluation, abm_result_to_frame
   :undoc-members:
   :show-inheritance:

.. currentmodule:: civicmorph.types

Configuration Types
-------------------

.. autosummary::
   :toctree: generated
   :nosignatures:

   ABMConfig
   ABMResult
   ABMPenaltyBreakdown

.. automodule:: civicmorph.types
   :members: ABMConfig, ABMResult, ABMPenaltyBreakdown
   :undoc-members:
   :show-inheritance:

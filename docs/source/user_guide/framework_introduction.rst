Framework Introduction (Boulder, Colorado)
==========================================

This guide introduces the CivicMorph framework before you dive into command-level workflows.
Use Boulder, Colorado as the reference city throughout this section.

What CivicMorph Is
------------------

CivicMorph is a deterministic, one-shot speculative urban planning framework that transforms
OSM + terrain inputs into an ensemble of future plan alternatives. It prioritizes:

- Public transit, biking, and walking over private auto dependence.
- Human-scale intensity defaults (with 60 ft cap logic in baseline profiles).
- Terrain-informed planning decisions (slope, flood, and view-shed aware).
- Penalty-based scoring instead of hard rejection of imperfect candidates.

What CivicMorph Is Not
----------------------

- Not a parcel-accurate entitlement simulator.
- Not a GTFS-dependent transit model.
- Not an UrbanSim or VoxCity wrapper.
- Not a single "best plan" optimizer. It is an ensemble exploration system.

Core Building Blocks
--------------------

Each ensemble member produces four products:

1. Cell overlays:
   ``proposed_intensity_far``, ``proposed_height_cap_ft``, ``street_priority_class``,
   ``car_deemphasis_score``, ``green_access_score``, ``flood_risk_score``,
   ``slope_constraint_score``, ``view_shed_value_score``.
2. Synthetic blocks:
   block polygons, typology assignment, and envelope parameters.
3. Synthetic transit:
   abstract lines and stops with type/headway/speed/spacing attributes.
4. Composite rendering:
   static PNG and interactive HTML map products for presentation and review.

Guiding Commitments
-------------------

These commitments remain active even when you enable Graph2City and Mesa support:

- Cell-first representation drives synthesis and scoring.
- Blocks and transit are synthetic outputs, not imported as authoritative truth.
- Transformations are one-shot regime shifts for each member.
- Terrain is first-class across intensity, block form, and green placement.
- Undesirable patterns are penalized in scoring, not hard-filtered out.

Boulder Example Framing
-----------------------

For Boulder, a typical framing question is:

"Which speculative plan alternatives improve non-auto access and green equity while
reducing flood and slope overbuild risk?"

In CivicMorph terms, this means:

- Build baseline from Boulder OSM + terrain sources.
- Generate a stratified ensemble across corridor, intensity, and terrain-sensitivity dimensions.
- Score members on objectives and penalties.
- Optionally refine top-ranked members with Mesa post-plan simulation.

Read Next
---------

- :doc:`framework_workflow` for the run lifecycle and artifact layout.
- :doc:`framework_interoperability` for Graph2City + Mesa integration behavior.
- :doc:`intermediate_applications` for applied Boulder scenario patterns.

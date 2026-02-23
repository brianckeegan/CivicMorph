Profile Parameters and Examples (Boulder)
=========================================

Profiles are YAML files that tune CivicMorph generation behavior through scalar multipliers.
Built-in profiles live in ``config/profiles/`` and are selected with ``--profile`` during
``generate``.

Where Profiles Are Loaded
-------------------------

- Loader: ``civicmorph.config.load_profile(...)``
- Files: ``config/profiles/<profile_name>.yaml``
- CLI usage:

.. code-block:: bash

   civicmorph generate \
     --project-dir runs/boulder_demo \
     --profile optimistic_courtyard_city \
     --ensemble 50 \
     --seed 1

Parameter Definitions
---------------------

.. list-table::
   :header-rows: 1
   :widths: 28 10 10 20 32

   * - Parameter
     - Type
     - Default
     - Applied in generation
     - Effect
   * - ``name``
     - ``str``
     - filename stem
     - metadata
     - Scenario/profile identifier in manifests and outputs.
   * - ``transit_investment_intensity``
     - ``float``
     - ``1.0``
     - reserved
     - Transit investment scenario scalar reserved for transit weighting extensions. It is currently not applied directly in core synthesis formulas.
   * - ``green_budget``
     - ``float``
     - ``1.0``
     - yes
     - Multiplies green budget scalar. Higher values increase green access uplift and green-network expansion.
   * - ``street_conversion_budget``
     - ``float``
     - ``1.0``
     - yes
     - Multiplies street conversion scalar. Higher values increase car deemphasis and pedestrian/bike/transit priority shifts.
   * - ``intensity_budget``
     - ``float``
     - ``1.0``
     - yes
     - Multiplies intensity scalar. Higher values generally increase proposed FAR and push more cells toward upper human-scale bands.
   * - ``terrain_sensitivity``
     - ``float``
     - ``1.0``
     - yes
     - Multiplies terrain-penalty sensitivity. Higher values impose stronger slope/flood moderation on intensity allocation.

Built-in Profiles
-----------------

.. list-table::
   :header-rows: 1
   :widths: 26 12 12 14 12 12

   * - Profile
     - transit_investment_intensity
     - green_budget
     - street_conversion_budget
     - intensity_budget
     - terrain_sensitivity
   * - ``optimistic_courtyard_city``
     - 1.10
     - 1.05
     - 1.00
     - 1.10
     - 1.00
   * - ``green_weave_first``
     - 0.90
     - 1.30
     - 1.00
     - 0.95
     - 1.20
   * - ``transit_corridor_city``
     - 1.30
     - 0.95
     - 1.15
     - 1.20
     - 0.95
   * - ``bike_supergrid_city``
     - 1.00
     - 1.10
     - 1.30
     - 1.00
     - 1.05

Boulder Usage Examples
----------------------

Choose a built-in profile:

.. code-block:: bash

   civicmorph generate \
     --project-dir runs/boulder_demo \
     --profile green_weave_first \
     --ensemble 50 \
     --seed 1

Create a custom Boulder profile:

.. code-block:: yaml

   # config/profiles/boulder_balanced_demo.yaml
   name: boulder_balanced_demo
   transit_investment_intensity: 1.20
   green_budget: 1.15
   street_conversion_budget: 1.10
   intensity_budget: 1.05
   terrain_sensitivity: 1.20

Run with your custom profile:

.. code-block:: bash

   civicmorph generate \
     --project-dir runs/boulder_demo \
     --profile boulder_balanced_demo \
     --ensemble 50 \
     --seed 1

Python Example
--------------

.. code-block:: python

   from pathlib import Path
   from civicmorph.config import load_profile

   profile = load_profile(
       profile_name="transit_corridor_city",
       profiles_dir=Path("config/profiles"),
   )
   print(profile)

Read Next
---------

- :doc:`framework_workflow` for full run lifecycle.
- :doc:`../api/config` for configuration API references.

Tutorial Notebook (Boulder)
===========================

The step-by-step tutorial notebook for Boulder is available at:

- ``output/jupyter-notebook/civicmorph-boulder-colorado-tutorial.ipynb``
- ``docs/source/notebooks/civicmorph-boulder-colorado-tutorial.ipynb``

The notebook covers:

1. Preparing Boulder-specific inputs and run directories.
2. Executing baseline, generation, scoring, and export workflows.
3. Comparing all Mesa simulation modes (``abm``, ``dla``, ``ca``, ``network``, ``multi_scale``).
4. Applying policy, network, and regional lever bundles in scoring.
5. Interpreting top plans, penalties, and ABM-adjusted rankings.
6. Exporting Graph2City-compatible plan packages.

You can execute the notebook locally with JupyterLab:

.. code-block:: bash

   pip install jupyterlab
   jupyter lab output/jupyter-notebook/civicmorph-boulder-colorado-tutorial.ipynb

Notebook in this documentation build:

.. toctree::
   :maxdepth: 1

   notebooks/civicmorph-boulder-colorado-tutorial

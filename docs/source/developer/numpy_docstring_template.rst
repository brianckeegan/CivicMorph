NumPy Docstring Template
========================

CivicMorph uses NumPy-style docstrings so API pages can be generated consistently with Sphinx Napoleon.

Function Template
-----------------

.. code-block:: python

   def example(arg1: int, arg2: str = "x") -> bool:
       """One-line summary.

       Extended summary with implementation notes if needed.

       Parameters
       ----------
       arg1 : int
           Description of ``arg1``.
       arg2 : str, default="x"
           Description of ``arg2``.

       Returns
       -------
       bool
           Description of return value.

       Raises
       ------
       ValueError
           Raised when input constraints are not met.

       Notes
       -----
       Optional section for algorithm or behavior details.

       Examples
       --------
       >>> example(1, "x")
       True
       """

Minimum Required Sections
-------------------------

- Summary line
- ``Parameters``
- ``Returns``

Recommended Sections (when applicable)
--------------------------------------

- ``Raises``
- ``Notes``
- ``Examples``

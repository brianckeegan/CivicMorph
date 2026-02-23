"""Sphinx configuration for CivicMorph documentation."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

project = "CivicMorph"
author = "CivicMorph Contributors"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "numpydoc",
    "nbsphinx",
]

autosummary_generate = True
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_param = False
napoleon_use_rtype = False

numpydoc_show_class_members = False

# Keep docs build resilient in minimal environments.
autodoc_mock_imports = [
    "graph2city",
    "mesa",
    "geopandas",
    "rasterio",
    "shapely",
    "folium",
    "typer",
    "pydantic",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "**.ipynb_checkpoints"]

html_theme = "alabaster"
html_static_path = ["_static"]

# Notebook execution is disabled for deterministic docs builds.
nbsphinx_execute = "never"


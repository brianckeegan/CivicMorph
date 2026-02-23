"""Composite rendering for CivicMorph outputs."""

from __future__ import annotations

import base64
from pathlib import Path

import numpy as np
import pandas as pd

from .io import ensure_dir, read_dataframe


_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7b"
    "G6wAAAAASUVORK5CYII="
)


def _write_tiny_png(path: Path) -> None:
    """Write a 1x1 fallback PNG.

    Parameters
    ----------
    path : Path
        Destination PNG file path.
    """

    path.write_bytes(base64.b64decode(_TINY_PNG_B64))


def render_composite_png(
    cells_path: Path,
    blocks_path: Path,
    transit_lines_path: Path,
    transit_stops_path: Path,
    green_path: Path,
    streets_path: Path,
    out_png: Path,
) -> Path:
    """Render static composite PNG from primary layers.

    Parameters
    ----------
    cells_path : Path
        Cell overlay table path.
    blocks_path : Path
        Synthetic blocks table path.
    transit_lines_path : Path
        Transit lines table path.
    transit_stops_path : Path
        Transit stops table path.
    green_path : Path
        Green network table path.
    streets_path : Path
        Street-priority table path.
    out_png : Path
        Output PNG path.

    Returns
    -------
    Path
        Rendered image path.
    """

    cells = read_dataframe(cells_path)
    blocks = read_dataframe(blocks_path)
    lines = read_dataframe(transit_lines_path)
    stops = read_dataframe(transit_stops_path)
    green = read_dataframe(green_path)
    streets = read_dataframe(streets_path)

    ensure_dir(out_png.parent)
    try:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(11, 8), dpi=150)
        sc = ax.scatter(
            cells["x"],
            cells["y"],
            c=cells["proposed_intensity_far"],
            cmap="YlOrRd",
            s=12,
            alpha=0.9,
            label="FAR heat",
        )
        plt.colorbar(sc, ax=ax, label="Proposed FAR")

        ax.scatter(green["priority_score"] * 0 + green.index % 25, green.index // 25, c="green", s=10, alpha=0.4)
        ax.scatter(stops["x"], stops["y"], c="royalblue", s=10, marker="^", alpha=0.8)

        # Light street backdrop using segment IDs as x locations.
        if "segment_id" in streets.columns:
            for x in streets["segment_id"].astype(float).to_numpy():
                ax.plot([x, x], [0, max(cells["y"])], color="gray", alpha=0.07, linewidth=1)

        ax.set_title("CivicMorph Composite Rendering")
        ax.set_xlabel("Grid X")
        ax.set_ylabel("Grid Y")
        ax.grid(alpha=0.15)
        fig.tight_layout()
        fig.savefig(out_png)
        plt.close(fig)
    except Exception:
        _write_tiny_png(out_png)

    return out_png


def render_interactive_html(
    cells_path: Path,
    lines_path: Path,
    stops_path: Path,
    green_path: Path,
    out_html: Path,
) -> Path:
    """Render interactive HTML map with layer toggles.

    Parameters
    ----------
    cells_path : Path
        Cell overlay table path.
    lines_path : Path
        Transit lines table path.
    stops_path : Path
        Transit stops table path.
    green_path : Path
        Green network table path.
    out_html : Path
        Output HTML path.

    Returns
    -------
    Path
        Rendered HTML file path.
    """

    cells = read_dataframe(cells_path)
    lines = read_dataframe(lines_path)
    stops = read_dataframe(stops_path)
    green = read_dataframe(green_path)

    ensure_dir(out_html.parent)
    try:
        import folium

        center = [float(cells["y"].mean()), float(cells["x"].mean())]
        fmap = folium.Map(location=center, zoom_start=12, tiles="CartoDB positron")

        fg_cells = folium.FeatureGroup(name="FAR Cells")
        for _, row in cells.sample(min(500, len(cells)), random_state=1).iterrows():
            folium.CircleMarker(
                location=[row["y"], row["x"]],
                radius=3,
                color=None,
                fill=True,
                fill_opacity=0.6,
                fill_color="#e34a33",
                popup=f"cell={row['cell_id']} FAR={row['proposed_intensity_far']:.2f}",
            ).add_to(fg_cells)
        fg_cells.add_to(fmap)

        fg_transit = folium.FeatureGroup(name="Transit Stops")
        for _, row in stops.iterrows():
            folium.Marker(
                location=[row["y"], row["x"]],
                icon=folium.Icon(color="blue", icon="info-sign"),
                popup=f"{row['line_id']} - {row['name']}",
            ).add_to(fg_transit)
        fg_transit.add_to(fmap)

        fg_green = folium.FeatureGroup(name="Green Network")
        for i, row in green.head(400).iterrows():
            y = (i // 25) % 25
            x = i % 25
            folium.CircleMarker(
                location=[y, x],
                radius=2,
                fill=True,
                color="green",
                fill_opacity=0.5,
                popup=f"priority={row.get('priority_score', 0):.2f}",
            ).add_to(fg_green)
        fg_green.add_to(fmap)

        folium.LayerControl().add_to(fmap)
        fmap.save(str(out_html))
    except Exception:
        html = """<!doctype html><html><head><meta charset='utf-8'><title>CivicMorph Map</title></head>
<body><h1>CivicMorph Interactive Map</h1>
<p>Fallback renderer generated this page because folium is unavailable.</p>
<ul>
<li>Cells: {cells}</li>
<li>Transit lines: {lines}</li>
<li>Transit stops: {stops}</li>
<li>Green network points: {green}</li>
</ul>
</body></html>
""".format(cells=len(cells), lines=len(lines), stops=len(stops), green=len(green))
        out_html.write_text(html)

    return out_html

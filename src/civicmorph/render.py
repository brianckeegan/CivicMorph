"""Composite rendering for CivicMorph outputs."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .io import ensure_dir, read_dataframe


_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7b"
    "G6wAAAAASUVORK5CYII="
)

_STREET_COLORS = {
    "ped_priority": "#c1121f",
    "transit_priority": "#f77f00",
    "bike_priority": "#2a9d8f",
    "mixed_local": "#457b9d",
    "vehicle_limited": "#6c757d",
}

_TRANSIT_COLORS = {
    "BRT": "#e63946",
    "Tram": "#7b2cbf",
    "MetroLite": "#1d3557",
}

_TYPOLOGY_COLORS = {
    "courtyard": "#ffd166",
    "perimeter_mixed_use": "#f4a261",
    "rowhouse": "#a8dadc",
    "small_apartment_court": "#90be6d",
}


def _write_tiny_png(path: Path) -> None:
    """Write a 1x1 fallback PNG.

    Parameters
    ----------
    path : Path
        Destination PNG file path.
    """

    path.write_bytes(base64.b64decode(_TINY_PNG_B64))


def _coerce_numeric(frame: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    """Read a numeric series from a dataframe with stable fallback values.

    Parameters
    ----------
    frame : pandas.DataFrame
        Input dataframe.
    col : str
        Column name to parse.
    default : float, default=0.0
        Fallback value when column is missing or cannot be parsed.

    Returns
    -------
    pandas.Series
        Numeric series aligned to the input index.
    """

    if col not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[col], errors="coerce").fillna(default)


def _series_or_default(frame: pd.DataFrame, col: str, default: str = "") -> pd.Series:
    """Read a string-like series from dataframe with default fallback.

    Parameters
    ----------
    frame : pandas.DataFrame
        Input dataframe.
    col : str
        Column name to read.
    default : str, default=""
        Fallback value when column is missing.

    Returns
    -------
    pandas.Series
        Series aligned to the input index.
    """

    if col not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="object")
    return frame[col].fillna(default)


def _to_geodataframe(table: pd.DataFrame, crs: str = "EPSG:3857"):
    """Convert an input table with geometry WKT or x/y columns to a GeoDataFrame.

    Parameters
    ----------
    table : pandas.DataFrame
        Input layer table.
    crs : str, default="EPSG:3857"
        Coordinate reference system to attach to the resulting geometry.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame with non-null geometries.
    """

    import geopandas as gpd
    from shapely import wkt

    work = table.copy()
    geometry = pd.Series([None] * len(work), index=work.index, dtype=object)

    if "geometry_wkt" in work.columns:
        parsed = []
        for value in work["geometry_wkt"]:
            if isinstance(value, str) and value.strip():
                try:
                    parsed.append(wkt.loads(value))
                except Exception:
                    parsed.append(None)
            else:
                parsed.append(None)
        geometry = pd.Series(parsed, index=work.index, dtype=object)

    if geometry.isna().all() and {"x", "y"}.issubset(work.columns):
        x = pd.to_numeric(work["x"], errors="coerce")
        y = pd.to_numeric(work["y"], errors="coerce")
        geometry = gpd.points_from_xy(x, y)

    gdf = gpd.GeoDataFrame(work, geometry=geometry, crs=crs)
    gdf = gdf[gdf.geometry.notna()].copy()
    if gdf.empty:
        return gdf

    if "x" not in gdf.columns:
        gdf["x"] = gdf.geometry.centroid.x
    if "y" not in gdf.columns:
        gdf["y"] = gdf.geometry.centroid.y
    return gdf


def _to_wgs84(gdf):
    """Project a GeoDataFrame to EPSG:4326 when possible.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        Input geometry layer.

    Returns
    -------
    geopandas.GeoDataFrame
        Reprojected layer when CRS information is valid, otherwise unchanged.
    """

    if gdf.empty:
        return gdf
    try:
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:3857", allow_override=True)
        if str(gdf.crs).upper() != "EPSG:4326":
            return gdf.to_crs(epsg=4326)
    except Exception:
        return gdf
    return gdf


def _plot_empty_panel(ax, title: str) -> None:
    """Render a consistent placeholder panel when data is unavailable."""

    ax.set_title(title)
    ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes, color="#555")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_frame_on(False)


def _draw_simple_fallback_png(cells: pd.DataFrame, stops: pd.DataFrame, out_png: Path) -> bool:
    """Try a plain matplotlib scatter fallback before writing a tiny placeholder."""

    try:
        import matplotlib.pyplot as plt
    except Exception:
        return False

    if not {"x", "y"}.issubset(cells.columns):
        return False

    fig, ax = plt.subplots(figsize=(10, 7), dpi=120)
    far = _coerce_numeric(cells, "proposed_intensity_far", 0.8)
    sc = ax.scatter(
        pd.to_numeric(cells["x"], errors="coerce"),
        pd.to_numeric(cells["y"], errors="coerce"),
        c=far,
        cmap="YlOrRd",
        s=12,
        alpha=0.85,
    )
    if {"x", "y"}.issubset(stops.columns):
        ax.scatter(
            pd.to_numeric(stops["x"], errors="coerce"),
            pd.to_numeric(stops["y"], errors="coerce"),
            c="#1d3557",
            s=16,
            marker="^",
            alpha=0.85,
        )
    fig.colorbar(sc, ax=ax, label="Proposed FAR")
    ax.set_title("CivicMorph Composite Rendering")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)
    return True


def render_composite_png(
    cells_path: Path,
    blocks_path: Path,
    transit_lines_path: Path,
    transit_stops_path: Path,
    green_path: Path,
    streets_path: Path,
    out_png: Path,
    crs: str = "EPSG:3857",
) -> Path:
    """Render a static composite PNG from CivicMorph layers.

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
    crs : str, default="EPSG:3857"
        CRS for geometry parsing and plotting.

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

        g_cells = _to_geodataframe(cells, crs)
        g_blocks = _to_geodataframe(blocks, crs)
        g_lines = _to_geodataframe(lines, crs)
        g_stops = _to_geodataframe(stops, crs)
        g_green = _to_geodataframe(green, crs)
        g_streets = _to_geodataframe(streets, crs)

        fig, ax = plt.subplots(figsize=(12, 9), dpi=170)
        ax.set_facecolor("#f6f3eb")

        if not g_cells.empty:
            cells_plot = g_cells.copy()
            cells_plot["proposed_intensity_far"] = _coerce_numeric(cells_plot, "proposed_intensity_far", 0.8)
            cells_plot["terrain_overlay"] = np.clip(
                0.55 * _coerce_numeric(cells_plot, "slope_constraint_score", 0.0)
                + 0.45 * _coerce_numeric(cells_plot, "flood_risk_score", 0.0),
                0.0,
                1.0,
            )
            cells_plot.plot(
                ax=ax,
                column="terrain_overlay",
                cmap="Greys",
                alpha=0.18,
                linewidth=0,
                legend=False,
            )
            cells_plot.plot(
                ax=ax,
                column="proposed_intensity_far",
                cmap="YlOrRd",
                alpha=0.72,
                linewidth=0.05,
                edgecolor="#fbf8f1",
                legend=True,
                legend_kwds={"label": "Proposed FAR", "shrink": 0.7},
            )

        if not g_blocks.empty:
            typologies = _series_or_default(g_blocks, "typology", "")
            colors = typologies.map(_TYPOLOGY_COLORS).fillna("#bdbdbd")
            g_blocks.plot(ax=ax, color=colors.to_list(), alpha=0.17, edgecolor="#3a3a3a", linewidth=0.45)

        if not g_streets.empty and "street_priority_class" in g_streets.columns:
            for label, color in _STREET_COLORS.items():
                subset = g_streets[g_streets["street_priority_class"] == label]
                if not subset.empty:
                    subset.plot(ax=ax, color=color, linewidth=1.1, alpha=0.7)

        if not g_lines.empty:
            line_types = _series_or_default(g_lines, "type", "")
            for mode, color in _TRANSIT_COLORS.items():
                subset = g_lines[line_types == mode]
                if not subset.empty:
                    subset.plot(ax=ax, color=color, linewidth=2.1, alpha=0.95)
            other = g_lines[~line_types.isin(_TRANSIT_COLORS)]
            if not other.empty:
                other.plot(ax=ax, color="#1d3557", linewidth=2.0, alpha=0.85)

        if not g_green.empty:
            g_green.plot(ax=ax, color="#2a9d8f", markersize=14, alpha=0.75)

        if not g_stops.empty:
            g_stops.plot(ax=ax, color="#0d3b66", markersize=18, alpha=0.9, marker="^")

        ax.set_title("CivicMorph Composite Rendering", pad=10)
        ax.set_axis_off()
        fig.tight_layout()
        fig.savefig(out_png, bbox_inches="tight")
        plt.close(fig)
    except Exception:
        fallback_drawn = _draw_simple_fallback_png(cells=cells, stops=stops, out_png=out_png)
        if not fallback_drawn:
            _write_tiny_png(out_png)

    return out_png


def render_thematic_panels_png(
    cells_path: Path,
    blocks_path: Path,
    lines_path: Path,
    green_path: Path,
    streets_path: Path,
    out_png: Path,
    crs: str = "EPSG:3857",
) -> Path:
    """Render a four-panel static image for key plan themes.

    Parameters
    ----------
    cells_path : Path
        Cell overlay table path.
    blocks_path : Path
        Synthetic blocks table path.
    lines_path : Path
        Transit lines table path.
    green_path : Path
        Green network table path.
    streets_path : Path
        Street-priority table path.
    out_png : Path
        Output panel PNG path.
    crs : str, default="EPSG:3857"
        CRS for geometry parsing and plotting.

    Returns
    -------
    Path
        Rendered image path.
    """

    cells = read_dataframe(cells_path)
    blocks = read_dataframe(blocks_path)
    lines = read_dataframe(lines_path)
    green = read_dataframe(green_path)
    streets = read_dataframe(streets_path)

    ensure_dir(out_png.parent)
    try:
        import matplotlib.pyplot as plt

        g_cells = _to_geodataframe(cells, crs)
        g_blocks = _to_geodataframe(blocks, crs)
        g_lines = _to_geodataframe(lines, crs)
        g_green = _to_geodataframe(green, crs)
        g_streets = _to_geodataframe(streets, crs)

        fig, axes = plt.subplots(2, 2, figsize=(13, 10), dpi=160)
        fig.patch.set_facecolor("#f8f7f2")
        ax_intensity, ax_mobility, ax_green, ax_terrain = axes.ravel()

        if not g_cells.empty:
            intensity = g_cells.copy()
            intensity["proposed_intensity_far"] = _coerce_numeric(intensity, "proposed_intensity_far", 0.8)
            intensity.plot(
                ax=ax_intensity,
                column="proposed_intensity_far",
                cmap="YlOrRd",
                alpha=0.8,
                linewidth=0.05,
                edgecolor="#ffffff",
                legend=True,
                legend_kwds={"shrink": 0.65},
            )
            if not g_blocks.empty:
                g_blocks.boundary.plot(ax=ax_intensity, color="#555", linewidth=0.3, alpha=0.65)
            ax_intensity.set_title("Intensity + Block Fabric")
            ax_intensity.set_axis_off()
        else:
            _plot_empty_panel(ax_intensity, "Intensity + Block Fabric")

        if not g_streets.empty and "street_priority_class" in g_streets.columns:
            for label, color in _STREET_COLORS.items():
                subset = g_streets[g_streets["street_priority_class"] == label]
                if not subset.empty:
                    subset.plot(ax=ax_mobility, color=color, linewidth=1.1, alpha=0.8)
            if not g_lines.empty:
                line_types = _series_or_default(g_lines, "type", "")
                for mode, color in _TRANSIT_COLORS.items():
                    subset = g_lines[line_types == mode]
                    if not subset.empty:
                        subset.plot(ax=ax_mobility, color=color, linewidth=2.0, alpha=0.9)
            ax_mobility.set_title("Street Priority + Transit")
            ax_mobility.set_axis_off()
        else:
            _plot_empty_panel(ax_mobility, "Street Priority + Transit")

        if not g_cells.empty:
            viewshed = g_cells.copy()
            viewshed["view_shed_value_score"] = _coerce_numeric(viewshed, "view_shed_value_score", 0.0)
            viewshed.plot(
                ax=ax_green,
                column="view_shed_value_score",
                cmap="BuGn",
                alpha=0.25,
                linewidth=0,
                legend=True,
                legend_kwds={"shrink": 0.65},
            )
            if not g_green.empty:
                g_green.plot(ax=ax_green, color="#2a9d8f", markersize=14, alpha=0.85)
            ax_green.set_title("Green Network + View Shed")
            ax_green.set_axis_off()
        else:
            _plot_empty_panel(ax_green, "Green Network + View Shed")

        if not g_cells.empty:
            terrain = g_cells.copy()
            terrain["flood_risk_score"] = _coerce_numeric(terrain, "flood_risk_score", 0.0)
            terrain["slope_constraint_score"] = _coerce_numeric(terrain, "slope_constraint_score", 0.0)
            terrain.plot(
                ax=ax_terrain,
                column="flood_risk_score",
                cmap="Blues",
                alpha=0.55,
                linewidth=0,
                legend=True,
                legend_kwds={"shrink": 0.65},
            )
            terrain.plot(
                ax=ax_terrain,
                column="slope_constraint_score",
                cmap="Purples",
                alpha=0.32,
                linewidth=0,
                legend=False,
            )
            ax_terrain.set_title("Flood + Slope Constraints")
            ax_terrain.set_axis_off()
        else:
            _plot_empty_panel(ax_terrain, "Flood + Slope Constraints")

        fig.tight_layout()
        fig.savefig(out_png, bbox_inches="tight")
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
    blocks_path: Path | None = None,
    streets_path: Path | None = None,
    crs: str = "EPSG:3857",
) -> Path:
    """Render an interactive HTML map with toggled geospatial layers.

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
    blocks_path : Path or None, default=None
        Optional blocks table path.
    streets_path : Path or None, default=None
        Optional street-priority table path.
    crs : str, default="EPSG:3857"
        CRS for geometry parsing and plotting.

    Returns
    -------
    Path
        Rendered HTML file path.
    """

    cells = read_dataframe(cells_path)
    lines = read_dataframe(lines_path)
    stops = read_dataframe(stops_path)
    green = read_dataframe(green_path)
    blocks = read_dataframe(blocks_path) if blocks_path is not None else pd.DataFrame()
    streets = read_dataframe(streets_path) if streets_path is not None else pd.DataFrame()

    ensure_dir(out_html.parent)
    try:
        import folium

        g_cells = _to_wgs84(_to_geodataframe(cells, crs))
        g_lines = _to_wgs84(_to_geodataframe(lines, crs))
        g_stops = _to_wgs84(_to_geodataframe(stops, crs))
        g_green = _to_wgs84(_to_geodataframe(green, crs))
        g_blocks = _to_wgs84(_to_geodataframe(blocks, crs))
        g_streets = _to_wgs84(_to_geodataframe(streets, crs))

        if not g_cells.empty:
            bounds = g_cells.total_bounds
            center = [(bounds[1] + bounds[3]) / 2.0, (bounds[0] + bounds[2]) / 2.0]
        else:
            center = [40.015, -105.27]
        fmap = folium.Map(location=center, zoom_start=12, tiles="CartoDB positron")

        if not g_cells.empty:
            cells_geo = g_cells.copy()
            cells_geo["proposed_intensity_far"] = _coerce_numeric(cells_geo, "proposed_intensity_far", 0.8)

            def _cell_style(feature: dict) -> dict[str, float | str]:
                value = float(feature["properties"].get("proposed_intensity_far", 0.8))
                if value < 1.2:
                    color = "#fee8c8"
                elif value < 2.5:
                    color = "#fdbb84"
                elif value < 3.8:
                    color = "#ef6548"
                else:
                    color = "#b30000"
                return {"color": "#ffffff", "weight": 0.2, "fillColor": color, "fillOpacity": 0.55}

            cell_fields = [name for name in ["cell_id", "proposed_intensity_far"] if name in cells_geo.columns]
            tooltip = folium.GeoJsonTooltip(fields=cell_fields) if cell_fields else None
            fg_cells = folium.FeatureGroup(name="Intensity Cells", show=True)
            folium.GeoJson(
                data=json.loads(cells_geo.to_json()),
                style_function=_cell_style,
                tooltip=tooltip,
            ).add_to(fg_cells)
            fg_cells.add_to(fmap)

        if not g_blocks.empty:
            blocks_geo = g_blocks.copy()

            def _block_style(feature: dict) -> dict[str, float | str]:
                typology = str(feature["properties"].get("typology", ""))
                color = _TYPOLOGY_COLORS.get(typology, "#bdbdbd")
                return {"color": "#4b4b4b", "weight": 0.4, "fillColor": color, "fillOpacity": 0.25}

            block_fields = [name for name in ["block_id", "typology", "far_target"] if name in blocks_geo.columns]
            tooltip = folium.GeoJsonTooltip(fields=block_fields) if block_fields else None
            fg_blocks = folium.FeatureGroup(name="Blocks", show=True)
            folium.GeoJson(
                data=json.loads(blocks_geo.to_json()),
                style_function=_block_style,
                tooltip=tooltip,
            ).add_to(fg_blocks)
            fg_blocks.add_to(fmap)

        if not g_streets.empty:
            streets_geo = g_streets.copy()

            def _street_style(feature: dict) -> dict[str, float | str]:
                street_type = str(feature["properties"].get("street_priority_class", "mixed_local"))
                return {
                    "color": _STREET_COLORS.get(street_type, "#6c757d"),
                    "weight": 1.6,
                    "opacity": 0.85,
                }

            street_fields = [name for name in ["street_priority_class"] if name in streets_geo.columns]
            tooltip = folium.GeoJsonTooltip(fields=street_fields) if street_fields else None
            fg_streets = folium.FeatureGroup(name="Street Priority", show=True)
            folium.GeoJson(
                data=json.loads(streets_geo.to_json()),
                style_function=_street_style,
                tooltip=tooltip,
            ).add_to(fg_streets)
            fg_streets.add_to(fmap)

        if not g_lines.empty:
            lines_geo = g_lines.copy()

            def _transit_style(feature: dict) -> dict[str, float | str]:
                mode = str(feature["properties"].get("type", "MetroLite"))
                return {"color": _TRANSIT_COLORS.get(mode, "#1d3557"), "weight": 3.0, "opacity": 0.9}

            line_fields = [name for name in ["line_id", "type", "headway_min"] if name in lines_geo.columns]
            tooltip = folium.GeoJsonTooltip(fields=line_fields) if line_fields else None
            fg_lines = folium.FeatureGroup(name="Transit Lines", show=True)
            folium.GeoJson(
                data=json.loads(lines_geo.to_json()),
                style_function=_transit_style,
                tooltip=tooltip,
            ).add_to(fg_lines)
            fg_lines.add_to(fmap)

        if not g_stops.empty:
            fg_stops = folium.FeatureGroup(name="Transit Stops", show=True)
            for _, row in g_stops.iterrows():
                geom = row.geometry.centroid if row.geometry is not None else None
                if geom is None:
                    continue
                popup_text = f"{row.get('line_id', 'line')} - {row.get('name', 'stop')}"
                folium.CircleMarker(
                    location=[float(geom.y), float(geom.x)],
                    radius=3,
                    color="#0d3b66",
                    fill=True,
                    fill_color="#0d3b66",
                    fill_opacity=0.9,
                    popup=popup_text,
                ).add_to(fg_stops)
            fg_stops.add_to(fmap)

        if not g_green.empty:
            fg_green = folium.FeatureGroup(name="Green Network", show=True)
            for _, row in g_green.head(2000).iterrows():
                geom = row.geometry.centroid if row.geometry is not None else None
                if geom is None:
                    continue
                popup_text = f"priority={float(row.get('priority_score', 0.0)):.2f}"
                folium.CircleMarker(
                    location=[float(geom.y), float(geom.x)],
                    radius=2.5,
                    color="#2a9d8f",
                    fill=True,
                    fill_color="#2a9d8f",
                    fill_opacity=0.75,
                    popup=popup_text,
                ).add_to(fg_green)
            fg_green.add_to(fmap)

        if not g_cells.empty:
            terrain = g_cells.copy()
            terrain["terrain_risk"] = np.clip(
                0.55 * _coerce_numeric(terrain, "slope_constraint_score", 0.0)
                + 0.45 * _coerce_numeric(terrain, "flood_risk_score", 0.0),
                0.0,
                1.0,
            )

            def _terrain_style(feature: dict) -> dict[str, float | str]:
                risk = float(feature["properties"].get("terrain_risk", 0.0))
                if risk < 0.33:
                    color = "#e5e5e5"
                elif risk < 0.66:
                    color = "#bdbdbd"
                else:
                    color = "#737373"
                return {"color": "#ffffff", "weight": 0.1, "fillColor": color, "fillOpacity": 0.22}

            fg_terrain = folium.FeatureGroup(name="Terrain Risk", show=False)
            folium.GeoJson(
                data=json.loads(terrain.to_json()),
                style_function=_terrain_style,
            ).add_to(fg_terrain)
            fg_terrain.add_to(fmap)

            bounds = g_cells.total_bounds
            if np.isfinite(bounds).all():
                fmap.fit_bounds([[float(bounds[1]), float(bounds[0])], [float(bounds[3]), float(bounds[2])]])

        folium.LayerControl(collapsed=False).add_to(fmap)
        fmap.save(str(out_html))
    except Exception:
        html = """<!doctype html><html><head><meta charset='utf-8'><title>CivicMorph Map</title></head>
<body><h1>CivicMorph Interactive Map</h1>
<p>Fallback renderer generated this page because folium/geopandas is unavailable.</p>
<ul>
<li>Cells: {cells}</li>
<li>Transit lines: {lines}</li>
<li>Transit stops: {stops}</li>
<li>Green network points: {green}</li>
<li>Blocks: {blocks}</li>
<li>Street segments: {streets}</li>
</ul>
</body></html>
""".format(
            cells=len(cells),
            lines=len(lines),
            stops=len(stops),
            green=len(green),
            blocks=len(blocks),
            streets=len(streets),
        )
        out_html.write_text(html)

    return out_html

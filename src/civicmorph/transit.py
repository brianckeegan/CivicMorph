"""Synthetic transit generation for CivicMorph."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

TRANSIT_DEFAULTS = {
    "BRT": {"speed_kmh": 25.0, "headway_min": 6.0, "stop_spacing_m": 600.0},
    "Tram": {"speed_kmh": 20.0, "headway_min": 8.0, "stop_spacing_m": 500.0},
    "MetroLite": {"speed_kmh": 35.0, "headway_min": 5.0, "stop_spacing_m": 900.0},
}


def _choose_type(mix: str, idx: int) -> str:
    """Choose a transit mode for a synthetic corridor.

    Parameters
    ----------
    mix : str
        Transit type mix selector.
    idx : int
        Corridor index within a member.

    Returns
    -------
    str
        Transit mode label.
    """

    if mix == "brt_bias":
        return "BRT" if idx % 2 == 0 else "Tram"
    if mix == "tram_bias":
        return "Tram" if idx % 2 == 0 else "BRT"
    if mix == "metro_bias":
        return "MetroLite" if idx % 2 == 0 else "BRT"
    return ["BRT", "Tram", "MetroLite"][idx % 3]


def generate_transit(
    cells: pd.DataFrame,
    member_id: int,
    params: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build abstract transit lines and stops with cross/ring guarantee.

    Parameters
    ----------
    cells : pandas.DataFrame
        Cell-level overlays for one ensemble member.
    member_id : int
        Ensemble member identifier.
    params : dict of str to Any
        Sampled parameters including stop spacing jitter and mode mix.

    Returns
    -------
    tuple of pandas.DataFrame
        Line dataframe and stop dataframe.
    """

    max_x = int(cells["x"].max())
    max_y = int(cells["y"].max())

    # Cross pattern by default when geometry supports at least a 5x5 grid.
    supports_cross = max_x >= 5 and max_y >= 5

    line_specs: list[dict[str, Any]] = []
    if supports_cross:
        line_specs.extend(
            [
                {
                    "line_id": f"l_{member_id:03d}_x",
                    "points": [(0, max_y // 2), (max_x, max_y // 2)],
                    "pattern": "cross",
                },
                {
                    "line_id": f"l_{member_id:03d}_y",
                    "points": [(max_x // 2, 0), (max_x // 2, max_y)],
                    "pattern": "cross",
                },
            ]
        )
    else:
        line_specs.append(
            {
                "line_id": f"l_{member_id:03d}_ring",
                "points": [(0, 0), (max_x, 0), (max_x, max_y), (0, max_y), (0, 0)],
                "pattern": "ring",
            }
        )

    jitter = float(params["stop_spacing_jitter"])
    mix = str(params["transit_type_mix"])

    line_rows: list[dict[str, Any]] = []
    stop_rows: list[dict[str, Any]] = []
    for idx, spec in enumerate(line_specs):
        transit_type = _choose_type(mix, idx)
        defaults = TRANSIT_DEFAULTS[transit_type]
        spacing = defaults["stop_spacing_m"] * (1 + jitter)
        spacing = float(np.clip(spacing, 350.0, 1100.0))

        line_rows.append(
            {
                "line_id": spec["line_id"],
                "member_id": member_id,
                "type": transit_type,
                "headway_min": defaults["headway_min"],
                "speed_kmh": defaults["speed_kmh"],
                "stop_spacing_m": spacing,
                "pattern": spec["pattern"],
                "geometry_wkt": "LINESTRING(" + ", ".join(f"{x*100} {y*100}" for x, y in spec["points"]) + ")",
            }
        )

        stop_count = max(2, int((max(max_x, max_y) * 100) / spacing))
        for stop_idx in range(stop_count):
            t = stop_idx / max(1, stop_count - 1)
            x0, y0 = spec["points"][0]
            x1, y1 = spec["points"][-1]
            sx = int(round((1 - t) * x0 + t * x1))
            sy = int(round((1 - t) * y0 + t * y1))
            stop_rows.append(
                {
                    "stop_id": f"s_{spec['line_id']}_{stop_idx:02d}",
                    "line_id": spec["line_id"],
                    "member_id": member_id,
                    "name": f"Stop {stop_idx + 1}",
                    "x": sx,
                    "y": sy,
                    "geometry_wkt": f"POINT({sx*100} {sy*100})",
                }
            )

    return pd.DataFrame(line_rows), pd.DataFrame(stop_rows)

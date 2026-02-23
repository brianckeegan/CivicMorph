"""I/O helpers for artifact persistence."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


def ensure_dir(path: Path) -> Path:
    """Ensure a directory exists.

    Parameters
    ----------
    path : Path
        Directory path to create if missing.

    Returns
    -------
    Path
        The same directory path for fluent chaining.
    """

    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_project_dir(project_dir: str | Path | None, create_if_missing: bool) -> Path:
    """Resolve a CivicMorph run directory.

    Parameters
    ----------
    project_dir : str or Path or None
        Explicit run directory. If ``None``, the resolver either creates a new run
        directory (when ``create_if_missing`` is ``True``) or selects the latest
        existing run under ``runs/``.
    create_if_missing : bool
        Whether to create a new directory when one is not explicitly provided.

    Returns
    -------
    Path
        Resolved run directory path.

    Raises
    ------
    FileNotFoundError
        Raised when no directory can be resolved in read-only mode.
    """

    if project_dir is not None:
        path = Path(project_dir)
        if create_if_missing:
            path.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            raise FileNotFoundError(f"Project directory does not exist: {path}")
        return path

    runs_root = Path("runs")
    if create_if_missing:
        run_id = datetime.utcnow().strftime("run_%Y%m%d_%H%M%S")
        path = runs_root / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    if not runs_root.exists():
        raise FileNotFoundError("No runs directory found. Run build-baseline first.")

    candidates = sorted([p for p in runs_root.iterdir() if p.is_dir()], key=lambda p: p.name)
    if not candidates:
        raise FileNotFoundError("No run directories found. Run build-baseline first.")
    return candidates[-1]


def write_dataframe(df: pd.DataFrame, path: Path) -> Path:
    """Write a dataframe with format-aware fallbacks.

    Parameters
    ----------
    df : pandas.DataFrame
        Table to persist.
    path : Path
        Target path. Suffix controls serialization behavior.

    Returns
    -------
    Path
        Original requested path. If fallback serialization is used, a sidecar metadata
        file is emitted next to ``path``.
    """

    ensure_dir(path.parent)
    if path.suffix == ".parquet":
        try:
            df.to_parquet(path, index=False)
            return path
        except Exception:
            fallback = path.with_name(path.name + ".csv")
            df.to_csv(fallback, index=False)
            sidecar = path.with_suffix(path.suffix + ".meta.json")
            sidecar.write_text(json.dumps({"fallback": fallback.name}, indent=2))
            return path

    if path.suffix in {".gpkg", ".graphml"}:
        fallback = path.with_name(path.name + ".csv")
        df.to_csv(fallback, index=False)
        sidecar = path.with_suffix(path.suffix + ".meta.json")
        sidecar.write_text(json.dumps({"fallback": fallback.name}, indent=2))
        return path

    if path.suffix == ".json":
        path.write_text(df.to_json(orient="records", indent=2))
        return path

    df.to_csv(path, index=False)
    return path


def read_dataframe(path: Path) -> pd.DataFrame:
    """Read a dataframe from primary or fallback artifacts.

    Parameters
    ----------
    path : Path
        Requested table path.

    Returns
    -------
    pandas.DataFrame
        Loaded dataframe from the primary artifact or fallback sidecar target.

    Raises
    ------
    FileNotFoundError
        Raised when neither primary nor fallback artifacts are available.
    """

    if path.suffix == ".parquet":
        if path.exists():
            try:
                return pd.read_parquet(path)
            except Exception:
                pass
        sidecar = path.with_suffix(path.suffix + ".meta.json")
        if sidecar.exists():
            payload = json.loads(sidecar.read_text())
            fallback = path.parent / payload["fallback"]
            return pd.read_csv(fallback)
        fallback = path.with_name(path.name + ".csv")
        if fallback.exists():
            return pd.read_csv(fallback)
        raise FileNotFoundError(f"Could not read dataframe at {path}")

    if path.suffix in {".gpkg", ".graphml"}:
        sidecar = path.with_suffix(path.suffix + ".meta.json")
        if sidecar.exists():
            payload = json.loads(sidecar.read_text())
            fallback = path.parent / payload["fallback"]
            return pd.read_csv(fallback)
        fallback = path.with_name(path.name + ".csv")
        if fallback.exists():
            return pd.read_csv(fallback)
        raise FileNotFoundError(f"Could not read sidecar fallback for {path}")

    if path.suffix == ".json":
        return pd.read_json(path)

    return pd.read_csv(path)


def write_json(payload: dict[str, Any] | list[Any], path: Path) -> Path:
    """Write a JSON payload to disk.

    Parameters
    ----------
    payload : dict or list
        JSON-serializable data structure.
    path : Path
        Destination JSON file.

    Returns
    -------
    Path
        Path to the written file.
    """

    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def read_json(path: Path) -> Any:
    """Read a JSON payload from disk.

    Parameters
    ----------
    path : Path
        Source JSON file.

    Returns
    -------
    Any
        Decoded JSON object.
    """

    return json.loads(path.read_text())

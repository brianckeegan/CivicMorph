"""Optional dependency checks."""

from __future__ import annotations

from importlib import metadata

from .exceptions import OptionalDependencyError, UnsupportedIntegrationVersionError

GRAPH2CITY_MIN_MAJOR = 0
GRAPH2CITY_MAX_MAJOR = 99


def _parse_major(version: str) -> int:
    """Parse a major version integer from a version string.

    Parameters
    ----------
    version : str
        Version string.

    Returns
    -------
    int
        Major version integer or ``-1`` when parsing fails.
    """

    token = version.split(".", 1)[0]
    try:
        return int(token)
    except ValueError:
        return -1


def get_optional_version(package_name: str) -> str:
    """Return installed version for optional packages.

    Parameters
    ----------
    package_name : str
        Python distribution name.

    Returns
    -------
    str
        Installed package version.

    Raises
    ------
    OptionalDependencyError
        Raised when package is not installed.
    """
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError as exc:
        extra_hint = {
            "graph2city": "graph2city",
            "mesa": "abm",
        }.get(package_name, package_name)
        raise OptionalDependencyError(
            f"Optional dependency '{package_name}' is not installed. "
            f"Install with: pip install civicmorph[{extra_hint}]"
        ) from exc


def validate_graph2city_version() -> str:
    """Validate Graph2City availability and compatibility.

    Parameters
    ----------
    None

    Returns
    -------
    str
        Installed Graph2City version.

    Raises
    ------
    OptionalDependencyError
        Raised when Graph2City is missing.
    UnsupportedIntegrationVersionError
        Raised when installed Graph2City major version is out of supported range.
    """
    version = get_optional_version("graph2city")
    major = _parse_major(version)
    if major < GRAPH2CITY_MIN_MAJOR or major > GRAPH2CITY_MAX_MAJOR:
        raise UnsupportedIntegrationVersionError(
            "Unsupported graph2city version "
            f"{version}. Supported major versions: "
            f"{GRAPH2CITY_MIN_MAJOR}..{GRAPH2CITY_MAX_MAJOR}."
        )
    return version


def validate_mesa_version() -> str:
    """Validate Mesa availability for ABM scoring.

    Parameters
    ----------
    None

    Returns
    -------
    str
        Installed Mesa version.

    Raises
    ------
    OptionalDependencyError
        Raised when Mesa is missing.
    """
    return get_optional_version("mesa")

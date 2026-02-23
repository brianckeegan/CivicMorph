"""Custom exception classes for CivicMorph."""


class CivicMorphError(Exception):
    """Base exception class for CivicMorph."""


class OptionalDependencyError(CivicMorphError):
    """Raised when an optional framework dependency is required but missing."""


class UnsupportedIntegrationVersionError(CivicMorphError):
    """Raised when an external integration version is unsupported."""

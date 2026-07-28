from __future__ import annotations

from aipet.platforms.contracts import (
    PlatformNotImplementedError,
    PlatformRuntime,
)


def create_runtime() -> PlatformRuntime:
    """Placeholder entrypoint for the future macOS platform adapter."""

    raise PlatformNotImplementedError(
        "The macOS platform adapter has not been implemented yet. "
        "Implement the contracts in aipet.platforms.contracts without "
        "changing shared core modules."
    )


__all__ = ["create_runtime"]

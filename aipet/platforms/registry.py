from __future__ import annotations

import sys
from functools import lru_cache

from aipet.platforms.contracts import (
    PlatformNotImplementedError,
    PlatformRuntime,
)


@lru_cache(maxsize=1)
def get_platform_runtime() -> PlatformRuntime:
    """Return the single platform runtime selected for this process."""

    if sys.platform == "win32":
        from aipet.platforms.windows import create_runtime

        return create_runtime()
    if sys.platform == "darwin":
        from aipet.platforms.macos import create_runtime

        return create_runtime()
    raise PlatformNotImplementedError(
        f"AIpet does not have a platform adapter for {sys.platform!r}."
    )


def reset_platform_runtime_for_tests() -> None:
    """Clear the process runtime singleton for tests that patch sys.platform."""

    get_platform_runtime.cache_clear()

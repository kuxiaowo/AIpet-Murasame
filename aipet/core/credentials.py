"""Platform-neutral secure credential facade."""

from __future__ import annotations

from aipet.platforms import CredentialError, get_platform_runtime


def protect_secret(secret: str) -> str:
    return get_platform_runtime().credentials.protect(secret)


def unprotect_secret(token: str) -> str:
    return get_platform_runtime().credentials.unprotect(token)


__all__ = ["CredentialError", "protect_secret", "unprotect_secret"]

from __future__ import annotations

import base64
import ctypes
import os
import subprocess
import sys
from ctypes import wintypes


class CredentialError(RuntimeError):
    pass


KEYCHAIN_SERVICE = "AIpet-Murasame AutoDL TTS"
KEYCHAIN_ACCOUNT = "AutoDL"


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _windows_apis():
    crypt32 = ctypes.WinDLL("Crypt32.dll", use_last_error=True)
    kernel32 = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
    blob_pointer = ctypes.POINTER(_DataBlob)
    crypt32.CryptProtectData.argtypes = [
        blob_pointer,
        wintypes.LPCWSTR,
        blob_pointer,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        blob_pointer,
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [
        blob_pointer,
        ctypes.POINTER(wintypes.LPWSTR),
        blob_pointer,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        blob_pointer,
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    return crypt32, kernel32


def protect_secret(secret: str) -> str:
    """Store a secret with the current operating system's credential service."""

    if not secret:
        return ""
    if sys.platform == "darwin":
        try:
            subprocess.run(
                [
                    "/usr/bin/security",
                    "add-generic-password",
                    "-U",
                    "-a",
                    KEYCHAIN_ACCOUNT,
                    "-s",
                    KEYCHAIN_SERVICE,
                    "-w",
                    secret,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise CredentialError(
                "macOS could not save the AutoDL password in Keychain."
            ) from exc
        return f"keychain:{KEYCHAIN_ACCOUNT}"
    if os.name != "nt":
        raise CredentialError(
            "Secure AutoDL password storage is unavailable on this system."
        )

    raw = secret.encode("utf-8")
    buffer = ctypes.create_string_buffer(raw)
    source = _DataBlob(
        len(raw),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)),
    )
    protected = _DataBlob()
    crypt32, kernel32 = _windows_apis()
    if not crypt32.CryptProtectData(
        ctypes.byref(source),
        "AIpet AutoDL TTS",
        None,
        None,
        None,
        0x1,
        ctypes.byref(protected),
    ):
        raise CredentialError(
            f"Windows could not encrypt the AutoDL password "
            f"(error {ctypes.get_last_error()})."
        )
    try:
        encrypted = ctypes.string_at(protected.pbData, protected.cbData)
        return base64.b64encode(encrypted).decode("ascii")
    finally:
        kernel32.LocalFree(protected.pbData)


def unprotect_secret(token: str) -> str:
    """Read a secret from the current operating system's credential service."""

    if not token:
        return ""
    if sys.platform == "darwin":
        if token != f"keychain:{KEYCHAIN_ACCOUNT}":
            raise CredentialError("The stored AutoDL password is invalid.")
        try:
            result = subprocess.run(
                [
                    "/usr/bin/security",
                    "find-generic-password",
                    "-a",
                    KEYCHAIN_ACCOUNT,
                    "-s",
                    KEYCHAIN_SERVICE,
                    "-w",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise CredentialError(
                "macOS could not read the AutoDL password from Keychain."
            ) from exc
        return result.stdout.rstrip("\n")
    if os.name != "nt":
        raise CredentialError(
            "Secure AutoDL password storage is unavailable on this system."
        )
    try:
        encrypted = base64.b64decode(token, validate=True)
    except (ValueError, TypeError) as exc:
        raise CredentialError("The stored AutoDL password is invalid.") from exc

    buffer = ctypes.create_string_buffer(encrypted)
    source = _DataBlob(
        len(encrypted),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)),
    )
    clear = _DataBlob()
    crypt32, kernel32 = _windows_apis()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source),
        None,
        None,
        None,
        None,
        0x1,
        ctypes.byref(clear),
    ):
        raise CredentialError(
            f"Windows could not decrypt the AutoDL password "
            f"(error {ctypes.get_last_error()})."
        )
    try:
        raw = ctypes.string_at(clear.pbData, clear.cbData)
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CredentialError("The stored AutoDL password is invalid.") from exc
    finally:
        kernel32.LocalFree(clear.pbData)

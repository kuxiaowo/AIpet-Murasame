from __future__ import annotations

import base64
import ctypes
import os
from ctypes import wintypes


class CredentialError(RuntimeError):
    pass


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
    """Encrypt a secret for the current Windows user with DPAPI."""

    if not secret:
        return ""
    if os.name != "nt":
        raise CredentialError(
            "AutoDL password storage is available only on Windows."
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
    """Decrypt a DPAPI token created for the current Windows user."""

    if not token:
        return ""
    if os.name != "nt":
        raise CredentialError(
            "AutoDL password storage is available only on Windows."
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

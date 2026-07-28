"""macOS Keychain credential storage."""

from __future__ import annotations

import ctypes
import ctypes.util

from aipet.platforms.contracts import CredentialError


_SERVICE = b"AIpet-Murasame"
_ACCOUNT = b"AutoDL TTS"
_TOKEN = "macos-keychain:autodl"
_ITEM_NOT_FOUND = -25300


class KeychainStore:
    def __init__(self) -> None:
        security_path = ctypes.util.find_library("Security")
        core_foundation_path = ctypes.util.find_library("CoreFoundation")
        if not security_path or not core_foundation_path:
            raise CredentialError("macOS Keychain is unavailable.")
        self._security = ctypes.CDLL(security_path)
        self._core_foundation = ctypes.CDLL(core_foundation_path)
        self._configure_apis()

    def _configure_apis(self) -> None:
        self._security.SecKeychainFindGenericPassword.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self._security.SecKeychainFindGenericPassword.restype = ctypes.c_int32
        self._security.SecKeychainAddGenericPassword.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self._security.SecKeychainAddGenericPassword.restype = ctypes.c_int32
        self._security.SecKeychainItemModifyAttributesAndData.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        self._security.SecKeychainItemModifyAttributesAndData.restype = (
            ctypes.c_int32
        )
        self._security.SecKeychainItemFreeContent.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self._security.SecKeychainItemFreeContent.restype = ctypes.c_int32
        self._core_foundation.CFRelease.argtypes = [ctypes.c_void_p]

    def protect(self, secret: str) -> str:
        if not secret:
            return ""
        raw = secret.encode("utf-8")
        item = ctypes.c_void_p()
        status = self._find(item=item)
        if status == 0:
            try:
                status = self._security.SecKeychainItemModifyAttributesAndData(
                    item,
                    None,
                    len(raw),
                    ctypes.c_char_p(raw),
                )
            finally:
                self._core_foundation.CFRelease(item)
        elif status == _ITEM_NOT_FOUND:
            status = self._security.SecKeychainAddGenericPassword(
                None,
                len(_SERVICE),
                _SERVICE,
                len(_ACCOUNT),
                _ACCOUNT,
                len(raw),
                ctypes.c_char_p(raw),
                None,
            )
        if status != 0:
            raise CredentialError(
                f"macOS Keychain could not store the password "
                f"(status {status})."
            )
        return _TOKEN

    def unprotect(self, token: str) -> str:
        if not token:
            return ""
        if token != _TOKEN:
            raise CredentialError("The stored macOS Keychain token is invalid.")
        length = ctypes.c_uint32()
        data = ctypes.c_void_p()
        status = self._find(length=length, data=data)
        if status != 0:
            raise CredentialError(
                f"macOS Keychain could not read the password "
                f"(status {status})."
            )
        try:
            return ctypes.string_at(data, length.value).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CredentialError(
                "The stored macOS Keychain password is invalid."
            ) from exc
        finally:
            self._security.SecKeychainItemFreeContent(None, data)

    def _find(
        self,
        *,
        length: ctypes.c_uint32 | None = None,
        data: ctypes.c_void_p | None = None,
        item: ctypes.c_void_p | None = None,
    ) -> int:
        return self._security.SecKeychainFindGenericPassword(
            None,
            len(_SERVICE),
            _SERVICE,
            len(_ACCOUNT),
            _ACCOUNT,
            ctypes.byref(length) if length is not None else None,
            ctypes.byref(data) if data is not None else None,
            ctypes.byref(item) if item is not None else None,
        )


__all__ = ["KeychainStore"]

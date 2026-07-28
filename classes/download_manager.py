"""Compatibility alias for :mod:`aipet.core.download_manager`."""

from __future__ import annotations

import sys

from aipet.core import download_manager as _implementation

sys.modules[__name__] = _implementation

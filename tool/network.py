"""Compatibility alias for :mod:`aipet.core.network`."""

from __future__ import annotations

import sys

from aipet.core import network as _implementation

sys.modules[__name__] = _implementation

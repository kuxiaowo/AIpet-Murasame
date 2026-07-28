"""Compatibility alias for :mod:`aipet.core.storage`."""

from __future__ import annotations

import sys

from aipet.core import storage as _implementation

sys.modules[__name__] = _implementation

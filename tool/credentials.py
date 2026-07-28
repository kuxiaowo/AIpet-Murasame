"""Compatibility alias for :mod:`aipet.core.credentials`."""

from __future__ import annotations

import sys

from aipet.core import credentials as _implementation

sys.modules[__name__] = _implementation

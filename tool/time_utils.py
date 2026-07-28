"""Compatibility alias for :mod:`aipet.core.time_utils`."""

from __future__ import annotations

import sys

from aipet.core import time_utils as _implementation

sys.modules[__name__] = _implementation

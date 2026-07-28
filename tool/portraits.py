"""Compatibility alias for :mod:`aipet.core.portraits`."""

from __future__ import annotations

import sys

from aipet.core import portraits as _implementation

sys.modules[__name__] = _implementation

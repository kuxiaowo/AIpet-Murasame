"""AIpet executable entrypoint and legacy module alias."""

from __future__ import annotations

import sys

from aipet import application as _application


if __name__ == "__main__":
    special_mode_result = _application.run_special_mode()
    raise SystemExit(
        _application.main()
        if special_mode_result is None
        else special_mode_result
    )

sys.modules[__name__] = _application

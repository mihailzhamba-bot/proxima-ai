"""Точка входа: python -m proxima_control_plane.norm run --tenant <tenant>."""

from __future__ import annotations

import sys

from proxima_control_plane.norm.cli import main

if __name__ == "__main__":
    sys.exit(main())

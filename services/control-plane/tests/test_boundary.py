import sys

import proxima_control_plane


def test_control_plane_requires_locked_python_runtime() -> None:
    assert sys.version_info[:2] == (3, 14)


def test_control_plane_has_no_collector_runtime() -> None:
    assert proxima_control_plane.__version__ == "0.1.0"
    assert not hasattr(proxima_control_plane, "collect")

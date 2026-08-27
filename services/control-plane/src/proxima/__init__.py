"""PROXIMA AI Manager.

Read-only анализ WB, детерминированный workflow, внутренний кабинет Account Manager.
Границы и запреты: `.planning/PROJECT.md`, `.planning/SECURITY.md`.
"""

from __future__ import annotations

__version__ = "0.1.0"

# Версия кода workflow. Входит в идентичность идемпотентности цикла
# (client_id + snapshot_id + scenario_set + workflow_version) по 03-01-PLAN.
# Это версия кода, не бизнес-политики: пороги и формулы живут в Client Passport.
WORKFLOW_VERSION = "0.1.0-dev"

__all__ = ["WORKFLOW_VERSION", "__version__"]

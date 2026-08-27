"""SCN-001 sales-drop detector core (pure, deterministic, no I/O)."""

from proxima_control_plane.detectors.scn001.baseline import (
    expected,
    history_status,
    weekday_index,
)
from proxima_control_plane.detectors.scn001.clock import MOSCOW_TZ, default_evaluation_date
from proxima_control_plane.detectors.scn001.config import (
    GlobalThresholdSource,
    Scn001Config,
    ThresholdSource,
    default_config,
)
from proxima_control_plane.detectors.scn001.decomposition import Contributions, decompose
from proxima_control_plane.detectors.scn001.metrics import DailyMetrics, MetricBundle
from proxima_control_plane.detectors.scn001.signal import (
    LEVEL_CABINET,
    LEVEL_SKU,
    REASON_INVALID_BASELINE,
    REASON_INVALID_INPUT,
    REASON_INSUFFICIENT_HISTORY,
    REVENUE_METHOD,
    SCENARIO_CODE,
    TRUST_MARKING,
    BlockedEntry,
    DedupEntry,
    FactorSnapshot,
    MoneyDelta,
    RunCounters,
    Scn001RunResult,
    Scn001Signal,
    SignalContext,
    canonical_hash,
    detect,
)

__all__ = [
    "BlockedEntry",
    "Contributions",
    "DailyMetrics",
    "DedupEntry",
    "FactorSnapshot",
    "GlobalThresholdSource",
    "LEVEL_CABINET",
    "LEVEL_SKU",
    "MetricBundle",
    "MoneyDelta",
    "MOSCOW_TZ",
    "REASON_INVALID_BASELINE",
    "REASON_INVALID_INPUT",
    "REASON_INSUFFICIENT_HISTORY",
    "REVENUE_METHOD",
    "RunCounters",
    "SCENARIO_CODE",
    "Scn001Config",
    "Scn001RunResult",
    "Scn001Signal",
    "SignalContext",
    "ThresholdSource",
    "TRUST_MARKING",
    "canonical_hash",
    "default_config",
    "default_evaluation_date",
    "decompose",
    "detect",
    "expected",
    "history_status",
    "weekday_index",
]

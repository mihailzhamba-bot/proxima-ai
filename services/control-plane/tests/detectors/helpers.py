from datetime import date, timedelta
from decimal import Decimal

from proxima_control_plane.detectors.scn001.config import (
    GlobalThresholdSource,
    default_config,
)
from proxima_control_plane.detectors.scn001.metrics import DailyMetrics, MetricBundle
from proxima_control_plane.detectors.scn001.signal import detect


def synth_row(sku, day, orders, open_card=200, aov=1000, buyouts=0):
    orders_d = Decimal(orders)
    aov_d = Decimal(aov)
    return DailyMetrics(
        sku=sku,
        date=day,
        orders=orders_d,
        open_card=Decimal(open_card),
        orders_sum_rub=orders_d * aov_d,
        buyouts=Decimal(buyouts),
    )


def synth_bundle(
    eval_date,
    specs,
    history_days=28,
    history_orders=Decimal("100"),
    history_open_card=Decimal("200"),
    history_aov=Decimal("1000"),
    history_orders_fn=None,
):
    rows = []
    for spec in specs:
        sku = spec["sku"]
        h_orders = spec.get("history_orders", history_orders)
        h_open = spec.get("history_open_card", history_open_card)
        h_aov = spec.get("history_aov", history_aov)
        for offset in range(history_days, 0, -1):
            orders = history_orders_fn(offset) if history_orders_fn is not None else h_orders
            rows.append(synth_row(sku, eval_date - timedelta(days=offset), orders, h_open, h_aov))
        rows.append(
            synth_row(
                sku,
                eval_date,
                spec.get("orders", h_orders),
                spec.get("open_card", h_open),
                spec.get("aov", h_aov),
            )
        )
    return MetricBundle.build(rows)


def run_detect(bundle, evaluation_date, source=None, dedup_state=()):
    config = default_config()
    return detect(
        bundle,
        config,
        source if source is not None else GlobalThresholdSource(config),
        dedup_state,
        evaluation_date=evaluation_date,
    )

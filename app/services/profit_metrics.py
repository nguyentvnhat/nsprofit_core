"""
Apply normalized profit configuration to SKU-level discount metrics rows.

Deterministic only — no formula interpreter. Unsupported modes are skipped with warnings.
Cost affects **metrics** (margin proxy bands), not the recommendation ranker directly.
"""

from __future__ import annotations

from typing import Any

from app.models.order import Order
from app.services.profit_configuration_normalizer import NormalizedProfitConfiguration


def _to_float(x: Any) -> float:
    try:
        return float(x or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _sku_key(sku: str, pname: str) -> tuple[str, str]:
    return ((sku or "UNKNOWN").strip() or "UNKNOWN", (pname or "").strip() or "Unnamed product")


def apply_profit_configuration_to_rows(
    orders: list[Order],
    rows: list[dict[str, Any]],
    cfg: NormalizedProfitConfiguration,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Returns enriched rows + applied_cost_components summary for meta/traceability.
    """
    # Local import avoids circular import with discount_recommendation.
    from app.services.discount_recommendation import _line_discount_amount, _margin_band
    if not rows or not any(
        (
            cfg.cogs.enabled,
            cfg.shipping_costs.enabled,
            cfg.transaction_fees.enabled,
            cfg.custom_costs.enabled,
        )
    ):
        out = []
        for r in rows:
            rr = dict(r)
            rr.setdefault("metrics_profit", {"profit_configuration_applied": False})
            out.append(rr)
        return out, {
            "cogs": False,
            "shipping_costs": False,
            "transaction_fees": False,
            "custom_costs": False,
            "notes": "no enabled profit groups",
        }

    # Index rows by SKU key for updates
    row_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        k = _sku_key(str(r.get("sku") or ""), str(r.get("product_name") or ""))
        row_by_key[k] = r

    total_pre = sum(
        max(0.0, _to_float(r.get("net_revenue")) + _to_float(r.get("line_discount_total"))) for r in rows
    )
    n_orders = max(1, len(orders))

    # Accumulators: cost in currency units per SKU key
    cogs_by_key: dict[tuple[str, str], float] = {k: 0.0 for k in row_by_key}
    ship_by_key: dict[tuple[str, str], float] = {k: 0.0 for k in row_by_key}
    fee_by_key: dict[tuple[str, str], float] = {k: 0.0 for k in row_by_key}
    custom_by_key: dict[tuple[str, str], float] = {k: 0.0 for k in row_by_key}

    applied = {
        "cogs": False,
        "shipping_costs": False,
        "transaction_fees": False,
        "custom_costs": False,
    }

    # --- COGS ---
    if cfg.cogs.enabled and cfg.cogs.mode not in ("none", "rules"):
        cogs_items = cfg.cogs.items
        if cfg.cogs.mode == "percentage":
            pct = _to_float((cogs_items[0] if cogs_items else {}).get("percentage_value"))
            if pct > 0:
                applied["cogs"] = True
                for k in row_by_key:
                    pre = _to_float(row_by_key[k].get("net_revenue")) + _to_float(
                        row_by_key[k].get("line_discount_total")
                    )
                    cogs_by_key[k] += pre * (pct / 100.0)
        elif cfg.cogs.mode in ("fixed", "per_product"):
            global_fixed = 0.0
            for it in cogs_items:
                ref_t = str(it.get("reference_type") or "").lower().strip()
                ref_v = str(it.get("reference_value") or "").strip()
                amt = _to_float(it.get("fixed_amount"))
                pct_i = _to_float(it.get("percentage_value"))
                if ref_t in ("sku", "product_id", "variant_id") and ref_v:
                    matched = [kk for kk in row_by_key if kk[0].lower() == ref_v.lower()]
                    for k in matched:
                        applied["cogs"] = True
                        pre = _to_float(row_by_key[k].get("net_revenue")) + _to_float(
                            row_by_key[k].get("line_discount_total")
                        )
                        if pct_i > 0:
                            cogs_by_key[k] += pre * (pct_i / 100.0)
                        elif amt > 0:
                            cogs_by_key[k] += amt
                else:
                    global_fixed += amt
            if global_fixed > 0 and total_pre > 0:
                applied["cogs"] = True
                for k in row_by_key:
                    pre = _to_float(row_by_key[k].get("net_revenue")) + _to_float(
                        row_by_key[k].get("line_discount_total")
                    )
                    cogs_by_key[k] += global_fixed * (pre / total_pre)

    # --- Shipping (fixed / by_order: flat per order) ---
    if cfg.shipping_costs.enabled and cfg.shipping_costs.mode in ("fixed", "by_order"):
        ship_items = cfg.shipping_costs.items
        per_order = _to_float((ship_items[0] if ship_items else {}).get("fixed_amount"))
        if per_order > 0 and total_pre > 0:
            applied["shipping_costs"] = True
            total_ship = per_order * n_orders
            for k in row_by_key:
                pre = _to_float(row_by_key[k].get("net_revenue")) + _to_float(
                    row_by_key[k].get("line_discount_total")
                )
                ship_by_key[k] += total_ship * (pre / total_pre)

    # --- Transaction fees (hybrid / percentage / fixed): per order then allocate ---
    if cfg.transaction_fees.enabled and cfg.transaction_fees.mode in (
        "fixed",
        "percentage",
        "hybrid",
    ):
        pct_fee = _to_float(
            (cfg.transaction_fees.items[0] if cfg.transaction_fees.items else {}).get("percentage_value")
        )
        fix_fee = _to_float(
            (cfg.transaction_fees.items[0] if cfg.transaction_fees.items else {}).get("fixed_amount")
        )
        if pct_fee > 0 or fix_fee > 0:
            applied["transaction_fees"] = True
            for o in orders:
                lines: list[tuple[tuple[str, str], float, float]] = []
                onet = 0.0
                for li in o.items or []:
                    sku = (li.sku or "UNKNOWN").strip() or "UNKNOWN"
                    pname = (li.product_name or "").strip() or "Unnamed product"
                    net = float(li.net_line_revenue or li.line_total or 0)
                    disc = _line_discount_amount(li)
                    pre = net + disc
                    kk = _sku_key(sku, pname)
                    if kk not in row_by_key:
                        continue
                    onet += net
                    lines.append((kk, net, pre))
                if onet <= 0 or not lines:
                    continue
                fee_o = onet * (pct_fee / 100.0) + fix_fee
                for kk, net, _pre in lines:
                    fee_by_key[kk] += fee_o * (net / onet)

    # --- Custom costs (fixed global pool) ---
    if cfg.custom_costs.enabled and cfg.custom_costs.mode == "fixed":
        amt = _to_float((cfg.custom_costs.items[0] if cfg.custom_costs.items else {}).get("fixed_amount"))
        if amt > 0 and total_pre > 0:
            applied["custom_costs"] = True
            total_custom = amt * n_orders
            for k in row_by_key:
                pre = _to_float(row_by_key[k].get("net_revenue")) + _to_float(
                    row_by_key[k].get("line_discount_total")
                )
                custom_by_key[k] += total_custom * (pre / total_pre)

    out_rows: list[dict[str, Any]] = []
    for r in rows:
        k = _sku_key(str(r.get("sku") or ""), str(r.get("product_name") or ""))
        pre = max(1e-9, _to_float(r.get("net_revenue")) + _to_float(r.get("line_discount_total")))
        retained = _to_float(r.get("value_retained_pct"))

        cogs = cogs_by_key.get(k, 0.0)
        ship = ship_by_key.get(k, 0.0)
        fee = fee_by_key.get(k, 0.0)
        cust = custom_by_key.get(k, 0.0)
        total_cost = cogs + ship + fee + cust
        cost_pct_of_list = min(100.0, max(0.0, (total_cost / pre) * 100.0))
        economic_retained = max(0.0, retained - cost_pct_of_list)

        low_m, high_m = _margin_band(economic_retained)
        rr = dict(r)
        rr["metrics_profit"] = {
            "profit_configuration_applied": True,
            "estimated_cost_pct_of_list": round(cost_pct_of_list, 3),
            "economic_value_retained_pct": round(economic_retained, 3),
            "cost_components_currency": {
                "cogs": round(cogs, 4),
                "shipping": round(ship, 4),
                "transaction_fees": round(fee, 4),
                "custom": round(cust, 4),
            },
        }
        # Metrics layer: expose config-aware margin band alongside legacy proxy (additive keys)
        rr["margin_proxy_low_pct_config"] = round(low_m, 1)
        rr["margin_proxy_high_pct_config"] = round(high_m, 1)
        out_rows.append(rr)

    return out_rows, applied

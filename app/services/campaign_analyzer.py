"""Orchestrate store metrics → signals → rules → narratives per campaign bucket (pure + in-memory)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.services.campaign_extractor import group_orders_by_campaign
from app.services.metrics_engine import metrics_as_flat_dict, run_all_metrics
from app.services.narrative_engine import narrate_all
from app.services.rules_engine import evaluate_rules
from app.services.signal_engine import run_all_signals, signal_codes


def _severity_to_priority(severity: str) -> str:
    s = (severity or "").strip().lower()
    if s in {"high", "critical", "warning"}:
        return "high"
    if s in {"medium", "moderate"}:
        return "medium"
    return "low"


def _risk_level_from_signals(signals: list[dict[str, Any]]) -> str:
    for s in signals:
        if str(s.get("severity") or "").lower() in {"high", "critical", "warning"}:
            return "high"
    for s in signals:
        if str(s.get("severity") or "").lower() in {"medium", "moderate"}:
            return "medium"
    return "low"


def _decimal_to_jsonable(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_jsonable(x) for x in obj]
    return obj


def _summary_from_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rev = metrics.get("revenue", {}) or {}
    gross = float(rev.get("gross_revenue") or 0.0)
    net = float(rev.get("net_revenue") or 0.0)
    d2g = float(rev.get("discount_to_gross_ratio") or 0.0)
    aov = float(rev.get("aov") or 0.0)
    return {
        "revenue": gross,
        "net_revenue": net,
        "discount_rate": d2g,
        "aov": aov,
    }


def _filter_customers_for_orders(
    customers: list[dict[str, Any]],
    order_emails: set[str],
) -> list[dict[str, Any]]:
    if not order_emails:
        return []
    out: list[dict[str, Any]] = []
    for c in customers:
        if not isinstance(c, dict):
            continue
        em = c.get("email")
        if em is not None and str(em).strip() in order_emails:
            out.append(c)
    return out


def analyze_campaigns(
    orders: list[dict[str, Any]],
    order_items: list[dict[str, Any]],
    customers: list[dict[str, Any]],
    *,
    max_campaigns: int | None = 100,
) -> list[dict[str, Any]]:
    """
    Run the existing metrics → signals → rules → narrative stack once per campaign key.

    No database writes. Campaigns are ordered by order count (desc); optional cap for safety.
    """
    if not orders:
        return []

    grouped = group_orders_by_campaign(orders)
    ranked = sorted(grouped.items(), key=lambda kv: len(kv[1]), reverse=True)
    if max_campaigns is not None and max_campaigns > 0:
        ranked = ranked[:max_campaigns]

    results: list[dict[str, Any]] = []
    for campaign_key, c_orders in ranked:
        names = {str(o.get("order_name") or "") for o in c_orders if o.get("order_name")}
        names.discard("")

        c_items = [
            it
            for it in order_items
            if isinstance(it, dict) and str(it.get("order_name") or "") in names
        ]

        emails: set[str] = set()
        for o in c_orders:
            ce = o.get("customer_email")
            if ce is not None and str(ce).strip():
                emails.add(str(ce).strip())

        c_customers = _filter_customers_for_orders(customers, emails)

        metrics = run_all_metrics(orders=c_orders, order_items=c_items, customers=c_customers)
        flat = metrics_as_flat_dict(metrics)
        sigs = run_all_signals(metrics)
        codes = signal_codes(sigs)
        payloads = evaluate_rules(flat, codes)
        narrated = narrate_all(payloads)

        insights_out: list[dict[str, Any]] = []
        for n in narrated:
            insights_out.append(
                {
                    "insight_code": n.rule_code,
                    "category": n.category,
                    "priority": _severity_to_priority(n.severity),
                    "title": n.title,
                    "summary": n.summary,
                    "implication": n.implication,
                    "action": n.action,
                }
            )

        signals_out: list[dict[str, Any]] = [dict(s) for s in sigs]
        risk = _risk_level_from_signals(signals_out)
        summary = _summary_from_metrics(metrics)
        summary["risk_level"] = risk

        results.append(
            {
                "campaign": campaign_key,
                "order_count": len(c_orders),
                "metrics": _decimal_to_jsonable(metrics),
                "signals": signals_out,
                "insights": insights_out,
                "summary": summary,
            }
        )

    return results


def campaign_summary_table_rows(campaign_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten ``analyze_campaigns`` output for tabular dashboards."""
    rows: list[dict[str, Any]] = []
    for r in campaign_results:
        if not isinstance(r, dict):
            continue
        s = r.get("summary") if isinstance(r.get("summary"), dict) else {}
        rows.append(
            {
                "campaign": r.get("campaign", "unknown"),
                "orders": int(r.get("order_count") or 0),
                "revenue": float(s.get("revenue") or 0.0),
                "net_revenue": float(s.get("net_revenue") or 0.0),
                "discount_rate": float(s.get("discount_rate") or 0.0),
                "aov": float(s.get("aov") or 0.0),
                "risk_level": str(s.get("risk_level") or "low"),
            }
        )
    return rows


def top_campaign_risks(
    campaign_results: list[dict[str, Any]],
    *,
    limit: int = 30,
    severities: tuple[str, ...] = ("high", "critical", "warning"),
) -> list[dict[str, Any]]:
    """High-severity signals with campaign label (newest / first-seen order preserved)."""
    out: list[dict[str, Any]] = []
    for r in campaign_results:
        if not isinstance(r, dict):
            continue
        camp = str(r.get("campaign") or "unknown")
        for s in r.get("signals") or []:
            if not isinstance(s, dict):
                continue
            if str(s.get("severity") or "").lower() not in severities:
                continue
            row = dict(s)
            row["campaign"] = camp
            out.append(row)
            if len(out) >= limit:
                return out
    return out


def top_campaign_insights(
    campaign_results: list[dict[str, Any]],
    *,
    limit: int = 30,
    priorities: tuple[str, ...] = ("high", "medium"),
) -> list[dict[str, Any]]:
    """Prioritized campaign insights with ``campaign`` column."""
    out: list[dict[str, Any]] = []
    for r in campaign_results:
        if not isinstance(r, dict):
            continue
        camp = str(r.get("campaign") or "unknown")
        for ins in r.get("insights") or []:
            if not isinstance(ins, dict):
                continue
            if str(ins.get("priority") or "").lower() not in priorities:
                continue
            row = dict(ins)
            row["campaign"] = camp
            out.append(row)
            if len(out) >= limit:
                return out
    return out

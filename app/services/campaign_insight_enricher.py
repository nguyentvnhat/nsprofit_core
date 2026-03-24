"""
Post-process campaign-level insights with deterministic impact estimates, scoring, and ranking.

Pure functions only — no I/O, no Streamlit, no changes to core engines.
"""

from __future__ import annotations

import math
import re
import statistics
from typing import Any

# --- Tunable proxies (deterministic, documented) ---
_TARGET_DISCOUNT_RATE = 0.15
_STACKED_DISCOUNT_CAP = 0.10
_TARGET_AOV = 65.0
_GROWTH_OPPORTUNITY_PCT = 0.03
_REFUND_FALLBACK_RATE = 0.02
_GROWTH_VOLATILITY_FALLBACK_PCT = 0.05
_BUNDLE_OPP_PCT = 0.03
_FREE_SHIP_OPP_PCT = 0.025

# When YAML rule parsing yields no signal codes (e.g. legacy session payloads), map rule → typical signal.
_INSIGHT_CODE_TO_SIGNAL_FALLBACK: dict[str, str] = {
    "discount_dependency_risk": "HIGH_DISCOUNT_DEPENDENCY_V2",
    "double_discounting_issue": "STACKED_DISCOUNTING",
    "low_quality_growth": "VOLUME_DRIVEN_GROWTH",
    "sku_concentration_risk": "HERO_SKU_CONCENTRATION",
    "aov_structure_issue": "LOW_ORDER_VALUE_PROBLEM",
    "free_shipping_optimization_opportunity": "FREE_SHIPPING_OPPORTUNITY",
    "channel_dependency_risk": "SOURCE_CONCENTRATION_RISK",
    "bundle_revenue_opportunity": "BUNDLE_OPPORTUNITY",
    "data_quality_issue": "DATA_HYGIENE_ISSUE",
    "revenue_instability": "UNSTABLE_GROWTH",
    "revenue_discount_dependency": "HIGH_DISCOUNT_DEPENDENCY",
    "revenue_low_aov": "LOW_AOV_PRESSURE",
    "risk_refund_rate_elevated": "ELEVATED_REFUND_RATE",
    "risk_free_shipping_overuse": "FREE_SHIPPING_HEAVY",
    "product_concentration": "HERO_SKU_CONCENTRATION",
    "product_discount_intensity": "HIGH_DISCOUNT_DEPENDENCY_V2",
}

# Primary signal_code → valuation channel (overrides title/category heuristics when present).
_SIGNAL_TO_VALUATION_KIND: dict[str, str] = {
    "STACKED_DISCOUNTING": "stacked_discount",
    "HIGH_DISCOUNT_DEPENDENCY_V2": "pricing",
    "HIGH_DISCOUNT_DEPENDENCY": "pricing",
    "PRODUCT_DISCOUNT_RATE_HIGH": "pricing",
    "LOW_ORDER_VALUE_PROBLEM": "aov_structure",
    "LOW_AOV_PRESSURE": "aov_structure",
    "UNSTABLE_GROWTH": "growth_volatility",
    "VOLUME_DRIVEN_GROWTH": "volume_driven_growth",
    "ELEVATED_REFUND_RATE": "refund",
    "SOURCE_CONCENTRATION_RISK": "concentration",
    "HERO_SKU_CONCENTRATION": "concentration",
    "SKU_QUANTITY_CONCENTRATION": "concentration",
    "TOP_CUSTOMER_CONCENTRATION_HIGH": "concentration",
    "DATA_HYGIENE_ISSUE": "data_hygiene",
    "BUNDLE_OPPORTUNITY": "bundle_opportunity",
    "FREE_SHIPPING_OPPORTUNITY": "free_shipping_opportunity",
    "FREE_SHIPPING_HEAVY": "free_shipping_heavy",
}


def _f(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(v):
        return default
    return v


def _norm_text(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _fmt_money_phrase(amount: float) -> str:
    """Compact USD phrase for narrative fields (no 'USD' suffix)."""
    v = max(_f(amount), 0.0)
    return f"${v:,.0f}"


def _resolve_campaign_money(
    summary: dict[str, Any],
    metrics: dict[str, Any],
    order_count: int,
) -> dict[str, float]:
    """
    Merge summary + nested revenue metrics.

    Many exports leave ``total_price`` empty while ``net_revenue`` is populated; gross-based
    summary alone would then be all zeros. We fall back to net and to discount/totals from
    the metrics engine so proxies and shares are non-degenerate.
    """
    rev_dom = _revenue_domain(metrics)
    g = max(_f(summary.get("revenue")), _f(rev_dom.get("gross_revenue")))
    n = max(_f(summary.get("net_revenue")), _f(rev_dom.get("net_revenue")))
    primary = g if g > 0 else n

    dr = max(_f(summary.get("discount_rate")), _f(rev_dom.get("discount_to_gross_ratio")))
    td = _f(rev_dom.get("total_discounts"))
    if dr <= 0 and td > 0:
        if g > 0:
            dr = min(td / g, 1.0)
        elif n > 0:
            dr = min(td / n, 1.0)

    aov = max(_f(summary.get("aov")), _f(rev_dom.get("aov")))
    oc = int(order_count) if int(order_count) > 0 else int(_f(rev_dom.get("total_orders")))

    return {
        "gross_revenue": g,
        "net_revenue": n,
        "primary_revenue": max(primary, 0.0),
        "discount_rate": max(dr, 0.0),
        "aov": max(aov, 0.0),
        "orders": max(oc, 0),
    }


def _total_primary_revenue_in_view(campaign_results: list[dict[str, Any]]) -> float:
    t = 0.0
    for r in campaign_results:
        if not isinstance(r, dict):
            continue
        summary = r.get("summary") if isinstance(r.get("summary"), dict) else {}
        metrics = r.get("metrics") if isinstance(r.get("metrics"), dict) else {}
        m = _resolve_campaign_money(summary, metrics, int(r.get("order_count") or 0))
        t += m["primary_revenue"]
    return max(t, 0.0)


def _advanced(metrics: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(metrics, dict):
        return {}
    adv = metrics.get("advanced")
    return adv if isinstance(adv, dict) else {}


def _revenue_domain(metrics: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(metrics, dict):
        return {}
    rev = metrics.get("revenue")
    return rev if isinstance(rev, dict) else {}


def _monthly_revenue_values(metrics: dict[str, Any]) -> list[float]:
    """Ordered not required; values are non-negative floats."""
    adv = _advanced(metrics)
    mr = adv.get("monthly_revenue")
    if not isinstance(mr, dict):
        return []
    out: list[float] = []
    for v in mr.values():
        fv = _f(v)
        if fv >= 0.0:
            out.append(fv)
    return out


def _revenue_volatility_ratio(metrics: dict[str, Any]) -> float | None:
    """std(monthly revenue) / mean(monthly revenue); None if not computable."""
    vals = _monthly_revenue_values(metrics)
    if len(vals) < 2:
        return None
    mean_m = statistics.mean(vals)
    if mean_m <= 0.0:
        return None
    sd = statistics.pstdev(vals)
    return sd / mean_m


def extract_rule_signal_codes(rule: dict[str, Any] | None) -> list[str]:
    """Collect ``signal_code`` values from nested rule ``condition`` blocks."""
    if not isinstance(rule, dict):
        return []
    cond = rule.get("condition")
    if not isinstance(cond, dict):
        return []

    out: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if str(node.get("type") or "").lower() == "signal":
                sc = node.get("signal_code")
                if sc is not None and str(sc).strip():
                    out.append(str(sc).strip())
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(cond)
    return out


def _infer_signal_code(insight: dict[str, Any], signals: list[dict[str, Any]]) -> str:
    """Pick a display signal: prefer rule-linked codes, then category match, else strongest severity."""
    rs = insight.get("rule_signal_codes")
    if isinstance(rs, list) and rs:
        return str(rs[0])

    ic = _norm_text(insight.get("insight_code")).replace(" ", "_")
    if ic in _INSIGHT_CODE_TO_SIGNAL_FALLBACK:
        return _INSIGHT_CODE_TO_SIGNAL_FALLBACK[ic]

    ins_cat = _norm_text(insight.get("category"))
    best: tuple[int, str] = (0, "")
    sev_rank = {"high": 3, "critical": 3, "warning": 3, "medium": 2, "moderate": 2, "low": 1}

    for s in signals:
        if not isinstance(s, dict):
            continue
        code = str(s.get("signal_code") or "")
        cat = _norm_text(s.get("category"))
        rank = sev_rank.get(_norm_text(s.get("severity")), 1)
        if ins_cat and cat and ins_cat == cat and rank >= best[0]:
            best = (rank, code)
    if best[1]:
        return best[1]

    for s in signals:
        if not isinstance(s, dict):
            continue
        code = str(s.get("signal_code") or "")
        rank = sev_rank.get(_norm_text(s.get("severity")), 1)
        if rank >= best[0]:
            best = (rank, code)
    return best[1]


def _valuation_kind_from_heuristic(insight: dict[str, Any]) -> str:
    """Map insight copy to a coarse valuation bucket when signal mapping is ambiguous."""
    code = _norm_text(insight.get("insight_code"))
    title = _norm_text(insight.get("title"))
    cat = _norm_text(insight.get("category"))
    blob = f"{code} {title} {cat}"

    if "double" in blob or "stack" in blob:
        return "stacked_discount"
    if "refund" in blob or "return" in blob:
        return "refund"
    if "unstable" in blob or "volatil" in blob or "revenue_instability" in code:
        return "growth_volatility"
    if "concentration" in blob or "channel" in blob or ("dependency" in blob and "discount" not in blob):
        return "concentration"
    if "hygiene" in blob or "data quality" in blob or ("sku" in blob and "blank" in blob):
        return "data_hygiene"
    if "growth" in blob and ("quality" in blob or "volume" in blob or "low_quality" in code):
        return "volume_driven_growth"
    if (
        "aov" in blob
        or "basket" in blob
        or "order value" in blob
        or "low order" in blob
        or "revenue_low_aov" in code
    ):
        return "aov_structure"
    if (
        "discount" in blob
        or "pricing" in cat
        or "markdown" in blob
        or "promo" in blob
        or "discount_dependency" in code
        or "product_discount" in code
    ):
        return "pricing"
    return "general"


def _resolve_valuation_kind(insight: dict[str, Any], signal_code: str) -> str:
    sc = (signal_code or "").strip().upper()
    if sc in _SIGNAL_TO_VALUATION_KIND:
        return _SIGNAL_TO_VALUATION_KIND[sc]
    return _valuation_kind_from_heuristic(insight)


def _severity_numeric(priority: str) -> float:
    p = _norm_text(priority)
    if p in {"high", "critical", "warning"}:
        return 25.0
    if p in {"medium", "moderate", "normal"}:
        return 15.0
    return 8.0


def _urgency_score(kind: str) -> float:
    if kind in {"pricing", "stacked_discount", "refund"}:
        return 10.0
    if kind in {"growth_volatility", "volume_driven_growth", "aov_structure", "growth_quality"}:
        return 7.0
    if kind == "concentration":
        return 6.0
    if kind in {"bundle_opportunity", "free_shipping_opportunity", "free_shipping_heavy"}:
        return 7.0
    if kind == "data_hygiene":
        return 4.0
    return 4.0


def _money_impact_score(impact_value: float, campaign_primary_revenue: float) -> float:
    """0–25 from (loss+opportunity) vs this bucket's primary revenue."""
    if impact_value <= 0.0:
        return 0.0
    denom = max(campaign_primary_revenue, 1.0)
    return min(25.0, (impact_value / denom) * 25.0)


def _concentration_priority_boost(kind: str, affected_share: float, primary: float) -> float:
    """Extra points for large-bucket concentration (spec: high priority when revenue is large)."""
    if kind != "concentration" or primary <= 0.0:
        return 0.0
    return min(20.0, affected_share * 55.0)


def _loss_and_opportunity(
    kind: str,
    *,
    revenue: float,
    discount_rate: float,
    orders: int,
    aov: float,
    metrics: dict[str, Any],
) -> tuple[float, float]:
    """Return (estimated_loss, opportunity_size) in currency proxy units."""
    rev = max(revenue, 0.0)
    dr = max(discount_rate, 0.0)
    rev_dom = _revenue_domain(metrics)

    loss = 0.0
    opp = 0.0

    if kind == "pricing":
        excess = max(dr - _TARGET_DISCOUNT_RATE, 0.0)
        loss = excess * rev
    elif kind == "stacked_discount":
        loss = rev * min(dr, _STACKED_DISCOUNT_CAP)
    elif kind == "aov_structure":
        gap = max(_TARGET_AOV - aov, 0.0)
        opp = gap * max(orders, 0)
    elif kind == "refund":
        # Spec D: use aggregate refunds when present; else safe % of revenue (no rate chain).
        tr = _f(rev_dom.get("total_refunds"))
        if tr > 0.0:
            loss = tr
        elif rev > 0.0:
            loss = rev * _REFUND_FALLBACK_RATE
    elif kind == "growth_volatility":
        vol = _revenue_volatility_ratio(metrics)
        if vol is not None and vol > 0.0:
            opp = vol * rev * 0.5
        elif rev > 0.0:
            opp = rev * _GROWTH_VOLATILITY_FALLBACK_PCT
        if opp <= 0.0 and rev > 0.0:
            opp = rev * _GROWTH_VOLATILITY_FALLBACK_PCT
    elif kind == "volume_driven_growth":
        if rev > 0.0:
            opp = rev * _GROWTH_OPPORTUNITY_PCT
    elif kind == "bundle_opportunity":
        if rev > 0.0:
            opp = rev * _BUNDLE_OPP_PCT
    elif kind == "free_shipping_opportunity":
        if rev > 0.0:
            opp = rev * _FREE_SHIP_OPP_PCT
    elif kind == "free_shipping_heavy":
        # Margin pressure proxy — safe loss without COGS.
        if rev > 0.0:
            loss = rev * 0.02
    elif kind == "concentration":
        pass
    elif kind == "data_hygiene":
        pass
    elif kind == "growth_quality":
        # Heuristic bucket: treat like volume-driven when signal data missing.
        if rev > 0.0:
            opp = rev * _GROWTH_OPPORTUNITY_PCT
    elif kind == "general":
        pass

    return max(loss, 0.0), max(opp, 0.0)


def _why_now_sentence(
    *,
    kind: str,
    affected_share: float,
    discount_rate: float,
    orders: int,
    aov: float,
    priority: str,
    revenue: float,
    total_view: float,
    estimated_loss: float,
    opportunity_size: float,
) -> str:
    """Operator style text: [Problem] [Impact] [Action]."""
    rev = max(revenue, 0.0)
    loss = max(estimated_loss, 0.0)
    opp = max(opportunity_size, 0.0)
    share_pct = affected_share * 100.0 if total_view > 0.0 else 0.0

    problem_prefix = (
        f"This campaign contributes {share_pct:.1f}% of revenue in view "
        f"(~{_fmt_money_phrase(rev)})."
        if total_view > 0.0
        else f"This campaign contributes ~{_fmt_money_phrase(rev)} in attributed revenue."
    )
    if kind == "pricing":
        problem = (
            f"Discount rate exceeds the {_TARGET_DISCOUNT_RATE * 100:.0f}% reference "
            f"({discount_rate * 100:.1f}% discount-to-revenue)."
            if discount_rate > _TARGET_DISCOUNT_RATE
            else "Discount rate is close to threshold and requires control."
        )
        action = "Action: tighten discount rules by campaign and cap promo depth."
    elif kind == "stacked_discount":
        problem = "Compare-at, line, and order discounts are stacking and cutting realized price."
        action = "Action: disable overlap between compare-at and order-level discounts."
    elif kind == "aov_structure":
        problem = (
            f"Order value structure is below the {_TARGET_AOV:.0f} AOV reference "
            f"({_f(aov):.2f} across {orders} orders)."
            if orders > 0
            else f"Order value structure is below the {_TARGET_AOV:.0f} AOV reference ({_f(aov):.2f})."
        )
        action = "Action: lift basket size with bundles and minimum-order thresholds."
    elif kind == "refund":
        problem = "Refund and return leakage is high in this campaign slice."
        action = "Action: audit top refunded SKUs and tighten return-prone offers."
    elif kind == "growth_volatility":
        problem = "Revenue swings month-to-month and planning accuracy drops."
        action = "Action: stabilize spend and promo cadence by week before scaling."
    elif kind == "volume_driven_growth":
        problem = "Revenue growth comes from more orders while basket value stays weak."
        action = "Action: increase AOV with bundles, threshold offers, or price architecture."
    elif kind == "concentration":
        problem = "Revenue is concentrated in a narrow source/SKU set."
        action = "Action: diversify channel mix and expand contribution of secondary SKUs."
    elif kind == "data_hygiene":
        problem = "SKU/title gaps in the feed block precise campaign diagnostics."
        action = "Action: fix missing SKU/title fields in the next export and rerun."
    elif kind in {"bundle_opportunity", "free_shipping_opportunity"}:
        problem = "Commercial levers for bundling or shipping thresholds are underused."
        action = "Action: launch bundle/threshold tests on this campaign and track AOV lift."
    elif kind == "free_shipping_heavy":
        problem = "Free-shipping usage is high against campaign revenue."
        action = "Action: raise threshold or gate free shipping to protect margin."
    elif kind == "general":
        problem = "This rule fired and requires operator review."
        action = "Action: validate promo setup, catalog mix, and source quality."
    else:
        problem = "This signal is active and needs immediate operational review."
        action = "Action: check campaign setup and apply the relevant playbook."

    if loss > 0.0 and opp > 0.0:
        impact = (
            f"Impact: ~{_fmt_money_phrase(loss)} at risk and "
            f"~{_fmt_money_phrase(opp)} in opportunity."
        )
    elif loss > 0.0:
        impact = f"Impact: ~{_fmt_money_phrase(loss)} at risk."
    elif opp > 0.0:
        impact = f"Impact: ~{_fmt_money_phrase(opp)} opportunity."
    else:
        impact = "Impact: no direct dollar proxy for this signal type."

    sev = _norm_text(priority)
    if sev in {"high", "critical", "warning"}:
        urgency = "Priority: high."
    elif sev in {"medium", "moderate", "normal"}:
        urgency = "Priority: medium."
    else:
        urgency = "Priority: low."

    return f"{problem_prefix} {problem} {impact} {urgency} {action}"


def _estimated_impact_text(
    *,
    kind: str,
    estimated_loss: float,
    opportunity_size: float,
) -> str:
    """Short dollar headline for cards and exports."""
    loss = max(estimated_loss, 0.0)
    opp = max(opportunity_size, 0.0)
    if loss > 0.0 and opp > 0.0:
        return (
            f"{_fmt_money_phrase(loss)} at risk; {_fmt_money_phrase(opp)} opportunity from operational levers"
        )
    if loss > 0.0:
        reasons = {
            "pricing": "pricing inefficiency",
            "stacked_discount": "stacked discount leakage",
            "refund": "refund and return leakage",
            "free_shipping_heavy": "free-shipping cost pressure",
            "general": "metric-driven leakage",
        }
        tag = reasons.get(kind, "margin leakage")
        return f"{_fmt_money_phrase(loss)} at risk due to {tag}"
    if opp > 0.0:
        reasons = {
            "aov_structure": "improving AOV",
            "growth_volatility": "stabilizing revenue volatility",
            "volume_driven_growth": "improving growth quality",
            "growth_quality": "improving growth quality",
            "bundle_opportunity": "bundle and cross-sell design",
            "free_shipping_opportunity": "shipping-threshold and AOV lift",
            "general": "operational upside",
        }
        tag = reasons.get(kind, "strategic follow-through")
        return f"{_fmt_money_phrase(opp)} opportunity from {tag}"
    if kind == "concentration":
        return "Concentration risk—prioritize diversification; no separate dollar proxy on this signal"
    if kind == "data_hygiene":
        return "Fix data gaps first; dollar impact not modeled until SKU attribution improves"
    return "No separate dollar proxy on this signal"


def enrich_campaign_insights(campaign_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Flatten per-campaign insights and attach impact estimates, scores, ranks, and ``why_now``.

    Safe on empty input, missing keys, or partial metrics.
    """
    if not campaign_results:
        return []

    total_view = _total_primary_revenue_in_view(campaign_results)
    enriched: list[dict[str, Any]] = []

    for block in campaign_results:
        if not isinstance(block, dict):
            continue
        campaign = str(block.get("campaign") or "unknown")
        summary = block.get("summary") if isinstance(block.get("summary"), dict) else {}
        metrics = block.get("metrics") if isinstance(block.get("metrics"), dict) else {}
        signals = [s for s in (block.get("signals") or []) if isinstance(s, dict)]
        insights = [i for i in (block.get("insights") or []) if isinstance(i, dict)]

        money = _resolve_campaign_money(summary, metrics, int(block.get("order_count") or 0))
        gross_r = money["gross_revenue"]
        net_revenue = money["net_revenue"]
        primary = money["primary_revenue"]
        discount_rate = money["discount_rate"]
        aov = money["aov"]
        orders = money["orders"]

        for ins in insights:
            sig_code = _infer_signal_code(ins, signals)
            kind = _resolve_valuation_kind(ins, sig_code)
            loss, opp = _loss_and_opportunity(
                kind,
                revenue=primary,
                discount_rate=discount_rate,
                orders=orders,
                aov=aov,
                metrics=metrics,
            )

            impacted = primary
            affected_share = (impacted / total_view) if total_view > 0.0 else 0.0

            rev_score = min(40.0, affected_share * 40.0)
            sev_score = _severity_numeric(str(ins.get("priority") or "low"))
            impact_value = loss + opp
            money_score = _money_impact_score(impact_value, primary)
            urg_score = _urgency_score(kind)
            conc_boost = _concentration_priority_boost(kind, affected_share, primary)

            priority_score = min(100.0, rev_score + sev_score + money_score + urg_score + conc_boost)

            why = _why_now_sentence(
                kind=kind,
                affected_share=affected_share,
                discount_rate=discount_rate,
                orders=orders,
                aov=aov,
                priority=str(ins.get("priority") or "low"),
                revenue=primary,
                total_view=total_view,
                estimated_loss=loss,
                opportunity_size=opp,
            )
            impact_txt = _estimated_impact_text(
                kind=kind,
                estimated_loss=loss,
                opportunity_size=opp,
            )

            row: dict[str, Any] = {
                "campaign": campaign,
                "title": str(ins.get("title") or ""),
                "summary": str(ins.get("summary") or ""),
                "implication": str(ins.get("implication") or ""),
                "action": str(ins.get("action") or ""),
                "priority": str(ins.get("priority") or "low"),
                "category": str(ins.get("category") or ""),
                "insight_code": str(ins.get("insight_code") or ""),
                "signal_code": sig_code,
                "revenue": round(gross_r if gross_r > 0 else primary, 2),
                "net_revenue": round(net_revenue, 2),
                "orders": orders,
                "aov": round(aov, 2),
                "discount_rate": round(discount_rate, 6),
                "impacted_revenue": round(impacted, 2),
                "estimated_loss": round(loss, 2),
                "opportunity_size": round(opp, 2),
                "affected_revenue_share": round(affected_share, 6),
                "priority_score": round(priority_score, 2),
                "rank": 0,
                "why_now": why,
                "estimated_impact_text": impact_txt,
                "_valuation_kind": kind,
            }
            enriched.append(row)

    def _rank_key(row: dict[str, Any]) -> tuple[float, float, float, str]:
        ps = _f(row.get("priority_score"))
        imp = _f(row.get("impacted_revenue"))
        dollars = _f(row.get("estimated_loss")) + _f(row.get("opportunity_size"))
        camp = str(row.get("campaign") or "")
        return (-ps, -dollars, -imp, camp)

    enriched.sort(key=_rank_key)
    for idx, row in enumerate(enriched, start=1):
        row["rank"] = idx
        row.pop("_valuation_kind", None)

    return enriched


def build_campaign_opportunity_summary(enriched: list[dict[str, Any]]) -> dict[str, Any]:
    """Roll up loss/opportunity totals and the top ranked row metadata."""
    total_loss = sum(_f(r.get("estimated_loss")) for r in enriched)
    total_opp = sum(_f(r.get("opportunity_size")) for r in enriched)
    top = enriched[0] if enriched else {}
    return {
        "total_estimated_loss": round(total_loss, 2),
        "total_opportunity_size": round(total_opp, 2),
        "top_priority_campaign": top.get("campaign"),
        "top_priority_title": top.get("title"),
        "insight_count": len(enriched),
    }


__all__ = [
    "build_campaign_opportunity_summary",
    "enrich_campaign_insights",
    "extract_rule_signal_codes",
]

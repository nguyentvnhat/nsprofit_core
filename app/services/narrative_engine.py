"""Deterministic narrative rendering from rule templates (no LLM)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.rules_engine import RuleInsightPayload


def _format_template(template: str, context: dict[str, Any]) -> str:
    """Safe deterministic formatter: unknown keys keep template unchanged."""
    try:
        return template.format(**context)
    except Exception:
        return template


@dataclass(frozen=True)
class NarratedInsight:
    rule_code: str
    category: str
    severity: str
    title: str
    summary: str
    implication: str
    action: str
    payload_json: dict[str, Any]


@dataclass(frozen=True)
class RuleInsightTemplate:
    title: str
    summary: str
    implication: str
    action: str
    priority: str


_PRIORITY_WEIGHT: dict[str, int] = {"high": 3, "medium": 2, "low": 1}

_RULE_INSIGHT_LIBRARY: dict[str, RuleInsightTemplate] = {
    "discount_dependency_risk": RuleInsightTemplate(
        title="Discount becoming default sales mechanism",
        summary="A large share of sales currently depends on discounting to convert.",
        implication="Margin resilience is reduced and revenue becomes sensitive to promo intensity.",
        action="Tighten discount depth by segment, protect hero SKUs from blanket promos, and test value-add offers.",
        priority="high",
    ),
    "double_discounting_issue": RuleInsightTemplate(
        title="Stacked discounts are eroding price realization",
        summary="Compare-at markdowns and order discounts are being applied together.",
        implication="Effective selling price drops faster than expected and margin leakage compounds.",
        action="Set discount guardrails to prevent stacking and enforce one primary promo mechanism per campaign.",
        priority="high",
    ),
    "low_quality_growth": RuleInsightTemplate(
        title="Revenue growth is driven by volume, not value",
        summary="Revenue is increasing while average order value is flat or declining.",
        implication="Growth quality weakens because more operational load is needed for the same gross profit progress.",
        action="Launch AOV lifts (bundles, threshold offers, upsell paths) and track mix shift weekly.",
        priority="high",
    ),
    "sku_concentration_risk": RuleInsightTemplate(
        title="Over-reliance on a single product",
        summary="One SKU contributes a disproportionate share of revenue.",
        implication="Any stock-out, demand dip, or pricing pressure on that SKU can materially impact total revenue.",
        action="Diversify with attach products, cross-sell flows, and dedicated campaigns for mid-tail SKUs.",
        priority="high",
    ),
    "aov_structure_issue": RuleInsightTemplate(
        title="Order value structure is limiting growth",
        summary="A large portion of orders sits in low-value baskets.",
        implication="Customer acquisition spend becomes harder to recover and shipping economics deteriorate.",
        action="Increase basket architecture with bundle ladders, minimum-spend perks, and targeted post-add recommendations.",
        priority="high",
    ),
    "free_shipping_optimization_opportunity": RuleInsightTemplate(
        title="Missed opportunity to increase AOV via shipping threshold",
        summary="Many orders cluster just below the free-shipping threshold.",
        implication="A small incentive change could convert low baskets into higher-value orders.",
        action="Set free-shipping nudges near threshold and measure uplift in conversion and AOV by cohort.",
        priority="medium",
    ),
    "channel_dependency_risk": RuleInsightTemplate(
        title="Revenue is overly dependent on one channel",
        summary="One source currently drives most of store revenue.",
        implication="Channel shocks can create immediate top-line volatility and reduce negotiating flexibility.",
        action="Build secondary channels with dedicated offers and rebalance budget toward proven incremental sources.",
        priority="high",
    ),
    "bundle_revenue_opportunity": RuleInsightTemplate(
        title="Repeated product combinations indicate bundle upside",
        summary="Certain SKU pairs are frequently purchased together.",
        implication="Current cart behavior suggests untapped bundle conversion and merchandising efficiency gains.",
        action="Create fixed and dynamic bundles for top pairs, then track attach rate and margin impact.",
        priority="medium",
    ),
    "data_quality_issue": RuleInsightTemplate(
        title="SKU data quality is impacting revenue visibility",
        summary="A measurable amount of revenue is tied to blank SKU line items.",
        implication="Merchandising, replenishment, and profitability decisions become less reliable.",
        action="Enforce SKU completeness in catalog and checkout flows; backfill missing identifiers in historical data.",
        priority="medium",
    ),
    "revenue_instability": RuleInsightTemplate(
        title="Revenue trend shows unstable month-to-month swings",
        summary="Revenue fluctuates significantly across recent months.",
        implication="Forecast accuracy drops and inventory/cash planning risk increases.",
        action="Stabilize demand with campaign cadence planning, retention pushes, and source-mix smoothing.",
        priority="high",
    ),
}


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except Exception:
        return 0.0


def _rules_by_priority(rule_codes: list[str], metrics: dict[str, Any]) -> list[str]:
    _ = metrics  # reserved for future metric-aware impact scoring
    deduped = list(dict.fromkeys(rule_codes))
    return sorted(
        deduped,
        key=lambda code: (
            -_PRIORITY_WEIGHT.get(_RULE_INSIGHT_LIBRARY.get(code, RuleInsightTemplate("", "", "", "", "low")).priority, 1),
            code,
        ),
    )


def generate_business_insights(
    rules: list[str],
    metrics: dict[str, Any] | None = None,
    *,
    max_items: int = 10,
) -> list[dict[str, Any]]:
    metric_map = metrics or {}
    ranked_rules = _rules_by_priority(rules, metric_map)
    out: list[dict[str, Any]] = []
    for code in ranked_rules:
        tpl = _RULE_INSIGHT_LIBRARY.get(code)
        if tpl is None:
            continue
        out.append(
            {
                "title": tpl.title,
                "summary": tpl.summary,
                "implication": tpl.implication,
                "action": tpl.action,
                "priority": tpl.priority,
                "rule_code": code,
            }
        )
        if len(out) >= max_items:
            break
    return out


def narrate(payload: RuleInsightPayload) -> NarratedInsight:
    m = payload.context.get("metrics", {})
    ctx = {
        **{k: v for k, v in m.items() if isinstance(v, (int, float))},
        "signal_count": len(payload.context.get("signals", [])),
    }
    templates = payload.templates or {}
    title_t = templates.get("title_template") or f"Rule triggered: {payload.rule_code}"
    summary_t = templates.get("summary_template") or "A configured rule matched current metrics and signals."
    implication_t = templates.get("implication_template") or ""
    action_t = templates.get("action_template") or ""
    return NarratedInsight(
        rule_code=payload.rule_code,
        category=payload.category,
        severity=payload.severity,
        title=_format_template(title_t, ctx),
        summary=_format_template(summary_t, ctx),
        implication=_format_template(implication_t, ctx),
        action=_format_template(action_t, ctx),
        payload_json={
            "rule_code": payload.rule_code,
            "category": payload.category,
            "context": payload.context,
            "templates": templates,
        },
    )


def narrate_all(payloads: list[RuleInsightPayload]) -> list[NarratedInsight]:
    return [narrate(p) for p in payloads]

"""Deterministic narrative rendering from rule templates (no LLM)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.rules_engine import RuleInsightPayload


def _resolve_path(obj: Any, path: str) -> Any:
    cur: Any = obj
    for part in [p for p in str(path or "").split(".") if p]:
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, (list, tuple)):
            try:
                cur = cur[int(part)]
            except Exception:
                return None
        else:
            try:
                cur = getattr(cur, part)
            except Exception:
                return None
        if cur is None:
            return None
    return cur


def _render_mustache(template: str, ctx: dict[str, Any]) -> str:
    """
    Render `{{path.to.value}}` tokens using a dotted-path resolver.
    Unknown tokens remain unchanged.
    """
    import re

    def repl(m: re.Match) -> str:
        key = str(m.group(1) or "").strip()
        val = _resolve_path(ctx, key)
        if val is None:
            return m.group(0)
        # Keep formatting simple/deterministic (no locale).
        if isinstance(val, float):
            # Avoid long floats in UI copy
            return str(round(val, 4)).rstrip("0").rstrip(".")
        return str(val)

    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", repl, str(template or ""))


def _format_template(template: str, context: dict[str, Any]) -> str:
    """Safe deterministic formatter supporting both `.format()` and `{{ }}` tokens."""
    out = str(template or "")
    out = _render_mustache(out, context)
    try:
        return out.format(**context)
    except Exception:
        return out


def _render_any(node: Any, ctx: dict[str, Any]) -> Any:
    if isinstance(node, str):
        return _format_template(node, ctx)
    if isinstance(node, list):
        return [_render_any(x, ctx) for x in node]
    if isinstance(node, dict):
        return {str(k): _render_any(v, ctx) for k, v in node.items()}
    return node


def _compute_decision_vars(rule_code: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """
    Compute derived numeric vars used by decision-ready templates.
    Keep deterministic and safe (missing context => zeros).
    """
    out: dict[str, Any] = {}
    if rule_code == "slow_mover_discount_playbook":
        sig = ctx.get("SKU_SLOW_MOVERS_HIGH") if isinstance(ctx.get("SKU_SLOW_MOVERS_HIGH"), dict) else {}
        sc = sig.get("context") if isinstance(sig, dict) else {}
        sc = sc if isinstance(sc, dict) else {}
        slow_share = float(sc.get("slow_mover_sku_share") or 0.0)
        avg_days = float(sc.get("avg_days_since_last_sale_active_30d") or 0.0)
        active = float(sc.get("active_sku_count_30d") or 0.0)
        slow_cnt = int(round(active * slow_share)) if active > 0 and slow_share > 0 else 0

        # If the signal context doesn't have money, compute a conservative proxy (0).
        stuck = float(sc.get("slow_mover_net_revenue_30d_usd") or 0.0)

        # Priority score: weighted by ratio + staleness + money (caps at 100).
        score = (slow_share * 100.0) * 1.2 + avg_days * 1.0 + (stuck / 1000.0) * 1.5
        out["priority_score_0_100"] = int(max(0, min(100, round(score))))

        # Revenue recovery proxy bounds.
        out["revenue_recovery_low"] = round(stuck * 0.10, 0)
        out["revenue_recovery_high"] = round(stuck * 0.25, 0)

        # Convenience: expose computed count if missing upstream.
        out["slow_mover_sku_count_30d"] = int(sc.get("slow_mover_sku_count_30d") or slow_cnt)
    return out


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
    ctx: dict[str, Any] = {
        **{k: v for k, v in m.items() if isinstance(v, (int, float))},
        "signal_count": len(payload.context.get("signals", [])),
    }
    sig_map = payload.context.get("signal_map") or {}
    if isinstance(sig_map, dict):
        # Expose signals by code for templates like {{SKU_SLOW_MOVERS_HIGH.context...}}
        for k, v in sig_map.items():
            if isinstance(k, str) and isinstance(v, dict):
                ctx[k] = v
        ctx["signal"] = sig_map

    # Derived vars for decision-ready templates
    ctx.update(_compute_decision_vars(payload.rule_code, ctx))

    templates = payload.templates or {}
    title_t = templates.get("title_template") or f"Rule triggered: {payload.rule_code}"
    summary_t = templates.get("summary_template") or "A configured rule matched current metrics and signals."
    implication_t = templates.get("implication_template") or ""
    action_t = templates.get("action_template") or ""

    rule = payload.context.get("rule") or {}
    decision_object = None
    if isinstance(rule, dict):
        # Render the new decision-ready blocks if present (additive; safe if absent).
        decision_object = _render_any(
            {
                "quantified_signals": rule.get("quantified_signals"),
                "insight": rule.get("insight"),
                "decision": rule.get("decision"),
                "expected_impact": rule.get("expected_impact"),
                "risk": rule.get("risk"),
                "ui_payload": rule.get("ui_payload"),
                "action_prompt": rule.get("action_prompt"),
            },
            ctx,
        )
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
            "decision_object": decision_object,
        },
    )


def narrate_all(payloads: list[RuleInsightPayload]) -> list[NarratedInsight]:
    return [narrate(p) for p in payloads]

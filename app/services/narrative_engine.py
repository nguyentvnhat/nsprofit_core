"""
Deterministic narratives from rule payloads (no LLM).

Templates keyed by `narrative_key` from YAML; extend by adding entries to `NARRATIVES`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.services.rules_engine import RuleInsightPayload

Context = dict[str, Any]
NarrativeFn = Callable[[RuleInsightPayload], dict[str, str]]


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _revenue_discount_pressure(p: RuleInsightPayload) -> dict[str, str]:
    m = p.context.get("metrics", {})
    ratio = float(m.get("discount_to_gross_ratio", 0.0))
    return {
        "title": "Discounts absorb a large share of gross revenue",
        "summary": (
            f"Discounts represent {_pct(ratio)} of gross revenue in this upload, "
            "which may compress margin if list prices are not carefully anchored."
        ),
        "implication": "Promotional efficiency and price architecture deserve a focused review.",
        "action": "Segment orders by discount code and campaign; test elasticity on top SKUs.",
    }


def _product_concentration(p: RuleInsightPayload) -> dict[str, str]:
    m = p.context.get("metrics", {})
    share = float(m.get("top_sku_quantity_share", 0.0))
    return {
        "title": "Demand is concentrated in a small set of SKUs",
        "summary": f"Top SKU(s) account for {_pct(share)} of units sold in this dataset.",
        "implication": "Supply, merchandising, and churn risk are tightly coupled to few products.",
        "action": "Model stock-out impact; diversify bundles and cross-sell paths.",
    }


def _customer_repeat_low(p: RuleInsightPayload) -> dict[str, str]:
    m = p.context.get("metrics", {})
    r = float(m.get("repeat_customer_ratio", 0.0))
    return {
        "title": "Repeat purchasers are a thin slice of the customer base",
        "summary": f"Only {_pct(r)} of distinct customers placed more than one order here.",
        "implication": "Growth may be acquisition-heavy; retention programs are under-leveraged.",
        "action": "Instrument post-purchase journeys; launch win-back and replenishment flows.",
    }


def _risk_refunds(p: RuleInsightPayload) -> dict[str, str]:
    # Uses signal payload if present, else metrics
    return {
        "title": "Refund pressure is elevated relative to gross sales",
        "summary": (
            "Refunds are material versus gross totals — investigate product, fulfillment, or "
            "expectation gaps before scaling spend."
        ),
        "implication": "Unit economics and cash conversion may be overstated without refund controls.",
        "action": "Drill into refund reasons and high-risk SKUs; tighten QA and PDP accuracy.",
    }


def _default_narrative(p: RuleInsightPayload) -> dict[str, str]:
    return {
        "title": f"Rule triggered: {p.rule_id}",
        "summary": "A configured rule matched the current metrics and signals.",
        "implication": "Review supporting metrics in the dashboard for business context.",
        "action": "Validate with finance and operations before changing pricing or policy.",
    }


NARRATIVES: dict[str, NarrativeFn] = {
    "revenue_discount_pressure": _revenue_discount_pressure,
    "product_concentration": _product_concentration,
    "customer_repeat_low": _customer_repeat_low,
    "risk_refunds": _risk_refunds,
}


@dataclass(frozen=True)
class NarratedInsight:
    rule_id: str
    domain: str
    narrative_key: str
    severity: str
    title: str
    summary: str
    implication: str
    action: str
    payload_json: dict[str, Any]


def narrate(payload: RuleInsightPayload) -> NarratedInsight:
    fn = NARRATIVES.get(payload.narrative_key, _default_narrative)
    parts = fn(payload)
    return NarratedInsight(
        rule_id=payload.rule_id,
        domain=payload.domain,
        narrative_key=payload.narrative_key,
        severity=payload.severity,
        title=parts["title"],
        summary=parts["summary"],
        implication=parts.get("implication", ""),
        action=parts.get("action", ""),
        payload_json={
            "rule_id": payload.rule_id,
            "domain": payload.domain,
            "narrative_key": payload.narrative_key,
            "context": payload.context,
        },
    )


def narrate_all(payloads: list[RuleInsightPayload]) -> list[NarratedInsight]:
    return [narrate(p) for p in payloads]

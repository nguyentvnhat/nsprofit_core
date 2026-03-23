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

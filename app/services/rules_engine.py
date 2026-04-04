"""Data-driven rule evaluation from YAML (metrics + signals -> insight payloads)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.rule_definition import RuleDefinition


@dataclass(frozen=True)
class RuleInsightPayload:
    """Structured output consumed by `narrative_engine`."""

    rule_code: str
    category: str
    severity: str
    templates: dict[str, str]
    context: dict[str, Any]


_OPS = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
}

_BUSINESS_RULE_SIGNAL_MAP: tuple[tuple[str, str], ...] = (
    ("high_discount_dependency", "discount_dependency_risk"),
    ("stacked_discounting", "double_discounting_issue"),
    ("volume_driven_growth", "low_quality_growth"),
    ("hero_sku_concentration", "sku_concentration_risk"),
    ("low_order_value_problem", "aov_structure_issue"),
    ("free_shipping_opportunity", "free_shipping_optimization_opportunity"),
    ("source_concentration_risk", "channel_dependency_risk"),
    ("bundle_opportunity", "bundle_revenue_opportunity"),
    ("data_hygiene_issue", "data_quality_issue"),
    ("unstable_growth", "revenue_instability"),
)


def _compare(left: float, op: str, right: float) -> bool:
    fn = _OPS.get(op)
    if fn is None:
        raise ValueError(f"Unsupported operator: {op}")
    return bool(fn(left, right))


def _flatten_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    """Flatten nested metrics dict to scalar lookups by metric key."""
    out: dict[str, float] = {}
    for _, values in metrics.items():
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            if isinstance(value, (int, float)):
                out[key] = float(value)
            else:
                try:
                    out[key] = float(value)
                except Exception:
                    continue
    return out


def _extract_signal_codes(signals: list[dict[str, Any]] | set[str]) -> set[str]:
    if isinstance(signals, set):
        return {str(s) for s in signals}
    out: set[str] = set()
    for s in signals:
        code = s.get("signal_code")
        if code:
            out.add(str(code))
    return out


def _is_triggered_signal_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return float(value) > 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    if isinstance(value, dict):
        if "active" in value:
            return _is_triggered_signal_value(value.get("active"))
        if "triggered" in value:
            return _is_triggered_signal_value(value.get("triggered"))
    return False


def map_business_rule_flags(signals: dict[str, Any]) -> list[str]:
    """
    Deterministically map signal flags -> business rule flags.

    Expected signal keys:
      high_discount_dependency, stacked_discounting, volume_driven_growth,
      hero_sku_concentration, low_order_value_problem, free_shipping_opportunity,
      source_concentration_risk, bundle_opportunity, data_hygiene_issue, unstable_growth.
    """
    out: list[str] = []
    for signal_key, rule_flag in _BUSINESS_RULE_SIGNAL_MAP:
        if _is_triggered_signal_value(signals.get(signal_key)):
            out.append(rule_flag)
    return out


def _eval_condition(
    cond: dict[str, Any],
    metric_map: dict[str, float],
    signal_codes: set[str],
) -> bool:
    ctype = str(cond.get("type", "")).strip().lower()
    if ctype == "signal":
        wanted = str(cond.get("signal_code", ""))
        return wanted in signal_codes
    if ctype == "metric":
        mk = str(cond.get("metric", ""))
        op = str(cond.get("operator", ""))
        if mk not in metric_map:
            return False
        return _compare(metric_map[mk], op, float(cond.get("value", 0)))
    if ctype in ("metric_vs_metric", "metric_compare"):
        left = str(cond.get("left_metric", ""))
        right = str(cond.get("right_metric", ""))
        op = str(cond.get("operator", ""))
        if left not in metric_map or right not in metric_map:
            return False
        return _compare(metric_map[left], op, metric_map[right])
    raise ValueError(f"Unrecognized condition type: {cond}")


def _eval_condition_group(
    block: dict[str, Any],
    metric_map: dict[str, float],
    signal_codes: set[str],
) -> bool:
    """Recursively evaluate `all` / `any` condition groups."""
    if "all" in block:
        checks = []
        for c in block["all"]:
            if isinstance(c, dict) and "type" in c:
                checks.append(_eval_condition(c, metric_map, signal_codes))
            else:
                checks.append(_eval_condition_group(c, metric_map, signal_codes))
        return all(checks)
    if "any" in block:
        checks = []
        for c in block["any"]:
            if isinstance(c, dict) and "type" in c:
                checks.append(_eval_condition(c, metric_map, signal_codes))
            else:
                checks.append(_eval_condition_group(c, metric_map, signal_codes))
        return any(checks)
    raise ValueError(f"Unrecognized condition group: {block}")


def _load_yaml_files(rules_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    paths = sorted(set(rules_dir.glob("*.yaml")) | set(rules_dir.glob("*.yml")))
    loaded: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as fh:
            loaded.append((path, yaml.safe_load(fh) or {}))
    return loaded


def evaluate_rules(
    metrics: dict[str, Any] | dict[str, float],
    signals: list[dict[str, Any]] | set[str],
    *,
    rules_dir: Path | None = None,
) -> list[RuleInsightPayload]:
    """Evaluate all YAML rule packs and return payloads for deterministic narrative rendering."""
    base = rules_dir or get_settings().resolved_rules_dir
    metric_map = (
        dict(metrics)
        if metrics and all(isinstance(v, (int, float)) for v in metrics.values())  # type: ignore[arg-type]
        else _flatten_metrics(metrics)  # type: ignore[arg-type]
    )
    signal_codes = _extract_signal_codes(signals)
    signal_map: dict[str, dict[str, Any]] = {}
    if isinstance(signals, list):
        for s in signals:
            code = str(s.get("signal_code") or "").strip()
            if not code:
                continue
            # Keep the raw signal payload (incl. context) so narrative/decision layers can render numbers.
            signal_map[code] = dict(s)

    payloads: list[RuleInsightPayload] = []
    for path, doc in _load_yaml_files(base):
        for rule in doc.get("rules", []) or []:
            if not bool(rule.get("enabled", True)):
                continue
            condition = rule.get("condition") or {}
            if not _eval_condition_group(condition, metric_map, signal_codes):
                continue
            payloads.append(
                RuleInsightPayload(
                    rule_code=str(rule["rule_code"]),
                    category=str(rule.get("category", "general")),
                    severity=str(rule.get("severity", "medium")),
                    templates={
                        "title_template": str(rule.get("title_template", "")),
                        "summary_template": str(rule.get("summary_template", "")),
                        "implication_template": str(rule.get("implication_template", "")),
                        "action_template": str(rule.get("action_template", "")),
                    },
                    context={
                        "metrics": metric_map,
                        "signals": sorted(signal_codes),
                        "signal_map": signal_map,
                        "rule_source": str(path),
                        "rule": rule,
                    },
                )
            )
    return payloads


def sync_rule_definitions(session: Session, rules_dir: Path | None = None) -> None:
    """Mirror YAML rules into `rule_definitions` for auditing."""
    base = rules_dir or get_settings().resolved_rules_dir
    from datetime import datetime

    for path, doc in _load_yaml_files(base):
        for rule in doc.get("rules", []) or []:
            rid = str(rule["rule_code"])
            row = session.scalars(
                select(RuleDefinition).where(RuleDefinition.rule_code == rid)
            ).first()
            sev = str(rule.get("severity", "medium"))
            if row is None:
                row = RuleDefinition(
                    rule_id=rid,
                    domain=str(rule.get("category", "general")),
                    yaml_source_path=str(path),
                    definition_hash=None,
                    description=rule.get("description"),
                    last_synced_at=datetime.utcnow(),
                    rule_code=rid,
                    category=str(rule.get("category", "general")),
                    is_active=bool(rule.get("enabled", True)),
                    severity=sev,
                    condition_json=rule.get("condition"),
                    title_template=rule.get("title_template"),
                    summary_template=rule.get("summary_template"),
                    implication_template=rule.get("implication_template"),
                    action_template=rule.get("action_template"),
                )
                session.add(row)
            else:
                row.rule_id = rid
                row.domain = str(rule.get("category", "general"))
                row.yaml_source_path = str(path)
                row.description = rule.get("description")
                row.last_synced_at = datetime.utcnow()
                row.category = str(rule.get("category", "general"))
                row.is_active = bool(rule.get("enabled", True))
                row.severity = sev
                row.condition_json = rule.get("condition")
                row.title_template = rule.get("title_template")
                row.summary_template = rule.get("summary_template")
                row.implication_template = rule.get("implication_template")
                row.action_template = rule.get("action_template")
    session.flush()

"""
Load external YAML rules and evaluate against metric snapshots + signal codes.

No business thresholds belong in Streamlit — extend rule files instead.
"""

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
    """Structured output consumed by `narrative_engine` (no prose here)."""

    rule_id: str
    domain: str
    narrative_key: str
    severity: str
    context: dict[str, Any]


_OPS = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
}


def _compare(left: float, op: str, right: float) -> bool:
    fn = _OPS.get(op)
    if fn is None:
        raise ValueError(f"Unsupported operator: {op}")
    return bool(fn(left, right))


def _eval_condition(
    cond: dict[str, Any],
    metric_map: dict[str, float],
    signal_codes: set[str],
) -> bool:
    if "signal" in cond:
        return str(cond["signal"]) in signal_codes
    if "metric" in cond and "op" in cond and "value" in cond:
        key = str(cond["metric"])
        if key not in metric_map:
            return False
        return _compare(float(metric_map[key]), str(cond["op"]), float(cond["value"]))
    if "metric_left" in cond and "metric_right" in cond and "op" in cond:
        lk = str(cond["metric_left"])
        rk = str(cond["metric_right"])
        if lk not in metric_map or rk not in metric_map:
            return False
        return _compare(float(metric_map[lk]), str(cond["op"]), float(metric_map[rk]))
    raise ValueError(f"Unrecognized condition shape: {cond}")


def _eval_match_block(
    block: dict[str, Any],
    metric_map: dict[str, float],
    signal_codes: set[str],
) -> bool:
    if "all" in block:
        return all(
            _eval_condition(c, metric_map, signal_codes)
            if isinstance(c, dict) and ("metric" in c or "signal" in c or "metric_left" in c)
            else _eval_match_block(c, metric_map, signal_codes)
            for c in block["all"]
        )
    if "any" in block:
        return any(
            _eval_condition(c, metric_map, signal_codes)
            if isinstance(c, dict) and ("metric" in c or "signal" in c or "metric_left" in c)
            else _eval_match_block(c, metric_map, signal_codes)
            for c in block["any"]
        )
    raise ValueError(f"Unrecognized match block: {block}")


def _load_yaml_files(rules_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    paths = sorted(set(rules_dir.glob("*.yaml")) | set(rules_dir.glob("*.yml")))
    loaded: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as fh:
            loaded.append((path, yaml.safe_load(fh) or {}))
    return loaded


def evaluate_rules(
    metric_map: dict[str, float],
    signal_codes: set[str],
    *,
    rules_dir: Path | None = None,
) -> list[RuleInsightPayload]:
    """Evaluate all YAML rule packs and return insight payloads (pre-narrative)."""
    base = rules_dir or get_settings().resolved_rules_dir
    payloads: list[RuleInsightPayload] = []
    for _path, doc in _load_yaml_files(base):
        domain = str(doc.get("domain", "unknown"))
        for rule in doc.get("rules", []) or []:
            if not rule.get("enabled", True):
                continue
            rid = str(rule["id"])
            req_signals = set(str(s) for s in (rule.get("require_signals") or []))
            if req_signals and not req_signals.issubset(signal_codes):
                continue
            match = rule.get("match") or {}
            if not _eval_match_block(match, metric_map, signal_codes):
                continue
            insight = rule.get("insight") or {}
            payloads.append(
                RuleInsightPayload(
                    rule_id=rid,
                    domain=domain,
                    narrative_key=str(insight.get("narrative_key", rid)),
                    severity=str(insight.get("severity", "info")),
                    context={
                        "metrics": dict(metric_map),
                        "signals": sorted(signal_codes),
                        "rule": rule,
                    },
                )
            )
    return payloads


def sync_rule_definitions(session: Session, rules_dir: Path | None = None) -> None:
    """Mirror YAML rules into `rule_definitions` for auditing."""
    base = rules_dir or get_settings().resolved_rules_dir
    for path, doc in _load_yaml_files(base):
        domain = str(doc.get("domain", "unknown"))
        for rule in doc.get("rules", []) or []:
            rid = str(rule["id"])
            row = session.scalars(select(RuleDefinition).where(RuleDefinition.rule_code == rid)).first()
            insight = rule.get("insight") or {}
            sev = str(insight.get("severity", "info"))
            if row is None:
                row = RuleDefinition(
                    rule_code=rid,
                    category=domain,
                    is_active=bool(rule.get("enabled", True)),
                    severity=sev,
                    condition_json=rule,
                )
                session.add(row)
            else:
                row.category = domain
                row.is_active = bool(rule.get("enabled", True))
                row.severity = sev
                row.condition_json = rule
    session.flush()

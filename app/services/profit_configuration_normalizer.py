"""
Normalize optional profit_configuration payloads from portal_merchant / API callers.

Safe defaults: missing groups → disabled, completeness basic.
Malformed structures never raise; warnings are collected for logging and meta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


GROUP_KEYS = ("cogs", "shipping_costs", "transaction_fees", "custom_costs")
COMPLETENESS_VALUES = frozenset({"basic", "partial", "enriched"})


@dataclass(frozen=True)
class ProfitGroupNormalized:
    enabled: bool
    mode: str
    items: list[dict[str, Any]]
    summary: dict[str, Any]


@dataclass(frozen=True)
class NormalizedProfitConfiguration:
    cogs: ProfitGroupNormalized
    shipping_costs: ProfitGroupNormalized
    transaction_fees: ProfitGroupNormalized
    custom_costs: ProfitGroupNormalized
    completeness: str
    warnings: tuple[str, ...] = ()


def _empty_group() -> ProfitGroupNormalized:
    return ProfitGroupNormalized(
        enabled=False,
        mode="none",
        items=[],
        summary={},
    )


def _coerce_group(raw: Any, key: str) -> tuple[ProfitGroupNormalized, list[str]]:
    warns: list[str] = []
    if not isinstance(raw, dict):
        return _empty_group(), [f"{key}: expected object, ignored"]

    en = raw.get("enabled")
    enabled = bool(en) if en is not None else False

    mode = raw.get("mode")
    if mode is None or (isinstance(mode, str) and not mode.strip()):
        mode = "none"
    elif not isinstance(mode, str):
        mode = "none"
        warns.append(f"{key}.mode: invalid type, using none")

    items = raw.get("items")
    if items is None:
        items_list: list[dict[str, Any]] = []
    elif isinstance(items, list):
        items_list = [x for x in items if isinstance(x, dict)]
        if len(items_list) != len(items):
            warns.append(f"{key}.items: non-object entries skipped")
    else:
        items_list = []
        warns.append(f"{key}.items: expected array, ignored")

    summary = raw.get("summary")
    if summary is None:
        summary_dict: dict[str, Any] = {}
    elif isinstance(summary, dict):
        summary_dict = summary
    else:
        summary_dict = {}
        warns.append(f"{key}.summary: expected object, ignored")

    return (
        ProfitGroupNormalized(
            enabled=enabled and mode != "none",
            mode=str(mode).strip().lower(),
            items=items_list,
            summary=summary_dict,
        ),
        warns,
    )


def normalize_profit_configuration(raw: Any) -> tuple[NormalizedProfitConfiguration, list[str]]:
    """
    Accept dict-like API/JSON or None. Returns normalized config + warnings (never raises).
    """
    warns: list[str] = []
    if raw is None:
        return (
            NormalizedProfitConfiguration(
                cogs=_empty_group(),
                shipping_costs=_empty_group(),
                transaction_fees=_empty_group(),
                custom_costs=_empty_group(),
                completeness="basic",
                warnings=(),
            ),
            [],
        )

    if not isinstance(raw, dict):
        return (
            NormalizedProfitConfiguration(
                cogs=_empty_group(),
                shipping_costs=_empty_group(),
                transaction_fees=_empty_group(),
                custom_costs=_empty_group(),
                completeness="basic",
                warnings=("profit_configuration: expected object, using defaults",),
            ),
            ["profit_configuration: expected object, using defaults"],
        )

    groups: dict[str, ProfitGroupNormalized] = {}
    for key in GROUP_KEYS:
        g, w = _coerce_group(raw.get(key), key)
        groups[key] = g
        warns.extend(w)

    comp = raw.get("completeness")
    if isinstance(comp, str) and comp.strip().lower() in COMPLETENESS_VALUES:
        completeness = comp.strip().lower()
    else:
        completeness = "basic"
        if comp is not None:
            warns.append("completeness: invalid value, using basic")

    # Derive completeness if absent in payload
    any_enabled = any(
        getattr(groups[k], "enabled", False) for k in GROUP_KEYS
    )
    if raw.get("completeness") is None and any_enabled:
        all_four = all(groups[k].enabled for k in GROUP_KEYS)
        completeness = "enriched" if all_four else "partial"

    cfg = NormalizedProfitConfiguration(
        cogs=groups["cogs"],
        shipping_costs=groups["shipping_costs"],
        transaction_fees=groups["transaction_fees"],
        custom_costs=groups["custom_costs"],
        completeness=completeness,
        warnings=tuple(warns),
    )
    return cfg, warns


def profit_configuration_to_jsonable(cfg: NormalizedProfitConfiguration) -> dict[str, Any]:
    """Serialize for response meta / logging."""

    def _g(g: ProfitGroupNormalized) -> dict[str, Any]:
        return {
            "enabled": g.enabled,
            "mode": g.mode,
            "items": g.items,
            "summary": g.summary,
        }

    return {
        "cogs": _g(cfg.cogs),
        "shipping_costs": _g(cfg.shipping_costs),
        "transaction_fees": _g(cfg.transaction_fees),
        "custom_costs": _g(cfg.custom_costs),
        "completeness": cfg.completeness,
    }

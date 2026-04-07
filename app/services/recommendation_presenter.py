def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _fmt_pct(value: float) -> str:
    v = round(float(value), 1)
    if float(v).is_integer():
        return str(int(v))
    return str(v)


def _fmt_money(value: float) -> str:
    v = round(float(value), 2)
    if float(v).is_integer():
        return str(int(v))
    return f"{v:.2f}"


def _current_discount_pct(draft: dict) -> float:
    return _safe_float(draft.get("current_discount_pct"))


def _recommended_discount_pct(draft: dict) -> float:
    # backward-compatible: keep support for old key
    val = _safe_float(draft.get("recommended_discount_pct"))
    if val > 0:
        return val
    return _safe_float(draft.get("suggested_discount_pct"))


def _discount_delta_pct(draft: dict) -> float:
    val = _safe_float(draft.get("discount_delta_pct"))
    if val > 0:
        return val
    current = _current_discount_pct(draft)
    recommended = _recommended_discount_pct(draft)
    return max(0.0, current - recommended)


def _estimated_margin_recovery_per_order(draft: dict) -> float:
    val = _safe_float(draft.get("estimated_margin_recovery_per_order"))
    if val > 0:
        return val

    # fallback from AOV if available
    delta = _discount_delta_pct(draft)
    aov = _safe_float(draft.get("avg_order_value"))
    if aov <= 0:
        aov = _safe_float(draft.get("aov"))

    return round((delta / 100.0) * aov, 2)


def _estimated_total_margin_recovery(draft: dict, duration_days: int) -> float:
    val = _safe_float(draft.get("estimated_total_margin_recovery"))
    if val > 0:
        return val

    per_order = _estimated_margin_recovery_per_order(draft)
    avg_orders_during_test = _safe_float(draft.get("avg_orders_during_test"))
    if avg_orders_during_test > 0:
        return round(per_order * avg_orders_during_test, 2)

    avg_orders_per_day = _safe_float(draft.get("avg_orders_per_day"))
    if avg_orders_per_day <= 0:
        avg_orders_per_day = _safe_float(draft.get("orders_per_day"))

    return round(per_order * avg_orders_per_day * max(int(duration_days), 0), 2)


def _avg_orders_during_test(draft: dict, duration_days: int) -> float:
    val = _safe_float(draft.get("avg_orders_during_test"))
    if val > 0:
        return val

    avg_orders_per_day = _safe_float(draft.get("avg_orders_per_day"))
    if avg_orders_per_day <= 0:
        avg_orders_per_day = _safe_float(draft.get("orders_per_day"))

    return round(avg_orders_per_day * max(int(duration_days), 0), 1)


def demand_impact_label(delta_pts: float) -> str:
    if delta_pts <= 3:
        return "Low demand sensitivity margin recovery is the primary opportunity"
    if delta_pts <= 10:
        return "Balanced trade-off between demand response and margin improvement"
    return "Demand is likely sensitive so controlled rollout is recommended"


def risk_level(draft: dict) -> tuple[str, str]:
    conf = str(draft.get("confidence", "")).lower()

    if conf == "high":
        return "low", "Low"
    if conf == "medium":
        return "medium", "Medium"
    if conf == "low":
        return "high", "High"

    return "medium", "Medium"


def build_summary(draft: dict, duration_days: int) -> str:
    current = _current_discount_pct(draft)
    suggested = _recommended_discount_pct(draft)
    ct = str(draft.get("campaign_type", "discount") or "discount")
    per_order = _estimated_margin_recovery_per_order(draft)

    if ct == "flash_sale":
        if current > 0 and suggested > 0:
            return (
                f"Reduce discount from {_fmt_pct(current)}% to {_fmt_pct(suggested)}% "
                f"for {duration_days} days to recover ~${_fmt_money(per_order)}/order"
            )
        return (
            f"Test a {_fmt_pct(suggested)}% flash sale for {duration_days} days "
            f"to capture short-term demand"
        )

    if ct == "bundle":
        return f"Test a bundle offer for {duration_days} days instead of deeper discounting"

    if suggested > 0 and current > 0 and suggested < current:
        return (
            f"Reduce discount from {_fmt_pct(current)}% to {_fmt_pct(suggested)}% "
            f"for {duration_days} days to recover ~${_fmt_money(per_order)}/order"
        )

    if suggested > 0:
        return (
            f"Test promotional pricing at {_fmt_pct(suggested)}% for {duration_days} days "
            f"and validate profit impact"
        )

    return f"Run a targeted pricing test for {duration_days} days and validate profit impact"


def build_why(draft: dict, duration_days: int) -> list[str]:
    out = []

    current = _current_discount_pct(draft)
    suggested = _recommended_discount_pct(draft)
    delta = _discount_delta_pct(draft)
    per_order = _estimated_margin_recovery_per_order(draft)
    total_recovery = _estimated_total_margin_recovery(draft, duration_days)
    avg_orders = _avg_orders_during_test(draft, duration_days)

    velocity = str(draft.get("velocity", "") or "").lower().strip()
    margin = draft.get("margin_proxy_low_pct")
    margin_val = _safe_float(margin, -1.0)

    if current > 0 and suggested > 0 and delta > 0:
        out.append(
            f"Current discount is {_fmt_pct(current)}% while recommended discount is "
            f"{_fmt_pct(suggested)}% ({_fmt_pct(delta)} pts lower)"
        )

    if per_order > 0:
        out.append(f"That change can recover about ${_fmt_money(per_order)} per order")

    if total_recovery > 0:
        if avg_orders > 0:
            out.append(
                f"At expected test volume (~{_fmt_money(avg_orders)} orders), "
                f"that is about ${_fmt_money(total_recovery)} over {duration_days} days"
            )
        else:
            out.append(
                f"Estimated total margin recovery is about ${_fmt_money(total_recovery)} "
                f"over {duration_days} days"
            )

    if velocity == "slow":
        out.append("Sales velocity is weak so the test should stay controlled and SKU-specific")
    elif velocity == "fast":
        out.append("Sales velocity is strong so avoiding unnecessary discount depth protects margin")

    if margin is not None and margin_val >= 0:
        if margin_val >= 50:
            out.append("Post-change margin remains strong supporting a low-risk test")
        elif margin_val >= 30:
            out.append("Post-change margin is acceptable but should be monitored closely")
        else:
            out.append("Margin buffer is thin so rollout should stay narrow and closely monitored")

    out.append("This is a short-term experiment not a permanent pricing decision")

    return out


def build_next_steps(duration_days: int, draft: dict | None = None) -> list[str]:
    d = draft or {}

    current = _current_discount_pct(d)
    suggested = _recommended_discount_pct(d)
    per_order = _estimated_margin_recovery_per_order(d)
    delta = _discount_delta_pct(d)

    steps: list[str] = []

    if current > 0 and suggested > 0:
        headline = f"Reduce discount from {_fmt_pct(current)}% to {_fmt_pct(suggested)}%"
        if per_order > 0:
            headline += f" to recover ~${_fmt_money(per_order)}/order"
        steps.append(headline)
    elif suggested > 0:
        steps.append(f"Apply {_fmt_pct(suggested)}% promotional pricing for the test window")
    else:
        steps.append(f"Run the pricing test for {duration_days} days")

    steps.append(f"Run for {duration_days} days to collect decision data")

    if per_order > 0:
        steps.append(
            f"Track profit per order with a target improvement of about ${_fmt_money(per_order)}"
        )
    else:
        steps.append("Track conversion rate and profit per order together")

    if delta > 0:
        steps.append("Revert or narrow the change if conversion drops beyond your threshold")
    else:
        steps.append("Stop early if profit quality declines")

    return steps


def present_promotion_draft(draft: dict, duration_days: int = 3) -> dict:
    delta = abs(
        _safe_float(draft.get("retained_after_pct")) - _safe_float(draft.get("retained_before_pct"))
    )

    risk_key, risk_label = risk_level(draft)

    current = _current_discount_pct(draft)
    suggested = _recommended_discount_pct(draft)
    delta_pct = _discount_delta_pct(draft)
    per_order = _estimated_margin_recovery_per_order(draft)
    total_recovery = _estimated_total_margin_recovery(draft, duration_days)
    avg_orders_test = _avg_orders_during_test(draft, duration_days)

    return {
        **draft,
        # additive fields, non-breaking
        "current_discount_pct": current,
        "recommended_discount_pct": suggested,
        "discount_delta_pct": delta_pct,
        "estimated_margin_recovery_per_order": per_order,
        "estimated_total_margin_recovery": total_recovery,
        "avg_orders_during_test": avg_orders_test,
        # existing structure preserved
        "summary": build_summary(draft, duration_days),
        "risk_level_key": risk_key,
        "risk_level_label": risk_label,
        "demand_impact_label": demand_impact_label(delta),
        "why_bullets": build_why(draft, duration_days),
        "next_step_bullets": build_next_steps(duration_days, draft),
    }
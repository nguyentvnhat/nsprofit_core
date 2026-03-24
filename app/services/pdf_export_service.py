"""Executive PDF export from existing dashboard payload."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from pathlib import Path
import re
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

try:
    from weasyprint import CSS, HTML
except Exception as exc:  # pragma: no cover - optional runtime dependency
    HTML = None  # type: ignore[assignment]
    CSS = None  # type: ignore[assignment]
    _WEASYPRINT_IMPORT_ERROR = exc
else:
    _WEASYPRINT_IMPORT_ERROR = None


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt_money(value: Any) -> str:
    return f"${_f(value):,.2f}"


def _fmt_pct(value: Any) -> str:
    return f"{_f(value) * 100.0:.1f}%"


def _priority_label(priority: Any) -> str:
    p = str(priority or "").strip().lower()
    if p in {"high", "critical", "warning"}:
        return "High"
    if p in {"medium", "moderate", "normal"}:
        return "Medium"
    return "Low"


def _signal_human(code: Any) -> str:
    c = str(code or "").strip()
    if not c:
        return "-"
    return c.replace("_", " ").title()


def _money_basis(ins: dict[str, Any]) -> str:
    code = str(ins.get("signal_code") or "").upper()
    title = str(ins.get("title") or "").lower()
    loss = max(_f(ins.get("estimated_loss")), 0.0)
    opp = max(_f(ins.get("opportunity_size")), 0.0)
    blob = f"{code} {title}"
    if "REFUND" in blob and loss > 0:
        return "Measured"
    if ("DISCOUNT" in blob or "AOV" in blob or "UNSTABLE" in blob or "VOLUME_DRIVEN" in blob) and (loss > 0 or opp > 0):
        return "Estimated (proxy)"
    return "Estimated (proxy)"


def _impact_numbers(ins: dict[str, Any]) -> tuple[float, float]:
    loss = max(_f(ins.get("estimated_loss")), 0.0)
    opp = max(_f(ins.get("opportunity_size")), 0.0)
    if loss > 0 or opp > 0:
        return loss, opp
    revenue = max(_f(ins.get("impacted_revenue")), _f(ins.get("revenue")))
    code = str(ins.get("signal_code") or "").upper()
    title = str(ins.get("title") or "").lower()
    blob = f"{code} {title}"
    if revenue <= 0:
        return 0.0, 0.0
    if "CONCENTRATION" in blob or "DEPENDENCY" in blob:
        return revenue * 0.05, revenue * 0.09
    if "LOW_REPEAT" in blob or "REPEAT" in blob:
        return revenue * 0.06, revenue * 0.10
    if "UNSTABLE" in blob or "VOLAT" in blob:
        return revenue * 0.03, revenue * 0.07
    return revenue * 0.04, revenue * 0.08


def _impact_text(ins: dict[str, Any]) -> str:
    loss, opp = _impact_numbers(ins)
    if loss > 0 and loss >= opp:
        return f"{_fmt_money(loss)} at risk"
    if opp > 0:
        return f"{_fmt_money(opp)} opportunity"
    low, high = _impact_numbers(ins)
    if low > 0 and high > low:
        return f"{_fmt_money(low)}-{_fmt_money(high)} estimated impact"
    return f"{_fmt_money(max(low, high))} estimated impact"


def _impact_value(ins: dict[str, Any]) -> float:
    loss, opp = _impact_numbers(ins)
    return max(loss, opp)


def _impact_range_text(ins: dict[str, Any]) -> str:
    low, high = _impact_numbers(ins)
    if low > 0 and high > low:
        return f"{_fmt_money(low)}-{_fmt_money(high)}"
    v = max(low, high)
    return _fmt_money(v)


def _decision_type(ins: dict[str, Any]) -> str:
    blob = f"{str(ins.get('signal_code') or '').upper()} {str(ins.get('title') or '').lower()}"
    if "STACK" in blob or "DISCOUNT" in blob or "REFUND" in blob or "CONCENTRATION" in blob:
        return "RISK"
    if "AOV" in blob or "BUNDLE" in blob or "SHIPPING" in blob or "REPEAT" in blob:
        return "GROWTH"
    return "QUICK WIN"


def _decision_title(ins: dict[str, Any]) -> str:
    blob = f"{str(ins.get('signal_code') or '').upper()} {str(ins.get('title') or '').lower()}"
    if "STACK" in blob or "DISCOUNT" in blob:
        return "Reduce discount stacking leakage"
    if "AOV" in blob or "LOW_ORDER_VALUE" in blob:
        return "Increase AOV with bundle + threshold offer"
    if "CONCENTRATION" in blob or "DEPENDENCY" in blob:
        return "Reduce channel dependency risk"
    if "REPEAT" in blob:
        return "Lift repeat purchase rate"
    if "SHIPPING" in blob or "FREE_SHIP" in blob:
        return "Set free-shipping threshold for higher margin"
    if "BUNDLE" in blob or "PAIR" in blob:
        return "Launch high-conversion bundle offer"
    if "REFUND" in blob or "RETURN" in blob:
        return "Reduce refund and return leakage"
    return "Increase campaign profit this week"


def _time_to_impact(ins: dict[str, Any]) -> str:
    blob = f"{str(ins.get('signal_code') or '').upper()} {str(ins.get('title') or '').lower()}"
    if "STACK" in blob or "DISCOUNT" in blob or "SHIPPING" in blob:
        return "3-7 days"
    if "AOV" in blob or "BUNDLE" in blob or "REPEAT" in blob:
        return "7-14 days"
    if "CONCENTRATION" in blob or "DEPENDENCY" in blob:
        return "14-30 days"
    return "7-14 days"


def _confidence(ins: dict[str, Any]) -> str:
    basis = _money_basis(ins)
    blob = f"{str(ins.get('signal_code') or '').upper()} {str(ins.get('title') or '').lower()}"
    if basis == "Measured":
        return "High"
    if "DISCOUNT" in blob or "AOV" in blob or "REFUND" in blob or "UNSTABLE" in blob:
        return "Medium"
    return "Low"


def _action_text(ins: dict[str, Any]) -> str:
    code = str(ins.get("signal_code") or "").upper()
    title = str(ins.get("title") or "").lower()
    campaign = str(ins.get("campaign") or "this campaign")
    loss = max(_f(ins.get("estimated_loss")), 0.0)
    opp = max(_f(ins.get("opportunity_size")), 0.0)
    revenue = max(_f(ins.get("impacted_revenue")), _f(ins.get("revenue")))
    blob = f"{code} {title}"
    if "STACK" in blob or "DISCOUNT" in blob:
        base = f"Reduce discount stacking in {campaign}"
    elif "AOV" in blob or "LOW_ORDER_VALUE" in blob or "order value" in blob:
        base = f"Increase AOV in {campaign}"
    elif "UNSTABLE" in blob or "VOLAT" in blob:
        base = f"Stabilize revenue in {campaign}"
    elif "CONCENTRATION" in blob or "DEPENDENCY" in blob:
        base = f"Diversify channels/SKUs in {campaign}"
    elif "LOW_REPEAT" in blob or "REPEAT" in blob:
        base = f"Lift repeat mix in {campaign}"
    elif "BUNDLE" in blob or "PAIR" in blob:
        base = f"Launch bundle/paired offer in {campaign}"
    elif "SHIPPING" in blob or "FREE_SHIP" in blob or "THRESHOLD" in blob:
        base = f"Adjust free-shipping threshold and cart nudges in {campaign}"
    elif "REFUND" in blob or "RETURN" in blob:
        base = f"Reduce refund drivers in {campaign}"
    else:
        raw = str(ins.get("action") or "").strip()
        if raw:
            raw = re.sub(r"(?i)^action:\s*", "", raw).strip(" .")
            base = f"{raw} in {campaign}" if campaign.lower() not in raw.lower() else raw
        else:
            base = f"Tighten targeting and offer design in {campaign}"

    if loss > 0:
        return f"{base} -> save {_fmt_money(loss)}"
    if opp > 0:
        return f"{base} -> gain {_fmt_money(opp)}"
    if revenue <= 0:
        return f"{base} -> estimated impact {_impact_range_text(ins)}"
    if "CONCENTRATION" in blob or "DEPENDENCY" in blob:
        return f"Protect {_fmt_money(revenue * 0.05)} exposure by diversifying channels in {campaign}"
    if "LOW_REPEAT" in blob or "REPEAT" in blob:
        return f"Recover {_fmt_money(revenue * 0.08)} by increasing repeat mix in {campaign}"
    return f"Protect {_fmt_money(revenue * 0.05)} by tightening controls in {campaign}"


def _sort_insights(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            -_f(r.get("priority_score")),
            -(_f(r.get("estimated_loss")) + _f(r.get("opportunity_size"))),
            -_f(r.get("impacted_revenue")),
        ),
    )


def _execution_score(ins: dict[str, Any]) -> float:
    impact = _impact_value(ins)
    confidence_w = {"High": 1.0, "Medium": 0.75, "Low": 0.5}.get(_confidence(ins), 0.6)
    speed_w = {"3-7 days": 1.0, "7-14 days": 0.8, "14-30 days": 0.55, "30+ days": 0.35}.get(_time_to_impact(ins), 0.6)
    return impact * confidence_w * speed_w


def _execution_plan(insights: list[dict[str, Any]]) -> list[dict[str, str]]:
    ordered = sorted(insights, key=lambda x: -_execution_score(x))
    slots = [
        ("#1 Quick Win (<7 days)", {"3-7 days"}),
        ("#2 Growth Lever (7-14 days)", {"7-14 days"}),
        ("#3 Strategic / Risk Control (longer-term)", {"14-30 days", "30+ days"}),
    ]
    plan: list[dict[str, str]] = []
    used: set[int] = set()
    for label, allowed in slots:
        pick_idx = next((i for i, ins in enumerate(ordered) if i not in used and _time_to_impact(ins) in allowed), None)
        if pick_idx is None:
            pick_idx = next((i for i in range(len(ordered)) if i not in used), None)
        if pick_idx is None:
            break
        used.add(pick_idx)
        ins = ordered[pick_idx]
        plan.append(
            {
                "slot": label,
                "decision": _action_text(ins),
                "impact": _impact_range_text(ins),
                "time_to_impact": _time_to_impact(ins),
                "confidence": _confidence(ins),
                "type": _decision_type(ins),
            }
        )
    return plan


def _impact_high_from_range(range_text: str) -> float:
    t = str(range_text or "").replace("$", "").replace(",", "")
    parts = [p.strip() for p in t.split("-") if p.strip()]
    if not parts:
        return 0.0
    try:
        return float(parts[-1])
    except ValueError:
        return 0.0


def _campaign_reason_map(risks: list[dict[str, Any]], max_reasons: int = 2) -> dict[str, str]:
    by_campaign: dict[str, list[str]] = {}
    for r in risks:
        campaign = str(r.get("campaign") or "").strip()
        if not campaign:
            continue
        reason = str(r.get("signal_desc") or _signal_human(r.get("signal_code"))).strip()
        if not reason:
            continue
        bucket = by_campaign.setdefault(campaign, [])
        if reason not in bucket:
            bucket.append(reason)
    out: dict[str, str] = {}
    for campaign, reasons in by_campaign.items():
        out[campaign] = "; ".join(reasons[:max_reasons])
    return out


def _upcoming_campaign_calendar(today: date | None = None, limit: int = 5) -> list[dict[str, str]]:
    d0 = today or date.today()
    events = [
        (1, 1, "New Year", "Clear old stock without killing margin", "Only discount slow-moving SKUs; keep best sellers at normal price."),
        (2, 14, "Valentine's Day", "Increase basket value", "Use gift bundles and cap voucher depth by channel."),
        (3, 8, "International Women's Day", "Grow revenue from gift sets", "Push combo offers before event day; avoid site-wide deep discount."),
        (4, 30, "Reunification Day (VN)", "Scale paid traffic safely", "Raise budget only on campaigns meeting margin floor."),
        (5, 1, "Labor Day", "Protect profit during short promo", "Run shorter flash windows and pause low-margin ad sets."),
        (6, 6, "Mid-Year Mega Sale 6.6", "Maximize volume with controlled discount", "Prioritize high-margin SKUs and stop coupon stacking."),
        (7, 7, "Mega Sale 7.7", "Lift AOV", "Set free-ship threshold above current AOV and upsell add-ons."),
        (8, 8, "Mega Sale 8.8", "Avoid margin-negative scale", "Bid down or pause SKUs/campaigns with weak contribution margin."),
        (9, 9, "Mega Sale 9.9", "Win incremental profit, not just gross sales", "Compare event revenue versus baseline after promo costs."),
        (10, 10, "Mega Sale 10.10", "Find best promo depth", "A/B test discount levels and keep the strongest net-margin variant."),
        (11, 11, "Singles' Day 11.11", "Capture peak demand efficiently", "Pre-book spend to proven campaigns and throttle losers fast."),
        (11, 29, "Black Friday / Cyber Monday window", "Prevent leakage at peak traffic", "Monitor margin every few hours and enforce stop-loss rules."),
        (12, 12, "Mega Sale 12.12", "Close year with profitable growth", "Use margin-based campaign caps and protect repeat buyers."),
        (12, 24, "Christmas / Year-end gifting", "Monetize gifting demand", "Push gift bundles and prioritize high-LTV customer segments."),
    ]
    out: list[dict[str, str]] = []
    for month, day, name, focus, do_now in events:
        evt = date(d0.year, month, day)
        if evt < d0:
            evt = date(d0.year + 1, month, day)
        days_left = (evt - d0).days
        out.append(
            {
                "date": evt.strftime("%Y-%m-%d"),
                "name": name,
                "days_left": f"D-{days_left}",
                "focus": focus,
                "do_now": do_now,
                "success_check": "Success check: margin % does not drop, net revenue grows, CAC stays in target, refund rate does not spike.",
            }
        )
    out.sort(key=lambda x: x["date"])
    return out[:limit]


def _build_report_payload(dashboard_data: Any) -> dict[str, Any]:
    data = asdict(dashboard_data) if is_dataclass(dashboard_data) else dict(dashboard_data)
    kpis: dict[str, Any] = dict(data.get("kpis") or {})
    opp_summary: dict[str, Any] = dict(data.get("campaign_opportunity_summary") or {})
    risks: list[dict[str, Any]] = [r for r in (data.get("top_campaign_risks") or []) if isinstance(r, dict)]
    camp_summary: list[dict[str, Any]] = [r for r in (data.get("campaign_summary_table") or []) if isinstance(r, dict)]
    insights_raw: list[dict[str, Any]] = [
        r for r in (data.get("enriched_campaign_insights") or data.get("top_campaign_insights") or []) if isinstance(r, dict)
    ]
    insights = _sort_insights(insights_raw)
    top3 = insights[:3]

    top_risks = [
        {
            "campaign": str(r.get("campaign") or "-"),
            "signal": _signal_human(r.get("signal_code")),
            "signal_desc": str(r.get("signal_desc") or _signal_human(r.get("signal_code"))),
            "value": f"{_f(r.get('signal_value')):.2f}",
            "threshold": f"{_f(r.get('threshold_value')):.2f}",
            "severity": str(r.get("severity") or "-").title(),
        }
        for r in risks
    ]

    top_opportunities = []
    for i, ins in enumerate(top3, start=1):
        top_opportunities.append(
            {
                "rank": i,
                "campaign": str(ins.get("campaign") or "-"),
                "title": _decision_title(ins),
                "impact": _impact_text(ins),
                "expected_impact": _impact_range_text(ins),
                "why_now": str(ins.get("why_now") or ""),
                "priority": _priority_label(ins.get("priority")),
                "decision_type": _decision_type(ins),
                "time_to_impact": _time_to_impact(ins),
                "confidence": _confidence(ins),
                "score": f"{_f(ins.get('priority_score')):.1f}",
                "money_basis": _money_basis(ins),
                "decision": _action_text(ins),
            }
        )

    actions: list[dict[str, Any]] = []
    seen_actions: set[str] = set()
    for ins in insights:
        text = _action_text(ins).strip()
        key = text.lower()
        if not text or key in seen_actions:
            continue
        seen_actions.add(key)
        actions.append({"rank": len(actions) + 1, "text": text})
        if len(actions) >= 3:
            break

    appendix_insights = []
    for i, ins in enumerate(insights, start=1):
        appendix_insights.append(
            {
                "idx": i,
                "campaign": str(ins.get("campaign") or "-"),
                "title": str(ins.get("title") or "-"),
                "decision": _action_text(ins),
                "impact": _impact_range_text(ins),
                "type": _decision_type(ins),
                "time_to_impact": _time_to_impact(ins),
                "confidence": _confidence(ins),
            }
        )

    reason_map = _campaign_reason_map(risks, max_reasons=2)
    camp_summary_with_reason: list[dict[str, Any]] = []
    for row in camp_summary:
        campaign = str(row.get("campaign") or "").strip()
        risk_level = str(row.get("risk_level") or "").strip().lower()
        reason = reason_map.get(campaign, "")
        if not reason:
            if risk_level in {"high", "critical"}:
                reason = "High risk based on threshold breaches in current window"
            elif risk_level in {"medium", "moderate"}:
                reason = "Medium risk due to near-threshold performance signals"
            else:
                reason = "-"
        row_with_reason = dict(row)
        row_with_reason["reason"] = reason
        camp_summary_with_reason.append(row_with_reason)

    execution_plan = _execution_plan(insights)
    top_plan = execution_plan[:3]
    recover_7d = sum(_impact_high_from_range(r.get("impact", "")) for r in top_plan if r.get("time_to_impact") == "3-7 days")
    grow_14d = sum(_impact_high_from_range(r.get("impact", "")) for r in top_plan if r.get("time_to_impact") == "7-14 days")
    risk_reduce = sum(_impact_high_from_range(r.get("impact", "")) for r in top_plan if r.get("type") == "RISK")
    total_30 = sum(_impact_high_from_range(r.get("impact", "")) for r in top_plan)

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "file_name": str(data.get("file_name") or ""),
        "upload_id": data.get("upload_id"),
        "kpis": {
            "total_revenue": _fmt_money(kpis.get("total_revenue")),
            "net_revenue": _fmt_money(kpis.get("net_revenue")),
            "aov": _fmt_money(kpis.get("aov")),
            "total_orders": f"{int(_f(kpis.get('total_orders'))):,}",
        },
        "profit_summary": {
            "loss": _fmt_money(opp_summary.get("total_estimated_loss")),
            "opportunity": _fmt_money(opp_summary.get("total_opportunity_size")),
            "top_campaign": str(opp_summary.get("top_priority_campaign") or "-"),
            "short_term_recoverable": _fmt_money(sum(_impact_value(ins) for ins in insights if _time_to_impact(ins) == "3-7 days")),
            "mid_term_growth": _fmt_money(sum(_impact_value(ins) for ins in insights if _time_to_impact(ins) in {"7-14 days", "14-30 days"})),
            "recover_7d": _fmt_money(recover_7d),
            "grow_14d": _fmt_money(grow_14d),
            "risk_reduce": _fmt_money(risk_reduce),
            "total_30d": _fmt_money(total_30),
        },
        "top_opportunities": top_opportunities,
        "top_risks": top_risks,
        "recommended_actions": actions,
        "execution_plan": execution_plan,
        "upcoming_calendar": _upcoming_campaign_calendar(limit=5),
        "campaign_summary_table": camp_summary_with_reason,
        "appendix_insights": appendix_insights,
        "method_note": (
            "Measured values come directly from metrics. "
            "Estimated (proxy) values use deterministic formulas on campaign metrics."
        ),
    }


def export_executive_report_pdf(dashboard_data: Any, output_path: str) -> str:
    """
    Build report payload from existing dashboard data, render HTML template, export PDF.

    Returns the output path.
    """
    if HTML is None or CSS is None:
        raise RuntimeError(
            "WeasyPrint is not available. Install dependency 'weasyprint' to enable HTML-to-PDF export."
        ) from _WEASYPRINT_IMPORT_ERROR

    payload = _build_report_payload(dashboard_data)
    base_dir = Path(__file__).resolve().parents[2]
    templates_dir = base_dir / "templates" / "reports"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("executive_report.html")
    html = template.render(report=payload)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    css_file = templates_dir / "executive_report.css"
    HTML(string=html, base_url=str(base_dir)).write_pdf(str(output), stylesheets=[CSS(filename=str(css_file))])
    return str(output)


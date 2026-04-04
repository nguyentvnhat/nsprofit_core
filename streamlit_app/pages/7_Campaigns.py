"""Campaign dimension view: revenue, discount intensity, and risk by attribution bucket."""

from __future__ import annotations

import html
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from streamlit_pkg_bootstrap import ensure_streamlit_app_package

ensure_streamlit_app_package(ROOT)

import pandas as pd
import streamlit as st

from app.database import session_scope
from app.services.dashboard_service import get_dashboard_data
from streamlit_app.ui_components import (
    apply_saas_theme,
    brand_page_icon,
    fmt_usd,
    prettify_dataframe_columns,
    render_footer,
    render_page_header,
    signal_desc,
    signal_friendly_pair,
)

st.set_page_config(page_title="Campaigns — NosaProfit", page_icon=brand_page_icon(), layout="wide")
apply_saas_theme(current_page="Campaigns")
render_page_header(
    "Campaigns",
    "Compare campaign groups (UTM, landing page, source, discount code) to see where revenue is coming from, where discounts are leaking, and what to fix first.",
)

uid = st.session_state.get("active_upload_id")
dashboard = st.session_state.get("dashboard_data")
if dashboard is None or dashboard.upload_id != uid:
    if uid is None:
        st.warning("Select or process an upload from `Home`.")
        st.stop()
    with session_scope() as session:
        dashboard = get_dashboard_data(session, upload_id=uid)
    st.session_state["dashboard_data"] = dashboard
elif not hasattr(dashboard, "campaign_summary_table") or not hasattr(
    dashboard, "enriched_campaign_insights"
):
    with session_scope() as session:
        dashboard = get_dashboard_data(session, upload_id=uid)
    st.session_state["dashboard_data"] = dashboard

summary_rows = list(getattr(dashboard, "campaign_summary_table", None) or [])
risks_rows = list(getattr(dashboard, "top_campaign_risks", None) or [])
insights_rows = list(getattr(dashboard, "top_campaign_insights", None) or [])
opp_summary = getattr(dashboard, "campaign_opportunity_summary", None) or {}
campaign_results = list(getattr(dashboard, "campaign_results", None) or [])
enriched_all = list(getattr(dashboard, "enriched_campaign_insights", None) or [])

if not summary_rows:
    st.info(
        "No campaign buckets found for this upload. "
        "Re-process the CSV after upgrading, or ensure exports include Source / UTM / Landing / Referring / Discount Code "
        "so orders can be grouped beyond **unknown**."
    )
    render_footer()
    st.stop()

st.caption("Discount rate = discounts ÷ gross revenue, shown as a % for each campaign group. Currency is USD.")

def _build_local_text_pdf_bytes() -> bytes:
    """
    Tiny dependency-free PDF fallback.
    Generates a plain one-page report so local export always works.
    """
    lines: list[str] = []
    lines.append(f"NosaProfit - Campaigns report (upload {uid})")
    lines.append("")
    lines.append(f"Estimated loss (proxy): {fmt_usd(float((opp_summary or {}).get('total_estimated_loss') or 0.0))}")
    lines.append(f"Opportunity (proxy): {fmt_usd(float((opp_summary or {}).get('total_opportunity_size') or 0.0))}")
    lines.append(f"Top campaign: {str((opp_summary or {}).get('top_priority_campaign') or '-')}")
    lines.append("")
    lines.append("NosaProfit - Provider by Uway Technology")
    lines.append("")
    lines.append("Top insights:")
    for i, row in enumerate([r for r in enriched_all if isinstance(r, dict)][:20], start=1):
        camp = str(row.get("campaign") or "unknown")
        title = str(row.get("title") or "Insight")
        impact = str(row.get("estimated_impact_text") or "")
        lines.append(f"{i}. {camp} - {title}")
        if impact:
            lines.append(f"   Impact: {impact}")

    def _esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    y = 810
    content_ops = ["BT", "/F1 10 Tf", "40 810 Td", "14 TL"]
    for ln in lines:
        safe = _esc(ln.encode("latin-1", "replace").decode("latin-1"))
        content_ops.append(f"({safe}) Tj")
        content_ops.append("T*")
        y -= 14
        if y < 40:
            break
    content_ops.append("ET")
    content = "\n".join(content_ops).encode("latin-1", "replace")

    objs: list[bytes] = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objs.append(f"<< /Length {len(content)} >>\nstream\n".encode("latin-1") + content + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("latin-1"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objs)+1}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode("latin-1")
    )
    return bytes(out)

try:
    from streamlit_app.campaigns_report_pdf import build_campaigns_pdf_bytes

    _pdf_bytes = build_campaigns_pdf_bytes(
        upload_id=int(uid),
        file_name=str(getattr(dashboard, "file_name", None) or ""),
        summary_rows=summary_rows,
        enriched_insights=enriched_all,
        risks_rows=risks_rows,
        opp_summary=opp_summary if isinstance(opp_summary, dict) else {},
        signal_label_fn=signal_friendly_pair,
        signal_desc_fn=signal_desc,
    )
except Exception:
    _pdf_bytes = None
    try:
        _pdf_bytes = _build_local_text_pdf_bytes()
    except Exception:
        _pdf_bytes = None
        st.info("PDF export is unavailable in this environment.")

if _pdf_bytes:
    st.download_button(
        label="Download campaigns (PDF)",
        data=_pdf_bytes,
        file_name=f"nosa_campaigns_upload_{uid}.pdf",
        mime="application/pdf",
        help="Summary table, high-severity risks, and enriched insights (up to 35) in one report.",
    )

def _f(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _priority_meta(priority: str) -> tuple[str, str, str]:
    p = str(priority or "").strip().lower()
    if p in {"high", "critical", "warning"}:
        return "High", "#e03131", "#fff5f5"
    if p in {"medium", "moderate", "normal"}:
        return "Medium", "#f08c00", "#fff4e6"
    return "Low", "#2b8a3e", "#ebfbee"


def _sort_insights(rows: list[dict]) -> list[dict]:
    def _speed_score(row: dict) -> int:
        t = _time_to_impact(row)
        return {"3-7 days": 4, "7-14 days": 3, "14-30 days": 2, "30+ days": 1}.get(t, 2)

    def _confidence_score(row: dict) -> int:
        c = _confidence_label(row)
        return {"High": 3, "Medium": 2, "Low": 1}.get(c, 1)

    return sorted(
        rows,
        key=lambda r: (
            -_impact_value(r),
            -_speed_score(r),
            -_confidence_score(r),
            -_f(r.get("priority_score")),
        ),
    )


def _top_actions(rows: list[dict], limit: int = 3) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        action = _money_driven_action(row)
        key = action.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(action)
        if len(out) >= limit:
            break
    return out


def _short_title(title: str, max_words: int = 8) -> str:
    words = str(title or "").split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]) + "..."


def _operator_copy(text: str, max_len: int = 160) -> str:
    raw = " ".join(str(text or "").strip().split())
    if not raw:
        return ""
    raw = re.sub(r"\[(Problem|Impact in numbers|Action)\]\s*", "", raw, flags=re.IGNORECASE)
    raw = raw.replace("c Impact:", "Impact:")
    for bad, good in (
        ("appears to be", "is"),
        ("appears", "is"),
        ("suggests that", "shows"),
        ("suggests", "shows"),
        ("may indicate", "indicates"),
        ("driven by healthier basket economics", "with stronger basket value"),
    ):
        raw = raw.replace(bad, good).replace(bad.title(), good.capitalize())
    first = raw.split(".")[0].strip()
    out = first if first else raw
    if len(out) > max_len:
        out = out[: max_len - 1].rstrip() + "..."
    return out


def _clean_long_text(text: str, max_len: int = 500) -> str:
    raw = " ".join(str(text or "").strip().split())
    raw = re.sub(r"\[(Problem|Impact in numbers|Action)\]\s*", "", raw, flags=re.IGNORECASE)
    raw = raw.replace("c Impact:", "Impact:")
    if len(raw) > max_len:
        return raw[: max_len - 1].rstrip() + "..."
    return raw


def _impact_tone(row: dict) -> tuple[str, str]:
    loss = _f(row.get("estimated_loss"))
    opp = _f(row.get("opportunity_size"))
    if loss > 0 and loss >= opp:
        return "#e03131", "#fff5f5"
    if opp > 0:
        return "#2b8a3e", "#ebfbee"
    return "#6b7280", "#f8f9fa"


def _impact_basis(row: dict) -> tuple[str, str]:
    """
    Return (basis_code, display_label) describing whether money number is measured or proxy.
    """
    code = str(row.get("signal_code") or "").upper()
    title = str(row.get("title") or "").lower()
    loss = max(_f(row.get("estimated_loss")), 0.0)
    opp = max(_f(row.get("opportunity_size")), 0.0)
    blob = f"{code} {title}"

    if "REFUND" in blob and loss > 0:
        return "measured_refunds", "Measured"
    if ("PRICING" in blob or "DISCOUNT" in blob or "AOV" in blob or "LOW_ORDER_VALUE" in blob or "UNSTABLE" in blob or "VOLUME_DRIVEN" in blob) and (loss > 0 or opp > 0):
        return "estimated_proxy_formula", "Estimated (proxy)"
    if "CONCENTRATION" in blob or "DEPENDENCY" in blob or "LOW_REPEAT" in blob or "REPEAT" in blob:
        return "estimated_proxy_exposure", "Estimated (proxy)"
    return "no_direct_dollar_model", "Estimated (proxy)"


def _basis_note(row: dict) -> str:
    basis, _ = _impact_basis(row)
    if basis == "measured_refunds":
        return "Basis: measured refund amount from revenue metrics."
    if basis == "estimated_proxy_formula":
        return "Basis: deterministic proxy from campaign metrics (discount/AOV/growth formulas)."
    if basis == "estimated_proxy_exposure":
        return "Basis: exposure proxy from impacted revenue (5-10% guardrail)."
    return "Basis: no direct dollar model; qualitative risk only."


def _money_driven_action(row: dict) -> str:
    """Operator-style action with explicit dollar impact (direct or proxy)."""
    code = str(row.get("signal_code") or "").upper()
    title = str(row.get("title") or "").lower()
    campaign = str(row.get("campaign") or "this campaign")
    loss = max(_f(row.get("estimated_loss")), 0.0)
    opp = max(_f(row.get("opportunity_size")), 0.0)
    revenue = max(_f(row.get("impacted_revenue")), _f(row.get("revenue")))
    blob = f"{code} {title}"

    if "STACK" in blob or "DISCOUNT" in blob:
        base = f"Reduce discount stacking in {campaign}"
    elif "AOV" in blob or "LOW_ORDER_VALUE" in blob or "order value" in blob:
        base = f"Increase AOV in {campaign}"
    elif "UNSTABLE" in blob or "VOLAT" in blob:
        base = f"Stabilize revenue pacing in {campaign}"
    elif "CONCENTRATION" in blob or "DEPENDENCY" in blob:
        base = f"Diversify channels/SKUs in {campaign}"
    elif "LOW_REPEAT" in blob or "REPEAT" in blob:
        base = f"Lift repeat rate in {campaign}"
    elif "BUNDLE" in blob or "PAIR" in blob:
        base = f"Launch bundle/paired offer in {campaign}"
    elif "SHIPPING" in blob or "FREE_SHIP" in blob or "THRESHOLD" in blob:
        base = f"Adjust free-shipping threshold and cart nudges in {campaign}"
    elif "REFUND" in blob or "RETURN" in blob:
        base = f"Reduce refund drivers in {campaign}"
    else:
        fallback = str(row.get("action") or "").strip()
        if fallback:
            fallback = re.sub(r"(?i)^action:\s*", "", fallback).strip(" .")
            base = f"{fallback} in {campaign}" if campaign.lower() not in fallback.lower() else fallback
        else:
            base = f"Tighten targeting and offer design in {campaign}"

    if loss > 0:
        return f"{base} -> protect {fmt_usd(loss)}"
    if opp > 0:
        return f"{base} -> gain {fmt_usd(opp)}"

    # Proxy when direct dollar impact is not available.
    if revenue <= 0:
        return f"{base} -> protect {fmt_usd(0)} (directional)"
    if "CONCENTRATION" in blob or "DEPENDENCY" in blob:
        proxy = revenue * 0.05
        return f"Protect ~{fmt_usd(proxy)} revenue exposure by diversifying channels in {campaign}"
    if "LOW_REPEAT" in blob or "REPEAT" in blob:
        proxy = revenue * 0.08  # 5-10% proxy midpoint
        return f"Recover ~{fmt_usd(proxy)} by increasing repeat mix in {campaign}"
    proxy = revenue * 0.05
    return f"Protect ~{fmt_usd(proxy)} in {campaign} by tightening campaign controls"


def _impact_numbers(row: dict) -> tuple[float, float]:
    loss = max(_f(row.get("estimated_loss")), 0.0)
    opp = max(_f(row.get("opportunity_size")), 0.0)
    if loss > 0 or opp > 0:
        return loss, opp
    revenue = max(_f(row.get("impacted_revenue")), _f(row.get("revenue")))
    code = str(row.get("signal_code") or "").upper()
    title = str(row.get("title") or "").lower()
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


def _impact_value(row: dict) -> float:
    lo, hi = _impact_numbers(row)
    return max(lo, hi)


def _impact_display(row: dict) -> tuple[str, str]:
    loss, opp = _impact_numbers(row)
    if loss > 0 and loss >= opp:
        return f"-{fmt_usd(loss)} loss", "loss"
    if opp > 0 and opp > loss:
        return f"+{fmt_usd(opp)} opportunity", "opportunity"
    lo, hi = _impact_numbers(row)
    if lo > 0 and hi > lo:
        return f"Protect {fmt_usd(lo)}-{fmt_usd(hi)} at risk", "range"
    return f"Protect {fmt_usd(max(lo, hi))} at risk", "range"


def _decision_type(row: dict) -> str:
    blob = f"{str(row.get('signal_code') or '').upper()} {str(row.get('title') or '').lower()}"
    if "STACK" in blob or "DISCOUNT" in blob or "REFUND" in blob or "CONCENTRATION" in blob or "DEPENDENCY" in blob:
        return "RISK"
    if "AOV" in blob or "BUNDLE" in blob or "SHIPPING" in blob or "REPEAT" in blob:
        return "GROWTH"
    return "QUICK WIN"


def _type_badge_style(decision_type: str) -> tuple[str, str]:
    t = str(decision_type or "").upper()
    if t == "RISK":
        return "#fff5f5", "#c92a2a"
    if t == "GROWTH":
        return "#ebfbee", "#2b8a3e"
    return "#fff4e6", "#d9480f"


def _time_to_impact(row: dict) -> str:
    blob = f"{str(row.get('signal_code') or '').upper()} {str(row.get('title') or '').lower()}"
    if "STACK" in blob or "DISCOUNT" in blob or "SHIPPING" in blob:
        return "3-7 days"
    if "AOV" in blob or "BUNDLE" in blob or "REPEAT" in blob:
        return "7-14 days"
    if "CONCENTRATION" in blob or "DEPENDENCY" in blob:
        return "14-30 days"
    return "7-14 days"


def _confidence_label(row: dict) -> str:
    basis, _ = _impact_basis(row)
    blob = f"{str(row.get('signal_code') or '').upper()} {str(row.get('title') or '').lower()}"
    if basis == "measured_refunds":
        return "High"
    if "DISCOUNT" in blob or "AOV" in blob or "UNSTABLE" in blob or "REFUND" in blob:
        return "Medium"
    return "Low"


def _decision_title(row: dict) -> str:
    blob = f"{str(row.get('signal_code') or '').upper()} {str(row.get('title') or '').lower()}"
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


def _what_to_do(row: dict) -> str:
    txt = _money_driven_action(row)
    return txt.split("->")[0].strip()


def _time_weight(time_to_impact: str) -> float:
    return {"3-7 days": 1.0, "7-14 days": 1.35, "14-30 days": 1.8, "30+ days": 2.4}.get(time_to_impact, 1.5)


def _confidence_weight(confidence: str) -> float:
    return {"High": 1.0, "Medium": 0.75, "Low": 0.5}.get(confidence, 0.6)


def _impact_range(value: float, confidence: str) -> tuple[float, float]:
    if confidence == "High":
        return value * 0.85, value * 1.05
    if confidence == "Medium":
        return value * 0.60, value * 1.15
    return value * 0.35, value * 1.35


def _decision_category(row: dict) -> str:
    blob = f"{str(row.get('signal_code') or '').upper()} {str(row.get('title') or '').lower()}"
    if "DISCOUNT" in blob or "STACK" in blob or "PRICING" in blob:
        return "Pricing / Discount"
    if "AOV" in blob or "BUNDLE" in blob or "SHIPPING" in blob:
        return "AOV / Cart"
    if "REPEAT" in blob or "REFUND" in blob or "RETURN" in blob:
        return "Retention"
    return "Channel / Risk"


def _urgency_label(time_to_impact: str) -> str:
    if time_to_impact == "3-7 days":
        return "Do now (this week)"
    if time_to_impact == "7-14 days":
        return "Next 2 weeks"
    return "Strategic follow-up"


def _why_this_happening(row: dict) -> list[str]:
    out: list[str] = []
    share_pct = _f(row.get("affected_revenue_share")) * 100.0
    if share_pct > 0:
        out.append(f"{share_pct:.1f}% of revenue in view is exposed to this issue.")
    discount_pct = _f(row.get("discount_rate")) * 100.0
    if discount_pct > 0:
        out.append(f"Current discount rate is {discount_pct:.1f}% in this campaign.")
    signal_val = _f(row.get("signal_value"))
    threshold = _f(row.get("threshold_value"))
    if signal_val > 0 and threshold > 0:
        out.append(f"Signal {signal_val:.2f} is beyond threshold {threshold:.2f}.")
    if not out:
        out.append(_operator_copy(str(row.get("why_now") or ""), max_len=120) or "Campaign structure is reducing profit capture.")
    return out[:2]


def _next_steps(row: dict) -> list[str]:
    blob = f"{str(row.get('signal_code') or '').upper()} {str(row.get('title') or '').lower()}"
    if "SHIPPING" in blob or "AOV" in blob:
        return [
            "Set free-shipping threshold 10-15% above current AOV.",
            "Launch a 2-item bundle offer on top-selling SKUs.",
            "Stop low-AOV ad sets that miss margin floor.",
        ]
    if "DISCOUNT" in blob or "STACK" in blob:
        return [
            "Set max discount cap by campaign and channel.",
            "Stop overlapping vouchers on same checkout.",
            "Move spend to campaigns with better net margin.",
        ]
    if "CONCENTRATION" in blob or "DEPENDENCY" in blob:
        return [
            "Shift 20% budget to the second-best channel.",
            "Launch one additional product set for this campaign.",
            "Set spend stop-rule if one source exceeds risk limit.",
        ]
    if "REPEAT" in blob or "RETENTION" in blob:
        return [
            "Launch repeat offer to last 30-day buyers.",
            "Set reminder flow at day 14 and day 28.",
            "Add bundle add-on for repeat cohorts only.",
        ]
    return [
        "Set campaign margin floor and enforce daily checks.",
        "Stop low-margin ad sets by end of day.",
        "Reallocate spend to top net-margin campaign cells.",
    ]


def _build_decisions(rows: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for row in rows:
        decision = _decision_title(row)
        d_type = _decision_type(row)
        tti = _time_to_impact(row)
        conf = _confidence_label(row)
        impact_val = _impact_value(row)
        if impact_val <= 0:
            continue
        key = decision.lower().strip()
        if key not in merged:
            merged[key] = {
                "decision": decision,
                "campaigns": {str(row.get("campaign") or "unknown")},
                "type": d_type,
                "time_to_impact": tti,
                "confidence": conf,
                "impact_value": impact_val,
                "why": _why_this_happening(row),
                "steps": _next_steps(row),
                "category": _decision_category(row),
                "priority_label": str(row.get("priority") or "low").upper(),
            }
        else:
            cur = merged[key]
            cur["campaigns"].add(str(row.get("campaign") or "unknown"))
            cur["impact_value"] = float(cur["impact_value"]) + impact_val
            why = list(cur["why"])
            for line in _why_this_happening(row):
                if line not in why:
                    why.append(line)
            cur["why"] = why[:2]
            conf_w = _confidence_weight(str(cur["confidence"]))
            new_w = _confidence_weight(conf)
            if new_w > conf_w:
                cur["confidence"] = conf
            if _time_weight(tti) < _time_weight(str(cur["time_to_impact"])):
                cur["time_to_impact"] = tti

    out: list[dict] = []
    for item in merged.values():
        conf = str(item["confidence"])
        tti = str(item["time_to_impact"])
        impact_val = float(item["impact_value"])
        low, high = _impact_range(impact_val, conf)
        score = impact_val * _confidence_weight(conf) / _time_weight(tti)
        out.append(
            {
                **item,
                "campaigns": ", ".join(sorted(item["campaigns"])),
                "impact_low": low,
                "impact_high": high,
                "priority_score": score,
                "urgency": _urgency_label(tti),
            }
        )
    out.sort(key=lambda x: (-float(x["priority_score"]), -float(x["impact_value"])))
    return out


def _pick_top_3(decisions: list[dict]) -> list[dict]:
    picks: list[dict] = []
    used_idx: set[int] = set()
    for target in ("QUICK WIN", "GROWTH", "RISK"):
        idx = next((i for i, d in enumerate(decisions) if i not in used_idx and d["type"] == target), None)
        if idx is not None:
            used_idx.add(idx)
            picks.append(decisions[idx])
    for i, d in enumerate(decisions):
        if len(picks) >= 3:
            break
        if i in used_idx:
            continue
        used_idx.add(i)
        picks.append(d)
    return picks[:3]


def _upcoming_campaign_calendar(today: date | None = None, limit: int = 6) -> list[dict[str, str]]:
    d0 = today or date.today()
    # Mixed retail calendar (VN + ecommerce shopping events), deterministic and timezone-agnostic.
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
        year = d0.year
        try:
            evt = date(year, month, day)
        except ValueError:
            continue
        if evt < d0:
            evt = date(year + 1, month, day)
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


sorted_insights = _sort_insights([r for r in insights_rows if isinstance(r, dict)])
decisions = _build_decisions(sorted_insights)
top_3 = _pick_top_3(decisions)

total_loss = _f((opp_summary or {}).get("total_estimated_loss"))
total_opp = _f((opp_summary or {}).get("total_opportunity_size"))
top_campaign_name = str((opp_summary or {}).get("top_priority_campaign") or "—")
hero_title = (
    f"You are losing {fmt_usd(total_loss)} from your campaigns"
    if total_loss > 0
    else f"You have {fmt_usd(total_opp)} in recoverable profit opportunities"
)
st.markdown(
    (
        "<div style='border:1px solid #e5e7eb; border-left:8px solid #e03131; border-radius:12px;"
        "padding:16px 18px; background:#fff;'>"
        f"<div style='font-size:1.55rem; font-weight:800; line-height:1.25;'>{html.escape(hero_title)}</div>"
        f"<div style='margin-top:10px; color:#4b5563;'>"
        f"Estimated loss: <strong>{fmt_usd(total_loss)}</strong> &nbsp;|&nbsp; "
        f"Opportunity: <strong>{fmt_usd(total_opp)}</strong> &nbsp;|&nbsp; "
        f"Top campaign: <strong>{html.escape(top_campaign_name)}</strong>"
        "</div></div>"
    ),
    unsafe_allow_html=True,
)
st.caption("Money labels: 'Measured' uses direct totals; 'Estimated' is a directional model based on your campaign metrics.")

quick_wins_value = sum(float(d["impact_high"]) for d in decisions if d["time_to_impact"] == "3-7 days")
s1, s2, s3, s4 = st.columns(4)
s1.metric("Revenue at risk", fmt_usd(total_loss))
s2.metric("Growth opportunity", fmt_usd(total_opp))
s3.metric("Quick wins available", fmt_usd(quick_wins_value))
s4.metric("Highest-priority campaign", top_campaign_name)

recover_7d = sum(float(d["impact_high"]) for d in top_3 if d["time_to_impact"] == "3-7 days")
grow_14d = sum(float(d["impact_high"]) for d in top_3 if d["time_to_impact"] == "7-14 days")
risk_reduce = sum(float(d["impact_high"]) for d in top_3 if d["type"] == "RISK")
total_30d = sum(float(d["impact_high"]) for d in top_3)
st.markdown("#### Execution impact if you act now")
e1, e2, e3, e4 = st.columns(4)
e1.metric("Recover (0-7 days)", fmt_usd(recover_7d))
e2.metric("Grow (7-14 days)", fmt_usd(grow_14d))
e3.metric("Reduce risk", fmt_usd(risk_reduce))
e4.metric("Total impact (30 days)", fmt_usd(total_30d))

st.markdown("### Top profit decisions")
if not top_3:
    st.info("No decision-ready campaign items in the current slice.")
else:
    cols = st.columns(3)
    for idx, col in enumerate(cols):
        if idx >= len(top_3):
            continue
        row = top_3[idx]
        label, badge_color, _ = _priority_meta(str(row.get("priority_label") or "low"))
        decision_type = str(row["type"])
        tti = str(row["time_to_impact"])
        conf = str(row["confidence"])
        urgency = str(row["urgency"])
        type_bg, type_fg = _type_badge_style(decision_type)
        tone_color, tone_bg = ("#e03131", "#fff5f5") if decision_type == "RISK" else ("#2b8a3e", "#ebfbee")
        camp = html.escape(str(row["campaigns"]))
        title = html.escape(str(row["decision"]))
        impact = f"{fmt_usd(float(row['impact_low']))} - {fmt_usd(float(row['impact_high']))} (confidence-adjusted)"
        why_now = html.escape(" ".join(row["why"]))
        score = float(row["priority_score"])
        do_now = html.escape(str(row["steps"][0]))
        type_bg, type_fg = _type_badge_style(decision_type)
        with col:
            st.markdown(
                (
                    "<div style='border:1px solid #e9ecef; border-left:6px solid "
                    f"{tone_color}; border-radius:10px; padding:12px; background:{tone_bg}; min-height:228px;'>"
                    f"<div style='display:flex;justify-content:space-between;gap:8px;'>"
                    f"<strong>#{idx + 1} · {camp}</strong>"
                    f"<span style='background:{badge_color};color:#fff;padding:2px 8px;border-radius:999px;font-size:12px;'>{label}</span>"
                    "</div>"
                    f"<div style='margin-top:6px;font-size:14px;'>{title}</div>"
                    f"<div style='margin-top:10px;font-size:23px;font-weight:800;color:{tone_color};'>{html.escape(impact)}</div>"
                    f"<div style='margin-top:6px;font-size:11px;color:#334155;'>Type: "
                    f"<span style='background:{type_bg}; color:{type_fg}; border:1px solid {type_fg}; "
                    f"padding:1px 6px; border-radius:999px; font-weight:700;'>{decision_type}</span>"
                    f" &nbsp;|&nbsp; "
                    f"Priority: <strong>{label.upper()}</strong></div>"
                    f"<div style='margin-top:2px;font-size:11px;color:#334155;'>Time to impact: <strong>{tti}</strong> &nbsp;|&nbsp; "
                    f"Confidence: <strong>{conf}</strong> &nbsp;|&nbsp; When to act: <strong>{urgency}</strong></div>"
                    f"<div style='margin-top:8px;font-size:12px;color:#495057;'>Score {score:.1f}</div>"
                    f"<div style='margin-top:8px;font-size:12px;color:#495057;'>{why_now}</div>"
                    f"<div style='margin-top:6px;font-size:12px;color:#0f172a;'><strong>What to do:</strong> {do_now}</div>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )

st.markdown("### Priority execution plan")
if not top_3:
    st.caption("No action text available in current insight slice.")
else:
    for i, d in enumerate(top_3, start=1):
        st.markdown(f"**#{i} {d['urgency']} · {d['decision']}**")
        st.caption(
            f"{fmt_usd(float(d['impact_low']))} - {fmt_usd(float(d['impact_high']))} | "
            f"{d['time_to_impact']} | {d['confidence']}"
        )
        for sidx, step in enumerate(d["steps"], start=1):
            st.markdown(f"{sidx}. {step}")

st.markdown("### Upcoming special dates (execution + margin measurement)")
for ev in _upcoming_campaign_calendar(limit=5):
    st.markdown(f"**{ev['days_left']} · {ev['date']} · {ev['name']}**")
    st.caption(f"Goal: {ev['focus']}")
    st.caption(f"Do now: {ev['do_now']}")
    st.caption(ev["success_check"])

st.divider()
with st.expander("Top campaign decisions (ranked)", expanded=False):
    if not decisions:
        st.info("No campaign-level decisions in the ranked top slice.")
    else:
        grouped: dict[str, list[dict]] = {"Pricing / Discount": [], "AOV / Cart": [], "Retention": [], "Channel / Risk": []}
        for d in decisions:
            grouped.setdefault(str(d["category"]), []).append(d)
        for grp in ("Pricing / Discount", "AOV / Cart", "Retention", "Channel / Risk"):
            rows = grouped.get(grp) or []
            if not rows:
                continue
            st.markdown(f"#### {grp}")
            for row in rows:
                label, badge_color, _ = _priority_meta(str(row.get("priority_label") or "low"))
                decision_type = str(row["type"])
                type_bg, type_fg = _type_badge_style(decision_type)
                tone_color, tone_bg = ("#e03131", "#fff5f5") if decision_type == "RISK" else ("#2b8a3e", "#ebfbee")
                rank = decisions.index(row) + 1
                impact_txt = f"{fmt_usd(float(row['impact_low']))} - {fmt_usd(float(row['impact_high']))} (confidence-adjusted)"
                with st.container(border=True):
                    st.markdown(
                        (
                            "<div style='border-left:6px solid "
                            f"{tone_color}; background:{tone_bg}; border-radius:8px; padding:10px 12px; margin-bottom:8px;'>"
                            f"<div style='display:flex;justify-content:space-between;gap:8px; align-items:center;'>"
                            f"<div><strong>#{rank} {row['campaigns']} — {row['decision']}</strong><br/>score {float(row['priority_score']):.1f}</div>"
                            f"<span style='background:{badge_color};color:#fff;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;'>{label}</span>"
                            "</div>"
                            "</div>"
                        ),
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"<div style='font-size:22px; font-weight:800; color:{tone_color}; margin-bottom:8px;'>{impact_txt}</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        (
                            f"<div style='font-size:12px; color:#475569; margin-bottom:4px;'>"
                            f"Type: <span style='background:{type_bg}; color:{type_fg}; border:1px solid {type_fg}; "
                            f"padding:1px 6px; border-radius:999px; font-weight:700;'>{decision_type}</span>"
                            f" &nbsp;|&nbsp; Priority: <strong>{label.upper()}</strong>"
                            f" &nbsp;|&nbsp; Time to impact: <strong>{row['time_to_impact']}</strong>"
                            f" &nbsp;|&nbsp; Confidence: <strong>{row['confidence']}</strong>"
                            f" &nbsp;|&nbsp; When to act: <strong>{row['urgency']}</strong>"
                            f"</div>"
                        ),
                        unsafe_allow_html=True,
                    )
                    for why in row["why"]:
                        st.caption(f"Why: {why}")
                    st.markdown("**What to do next:**")
                    for sidx, step in enumerate(row["steps"], start=1):
                        st.markdown(f"{sidx}. {step}")

st.divider()
df = pd.DataFrame(summary_rows)
if not df.empty and "discount_rate" in df.columns:
    df = df.copy()
    df["discount_pct"] = (df["discount_rate"].astype(float) * 100.0).round(2)
    df = df.drop(columns=["discount_rate"], errors="ignore")

display_df = prettify_dataframe_columns(df)
with st.expander("Campaign summary table", expanded=False):
    st.dataframe(
        display_df,
        use_container_width=True,
        height=min(420, 48 + len(summary_rows) * 36),
        hide_index=True,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Campaign buckets", len(summary_rows))
    if not df.empty and "orders" in df.columns:
        c2.metric("Orders in view", int(df["orders"].sum()))
    if not df.empty and "net_revenue" in summary_rows[0]:
        total_net = sum(float(r.get("net_revenue") or 0) for r in summary_rows)
        c3.metric("Net revenue (summed)", fmt_usd(total_net))

with st.expander("High-severity signals table", expanded=False):
    if not risks_rows:
        st.info("No high-severity campaign-level signals in the current top slice.")
    else:
        rdf = pd.DataFrame(risks_rows)
        if not rdf.empty and "signal_code" in rdf.columns:
            rdf = rdf.copy()
            rdf.insert(
                0,
                "plain_language",
                rdf["signal_code"].map(lambda c: signal_friendly_pair(str(c))[0]),
            )
            rdf.insert(
                1,
                "signal_desc",
                rdf["signal_code"].map(lambda c: signal_desc(str(c))),
            )
        cols = [
            c
            for c in (
                "campaign",
                "plain_language",
                "signal_desc",
                "severity",
                "entity_type",
                "signal_value",
                "threshold_value",
            )
            if c in rdf.columns
        ]
        if cols:
            st.dataframe(
                prettify_dataframe_columns(rdf[cols]),
                use_container_width=True,
                hide_index=True,
                height=280,
            )

with st.expander("Per-campaign detail (pick a bucket)"):
    if not campaign_results:
        st.write("No detailed payloads.")
    else:
        labels = [str(r.get("campaign") or "unknown") for r in campaign_results]
        choice = st.selectbox("Campaign", options=labels, index=0)
        picked = next((r for r in campaign_results if str(r.get("campaign")) == choice), None)
        if picked and isinstance(picked, dict):
            summ = picked.get("summary") or {}
            st.markdown(
                f"**Orders:** {picked.get('order_count', 0)} · "
                f"**Net revenue:** {fmt_usd(float(summ.get('net_revenue') or 0))} · "
                f"**Risk:** {str(summ.get('risk_level') or 'low').title()}"
            )
            sig_n = len(picked.get("signals") or [])
            ins_n = len(picked.get("insights") or [])
            st.caption(f"{sig_n} signals · {ins_n} insights in this bucket.")

            st.markdown("##### Bucket KPIs")
            dr = float(summ.get("discount_rate") or 0)
            bk1, bk2, bk3, bk4 = st.columns(4)
            bk1.metric("Gross revenue", fmt_usd(float(summ.get("revenue") or 0)))
            bk2.metric("Net revenue", fmt_usd(float(summ.get("net_revenue") or 0)))
            bk3.metric("Discount ÷ gross", f"{dr * 100:.2f}%")
            bk4.metric("AOV", fmt_usd(float(summ.get("aov") or 0)))

            st.markdown("##### Signals in this bucket")
            sig_rows: list[dict] = []
            for s in picked.get("signals") or []:
                if not isinstance(s, dict):
                    continue
                sv = s.get("signal_value")
                tv = s.get("threshold_value")
                try:
                    sv_f = float(sv) if sv is not None else None
                except (TypeError, ValueError):
                    sv_f = None
                try:
                    tv_f = float(tv) if tv is not None else None
                except (TypeError, ValueError):
                    tv_f = None
                _code = str(s.get("signal_code") or "")
                _plab, _ = signal_friendly_pair(_code)
                sig_rows.append(
                    {
                        "plain_language": _plab,
                        "signal_desc": signal_desc(_code),
                        "severity": s.get("severity"),
                        "category": s.get("category"),
                        "signal_value": sv_f,
                        "threshold_value": tv_f,
                        "entity_type": s.get("entity_type"),
                    }
                )
            if not sig_rows:
                st.caption("No signals in this bucket.")
            else:
                sdf = pd.DataFrame(sig_rows)
                st.dataframe(
                    prettify_dataframe_columns(sdf),
                    use_container_width=True,
                    hide_index=True,
                    height=min(360, 48 + len(sig_rows) * 36),
                )

            st.markdown("##### Insights in this bucket")
            enriched_for = [r for r in enriched_all if str(r.get("campaign") or "") == choice]
            enriched_for.sort(key=lambda r: int(float(r.get("rank") or 9999)))

            if enriched_for:
                for row in enriched_for:
                    title = str(row.get("title") or "Insight")
                    rk = row.get("rank", "")
                    sc = row.get("priority_score", "")
                    head = f"#{rk} · score {sc}" if rk != "" and sc != "" else ""
                    with st.expander(f"**{title}**  \n_{head}_"):
                        st.markdown(f"**Why now:** {_clean_long_text(str(row.get('why_now') or ''), max_len=420)}")
                        im1, im2, im3, im4 = st.columns(4)
                        im1.metric("Impacted revenue", fmt_usd(float(row.get("impacted_revenue") or 0)))
                        im2.metric("Est. loss (proxy)", fmt_usd(float(row.get("estimated_loss") or 0)))
                        im3.metric("Opportunity (proxy)", fmt_usd(float(row.get("opportunity_size") or 0)))
                        im4.metric(
                            "Share of revenue in view",
                            f"{float(row.get('affected_revenue_share') or 0) * 100:.1f}%",
                        )
                        st.markdown(str(row.get("summary") or ""))
                        _sc2 = str(row.get("signal_code") or "")
                        _slab2, _shlp2 = signal_friendly_pair(_sc2)
                        st.caption(
                            f"Priority: {str(row.get('priority') or '').title()} · "
                            f"{str(row.get('category') or '')}"
                        )
                        st.markdown(f"**Signal:** {_slab2}")
                        if _shlp2:
                            st.caption(_shlp2)
            else:
                for ins in picked.get("insights") or []:
                    if not isinstance(ins, dict):
                        continue
                    with st.expander(str(ins.get("title") or "Insight")):
                        st.markdown(str(ins.get("summary") or ""))
                        st.caption(
                            f"Priority: {str(ins.get('priority') or '')} · {str(ins.get('category') or '')}"
                        )

st.caption("NosaProfit - Provider by Uway Technology")
render_footer()

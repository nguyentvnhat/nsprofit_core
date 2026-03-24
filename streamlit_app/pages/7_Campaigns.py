"""Campaign dimension view: revenue, discount intensity, and risk by attribution bucket."""

from __future__ import annotations

import html
import sys
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
    signal_friendly_pair,
)

st.set_page_config(page_title="Campaigns — NosaProfit", page_icon=brand_page_icon(), layout="wide")
apply_saas_theme(current_page="Campaigns")
render_page_header(
    "Campaigns",
    "Compare attribution buckets (UTM, landing, source, discount code) using the same metrics, signals, and rules as store-level analysis.",
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

st.caption("Discount rate = discounts ÷ gross revenue (0–1) within each bucket. Currency amounts are USD.")

try:
    from streamlit_app.campaigns_report_pdf import build_campaigns_pdf_bytes

    _pdf_bytes = build_campaigns_pdf_bytes(
        upload_id=int(uid),
        summary_rows=summary_rows,
        enriched_insights=enriched_all,
        risks_rows=risks_rows,
        opp_summary=opp_summary if isinstance(opp_summary, dict) else {},
        signal_label_fn=signal_friendly_pair,
    )
except Exception as exc:
    _pdf_bytes = None
    st.info(f"PDF export is unavailable in this environment ({exc}). Install dependencies to enable it.")

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
    return sorted(
        rows,
        key=lambda r: (
            -_f(r.get("priority_score")),
            -(_f(r.get("estimated_loss")) + _f(r.get("opportunity_size"))),
            -_f(r.get("impacted_revenue")),
        ),
    )


def _top_actions(rows: list[dict], limit: int = 3) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        action = str(row.get("action") or "").strip()
        if not action:
            continue
        key = action.lower()
        if key in seen:
            continue
        seen.add(key)
        camp = str(row.get("campaign") or "unknown")
        out.append(f"{action} (campaign: {camp})")
        if len(out) >= limit:
            break
    return out


sorted_insights = _sort_insights([r for r in insights_rows if isinstance(r, dict)])
top_3 = sorted_insights[:3]

st.subheader("Top campaign opportunities")
if not top_3:
    st.info("No campaign-level insights in the ranked top slice.")
else:
    cols = st.columns(3)
    for idx, col in enumerate(cols):
        if idx >= len(top_3):
            continue
        row = top_3[idx]
        label, color, bg = _priority_meta(str(row.get("priority") or "low"))
        camp = html.escape(str(row.get("campaign") or "unknown"))
        title = html.escape(str(row.get("title") or "Insight"))
        impact = html.escape(str(row.get("estimated_impact_text") or "No separate dollar proxy on this signal"))
        why_now = html.escape(str(row.get("why_now") or "")[:190])
        score = _f(row.get("priority_score"))
        with col:
            st.markdown(
                (
                    "<div style='border:1px solid #e9ecef; border-left:6px solid "
                    f"{color}; border-radius:10px; padding:12px; background:{bg}; min-height:230px;'>"
                    f"<div style='display:flex;justify-content:space-between;gap:8px;'>"
                    f"<strong>#{idx + 1} · {camp}</strong>"
                    f"<span style='background:{color};color:#fff;padding:2px 8px;border-radius:999px;font-size:12px;'>{label}</span>"
                    "</div>"
                    f"<div style='margin-top:6px;font-size:14px;'>{title}</div>"
                    f"<div style='margin-top:10px;font-size:21px;font-weight:700;color:#1f2937;'>{impact}</div>"
                    f"<div style='margin-top:8px;font-size:12px;color:#495057;'>Score {score:.1f}</div>"
                    f"<div style='margin-top:8px;font-size:12px;color:#495057;'>{why_now}</div>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )

if isinstance(opp_summary, dict) and opp_summary:
    r1, r2, r3 = st.columns(3)
    r1.metric("Est. leakage (proxy)", fmt_usd(_f(opp_summary.get("total_estimated_loss"))))
    r2.metric("Opportunity (proxy)", fmt_usd(_f(opp_summary.get("total_opportunity_size"))))
    top_t = str(opp_summary.get("top_priority_title") or "—")
    top_c = str(opp_summary.get("top_priority_campaign") or "—")
    r3.metric("Top priority", top_t[:48] + ("…" if len(top_t) > 48 else ""), help=f"Campaign: {top_c}")

st.markdown("#### Recommended actions")
actions = _top_actions(sorted_insights, limit=3)
if not actions:
    st.caption("No action text available in current insight slice.")
else:
    for i, a in enumerate(actions, start=1):
        st.markdown(f"{i}. {a}")

st.divider()
st.subheader("Top campaign insights (ranked)")
if not sorted_insights:
    st.info("No campaign-level insights in the ranked top slice.")
else:
    for row in sorted_insights:
        label, color, bg = _priority_meta(str(row.get("priority") or "low"))
        camp = str(row.get("campaign") or "unknown")
        title = str(row.get("title") or "Insight")
        rank = int(_f(row.get("rank"), default=0))
        score = _f(row.get("priority_score"))
        impact_txt = str(row.get("estimated_impact_text") or "No separate dollar proxy on this signal")
        share_pct = _f(row.get("affected_revenue_share")) * 100.0
        signal_code = str(row.get("signal_code") or "")
        signal_label, signal_help = signal_friendly_pair(signal_code)

        with st.container(border=True):
            st.markdown(
                (
                    "<div style='border-left:6px solid "
                    f"{color}; background:{bg}; border-radius:8px; padding:10px 12px; margin-bottom:8px;'>"
                    f"<div style='display:flex;justify-content:space-between;gap:8px; align-items:center;'>"
                    f"<div><strong>{camp} — {title}</strong><br/># {rank} · score {score:.1f}</div>"
                    f"<span style='background:{color};color:#fff;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;'>{label}</span>"
                    "</div>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )

            st.markdown(
                f"<div style='font-size:21px; font-weight:700; color:#1f2937; margin-bottom:8px;'>{html.escape(impact_txt)}</div>",
                unsafe_allow_html=True,
            )
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Impacted revenue", fmt_usd(_f(row.get("impacted_revenue"))))
            m2.metric("Estimated loss", fmt_usd(_f(row.get("estimated_loss"))))
            m3.metric("Opportunity size", fmt_usd(_f(row.get("opportunity_size"))))
            m4.metric("Share of revenue", f"{share_pct:.1f}%")

            st.markdown(f"**Why now:** {str(row.get('why_now') or '')}")
            st.caption(
                f"Priority: {label} · {str(row.get('category') or '')} · Signal: {signal_label}"
            )
            if signal_help:
                st.caption(signal_help)
            if str(row.get("summary") or "").strip():
                st.write(str(row.get("summary") or ""))

st.divider()
df = pd.DataFrame(summary_rows)
if not df.empty and "discount_rate" in df.columns:
    df = df.copy()
    df["discount_pct"] = (df["discount_rate"].astype(float) * 100.0).round(2)
    df = df.drop(columns=["discount_rate"], errors="ignore")

display_df = prettify_dataframe_columns(df)
st.subheader("Summary by campaign")
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

st.subheader("High-severity signals by campaign")
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
    cols = [
        c
        for c in (
            "campaign",
            "plain_language",
            "signal_code",
            "severity",
            "entity_type",
            "signal_value",
            "threshold_value",
        )
        if c in rdf.columns
    ]
    if cols:
        st.dataframe(prettify_dataframe_columns(rdf[cols]), use_container_width=True, hide_index=True, height=280)

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
                        "signal_code": _code,
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
                        st.markdown(f"**Why now:** {str(row.get('why_now') or '')}")
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

render_footer()

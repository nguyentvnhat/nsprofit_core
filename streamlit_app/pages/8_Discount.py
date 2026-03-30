"""SKU-level discount recommendations: simple promo %, product list, margin proxy bands."""

from __future__ import annotations

import json
import sys
import time
import hashlib
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from streamlit_pkg_bootstrap import ensure_streamlit_app_package

ensure_streamlit_app_package(ROOT)

import streamlit as st

from app.database import session_scope
from app.integration.shopify_discounts import (
    build_shopify_discount_graphql_variables,
    shopify_discount_integration_enabled,
)
from app.models.ai_campaign_log import AiCampaignLog
from app.models.promotion_draft import PromotionDraft as PromotionDraftModel
from app.repositories.ai_campaign_log_repository import AiCampaignLogRepository
from app.repositories.insight_repository import InsightRepository
from app.repositories.promotion_draft_repository import PromotionDraftRepository
from app.repositories.signal_repository import SignalRepository
from app.services.discount_recommendation import build_discount_recommendation_rows, get_discount_recommendation_dataframe
from app.services.promotion_draft import promotion_drafts_from_discount_rows
from streamlit_app.ui_components import (
    apply_saas_theme,
    brand_page_icon,
    fmt_usd,
    prettify_dataframe_columns,
    render_footer,
    render_page_header,
)

st.set_page_config(page_title="Discount — NosaProfit", page_icon=brand_page_icon(), layout="wide")
apply_saas_theme(current_page="Discount")
render_page_header(
    "Discount recommendations",
    "Per-SKU simple promo % suggestions, retained-value economics, and a proxy margin band (no COGS in export). "
    "Campaigns compares attribution buckets; this page focuses on catalog promo depth. "
    "Promotion drafts are review-ready for a future Shopify one-click create (API not wired yet).",
)

with st.expander("Discount engine roadmap (Levels 1–5)", expanded=False):
    st.markdown(
        """
| Level | Status | Focus |
|-------|--------|--------|
| **1** | **Active on this page** | Simple **%** + SKU + duration; sales & line-discount **heuristics**; human approves. |
| **2 (lite)** | **Active on this page** | Add **velocity** (7d/30d), **confidence**, and **segment policy** (default all / new-customer-only for deeper promos). |
| 3 | Planned | **Promotion mix** — bundles, BXGY, tiered %, free-ship threshold (templates, not only flat %). |
| 4 | Planned | **Profit-aware** — contribution / margin (needs **COGS** or margin assumptions). |
| 5 | Planned | **Autonomous** — gated execution (e.g. Shopify), constraints, feedback loop. |

Details: `docs/discount-recommendation.md` in the repo.
        """
    )

st.caption("Engine: **Level 2 (lite)** — velocity + confidence + segment policy (export JSON `level`: 2).")

uid = st.session_state.get("active_upload_id")
if uid is None:
    st.warning("Select or process an upload from `Home`.")
    render_footer()
    st.stop()

with session_scope() as session:
    df = get_discount_recommendation_dataframe(session, int(uid))
    raw_rows = build_discount_recommendation_rows(session, int(uid))
    saved_rows = PromotionDraftRepository(session).list_for_upload(int(uid))
    signals = SignalRepository(session).list_for_upload(int(uid))
    insights = InsightRepository(session).list_for_upload(int(uid))

if df.empty:
    st.info("No line items with revenue found for this upload.")
    render_footer()
    st.stop()

# --- Engine explain / guardrails (store-level) ---
sig_by_code = {str(s.signal_code): s for s in signals}
slow_sig = sig_by_code.get("SKU_SLOW_MOVERS_HIGH")
slow_ins = next((i for i in insights if str(i.insight_code) == "slow_mover_discount_playbook"), None)
store_signal_codes = sorted(sig_by_code.keys())

if slow_sig is not None:
    st.warning("Store signal: **Many SKUs are slow-moving** (proxy from 7d vs 30d units).")
    ctx = slow_sig.signal_context_json or {}
    c10, c11, c12 = st.columns(3)
    c10.metric("Active SKUs (30d)", int(float(ctx.get("active_sku_count_30d") or 0)))
    c11.metric("Slow-mover share", f"{float(ctx.get('slow_mover_sku_share') or 0) * 100:.1f}%")
    c12.metric("Avg days since last sale", f"{float(ctx.get('avg_days_since_last_sale_active_30d') or 0):.1f}")
    if slow_ins is not None:
        with st.expander("Why this matters (rule insight)", expanded=False):
            st.markdown(f"**{slow_ins.title}**")
            st.write(slow_ins.summary)
            if slow_ins.recommended_action:
                st.markdown("**Suggested action:**")
                st.write(slow_ins.recommended_action)

# Attach store-level signal codes to each row so drafts carry rationale linkage.
for r in raw_rows:
    if isinstance(r, dict):
        r["store_signal_codes"] = store_signal_codes

st.caption(
    "Line economics: pre-discount value ≈ net line revenue + line discounts. "
    "Suggested promo % is capped near the same 15% reference used in campaign insights. "
    "Margin band is a deterministic uncertainty range around retained value, not accounting gross margin."
)

dur = st.slider("Draft promo duration (days)", min_value=1, max_value=14, value=3, step=1)
drafts = promotion_drafts_from_discount_rows(
    raw_rows,
    upload_id=int(uid),
    duration_days=int(dur),
    limit=50,
)

# Fast lookup for card-level “expected impact” proxy numbers.
_df_by_sku: dict[str, dict] = {}
try:
    for r in df.to_dict(orient="records"):
        sku_key = str(r.get("sku") or "").strip()
        if sku_key:
            _df_by_sku[sku_key] = r
except Exception:
    _df_by_sku = {}

c5, c6, c7 = st.columns([1.2, 1, 1])
with c5:
    st.caption("Review drafts quickly: filter → review → accept/reject/adjust. Decisions are saved per SKU.")
with c6:
    if shopify_discount_integration_enabled():
        st.info(
            "Shopify: **enabled** (execution not wired yet). You can preview the payload below; "
            "later this becomes one-click create."
        )
    else:
        st.caption("Shopify: **not connected** (drafts are view-only).")

with c7:
    # Auto-save drafts to DB (default behavior). Preserve previous per-SKU review status.
    existing_status_by_key: dict[str, str] = {}
    existing_payload_by_key: dict[str, dict] = {}
    for r in saved_rows:
        try:
            k = str(getattr(r, "entity_key", "") or "")
            if k:
                existing_status_by_key[k] = str(getattr(r, "status", "") or "draft")
                if isinstance(getattr(r, "draft_json", None), dict):
                    existing_payload_by_key[k] = r.draft_json
        except Exception:
            continue

    key = f"drafts_digest::{int(uid)}::{int(dur)}"
    payload = [d.to_dict() for d in drafts]
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    prev = str(st.session_state.get(key) or "")
    if digest and digest != prev:
        with session_scope() as session:
            repo = PromotionDraftRepository(session)
            models = [
                PromotionDraftModel(
                    upload_id=int(uid),
                    schema_version=int(d.schema_version),
                    level=int(d.level),
                    source=str(d.source),
                    entity_type="sku",
                    entity_key=str(d.sku),
                    status=str(existing_status_by_key.get(str(d.sku), "draft") or "draft"),
                    draft_json=(existing_payload_by_key.get(str(d.sku)) or d.to_dict()),
                )
                for d in drafts
            ]
            repo.replace_for_upload(int(uid), models)
        st.session_state[key] = digest
        st.caption(f"Auto-saved {len(drafts)} drafts to DB.")

st.divider()

# --- Overview layer (before review) ---
def _overview_rationale_bullets(codes: list[str]) -> list[str]:
    """
    Translate rationale codes into short merchant-facing bullets.
    Keep JSON/details in Advanced; show only top 2-3 reasons.
    """
    out: list[str] = []
    code_set = {str(c or "").strip().lower() for c in (codes or []) if str(c or "").strip()}

    # Pricing state
    if "low_prior_discount" in code_set:
        out.append("Mostly full-price today → a small discount can test demand without heavy margin risk.")
    if "already_heavily_discounted_cap" in code_set:
        out.append("Already deeply discounted → avoid discounting further (or scope to new customers only).")

    # Velocity
    if "velocity_fast" in code_set:
        out.append("Fast mover → keep discounts shallow and run for fewer days to protect profit.")
    elif "velocity_slow" in code_set:
        out.append("Slow mover → discounts can help move inventory, but enforce caps (% and duration).")
    elif "velocity_new_or_sparse" in code_set:
        out.append("Limited history → treat as an experiment (short run + conservative discount).")

    # Confidence
    if "confidence_high" in code_set:
        out.append("High confidence → enough recent sales data to act.")
    elif "confidence_medium" in code_set:
        out.append("Medium confidence → run short and re-check results.")
    elif "confidence_low" in code_set:
        out.append("Low confidence → review carefully or skip.")

    # Store context
    if "store_signal_sku_slow_movers_high" in code_set:
        out.append("Store context: many products are slow-moving → prioritize controlled clearance plays.")

    if not out:
        out.append("Recommendations are computed from recent product sales + discount history, with built-in guardrails and simple % steps.")

    return out[:3]


def _top_overview_reasons(drafts_in: list) -> list[str]:
    counts: dict[str, int] = {}
    for d in drafts_in or []:
        for c in (getattr(d, "rationale_codes", ()) or ()):
            key = str(c or "").strip().lower()
            if not key:
                continue
            counts[key] = counts.get(key, 0) + 1

    candidates: list[tuple[str, int]] = [
        ("Start with high-confidence recommendations", counts.get("confidence_high", 0)),
        ("Guardrail: don’t deepen already-deep discounts", counts.get("already_heavily_discounted_cap", 0)),
        ("Many recommended products are currently full-price", counts.get("low_prior_discount", 0)),
        ("Use discounts to move slow inventory (with caps)", counts.get("velocity_slow", 0)),
    ]
    out: list[str] = []
    for title, score in sorted(candidates, key=lambda x: x[1], reverse=True):
        if score <= 0:
            continue
        out.append(f"{title} ({score})")
        if len(out) >= 3:
            break
    if not out and drafts_in:
        out = [f"{len(drafts_in)} discount recommendations are ready to review today."]
    return out[:3]


if drafts:
    total_drafts = len(drafts)
    high_conf = sum(1 for d in drafts if str(getattr(d, "confidence", "") or "").lower().strip() == "high")
    heavy = sum(1 for d in drafts if float(getattr(d, "current_discount_pct", 0.0) or 0.0) >= 25.0)
    net_rev_total = sum(float(getattr(d, "net_revenue", 0.0) or 0.0) for d in drafts)
    avg_pct = sum(float(getattr(d, "suggested_discount_pct", 0.0) or 0.0) for d in drafts) / max(1, total_drafts)

    st.markdown("### Today’s overview")
    o1, o2, o3, o4 = st.columns(4)
    o1.metric("Products with recommendations", f"{total_drafts}")
    o2.metric("High-confidence items", f"{high_conf}")
    o3.metric("Already ≥25% off", f"{heavy}")
    o4.metric("Net revenue covered", fmt_usd(net_rev_total))

    c_ov1, c_ov2 = st.columns([1.25, 1])
    with c_ov1:
        st.markdown("#### What we recommend today")
        for line in _top_overview_reasons(drafts):
            st.markdown(f"- {line}")
        st.caption(f"Average suggested discount: **{avg_pct:.1f}%** · Default duration: **{int(dur)} days**.")
    with c_ov2:
        with st.container(border=True):
            st.markdown("**Guardrails (default)**")
            st.markdown("- Cap extra discount: **≤15%** (simple steps: 5/8/10/12/15).")
            st.markdown("- If already discounted **≥25%**, prefer **new customers only** or reject.")
            st.markdown("- Low confidence → run shorter (e.g. **3 days**) or skip.")
            st.markdown("- Keep discounts scoped per product (avoid site-wide blanket promos).")

st.subheader("Review recommendations (Accept / Reject / Adjust)")
if not drafts:
    st.info("No actionable drafts found (suggested promo % = 0).")
else:
    # ---- Review controls (filter / sort / focus) ----
    cflt1, cflt2, cflt3, cflt4, cflt5 = st.columns([1.1, 1.1, 1.1, 1.25, 1.5])
    with cflt1:
        review_mode = st.radio("Review mode", ["One by one", "List"], horizontal=True)
    with cflt2:
        hide_reviewed = st.toggle("Hide reviewed products", value=True)
    with cflt3:
        sort_by = st.selectbox(
            "Sort",
            options=[
                "Suggested discount % (high→low)",
                "Net revenue (high→low)",
                "Confidence",
                "Sales speed",
            ],
            index=0,
        )
    with cflt4:
        q = st.text_input("Search product code / name", value="", placeholder="e.g. GP_B15")
    with cflt5:
        conf_filter = st.multiselect(
            "Confidence",
            options=["High", "Medium", "Low"],
            default=["High", "Medium", "Low"],
        )

    if "draft_decision_start_ts" not in st.session_state:
        st.session_state["draft_decision_start_ts"] = {}
    start_ts: dict[str, float] = st.session_state["draft_decision_start_ts"]

    reject_options = [
        ("too_much_discount", "Discount is too deep"),
        ("wrong_product", "Not the right product"),
        ("low_confidence", "Not enough data / low confidence"),
        ("already_on_promo", "Already on promotion"),
        ("inventory_risk", "Inventory risk"),
        ("other", "Other"),
    ]

    def _draft_key(d) -> str:
        return f"{int(uid)}::{str(getattr(d, 'sku', '') or '')}::{int(getattr(d, 'duration_days', 0) or 0)}"

    def _ensure_start(d) -> float:
        k = _draft_key(d)
        if k not in start_ts:
            start_ts[k] = time.time()
        return float(start_ts[k])

    def _log_action(
        *,
        action_status: str,
        d,
        reject_reason: str | None = None,
        modification_detail: dict | None = None,
    ) -> None:
        t0 = _ensure_start(d)
        elapsed = max(0, int(time.time() - t0))
        payload = d.to_dict() if hasattr(d, "to_dict") else {}
        try:
            with session_scope() as session:
                repo = AiCampaignLogRepository(session)
                log = AiCampaignLog(
                    store_id=None,
                    campaign_id=str(uid),
                    industry=None,
                    aov=None,
                    inventory_level=None,
                    margin_estimate=None,
                    ai_prompt=str(getattr(d, "source", "") or "discount_recommendation"),
                    ai_response=json.dumps(payload, ensure_ascii=False),
                    campaign_type="discount",
                    discount_percent=float(getattr(d, "suggested_discount_pct", 0.0) or 0.0),
                    products_selected=[str(getattr(d, "sku", "") or "")],
                    status=action_status,
                    modification_detail=modification_detail,
                    reject_reason=reject_reason,
                    decision_time_seconds=elapsed,
                )
                repo.create(log)
        except Exception as exc:  # noqa: BLE001
            # Logging is optional (analytics). If DB migrations haven't been applied yet,
            # the page should still work (save accept/reject/adjust decisions).
            msg = str(exc).lower()
            if "doesn't exist" in msg and "ai_campaign_logs" in msg:
                st.info("Analytics logging is not set up yet (missing `ai_campaign_logs`). Run `python -m app.main provision-db` to create tables.")
                return
            # Fail-safe: never break the merchant workflow because of analytics.
            st.caption("Note: action logging is temporarily unavailable.")
            return

    # Pull latest saved statuses to display in UI and to hide reviewed items.
    saved_status_by_sku: dict[str, str] = {}
    saved_json_by_sku: dict[str, dict] = {}
    for r in saved_rows:
        sku_key = str(getattr(r, "entity_key", "") or "")
        if sku_key:
            saved_status_by_sku[sku_key] = str(getattr(r, "status", "") or "draft")
            if isinstance(getattr(r, "draft_json", None), dict):
                saved_json_by_sku[sku_key] = r.draft_json

    def _status_label(status: str) -> str:
        s = str(status or "draft")
        if s == "accepted":
            return "Accepted"
        if s == "rejected":
            return "Rejected"
        if s == "modified":
            return "Adjusted"
        return "Pending"

    def _matches_filters(d) -> bool:
        sku = str(getattr(d, "sku", "") or "")
        pname = str(getattr(d, "product_name", "") or "")
        conf = str(getattr(d, "confidence", "") or "").lower().strip()
        conf_map = {"high": "High", "medium": "Medium", "low": "Low"}
        if conf_filter and conf:
            mapped = conf_map.get(conf, "")
            if mapped and mapped not in set(conf_filter):
                return False
        if q:
            needle = q.strip().lower()
            if needle and (needle not in sku.lower()) and (needle not in pname.lower()):
                return False
        if hide_reviewed:
            stt = str(saved_status_by_sku.get(sku, "draft") or "draft")
            # Keep "Adjusted" items visible so merchants can come back and review.
            if stt in ("accepted", "rejected"):
                return False
        return True

    filtered = [d for d in drafts if _matches_filters(d)]

    def _sort_key(d):
        sku = str(getattr(d, "sku", "") or "")
        j = saved_json_by_sku.get(sku, {}) if isinstance(saved_json_by_sku.get(sku, {}), dict) else {}
        net_rev = float(j.get("net_revenue") or getattr(d, "net_revenue", 0.0) or 0.0)
        pct = float(getattr(d, "suggested_discount_pct", 0.0) or 0.0)
        conf = str(getattr(d, "confidence", "") or "")
        vb = str(getattr(d, "velocity_bucket", "") or "")
        conf_rank = {"high": 3, "medium": 2, "low": 1}.get(conf.lower().strip(), 0)
        vb_rank = {"fast": 3, "medium": 2, "slow": 1}.get(vb.lower().strip(), 0)
        if sort_by.startswith("Net revenue"):
            return (net_rev, pct, conf_rank, vb_rank)
        if sort_by.startswith("Confidence"):
            return (conf_rank, pct, net_rev, vb_rank)
        if sort_by.startswith("Sales speed"):
            return (vb_rank, pct, net_rev, conf_rank)
        return (pct, net_rev, conf_rank, vb_rank)

    filtered.sort(key=_sort_key, reverse=True)

    if not filtered:
        st.info("No drafts match your filters.")
    else:
        # One-by-one index
        if "discount_review_idx" not in st.session_state:
            st.session_state["discount_review_idx"] = 0
        if st.session_state["discount_review_idx"] >= len(filtered):
            st.session_state["discount_review_idx"] = 0

        def _go_prev() -> None:
            st.session_state["discount_review_idx"] = max(0, int(st.session_state.get("discount_review_idx", 0)) - 1)

        def _go_next() -> None:
            st.session_state["discount_review_idx"] = min(
                len(filtered) - 1,
                int(st.session_state.get("discount_review_idx", 0)) + 1,
            )

        def _persist_status_and_json(*, sku: str, status: str, draft_json: dict) -> None:
            with session_scope() as session:
                rows = PromotionDraftRepository(session).list_for_upload(int(uid))
                target = next((r for r in rows if str(getattr(r, "entity_key", "") or "") == str(sku)), None)
                if target is not None:
                    target.status = str(status)
                    target.draft_json = draft_json
                    session.flush()

        def _render_review_card(d, idx: int, total: int) -> None:
            _ensure_start(d)
            sku = str(getattr(d, "sku", "") or "")
            pname = str(getattr(d, "product_name", "") or "")
            pct = float(getattr(d, "suggested_discount_pct", 0.0) or 0.0)
            days = int(getattr(d, "duration_days", 0) or 0)
            conf = str(getattr(d, "confidence", "") or "")
            vb = str(getattr(d, "velocity_bucket", "") or "")
            seg = str(getattr(d, "segment_policy", "") or "")
            current_status = str(saved_status_by_sku.get(sku, "draft") or "draft")
            status_txt = _status_label(current_status)

            base_json = saved_json_by_sku.get(sku, None)
            if not isinstance(base_json, dict):
                base_json = d.to_dict() if hasattr(d, "to_dict") else {}

            row = _df_by_sku.get(sku) if isinstance(_df_by_sku, dict) else None
            cur_band = ""
            after_band = ""
            try:
                if isinstance(row, dict):
                    c_lo = float(row.get("margin_proxy_low_pct") or 0.0)
                    c_hi = float(row.get("margin_proxy_high_pct") or 0.0)
                    a_lo = float(row.get("after_promo_margin_band_low_pct") or 0.0)
                    a_hi = float(row.get("after_promo_margin_band_high_pct") or 0.0)
                    if c_hi > 0:
                        cur_band = f"{c_lo:.0f}–{c_hi:.0f}%"
                    if a_hi > 0:
                        after_band = f"{a_lo:.0f}–{a_hi:.0f}%"
            except Exception:
                cur_band = ""
                after_band = ""

            def _label_velocity(v: str) -> str:
                vv = str(v or "").lower().strip()
                return {
                    "fast": "Fast seller",
                    "normal": "Normal",
                    "slow": "Slow seller",
                    "new_or_sparse": "Limited history",
                }.get(vv, "—")

            def _label_confidence(c: str) -> str:
                cc = str(c or "").lower().strip()
                return {"high": "High", "medium": "Medium", "low": "Low"}.get(cc, "—")

            def _label_segment(s: str) -> str:
                ss = str(s or "").lower().strip()
                return {"all_customers": "All customers", "new_customers": "New customers only"}.get(ss, "—")

            with st.container(border=True):
                st.markdown(
                    f"**{status_txt} · #{idx} / {total} · {pname or 'Unnamed product'}**  \n"
                    f"Product code: `{sku}` · Suggested discount: **{pct:.0f}%** · Duration: **{days} days**"
                    + (f" · Expected margin (proxy): **{after_band}**" if after_band else "")
                )
                st.caption(
                    f"Sales speed: **{_label_velocity(vb)}** · Confidence: **{_label_confidence(conf)}** · Applies to: **{_label_segment(seg)}**"
                    + (f" · Current margin (proxy): **{cur_band}**" if cur_band else "")
                )

                a1, a2, a3, a4 = st.columns([1, 1, 1.2, 2])
                with a1:
                    if st.button("Accept", key=f"accept::{_draft_key(d)}", type="primary"):
                        _log_action(action_status="accepted", d=d)
                        _persist_status_and_json(sku=sku, status="accepted", draft_json=base_json)
                        st.session_state["discount_review_idx"] = min(st.session_state["discount_review_idx"] + 1, max(0, len(filtered) - 1))
                        st.rerun()
                with a2:
                    rr_code = st.selectbox(
                        "Reject reason",
                        options=[x[0] for x in reject_options],
                        format_func=lambda v: dict(reject_options).get(v, v),
                        index=2,
                        key=f"reject_reason::{_draft_key(d)}",
                        label_visibility="collapsed",
                    )
                    if st.button("Reject", key=f"reject::{_draft_key(d)}"):
                        _log_action(action_status="rejected", d=d, reject_reason=str(rr_code))
                        _persist_status_and_json(
                            sku=sku,
                            status="rejected",
                            draft_json={**base_json, "review": {"status": "rejected", "reason": str(rr_code)}},
                        )
                        st.session_state["discount_review_idx"] = min(st.session_state["discount_review_idx"] + 1, max(0, len(filtered) - 1))
                        st.rerun()
                with a3:
                    if st.button("Skip", key=f"skip::{_draft_key(d)}"):
                        st.session_state["discount_review_idx"] = min(st.session_state["discount_review_idx"] + 1, max(0, len(filtered) - 1))
                        st.rerun()
                with a4:
                    with st.expander("Adjust recommendation", expanded=False):
                        c11, c12, c13 = st.columns(3)
                        with c11:
                            new_pct = st.slider(
                                "Discount %",
                                min_value=0,
                                max_value=30,
                                value=int(round(float(base_json.get("suggested_discount_pct", pct) or 0.0))),
                                step=1,
                                key=f"adj_pct::{_draft_key(d)}",
                            )
                        with c12:
                            new_days = st.number_input(
                                "Duration (days)",
                                min_value=1,
                                max_value=30,
                                value=int(base_json.get("duration_days", days) or days or 3),
                                step=1,
                                key=f"adj_days::{_draft_key(d)}",
                            )
                        with c13:
                            new_seg = st.selectbox(
                                "Applies to",
                                options=["all_customers", "new_customers"],
                                index=0 if str(base_json.get("segment_policy", seg) or "all_customers") == "all_customers" else 1,
                                key=f"adj_seg::{_draft_key(d)}",
                                format_func=lambda v: _label_segment(str(v)),
                            )
                        note = st.text_input(
                            "Note (optional)",
                            value=str((base_json.get("review", {}) or {}).get("note") or ""),
                            key=f"adj_note::{_draft_key(d)}",
                            placeholder="e.g. cap at 10% due to thin margin",
                        )

                        next_json = dict(base_json)
                        next_json["suggested_discount_pct"] = float(new_pct)
                        next_json["duration_days"] = int(new_days)
                        next_json["segment_policy"] = str(new_seg)
                        next_json["review"] = {
                            "status": "modified",
                            "note": str(note or "").strip(),
                            "change": {
                                "suggested_discount_pct": float(new_pct),
                                "duration_days": int(new_days),
                                "segment_policy": str(new_seg),
                            },
                        }

                        if st.button("Save changes", key=f"modify::{_draft_key(d)}", type="primary"):
                            _log_action(
                                action_status="modified",
                                d=d,
                                modification_detail={
                                    "suggested_discount_pct": float(new_pct),
                                    "duration_days": int(new_days),
                                    "segment_policy": str(new_seg),
                                    "note": str(note or "").strip(),
                                },
                            )
                            _persist_status_and_json(sku=sku, status="modified", draft_json=next_json)
                            st.session_state["discount_review_idx"] = min(st.session_state["discount_review_idx"] + 1, max(0, len(filtered) - 1))
                            st.rerun()

        if review_mode == "One by one":
            nav1, nav2, nav3, nav4 = st.columns([1, 2, 1, 2.2])
            with nav1:
                st.button("◀ Prev", key="discount_prev", on_click=_go_prev, use_container_width=True)
            with nav2:
                st.progress((int(st.session_state["discount_review_idx"]) + 1) / max(1, len(filtered)))
            with nav3:
                st.button("Next ▶", key="discount_next", on_click=_go_next, use_container_width=True)
            with nav4:
                d0 = filtered[int(st.session_state["discount_review_idx"])]
                st.caption(
                    f"Showing: `{str(getattr(d0, 'sku', '') or '')}` · {int(st.session_state['discount_review_idx']) + 1}/{len(filtered)}"
                )

            _render_review_card(d0, int(st.session_state["discount_review_idx"]) + 1, len(filtered))
        else:
            show_n = st.slider(
                "How many products to show",
                min_value=3,
                max_value=min(50, len(filtered)),
                value=min(10, len(filtered)),
                step=1,
            )
            for idx, d in enumerate(filtered[: int(show_n)], start=1):
                _render_review_card(d, idx, min(int(show_n), len(filtered)))

st.divider()
st.subheader("Shopify execution (optional)")
if not shopify_discount_integration_enabled():
    c8, c9 = st.columns([1, 2])
    with c8:
        st.button("Connect Shopify (coming soon)", disabled=True)
    with c9:
        st.caption(
            "When Shopify is connected, saved drafts can be executed with one click. "
            "For now, keep using JSON export or DB drafts for portal integration."
        )
else:
    with st.expander("Shopify GraphQL placeholder (first draft only)", expanded=False):
        if drafts:
            st.code(
                json.dumps(build_shopify_discount_graphql_variables(drafts[0]), ensure_ascii=False, indent=2),
                language="json",
            )
        else:
            st.write("No drafts to preview.")

with st.expander("Saved drafts in DB (this upload)", expanded=False):
    if not saved_rows:
        st.write("No saved drafts yet.")
    else:
        sdf = pd.DataFrame([r.draft_json for r in saved_rows if isinstance(r.draft_json, dict)])
        if not sdf.empty:
            cols = [
                c
                for c in (
                    "product_name",
                    "sku",
                    "suggested_discount_pct",
                    "duration_days",
                    "segment_policy",
                    "velocity_bucket",
                    "confidence",
                    "current_discount_pct",
                    "net_revenue",
                    "source",
                    "level",
                    "schema_version",
                )
                if c in sdf.columns
            ]
            st.dataframe(prettify_dataframe_columns(sdf[cols] if cols else sdf), use_container_width=True, hide_index=True)
        else:
            st.write("Saved drafts exist but payload is empty/unexpected.")

top = df.head(min(5, len(df)))
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("SKUs in view", len(df))
with c2:
    st.metric("Top SKU suggested promo", f"{float(top.iloc[0]['suggested_promo_pct']):.0f}%")
with c3:
    avg_ret = float(df["value_retained_pct"].mean())
    st.metric("Avg value retained (catalog)", f"{avg_ret:.1f}%")
with c4:
    deep = int((df["current_discount_pct"] > 25).sum())
    st.metric("SKUs already >25% off list", deep)

with st.expander("Advanced: data tables (optional)", expanded=False):
    st.subheader("Recommended products to promote")
    st.dataframe(
        prettify_dataframe_columns(
            df[
                [
                    "product_name",
                    "sku",
                    "net_revenue",
                    "units_7d",
                    "units_30d",
                    "velocity_bucket",
                    "confidence",
                    "current_discount_pct",
                    "suggested_promo_pct",
                    "margin_proxy_low_pct",
                    "margin_proxy_high_pct",
                    "after_promo_margin_band_low_pct",
                    "after_promo_margin_band_high_pct",
                ]
            ].head(50)
        ),
        use_container_width=True,
        height=min(520, 48 + min(50, len(df)) * 36),
        hide_index=True,
    )

    with st.expander("Full table (all columns)", expanded=False):
        st.dataframe(
            prettify_dataframe_columns(df),
            use_container_width=True,
            height=min(560, 48 + len(df) * 35),
            hide_index=True,
        )

st.subheader("How this relates to Campaigns")
st.markdown(
    "- **Campaigns** rolls up **discount ÷ gross** per attribution bucket (UTM, source, discount code, etc.) and surfaces risks.\n"
    "- **This page** allocates **line-level discounts** to each SKU, proposes a **simple extra promo %**, and shows **retained-value / margin proxy** bands before and after that promo."
)

render_footer()

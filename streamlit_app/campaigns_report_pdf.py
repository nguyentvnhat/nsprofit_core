"""Deterministic PDF export for the Campaigns dashboard (Streamlit-only, no LLM)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fpdf import FPDF, FPDF_FONT_DIR


def _safe_txt(s: Any, max_len: int = 800) -> str:
    t = str(s or "").replace("\r", " ")
    t = " ".join(t.split())
    if len(t) > max_len:
        return t[: max_len - 1] + "…"
    return t


def _fmt_money(v: Any) -> str:
    try:
        x = float(v or 0.0)
    except (TypeError, ValueError):
        x = 0.0
    return f"${x:,.2f}"


def _register_fonts(pdf: FPDF) -> str:
    """Return font family name (use style ``B`` for bold)."""
    font_dir = Path(FPDF_FONT_DIR)
    reg = font_dir / "DejaVuSans.ttf"
    bold = font_dir / "DejaVuSans-Bold.ttf"
    if reg.is_file():
        pdf.add_font("NPDejaVu", "", str(reg))
        if bold.is_file():
            pdf.add_font("NPDejaVu", "B", str(bold))
        else:
            pdf.add_font("NPDejaVu", "B", str(reg))
        return "NPDejaVu"
    return "helvetica"


class _CampaignsPDF(FPDF):
    def __init__(self) -> None:
        super().__init__()
        self.set_auto_page_break(auto=True, margin=14)
        self.set_margins(left=14, top=14, right=14)
        self._ffam = _register_fonts(self)

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font(self._ffam, "", 9)
        self.set_text_color(90, 90, 90)
        self.cell(0, 8, "NosaProfit — Campaigns", ln=1)
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(self._ffam, "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C", ln=0)


def build_campaigns_pdf_bytes(
    *,
    upload_id: int,
    summary_rows: list[dict[str, Any]],
    enriched_insights: list[dict[str, Any]],
    risks_rows: list[dict[str, Any]],
    opp_summary: dict[str, Any],
    signal_label_fn: Callable[[str | None], tuple[str, str]],
) -> bytes:
    """Build a multi-section PDF report; safe on empty lists."""
    pdf = _CampaignsPDF()
    ff = pdf._ffam
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font(ff, "B", 16)
    pdf.cell(0, 10, "NosaProfit — Campaigns report", ln=1)
    pdf.set_font(ff, "", 10)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf.cell(0, 6, f"Upload ID: {upload_id} · Generated: {ts}", ln=1)
    pdf.ln(4)

    if isinstance(opp_summary, dict) and opp_summary:
        pdf.set_font(ff, "B", 12)
        pdf.cell(0, 8, "Roll-up (all enriched insights)", ln=1)
        pdf.set_font(ff, "", 10)
        pdf.cell(
            0,
            6,
            f"Est. leakage (proxy): {_fmt_money(opp_summary.get('total_estimated_loss'))}",
            ln=1,
        )
        pdf.cell(
            0,
            6,
            f"Opportunity (proxy): {_fmt_money(opp_summary.get('total_opportunity_size'))}",
            ln=1,
        )
        pdf.cell(
            0,
            6,
            f"Insights counted: {opp_summary.get('insight_count', '—')}",
            ln=1,
        )
        pdf.ln(2)

    # --- Summary table ---
    pdf.set_font(ff, "B", 12)
    pdf.cell(0, 8, "Summary by campaign", ln=1)
    pdf.set_font(ff, "", 8)
    # Total width ≈ 182mm (A4 minus 14mm side margins).
    col_w = (38, 20, 26, 26, 22, 20, 30)
    headers = ("Campaign", "Orders", "Gross rev.", "Net rev.", "Disc. %", "AOV", "Risk")
    pdf.set_fill_color(240, 242, 247)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, h, border=1, fill=True)
    pdf.ln()
    pdf.set_font(ff, "", 8)
    for row in summary_rows:
        if pdf.get_y() > 270:
            pdf.add_page()
        camp = _safe_txt(row.get("campaign"), 40)
        orders = str(int(row.get("orders") or 0))
        gross = _fmt_money(row.get("revenue"))
        net = _fmt_money(row.get("net_revenue"))
        dr = float(row.get("discount_rate") or 0.0) * 100.0
        disc = f"{dr:.1f}%"
        aov = _fmt_money(row.get("aov"))
        risk = _safe_txt(row.get("risk_level"), 12)
        vals = (camp, orders, gross, net, disc, aov, risk)
        for i, v in enumerate(vals):
            pdf.cell(col_w[i], 6, _safe_txt(v, 60), border=1)
        pdf.ln()
    pdf.ln(3)

    # --- Risks ---
    pdf.set_font(ff, "B", 12)
    pdf.cell(0, 8, "High-severity campaign risks (top slice)", ln=1)
    if not risks_rows:
        pdf.set_font(ff, "", 10)
        pdf.multi_cell(0, 5, "No rows in the current top slice.")
        pdf.ln(2)
    else:
        pdf.set_font(ff, "", 7)
        rw = (24, 44, 34, 16, 18, 18, 28)
        rh = ("Campaign", "Signal (plain)", "Code", "Severity", "Value", "Threshold", "Entity")
        pdf.set_fill_color(240, 242, 247)
        for i, h in enumerate(rh):
            pdf.cell(rw[i], 6, h, border=1, fill=True)
        pdf.ln()
        for r in risks_rows[:40]:
            if pdf.get_y() > 270:
                pdf.add_page()
            code = str(r.get("signal_code") or "")
            plab, _ = signal_label_fn(code)
            row_vals = (
                _safe_txt(r.get("campaign"), 26),
                _safe_txt(plab, 50),
                _safe_txt(code, 38),
                _safe_txt(r.get("severity"), 16),
                _safe_txt(f"{float(r.get('signal_value') or 0):.3f}", 20),
                _safe_txt(f"{float(r.get('threshold_value') or 0):.3f}", 20),
                _safe_txt(r.get("entity_type"), 20),
            )
            for i, v in enumerate(row_vals):
                pdf.cell(rw[i], 5, v, border=1)
            pdf.ln()
        pdf.ln(2)

    # --- Insights (full enriched list, capped per page budget) ---
    pdf.set_font(ff, "B", 12)
    pdf.cell(0, 8, "Enriched campaign insights", ln=1)
    sorted_ins = sorted(
        enriched_insights,
        key=lambda x: (float(x.get("rank") or 9999), str(x.get("campaign") or "")),
    )
    max_insights = 35
    for idx, ins in enumerate(sorted_ins[:max_insights], start=1):
        if pdf.get_y() > 245:
            pdf.add_page()
        pdf.set_font(ff, "B", 10)
        rank = ins.get("rank", idx)
        camp = _safe_txt(ins.get("campaign"), 30)
        title = _safe_txt(ins.get("title"), 120)
        pdf.multi_cell(0, 5, f"#{rank} · {camp} — {title}")
        pdf.set_font(ff, "", 9)
        sc = str(ins.get("signal_code") or "")
        slab, _ = signal_label_fn(sc)
        line = (
            f"Priority: {ins.get('priority', '—')} · Category: {ins.get('category', '—')} · "
            f"Signal: {slab} ({sc})"
        )
        pdf.multi_cell(0, 4, _safe_txt(line, 200))
        pdf.multi_cell(
            0,
            4,
            _safe_txt(
                f"Impacted revenue: {_fmt_money(ins.get('impacted_revenue'))} · "
                f"Est. loss: {_fmt_money(ins.get('estimated_loss'))} · "
                f"Opportunity: {_fmt_money(ins.get('opportunity_size'))} · "
                f"Share of view: {float(ins.get('affected_revenue_share') or 0) * 100:.1f}% · "
                f"Score: {ins.get('priority_score', '—')}",
                240,
            ),
        )
        impact = ins.get("estimated_impact_text")
        if impact:
            pdf.set_font(ff, "", 9)
            pdf.multi_cell(0, 4, _safe_txt(f"Impact: {impact}", 240))
        why = ins.get("why_now")
        if why:
            pdf.multi_cell(0, 4, _safe_txt(f"Why now: {why}", 500))
        pdf.ln(1)
        pdf.set_draw_color(220, 220, 230)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(2)

    if len(sorted_ins) > max_insights:
        pdf.set_font(ff, "", 9)
        pdf.multi_cell(
            0,
            5,
            f"… {len(sorted_ins) - max_insights} additional insights omitted in PDF; use app export for full data.",
        )

    raw = pdf.output(dest="S")
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    return str(raw).encode("latin-1", errors="replace")

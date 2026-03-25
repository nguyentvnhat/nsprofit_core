"""Deterministic PDF export for the Campaigns dashboard (Streamlit-only, no LLM)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import struct
from typing import Any, Callable

try:
    from fpdf import FPDF, FPDF_FONT_DIR

    _HAS_FPDF = True
except Exception:  # pragma: no cover - environment-dependent optional dependency
    FPDF = Any  # type: ignore[assignment]
    FPDF_FONT_DIR = ""
    _HAS_FPDF = False

_BRAND_FOOTER = "NosaProfit - Provider by Uway Technology"
_LOGO_BOX_PX = 150
_PX_TO_MM = 25.4 / 96.0


def _logo_path() -> Path | None:
    p = Path(__file__).resolve().parents[1] / "assets" / "nosaprofit.PNG"
    return p if p.is_file() else None


def _png_size(path: Path) -> tuple[int, int] | None:
    """Read PNG width/height from IHDR without external deps."""
    try:
        with path.open("rb") as f:
            raw = f.read(24)
        if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        width = struct.unpack(">I", raw[16:20])[0]
        height = struct.unpack(">I", raw[20:24])[0]
        if width <= 0 or height <= 0:
            return None
        return width, height
    except Exception:
        return None


def _logo_draw_size_mm(path: Path) -> tuple[float, float]:
    """
    Fit logo into a 150x150px box while preserving aspect ratio.
    Returns width/height in mm.
    """
    box_mm = _LOGO_BOX_PX * _PX_TO_MM
    size = _png_size(path)
    if not size:
        return box_mm, box_mm
    w_px, h_px = size
    ratio = w_px / h_px
    if ratio >= 1:
        return box_mm, box_mm / ratio
    return box_mm * ratio, box_mm


def _safe_txt(s: Any, max_len: int = 800, *, unicode_ok: bool = True) -> str:
    t = str(s or "").replace("\r", " ")
    t = " ".join(t.split())
    # Core PDF fonts (e.g. helvetica) are not Unicode-safe; sanitize aggressively.
    if not unicode_ok:
        t = (
            t.replace("—", "-")
            .replace("–", "-")
            .replace("…", "...")
            .replace("•", "-")
            .replace("“", '"')
            .replace("”", '"')
            .replace("’", "'")
            .replace("‘", "'")
        )
        t = t.encode("latin-1", "replace").decode("latin-1")
    if len(t) > max_len:
        return t[: max_len - 1] + "…"
    return t


def _fmt_money(v: Any) -> str:
    try:
        x = float(v or 0.0)
    except (TypeError, ValueError):
        x = 0.0
    return f"${x:,.2f}"


def _register_fonts(pdf: FPDF) -> tuple[str, bool]:
    """Return (font_family_name, unicode_ok)."""
    font_dir = Path(FPDF_FONT_DIR)
    reg = font_dir / "DejaVuSans.ttf"
    bold = font_dir / "DejaVuSans-Bold.ttf"
    if reg.is_file():
        pdf.add_font("NPDejaVu", "", str(reg))
        if bold.is_file():
            pdf.add_font("NPDejaVu", "B", str(bold))
        else:
            pdf.add_font("NPDejaVu", "B", str(reg))
        return "NPDejaVu", True
    return "helvetica", False


class _CampaignsPDF(FPDF):
    def __init__(self) -> None:
        super().__init__()
        self.set_auto_page_break(auto=True, margin=14)
        self.set_margins(left=14, top=14, right=14)
        self._ffam, self._unicode_ok = _register_fonts(self)

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font(self._ffam, "", 9)
        self.set_text_color(90, 90, 90)
        self.cell(0, 8, "NosaProfit - Campaigns", ln=1)
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def footer(self) -> None:
        self.set_y(-16)
        self.set_font(self._ffam, "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, _BRAND_FOOTER, align="C", ln=1)
        self.set_y(-10)
        self.set_font(self._ffam, "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C", ln=0)


def _build_minimal_pdf_bytes(
    *,
    upload_id: int,
    summary_rows: list[dict[str, Any]],
    enriched_insights: list[dict[str, Any]],
    risks_rows: list[dict[str, Any]] | None = None,
    opp_summary: dict[str, Any] | None = None,
) -> bytes:
    """Always-safe ASCII fallback report when rich layout fails."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_margins(left=14, top=14, right=14)
    pdf.alias_nb_pages()
    pdf.add_page()
    logo = _logo_path()
    if logo is not None:
        try:
            logo_w_mm, logo_h_mm = _logo_draw_size_mm(logo)
            y0 = pdf.get_y()
            pdf.image(str(logo), x=(pdf.w - logo_w_mm) / 2.0, y=y0, w=logo_w_mm, h=logo_h_mm)
            pdf.set_y(y0 + logo_h_mm + 2.0)
        except Exception:
            pass
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 8, "NosaProfit - Campaigns report", ln=1)
    pdf.set_font("helvetica", "", 10)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf.cell(0, 6, f"Upload ID: {upload_id} | Generated: {ts}", ln=1)
    pdf.ln(2)
    if isinstance(opp_summary, dict) and opp_summary:
        pdf.set_font("helvetica", "", 9)
        pdf.multi_cell(
            0,
            5,
            _safe_txt(
                f"Estimated loss: {_fmt_money(opp_summary.get('total_estimated_loss'))} | "
                f"Opportunity: {_fmt_money(opp_summary.get('total_opportunity_size'))} | "
                f"Top campaign: {opp_summary.get('top_priority_campaign', '-')}",
                220,
                unicode_ok=False,
            ),
        )
        pdf.ln(1)
    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, _BRAND_FOOTER, ln=1, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)

    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 7, "Summary by campaign", ln=1)
    pdf.set_font("helvetica", "", 9)
    for r in summary_rows[:50]:
        line = (
            f"- {r.get('campaign', 'unknown')}: orders={int(r.get('orders') or 0)}, "
            f"gross={_fmt_money(r.get('revenue'))}, net={_fmt_money(r.get('net_revenue'))}, "
            f"risk={r.get('risk_level', 'low')}"
        )
        pdf.multi_cell(0, 5, _safe_txt(line, 220, unicode_ok=False))
    pdf.ln(2)

    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 7, "Top insights", ln=1)
    pdf.set_font("helvetica", "", 9)
    for i, ins in enumerate(enriched_insights, start=1):
        line = (
            f"#{int(_safe_float(ins.get('rank'), i))} "
            f"{ins.get('campaign', 'unknown')} - {ins.get('title', 'Insight')}"
        )
        pdf.multi_cell(0, 5, _safe_txt(line, 240, unicode_ok=False))
        impact_text, _, _ = _executive_impact(ins)
        pdf.multi_cell(0, 5, _safe_txt(f"  Impact: {impact_text}", 220, unicode_ok=False))
        why = _safe_txt(ins.get("why_now"), 240, unicode_ok=False)
        if why:
            pdf.multi_cell(0, 5, f"  Why now: {why}")
        if pdf.get_y() > 270:
            pdf.add_page()

    if risks_rows:
        pdf.ln(2)
        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 7, "High severity signals", ln=1)
        pdf.set_font("helvetica", "", 9)
        for r in risks_rows:
            line = (
                f"- {r.get('campaign', 'unknown')} | {r.get('signal_code', '-')}"
                f" | value={_safe_float(r.get('signal_value')):.2f}"
                f" | threshold={_safe_float(r.get('threshold_value')):.2f}"
            )
            pdf.multi_cell(0, 5, _safe_txt(line, 220, unicode_ok=False))
            if pdf.get_y() > 270:
                pdf.add_page()
    raw = pdf.output(dest="S")
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    return str(raw).encode("latin-1", errors="replace")


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _build_reportlab_pdf_bytes(
    *,
    upload_id: int,
    summary_rows: list[dict[str, Any]],
    enriched_insights: list[dict[str, Any]],
    risks_rows: list[dict[str, Any]],
    opp_summary: dict[str, Any],
) -> bytes:
    """
    Styled fallback PDF using reportlab (if installed).
    More readable than plain text fallback and independent from fpdf2.
    """
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    s_title = ParagraphStyle("np_title", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=21)
    s_sub = ParagraphStyle("np_sub", parent=styles["Normal"], fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#6b7280"))
    s_h2 = ParagraphStyle("np_h2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15)
    s_txt = ParagraphStyle("np_txt", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12)
    s_impact = ParagraphStyle("np_impact", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, textColor=colors.HexColor("#b02a37"))

    story: list[Any] = []
    logo = _logo_path()
    if logo is not None:
        try:
            logo_w_mm, logo_h_mm = _logo_draw_size_mm(logo)
            logo_img = Image(str(logo), width=logo_w_mm * mm, height=logo_h_mm * mm)
            logo_img.hAlign = "CENTER"
            story.append(logo_img)
            story.append(Spacer(1, 4))
        except Exception:
            pass
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story.append(Paragraph("NosaProfit - Campaigns report", s_title))
    story.append(Paragraph(f"Upload ID: {upload_id} | Generated: {ts}", s_sub))
    story.append(Spacer(1, 8))

    if isinstance(opp_summary, dict) and opp_summary:
        loss = _fmt_money(opp_summary.get("total_estimated_loss"))
        opp = _fmt_money(opp_summary.get("total_opportunity_size"))
        top_c = _safe_txt(opp_summary.get("top_priority_campaign"), 60, unicode_ok=False)
        hero = Table(
            [[f"Estimated loss: {loss}", f"Opportunity: {opp}", f"Top campaign: {top_c}"]],
            colWidths=[58 * mm, 58 * mm, 54 * mm],
        )
        hero.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#dee2e6")),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(hero)
        story.append(Spacer(1, 10))

    story.append(Paragraph("Summary by campaign", s_h2))
    table_rows = [["Campaign", "Orders", "Gross", "Net", "Discount %", "AOV", "Risk"]]
    for r in summary_rows:
        table_rows.append(
            [
                _safe_txt(r.get("campaign"), 20, unicode_ok=False),
                str(int(r.get("orders") or 0)),
                _fmt_money(r.get("revenue")),
                _fmt_money(r.get("net_revenue")),
                f"{_safe_float(r.get('discount_rate')) * 100.0:.1f}%",
                _fmt_money(r.get("aov")),
                _safe_txt(r.get("risk_level"), 10, unicode_ok=False),
            ]
        )
    t = Table(table_rows, colWidths=[38 * mm, 15 * mm, 23 * mm, 23 * mm, 20 * mm, 18 * mm, 20 * mm], repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f3f5")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Top insights", s_h2))
    for i, ins in enumerate(enriched_insights, start=1):
        camp = _safe_txt(ins.get("campaign"), 30, unicode_ok=False)
        title = _safe_txt(ins.get("title"), 70, unicode_ok=False)
        story.append(Paragraph(f"{i}. {camp} - {title}", s_txt))
        story.append(Paragraph(f"Impact: {_safe_txt(ins.get('estimated_impact_text'), 140, unicode_ok=False)}", s_impact))
        why = _safe_txt(ins.get("why_now"), 260, unicode_ok=False)
        if why:
            story.append(Paragraph(f"Why now: {why}", s_txt))
        story.append(Spacer(1, 4))

    if risks_rows:
        story.append(Spacer(1, 8))
        story.append(Paragraph("High-severity signals", s_h2))
        for r in risks_rows:
            code = _safe_txt(r.get("signal_code"), 40, unicode_ok=False)
            camp = _safe_txt(r.get("campaign"), 30, unicode_ok=False)
            story.append(
                Paragraph(
                    f"- {camp} | {code} | value={_safe_float(r.get('signal_value')):.2f} | threshold={_safe_float(r.get('threshold_value')):.2f}",
                    s_txt,
                )
            )

    def _draw_footer(canvas: Any, doc_obj: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColorRGB(0.47, 0.47, 0.47)
        canvas.drawCentredString(A4[0] / 2, 8 * mm, _BRAND_FOOTER)
        canvas.restoreState()

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buf.getvalue()


def _executive_sorted(insights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        insights,
        key=lambda x: (
            -_safe_float(x.get("priority_score")),
            -(_safe_float(x.get("estimated_loss")) + _safe_float(x.get("opportunity_size"))),
            -_safe_float(x.get("impacted_revenue")),
        ),
    )


def _executive_impact_numbers(ins: dict[str, Any]) -> tuple[float, float]:
    loss = max(_safe_float(ins.get("estimated_loss")), 0.0)
    opp = max(_safe_float(ins.get("opportunity_size")), 0.0)
    if loss > 0 or opp > 0:
        return loss, opp
    revenue = max(_safe_float(ins.get("impacted_revenue")), _safe_float(ins.get("revenue")))
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


def _executive_impact(ins: dict[str, Any]) -> tuple[str, float, str]:
    loss, opp = _executive_impact_numbers(ins)
    if loss > 0 and loss >= opp:
        return f"{_fmt_money(loss)} loss", loss, "loss"
    if opp > 0:
        return f"{_fmt_money(opp)} opportunity", opp, "opportunity"
    low, high = _executive_impact_numbers(ins)
    if low > 0 and high > low:
        return f"{_fmt_money(low)}-{_fmt_money(high)} estimated impact", high, "range"
    return f"{_fmt_money(max(low, high))} estimated impact", max(low, high), "range"


def _executive_impact_range_text(ins: dict[str, Any]) -> str:
    low, high = _executive_impact_numbers(ins)
    if low > 0 and high > low:
        return f"{_fmt_money(low)}-{_fmt_money(high)}"
    return _fmt_money(max(low, high))


def _executive_basis(ins: dict[str, Any]) -> str:
    code = str(ins.get("signal_code") or "").upper()
    title = str(ins.get("title") or "").lower()
    loss = max(_safe_float(ins.get("estimated_loss")), 0.0)
    opp = max(_safe_float(ins.get("opportunity_size")), 0.0)
    blob = f"{code} {title}"
    if "REFUND" in blob and loss > 0:
        return "Measured"
    if ("DISCOUNT" in blob or "AOV" in blob or "UNSTABLE" in blob or "VOLUME_DRIVEN" in blob) and (loss > 0 or opp > 0):
        return "Estimated (proxy)"
    if "CONCENTRATION" in blob or "DEPENDENCY" in blob or "LOW_REPEAT" in blob or "REPEAT" in blob:
        return "Estimated (proxy)"
    return "Estimated (proxy)"


def _executive_action(ins: dict[str, Any]) -> str:
    code = str(ins.get("signal_code") or "").upper()
    title = str(ins.get("title") or "").lower()
    campaign = str(ins.get("campaign") or "this campaign")
    revenue = max(_safe_float(ins.get("impacted_revenue")), _safe_float(ins.get("revenue")))
    blob = f"{code} {title}"
    if "STACK" in code or "discount" in title:
        verb = f"Reduce discount stacking in {campaign}"
    elif "AOV" in code or "LOW_ORDER_VALUE" in code or "order value" in title:
        verb = f"Increase AOV in {campaign}"
    elif "UNSTABLE" in code or "volatility" in title or "trajectory" in title:
        verb = f"Stabilize revenue in {campaign}"
    elif "CONCENTRATION" in code or "DEPENDENCY" in title:
        verb = f"Diversify channels/SKUs in {campaign}"
    elif "LOW_REPEAT" in code or "REPEAT" in title:
        verb = f"Lift repeat mix in {campaign}"
    elif "BUNDLE" in code or "PAIR" in title:
        verb = f"Launch bundle/paired offer in {campaign}"
    elif "SHIPPING" in code or "FREE_SHIP" in code or "threshold" in title:
        verb = f"Adjust free-shipping threshold and cart nudges in {campaign}"
    elif "REFUND" in code or "return" in title:
        verb = f"Reduce refund drivers in {campaign}"
    else:
        raw = str(ins.get("action") or "").strip()
        if raw:
            raw = _safe_txt(raw, 120, unicode_ok=False)
            if raw.lower().startswith("action:"):
                raw = raw[7:].strip()
            verb = raw if campaign.lower() in raw.lower() else f"{raw} in {campaign}"
        else:
            verb = f"Tighten targeting and offer design in {campaign}"
    impact_text, amount, kind = _executive_impact(ins)
    if amount > 0 and kind == "loss":
        return f"{verb} -> save {impact_text.split(' ')[0]}"
    if amount > 0 and kind == "opportunity":
        return f"{verb} -> gain {impact_text.split(' ')[0]}"
    if revenue <= 0:
        return f"{verb} -> estimated impact {_executive_impact_range_text(ins)}"
    if "CONCENTRATION" in blob or "DEPENDENCY" in blob:
        return f"Protect ~{_fmt_money(revenue * 0.05)} revenue exposure by diversifying channels in {campaign}"
    if "LOW_REPEAT" in blob or "REPEAT" in blob:
        return f"Recover ~{_fmt_money(revenue * 0.08)} by increasing repeat mix in {campaign}"
    return f"Protect ~{_fmt_money(revenue * 0.05)} in {campaign} by tightening campaign controls"


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


def _decision_category(ins: dict[str, Any]) -> str:
    blob = f"{str(ins.get('signal_code') or '').upper()} {str(ins.get('title') or '').lower()}"
    if "DISCOUNT" in blob or "STACK" in blob or "PRICING" in blob:
        return "Pricing / Discount"
    if "AOV" in blob or "BUNDLE" in blob or "SHIPPING" in blob:
        return "AOV / Cart"
    if "REPEAT" in blob or "REFUND" in blob or "RETURN" in blob:
        return "Retention"
    return "Channel / Risk"


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
    basis = _executive_basis(ins)
    blob = f"{str(ins.get('signal_code') or '').upper()} {str(ins.get('title') or '').lower()}"
    if basis == "Measured":
        return "High"
    if "DISCOUNT" in blob or "AOV" in blob or "REFUND" in blob or "UNSTABLE" in blob:
        return "Medium"
    return "Low"


def _urgency_label(time_to_impact: str) -> str:
    if time_to_impact == "3-7 days":
        return "Do now (this week)"
    if time_to_impact == "7-14 days":
        return "Next 2 weeks"
    return "Strategic follow-up"


def _confidence_adjusted_range(ins: dict[str, Any]) -> tuple[float, float]:
    value = _safe_float(ins.get("impact_value"))
    if value <= 0:
        value = max(_executive_impact_numbers(ins))
    conf = str(ins.get("confidence") or _confidence(ins))
    if conf == "High":
        return value * 0.85, value * 1.05
    if conf == "Medium":
        return value * 0.60, value * 1.15
    return value * 0.35, value * 1.35


def _why_this_happening(ins: dict[str, Any]) -> list[str]:
    out: list[str] = []
    share_pct = _safe_float(ins.get("affected_revenue_share")) * 100.0
    if share_pct > 0:
        out.append(f"{share_pct:.1f}% of revenue in view is exposed to this issue.")
    discount_pct = _safe_float(ins.get("discount_rate")) * 100.0
    if discount_pct > 0:
        out.append(f"Current discount rate is {discount_pct:.1f}% in this campaign.")
    signal_val = _safe_float(ins.get("signal_value"))
    threshold = _safe_float(ins.get("threshold_value"))
    if signal_val > 0 and threshold > 0:
        out.append(f"Signal {signal_val:.2f} is beyond threshold {threshold:.2f}.")
    if not out:
        out.append(_safe_txt(ins.get("why_now"), 120, unicode_ok=False) or "Campaign structure is reducing profit capture.")
    return out[:2]


def _next_steps(ins: dict[str, Any]) -> list[str]:
    blob = f"{str(ins.get('signal_code') or '').upper()} {str(ins.get('title') or '').lower()}"
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


def _execution_score(ins: dict[str, Any]) -> float:
    impact = max(_executive_impact_numbers(ins))
    conf_w = {"High": 1.0, "Medium": 0.75, "Low": 0.5}.get(_confidence(ins), 0.6)
    speed_w = {"3-7 days": 1.0, "7-14 days": 0.8, "14-30 days": 0.55, "30+ days": 0.35}.get(_time_to_impact(ins), 0.6)
    return impact * conf_w * speed_w


def _execution_plan(insights: list[dict[str, Any]]) -> list[dict[str, str]]:
    merged: dict[str, dict[str, Any]] = {}
    for ins in insights:
        title = _decision_title(ins)
        key = title.lower().strip()
        impact_val = max(_executive_impact_numbers(ins))
        if impact_val <= 0:
            continue
        if key not in merged:
            merged[key] = {
                "title": title,
                "type": _decision_type(ins),
                "impact_value": impact_val,
                "time_to_impact": _time_to_impact(ins),
                "confidence": _confidence(ins),
                "decision": _executive_action(ins),
                "why": _why_this_happening(ins),
                "steps": _next_steps(ins),
                "category": _decision_category(ins),
            }
        else:
            cur = merged[key]
            cur["impact_value"] = float(cur["impact_value"]) + impact_val
            if _confidence(ins) == "High":
                cur["confidence"] = "High"
            elif _confidence(ins) == "Medium" and cur["confidence"] == "Low":
                cur["confidence"] = "Medium"
            if _time_to_impact(ins) == "3-7 days":
                cur["time_to_impact"] = "3-7 days"
            why = list(cur["why"])
            for line in _why_this_happening(ins):
                if line not in why:
                    why.append(line)
            cur["why"] = why[:2]

    ordered = sorted(
        merged.values(),
        key=lambda x: -(
            float(x["impact_value"])
            * {"High": 1.0, "Medium": 0.75, "Low": 0.5}.get(str(x["confidence"]), 0.6)
            / {"3-7 days": 1.0, "7-14 days": 1.35, "14-30 days": 1.8, "30+ days": 2.4}.get(str(x["time_to_impact"]), 1.5)
        ),
    )
    slots = [
        ("#1 Quick Win (<7 days)", {"3-7 days"}),
        ("#2 Growth Lever (7-14 days)", {"7-14 days"}),
        ("#3 Strategic / Risk Control (longer-term)", {"14-30 days", "30+ days"}),
    ]
    plan: list[dict[str, str]] = []
    used: set[int] = set()
    for slot, allowed in slots:
        pick_idx = next((i for i, ins in enumerate(ordered) if i not in used and _time_to_impact(ins) in allowed), None)
        if pick_idx is None:
            pick_idx = next((i for i in range(len(ordered)) if i not in used), None)
        if pick_idx is None:
            break
        used.add(pick_idx)
        ins = ordered[pick_idx]
        low, high = _confidence_adjusted_range(ins)
        plan.append(
            {
                "slot": slot,
                "type": str(ins["type"]),
                "title": str(ins["title"]),
                "decision": str(ins["decision"]),
                "impact": f"{_fmt_money(low)}-{_fmt_money(high)}",
                "time_to_impact": str(ins["time_to_impact"]),
                "confidence": str(ins["confidence"]),
                "urgency": _urgency_label(str(ins["time_to_impact"])),
                "category": str(ins["category"]),
                "why": " ".join(ins["why"]),
                "steps": " | ".join([f"{i+1}) {s}" for i, s in enumerate(ins["steps"])]),
            }
        )
    return plan


def _unique_actions(insights: list[dict[str, Any]], limit: int = 3) -> list[str]:
    """Return distinct action lines while preserving first-seen rank order."""
    out: list[str] = []
    seen: set[str] = set()
    for ins in insights:
        action = _executive_action(ins).strip()
        key = action.lower()
        if not action or key in seen:
            continue
        seen.add(key)
        out.append(action)
        if len(out) >= limit:
            break
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
        out.append(
            {
                "days_left": f"D-{(evt - d0).days}",
                "date": evt.strftime("%Y-%m-%d"),
                "name": name,
                "focus": focus,
                "do_now": do_now,
                "success_check": "Success check: margin % does not drop, net revenue grows, CAC stays in target, refund rate does not spike.",
            }
        )
    out.sort(key=lambda x: x["date"])
    return out[:limit]


def _build_reportlab_executive_pdf_bytes(
    *,
    upload_id: int,
    summary_rows: list[dict[str, Any]],
    enriched_insights: list[dict[str, Any]],
    risks_rows: list[dict[str, Any]],
    opp_summary: dict[str, Any],
    signal_desc_fn: Callable[[str | None], str],
) -> bytes:
    """Decision-focused PDF layout for executives."""
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    sorted_ins = _executive_sorted(enriched_insights)
    execution_plan = _execution_plan(sorted_ins)
    top3 = execution_plan[:3]
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    s_title = ParagraphStyle("ex_title", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=22)
    s_h2 = ParagraphStyle("ex_h2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15)
    s_txt = ParagraphStyle("ex_txt", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12)
    s_money = ParagraphStyle("ex_money", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=14, leading=17)
    s_impact = ParagraphStyle("ex_impact", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=13)

    story: list[Any] = []
    logo = _logo_path()
    if logo is not None:
        try:
            logo_w_mm, logo_h_mm = _logo_draw_size_mm(logo)
            logo_img = Image(str(logo), width=logo_w_mm * mm, height=logo_h_mm * mm)
            logo_img.hAlign = "CENTER"
            story.append(logo_img)
            story.append(Spacer(1, 4))
        except Exception:
            pass
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story.append(Paragraph("NosaProfit - Campaigns report", s_title))
    story.append(Paragraph(f"Upload ID: {upload_id} | Generated: {ts}", s_txt))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Profit summary", s_h2))
    story.append(Paragraph(f"{_fmt_money((opp_summary or {}).get('total_estimated_loss'))} at risk", s_money))
    story.append(Paragraph(f"{_fmt_money((opp_summary or {}).get('total_opportunity_size'))} opportunity", s_money))
    short_term = sum(max(_executive_impact_numbers(ins)) for ins in sorted_ins if _time_to_impact(ins) == "3-7 days")
    mid_term = sum(max(_executive_impact_numbers(ins)) for ins in sorted_ins if _time_to_impact(ins) in {"7-14 days", "14-30 days"})
    story.append(Paragraph(f"Short-term recoverable profit: {_fmt_money(short_term)}", s_txt))
    story.append(Paragraph(f"Mid-term growth potential: {_fmt_money(mid_term)}", s_txt))
    story.append(Paragraph(f"Top campaign: {_safe_txt((opp_summary or {}).get('top_priority_campaign', '-'), 50, unicode_ok=False)}", s_txt))
    story.append(Spacer(1, 8))

    recover_7d = 0.0
    grow_14d = 0.0
    risk_reduce = 0.0
    total_30 = 0.0
    for row in top3:
        imp = str(row.get("impact") or "$0.00-$0.00")
        nums = [p for p in imp.replace("$", "").split("-") if p.strip()]
        hi = 0.0
        if nums:
            try:
                hi = float(nums[-1].replace(",", ""))
            except ValueError:
                hi = 0.0
        total_30 += hi
        if row.get("time_to_impact") == "3-7 days":
            recover_7d += hi
        if row.get("time_to_impact") == "7-14 days":
            grow_14d += hi
        if row.get("type") == "RISK":
            risk_reduce += hi
    story.append(Paragraph("Execution impact if you act now", s_h2))
    exec_rows = [
        ["Recover (0-7 days)", "Grow (7-14 days)", "Reduce risk", "Total impact (30 days)"],
        [_fmt_money(recover_7d), _fmt_money(grow_14d), _fmt_money(risk_reduce), _fmt_money(total_30)],
    ]
    exec_t = Table(exec_rows, colWidths=[42 * mm, 42 * mm, 42 * mm, 42 * mm], repeatRows=1)
    exec_t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f3f5")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTSIZE", (0, 1), (-1, 1), 11),
                ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#111827")),
                ("ALIGN", (0, 1), (-1, 1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(exec_t)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Top profit decisions", s_h2))
    decision_meta_style = ParagraphStyle(
        "decision_meta",
        parent=s_txt,
        fontName="Helvetica",
        fontSize=8,
        leading=10,
    )
    for i, row in enumerate(top3, start=1):
        card_rows = [
            [Paragraph(f"<b>#{i} {_safe_txt(row.get('title'), 90, unicode_ok=False)}</b>", s_txt)],
            [Paragraph(f"<b>Expected impact:</b> {_safe_txt(row.get('impact'), 40, unicode_ok=False)}", s_impact)],
            [Paragraph(
                f"<b>Type:</b> {_safe_txt(row.get('type'), 12, unicode_ok=False)} | "
                f"<b>Time:</b> {_safe_txt(row.get('time_to_impact'), 16, unicode_ok=False)} | "
                f"<b>Confidence:</b> {_safe_txt(row.get('confidence'), 10, unicode_ok=False)} | "
                f"<b>When to act:</b> {_safe_txt(row.get('urgency'), 24, unicode_ok=False)}",
                decision_meta_style,
            )],
            [Paragraph(f"<b>Why:</b> {_safe_txt(row.get('why'), 220, unicode_ok=False)}", s_txt)],
            [Paragraph(f"<b>Decision:</b> {_safe_txt(row.get('decision'), 220, unicode_ok=False)}", s_txt)],
            [Paragraph(f"<b>What to do next:</b> {_safe_txt(row.get('steps'), 260, unicode_ok=False)}", s_txt)],
        ]
        card_t = Table(card_rows, colWidths=[168 * mm])
        card_t.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8f9fa")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(card_t)
        story.append(Spacer(1, 5))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Priority execution plan", s_h2))
    plan_rows = [["Slot", "Type", "Decision", "Impact", "Time", "Conf.", "When to act"]]
    for row in execution_plan:
        plan_rows.append(
            [
                Paragraph(_safe_txt(row["slot"], 36, unicode_ok=False), s_txt),
                Paragraph(_safe_txt(row["type"], 14, unicode_ok=False), s_txt),
                Paragraph(_safe_txt(row["decision"], 160, unicode_ok=False), s_txt),
                Paragraph(_safe_txt(row["impact"], 50, unicode_ok=False), s_txt),
                Paragraph(_safe_txt(row["time_to_impact"], 16, unicode_ok=False), s_txt),
                Paragraph(_safe_txt(row["confidence"], 10, unicode_ok=False), s_txt),
                Paragraph(_safe_txt(row["urgency"], 24, unicode_ok=False), s_txt),
            ]
        )
    plan_t = Table(
        plan_rows,
        # Rebalance widths to prevent header/body overlap on Conf./Urgency.
        colWidths=[24 * mm, 14 * mm, 54 * mm, 24 * mm, 16 * mm, 20 * mm, 20 * mm],
        repeatRows=1,
    )
    plan_t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f3f5")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("ALIGN", (4, 1), (6, -1), "CENTER"),
            ]
        )
    )
    story.append(plan_t)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Upcoming special dates", s_h2))
    cal_cell_style = ParagraphStyle(
        "ex_calendar_cell",
        parent=s_txt,
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        wordWrap="LTR",
    )
    cal_rows = [["Countdown", "Date", "Event", "Business goal", "What to do", "Success check"]]
    for ev in _upcoming_campaign_calendar(limit=5):
        cal_rows.append(
            [
                _safe_txt(ev.get("days_left"), 10, unicode_ok=False),
                _safe_txt(ev.get("date"), 14, unicode_ok=False),
                Paragraph(_safe_txt(ev.get("name"), 60, unicode_ok=False), cal_cell_style),
                Paragraph(_safe_txt(ev.get("focus"), 90, unicode_ok=False), cal_cell_style),
                Paragraph(_safe_txt(ev.get("do_now"), 140, unicode_ok=False), cal_cell_style),
                Paragraph(_safe_txt(ev.get("success_check"), 120, unicode_ok=False), cal_cell_style),
            ]
        )
    cal_t = Table(cal_rows, colWidths=[16 * mm, 20 * mm, 30 * mm, 36 * mm, 47 * mm, 33 * mm], repeatRows=1)
    cal_t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f3f5")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(cal_t)
    story.append(Spacer(1, 8))

    story.append(
        Paragraph(
            "Method note: 'Measured' uses direct metric values. 'Estimated (proxy)' uses deterministic formulas from campaign metrics (discount/AOV/growth/exposure).",
            s_txt,
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("Appendix - full decision list (grouped)", s_h2))
    insight_rows = [["#", "Category", "Campaign", "Decision", "Impact", "Type", "Time", "Confidence"]]
    cell_style = ParagraphStyle(
        "ex_cell",
        parent=s_txt,
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        wordWrap="LTR",
    )
    basis_style = ParagraphStyle(
        "ex_basis_cell",
        parent=s_txt,
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        wordWrap="LTR",
    )
    grouped_sorted = sorted(sorted_ins, key=lambda x: (_decision_category(x), -_execution_score(x)))
    for i, ins in enumerate(grouped_sorted, start=1):
        insight_rows.append(
            [
                str(i),
                _safe_txt(_decision_category(ins), 18, unicode_ok=False),
                _safe_txt(ins.get("campaign"), 14, unicode_ok=False),
                Paragraph(_safe_txt(_decision_title(ins), 180, unicode_ok=False), cell_style),
                Paragraph(_safe_txt(_executive_action(ins), 180, unicode_ok=False), cell_style),
                Paragraph(_safe_txt(f"{_fmt_money(_confidence_adjusted_range(ins)[0])}-{_fmt_money(_confidence_adjusted_range(ins)[1])}", 120, unicode_ok=False), cell_style),
                Paragraph(_safe_txt(_decision_type(ins), 18, unicode_ok=False), basis_style),
                Paragraph(_safe_txt(_time_to_impact(ins), 20, unicode_ok=False), basis_style),
                Paragraph(_safe_txt(_confidence(ins), 16, unicode_ok=False), basis_style),
            ]
        )
    insight_table = Table(
        insight_rows,
        colWidths=[7 * mm, 24 * mm, 16 * mm, 40 * mm, 44 * mm, 20 * mm, 14 * mm, 14 * mm, 14 * mm],
        repeatRows=1,
    )
    insight_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f3f5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for ridx in range(1, len(insight_rows)):
        if ridx % 2 == 0:
            insight_style.append(("BACKGROUND", (0, ridx), (-1, ridx), colors.HexColor("#fcfcfd")))
    insight_table.setStyle(TableStyle(insight_style))
    story.append(insight_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Appendix - campaign summary table", s_h2))
    reason_map: dict[str, list[str]] = {}
    for rr in risks_rows:
        campaign_key = str(rr.get("campaign") or "").strip()
        if not campaign_key:
            continue
        code = _safe_txt(rr.get("signal_code"), 40, unicode_ok=False)
        reason = _safe_txt(signal_desc_fn(code), 200, unicode_ok=False).strip()
        if not reason:
            continue
        bucket = reason_map.setdefault(campaign_key, [])
        if reason not in bucket:
            bucket.append(reason)
    summary_reason_style = ParagraphStyle(
        "summary_reason_cell",
        parent=s_txt,
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        wordWrap="LTR",
    )
    rows = [["Campaign", "Orders", "Gross", "Net", "Discount %", "AOV", "Risk", "Reason"]]
    for r in summary_rows:
        raw_campaign_key = str(r.get("campaign") or "").strip()
        campaign = _safe_txt(r.get("campaign"), 20, unicode_ok=False)
        risk_level = _safe_txt(r.get("risk_level"), 10, unicode_ok=False)
        reasons = reason_map.get(raw_campaign_key, [])
        if reasons:
            reason_text = "; ".join(reasons[:2])
        else:
            level = str(r.get("risk_level") or "").strip().lower()
            if level in {"high", "critical"}:
                reason_text = "High risk based on threshold breaches in current window"
            elif level in {"medium", "moderate"}:
                reason_text = "Medium risk due to near-threshold performance signals"
            else:
                reason_text = "-"
        rows.append(
            [
                campaign,
                str(int(r.get("orders") or 0)),
                _fmt_money(r.get("revenue")),
                _fmt_money(r.get("net_revenue")),
                f"{_safe_float(r.get('discount_rate')) * 100.0:.1f}%",
                _fmt_money(r.get("aov")),
                risk_level,
                Paragraph(_safe_txt(reason_text, 220, unicode_ok=False), summary_reason_style),
            ]
        )
    t = Table(
        rows,
        colWidths=[26 * mm, 12 * mm, 20 * mm, 20 * mm, 14 * mm, 14 * mm, 12 * mm, 64 * mm],
        repeatRows=1,
    )
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f3f5")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(t)
    if risks_rows:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Appendix - high-severity signals", s_h2))
        risk_cell_style = ParagraphStyle(
            "risk_cell",
            parent=s_txt,
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            wordWrap="LTR",
        )
        s_rows = [["Campaign", "Signal description", "Value", "Threshold", "Entity"]]
        for r in risks_rows:
            code = _safe_txt(r.get("signal_code"), 34, unicode_ok=False)
            s_rows.append(
                [
                    _safe_txt(r.get("campaign"), 18, unicode_ok=False),
                    Paragraph(_safe_txt(signal_desc_fn(code), 260, unicode_ok=False), risk_cell_style),
                    f"{_safe_float(r.get('signal_value')):.2f}",
                    f"{_safe_float(r.get('threshold_value')):.2f}",
                    _safe_txt(r.get("entity_type"), 14, unicode_ok=False),
                ]
            )
        s_table = Table(
            s_rows,
            colWidths=[24 * mm, 102 * mm, 14 * mm, 18 * mm, 14 * mm],
            repeatRows=1,
        )
        s_table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f3f5")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ALIGN", (2, 1), (3, -1), "RIGHT"),
            ("ALIGN", (4, 1), (4, -1), "CENTER"),
        ]
        for ridx in range(1, len(s_rows)):
            if ridx % 2 == 0:
                s_table_style.append(("BACKGROUND", (0, ridx), (-1, ridx), colors.HexColor("#fcfcfd")))
        s_table.setStyle(TableStyle(s_table_style))
        story.append(s_table)
    def _draw_footer(canvas: Any, doc_obj: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColorRGB(0.47, 0.47, 0.47)
        canvas.drawCentredString(A4[0] / 2, 8 * mm, _BRAND_FOOTER)
        canvas.restoreState()

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buf.getvalue()


def build_campaigns_pdf_bytes(
    *,
    upload_id: int,
    summary_rows: list[dict[str, Any]],
    enriched_insights: list[dict[str, Any]],
    risks_rows: list[dict[str, Any]],
    opp_summary: dict[str, Any],
    signal_label_fn: Callable[[str | None], tuple[str, str]],
    signal_desc_fn: Callable[[str | None], str],
) -> bytes:
    """Build a multi-section PDF report; safe on empty lists."""
    try:
        return _build_reportlab_executive_pdf_bytes(
            upload_id=upload_id,
            summary_rows=summary_rows,
            enriched_insights=enriched_insights,
            risks_rows=risks_rows,
            opp_summary=opp_summary,
            signal_desc_fn=signal_desc_fn,
        )
    except Exception:
        pass

    if not _HAS_FPDF:
        try:
            return _build_reportlab_pdf_bytes(
                upload_id=upload_id,
                summary_rows=summary_rows,
                enriched_insights=enriched_insights,
                risks_rows=risks_rows,
                opp_summary=opp_summary,
            )
        except Exception:
            return _build_minimal_pdf_bytes(
                upload_id=upload_id,
                summary_rows=summary_rows,
                enriched_insights=enriched_insights,
                risks_rows=risks_rows,
                opp_summary=opp_summary,
            )
    try:
        pdf = _CampaignsPDF()
        ff = pdf._ffam
        unicode_ok = bool(getattr(pdf, "_unicode_ok", False))
        pdf.alias_nb_pages()
        pdf.add_page()
        logo = _logo_path()
        if logo is not None:
            try:
                logo_w_mm, logo_h_mm = _logo_draw_size_mm(logo)
                y0 = pdf.get_y()
                pdf.image(str(logo), x=(pdf.w - logo_w_mm) / 2.0, y=y0, w=logo_w_mm, h=logo_h_mm)
                pdf.set_y(y0 + logo_h_mm + 2.0)
            except Exception:
                pass

        pdf.set_font(ff, "B", 16)
        pdf.cell(0, 10, "NosaProfit - Campaigns report", ln=1)
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
                f"Insights counted: {opp_summary.get('insight_count', '-')}",
                ln=1,
            )
            pdf.ln(2)

        # --- Summary table ---
        pdf.set_font(ff, "B", 12)
        pdf.cell(0, 8, "Summary by campaign", ln=1)
        pdf.set_font(ff, "", 8)
        # Keep table width safely below page effective width.
        col_w = (34, 18, 24, 24, 20, 18, 26)
        headers = ("Campaign", "Orders", "Gross rev.", "Net rev.", "Disc. %", "AOV", "Risk")
        pdf.set_fill_color(240, 242, 247)
        for i, h in enumerate(headers):
            pdf.cell(col_w[i], 7, h, border=1, fill=True)
        pdf.ln()
        pdf.set_font(ff, "", 8)
        for row in summary_rows:
            if pdf.get_y() > 270:
                pdf.add_page()
            camp = _safe_txt(row.get("campaign"), 32, unicode_ok=unicode_ok)
            orders = str(int(row.get("orders") or 0))
            gross = _fmt_money(row.get("revenue"))
            net = _fmt_money(row.get("net_revenue"))
            dr = float(row.get("discount_rate") or 0.0) * 100.0
            disc = f"{dr:.1f}%"
            aov = _fmt_money(row.get("aov"))
            risk = _safe_txt(row.get("risk_level"), 10, unicode_ok=unicode_ok)
            vals = (camp, orders, gross, net, disc, aov, risk)
            for i, v in enumerate(vals):
                pdf.cell(col_w[i], 6, _safe_txt(v, 44, unicode_ok=unicode_ok), border=1)
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
            rw = (20, 38, 28, 14, 16, 16, 22)
            rh = ("Campaign", "Signal", "Code", "Sev", "Value", "Thr", "Entity")
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
                    _safe_txt(r.get("campaign"), 18, unicode_ok=unicode_ok),
                    _safe_txt(plab, 30, unicode_ok=unicode_ok),
                    _safe_txt(code, 22, unicode_ok=unicode_ok),
                    _safe_txt(r.get("severity"), 10, unicode_ok=unicode_ok),
                    _safe_txt(f"{float(r.get('signal_value') or 0):.2f}", 12, unicode_ok=unicode_ok),
                    _safe_txt(f"{float(r.get('threshold_value') or 0):.2f}", 12, unicode_ok=unicode_ok),
                    _safe_txt(r.get("entity_type"), 16, unicode_ok=unicode_ok),
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
        for idx, ins in enumerate(sorted_ins, start=1):
            if pdf.get_y() > 245:
                pdf.add_page()
            pdf.set_font(ff, "B", 10)
            rank = ins.get("rank", idx)
            camp = _safe_txt(ins.get("campaign"), 24, unicode_ok=unicode_ok)
            title = _safe_txt(ins.get("title"), 80, unicode_ok=unicode_ok)
            pdf.multi_cell(0, 5, _safe_txt(f"#{rank} - {camp} - {title}", 170, unicode_ok=unicode_ok))
            pdf.set_font(ff, "", 9)
            sc = str(ins.get("signal_code") or "")
            slab, _ = signal_label_fn(sc)
            line = (
                f"Priority: {ins.get('priority', '-')} | Category: {ins.get('category', '-')} | "
                f"Signal: {slab} ({sc})"
            )
            pdf.multi_cell(0, 4, _safe_txt(line, 160, unicode_ok=unicode_ok))
            pdf.multi_cell(
                0,
                4,
                _safe_txt(
                    f"Impacted: {_fmt_money(ins.get('impacted_revenue'))} | "
                    f"Loss: {_fmt_money(ins.get('estimated_loss'))} | "
                    f"Opp: {_fmt_money(ins.get('opportunity_size'))} | "
                    f"Share: {float(ins.get('affected_revenue_share') or 0) * 100:.1f}% | "
                    f"Score: {ins.get('priority_score', '-')}",
                    190,
                    unicode_ok=unicode_ok,
                ),
            )
            impact = ins.get("estimated_impact_text")
            if impact:
                pdf.set_font(ff, "", 9)
                pdf.multi_cell(0, 4, _safe_txt(f"Impact: {impact}", 190, unicode_ok=unicode_ok))
            why = ins.get("why_now")
            if why:
                pdf.multi_cell(0, 4, _safe_txt(f"Why now: {why}", 240, unicode_ok=unicode_ok))
            pdf.ln(1)
            pdf.set_draw_color(220, 220, 230)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(2)

        raw = pdf.output(dest="S")
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw)
        return str(raw).encode("latin-1", errors="replace")
    except Exception:
        # Never bubble PDF rendering issues to Streamlit page.
        return _build_minimal_pdf_bytes(
            upload_id=upload_id,
            summary_rows=summary_rows,
            enriched_insights=enriched_insights,
            risks_rows=risks_rows,
            opp_summary=opp_summary,
        )
